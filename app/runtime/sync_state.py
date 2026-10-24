"""Shared state of the sync pipeline.

The sync process writes sync-status.json; the API server only reads it.
A flock on sync.lock guarantees a single sync, across processes and containers
that share the data volume.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime

from app.settings import DATA_DIR

STATUS_FILE = os.path.join(DATA_DIR, "sync-status.json")
LOCK_FILE = os.path.join(DATA_DIR, "sync.lock")


class SyncAlreadyRunning(Exception):
    pass


def utc_now():
    return datetime.now(UTC).isoformat()


def _default_status():
    return {
        "running": False,
        "pid": None,
        "last_result": None,
        "last_trigger": None,
        "last_started_at": None,
        "last_finished_at": None,
        "last_error": None,
        "step": 0,
        "step_count": 0,
        "step_label": None,
        "progress": 0.0,
        "log_file": None,
        "summary": {},
    }


def read_status():
    status = _default_status()

    try:
        with open(STATUS_FILE) as f:
            status.update(json.load(f))
    except (OSError, ValueError):
        pass

    status["running"] = is_sync_running()

    # The process died without reaching mark_finished (SIGKILL, container restart).
    if status["last_result"] == "running" and not status["running"]:
        status["last_result"] = "interrupted"
        status["pid"] = None

    return status


def write_status(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp_file = STATUS_FILE + ".tmp"

    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)

    os.replace(temp_file, STATUS_FILE)


def _update(**fields):
    status = read_status()
    status.update(fields)
    write_status(status)
    return status


def mark_running(trigger, step_count, log_file=None):
    _update(
        running=True,
        pid=os.getpid(),
        last_result="running",
        last_trigger=trigger,
        last_started_at=utc_now(),
        last_finished_at=None,
        last_error=None,
        step=0,
        step_count=step_count,
        step_label=None,
        progress=0.0,
        log_file=log_file,
        summary={},
    )


def mark_step(step, label, summary=None):
    status = read_status()
    step_count = status.get("step_count") or step
    _update(
        running=True,
        last_result="running",
        step=step,
        step_label=label,
        progress=round((step - 1) / step_count, 3),
        summary=summary if summary is not None else status.get("summary", {}),
    )


def mark_finished(result, error=None, summary=None):
    status = read_status()
    _update(
        running=False,
        pid=None,
        last_result=result,
        last_finished_at=utc_now(),
        last_error=error,
        step_label=None,
        progress=1.0 if result == "success" else status.get("progress", 0.0),
        summary=summary if summary is not None else status.get("summary", {}),
    )


def is_sync_running():
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(LOCK_FILE, "a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True

        fcntl.flock(lock_file, fcntl.LOCK_UN)
        return False


@contextmanager
def sync_lock():
    os.makedirs(DATA_DIR, exist_ok=True)
    lock_file = open(LOCK_FILE, "a+")

    try:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SyncAlreadyRunning() from None

        yield

    finally:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        except OSError:
            pass

        lock_file.close()
