import os
import re
import unicodedata

from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost
from app.stash.client import StashClient

# Files are saved as "{id} {filename}.{extension}", where id is the Reddit post id.
REDDIT_ID_PATTERN = re.compile(r"^([a-z0-9]+)(?:\s|$)", re.IGNORECASE)


def normalize_path(path):
    return unicodedata.normalize("NFC", os.path.normpath(path))


def run(config):
    """Recreate missing DB rows for images that Stash already knows below the download root.

    Covers files gallery-dl stored without reporting them (e.g. gallery posts).
    """
    root = normalize_path(config["downloads"]["root"])
    root_prefix = root.rstrip("/") + "/"
    stash = StashClient.from_config(config)
    db = SessionLocal()

    created = updated = unchanged = no_post = 0

    try:
        post_map = {
            post.reddit_id.removeprefix("t3_").strip().lower(): post
            for post in db.query(RedditPost).all()
            if post.reddit_id
        }
        existing_by_path = {normalize_path(row.path): row for row in db.query(DownloadedFile).all()}

        for raw_path, raw_image_id in stash.get_image_file_map(root).items():
            path = normalize_path(raw_path)
            if not path.startswith(root_prefix):
                continue

            match = REDDIT_ID_PATTERN.match(os.path.basename(path))
            post = post_map.get(match.group(1).lower()) if match else None
            if not post:
                no_post += 1
                continue

            image_id = int(raw_image_id)
            row = existing_by_path.get(path)

            if row is None:
                row = DownloadedFile(
                    reddit_post_id=post.id,
                    path=path,
                    image_id=image_id,
                    stash_imported=True,
                    performer_linked=False,
                )
                db.add(row)
                existing_by_path[path] = row
                created += 1
                continue

            changed = False
            if row.reddit_post_id != post.id:
                row.reddit_post_id = post.id
                changed = True
            if row.image_id != image_id:
                row.image_id = image_id
                changed = True
            if row.scene_id is not None:
                row.scene_id = None
                changed = True
            if not row.stash_imported:
                row.stash_imported = True
                changed = True

            if changed:
                row.performer_linked = False
                updated += 1
            else:
                unchanged += 1

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Reconcile: created {created}, updated {updated}, unchanged {unchanged}, without post {no_post}")
    return {"files_reconciled": created + updated}
