from datetime import datetime

from app.database.database import SessionLocal
from app.database.models import RedditSource, RedditPost
from app.providers.reddit.rss import fetch_posts


def run(config):

    db = SessionLocal()

    try:

        sources = db.query(
            RedditSource
        ).all()


        added = 0
        skipped = 0


        print()
        print("Checking Reddit sources...")
        print()


        for source in sources:

           # print(
           #     f"Source: {source.source_type}:{source.source_name}"
           # )


            posts = fetch_posts(
                source.source_type,
                source.source_name
            )

            source.last_scan = datetime.utcnow()

            for post in posts:

                exists = db.query(
                    RedditPost
                ).filter_by(
                    reddit_id=post["reddit_id"]
                ).first()


                if exists:

                    skipped += 1
                    continue


                reddit_post = RedditPost(
                    reddit_id=post["reddit_id"],
                    source=source.source_name,
                    url=post["url"],
                    title=post.get("title"),
                    downloaded=False
                )


                db.add(
                    reddit_post
                )

                added += 1

               # print(
               #     " NEW:",
               #     post["title"]
               # )


        db.commit()

    finally:
        db.close()


    print()
    print("Finished")
    print(
        f"Added: {added}"
    )
    print(
        f"Skipped: {skipped}"
    )
