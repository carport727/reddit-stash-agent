import requests


class StashClient:

    def __init__(self, url, api_key):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.endpoint = f"{self.url}/graphql"


    def query(self, query, variables=None):

        response = requests.post(
            self.endpoint,
            headers={
                "ApiKey": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "variables": variables or {}
            },
            timeout=30
        )


        result = response.json()

        if "errors" in result:
            print("GRAPHQL ERRORS:")
            print(result["errors"])
            raise Exception(result["errors"])

        response.raise_for_status()

        return result["data"]


    def get_performers(self):

        query = """
        query {
          findPerformers(
            filter:{
              per_page:1000
            }
          ){
            performers{
              id
              name
              urls
            }
          }
        }
        """

        data = self.query(query)

        return data["findPerformers"]["performers"]

    def scan_path(self, path):

        query = """
        mutation MetadataScan($input: ScanMetadataInput!) {
          metadataScan(input: $input)
        }
        """

        data = self.query(
            query,
            {
                "input": {
                    "paths": [
                        path
                    ]
                }
            }
        )

        return data["metadataScan"]

    def get_scene_file_map(self):

        scenes = self.get_scenes()

        result = {}

        for scene in scenes:
            for file in scene["files"]:
                result[file["path"]] = scene["id"]

        return result

    def get_image_file_map(self):

        images = self.get_images()

        result = {}

        for image in images:

            if image["files"]:

                result[
                    image["files"][0]["path"]
                ] = image["id"]

        return result

    def set_scene_performer(self, scene_id, performer_id):

        mutation = """
        mutation($input: SceneUpdateInput!) {
          sceneUpdate(input: $input) {
            id
          }
        }
        """

        self.query(
            mutation,
            {
                "input": {
                    "id": scene_id,
                    "performer_ids": [performer_id]
                }
            }
        )

    def get_scenes(self):

        query = """
        query {
          findScenes(
            scene_filter: {},
            filter: { per_page: -1 }
          ) {
            scenes {
              id
              files {
                path
              }
            }
          }
        }
        """

        data = self.query(query)

        return data["findScenes"]["scenes"]

    def get_images(self):

        query = """
        query {
          findImages(
            image_filter: {},
            filter: { per_page: -1 }
          ) {
            images {
              id
              files {
                path
              }
            }
          }
        }
        """

        data = self.query(query)

        return data["findImages"]["images"]    

    def set_image_performer(self, image_id, performer_id):

        mutation = """
        mutation($input: ImageUpdateInput!) {
          imageUpdate(input: $input) {
            id
          }
        }
        """

        self.query(
            mutation,
            {
                "input": {
                    "id": image_id,
                    "performer_ids": [
                        performer_id
                    ]
                }
            }
        )
