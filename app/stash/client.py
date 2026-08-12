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

            for visual_file in image.get(
                "visual_files",
                []
            ):

                path = visual_file.get("path")

                if not path:
                    continue

                result[path] = image["id"]

        return result


    def get_gallery_map(self):

        galleries = self.get_galleries()

        result = {}

        for gallery in galleries:

            if gallery["url"]:
                result[gallery["url"]] = gallery

        return result

    def create_gallery(
        self,
        title,
        url
    ):

        mutation = """
        mutation($input: GalleryCreateInput!) {
          galleryCreate(input: $input) {
            id
          }
        }
        """

        data = self.query(
            mutation,
            {
                "input": {
                    "title": title,
                    "url": url
                }
            }
        )

        return data["galleryCreate"]["id"]


    def set_scene_performers(
        self,
        scene_id,
        performer_ids,
    ):

        performer_ids = sorted({
            str(performer_id)
            for performer_id in performer_ids
            if performer_id is not None
        })

        mutation = """
        mutation($input: SceneUpdateInput!) {
          sceneUpdate(input: $input) {
            id
          }
        }
        """

        return self.query(
            mutation,
            {
                "input": {
                    "id": str(scene_id),
                    "performer_ids":
                        performer_ids,
                }
            },
        )


    def set_scene_performer(
        self,
        scene_id,
        performer_id,
    ):

        if not hasattr(
            self,
            "_scene_performer_cache",
        ):
            self._scene_performer_cache = {
                str(scene["id"]): {
                    str(performer["id"])
                    for performer in scene.get(
                        "performers",
                        [],
                    )
                }
                for scene in self.get_scenes()
            }

        scene_key = str(scene_id)

        existing = (
            self._scene_performer_cache
            .setdefault(scene_key, set())
        )

        performer_key = str(performer_id)

        if performer_key in existing:
            return None

        merged = existing | {
            performer_key
        }

        result = self.set_scene_performers(
            scene_key,
            merged,
        )

        self._scene_performer_cache[
            scene_key
        ] = merged

        return result

    def get_scenes(self):

        query = """
        query {
          findScenes(
            scene_filter: {},
            filter: { per_page: -1 }
          ) {
            scenes {
              id

              performers {
                id
                name
              }

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
            filter: {
              per_page: -1
            }
          ) {
            images {
              id
              title

              performers {
                id
                name
              }

              galleries {
                id
                title
                url
              }

              visual_files {
                __typename

                ... on ImageFile {
                  id
                  path
                }

                ... on VideoFile {
                  id
                  path
                }
              }
            }
          }
        }
        """

        data = self.query(query)

        return data["findImages"]["images"]

    def get_gallery_image_map(self):

        images = self.get_images()

        result = {}

        for image in images:

            for gallery in image.get("galleries", []):

                gallery_id = str(gallery["id"])

                if gallery_id not in result:
                    result[gallery_id] = set()

                result[gallery_id].add(
                    str(image["id"])
                )

        return result

    def get_galleries(self):

        query = """
        query {
          findGalleries(
            filter: {
              per_page: -1
            }
          ) {
            galleries {
              id
              title
              url

              performers {
                id
                name
              }
            }
          }
        }
        """

        data = self.query(query)

        return data["findGalleries"]["galleries"]


    def set_image_performers(
        self,
        image_id,
        performer_ids,
    ):

        performer_ids = sorted({
            str(performer_id)
            for performer_id in performer_ids
            if performer_id is not None
        })

        mutation = """
        mutation($input: ImageUpdateInput!) {
          imageUpdate(input: $input) {
            id
          }
        }
        """

        return self.query(
            mutation,
            {
                "input": {
                    "id": str(image_id),
                    "performer_ids":
                        performer_ids,
                }
            },
        )


    def set_image_performer(
        self,
        image_id,
        performer_id,
    ):

        if not hasattr(
            self,
            "_image_performer_cache",
        ):
            self._image_performer_cache = {
                str(image["id"]): {
                    str(performer["id"])
                    for performer in image.get(
                        "performers",
                        [],
                    )
                }
                for image in self.get_images()
            }

        image_key = str(image_id)

        existing = (
            self._image_performer_cache
            .setdefault(image_key, set())
        )

        performer_key = str(performer_id)

        if performer_key in existing:
            return None

        merged = existing | {
            performer_key
        }

        result = self.set_image_performers(
            image_key,
            merged,
        )

        self._image_performer_cache[
            image_key
        ] = merged

        return result


    def set_gallery_performers(
        self,
        gallery_id,
        performer_ids,
    ):

        performer_ids = sorted({
            str(performer_id)
            for performer_id in performer_ids
            if performer_id is not None
        })

        mutation = """
        mutation($input: GalleryUpdateInput!) {
          galleryUpdate(input: $input) {
            id
          }
        }
        """

        return self.query(
            mutation,
            {
                "input": {
                    "id": str(gallery_id),
                    "performer_ids":
                        performer_ids,
                }
            },
        )


    def set_gallery_performer(
        self,
        gallery_id,
        performer_id,
    ):

        if not hasattr(
            self,
            "_gallery_performer_cache",
        ):
            self._gallery_performer_cache = {
                str(gallery["id"]): {
                    str(performer["id"])
                    for performer in gallery.get(
                        "performers",
                        [],
                    )
                }
                for gallery in self.get_galleries()
            }

        gallery_key = str(gallery_id)

        existing = (
            self._gallery_performer_cache
            .setdefault(gallery_key, set())
        )

        performer_key = str(performer_id)

        if performer_key in existing:
            return None

        merged = existing | {
            performer_key
        }

        result = self.set_gallery_performers(
            gallery_key,
            merged,
        )

        self._gallery_performer_cache[
            gallery_key
        ] = merged

        return result

    def update_gallery(
        self,
        gallery_id,
        title,
        url
    ):

        mutation = """
        mutation($input: GalleryUpdateInput!) {
          galleryUpdate(input: $input) {
            id
          }
        }
        """

        self.query(
            mutation,
            {
                "input": {
                    "id": gallery_id,
                    "title": title,
                    "url": url
                }
            }
        )

    def add_gallery_images(
        self,
        gallery_id,
        image_ids
    ):

        if not image_ids:
            return None

        mutation = """
        mutation($input: GalleryAddInput!) {
          addGalleryImages(input: $input)
        }
        """

        return self.query(
            mutation,
            {
                "input": {
                    "gallery_id": str(gallery_id),
                    "image_ids": [
                        str(image_id)
                        for image_id in image_ids
                    ]
                }
            }
        )


    def generate_scene_media(
        self,
        scene_ids,
    ):
        scene_ids = sorted({
            str(scene_id)
            for scene_id in scene_ids
            if scene_id is not None
        })

        if not scene_ids:
            return None

        mutation = """
        mutation($input: GenerateMetadataInput!) {
          metadataGenerate(input: $input)
        }
        """

        return self.query(
            mutation,
            {
                "input": {
                    "covers": True,
                    "previews": True,
                    "sceneIDs": scene_ids,
                    "overwrite": False,
                }
            },
        )
