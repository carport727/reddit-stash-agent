import os

from app.database.database import SessionLocal
from app.database.models import (
    RedditSource,
    DownloadedFile,
)
from app.stash.client import StashClient


VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".webm",
    ".mov",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
}


def run(config):

    print()
    print("Linking Reddit performers...")
    print()

    dry_run = config.get(
        "dry_run",
        False,
    )

    if dry_run:
        print("DRY RUN enabled")
        print()

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"],
    )

    db = SessionLocal()

    try:

        sources = (
            db.query(RedditSource)
            .filter(
                RedditSource.performer_id.isnot(None)
            )
            .all()
        )

        performer_map = {
            source.source_name.strip().lower():
                str(source.performer_id)
            for source in sources
            if source.source_name
        }

        print("Sources:")

        for source_name, performer_id in (
            performer_map.items()
        ):
            print(
                " ",
                source_name,
                "->",
                performer_id,
            )

        files = (
            db.query(DownloadedFile)
            .filter(
                DownloadedFile.path.like(
                    "/Stash/Download/Reddit/%"
                )
            )
            .filter(
                DownloadedFile.performer_linked
                == False
            )
            .all()
        )

        print()
        print("Reddit files:", len(files))

        updated = 0
        no_mapping = 0
        no_stash_object = 0
        stale_objects = 0
        unknown_type = 0

        for file in files:

            post = file.post

            if not post:

                print(
                    "Missing Reddit post for:",
                    file.path,
                )

                no_mapping += 1
                continue

            source = post.source

            source_key = (
                source.strip().lower()
                if source
                else None
            )

            performer_id = performer_map.get(
                source_key
            )

            if not performer_id:

                print(
                    "No performer mapping:",
                    source,
                    "-",
                    file.path,
                )

                no_mapping += 1
                continue

            filename = os.path.basename(
                file.path
            )

            ext = os.path.splitext(
                filename
            )[1].lower()

            print()
            print(filename)
            print(
                "Source:",
                source,
                "Performer:",
                performer_id,
            )

            try:

                if ext in VIDEO_EXTENSIONS:

                    if not file.scene_id:

                        print("No scene found")
                        no_stash_object += 1
                        continue

                    print(
                        "Scene:",
                        file.scene_id,
                    )

                    if dry_run:

                        print(
                            "DRY RUN - "
                            "would update scene"
                        )

                    else:

                        stash.set_scene_performer(
                            file.scene_id,
                            performer_id,
                        )

                elif ext in IMAGE_EXTENSIONS:

                    if not file.image_id:

                        print("No image found")
                        no_stash_object += 1
                        continue

                    print(
                        "Image:",
                        file.image_id,
                    )

                    if dry_run:

                        print(
                            "DRY RUN - "
                            "would update image"
                        )

                    else:

                        stash.set_image_performer(
                            file.image_id,
                            performer_id,
                        )

                else:

                    print(
                        "Unknown type:",
                        ext,
                    )

                    unknown_type += 1
                    continue

            except Exception as error:

                print(
                    "Stash object is missing "
                    "or could not be updated"
                )
                print("Error:", error)

                if not dry_run:

                    if ext in VIDEO_EXTENSIONS:
                        file.scene_id = None

                    elif ext in IMAGE_EXTENSIONS:
                        file.image_id = None

                    file.stash_imported = False
                    file.performer_linked = False

                    db.commit()

                stale_objects += 1
                continue

            if not dry_run:

                file.performer_linked = True
                db.commit()

            updated += 1

        print()
        print(
            "Would update / Updated:",
            updated,
        )
        print(
            "No performer mapping:",
            no_mapping,
        )
        print(
            "No Stash object:",
            no_stash_object,
        )
        print(
            "Stale Stash objects:",
            stale_objects,
        )
        print(
            "Unknown types:",
            unknown_type,
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()
