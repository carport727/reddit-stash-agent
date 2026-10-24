import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

engine = None

# Bound in init_db(); modules import this object directly.
SessionLocal = sessionmaker()

Base = declarative_base()


def init_db(path):
    global engine

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"timeout": 30},
    )
    SessionLocal.configure(bind=engine)

    from app.database import models  # noqa: F401 - registers the tables

    Base.metadata.create_all(bind=engine)
    return add_missing_columns()


def add_missing_columns():
    """Add columns that exist in the models but not in an older database file.

    SQLite only supports ADD COLUMN, which is all the schema has needed so far.
    """
    added = []
    inspector = inspect(engine)

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {column["name"] for column in inspector.get_columns(table.name)}

            for column in table.columns:
                if column.name in existing:
                    continue

                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
                default = column.default.arg if column.default is not None else None
                if isinstance(default, bool):
                    ddl += f" DEFAULT {int(default)}"
                elif isinstance(default, int):
                    ddl += f" DEFAULT {default}"

                conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")

    return added
