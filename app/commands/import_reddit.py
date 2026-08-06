import os
import time

from app.database.database import SessionLocal
from app.database.models import DownloadedFile
from app.stash.client import StashClient
from collections import defaultdict


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
    print("Syncing Reddit downloads with Stash...")
    print()

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )

    db = SessionLocal()


    files = (
        db.query(DownloadedFile)
        .filter(
            DownloadedFile.stash_imported == False
        )
        .all()
    )


    print("Pending files:", len(files))


    if not files:
        print("Nothing to sync")
        db.close()
        return


    video_files = []
    image_files = []


    for file in files:

        ext = os.path.splitext(file.path)[1].lower()

        if ext in VIDEO_EXTENSIONS:
            video_files.append(file)

        elif ext in IMAGE_EXTENSIONS:
            image_files.append(file)


    print("Videos:", len(video_files))
    print("Images:", len(image_files))


    #
    # Images
    #
    # They only need Stash scan.
    #

    if image_files:

        print()
        print("Scanning images...")

        stash.scan_path(
            config["downloads"]["root"]
        )



    #
    # Videos
    #

    if video_files:

        print()
        print("Scanning videos...")

        stash.scan_path(
            config["downloads"]["root"]
        )


        print("Waiting for Stash scan...")
        time.sleep(15)


        print("Building scene map...")

        scene_map = stash.get_scene_file_map()


        print("Building image map...")

        image_map = stash.get_image_file_map()


        print("Building gallery map...")
        gallery_map = stash.get_gallery_map()

        linked = 0


        for file in video_files:

            scene_id = scene_map.get(
                file.path
            )


            if scene_id:

                print(
                    "Linked:",
                    file.path,
                    "->",
                    scene_id
                )

                file.scene_id = scene_id
                file.stash_imported = True

                linked += 1


        db.commit()


        print()
        print(
            "Video scenes linked:",
            linked
        )


        image_linked = 0

        for file in image_files:

            image_id = image_map.get(file.path)

            if image_id:

                print(
                    "Linked image:",
                    file.path,
                    "->",
                    image_id
                )

                file.image_id = image_id
                file.stash_imported = True

                image_linked += 1

        db.commit()

        print()
        print(
            "Images linked:",
            image_linked
        )

        print()
        print("Updating galleries...")

        post_images = defaultdict(list)

        for file in image_files:

            if file.image_id:

                post_images[file.reddit_post_id].append(file)

        for reddit_post_id, images in post_images.items():

            post = images[0].post

            if not post:
                continue

            gallery_title = post.title

            gallery_url = (
                f"https://reddit.com{post.permalink}"
            )

        gallery_id = gallery_map.get(
            gallery_url
        )

        if gallery_id:

            print(
                "Updating gallery:",
                gallery_title
            )

            stash.update_gallery(
                gallery_id,
                gallery_title,
                gallery_url
            )

        else:

            print(
                "Creating gallery:",
                gallery_title
            )

            gallery_id = stash.create_gallery(
                gallery_title,
                gallery_url
            )

        image_ids = [
            str(file.image_id)
            for file in images
        ]

        print(
            "Adding",
            len(image_ids),
            "images"
        )

        stash.add_gallery_images(
            gallery_id,
            image_ids
        )

    db.close()


    print()
    print("Sync finished")
