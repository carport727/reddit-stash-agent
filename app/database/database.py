from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE = "/data/reddit-agent.db"

engine = create_engine(
    f"sqlite:///{DATABASE}"
)

SessionLocal = sessionmaker(
    bind=engine
)

Base = declarative_base()


def init_db():

    from app.database import models

    Base.metadata.create_all(
        bind=engine
    )
