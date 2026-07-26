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


    print(
        "RSS:",
        url
    )


    cookie = load_cookie_header(
        "/config/reddit-cookies.json"
    )


    feed = feedparser.parse(
        url,
        request_headers={
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 reddit-stash-agent/0.1"
        }
    )


    print(
        "Entries:",
        len(feed.entries)
    )


    posts = []


    for entry in feed.entries:

        print(
            "TITLE:",
            entry.get("title")
        )


        reddit_id = entry.get(
            "id",
            ""
        ).split("/")[-1]


        if reddit_id.startswith("t3_"):
            
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
