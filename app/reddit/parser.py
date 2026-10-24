import re

SOURCE_PATTERN = re.compile(
    r"reddit\.com/(?P<kind>user|u|r)/(?P<name>[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def parse_reddit_url(url):
    """Return ("user"|"subreddit", lowercase name) or None."""
    match = SOURCE_PATTERN.search(url or "")
    if not match:
        return None

    kind = "subreddit" if match.group("kind").lower() == "r" else "user"
    return kind, match.group("name").lower()


def parse_reddit_urls(urls):
    sources = []
    for url in urls or []:
        source = parse_reddit_url(url)
        if source and source not in sources:
            sources.append(source)
    return sources
