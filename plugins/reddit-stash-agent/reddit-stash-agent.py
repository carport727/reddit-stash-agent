#!/usr/bin/env python3

import json
import sys
import urllib.error
import urllib.request


PLUGIN_ID = "reddit-stash-agent"


def read_input():
    try:
        return json.load(
            sys.stdin
        )
    except Exception:
        return {}


def stash_graphql(
    plugin_input,
    query,
):
    connection = plugin_input.get(
        "server_connection",
        {},
    )

    scheme = connection.get(
        "Scheme",
        "http",
    )

    port = connection.get(
        "Port",
        9999,
    )

    url = (
        f"{scheme}://127.0.0.1:"
        f"{port}/graphql"
    )

    payload = json.dumps(
        {
            "query": query,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type":
            "application/json",
    }

    cookie = connection.get(
        "SessionCookie"
    )

    if cookie:
        name = cookie.get("Name")
        value = cookie.get("Value")

        if name and value:
            headers["Cookie"] = (
                f"{name}={value}"
            )

    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        result = json.load(
            response
        )

    if result.get("errors"):
        raise RuntimeError(
            str(
                result["errors"]
            )
        )

    return result["data"]


def get_plugin_settings(
    plugin_input,
):
    result = stash_graphql(
        plugin_input,
        """
        query RedditStashAgentConfig {
          configuration {
            plugins
          }
        }
        """,
    )

    plugins = (
        result
        .get(
            "configuration",
            {},
        )
        .get(
            "plugins",
            {},
        )
    )

    return plugins.get(
        PLUGIN_ID,
        {},
    )


def get_agent_url(
    plugin_input,
):
    settings = (
        get_plugin_settings(
            plugin_input
        )
    )

    agent_url = settings.get(
        "agent_url"
    )

    if not agent_url:
        raise RuntimeError(
            "Agent URL is not "
            "configured"
        )

    return str(
        agent_url
    ).rstrip("/")


def agent_request(
    plugin_input,
    path,
    method="GET",
    body=None,
):
    agent_url = get_agent_url(
        plugin_input
    )

    url = agent_url + path

    headers = {
        "Accept":
            "application/json",
    }

    data = None

    if body is not None:
        data = json.dumps(
            body
        ).encode("utf-8")

        headers[
            "Content-Type"
        ] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            response_body = (
                response.read()
            )

    except urllib.error.HTTPError as exc:
        error_body = (
            exc.read().decode(
                "utf-8",
                errors="replace",
            )
        )

        raise RuntimeError(
            f"Agent returned HTTP "
            f"{exc.code}: "
            f"{error_body}"
        )

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach agent: "
            f"{exc.reason}"
        )

    if not response_body:
        return {}

    return json.loads(
        response_body.decode(
            "utf-8"
        )
    )


def apply_scheduler_settings(
    plugin_input,
):
    settings = (
        get_plugin_settings(
            plugin_input
        )
    )

    enabled = bool(
        settings.get(
            "enabled",
            False,
        )
    )

    interval_hours = float(
        settings.get(
            "interval_hours",
            6,
        )
        or 6
    )

    return agent_request(
        plugin_input,
        "/api/config",
        method="PUT",
        body={
            "enabled":
                enabled,
            "interval_hours":
                interval_hours,
        },
    )


def main():
    plugin_input = read_input()

    args = plugin_input.get(
        "args",
        {},
    )

    mode = (
        sys.argv[1]
        if len(sys.argv) > 1
        else args.get(
            "mode",
            "health",
        )
    )

    if mode == "health":
        result = agent_request(
            plugin_input,
            "/api/health",
        )

    elif mode == "status":
        apply_scheduler_settings(
            plugin_input
        )

        result = agent_request(
            plugin_input,
            "/api/status",
        )

    elif mode == "config":
        result = (
            apply_scheduler_settings(
                plugin_input
            )
        )

    elif mode == "sync":
        apply_scheduler_settings(
            plugin_input
        )

        result = agent_request(
            plugin_input,
            "/api/sync",
            method="POST",
        )

    else:
        raise RuntimeError(
            f"Unknown mode: {mode}"
        )

    print(
        json.dumps(
            {
                "output": result,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            json.dumps(
                {
                    "error":
                        str(exc),
                }
            )
        )
        sys.exit(1)
