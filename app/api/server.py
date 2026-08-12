import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.runtime.sync_state import (
    is_sync_running,
    read_status,
)


DATA_DIR = os.environ.get(
    "DATA_DIR",
    "/data",
)

SCHEDULER_CONFIG_FILE = os.path.join(
    DATA_DIR,
    "scheduler-config.json",
)

SCHEDULED_LOG_FILE = (
    "/logs/scheduled-sync.log"
)

JOB_ID = "reddit-sync"


class SchedulerConfig(BaseModel):
    enabled: bool = False
    interval_hours: float = 6


scheduler = BackgroundScheduler(
    timezone="UTC",
)


def load_scheduler_config():
    default = {
        "enabled": False,
        "interval_hours": 6.0,
    }

    if not os.path.exists(
        SCHEDULER_CONFIG_FILE
    ):
        return default

    try:
        with open(
            SCHEDULER_CONFIG_FILE,
            "r",
        ) as f:
            data = json.load(f)

        default.update(data)

    except Exception:
        pass

    return default


def save_scheduler_config(config):
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    temp_file = (
        SCHEDULER_CONFIG_FILE
        + ".tmp"
    )

    with open(
        temp_file,
        "w",
    ) as f:
        json.dump(
            config,
            f,
            indent=2,
        )

    os.replace(
        temp_file,
        SCHEDULER_CONFIG_FILE,
    )


def scheduled_sync():
    if is_sync_running():
        print(
            "Scheduled sync skipped: "
            "sync already running"
        )
        return

    os.makedirs(
        "/logs",
        exist_ok=True,
    )

    env = os.environ.copy()
    env["SYNC_TRIGGER"] = (
        "scheduler"
    )

    with open(
        SCHEDULED_LOG_FILE,
        "a",
    ) as log_file:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "app.main",
                "sync",
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
        )


def apply_scheduler_config(config):
    existing = scheduler.get_job(
        JOB_ID
    )

    if existing:
        scheduler.remove_job(
            JOB_ID
        )

    if not config["enabled"]:
        return

    interval_hours = float(
        config["interval_hours"]
    )

    if interval_hours <= 0:
        raise ValueError(
            "interval_hours must be "
            "greater than 0"
        )

    scheduler.add_job(
        scheduled_sync,
        trigger="interval",
        hours=interval_hours,
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def get_scheduler_status():
    config = load_scheduler_config()

    job = scheduler.get_job(
        JOB_ID
    )

    next_run_at = None

    if (
        job
        and job.next_run_time
    ):
        next_run_at = (
            job.next_run_time
            .astimezone(
                timezone.utc
            )
            .isoformat()
        )

    return {
        "enabled":
            bool(
                config["enabled"]
            ),
        "interval_hours":
            float(
                config[
                    "interval_hours"
                ]
            ),
        "next_run_at":
            next_run_at,
    }


@asynccontextmanager
async def lifespan(app):
    scheduler.start()

    try:
        apply_scheduler_config(
            load_scheduler_config()
        )

        yield

    finally:
        scheduler.shutdown(
            wait=False
        )


CONFIG_FILE = os.environ.get(
    "CONFIG_FILE",
    "/config/config.yaml",
)

with open(CONFIG_FILE) as f:
    config = yaml.safe_load(f)

stash_origin = (
    config["stash"]["url"]
    .rstrip("/")
)


app = FastAPI(
    title="Reddit Stash Agent API",
    version="0.4.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        stash_origin,
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service":
            "reddit-stash-agent",
    }


@app.get("/api/status")
def get_status():
    result = read_status()

    result["scheduler"] = (
        get_scheduler_status()
    )

    return result


@app.get("/api/config")
def get_config():
    return get_scheduler_status()


@app.put("/api/config")
def update_config(
    new_config: SchedulerConfig,
):
    if (
        new_config.interval_hours
        <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "interval_hours must "
                "be greater than 0"
            ),
        )

    config_data = {
        "enabled":
            new_config.enabled,
        "interval_hours":
            float(
                new_config
                .interval_hours
            ),
    }

    save_scheduler_config(
        config_data
    )

    apply_scheduler_config(
        config_data
    )

    return get_scheduler_status()


@app.post(
    "/api/sync",
    status_code=
        status.HTTP_202_ACCEPTED,
)
def start_sync():
    if is_sync_running():
        raise HTTPException(
            status_code=409,
            detail=(
                "Sync already running"
            ),
        )

    os.makedirs(
        "/logs",
        exist_ok=True,
    )

    log_path = (
        "/logs/api-sync.log"
    )

    env = os.environ.copy()
    env["SYNC_TRIGGER"] = "api"

    with open(
        log_path,
        "a",
    ) as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.main",
                "sync",
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

    return {
        "accepted": True,
        "pid": process.pid,
        "message": "Sync started",
    }
