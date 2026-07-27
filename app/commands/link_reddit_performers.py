import os

from app.database.database import SessionLocal
from app.database.models import RedditSource, RedditPost, DownloadedFile
from app.stash.client import StashClient


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


    print(
        "Sources with performers:",
        len(sources)
    )


    scene_updates = 0


    for source in sources:

        print()
        print(
            "Processing:",
            source.source_name,
            "->",
            source.performer_id
        )


        files = (
            db.query(DownloadedFile)
            .join(
                DownloadedFile.post
            )
            .filter(
                DownloadedFile.scene_id != None
            )
            .filter(
                RedditPost.source == source.source_name
            )
            .all()
        )


        for file in files:

            print(
                "Updating scene:",
                file.scene_id
            )

            scene_updates += 1

            stash.set_scene_performer(
                file.scene_id,
                source.performer_id
            )


            scene_updates += 1


    db.close()


    print()
    print(
        "Scenes updated:",
        scene_updates
    )
