from app.commands.gallery_sync import performer_map
from app.commands.import_reddit import media_kind
from app.database.database import SessionLocal
from app.database.models import DownloadedFile
from app.stash.client import StashClient, StashError


def run(config):
    """Add the source's performer to every imported scene and image."""
    dry_run = bool(config.get("dry_run"))
    if dry_run:
        print("DRY RUN enabled")

    stash = StashClient.from_config(config)
    db = SessionLocal()

    linked = no_mapping = stale = errors = 0

    try:
        performers = performer_map(db)
        files = (
            db.query(DownloadedFile)
            .filter(DownloadedFile.stash_imported.is_(True), DownloadedFile.performer_linked.is_(False))
            .all()
        )
        print(f"Files to link: {len(files)}")

        for file in files:
            post = file.post
            performer_id = performers.get((post.source or "").strip().lower()) if post else None
            if not performer_id:
                no_mapping += 1
                continue

            kind = media_kind(file.path)
            object_id = file.scene_id if kind == "video" else file.image_id if kind == "image" else None
            if not object_id:
                continue

            stash_kind = "scene" if kind == "video" else "image"
            if dry_run:
                print(f"DRY RUN - would link performer {performer_id} to {stash_kind} {object_id}")
                linked += 1
                continue

            try:
                result = stash.add_performer(stash_kind, object_id, performer_id)
            except StashError as error:
                # Transient (network, Stash busy): keep the file as is and retry next sync.
                errors += 1
                print(f"Could not link {stash_kind} {object_id}: {error}")
                continue

            if result == "missing":
                # Deleted in Stash: import again on the next sync.
                print(f"{stash_kind} {object_id} no longer exists in Stash: {file.path}")
                file.scene_id = None
                file.image_id = None
                file.stash_imported = False
                stale += 1
            else:
                file.performer_linked = True
                linked += 1

            db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Linked: {linked}, without performer mapping: {no_mapping}, stale: {stale}, errors: {errors}")
    return {"performers_linked": linked, "link_errors": errors}
