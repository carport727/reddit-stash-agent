import time

from app.commands import (
    download,
    gallery_sync,
    import_reddit,
    link_reddit_performers,
    reconcile_reddit_files,
    rss_scan,
    sync_reddit_sources,
)

STEPS = [
    ("Sync Reddit performer sources", sync_reddit_sources.run),
    ("RSS scan", rss_scan.run),
    ("Download", download.run),
    ("Import into Stash", import_reddit.run),
    ("Reconcile Reddit image files", reconcile_reddit_files.run),
    ("Sync galleries", gallery_sync.run),
    ("Link performers", link_reddit_performers.run),
]


def run(config, on_step=None):
    """Run the whole pipeline. on_step(index, label, summary) is called before each step."""
    print("=== Reddit Stash sync started ===", flush=True)
    start = time.time()
    summary = {}

    for index, (label, command) in enumerate(STEPS, start=1):
        if on_step:
            on_step(index, label, summary)

        print(f"\n--- {index}/{len(STEPS)} {label} ---", flush=True)
        summary.update(command(config) or {})

    summary["duration_seconds"] = round(time.time() - start, 1)
    print(f"\n=== Sync finished in {summary['duration_seconds']} s ===", flush=True)
    print("Summary: " + ", ".join(f"{key}={value}" for key, value in summary.items()), flush=True)
    return summary
