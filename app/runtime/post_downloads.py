"""Single post downloads requested over the API.

They run one at a time in a worker thread of the API server, next to (not inside) the sync.
Jobs are kept in post-downloads.json, so callers can read the result after the request
(e.g. a Stash task, whose output nobody receives).
"""

import json
import os
import sys
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.database.database import init_db
from app.runtime.sync_state import utc_now
from app.settings import DATA_DIR

JOBS_FILE = os.path.join(DATA_DIR, "post-downloads.json")
KEEP_JOBS = 50
KEEP_LOG_LINES = 500
ACTIVE = ("queued", "running")

_lock = threading.Lock()
_events = {}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="post-download")
_db_ready = False


class _ThreadTee:
    """stdout that also copies lines printed by a download worker into its job log."""

    def __init__(self, stream):
        self.stream = stream
        self.sinks = {}

    def write(self, text):
        sink = self.sinks.get(threading.get_ident())
        if sink:
            sink(text)
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


_tee = None


def _install_tee():
    global _tee
    if _tee is None:
        _tee = _ThreadTee(sys.stdout)
        sys.stdout = _tee
    return _tee


def _read_jobs():
    try:
        with open(JOBS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _write_jobs(jobs):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp_file = JOBS_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(jobs[-KEEP_JOBS:], f, indent=2)
    os.replace(temp_file, JOBS_FILE)


def _update(job_id, **fields):
    with _lock:
        jobs = _read_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job.update(fields)
                _write_jobs(jobs)
                return job
    return None


def _append_log(job_id, text):
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return
    with _lock:
        jobs = _read_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job["log"] = (job.get("log") or []) + lines
                del job["log"][:-KEEP_LOG_LINES]
                _write_jobs(jobs)
                return


def get_job(job_id):
    return next((job for job in _read_jobs() if job["id"] == job_id), None)


def list_jobs(limit=20):
    return list(reversed(_read_jobs()))[:limit]


def last_job():
    """Newest job without its log, for /api/status."""
    jobs = _read_jobs()
    if not jobs:
        return None
    return {key: value for key, value in jobs[-1].items() if key != "log"}


def mark_interrupted():
    """Jobs that were queued or running when the server stopped."""
    with _lock:
        jobs = _read_jobs()
        changed = False
        for job in jobs:
            if job["status"] in ACTIVE:
                job.update(status="interrupted", finished_at=utc_now(), error="Agent restarted during the download")
                changed = True
        if changed:
            _write_jobs(jobs)


def submit(config, url, runner=None):
    """Queue a download, or return the queued/running job for the same link."""
    from app.commands import download_post

    runner = runner or download_post.run
    url = url.strip()

    with _lock:
        jobs = _read_jobs()
        for job in reversed(jobs):
            if job["url"] == url and job["status"] in ACTIVE:
                return job

        job = {
            "id": uuid.uuid4().hex[:12],
            "url": url,
            "status": "queued",
            "created_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "step": 0,
            "step_count": len(download_post.STEPS),
            "step_label": None,
            "progress": 0.0,
            "error": None,
            "error_code": None,
            "result": None,
            "log": [],
        }
        jobs.append(job)
        _write_jobs(jobs)
        _events[job["id"]] = threading.Event()

    _executor.submit(_run, config, job["id"], url, runner)
    return job


def wait(job_id, timeout):
    event = _events.get(job_id)
    if event:
        event.wait(timeout)
    return get_job(job_id)


def _run(config, job_id, url, runner):
    global _db_ready
    from app.commands.download_post import PostDownloadError

    pending = [""]

    def collect(text):
        # print() writes text and newline separately; store whole lines only.
        pending[0] += text
        if "\n" in pending[0]:
            complete, pending[0] = pending[0].rsplit("\n", 1)
            _append_log(job_id, complete)

    tee = _install_tee()
    tee.sinks[threading.get_ident()] = collect
    _update(job_id, status="running", started_at=utc_now())

    def on_step(index, label):
        step_count = get_job(job_id)["step_count"]
        _update(job_id, step=index, step_label=label, progress=round((index - 1) / step_count, 3))

    try:
        if not _db_ready:
            init_db(config["database"]["path"])
            _db_ready = True
        print(f"Post download {job_id}: {url}", flush=True)
        result = runner(config, url, on_step=on_step)
        _update(job_id, status="success", result=result, progress=1.0, step_label=None, finished_at=utc_now())
    except PostDownloadError as exc:
        print(f"Post download {job_id} failed ({exc.code}): {exc}", flush=True)
        _update(job_id, status="failed", error=str(exc), error_code=exc.code, finished_at=utc_now())
    except Exception as exc:
        traceback.print_exc(file=sys.stdout)
        _update(
            job_id, status="failed", error=f"{type(exc).__name__}: {exc}", error_code="internal", finished_at=utc_now()
        )
    finally:
        tee.sinks.pop(threading.get_ident(), None)
        _append_log(job_id, pending[0])
        event = _events.pop(job_id, None)
        if event:
            event.set()
