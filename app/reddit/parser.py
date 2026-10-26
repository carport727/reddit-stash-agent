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


# Post links: /r/SUB/comments/ID, /user/NAME/comments/ID, /comments/ID, /gallery/ID, redd.it/ID.
POST_PATTERN = re.compile(
    r"^(?:[a-z0-9-]+\.)?reddit\.com/(?:(?:r|u|user)/[^/?#]+/)?(?:comments|gallery)/(?P<id>[a-z0-9]+)"
    r"|^redd\.it/(?P<short_id>[a-z0-9]+)",
    re.IGNORECASE,
)
# Share links from the Reddit app (/r/SUB/s/CODE); the post ID is only known after following the redirect.
SHARE_PATTERN = re.compile(r"^(?:[a-z0-9-]+\.)?reddit\.com(?P<path>/(?:r|u|user)/[^/?#]+/s/[a-z0-9]+)", re.IGNORECASE)
MEDIA_HOSTS = ("i.redd.it", "v.redd.it", "preview.redd.it")


def parse_post_url(url):
    """Return (reddit_id or None, URL for gallery-dl). Raises ValueError for links that are not a Reddit post.

    reddit_id is "t3_<id>" like in the RSS feed; it is None for share links.
    """
    text = (url or "").strip()
    bare = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)

    if bare.lower().split("/")[0] in MEDIA_HOSTS:
        raise ValueError("Direct media link; share the Reddit post link instead")

    match = POST_PATTERN.match(bare)
    if match:
        post_id = (match.group("id") or match.group("short_id")).lower()
        return f"t3_{post_id}", f"https://www.reddit.com/comments/{post_id}/"

    match = SHARE_PATTERN.match(bare)
    if match:
        return None, "https://www.reddit.com" + match.group("path")

    raise ValueError(f"Not a Reddit post link: {text[:200] or '(empty)'}")
