import json
import os
import threading
import time
from datetime import UTC, datetime

import feedparser

from app import __version__

USER_AGENT = f"Mozilla/5.0 (compatible; reddit-stash-agent/{__version__})"


class RssError(Exception):
    pass


def read_netscape_cookies(path):
    """(name, value, expires) tuples from a Netscape cookies.txt; expires 0 means session cookie."""
    pairs = []
    with open(path) as f:
        for line in f:
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_") :]
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) == 7:
                expires = int(fields[4]) if fields[4].isdigit() else 0
                pairs.append((fields[5], fields[6], expires))
    return pairs


def read_cookies(path):
    """(name, value, expires) tuples from a JSON browser export or a Netscape cookies.txt."""
    if not path.endswith(".json"):
        return read_netscape_cookies(path)
    with open(path) as f:
        return [(c["name"], c["value"], int(c.get("expirationDate") or 0)) for c in json.load(f)]


LOGIN_COOKIE = "reddit_session"


def login_cookie_status(path, now=None):
    """Expiry of the Reddit login cookie, for the status page."""
    status = {"file": path, "present": False, "expires_at": None, "expired": False, "days_left": None}
    if not path or not os.path.exists(path):
        return status

    try:
        cookies = read_cookies(path)
    except (OSError, ValueError, KeyError, TypeError):
        return status

    expires = next((e for name, _, e in cookies if name == LOGIN_COOKIE), None)
    if expires is None:
        return status

    status["present"] = True
    if expires:
        now = now or time.time()
        status["expires_at"] = datetime.fromtimestamp(expires, UTC).isoformat()
        status["expired"] = expires <= now
        status["days_left"] = int((expires - now) // 86400)
    return status


def load_cookie_header(path):
    """Build a Cookie header from a browser export (JSON list of {name, value})."""
    if not path or not os.path.exists(path):
        return ""

    try:
        return "; ".join(f"{name}={value}" for name, value, _ in read_cookies(path))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"WARNING: could not read Reddit cookies from {path}: {exc}")
        return ""


def gallery_dl_cookie_file(source, target):
    """Cookie file for gallery-dl (Netscape format).

    A .txt source is used as is. A browser JSON export is converted to target (mode 600).
    Returns None when there are no cookies.
    """
    if not source or not os.path.exists(source):
        return None
    if not source.endswith(".json"):
        return source

    try:
        with open(source) as f:
            cookies = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"WARNING: could not read Reddit cookies from {source}: {exc}")
        return None

    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        domain = cookie.get("domain") or ".reddit.com"
        lines.append(
            "\t".join(
                [
                    domain,
                    "TRUE" if domain.startswith(".") else "FALSE",
                    cookie.get("path") or "/",
                    "TRUE" if cookie.get("secure", True) else "FALSE",
                    str(int(cookie.get("expirationDate") or 0)),
                    cookie["name"],
                    cookie["value"],
                ]
            )
        )

    # Written atomically: a sync and a single post download may convert the file at the same time.
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp_file = f"{target}.{os.getpid()}.{threading.get_ident()}.tmp"
    fd = os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(temp_file, target)
    return target


def get_rss_url(source_type, source_name):
    if source_type == "user":
        return f"https://www.reddit.com/user/{source_name}/.rss"
    if source_type == "subreddit":
        return f"https://www.reddit.com/r/{source_name}/.rss"
    return None


def reddit_id_from_link(link):
    parts = (link or "").split("/")
    if "reddit.com" not in (link or "") or "comments" not in parts:
        return None

    index = parts.index("comments")
    if len(parts) > index + 1 and parts[index + 1]:
        return "t3_" + parts[index + 1]
    return None


def fetch_posts(source_type, source_name, cookie_header=""):
    url = get_rss_url(source_type, source_name)
    if not url:
        return []

    headers = {"User-Agent": USER_AGENT}
    if cookie_header:
        headers["Cookie"] = cookie_header

    feed = feedparser.parse(url, request_headers=headers)
    status = getattr(feed, "status", None)

    if status is not None and status >= 400:
        raise RssError(f"HTTP {status} for {url}")
    if status is None and feed.get("bozo"):
        raise RssError(f"could not load {url}: {feed.get('bozo_exception')}")

    posts = []
    seen = set()

    for entry in feed.entries:
        reddit_id = reddit_id_from_link(entry.get("link"))
        if not reddit_id or reddit_id in seen:
            continue

        seen.add(reddit_id)
        posts.append(
            {
                "reddit_id": reddit_id,
                "title": entry.get("title"),
                "url": entry.get("link"),
                "published": entry.get("published", ""),
            }
        )

    return posts
