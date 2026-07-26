from app.stash.client import StashClient


def run(config):

    print("\nReddit Stash Agent Doctor\n")

    stash_config = config["stash"]

    stash = StashClient(
        stash_config["url"],
        stash_config["api_key"]
    )

    try:
        performers = stash.get_performers()

        print("✓ Stash connected")
        print(f"✓ Found performers: {len(performers)}")

        print("\nFirst performers:")

        for performer in performers[:10]:
            print(
                f" - {performer['name']} ({performer['id']})"
            )

    except Exception as e:

        print("✗ Stash connection failed")
        print(e)
