import os
import signal
import sys

from app import __version__
from app.database.database import init_db
from app.settings import load_config

USAGE = f"""reddit-stash-agent {__version__}

Usage: python -m app.main COMMAND [ARGS]

  serve                         HTTP API and scheduler (default in Docker)
  sync                          full pipeline (all steps below in order)
  doctor                        check configuration and connections

Single pipeline steps:
  sync_reddit_sources           read Reddit URLs from Stash performers
  rss_scan                      fetch new posts from Reddit RSS
  download                      download new posts with gallery-dl
  import_reddit                 scan the download folder in Stash and link files
  reconcile_reddit_files        recreate DB rows for images Stash already has
  gallery_sync                  create/update one gallery per Reddit post
  link_reddit_performers        add performers to scenes and images

Tools:
  stash_scan                    start a Stash scan of the download folder
  stash_stats                   counts from the agent database
  test_rss user|subreddit NAME  show the first posts of a feed
  test_gallerydl URL            download one URL with gallery-dl
"""


class SyncCancelled(Exception):
    pass


def _raise_cancelled(signum, frame):
    raise SyncCancelled()


def run_sync(config):
    from app.commands import sync
    from app.runtime.sync_state import SyncAlreadyRunning, mark_finished, mark_running, mark_step, sync_lock
    from app.stash.client import StashError

    trigger = os.environ.get("SYNC_TRIGGER", "cli")

    try:
        with sync_lock():
            signal.signal(signal.SIGTERM, _raise_cancelled)
            mark_running(trigger, len(sync.STEPS), os.environ.get("SYNC_LOG_FILE"))
            summary = {}

            try:
                summary = sync.run(config, on_step=mark_step)
            except (SyncCancelled, KeyboardInterrupt):
                mark_finished("cancelled", "Cancelled by user", summary)
                print("Sync cancelled", flush=True)
                return 3
            except StashError as exc:
                # Expected failure (Stash down, wrong key): no traceback needed.
                mark_finished("failed", str(exc))
                print(f"ERROR: {exc}", flush=True)
                return 1
            except Exception as exc:
                mark_finished("failed", f"{type(exc).__name__}: {exc}")
                raise

            mark_finished("success", summary=summary)
            return 0

    except SyncAlreadyRunning:
        print("Sync already running")
        return 2


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    command, args = argv[0], argv[1:]

    if command == "serve":
        import uvicorn

        uvicorn.run(
            "app.api.server:app", host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 8787))
        )
        return 0

    config = load_config()
    added = init_db(config["database"]["path"])
    if added:
        print("Database upgraded: added " + ", ".join(added))

    if command == "sync":
        return run_sync(config)

    if command == "doctor":
        from app.commands import doctor

        return 1 if doctor.run(config) else 0

    if command == "test_rss":
        if len(args) != 2:
            print("Usage: test_rss user|subreddit NAME")
            return 2
        from app.commands import test_rss

        test_rss.run(config, *args)
        return 0

    if command == "test_gallerydl":
        if len(args) != 1:
            print("Usage: test_gallerydl URL")
            return 2
        from app.commands import test_gallerydl

        test_gallerydl.run(config, args[0])
        return 0

    steps = {
        "sync_reddit_sources",
        "rss_scan",
        "download",
        "import_reddit",
        "reconcile_reddit_files",
        "gallery_sync",
        "link_reddit_performers",
        "stash_scan",
        "stash_stats",
    }
    if command in steps:
        import importlib

        importlib.import_module(f"app.commands.{command}").run(config)
        return 0

    print(f"Unknown command: {command}\n")
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
