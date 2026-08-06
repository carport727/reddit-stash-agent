import os
import re
import unicodedata

from app.database.database import SessionLocal
from app.database.models import (
    RedditPost,
    DownloadedFile,
)
from app.stash.client import StashClient


REDDIT_ID_PATTERN = re.compile(
    r"^([a-z0-9]+)(?:\s|$)",
    re.IGNORECASE,
)


def normalize_path(path):

    return unicodedata.normalize(
        "NFC",
        os.path.normpath(path),
    )


def run(config):

    print()
    print("Reconciling Reddit image files...")
    print()

    root = normalize_path(
        config["downloads"]["root"]
    )

    root_prefix = root.rstrip("/") + "/"

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"],
    )

    db = SessionLocal()

    created = 0
    updated = 0
    unchanged = 0
    no_post = 0
    invalid_filename = 0
    outside_root = 0

    try:
        posts = db.query(RedditPost).all()

        post_map = {
            post.reddit_id
            .removeprefix("t3_")
            .strip()
            .lower(): post
            for post in posts
            if post.reddit_id
        }

        existing_by_path = {
            normalize_path(row.path): row
            for row in db.query(
                DownloadedFile
            ).all()
        }

        image_map = (
            stash.get_image_file_map()
        )

        print(
            "Stash image paths:",
            len(image_map),
        )

        for raw_path, raw_image_id in (
            image_map.items()
        ):
            path = normalize_path(raw_path)

            if not path.startswith(root_prefix):
                outside_root += 1
                continue

            filename = os.path.basename(path)

            match = REDDIT_ID_PATTERN.match(
                filename
            )

            if not match:
                invalid_filename += 1
                continue

            reddit_id = (
                match.group(1)
                .strip()
                .lower()
            )

            post = post_map.get(reddit_id)

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
                    scene_id=None,
                    gallery_id=None,
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

        print()
        print("Created rows:", created)
        print("Updated rows:", updated)
        print("Unchanged rows:", unchanged)
        print(
            "No matching RedditPost:",
            no_post,
        )
        print(
            "Invalid filenames:",
            invalid_filename,
        )
        print(
            "Outside download root:",
            outside_root,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    print()
    print("Reconcile finished")
