import os

from app.database.database import SessionLocal
from app.database.models import RedditSource, DownloadedFile
from app.stash.client import StashClient


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

            updates += 1


        elif ext in IMAGE_EXTENSIONS:


            image = stash.find_image_by_path(
                filename
            )


            if not image:

                print(
                    "Image not found"
                )

                skipped += 1
                continue


            print(
                "Image:",
                image["id"]
            )


            if config.get("dry_run"):

                print(
                    "DRY RUN - would update image"
                )

            else:

                stash.set_image_performer(
                    image["id"],
                    performer_id
                )


            updates += 1


        else:

            print(
                "Unknown type:",
                ext
            )

            skipped += 1



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
