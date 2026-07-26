from app.stash.client import StashClient


def run(config):

    print()
    print("Starting Stash scan...")
    print()


    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )


    path = config["downloads"]["root"]


    result = stash.scan_path(
        path
    )


    print(
        "Scan started:",
        result
    )
