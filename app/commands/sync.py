import time

from app.commands import sync_reddit_sources
from app.commands import rss_scan
from app.commands import download
from app.commands import import_reddit
from app.commands import gallery_sync
from app.commands import reconcile_reddit_files
from app.commands import link_reddit_performers


STEPS = [
    (
        "Sync Reddit performer sources",
        sync_reddit_sources.run,
    ),
    (
        "RSS scan",
        rss_scan.run,
    ),
    (
        "Download",
        download.run,
    ),
    (
        "Import into Stash",
        import_reddit.run,
    ),
    (
        "Reconcile Reddit image files",
        reconcile_reddit_files.run,
    ),
    (
        "Sync galleries",
        gallery_sync.run,
    ),
    (
        "Link performers",
        link_reddit_performers.run,
    ),
]


def run(config):

    print()
    print("==============================")
    print(" Reddit Stash Sync Started ")
    print("==============================")
    print()

    start = time.time()

    for index, (label, command) in enumerate(
        STEPS,
        start=1,
    ):
        print()
        print(f"{index}/{len(STEPS)} {label}")
        print("-" * 32)

        command(config)

    elapsed = round(
        time.time() - start,
        2,
    )

    print()
    print("==============================")
    print(
        "Sync finished in",
        elapsed,
        "seconds",
    )
    print("==============================")
