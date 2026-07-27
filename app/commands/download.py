import os
import subprocess

from app.database.database import SessionLocal
from app.database.models import RedditPost, DownloadedFile


def run(config):

    db = SessionLocal()

    try:

        posts = db.query(
            RedditPost
        ).filter_by(
            downloaded=False
        ).all()


        print()
        print("Downloading Reddit media...")
        print(
            "Pending:",
            len(posts)
        )
        print()


        downloaded = 0


        for post in posts:

            print(
                "Downloading:",
                post.url
            )


            output = subprocess.run(
                [
                    "gallery-dl",
                    "-d",
                    config["downloads"]["root"],
                    post.url,
                ],
                capture_output=True,
                text=True,
            )

            print("GALLERY STDOUT:")
            print(output.stdout)

            print("GALLERY STDERR:")
            print(output.stderr)


            if output.stdout.strip():

                post.downloaded = True
                downloaded += 1

                for line in output.stdout.splitlines():

                    if not line.startswith("# "):
                        continue

                    path = line[2:].strip()

                    if not path:
                        continue

                    existing = db.query(
                        DownloadedFile
                    ).filter_by(
                        path=path
                    ).first()

                    if existing:
                        continue

                    db.add(
                        DownloadedFile(
                            reddit_post_id=post.id,
                            path=path,
                        )
                    )

                print(
                    "DONE:",
                    post.title
                )

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print("DATABASE ERROR:", e)


        print()
        print(
            "Downloaded:",
            downloaded
        )


    finally:

        db.close()
