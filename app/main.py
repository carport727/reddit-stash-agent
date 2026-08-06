import os
import sys
import yaml

from app.commands import doctor
from app.commands import scan
from app.commands import test_rss
from app.commands import rss_scan
from app.commands import test_gallerydl
from app.commands import test_db
from app.commands import sync_reddit_sources
from app.commands import download
from app.commands import stash_scan
from app.commands import stash_stats
from app.commands import migrate_db
from app.commands import import_reddit
from app.commands import reconcile_reddit_files
from app.commands import link_reddit_performers
from app.commands import sync
from app.commands import gallery_sync
from app.database.database import init_db

init_db()

CONFIG = os.environ.get(
    "CONFIG_FILE",
    "/config/config.yaml"
)


with open(CONFIG) as f:
    config = yaml.safe_load(f)


print("✓ Configuration loaded")


if len(sys.argv) > 1:

    command = sys.argv[1]

    if command == "doctor":
        doctor.run(config)
        sys.exit(0)

    if command == "scan":
        scan.run(config)
        sys.exit(0)

    if command == "test_rss":
        test_rss.run(config)
        sys.exit(0)

    if command == "rss_scan":
        rss_scan.run(config)
        sys.exit(0)

    if command == "test_gallerydl":
        test_gallerydl.run(config)
        sys.exit(0)

    if command == "test_db":
        test_db.run()
        sys.exit(0)

    if command == "sync_reddit_sources":
        sync_reddit_sources.run(config)
        sys.exit(0)

    if command == "download":
        download.run(config)
        sys.exit(0)

    elif command == "stash_scan":

        stash_scan.run(config)

    elif command == "stash_stats":
        stash_stats.run(config)

    elif command == "match_scenes":
        from app.commands import match_scenes
        match_scenes.run(config)

    elif command == "migrate_db":
        migrate_db.run(config)

    if command == "import_reddit":
        import_reddit.run(config)
        sys.exit(0)

    if command == "reconcile_reddit_files":
        reconcile_reddit_files.run(config)
        sys.exit(0)

    if command == "link_reddit_performers":
        link_reddit_performers.run(config)
        sys.exit(0)

    if command == "sync":
        sync.run(config)
        sys.exit(0)

    elif command == "gallery_sync":
        gallery_sync.run(config)
        sys.exit(0)

print("reddit-stash-agent is running...")
