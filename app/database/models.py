from sqlalchemy import Column, Integer, String, Boolean, DateTime
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

    id = Column(
        Integer,
        primary_key=True
    )

    reddit_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    source = Column(
        String
    )

    url = Column(
        String
    )

    title = Column(
        String
    )

    downloaded = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
