from app.database.database import SessionLocal
from app.database.models import RedditPost


def post_exists(reddit_id):

    db = SessionLocal()

    try:
        return (
            db.query(RedditPost)
            .filter(
                RedditPost.reddit_id == reddit_id
            )
            .first()
            is not None
        )

    finally:
        db.close()


def add_post(post):

    db = SessionLocal()

    try:
        item = RedditPost(
            reddit_id=post["reddit_id"],
            source=post.get("source"),
            url=post.get("url"),
            title=post.get("title"),
            downloaded=False
        )

        db.add(item)
        db.commit()

    finally:
        db.close()


def mark_downloaded(reddit_id):

    db = SessionLocal()

    try:
        item = (
            db.query(RedditPost)
            .filter(
                RedditPost.reddit_id == reddit_id
            )
            .first()
        )

        if item:
            item.downloaded = True
            db.commit()

    finally:
        db.close()

