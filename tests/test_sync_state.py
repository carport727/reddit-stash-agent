import json

from app.runtime import sync_state


def test_lifecycle():
    with sync_state.sync_lock():
        sync_state.mark_running("api", 4, "/logs/x.log")
        sync_state.mark_step(3, "Download", {"posts_new": 2})
        status = sync_state.read_status()
        assert status["running"] is True
        assert status["step_label"] == "Download"
        assert status["progress"] == 0.5
        sync_state.mark_finished("success", summary={"posts_new": 2})

    status = sync_state.read_status()
    assert status["running"] is False
    assert status["last_result"] == "success"
    assert status["progress"] == 1.0
    assert status["summary"] == {"posts_new": 2}


def test_dead_sync_reported_as_interrupted():
    with open(sync_state.STATUS_FILE) as f:
        data = json.load(f)
    data.update(last_result="running", pid=12345)
    sync_state.write_status(data)

    status = sync_state.read_status()
    assert status["last_result"] == "interrupted"
    assert status["pid"] is None


def test_lock_is_exclusive():
    with sync_state.sync_lock():
        assert sync_state.is_sync_running()
        try:
            with sync_state.sync_lock():
                raise AssertionError("second lock acquired")
        except sync_state.SyncAlreadyRunning:
            pass
    assert not sync_state.is_sync_running()
