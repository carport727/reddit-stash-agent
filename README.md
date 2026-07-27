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

### Basic diagnostics
- Doctor  
  Checks configuration and Stash connection:  
  docker compose run --rm reddit-stash-agent doctor

### Database test
- test_db  
  docker compose run --rm reddit-stash-agent test_db

### RSS test
- test_rss  
  Test Reddit RSS access:  
  docker compose run --rm reddit-stash-agent test_rss

### Gallery downloader test
- test_gallerydl  
  docker compose run --rm reddit-stash-agent test_gallerydl

### Database
- migrate_db  
  Run migrations: docker compose run --rm reddit-stash-agent migrate_db

### Reddit source management
- add_source  
  Add Reddit source: docker compose run --rm reddit-stash-agent add_source

### Sync Reddit sources
- sync_reddit_sources  
  docker compose run --rm reddit-stash-agent sync_reddit_sources

### Scanning
- rss_scan  
  Scan Reddit RSS: docker compose run --rm reddit-stash-agent rss_scan

- scan  
  Full Reddit scan: docker compose run --rm reddit-stash-agent scan

### Downloads
- download  
  Download Reddit files: docker compose run --rm reddit-stash-agent download

### Stash integration
- stash_scan  
  Scan Stash folder and runs Stash metadata scan: docker compose run --rm reddit-stash-agent stash_scan

- stash_stats  
  Show Stash statistics: docker compose run --rm reddit-stash-agent stash_stats

### Import Reddit files into Stash
- import_reddit  
  Links downloaded files with Stash: docker compose run --rm reddit-stash-agent import_reddit

### Link Reddit performers
- link_reddit_performers  
  Assign performers: docker compose run --rm reddit-stash-agent link_reddit_performers

### Full pipeline (recommended)
- sync  
  This is the command for Pipeline: docker compose run --rm reddit-stash-agent sync

#### Pipeline steps
1. RSS scan
2. Download new Reddit files
3. Import into Stash
4. Link performers

### Development shell

Open container shell:

docker compose run --rm --entrypoint bash reddit-stash-agent

Then inside:

python

or:

python -m py_compile app/main.py

### Useful debugging commands

View database:

docker compose run --rm --entrypoint bash reddit-stash-agent

Then:

python

Example:

from app.database.database import SessionLocal
db = SessionLocal()
print(db.query(...).count())
