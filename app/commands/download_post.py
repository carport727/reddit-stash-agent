"""Download one Reddit post on request and import it into Stash.

Same pipeline as the sync (gallery-dl with the Reddit cookies, Stash import, gallery, performer),
limited to one post. The post is recorded in the agent DB, so the sync never downloads it again.
"""

import json
import os
import subprocess

from app.commands.download import (
    BLOCK_MARKERS,
    GALLERY_DL_TIMEOUT,
    extract_downloaded_paths,
    gallery_dl_options,
    is_blocked,
    run_gallery_dl,
    short_error,
)
from app.commands.import_reddit import import_files, media_kind
from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost, RedditSource
from app.providers.reddit.rss import login_cookie_status
from app.reddit.parser import parse_post_url, parse_reddit_urls
from app.stash.client import StashClient, StashError

STEPS = ["Check link", "Read post", "Download", "Import into Stash", "Gallery and performer"]

# gallery-dl -j message types
MESSAGE_DIRECTORY = 2
MESSAGE_QUEUE = 6


class PostDownloadError(Exception):
    """code: invalid_url | cookies_missing | cookies_expired | reddit_blocked | not_found | no_media
    | download_failed | stash_error"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _blocked_error(text, config):
    cookies = login_cookie_status(config["reddit"]["cookies"])
    if not cookies["present"]:
        return PostDownloadError(
            "cookies_missing", f"Reddit refused the request and no Reddit login cookies are configured: {text}"
        )
    return PostDownloadError(
        "reddit_blocked", f"Reddit refused the request; the cookies may be expired, export fresh ones: {text}"
    )


def _gallery_dl_json(url, options):
    command = ["gallery-dl", "-j", *options, url]
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=GALLERY_DL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise PostDownloadError("download_failed", "gallery-dl timed out reading the post") from None
    try:
        return output, json.loads(output.stdout or "[]")
    except ValueError:
        return output, []


def read_post(url, config, options, follow_redirect=True):
    """Post metadata via `gallery-dl -j`: {reddit_id, url, title, author, subreddit}."""
    output, messages = _gallery_dl_json(url, options)

    for message in messages:
        if message and message[0] == -1:
            text = f"{message[1].get('error')}: {message[1].get('message')}"
            if any(marker in text.lower() for marker in BLOCK_MARKERS):
                raise _blocked_error(text, config)
            if message[1].get("error") == "NotFoundError" or "404" in text:
                raise PostDownloadError("not_found", f"Reddit post not found: {text}")
            raise PostDownloadError("download_failed", text)

    if not messages and output.returncode != 0:
        if is_blocked(output):
            raise _blocked_error(short_error(output), config)
        raise PostDownloadError("download_failed", short_error(output))

    post = next((m[1] for m in messages if m[0] == MESSAGE_DIRECTORY and m[1].get("id")), None)
    if post is None:
        # Share links answer with a redirect to the post.
        queued = next((m[1] for m in messages if m[0] == MESSAGE_QUEUE), None)
        if queued and follow_redirect:
            try:
                reddit_id, post_url = parse_post_url(queued)
            except ValueError:
                reddit_id = None
            if reddit_id:
                return read_post(post_url, config, options, follow_redirect=False)
        raise PostDownloadError("not_found", "Reddit returned no post for this link")

    permalink = post.get("permalink") or f"/comments/{post['id']}/"
    return {
        "reddit_id": f"t3_{post['id']}",
        "url": "https://www.reddit.com" + permalink,
        "title": post.get("title"),
        "author": post.get("author"),
        "subreddit": post.get("subreddit"),
    }


def find_performer(stash, author, subreddit):
    """(source name, performer ID) of the Stash performer whose Reddit URL matches the author or subreddit."""
    wanted = []
    if author and author != "[deleted]":
        wanted.append(("user", author.lower()))
    if subreddit:
        name = subreddit.lower()
        wanted.append(("user", name[2:]) if name.startswith("u_") else ("subreddit", name))

    performers = {}
    for performer in stash.get_reddit_performers():
        for source in parse_reddit_urls(performer.get("urls")):
            performers.setdefault(source, str(performer["id"]))

    for source in wanted:
        if source in performers:
            return source[1], performers[source]
    return (wanted[0][1] if wanted else None), None


def _files(db, post):
    return db.query(DownloadedFile).filter_by(reddit_post_id=post.id).order_by(DownloadedFile.id).all()


def result_for(post, files, already_downloaded, performer_id=None):
    scene_ids = sorted({f.scene_id for f in files if f.scene_id is not None})
    image_ids = sorted({f.image_id for f in files if f.image_id is not None})
    gallery_ids = sorted({f.gallery_id for f in files if f.gallery_id is not None})
    return {
        "reddit_id": post.reddit_id,
        "post_url": post.url,
        "title": post.title,
        "source": post.source,
        "already_downloaded": already_downloaded,
        "scene_ids": [str(i) for i in scene_ids],
        "image_ids": [str(i) for i in image_ids],
        "gallery_id": str(gallery_ids[0]) if gallery_ids else None,
        "performer_id": performer_id,
        "files": len(files),
        "not_imported": sum(1 for f in files if not f.stash_imported and not f.ignored),
    }


def _complete(files):
    return bool(files) and all(f.stash_imported or f.ignored for f in files)


def run(config, url, on_step=None):
    """Download, import and link one post. on_step(index, label) is called before each step.

    Returns result_for(...); raises PostDownloadError with a code for expected failures.
    """

    def step(index):
        print(f"--- {index}/{len(STEPS)} {STEPS[index - 1]} ---", flush=True)
        if on_step:
            on_step(index, STEPS[index - 1])

    step(1)
    try:
        reddit_id, gallery_dl_url = parse_post_url(url)
    except ValueError as exc:
        raise PostDownloadError("invalid_url", str(exc)) from None

    root = config["downloads"]["root"]
    stash = StashClient.from_config(config)
    db = SessionLocal()

    try:
        post = db.query(RedditPost).filter_by(reddit_id=reddit_id).first() if reddit_id else None
        files = _files(db, post) if post and post.downloaded else []
        if post and _complete(files):
            print(f"Already downloaded: {post.title} ({len(files)} files)")
            return result_for(post, files, already_downloaded=True)

        already_downloaded = bool(files)
        performer_id = None

        if not already_downloaded:
            cookies = login_cookie_status(config["reddit"]["cookies"])
            if cookies["expired"]:
                raise PostDownloadError(
                    "cookies_expired",
                    f"The Reddit login cookie expired at {cookies['expires_at']}; export fresh cookies (see README)",
                )
            options = gallery_dl_options(config)

            step(2)
            meta = read_post(gallery_dl_url, config, options)
            print(f"Post {meta['reddit_id']}: {meta['title']} by u/{meta['author']} in r/{meta['subreddit']}")

            post = db.query(RedditPost).filter_by(reddit_id=meta["reddit_id"]).first()
            files = _files(db, post) if post and post.downloaded else []
            if post and _complete(files):
                print(f"Already downloaded: {post.title} ({len(files)} files)")
                return result_for(post, files, already_downloaded=True)
            already_downloaded = bool(files)

            source, performer_id = find_performer(stash, meta["author"], meta["subreddit"])
            if performer_id:
                print(f"Performer {performer_id} matches {source}")
            else:
                print(f"No Stash performer has a Reddit URL for u/{meta['author']} or r/{meta['subreddit']}")

            if post is None:
                post = RedditPost(reddit_id=meta["reddit_id"], url=meta["url"], downloaded=False)
                db.add(post)
            post.url = post.url or meta["url"]
            post.title = post.title or meta["title"]
            post.source = post.source or source
            db.commit()

        if not already_downloaded:
            step(3)
            print(f"Downloading: {post.url}")
            try:
                output = run_gallery_dl(gallery_dl_url, root, options)
            except subprocess.TimeoutExpired:
                post.last_error = "gallery-dl timed out"
                db.commit()
                raise PostDownloadError("download_failed", "gallery-dl timed out") from None

            if output.returncode != 0:
                post.last_error = short_error(output)
                db.commit()
                if is_blocked(output):
                    raise _blocked_error(post.last_error, config)
                raise PostDownloadError("download_failed", f"gallery-dl exit {output.returncode}: {post.last_error}")

            paths = extract_downloaded_paths(output.stdout, root)
            if not paths:
                post.last_error = "no media files found"
                db.commit()
                raise PostDownloadError("no_media", "The post has no media gallery-dl can download")

            for path in paths:
                existing = db.query(DownloadedFile).filter_by(path=path).first()
                if existing is None:
                    db.add(DownloadedFile(reddit_post_id=post.id, path=path, stash_imported=False))
                elif existing.reddit_post_id != post.id:
                    print(f"Path already belongs to another post: {path}")

            post.downloaded = True
            post.last_error = None
            db.commit()
            files = _files(db, post)
            print(f"Downloaded {len(paths)} files")

        if performer_id is None:
            performer_id = _performer_for_source(db, post.source)

        step(4)
        pending = [f for f in files if not f.stash_imported and not f.ignored]
        if pending:
            scan_paths = sorted({os.path.dirname(f.path) for f in pending})
            lookup_root = os.path.commonpath(scan_paths)
            imported = import_files(stash, db, pending, scan_paths, lookup_root)
            if imported["generate_ids"]:
                job_id = stash.generate_scene_media(imported["generate_ids"])
                print(f"Started cover/preview generation (job {job_id})")
            if imported["import_missing"]:
                print(f"{imported['import_missing']} files not found in Stash yet; the next sync retries them")

        step(5)
        sync_gallery(stash, db, post, files, performer_id)
        link_performer(stash, db, files, performer_id)

        result = result_for(post, files, already_downloaded, performer_id)
        print(
            f"Done: {len(result['scene_ids'])} scenes, {len(result['image_ids'])} images, "
            f"gallery {result['gallery_id'] or '-'}"
        )
        return result

    except StashError as exc:
        db.rollback()
        raise PostDownloadError("stash_error", str(exc)) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _performer_for_source(db, source):
    if not source:
        return None
    row = (
        db.query(RedditSource)
        .filter(RedditSource.source_name == source.lower(), RedditSource.performer_id.isnot(None))
        .first()
    )
    return str(row.performer_id) if row else None


def sync_gallery(stash, db, post, files, performer_id):
    """One gallery per post with images, as gallery_sync does it."""
    image_ids = sorted({str(f.image_id) for f in files if f.image_id is not None})
    if not image_ids or not post.url:
        return None

    title = post.title or post.reddit_id
    gallery = stash.find_gallery_by_url(post.url)
    if gallery:
        gallery_id = str(gallery["id"])
    else:
        gallery_id = str(stash.create_gallery(title, post.url))
        print(f"Created gallery {gallery_id}: {title}")

    stash.add_gallery_images(gallery_id, image_ids)

    linked = {str(p["id"]) for p in (gallery or {}).get("performers") or []}
    if performer_id and performer_id not in linked:
        stash.add_performer("gallery", gallery_id, performer_id)

    for file in files:
        if file.image_id is not None:
            file.gallery_id = int(gallery_id)
    db.commit()
    return gallery_id


def link_performer(stash, db, files, performer_id):
    if not performer_id:
        return
    for file in files:
        if not file.stash_imported or file.performer_linked:
            continue
        kind = media_kind(file.path)
        object_id = file.scene_id if kind == "video" else file.image_id
        if not object_id:
            continue
        if stash.add_performer("scene" if kind == "video" else "image", object_id, performer_id) != "missing":
            file.performer_linked = True
    db.commit()
