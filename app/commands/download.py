import os
import subprocess

from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost
from app.providers.reddit.rss import gallery_dl_cookie_file
from app.settings import DATA_DIR

GALLERY_DL_TIMEOUT = 15 * 60
GALLERY_DL_CONFIG = "/config/gallery-dl.conf"

GALLERY_DL_COOKIES = os.path.join(DATA_DIR, "gallery-dl-cookies.txt")

# Reddit refuses the request itself (IP block, rate limit, expired cookies). Not the post's fault:
# do not count it as an attempt, and stop the step when it keeps happening.
BLOCK_MARKERS = ("blocked by network security", "too many requests", "403 forbidden", "429")
MAX_CONSECUTIVE_BLOCKS = 3


def is_blocked(output):
    text = f"{output.stderr}\n{output.stdout}".lower()
    return any(marker in text for marker in BLOCK_MARKERS)


def short_error(output):
    """First error line, without the HTML pages Reddit sometimes returns."""
    for line in (output.stderr or output.stdout or "").splitlines():
        line = line.strip()
        if line:
            return line[:300]
    return f"exit {output.returncode}"


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


def gallery_dl_options(config):
    """Extra gallery-dl arguments: optional config file, Reddit cookies, browser emulation.

    Reddit blocks plain gallery-dl requests; logged-in cookies plus Firefox headers get through.
    """
    options = []
    if os.path.exists(GALLERY_DL_CONFIG):
        options += ["--config", GALLERY_DL_CONFIG]

    cookie_file = gallery_dl_cookie_file(config["reddit"]["cookies"], GALLERY_DL_COOKIES)
    if cookie_file:
        options += ["--cookies", cookie_file]

    browser = config["downloads"].get("gallery_dl_browser")
    if browser:
        options += ["-o", f"browser={browser}"]
    return options


def run_gallery_dl(url, download_root, options=()):
    command = ["gallery-dl", "-d", download_root, "--filename", "{id} {filename}.{extension}", *options]

    return subprocess.run(
        command + [url],
        capture_output=True,
        text=True,
        timeout=GALLERY_DL_TIMEOUT,
    )


def run(config):
    download_root = config["downloads"]["root"]
    max_attempts = int(config["downloads"].get("max_attempts") or 5)

    options = gallery_dl_options(config)
    if "--cookies" not in options and "--config" not in options:
        print("No Reddit cookies for gallery-dl; Reddit usually blocks downloads without them (see README).")

    db = SessionLocal()
    downloaded = created_files = failed = empty = blocked = consecutive_blocks = 0

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
                output = run_gallery_dl(post.url, download_root, options)
            except subprocess.TimeoutExpired:
                post.last_error = "gallery-dl timed out"
                failed += 1
                db.commit()
                print(f"DOWNLOAD TIMEOUT: {post.title}")
                continue

            if output.returncode != 0 and is_blocked(output):
                post.download_attempts -= 1
                post.last_error = short_error(output)
                blocked += 1
                consecutive_blocks += 1
                db.commit()
                print(f"BLOCKED BY REDDIT: {post.last_error}")
                if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                    print(
                        f"Reddit blocked {consecutive_blocks} downloads in a row; stopping this step. "
                        "Pending posts stay queued. Export fresh Reddit cookies (see README)."
                    )
                    break
                continue

            consecutive_blocks = 0

            if output.returncode != 0:
                post.last_error = short_error(output)
                failed += 1
                db.commit()
                print(f"DOWNLOAD FAILED (exit {output.returncode}, attempt {post.download_attempts}): {post.title}")
                print(post.last_error)
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

    print(
        f"Downloaded posts: {downloaded}, new files: {created_files}, failed: {failed}, "
        f"without media: {empty}, blocked by Reddit: {blocked}"
    )
    return {
        "posts_downloaded": downloaded,
        "files_new": created_files,
        "downloads_failed": failed + empty,
        "downloads_blocked": blocked,
    }
