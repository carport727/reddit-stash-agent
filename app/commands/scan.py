from app.stash.client import StashClient
from app.reddit.parser import parse_reddit_urls


def run(config):

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )

    performers = stash.get_performers()

    print()
    print("Reddit sources found:")
    print()

    count = 0

    for performer in performers:

        sources = parse_reddit_urls(
            performer.get("urls")
        )

        if sources:

            count += 1

            print(
                f"✓ {performer['name']}"
            )

            for source in sources:
                print(
                    f"   {source['type']}: {source['name']}"
                )


    print()
    print(
        f"Total: {count} performers"
    )
