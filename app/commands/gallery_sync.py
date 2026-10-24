from collections import defaultdict

from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditSource
from app.stash.client import StashClient


def performer_map(db):
    """Lowercase source name -> Stash performer ID."""
    return {
        source.source_name.strip().lower(): str(source.performer_id)
        for source in db.query(RedditSource).filter(RedditSource.performer_id.isnot(None)).all()
        if source.source_name
    }


def run(config):
    """One Stash gallery per Reddit post with images, titled after the post and linked to the performer."""
    dry_run = bool(config.get("dry_run"))
    if dry_run:
        print("DRY RUN enabled")

    stash = StashClient.from_config(config)
    db = SessionLocal()

    created = updated = images_added = performers_linked = skipped = 0

    try:
        performers = performer_map(db)

        post_images = defaultdict(list)
        for file in db.query(DownloadedFile).filter(DownloadedFile.image_id.isnot(None)).all():
            if file.post:
                post_images[file.reddit_post_id].append(file)

        gallery_map = stash.get_reddit_gallery_map()
        gallery_images = defaultdict(set)
        valid_image_ids = set()
        for image in stash.get_images(config["downloads"]["root"]):
            valid_image_ids.add(str(image["id"]))
            for gallery in image.get("galleries") or []:
                gallery_images[str(gallery["id"])].add(str(image["id"]))

        print(f"Posts with images: {len(post_images)}, existing Reddit galleries: {len(gallery_map)}")

        for files in post_images.values():
            post = files[0].post
            if not post.url:
                skipped += 1
                continue

            title = post.title or post.reddit_id
            image_ids = sorted({str(f.image_id) for f in files} & valid_image_ids)
            if not image_ids:
                skipped += 1
                continue

            gallery = gallery_map.get(post.url)
            if gallery:
                gallery_id = str(gallery["id"])
                if gallery.get("title") != title:
                    if not dry_run:
                        stash.update_gallery_title(gallery_id, title)
                    updated += 1
            else:
                print(f"Creating gallery: {title}")
                gallery_id = None if dry_run else str(stash.create_gallery(title, post.url))
                if gallery_id:
                    gallery_map[post.url] = {"id": gallery_id, "title": title, "performers": []}
                created += 1

            missing = [i for i in image_ids if i not in gallery_images.get(gallery_id, set())]
            if missing:
                if not dry_run:
                    try:
                        stash.add_gallery_images(gallery_id, missing)
                    except Exception as error:
                        print(f"Failed to add {len(missing)} images to gallery {gallery_id}: {error}")
                        skipped += 1
                        continue
                    gallery_images[gallery_id].update(missing)
                images_added += len(missing)

            performer_id = performers.get((post.source or "").strip().lower())
            linked_ids = {str(p["id"]) for p in (gallery or {}).get("performers") or []}
            if performer_id and gallery_id and not dry_run and performer_id not in linked_ids:
                if stash.add_performer("gallery", gallery_id, performer_id) == "added":
                    performers_linked += 1
                    gallery_map[post.url].setdefault("performers", []).append({"id": performer_id})

            if gallery_id and not dry_run:
                for file in files:
                    if file.gallery_id != int(gallery_id):
                        file.gallery_id = int(gallery_id)

        db.commit()

    finally:
        db.close()

    print(
        f"Galleries created: {created}, retitled: {updated}, images added: {images_added}, "
        f"performers linked: {performers_linked}, skipped: {skipped}"
    )
    return {"galleries_created": created, "gallery_images_added": images_added}
