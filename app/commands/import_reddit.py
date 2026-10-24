import os
import time

from app.database.database import SessionLocal
from app.database.models import DownloadedFile
from app.stash.client import StashClient

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".webm", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp",
}  # fmt: skip

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp"}


def media_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return None


def wait_for_paths(map_loader, expected_paths, label, attempts=6, interval=5):
    """Stash may still be processing files after the scan job ends; retry a few times."""
    object_map = {}
    for attempt in range(1, attempts + 1):
        object_map = map_loader()
        found = sum(1 for path in expected_paths if path in object_map)
        print(f"{label} found: {found}/{len(expected_paths)}")
        if found == len(expected_paths):
            break
        if attempt < attempts:
            time.sleep(interval)
    return object_map


def run(config):
    root = config["downloads"]["root"]
    stash = StashClient.from_config(config)
    db = SessionLocal()

    linked_scenes = linked_images = missing = ignored = 0
    generate_ids = []

    try:
        files = (
            db.query(DownloadedFile)
            .filter(DownloadedFile.stash_imported.is_(False), DownloadedFile.ignored.isnot(True))
            .all()
        )
        print(f"Files to import into Stash: {len(files)}")
        if not files:
            return {"scenes_linked": 0, "images_linked": 0, "import_missing": 0}

        videos, images = [], []
        for file in files:
            kind = media_kind(file.path)
            if kind == "video":
                videos.append(file)
            elif kind == "image":
                images.append(file)
            else:
                file.ignored = True
                ignored += 1
                print(f"Ignoring unsupported file type: {file.path}")
        db.commit()

        if videos or images:
            print(f"Starting Stash scan of {root} ({len(videos)} videos, {len(images)} images)")
            job_id = stash.scan_path(root)
            status = stash.wait_for_job(job_id)
            print(f"Stash scan job {job_id}: {status}")

        if images:
            image_map = wait_for_paths(lambda: stash.get_image_file_map(root), {f.path for f in images}, "Images")
            for file in images:
                image_id = image_map.get(file.path)
                if not image_id:
                    missing += 1
                    print(f"Image not found in Stash: {file.path}")
                    continue
                file.image_id = int(image_id)
                file.stash_imported = True
                linked_images += 1

        if videos:
            scene_map = wait_for_paths(lambda: stash.get_scene_file_map(root), {f.path for f in videos}, "Scenes")
            for file in videos:
                scene_id = scene_map.get(file.path)
                if not scene_id:
                    missing += 1
                    print(f"Scene not found in Stash: {file.path}")
                    continue
                file.scene_id = int(scene_id)
                file.stash_imported = True
                generate_ids.append(scene_id)
                linked_scenes += 1

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if generate_ids:
        job_id = stash.generate_scene_media(generate_ids)
        print(f"Started cover/preview generation for {len(set(generate_ids))} scenes (job {job_id})")

    print(f"Scenes linked: {linked_scenes}, images linked: {linked_images}, not found: {missing}, ignored: {ignored}")
    return {"scenes_linked": linked_scenes, "images_linked": linked_images, "import_missing": missing}
