from app.database.database import SessionLocal
from app.database.models import DownloadedFile


def run(config):

    print()
    print("Syncing Reddit galleries...")
    print()

    db = SessionLocal()

    count = (
        db.query(DownloadedFile)
        .filter(
            DownloadedFile.image_id != None
        )
        .count()
    )

    print("Images:", count)

    db.close()

    print()
    print("Gallery sync finished")
