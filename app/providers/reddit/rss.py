import feedparser
import json


def load_cookie_header(path):

    try:
        with open(path) as f:
            cookies = json.load(f)

        return "; ".join(
            [
                f"{c['name']}={c['value']}"
                for c in cookies
            ]
        )

    except Exception:
        return ""


def get_rss_url(source_type, source_name):

    if source_type == "user":
        return (
            f"https://www.reddit.com/user/"
            f"{source_name}/.rss"
        )

    if source_type == "subreddit":
        return (
            f"https://www.reddit.com/r/"
            f"{source_name}/.rss"
        )

    return None



def fetch_posts(source_type, source_name):

    url = get_rss_url(
        source_type,
        source_name
    )

    if not url:
        return []


    cookie = load_cookie_header(
        "/config/reddit-cookies.json"
    )


    feed = feedparser.parse(
        url,
        request_headers={
            "Cookie": cookie,
            "User-Agent": "reddit-stash-agent/0.1"
        }
    )


    posts = []


    for entry in feed.entries:

        reddit_id = entry.get(
            "id",
            ""
        ).split("/")[-1]


        if not reddit_id.startswith("t3_"):
            continue


        posts.append(
            {
                "reddit_id": reddit_id,
                "title": entry.get("title"),
                "url": entry.get("link"),
                "published": entry.get(
                    "published",
                    ""
                )
            }
        )


    return posts
