import time

from app.database.database import SessionLocal
from app.database.models import RedditPost, RedditSource, utcnow
from app.providers.reddit.rss import RssError, fetch_posts, load_cookie_header

RATE_LIMIT_PAUSE = 60


def fetch_with_retry(source, cookie_header):
    """Reddit answers HTTP 429 after a burst of feeds; wait once and retry."""
    try:
        return fetch_posts(source.source_type, source.source_name, cookie_header)
    except RssError as exc:
        if "HTTP 429" not in str(exc):
            raise
        print(f"Rate limited by Reddit, waiting {RATE_LIMIT_PAUSE} s")
        time.sleep(RATE_LIMIT_PAUSE)
        return fetch_posts(source.source_type, source.source_name, cookie_header)


def run(config):
    print("Checking Reddit RSS feeds...")

    cookie_header = load_cookie_header(config["reddit"]["cookies"])
    if not cookie_header:
        print("No Reddit cookies configured; NSFW or private feeds may be empty.")

    delay = float(config["reddit"].get("request_delay_seconds") or 0)

    db = SessionLocal()
    added = skipped = failed = 0

    try:
        sources = db.query(RedditSource).all()

        for index, source in enumerate(sources):
            if index and delay:
                time.sleep(delay)

            try:
                posts = fetch_with_retry(source, cookie_header)
            except RssError as exc:
                failed += 1
                print(f"RSS FAILED {source.source_type}:{source.source_name}: {exc}")
                continue

            source.last_scan = utcnow()
            new_here = 0

            for post in posts:
                if db.query(RedditPost).filter_by(reddit_id=post["reddit_id"]).first():
                    skipped += 1
                    continue

                db.add(
                    RedditPost(
                        reddit_id=post["reddit_id"],
                        source=source.source_name,
                        url=post["url"],
                        title=post.get("title"),
                        downloaded=False,
                    )
                )
                added += 1
                new_here += 1

            print(f"{source.source_type}:{source.source_name}: {len(posts)} entries, {new_here} new")
            db.commit()
    finally:
        db.close()

    print(f"New posts: {added}, known: {skipped}, failed feeds: {failed}")
    return {"posts_new": added, "feeds_failed": failed}
