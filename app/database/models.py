from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


def utcnow():
    # SQLite stores naive datetimes; keep them in UTC.
    return datetime.now(UTC).replace(tzinfo=None)


class RedditSource(Base):
    __tablename__ = "reddit_sources"

    id = Column(Integer, primary_key=True)
    performer_id = Column(String)
    source_type = Column(String)
    source_name = Column(String)
    last_scan = Column(DateTime, default=utcnow)


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True)
    reddit_id = Column(String, unique=True, nullable=False)
    source = Column(String)
    url = Column(String)
    title = Column(String)
    downloaded = Column(Boolean, default=False)
    download_path = Column(String, nullable=True)
    download_attempts = Column(Integer, default=0)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class DownloadedFile(Base):
    __tablename__ = "downloaded_files"

    id = Column(Integer, primary_key=True)
    reddit_post_id = Column(Integer, ForeignKey("reddit_posts.id"), nullable=False)
    path = Column(String, unique=True, nullable=False)
    scene_id = Column(Integer, nullable=True)
    image_id = Column(Integer, nullable=True)
    gallery_id = Column(Integer, nullable=True)
    stash_imported = Column(Boolean, default=False)
    performer_linked = Column(Boolean, default=False)
    # Files Stash cannot import (unknown extension); never retried.
    ignored = Column(Boolean, default=False)

    post = relationship("RedditPost")
