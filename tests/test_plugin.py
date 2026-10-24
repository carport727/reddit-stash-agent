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
