import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import __version__
from app.runtime import runner
from app.runtime.sync_state import read_status
from app.settings import DATA_DIR, load_config

SCHEDULER_CONFIG_FILE = os.path.join(DATA_DIR, "scheduler-config.json")
JOB_ID = "reddit-sync"
# First automatic run after enabling, when no sync ever ran.
FIRST_RUN_DELAY = timedelta(minutes=5)
# An overdue run (e.g. after a restart) starts this long after startup.
OVERDUE_RUN_DELAY = timedelta(minutes=1)

config = load_config()
scheduler = BackgroundScheduler(timezone="UTC")


class SchedulerConfig(BaseModel):
    enabled: bool = False
    interval_hours: float = Field(default=6, gt=0)


def load_scheduler_config():
    data = {"enabled": False, "interval_hours": 6.0}
    try:
        with open(SCHEDULER_CONFIG_FILE) as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    return data


def save_scheduler_config(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp_file = SCHEDULER_CONFIG_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_file, SCHEDULER_CONFIG_FILE)


def _parse_time(value):
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def compute_next_run(interval, last_started_at, now=None):
    """Next run based on the last sync, so restarts and config pushes never postpone it."""
    now = now or datetime.now(UTC)
    if last_started_at is None:
        return now + FIRST_RUN_DELAY

    candidate = last_started_at + interval
    return max(candidate, now + OVERDUE_RUN_DELAY) if candidate < now else candidate


def scheduled_sync():
    try:
        result = runner.start_sync("scheduler", wait=True)
        print(f"Scheduled sync finished with exit code {result['exit_code']}", flush=True)
    except runner.AlreadyRunning:
        print("Scheduled sync skipped: sync already running", flush=True)


def apply_scheduler_config(data):
    """(Re)schedule the job. Does nothing when the job already matches the config."""
    job = scheduler.get_job(JOB_ID)

    if not data["enabled"]:
        if job:
            scheduler.remove_job(JOB_ID)
        return

    interval = timedelta(hours=float(data["interval_hours"]))
    if job and job.trigger.interval == interval:
        return

    last_started = _parse_time(read_status().get("last_started_at"))
    next_run = compute_next_run(interval, last_started)

    scheduler.add_job(
        scheduled_sync,
        trigger=IntervalTrigger(seconds=interval.total_seconds(), start_date=next_run, timezone="UTC"),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )


def get_scheduler_status():
    data = load_scheduler_config()
    job = scheduler.get_job(JOB_ID)
    next_run_at = job.next_run_time.astimezone(UTC).isoformat() if job and job.next_run_time else None
    return {
        "enabled": bool(data["enabled"]),
        "interval_hours": float(data["interval_hours"]),
        "next_run_at": next_run_at,
    }


def require_token(authorization: str | None = Header(default=None)):
    token = config["agent"]["token"]
    if not token:
        return
    if not hmac.compare_digest((authorization or "").encode(), f"Bearer {token}".encode()):
        raise HTTPException(status_code=401, detail="Missing or wrong API token")


@asynccontextmanager
async def lifespan(app):
    if not config["agent"]["token"]:
        print("WARNING: AGENT_TOKEN is not set; the API is open to everyone who can reach this port.", flush=True)

    scheduler.start()
    try:
        apply_scheduler_config(load_scheduler_config())
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Reddit Stash Agent API", version=__version__, lifespan=lifespan)
api = [Depends(require_token)]


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "reddit-stash-agent",
        "version": __version__,
        "auth_required": bool(config["agent"]["token"]),
    }


@app.get("/api/status", dependencies=api)
def get_status():
    result = read_status()
    result["scheduler"] = get_scheduler_status()
    result["version"] = __version__
    return result


@app.get("/api/config", dependencies=api)
def get_config():
    return get_scheduler_status()


@app.put("/api/config", dependencies=api)
def update_config(new_config: SchedulerConfig):
    data = {"enabled": new_config.enabled, "interval_hours": float(new_config.interval_hours)}
    save_scheduler_config(data)
    apply_scheduler_config(data)
    return get_scheduler_status()


@app.post("/api/sync", status_code=status.HTTP_202_ACCEPTED, dependencies=api)
def start_sync():
    try:
        result = runner.start_sync("api")
    except runner.AlreadyRunning:
        raise HTTPException(status_code=409, detail="Sync already running") from None
    except runner.StartError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None

    return {"accepted": True, "pid": result["pid"], "message": "Sync started"}


@app.post("/api/sync/cancel", status_code=status.HTTP_202_ACCEPTED, dependencies=api)
def cancel_sync():
    if not runner.cancel_sync():
        raise HTTPException(status_code=409, detail="No sync running that this agent can cancel")
    return {"accepted": True, "message": "Cancel requested"}


@app.get("/api/logs", dependencies=api)
def get_logs(lines: int = Query(default=200, ge=1, le=5000)):
    log_file = read_status().get("log_file")
    return {"log_file": log_file, "lines": runner.tail(log_file, lines).splitlines()}
