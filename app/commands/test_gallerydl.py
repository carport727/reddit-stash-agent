from app.providers.reddit.gallerydl import download


def run(config):

    url = input(
        "Reddit URL: "
    )


    files = download(
        url,
        config["downloads"]["root"]
    )


    print()
    print(
        "Downloaded files:"
    )


    for file in files:
        print(file)
