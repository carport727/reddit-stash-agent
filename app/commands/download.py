import os
import subprocess

from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost

GALLERY_DL_TIMEOUT = 15 * 60


def extract_downloaded_paths(stdout, download_root):
    """Paths gallery-dl reports on stdout ("# " prefix marks already existing files)."""
    download_root = os.path.abspath(download_root)
    paths = []

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            line = line[2:].strip()
        if not line:
            continue

        path = os.path.abspath(line)
        try:
            inside = os.path.commonpath([download_root, path]) == download_root
        except ValueError:
            inside = False

        if inside and os.path.isfile(path):
            paths.append(path)

    return list(dict.fromkeys(paths))


def run_gallery_dl(url, download_root):
    return subprocess.run(
        ["gallery-dl", "-d", download_root, "--filename", "{id} {filename}.{extension}", url],
        capture_output=True,
        text=True,
        timeout=GALLERY_DL_TIMEOUT,
    )


def run(config):
    download_root = config["downloads"]["root"]
    max_attempts = int(config["downloads"].get("max_attempts") or 5)

    db = SessionLocal()
    downloaded = created_files = failed = empty = 0

    try:
        posts = (
            db.query(RedditPost)
            .filter(RedditPost.downloaded.is_(False))
            .filter((RedditPost.download_attempts.is_(None)) | (RedditPost.download_attempts < max_attempts))
            .all()
        )
        given_up = (
            db.query(RedditPost)
            .filter(RedditPost.downloaded.is_(False), RedditPost.download_attempts >= max_attempts)
            .count()
        )

        print(f"Downloading Reddit media: {len(posts)} pending, {given_up} given up after {max_attempts} attempts")

        for post in posts:
            print(f"Downloading: {post.url}")
            post.download_attempts = (post.download_attempts or 0) + 1

            try:
                output = run_gallery_dl(post.url, download_root)
            except subprocess.TimeoutExpired:
                post.last_error = "gallery-dl timed out"
                failed += 1
                db.commit()
                print(f"DOWNLOAD TIMEOUT: {post.title}")
                continue

            if output.returncode != 0:
                post.last_error = (output.stderr or output.stdout or "").strip()[-500:] or f"exit {output.returncode}"
                failed += 1
                db.commit()
                print(f"DOWNLOAD FAILED (exit {output.returncode}, attempt {post.download_attempts}): {post.title}")
                print(output.stderr.strip())
                continue

            paths = extract_downloaded_paths(output.stdout, download_root)
            if not paths:
                post.last_error = "no media files found"
                empty += 1
                db.commit()
                print(f"NO MEDIA FILES (attempt {post.download_attempts}): {post.title}")
                continue

            new_rows = 0
            for path in paths:
                existing = db.query(DownloadedFile).filter_by(path=path).first()
                if existing:
                    if existing.reddit_post_id != post.id:
                        print(f"Path already belongs to another post: {path}")
                    continue

                db.add(DownloadedFile(reddit_post_id=post.id, path=path, stash_imported=False, performer_linked=False))
                new_rows += 1

            post.downloaded = True
            post.last_error = None
            downloaded += 1
            created_files += new_rows
            db.commit()
            print(f"DONE: {post.title} ({len(paths)} files, {new_rows} new)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Downloaded posts: {downloaded}, new files: {created_files}, failed: {failed}, without media: {empty}")
    return {"posts_downloaded": downloaded, "files_new": created_files, "downloads_failed": failed + empty}
