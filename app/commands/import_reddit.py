import os
import time

from app.database.database import SessionLocal
from app.database.models import DownloadedFile
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
            DownloadedFile.scene_id == None
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
                linked += 1


        db.commit()


        print()
        print(
            "Video scenes linked:",
            linked
        )


    db.close()


    print()
    print("Sync finished")
