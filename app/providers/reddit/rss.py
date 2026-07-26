import feedparser


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


    feed = feedparser.parse(
        url,
        agent="reddit-stash-agent/0.1"
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
