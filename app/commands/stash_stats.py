from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost, RedditSource


def run(config):
    """Counts from the agent database."""
    db = SessionLocal()
    try:
        print("Sources:", db.query(RedditSource).count())
        print("Posts:", db.query(RedditPost).count())
        print("  downloaded:", db.query(RedditPost).filter(RedditPost.downloaded.is_(True)).count())
        print("  pending:", db.query(RedditPost).filter(RedditPost.downloaded.is_(False)).count())
        print("Files:", db.query(DownloadedFile).count())
        print("  imported:", db.query(DownloadedFile).filter(DownloadedFile.stash_imported.is_(True)).count())
        print("  performer linked:", db.query(DownloadedFile).filter(DownloadedFile.performer_linked.is_(True)).count())
        print("  ignored:", db.query(DownloadedFile).filter(DownloadedFile.ignored.is_(True)).count())
    finally:
        db.close()
