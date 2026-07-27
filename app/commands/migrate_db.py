from sqlalchemy import text
from app.database.database import engine


def run(config):

    with engine.connect() as conn:

        try:
            conn.execute(
                text(
                    "ALTER TABLE downloaded_files ADD COLUMN scene_id INTEGER"
                )
            )

            conn.commit()

            print("Added scene_id column")

        except Exception as e:
            print("Migration failed:")
            print(e)
