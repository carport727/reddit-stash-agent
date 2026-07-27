from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.database import Base


class RedditSource(Base):

    __tablename__ = "reddit_sources"

    id = Column(
        Integer,
        primary_key=True
    )

    performer_id = Column(
        String
    )

    source_type = Column(
        String
    )

    source_name = Column(
        String
    )

    last_scan = Column(
        DateTime,
        default=datetime.utcnow
    )


class RedditPost(Base):

    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True)

    reddit_id = Column(
        String,
        unique=True,
        nullable=False
    )

    source = Column(String)

    url = Column(String)

    title = Column(String)

    downloaded = Column(
        Boolean,
        default=False
    )

    download_path = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

class DownloadedFile(Base):
    __tablename__ = "downloaded_files"

    id = Column(Integer, primary_key=True)
    reddit_post_id = Column(
        Integer,
        ForeignKey("reddit_posts.id"),
        nullable=False,
    )
    path = Column(String, unique=True, nullable=False)


    scene_id = Column(
        Integer,
        nullable=True,
    )

    post = relationship("RedditPost")

    image_id = Column(
        Integer,
        nullable=True,
    )

    stash_imported = Column(
        Boolean,
        default=False,
    )

    performer_linked = Column(
        Boolean,
        default=False,
    )
