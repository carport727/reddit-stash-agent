"""Start the sync pipeline as a separate process, with one log file per run."""

import glob
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime

from app.runtime.sync_state import is_sync_running, read_status
from app.settings import LOG_DIR

RUN_LOG_DIR = os.path.join(LOG_DIR, "runs")
KEEP_RUN_LOGS = 30


class StartError(Exception):
    pass


class AlreadyRunning(StartError):
    pass


def _prune_run_logs():
    logs = sorted(glob.glob(os.path.join(RUN_LOG_DIR, "*.log")))
    for path in logs[:-KEEP_RUN_LOGS]:
        try:
            os.remove(path)
        except OSError:
            pass


def start_sync(trigger, wait=False):
    """Spawn `python -m app.main sync`.

    wait=False returns once the child holds the sync lock (or failed to start).
    Raises AlreadyRunning when another sync holds the lock.
    """
    if is_sync_running():
        raise AlreadyRunning("Sync already running")

    os.makedirs(RUN_LOG_DIR, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_path = os.path.join(RUN_LOG_DIR, f"{stamp}-{trigger}.log")

    env = dict(os.environ, SYNC_TRIGGER=trigger, SYNC_LOG_FILE=log_path, PYTHONUNBUFFERED="1")

    with open(log_path, "a") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.main", "sync"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,  # own process group, so cancel can signal gallery-dl too
        )

    _prune_run_logs()

    if wait:
        process.wait()
        return {"pid": process.pid, "log_file": log_path, "exit_code": process.returncode}

    # Wait until the child either holds the lock or exits early.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            if code == 2:
                raise AlreadyRunning("Sync already running")
            if read_status().get("log_file") == log_path:
                # It started and already finished (or failed); the status has the result.
                break
            raise StartError(f"Sync exited immediately with code {code}: {tail(log_path, 5)}")
        if is_sync_running() and read_status().get("pid") == process.pid:
            break
        time.sleep(0.2)

    return {"pid": process.pid, "log_file": log_path}


def cancel_sync():
    """Send SIGTERM to the running sync's process group. Returns False if nothing to cancel."""
    status = read_status()
    pid = status.get("pid")
    if not status["running"] or not pid:
        return False

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Started from another container (docker compose run); its pid is not ours.
        return False
    return True


def tail(path, lines=200):
    if not path or not os.path.exists(path):
        return ""

    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 256 * 1024))
        data = f.read().decode("utf-8", errors="replace")

    return "\n".join(data.splitlines()[-lines:])
