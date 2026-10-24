#!/usr/bin/env python3
"""Stash plugin that controls the Reddit Stash Agent over its HTTP API.

Mode comes from argv[1] (tasks, via execArgs) or args.mode (runPluginOperation).
Logs and progress go to stderr in Stash's plugin log format, the result to stdout
as {"output": ...} or {"error": ...}.
"""

import json
import ssl
import sys
import time
import urllib.error
import urllib.request

PLUGIN_ID = "reddit-stash-agent"
POLL_SECONDS = 3


# Stash plugin log protocol: SOH + level + STX + message on stderr.
def _log(level, message):
    for line in str(message).splitlines() or [""]:
        sys.stderr.write(f"\x01{level}\x02{line}\n")
    sys.stderr.flush()


def log_info(message):
    _log("i", message)


def log_warning(message):
    _log("w", message)


def log_error(message):
    _log("e", message)


def log_progress(value):
    _log("p", f"{min(max(float(value), 0.0), 1.0):.3f}")


class AgentError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def read_input():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def stash_graphql(plugin_input, query):
    connection = plugin_input.get("server_connection") or {}
    scheme = connection.get("Scheme") or "http"
    host = connection.get("Host") or "localhost"
    if host in ("0.0.0.0", "::", ""):
        host = "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = connection.get("Port") or 9999

    headers = {"Content-Type": "application/json"}
    cookie = connection.get("SessionCookie") or {}
    if cookie.get("Name") and cookie.get("Value"):
        headers["Cookie"] = f"{cookie['Name']}={cookie['Value']}"

    request = urllib.request.Request(
        f"{scheme}://{host}:{port}/graphql",
        data=json.dumps({"query": query}).encode(),
        headers=headers,
        method="POST",
    )

    # Stash talks to itself here; a self-signed certificate is expected.
    context = ssl._create_unverified_context() if scheme == "https" else None
    with urllib.request.urlopen(request, timeout=10, context=context) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(f"Stash GraphQL error: {result['errors']}")
    return result["data"]


def get_settings(plugin_input):
    data = stash_graphql(plugin_input, "query { configuration { plugins } }")
    return (data.get("configuration", {}).get("plugins") or {}).get(PLUGIN_ID) or {}


class Agent:
    def __init__(self, settings):
        url = str(settings.get("agent_url") or "").strip().rstrip("/")
        if not url:
            raise RuntimeError("Agent URL is not configured (Settings > Plugins > Reddit Stash Agent)")
        self.url = url
        self.token = str(settings.get("agent_token") or "").strip()

    def request(self, path, method="GET", body=None, timeout=20):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except ValueError:
                pass
            raise AgentError(f"Agent returned HTTP {exc.code}: {detail}", exc.code) from None
        except urllib.error.URLError as exc:
            raise AgentError(f"Could not reach agent at {self.url}: {exc.reason}") from None

        return json.loads(payload) if payload else {}


def push_scheduler_settings(agent, settings):
    interval = settings.get("interval_hours")
    try:
        interval = float(interval)
    except (TypeError, ValueError):
        interval = 0
    body = {"enabled": bool(settings.get("enabled", False)), "interval_hours": interval if interval > 0 else 6.0}
    return agent.request("/api/config", method="PUT", body=body)


def format_summary(summary):
    return ", ".join(f"{key}={value}" for key, value in (summary or {}).items()) or "-"


def follow_sync(agent):
    """Poll the agent until the running sync ends, reporting progress and steps to Stash."""
    last_step = None
    status = agent.request("/api/status")

    while status.get("running"):
        step = status.get("step")
        if step and step != last_step:
            last_step = step
            log_info(f"Step {step}/{status.get('step_count')}: {status.get('step_label')}")
        log_progress(status.get("progress") or 0)

        time.sleep(POLL_SECONDS)
        try:
            status = agent.request("/api/status")
        except AgentError as exc:
            log_warning(f"Status poll failed, retrying: {exc}")
            time.sleep(POLL_SECONDS)

    result = status.get("last_result")
    if result == "success":
        log_progress(1)
        log_info(f"Sync finished: {format_summary(status.get('summary'))}")
    elif result == "cancelled":
        log_warning("Sync was cancelled")
    else:
        try:
            tail = agent.request("/api/logs?lines=30").get("lines") or []
            if tail:
                log_error("Last log lines:\n" + "\n".join(tail))
        except AgentError:
            pass
        raise RuntimeError(f"Sync {result or 'failed'}: {status.get('last_error') or 'see agent log'}")

    return status


def run_mode(mode, agent, settings, as_task=False):
    """as_task: started from the Stash task queue. Only then write results to the Stash log,
    so UI and Stashfeed polling via runPluginOperation do not flood it."""
    if mode == "health":
        result = agent.request("/api/health")
        if as_task:
            log_info(f"Agent {result.get('version')} reachable at {agent.url}")
        return result

    if mode == "status":
        result = agent.request("/api/status")
        if as_task:
            scheduler = result.get("scheduler") or {}
            log_info(
                f"Running: {result.get('running')}, last result: {result.get('last_result')}, "
                f"last finished: {result.get('last_finished_at')}, summary: {format_summary(result.get('summary'))}, "
                f"auto-sync: {scheduler.get('enabled')} every {scheduler.get('interval_hours')} h, "
                f"next: {scheduler.get('next_run_at')}"
            )
        return result

    if mode == "config":
        result = push_scheduler_settings(agent, settings)
        log_info(
            f"Scheduler: enabled={result.get('enabled')}, every {result.get('interval_hours')} h, "
            f"next {result.get('next_run_at')}"
        )
        return result

    if mode == "start":
        return agent.request("/api/sync", method="POST")

    if mode == "sync":
        # Task mode: start (or attach to a running sync) and block until it ends.
        try:
            agent.request("/api/sync", method="POST")
            log_info("Reddit sync started")
        except AgentError as exc:
            if exc.status != 409:
                raise
            log_info("A sync is already running; following it")
        return follow_sync(agent)

    if mode == "cancel":
        result = agent.request("/api/sync/cancel", method="POST")
        log_info("Cancel requested")
        return result

    if mode == "logs":
        result = agent.request("/api/logs?lines=200")
        if as_task:
            log_info("\n".join(result.get("lines") or ["(no log)"]))
        return result

    raise RuntimeError(f"Unknown mode: {mode}")


def main():
    plugin_input = read_input()
    args = plugin_input.get("args") or {}
    as_task = len(sys.argv) > 1
    mode = sys.argv[1] if as_task else args.get("mode") or "health"

    settings = get_settings(plugin_input)
    result = run_mode(mode, Agent(settings), settings, as_task)
    print(json.dumps({"output": result}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Stash logs task errors itself ("Plugin returned error") and returns
        # operation errors to the GraphQL caller.
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
