import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone


DATA_DIR = os.environ.get(
    "DATA_DIR",
    "/data",
)

STATUS_FILE = os.path.join(
    DATA_DIR,
    "sync-status.json",
)

LOCK_FILE = os.path.join(
    DATA_DIR,
    "sync.lock",
)


class SyncAlreadyRunning(Exception):
    pass


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def read_status():
    default = {
        "running": False,
        "last_result": None,
        "last_trigger": None,
        "last_started_at": None,
        "last_finished_at": None,
        "last_error": None,
    }

    if not os.path.exists(
        STATUS_FILE
    ):
        return default

    try:
        with open(
            STATUS_FILE,
            "r",
        ) as f:
            data = json.load(f)

        default.update(data)

    except Exception:
        pass

    default["running"] = (
        is_sync_running()
    )

    return default


def write_status(data):
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    temp_file = (
        STATUS_FILE + ".tmp"
    )

    with open(
        temp_file,
        "w",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
        )

    os.replace(
        temp_file,
        STATUS_FILE,
    )


def mark_running(trigger):
    status = read_status()

    status.update(
        {
            "running": True,
            "last_result": "running",
            "last_trigger": trigger,
            "last_started_at": utc_now(),
            "last_finished_at": None,
            "last_error": None,
        }
    )

    write_status(status)


def mark_finished(
    result,
    error=None,
):
    status = read_status()

    status.update(
        {
            "running": False,
            "last_result": result,
            "last_finished_at": utc_now(),
            "last_error": error,
        }
    )

    write_status(status)


def is_sync_running():
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    lock_file = open(
        LOCK_FILE,
        "a+",
    )

    try:
        fcntl.flock(
            lock_file,
            fcntl.LOCK_EX
            | fcntl.LOCK_NB,
        )

        fcntl.flock(
            lock_file,
            fcntl.LOCK_UN,
        )

        return False

    except BlockingIOError:
        return True

    finally:
        lock_file.close()


@contextmanager
def sync_lock():
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    lock_file = open(
        LOCK_FILE,
        "a+",
    )

    try:
        try:
            fcntl.flock(
                lock_file,
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )

        except BlockingIOError:
            raise SyncAlreadyRunning()

        yield

    finally:
        try:
            fcntl.flock(
                lock_file,
                fcntl.LOCK_UN,
            )

        except Exception:
            pass

        lock_file.close()
