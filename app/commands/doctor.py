import os
import shutil

from app.commands.download import GALLERY_DL_CONFIG, GALLERY_DL_COOKIES
from app.providers.reddit.rss import gallery_dl_cookie_file, load_cookie_header
from app.stash.client import StashClient, StashError


def run(config):
    """Check configuration and connections. Returns the number of problems."""
    problems = 0

    def check(ok, message, hint=""):
        nonlocal problems
        print(("✓ " if ok else "✗ ") + message + ("" if ok or not hint else f"  ({hint})"))
        if not ok:
            problems += 1

    stash = StashClient.from_config(config)
    try:
        count = stash.count_performers()
        reddit = stash.get_reddit_performers()
        check(True, f"Stash reachable at {config['stash']['url']}: {count} performers, {len(reddit)} with Reddit URLs")
    except StashError as exc:
        check(False, f"Stash: {exc}", "check stash.url and stash.api_key / STASH_API_KEY")

    root = config["downloads"]["root"]
    check(
        os.path.isdir(root) and os.access(root, os.W_OK),
        f"Download root writable: {root}",
        "mount the folder that Stash scans",
    )
    check(shutil.which("gallery-dl") is not None, "gallery-dl installed")
    cookie_file = gallery_dl_cookie_file(config["reddit"]["cookies"], GALLERY_DL_COOKIES)
    check(
        bool(cookie_file) or os.path.exists(GALLERY_DL_CONFIG),
        "Reddit login for gallery-dl (cookies or gallery-dl.conf)",
        "Reddit blocks downloads without it; see README 'Reddit login'",
    )
    check(bool(load_cookie_header(config["reddit"]["cookies"])), f"Reddit cookies: {config['reddit']['cookies']}")
    check(
        bool(config["agent"]["token"]),
        "API token set (AGENT_TOKEN)",
        "without it anyone on the network can use the API",
    )

    return problems
