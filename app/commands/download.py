import os
import subprocess

from app.database.database import SessionLocal
from app.database.models import (
    RedditPost,
    DownloadedFile,
)


def extract_downloaded_paths(stdout, download_root):

    download_root = os.path.abspath(
        download_root
    )

    paths = []

    for raw_line in stdout.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        # Some gallery-dl configurations prefix
        # downloaded paths with "# ".
        if line.startswith("# "):
            line = line[2:].strip()

        if not line:
            continue

        path = os.path.abspath(line)

        try:
            inside_download_root = (
                os.path.commonpath(
                    [download_root, path]
                )
                == download_root
            )
        except ValueError:
            inside_download_root = False

        if not inside_download_root:
            continue

        if not os.path.isfile(path):
            continue

        paths.append(path)

    return list(dict.fromkeys(paths))


def run(config):

    db = SessionLocal()

    try:

        posts = (
            db.query(RedditPost)
            .filter_by(downloaded=False)
            .all()
        )

        print()
        print("Downloading Reddit media...")
        print("Pending:", len(posts))
        print()

        downloaded_posts = 0
        created_files = 0
        failed_posts = 0
        empty_posts = 0

        download_root = config[
            "downloads"
        ]["root"]

        for post in posts:

            print(
                "Downloading:",
                post.url
            )

            output = subprocess.run(
                [
                    "gallery-dl",
                    "-d",
                    download_root,
                    post.url,
                ],
                capture_output=True,
                text=True,
            )

            print("GALLERY STDOUT:")
            print(output.stdout)

            print("GALLERY STDERR:")
            print(output.stderr)

            paths = extract_downloaded_paths(
                output.stdout,
                download_root,
            )

            if output.returncode != 0:

                print(
                    "DOWNLOAD FAILED:",
                    post.title,
                    "return code:",
                    output.returncode,
                )

                failed_posts += 1
                continue

            if not paths:

                print(
                    "NO MEDIA FILES FOUND:",
                    post.title
                )

                empty_posts += 1
                continue

            post_file_count = 0

            for path in paths:

                existing = (
                    db.query(DownloadedFile)
                    .filter_by(path=path)
                    .first()
                )

                if existing:

                    # Repair an incorrect association,
                    # if one ever exists.
                    if (
                        existing.reddit_post_id
                        != post.id
                    ):
                        print(
                            "Path already belongs to "
                            "another post:",
                            path,
                        )

                    continue

                db.add(
                    DownloadedFile(
                        reddit_post_id=post.id,
                        path=path,
                        stash_imported=False,
                        performer_linked=False,
                    )
                )

                created_files += 1
                post_file_count += 1

            # Mark the post downloaded when at least
            # one valid file exists, including files
            # that were already present in the DB.
            post.downloaded = True
            downloaded_posts += 1

            db.commit()

            print(
                "DONE:",
                post.title,
                "- files discovered:",
                len(paths),
                "- new DB rows:",
                post_file_count,
            )

        print()
        print(
            "Downloaded posts:",
            downloaded_posts
        )
        print(
            "Created file rows:",
            created_files
        )
        print(
            "Failed posts:",
            failed_posts
        )
        print(
            "Posts without media:",
            empty_posts
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()
