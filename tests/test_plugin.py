import importlib.util
import os

import pytest

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "plugins", "reddit-stash-agent", "reddit-stash-agent.py")
spec = importlib.util.spec_from_file_location("rsa_plugin", PLUGIN)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
plugin.POLL_SECONDS = 0


class FakeAgent:
    url = "http://agent"

    def __init__(self, statuses, start_error=None):
        self.statuses = list(statuses)
        self.start_error = start_error
        self.calls = []

    def request(self, path, method="GET", body=None, timeout=20):
        self.calls.append((method, path, body))
        if path == "/api/sync":
            if self.start_error:
                raise self.start_error
            return {"accepted": True}
        if path == "/api/status":
            return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if path.startswith("/api/logs"):
            return {"lines": ["boom"]}
        if path == "/api/config":
            return dict(body, next_run_at=None)
        if path == "/api/download":
            return self.statuses[0]
        if path.startswith("/api/download/"):
            return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        raise AssertionError(path)


def running(step):
    return {"running": True, "step": step, "step_count": 7, "step_label": f"s{step}", "progress": (step - 1) / 7}


def test_sync_task_follows_until_success(capsys):
    agent = FakeAgent([running(1), running(2), {"running": False, "last_result": "success", "summary": {"a": 1}}])
    result = plugin.run_mode("sync", agent, {}, as_task=True)

    assert result["last_result"] == "success"
    err = capsys.readouterr().err
    assert "\x01i\x02Step 2/7: s2" in err
    assert "\x01p\x021.000" in err


def test_sync_task_attaches_to_running_sync():
    agent = FakeAgent(
        [running(3), {"running": False, "last_result": "success"}],
        start_error=plugin.AgentError("busy", 409),
    )
    assert plugin.run_mode("sync", agent, {}, as_task=True)["last_result"] == "success"


def test_sync_task_fails_on_failed_sync():
    agent = FakeAgent([{"running": False, "last_result": "failed", "last_error": "Stash down"}])
    with pytest.raises(RuntimeError, match="Stash down"):
        plugin.run_mode("sync", agent, {})


def test_status_is_read_only():
    agent = FakeAgent([{"running": False}])
    plugin.run_mode("status", agent, {"enabled": False})
    assert agent.calls == [("GET", "/api/status", None)]


def test_config_defaults_interval():
    agent = FakeAgent([{}])
    result = plugin.run_mode("config", agent, {"enabled": True, "interval_hours": 0})
    assert result["interval_hours"] == 6.0


def test_agent_requires_url():
    with pytest.raises(RuntimeError, match="Agent URL"):
        plugin.Agent({})


def test_download_post_follows_job(capsys):
    queued = {"id": "j1", "status": "queued", "log": []}
    running_job = {"id": "j1", "status": "running", "step": 3, "step_count": 5, "step_label": "Download",
                   "progress": 0.4, "log": ["Downloading: x"]}  # fmt: skip
    done = dict(running_job, status="success", log=["Downloading: x", "Done"], result={"image_ids": ["1"]})
    agent = FakeAgent([queued, running_job, done])

    result = plugin.run_mode("download_post", agent, {}, args={"url": "https://redd.it/abc"})
    assert result["result"]["image_ids"] == ["1"]
    assert agent.calls[0] == ("POST", "/api/download", {"url": "https://redd.it/abc"})
    err = capsys.readouterr().err
    assert err.count("Downloading: x") == 1
    assert "\x01i\x02Step 3/5: Download" in err


def test_download_post_reports_error_code():
    failed = {"id": "j1", "status": "failed", "error_code": "cookies_expired", "error": "expired", "log": []}
    with pytest.raises(RuntimeError, match=r"\(cookies_expired\): expired"):
        plugin.run_mode("download_post", FakeAgent([failed]), {}, args={"url": "https://redd.it/abc"})


def test_download_post_needs_url():
    with pytest.raises(RuntimeError, match="url"):
        plugin.run_mode("download_post", FakeAgent([{}]), {}, args={})
