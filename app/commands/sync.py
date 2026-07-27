import os
import time

from app.commands import rss_scan
from app.commands import download
from app.commands import import_reddit
from app.commands import link_reddit_performers


LOCK_FILE = "/tmp/reddit-stash-agent-sync.lock"


def acquire_lock():

    if os.path.exists(LOCK_FILE):
        raise RuntimeError(
            "Sync already running"
        )

    with open(LOCK_FILE, "w") as f:
        f.write(str(time.time()))


def release_lock():

    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def run(config):

    print()
    print("==============================")
    print(" Reddit Stash Sync Started ")
    print("==============================")
    print()

    acquire_lock()

    start = time.time()

    try:

        print("1/4 RSS scan")
        print("----------------")

        try:
            rss_scan.run(config)
        except Exception as e:
            print(
                "RSS scan warning:",
                e
            )


        print()
        print("2/4 Download")
        print("----------------")

        try:
            download.run(config)
        except Exception as e:
            print(
                "Download warning:",
                e
            )


        print()
        print("3/4 Import into Stash")
        print("----------------")

        try:
            import_reddit.run(config)
        except Exception as e:
            print(
                "Import warning:",
                e
            )


        print()
        print("4/4 Link performers")
        print("----------------")

        try:
            link_reddit_performers.run(config)
        except Exception as e:
            print(
                "Performer link warning:",
                e
            )


    finally:

        release_lock()


    elapsed = round(
        time.time() - start,
        2
    )

    print()
    print("==============================")
    print(
        "Sync finished in",
        elapsed,
        "seconds"
    )
    print("==============================")
