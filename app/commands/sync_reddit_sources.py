from app.database.database import SessionLocal
from app.database.models import RedditSource
from app.reddit.parser import parse_reddit_urls
from app.stash.client import StashClient


def run(config):
    """Mirror the Reddit URLs of Stash performers into reddit_sources.

    Sources whose URL was removed from the performer are deleted, so they stop syncing.
    Already downloaded posts and files are kept.
    """
    print("Syncing Reddit sources from Stash performers...")

    stash = StashClient.from_config(config)
    performers = stash.get_reddit_performers()

    wanted = {}
    for performer in performers:
        for source_type, source_name in parse_reddit_urls(performer.get("urls")):
            wanted[(str(performer["id"]), source_type, source_name)] = performer["name"]

    db = SessionLocal()
    added = removed = 0

    try:
        existing = {}
        for source in db.query(RedditSource).all():
            key = (str(source.performer_id), source.source_type, (source.source_name or "").lower())
            if key in existing or key not in wanted:
                db.delete(source)
                removed += 1
                print(f"REMOVED: {source.source_type}:{source.source_name} (performer {source.performer_id})")
                continue

            if source.source_name != key[2]:
                source.source_name = key[2]
            existing[key] = source

        for key, performer_name in wanted.items():
            if key in existing:
                continue

            performer_id, source_type, source_name = key
            db.add(RedditSource(performer_id=performer_id, source_type=source_type, source_name=source_name))
            added += 1
            print(f"NEW: {performer_name} -> {source_type}:{source_name}")

        db.commit()
    finally:
        db.close()

    print(f"Performers with Reddit URLs: {len(performers)}, sources: {len(wanted)}, added: {added}, removed: {removed}")
    return {"sources": len(wanted), "sources_added": added, "sources_removed": removed}
