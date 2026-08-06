from collections import defaultdict

from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditSource
from app.stash.client import StashClient


def run(config):

    print()
    print("Syncing Reddit galleries...")
    print()

    dry_run = config.get("dry_run", False)

    if dry_run:
        print("DRY RUN enabled")
        print()

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )

    db = SessionLocal()

    try:
        files = (
            db.query(DownloadedFile)
            .filter(
                DownloadedFile.image_id.isnot(None)
            )
            .all()
        )

        sources = (
            db.query(RedditSource)
            .filter(
                RedditSource.performer_id.isnot(None)
            )
            .all()
        )

        performer_map = {
            source.source_name: source.performer_id
            for source in sources
        }

        post_images = defaultdict(list)

        for file in files:

            if not file.post:
                continue

            post_images[file.reddit_post_id].append(file)

        print("Imported image files:", len(files))
        print("Reddit posts with images:", len(post_images))
        print("Performer mappings:", len(performer_map))
        print()

        print("Loading existing Stash galleries...")

        gallery_map = stash.get_gallery_map()

        stash_images = stash.get_images()

        valid_image_ids = {
            str(image["id"])
            for image in stash_images
        }

        gallery_image_map = {}

        for image in stash_images:

            image_id = str(image["id"])

            for gallery in image.get("galleries", []):

                gallery_id = str(gallery["id"])

                gallery_image_map.setdefault(
                    gallery_id,
                    set()
                ).add(image_id)

        print("Existing galleries:", len(gallery_map))
        print("Existing Stash images:", len(valid_image_ids))
        print()

        created = 0
        updated = 0
        images_added = 0
        performers_linked = 0
        stale_images = 0
        skipped = 0

        for reddit_post_id, image_files in post_images.items():

            post = image_files[0].post

            if not post:
                skipped += 1
                continue

            gallery_url = post.url
            gallery_title = post.title or post.reddit_id

            if not gallery_url:
                print(
                    "Skipping post without URL:",
                    post.reddit_id
                )
                skipped += 1
                continue

            database_image_ids = {
                str(file.image_id)
                for file in image_files
                if file.image_id
            }

            stale_image_ids = sorted(
                database_image_ids - valid_image_ids
            )

            image_ids = sorted(
                database_image_ids & valid_image_ids
            )

            if stale_image_ids:

                print(
                    "Skipping stale image IDs:",
                    ", ".join(stale_image_ids)
                )

                stale_images += len(stale_image_ids)

            if not image_ids:
                skipped += 1
                continue

            print()
            print("Post:", post.reddit_id)
            print("Title:", gallery_title)
            print("URL:", gallery_url)
            print("Images:", len(image_ids))

            gallery = gallery_map.get(gallery_url)

            if gallery:

                gallery_id = str(gallery["id"])

                print("Gallery exists:", gallery_id)

                title_changed = (
                    gallery.get("title") != gallery_title
                )

                if title_changed:

                    print("Updating gallery metadata")

                    if not dry_run:
                        stash.update_gallery(
                            gallery_id,
                            gallery_title,
                            gallery_url
                        )

                    updated += 1

            else:

                print("Creating gallery")

                if dry_run:
                    gallery_id = None

                else:
                    gallery_id = stash.create_gallery(
                        gallery_title,
                        gallery_url
                    )

                    gallery = {
                        "id": gallery_id,
                        "title": gallery_title,
                        "url": gallery_url,
                        "images": [],
                    }

                    gallery_map[gallery_url] = gallery

                created += 1

            existing_image_ids = set()

            if gallery_id:
                existing_image_ids = (
                    gallery_image_map.get(
                        str(gallery_id),
                        set()
                    )
                )

            missing_image_ids = [
                image_id
                for image_id in image_ids
                if image_id not in existing_image_ids
            ]

            if missing_image_ids:

                print(
                    "Adding images:",
                    len(missing_image_ids)
                )

                if not dry_run:
                    try:
                        stash.add_gallery_images(
                            gallery_id,
                            missing_image_ids
                        )

                    except Exception as error:

                        print(
                            "Failed to add images:",
                            missing_image_ids
                        )
                        print("Error:", error)

                        skipped += len(
                            missing_image_ids
                        )

                        continue

                images_added += len(missing_image_ids)

                if gallery_id:

                    gallery_image_map.setdefault(
                        str(gallery_id),
                        set()
                    ).update(missing_image_ids)

            else:
                print("All images already linked")

            performer_id = performer_map.get(post.source)

            if performer_id:

                print(
                    "Setting performer:",
                    performer_id
                )

                if not dry_run:
                    stash.set_gallery_performer(
                        gallery_id,
                        performer_id
                    )

                performers_linked += 1

            else:
                print(
                    "No performer mapping for source:",
                    post.source
                )

            if not dry_run and gallery_id:

                try:
                    database_gallery_id = int(gallery_id)
                except (TypeError, ValueError):
                    database_gallery_id = None

                for file in image_files:
                    file.gallery_id = database_gallery_id

                db.commit()

        print()
        print("Gallery sync finished")
        print()
        print(
            "Created:",
            created
        )
        print(
            "Updated:",
            updated
        )
        print(
            "Added images:",
            images_added
        )
        print(
            "Linked performers:",
            performers_linked
        )
        print(
            "Skipping stale image IDs:",
            stale_images
        )

        print(
            "Skipped:",
            skipped
        )

    finally:
        db.close()
