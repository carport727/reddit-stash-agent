"""Agent configuration.

Values come from the YAML file in CONFIG_FILE (default /config/config.yaml).
Environment variables override the file, so secrets can live in .env instead.
"""

import copy
import os

import yaml

DEFAULTS = {
    "stash": {
        "url": "http://localhost:9999",
        "api_key": "",
    },
    "reddit": {
        "cookies": "/config/reddit-cookies.json",
        "request_delay_seconds": 2,
    },
    "downloads": {
        "root": "/Stash/Download/Reddit",
        "max_attempts": 5,
        # gallery-dl browser emulation (headers/TLS); Reddit blocks the default client. Empty to disable.
        "gallery_dl_browser": "firefox",
    },
    "database": {
        "path": "/data/reddit-agent.db",
    },
    "agent": {
        "token": "",
    },
    "dry_run": False,
}

# env var -> (section, key)
ENV_OVERRIDES = {
    "STASH_URL": ("stash", "url"),
    "STASH_API_KEY": ("stash", "api_key"),
    "AGENT_TOKEN": ("agent", "token"),
    "DOWNLOADS_ROOT": ("downloads", "root"),
    "DATABASE_PATH": ("database", "path"),
    "REDDIT_COOKIES": ("reddit", "cookies"),
}

DATA_DIR = os.environ.get("DATA_DIR", "/data")
LOG_DIR = os.environ.get("LOG_DIR", "/logs")


def config_file():
    return os.environ.get("CONFIG_FILE", "/config/config.yaml")


def _merge(base, override):
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        elif value is not None:
            base[key] = value
    return base


def load_config(path=None):
    path = path or config_file()
    config = copy.deepcopy(DEFAULTS)

    if os.path.exists(path):
        with open(path) as f:
            _merge(config, yaml.safe_load(f) or {})

    for env, (section, key) in ENV_OVERRIDES.items():
        value = os.environ.get(env)
        if value:
            config[section][key] = value

    config["stash"]["url"] = str(config["stash"]["url"]).rstrip("/")
    config["downloads"]["root"] = os.path.normpath(config["downloads"]["root"])
    return config
