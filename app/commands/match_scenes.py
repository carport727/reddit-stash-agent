from app.database.database import SessionLocal
from app.database.models import DownloadedFile
from app.stash.client import StashClient


def run(config):

    db = SessionLocal()

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"],
    )

    try:

        files = db.query(
            DownloadedFile
        ).filter_by(
            scene_id=None
        ).all()

        print()
        print("Files waiting for scene matching:", len(files))
        print()

    finally:

        db.close()
