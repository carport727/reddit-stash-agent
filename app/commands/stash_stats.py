from app.stash.client import StashClient


def run(config):

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"]
    )

    query = """
    query {
      findScenes(
        filter: {
          per_page: 5
        }
      ) {
        scenes {
          id
          title
          files {
            path
          }
          performers {
            id
            name
          }
        }
      }
    }
    """

    result = stash.query(query)

    for scene in result["findScenes"]["scenes"]:

        print()
        print("ID:", scene["id"])
        print("TITLE:", scene["title"])

        print("FILES:")
        for f in scene["files"]:
            print(" ", f["path"])

        print("PERFORMERS:")
        for p in scene["performers"]:
            print(" ", p["name"])
