from app.database.database import SessionLocal
from app.database.models import RedditSource
from app.stash.client import StashClient


def extract_reddit_urls(urls):

    reddit_urls = []

    for url in urls:

        if "reddit.com" in url:
    
            reddit_urls.append(url)

    return reddit_urls



def parse_reddit_source(url):

    if "/user/" in url:

        name = url.split("/user/")[1].split("/")[0]

        return "user", name


    if "/r/" in url:

        name = url.split("/r/")[1].split("/")[0]

        return "subreddit", name


    return None, None



def run(config):

    db = SessionLocal()

    try:

        print()
        print("Syncing Reddit sources from Stash...")
        print()


        stash = StashClient(
            config["stash"]["url"],
            config["stash"]["api_key"]
        )


        performers = stash.get_performers()


        added = 0
        skipped = 0


        for performer in performers:


            reddit_urls = extract_reddit_urls(
                performer.get("urls", [])
            )


            if not reddit_urls:
                continue

            for reddit_url in reddit_urls:



                source_type, source_name = parse_reddit_source(
                    reddit_url
                )


                if not source_name:
                    continue



                exists = db.query(
                   RedditSource
                ).filter_by(
                   performer_id=performer["id"],
                   source_name=source_name
                ).first()



                if exists:

                    skipped += 1
                    continue



                source = RedditSource(

                    performer_id=performer["id"],

                    source_type=source_type,

                    source_name=source_name

                )


                db.add(source)

                added += 1


                print(
                    "NEW:",
                    performer["name"],
                    "->",
                    reddit_url
                )



        db.commit()



        print()
        print("Finished")
        print(
            "Added:",
            added
        )

        print(
            "Skipped:",
            skipped
        )


    finally:

        db.close()
