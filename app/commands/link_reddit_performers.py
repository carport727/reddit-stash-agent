import os

from app.database.database import SessionLocal
from app.database.models import RedditSource, DownloadedFile
from app.stash.client import StashClient
from collections import defaultdict


VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".webm",
    ".mov"
}


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp"
}


def run(config):

    print()
    print("Linking Reddit performers...")
    print()


    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )


    db = SessionLocal()


    sources = (
        db.query(RedditSource)
        .filter(
            RedditSource.performer_id != None
        )
        .all()
    )


    print("Sources:")

    for s in sources:
        print(
            " ",
            s.source_name,
            "->",
            s.performer_id
        )


    files = (
        db.query(DownloadedFile)
        .filter(
            DownloadedFile.path.like(
                "/Stash/Download/Reddit/%"
            )
        )
        .filter(
            DownloadedFile.performer_linked == False
        )
        .all()
    )


    print()
    print("Reddit files:", len(files))
    print(
        "Videos:",
        sum(
            1 for f in files
            if os.path.splitext(f.path)[1].lower() in VIDEO_EXTENSIONS
        )
    )

    print(
        "Images:",
        sum(
            1 for f in files
            if os.path.splitext(f.path)[1].lower() in IMAGE_EXTENSIONS
        )
    )


    updates = 0
    skipped = 0


    performer_map = {
        s.source_name: s.performer_id
        for s in sources
    }

    gallery_map = stash.get_gallery_map()

    post_images = defaultdict(list)

    for file in files:

        ext = os.path.splitext(file.path)[1].lower()

        if (
            ext in IMAGE_EXTENSIONS
            and file.image_id
        ):
            post_images[file.reddit_post_id].append(file)


    for file in files:

        source = file.post.source if file.post else None

        performer_id = performer_map.get(source)


        if not performer_id:
            skipped += 1
            continue


        filename = os.path.basename(file.path)
        ext = os.path.splitext(filename)[1].lower()


        print()
        print(filename)
        print(
            "Source:",
            source,
            "Performer:",
            performer_id
        )


        if ext in VIDEO_EXTENSIONS:

            if not file.scene_id:
                print("No scene found")
                skipped += 1
                continue


            print(
                "Scene:",
                file.scene_id
            )


            if config.get("dry_run"):

                print(
                    "DRY RUN - would update scene"
                )

            else:

                stash.set_scene_performer(
                    file.scene_id,
                    performer_id
                )

                file.performer_linked = True
                db.commit()

            updates += 1


        elif ext in IMAGE_EXTENSIONS:

            if not file.image_id:
                print("No image found")
                skipped += 1
                continue

            print(
                "Image:",
                file.image_id
            )

            if config.get("dry_run"):

                print(
                    "DRY RUN - would update image"
                )

            else:

                stash.set_image_performer(
                    file.image_id,
                    performer_id
                )

                file.performer_linked = True

                db.commit()

            updates += 1


        else:

            print(
                "Unknown type:",
                ext
            )

            skipped += 1


    print()
    print("Updating galleries...")

    for reddit_post_id, images in post_images.items():

        post = images[0].post

        if not post:
            continue

        gallery_url = f"https://reddit.com{post.permalink}"

        gallery_id = gallery_map.get(gallery_url)

        if not gallery_id:

            print(
                "Gallery not found:",
                gallery_url
            )

            continue

        performer_id = performer_map.get(post.source)

        if performer_id:

            print(
                "Gallery:",
                gallery_id,
                "Performer:",
                performer_id
            )

            if not config.get("dry_run"):

                stash.set_gallery_performer(
                    gallery_id,
                    performer_id
                )


    db.close()


    print()
    print(
        "Would update / Updated:",
        updates
    )

    print(
        "Skipped:",
        skipped
    )
