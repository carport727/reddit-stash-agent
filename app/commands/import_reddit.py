import os
import time

from app.database.database import SessionLocal
from app.database.models import DownloadedFile
from app.stash.client import StashClient


VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".webm",
    ".mov",
}


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
}


def wait_for_paths(
    map_loader,
    expected_paths,
    label,
    attempts=30,
    interval=5,
):
    object_map = {}

    for attempt in range(
        1,
        attempts + 1,
    ):
        object_map = map_loader()

        found_paths = {
            path
            for path in expected_paths
            if path in object_map
        }

        print(
            f"{label} found:",
            len(found_paths),
            "/",
            len(expected_paths),
            f"(attempt {attempt}/{attempts})",
        )

        if found_paths == expected_paths:
            break

        if attempt < attempts:
            time.sleep(interval)

    return object_map


def run(config):
    print()
    print(
        "Syncing Reddit downloads "
        "with Stash..."
    )
    print()

    stash = StashClient(
        config["stash"]["url"],
        config["stash"]["api_key"],
    )

    db = SessionLocal()

    imported_scene_ids = []

    try:
        files = (
            db.query(DownloadedFile)
            .filter(
                DownloadedFile
                .stash_imported
                == False
            )
            .all()
        )

        print(
            "Pending files:",
            len(files),
        )

        if not files:
            print(
                "Nothing to sync"
            )
            return

        video_files = []
        image_files = []
        unknown_files = []

        for file in files:
            ext = os.path.splitext(
                file.path
            )[1].lower()

            if ext in VIDEO_EXTENSIONS:
                video_files.append(
                    file
                )

            elif ext in IMAGE_EXTENSIONS:
                image_files.append(
                    file
                )

            else:
                unknown_files.append(
                    file
                )

        print(
            "Videos:",
            len(video_files),
        )

        print(
            "Images:",
            len(image_files),
        )

        print(
            "Unknown:",
            len(unknown_files),
        )

        scan_required = bool(
            video_files
            or image_files
        )

        if scan_required:
            print()
            print(
                "Starting Stash "
                "metadata scan..."
            )

            stash.scan_path(
                config[
                    "downloads"
                ][
                    "root"
                ]
            )

        image_map = {}

        if image_files:
            print()
            print(
                "Waiting for Stash "
                "image scan..."
            )

            expected_image_paths = {
                file.path
                for file in image_files
            }

            image_map = wait_for_paths(
                stash.get_image_file_map,
                expected_image_paths,
                "Images",
            )

        scene_map = {}

        if video_files:
            print()
            print(
                "Waiting for Stash "
                "video scan..."
            )

            expected_video_paths = {
                file.path
                for file in video_files
            }

            scene_map = wait_for_paths(
                stash.get_scene_file_map,
                expected_video_paths,
                "Scenes",
            )

        video_linked = 0
        video_missing = 0

        for file in video_files:
            scene_id = scene_map.get(
                file.path
            )

            if not scene_id:
                print(
                    "Scene not found:",
                    file.path,
                )

                video_missing += 1
                continue

            print(
                "Linked scene:",
                file.path,
                "->",
                scene_id,
            )

            file.scene_id = int(
                scene_id
            )

            file.stash_imported = True

            imported_scene_ids.append(
                str(scene_id)
            )

            video_linked += 1

        image_linked = 0
        image_missing = 0

        for file in image_files:
            image_id = image_map.get(
                file.path
            )

            if not image_id:
                print(
                    "Image not found:",
                    file.path,
                )

                image_missing += 1
                continue

            print(
                "Linked image:",
                file.path,
                "->",
                image_id,
            )

            file.image_id = int(
                image_id
            )

            file.stash_imported = True

            image_linked += 1

        db.commit()

        print()
        print(
            "Video scenes linked:",
            video_linked,
        )

        print(
            "Video scenes missing:",
            video_missing,
        )

        print(
            "Images linked:",
            image_linked,
        )

        print(
            "Images missing:",
            image_missing,
        )

        if imported_scene_ids:
            unique_scene_ids = sorted(
                set(
                    imported_scene_ids
                )
            )

            print()
            print(
                "Generating scene "
                "covers and previews..."
            )

            print(
                "Scenes:",
                len(
                    unique_scene_ids
                ),
            )

            stash.generate_scene_media(
                unique_scene_ids
            )

            print(
                "Generate task "
                "started"
            )

        else:
            print()
            print(
                "No new video scenes "
                "to generate"
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    print()
    print(
        "Sync finished"
    )
