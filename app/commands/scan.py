from app.stash.client import StashClient
from app.reddit.parser import parse_reddit_urls
from app.database.database import SessionLocal
from app.database.models import RedditSource


def run(config):

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )

    db = SessionLocal()

    performers = stash.get_performers()

    print()
    print("Scanning Stash performers...")
    print()

    added = 0
    skipped = 0

    for performer in performers:

        sources = parse_reddit_urls(
            performer.get("urls")
        )

        for source in sources:

            existing = db.query(RedditSource).filter_by(
                performer_id=performer["id"],
                source_type=source["type"],
                source_name=source["name"]
            ).first()


            if existing:

                skipped += 1

                print(
                    f"✓ {performer['name']}"
                    f" - {source['type']}:{source['name']}"
                    " (exists)"
                )

                continue


            reddit_source = RedditSource(
                performer_id=performer["id"],
                source_type=source["type"],
                source_name=source["name"]
            )

            db.add(reddit_source)

            added += 1

            print(
                f"✓ {performer['name']}"
                f" - {source['type']}:{source['name']}"
                " (saved)"
            )


    db.commit()
    db.close()


    print()
    print("Database update complete")
    print(f"Added: {added}")
    print(f"Skipped: {skipped}")
