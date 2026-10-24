import json
import os

import feedparser

from app import __version__

USER_AGENT = f"Mozilla/5.0 (compatible; reddit-stash-agent/{__version__})"


class RssError(Exception):
    pass


def load_cookie_header(path):
    """Build a Cookie header from a browser export (JSON list of {name, value})."""
    if not path or not os.path.exists(path):
        return ""

    try:
        with open(path) as f:
            cookies = json.load(f)
        return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"WARNING: could not read Reddit cookies from {path}: {exc}")
        return ""


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
