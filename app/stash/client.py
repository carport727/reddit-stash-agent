import time

import requests


class StashError(Exception):
    pass


class StashClient:
    def __init__(self, url, api_key, timeout=60):
        self.url = url.rstrip("/")
        self.endpoint = f"{self.url}/graphql"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if api_key:
            self.session.headers["ApiKey"] = api_key

    @classmethod
    def from_config(cls, config):
        return cls(config["stash"]["url"], config["stash"]["api_key"])

    def query(self, query, variables=None):
        try:
            response = self.session.post(
                self.endpoint,
                json={"query": query, "variables": variables or {}},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise StashError(f"Stash not reachable at {self.endpoint}: {exc}") from exc

        if response.status_code in (401, 403):
            raise StashError(f"Stash rejected the API key (HTTP {response.status_code})")

        try:
            result = response.json()
        except ValueError:
            raise StashError(
                f"Stash returned HTTP {response.status_code} without JSON: {response.text[:200]}"
            ) from None

        if result.get("errors"):
            messages = "; ".join(error.get("message", str(error)) for error in result["errors"])
            raise StashError(f"GraphQL error: {messages}")

        response.raise_for_status()
        return result["data"]

    # Performers

    def get_reddit_performers(self):
        data = self.query(
            """
            query {
              findPerformers(
                performer_filter: { url: { value: "reddit.com", modifier: INCLUDES } }
                filter: { per_page: -1 }
              ) {
                performers { id name urls }
              }
            }
            """
        )
        return data["findPerformers"]["performers"]

    def count_performers(self):
        data = self.query("query { findPerformers(filter: { per_page: 0 }) { count } }")
        return data["findPerformers"]["count"]

    # Scans and jobs

    def scan_path(self, path):
        data = self.query(
            "mutation($input: ScanMetadataInput!) { metadataScan(input: $input) }",
            {"input": {"paths": [path]}},
        )
        return data["metadataScan"]

    def wait_for_job(self, job_id, timeout=1800, interval=3):
        """Wait until a Stash job leaves the queue. Returns its last known status."""
        deadline = time.monotonic() + timeout
        status = None

        while time.monotonic() < deadline:
            data = self.query(
                "query($input: FindJobInput!) { findJob(input: $input) { status progress error } }",
                {"input": {"id": str(job_id)}},
            )
            job = data["findJob"]
            if job is None:
                return status or "FINISHED"

            status = job["status"]
            if status in ("FINISHED", "CANCELLED", "FAILED"):
                return status

            time.sleep(interval)

        return "TIMEOUT"

    def generate_scene_media(self, scene_ids):
        scene_ids = sorted({str(scene_id) for scene_id in scene_ids if scene_id is not None})
        if not scene_ids:
            return None

        data = self.query(
            "mutation($input: GenerateMetadataInput!) { metadataGenerate(input: $input) }",
            {"input": {"covers": True, "previews": True, "sceneIDs": scene_ids, "overwrite": False}},
        )
        return data["metadataGenerate"]

    # Files below the download root

    def get_scene_file_map(self, root):
        data = self.query(
            """
            query($path: String!) {
              findScenes(
                scene_filter: { path: { value: $path, modifier: INCLUDES } }
                filter: { per_page: -1 }
              ) {
                scenes { id files { path } }
              }
            }
            """,
            {"path": root},
        )
        return {file["path"]: scene["id"] for scene in data["findScenes"]["scenes"] for file in scene["files"]}

    def get_images(self, root):
        data = self.query(
            """
            query($path: String!) {
              findImages(
                image_filter: { path: { value: $path, modifier: INCLUDES } }
                filter: { per_page: -1 }
              ) {
                images {
                  id
                  galleries { id }
                  visual_files {
                    ... on ImageFile { path }
                    ... on VideoFile { path }
                  }
                }
              }
            }
            """,
            {"path": root},
        )
        return data["findImages"]["images"]

    def get_image_file_map(self, root):
        result = {}
        for image in self.get_images(root):
            for visual_file in image.get("visual_files") or []:
                if visual_file.get("path"):
                    result[visual_file["path"]] = image["id"]
        return result

    # Galleries

    def get_reddit_gallery_map(self):
        data = self.query(
            """
            query {
              findGalleries(
                gallery_filter: { url: { value: "reddit.com", modifier: INCLUDES } }
                filter: { per_page: -1 }
              ) {
                galleries { id title urls }
              }
            }
            """
        )
        result = {}
        for gallery in data["findGalleries"]["galleries"]:
            for url in gallery.get("urls") or []:
                result.setdefault(url, gallery)
        return result

    def create_gallery(self, title, url):
        data = self.query(
            "mutation($input: GalleryCreateInput!) { galleryCreate(input: $input) { id } }",
            {"input": {"title": title, "urls": [url]}},
        )
        return data["galleryCreate"]["id"]

    def update_gallery_title(self, gallery_id, title):
        self.query(
            "mutation($input: GalleryUpdateInput!) { galleryUpdate(input: $input) { id } }",
            {"input": {"id": str(gallery_id), "title": title}},
        )

    def add_gallery_images(self, gallery_id, image_ids):
        if not image_ids:
            return None

        return self.query(
            "mutation($input: GalleryAddInput!) { addGalleryImages(input: $input) }",
            {"input": {"gallery_id": str(gallery_id), "image_ids": [str(image_id) for image_id in image_ids]}},
        )

    # Performer links on scenes, images and galleries

    _OBJECTS = {
        "scene": ("findScene", "sceneUpdate", "SceneUpdateInput"),
        "image": ("findImage", "imageUpdate", "ImageUpdateInput"),
        "gallery": ("findGallery", "galleryUpdate", "GalleryUpdateInput"),
    }

    def get_performer_ids(self, kind, object_id):
        """Performer IDs on a Stash object, or None if the object does not exist."""
        find, _, _ = self._OBJECTS[kind]
        data = self.query(
            f"query($id: ID!) {{ {find}(id: $id) {{ id performers {{ id }} }} }}",
            {"id": str(object_id)},
        )
        obj = data[find]
        if obj is None:
            return None
        return {str(performer["id"]) for performer in obj["performers"]}

    def add_performer(self, kind, object_id, performer_id):
        """Add a performer without touching existing ones.

        Returns "added", "exists" or "missing" (object no longer in Stash).
        """
        existing = self.get_performer_ids(kind, object_id)
        if existing is None:
            return "missing"

        performer_id = str(performer_id)
        if performer_id in existing:
            return "exists"

        _, update, input_type = self._OBJECTS[kind]
        self.query(
            f"mutation($input: {input_type}!) {{ {update}(input: $input) {{ id }} }}",
            {"input": {"id": str(object_id), "performer_ids": sorted(existing | {performer_id})}},
        )
        return "added"
