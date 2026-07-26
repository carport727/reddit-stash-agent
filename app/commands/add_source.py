from app.database.database import SessionLocal
from app.database.models import RedditSource
from app.stash.performer import get_or_create_performer



def run(config, source_type, source_name):

    db = SessionLocal()

    try:

        performer_id = get_or_create_performer(
            source_name
        )


        source = RedditSource(
            source_type=source_type,
            source_name=source_name,
            performer_id=performer_id
        )


        db.add(source)

        db.commit()


        print()
        print("Added Reddit source")
        print(
            f"Source: {source_type}:{source_name}"
        )
        print(
            f"Performer ID: {performer_id}"
        )


    finally:
        db.close()
