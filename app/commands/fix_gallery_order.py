"""Number the files of older Reddit gallery downloads in their Reddit order.

Up to 0.10.0 files were saved as "{id} {filename}.{extension}". In a gallery post the filename is
Reddit's random media ID, so Stash, which sorts gallery images by file name, showed them in random
order. New downloads are saved as "{id} {num} {filename}.{extension}" (see download.FILENAME_FORMAT).

This reads each older gallery post once with `gallery-dl -j` (same cookies as downloads, one request
per post), renames its files to the new scheme, updates the agent database and rescans the folders in
Stash. Stash recognises renamed files by their fingerprint, so images, galleries, tags and performers
stay as they are.
"""

import os
import re
import time

from app.commands.download import BLOCK_MARKERS, MAX_CONSECUTIVE_BLOCKS, gallery_dl_options, is_blocked
from app.commands.download_post import _gallery_dl_json
from app.database.database import SessionLocal
from app.database.models import DownloadedFile, RedditPost
from app.stash.client import StashClient

MESSAGE_URL = 3
OLD_NAME = re.compile(r"^(?P<id>[a-z0-9]+) (?P<rest>.+)$", re.IGNORECASE)
NUMBERED_NAME = re.compile(r"^[a-z0-9]+ \d{2,} ", re.IGNORECASE)
# Rescan in Stash every this many posts, so renamed files do not show as missing for long.
SCAN_EVERY = 100


def gallery_positions(messages):
    """{media filename (without extension): position} for the items of a gallery post."""
    positions = {}
    for message in messages:
        if len(message) > 2 and message[0] == MESSAGE_URL and isinstance(message[2], dict):
            filename, num = message[2].get("filename"), message[2].get("num")
            if filename and num:
                positions[str(filename)] = int(num)
    return positions


def numbered_path(path, positions):
    """New path "{id} {num:02} {rest}" for an old-style file, or None when it is not part of the gallery."""
    name = os.path.basename(path)
    if NUMBERED_NAME.match(name):
        return None
    match = OLD_NAME.match(name)
    if not match:
        return None
    num = positions.get(os.path.splitext(match.group("rest"))[0])
    if not num:
        return None
    return os.path.join(os.path.dirname(path), f"{match.group('id')} {num:02d} {match.group('rest')}")


def _blocked(output, messages):
    for message in messages:
        if message and message[0] == -1:
            text = f"{message[1].get('error')}: {message[1].get('message')}".lower()
            return any(marker in text for marker in BLOCK_MARKERS)
    return not messages and output.returncode != 0 and is_blocked(output)


def run(config, dry_run=False, limit=None):
    options = gallery_dl_options(config)
    delay = float(config["reddit"].get("request_delay_seconds") or 0)
    stash = None if dry_run else StashClient.from_config(config)
    db = SessionLocal()

    checked = renamed = unmatched = failed = blocked = consecutive_blocks = 0
    folders = set()

    def rescan():
        if folders and not dry_run:
            print(f"Rescanning {len(folders)} folders in Stash so it picks up the new file names")
            print(f"Stash scan: {stash.wait_for_job(stash.scan_path(sorted(folders)))}")
        folders.clear()

    try:
        files_by_post = {}
        for row in db.query(DownloadedFile).filter(DownloadedFile.ignored.isnot(True)).all():
            files_by_post.setdefault(row.reddit_post_id, []).append(row)

        # Gallery posts with files still in the old naming scheme.
        todo = [
            post_id
            for post_id, rows in files_by_post.items()
            if len(rows) > 1 and any(not NUMBERED_NAME.match(os.path.basename(r.path)) for r in rows)
        ]
        if limit:
            todo = todo[: int(limit)]
        print(f"Gallery posts to check: {len(todo)}" + (" (dry run, nothing is renamed)" if dry_run else ""))

        for index, post_id in enumerate(todo, start=1):
            post = db.get(RedditPost, post_id)
            if post is None or not post.url:
                continue
            if index > 1 and delay:
                time.sleep(delay)

            output, messages = _gallery_dl_json(post.url, options)
            if _blocked(output, messages):
                blocked += 1
                consecutive_blocks += 1
                print(f"BLOCKED BY REDDIT: {post.url}")
                if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                    print("Reddit blocked 3 requests in a row; stopping. Run again later or with fresh cookies.")
                    break
                continue
            consecutive_blocks = 0

            positions = gallery_positions(messages)
            if not positions:
                failed += 1
                print(f"No gallery order from Reddit (deleted or not a gallery): {post.url}")
                continue

            checked += 1
            for row in files_by_post[post_id]:
                new_path = numbered_path(row.path, positions)
                if new_path is None:
                    if not NUMBERED_NAME.match(os.path.basename(row.path)):
                        unmatched += 1
                    continue
                if os.path.exists(new_path) or not os.path.exists(row.path):
                    unmatched += 1
                    continue
                if not dry_run:
                    os.rename(row.path, new_path)
                    row.path = new_path
                folders.add(os.path.dirname(new_path))
                renamed += 1
            db.commit()
            print(f"[{index}/{len(todo)}] {post.reddit_id}: {len(positions)} items in order")
            if index % SCAN_EVERY == 0:
                rescan()

        rescan()

        print(
            f"Done: {checked} galleries checked, {renamed} files {'to rename' if dry_run else 'renamed'}, "
            f"{unmatched} files left as they are, {failed} posts without order, {blocked} blocked"
        )
        return {"checked": checked, "renamed": renamed, "unmatched": unmatched, "failed": failed, "blocked": blocked}
    finally:
        db.close()
