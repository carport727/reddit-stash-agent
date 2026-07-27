## Alpha Status

This project is currently in alpha.

The current release is intended for testing and personal deployments.

Breaking changes may happen:
- Database schema
- Commands
- Configuration format
- Stash integration behaviour

## Commands

All commands use:

docker compose run --rm reddit-stash-agent COMMAND

Basic diagnostics
Doctor
Checks configuration and Stash connection:
docker compose run --rm reddit-stash-agent doctor

Database test
docker compose run --rm reddit-stash-agent test_db

RSS test
Test Reddit RSS access:
docker compose run --rm reddit-stash-agent test_rss

Gallery downloader test
docker compose run --rm reddit-stash-agent test_gallerydl

Database
Run migrations
docker compose run --rm reddit-stash-agent migrate_db

Reddit source management
Add Reddit source
docker compose run --rm reddit-stash-agent add_source

Sync Reddit sources
docker compose run --rm reddit-stash-agent sync_reddit_sources

Scanning
Scan Reddit RSS
docker compose run --rm reddit-stash-agent rss_scan

Full Reddit scan
docker compose run --rm reddit-stash-agent scan

Downloads
Download Reddit files
docker compose run --rm reddit-stash-agent download

Stash integration
Scan Stash folder
Runs Stash metadata scan:
docker compose run --rm reddit-stash-agent stash_scan

Show Stash statistics
docker compose run --rm reddit-stash-agent stash_stats

Import Reddit files into Stash
Links downloaded files with Stash:
docker compose run --rm reddit-stash-agent import_reddit

Link Reddit performers
Assign performers:
docker compose run --rm reddit-stash-agent link_reddit_performers

Full pipeline (recommended)
This is the command for Pipeline:
docker compose run --rm reddit-stash-agent sync

Pipeline:

1. RSS scan
2. Download new Reddit files
3. Import into Stash
4. Link performers
Development shell

Open container shell:

docker compose run --rm --entrypoint bash reddit-stash-agent

Then inside:

python

or:

python -m py_compile app/main.py
Useful debugging commands

View database:

docker compose run --rm --entrypoint bash reddit-stash-agent

Then:

python

Example:

from app.database.database import SessionLocal
db = SessionLocal()
print(db.query(...).count())
