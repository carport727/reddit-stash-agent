import subprocess

from app.database.database import SessionLocal
from app.database.models import RedditPost


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
                    post.url
                ],
                capture_output=True,
                text=True
            )


            if output.returncode == 0:

                post.downloaded = True

                downloaded += 1

                print(
                    "DONE:",
                    post.title
                )

            else:

                print(
                    "FAILED:",
                    post.url
                )

                print(
                    output.stderr
                )


        db.commit()


        print()
        print(
            "Downloaded:",
            downloaded
        )


    finally:

        db.close()
