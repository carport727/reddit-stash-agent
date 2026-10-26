# Reddit Stash Agent

Downloads new Reddit posts of your [Stash](https://stashapp.cc) performers and files them in Stash:
scenes and images linked to the performer, and one gallery per Reddit post.

It has two parts:

- **Agent** – a Docker container that does the work and runs the schedule. It has a small HTTP API on port 8787.
- **Stash plugin** – a "Reddit Agent" page and tasks in Stash, which start syncs and show progress through the agent API.

```
Stash UI / Stashfeed ──GraphQL──▶ Stash ──plugin──▶ Agent API :8787 ──▶ sync pipeline
                                    ▲                                       │
                                    └──────────── GraphQL (API key) ────────┘
```

> **Alpha.** The database schema, commands and config can still change between minor versions.

## How a sync works

A Reddit source is a Reddit URL on a Stash performer, e.g. `https://www.reddit.com/user/NAME` or
`https://www.reddit.com/r/NAME`. Each sync runs these steps:

1. **Sources** – read the Reddit URLs of all performers. Removing a URL in Stash stops that source.
2. **RSS scan** – fetch the newest posts of each source.
3. **Download** – download new posts with gallery-dl. A failing post is retried, up to `max_attempts` times.
4. **Import** – start a Stash scan of the download folder, wait for it, and remember the new scene and image IDs.
   Covers and previews are generated for new scenes.
5. **Reconcile** – recover files Stash found that gallery-dl did not report.
6. **Galleries** – one gallery per post with images, titled after the post, with the post URL.
7. **Performers** – add the performer to every new scene, image and gallery. Existing performers are kept.

Every step is idempotent: running a sync again only does what is still missing.

## Install the agent

You need Docker with Compose v2, and a folder inside a Stash library for the downloads.

```bash
mkdir -p reddit-stash-agent/config && cd reddit-stash-agent
curl -fLO https://raw.githubusercontent.com/carport727/reddit-stash-agent/main/docker-compose.yml
```

Open `docker-compose.yml` and fill in the values marked **Required**:

| Setting | |
|---|---|
| `STASH_URL` | how the container reaches Stash, e.g. `http://192.168.1.10:9999` |
| `STASH_API_KEY` | Stash → Settings → Security → API Key |
| `AGENT_TOKEN` | any long random string (`openssl rand -hex 32`); the same value goes into the plugin settings |
| `STASH_LIBRARY_HOST` / `STASH_LIBRARY_PATH` | your library folder on this host, and the path under which Stash sees it |
| `DOWNLOADS_ROOT` | download folder below `STASH_LIBRARY_PATH`, e.g. `/Stash/Download/Reddit` |

Write each value after the `:-`, e.g. `STASH_URL: ${STASH_URL:-http://192.168.1.10:9999}`. Alternatively put them
into a `.env` file next to the compose file (template: [`.env.example`](.env.example)), which keeps secrets out of it.

Put your Reddit cookies into `config/reddit-cookies.json` (see [Reddit login](#reddit-login)); without them Reddit
blocks the downloads. Then:

```bash
docker compose up -d
docker compose run --rm reddit-stash-agent doctor
```

`doctor` checks the Stash connection and API key, the download folder, gallery-dl, the Reddit cookies and the token.

Further settings (RSS delay, retry limit, dry run) can go into `config/config.yaml`; see
[`config/config.example.yaml`](config/config.example.yaml). Environment variables take precedence over that file.

### Reddit login

Reddit blocks anonymous downloads ("You've been blocked by network security" or "Too Many Requests"). The agent
therefore uses the cookies of a logged-in Reddit session for RSS and gallery-dl, and lets gallery-dl imitate Firefox
(`downloads.gallery_dl_browser`).

1. Log in to reddit.com in your browser and export the cookies with an extension such as Cookie-Editor:
   either as **JSON** to `config/reddit-cookies.json`, or as **Netscape** to `config/reddit-cookies.txt`
   (then set `reddit.cookies: /config/reddit-cookies.txt`).
2. Check it: `docker compose run --rm reddit-stash-agent test_gallerydl https://www.reddit.com/r/pics/`

The `reddit_session` cookie stays valid for months. The plugin page shows its expiry date (yellow two weeks before,
red when expired). When downloads get blocked again, export fresh cookies.
While Reddit blocks, the agent keeps the posts queued, stops the download step early and does not count these
as failed attempts.

Optional: a `config/gallery-dl.conf` is passed to gallery-dl as well, e.g. for an OAuth `refresh-token`
(`gallery-dl oauth:reddit`) if you have a Reddit API app.

Images are published at `ghcr.io/carport727/reddit-stash-agent` (`latest`, `X.Y`, `X.Y.Z`; amd64 and arm64).
To build locally instead, replace `image:` with `build: .` in `docker-compose.yml`.

### Update

```bash
docker compose pull && docker compose up -d
```

The database is migrated automatically on start.

## Install the Stash plugin

**From the plugin source (recommended):** Stash → Settings → Plugins → Available Plugins → **Add Source**

- Name: `Reddit Stash Agent`
- Source URL: `https://carport727.github.io/reddit-stash-agent/stable/index.yml`

Then install "Reddit Stash Agent" from that source. Updates appear under Installed Plugins.

**Manually:** copy `plugins/reddit-stash-agent/` into Stash's `plugins` folder and reload plugins.

The plugin needs `python3` on the Stash host; the official Stash Docker image has it. It uses only the standard library.

### Plugin settings

| Setting | Key | Meaning |
|---|---|---|
| Agent URL | `agent_url` | e.g. `http://192.168.1.10:8787` (as seen from the Stash server) |
| Agent API token | `agent_token` | the `AGENT_TOKEN` of the agent |
| Automatic sync enabled | `enabled` | turn the agent's schedule on or off |
| Sync interval in hours | `interval_hours` | default 6 |

After changing `enabled` or `interval_hours`, run the task **Apply Scheduler Settings**, or click
"Apply scheduler settings" on the plugin page. The schedule lives in the agent, so it also runs while Stash is closed.

The **Reddit Agent** button in the navigation bar opens a page with the status, live progress, the last summary and log,
and buttons to start, cancel and refresh.

## Plugin interface (for Stash clients such as Stashfeed)

Plugin ID: `reddit-stash-agent`

### Tasks – `runPluginTask(plugin_id: "reddit-stash-agent", task_name: "…")`

These run in the Stash job queue. Only `Download Reddit Post` takes an argument (`args_map: {url: "…"}`).

| Task name | What it does |
|---|---|
| `Start Reddit Sync` | starts a sync (or attaches to a running one) and **waits until it ends**. Job progress follows the pipeline; each step is logged to the Stash log. Fails when the sync fails. |
| `Download Reddit Post` | downloads one post (argument `url`, see [Single post download](#single-post-download)) and waits for it, with progress in the Stash log |
| `Cancel Reddit Sync` | cancels the running sync |
| `Apply Scheduler Settings` | sends `enabled` / `interval_hours` to the agent |
| `Get Agent Status` | writes the status to the Stash log |
| `Show Last Sync Log` | writes the last 200 lines of the sync log to the Stash log |
| `Test Agent Connection` | checks that Stash reaches the agent |

Stash itself marks a plugin job as *finished* even when the plugin fails, and only logs the error. To get the result,
read the Stash log (the plugin logs `Sync finished: …` or the error) or use the `status` operation below.
Cancelling the Stash job stops waiting but not the sync; use `Cancel Reddit Sync` for that.
The created IDs of `Download Reddit Post` are in `status.last_download.result` and in the `download_status` operation.

### Operations – `runPluginOperation(plugin_id: "reddit-stash-agent", args: {mode: "…"})`

These run immediately, outside the job queue, and return JSON. Errors come back as GraphQL errors.
They are safe to poll; `status` is read-only.

| `mode` | Returns |
|---|---|
| `health` | `{status, service, version, auth_required}` |
| `status` | see below |
| `start` | starts a sync without waiting: `{accepted, pid, message}`. Error "HTTP 409" if one is already running. |
| `cancel` | `{accepted, message}`. Error "HTTP 409" if nothing is running. |
| `config` | pushes the plugin settings: `{enabled, interval_hours, next_run_at}` |
| `logs` | `{log_file, lines: [...]}` (last 200 lines of the current or last run) |
| `sync` | like the task: starts and blocks until the sync ends. Prefer `start` + polling `status` in clients. |
| `download_post` | args `{url, wait}`: downloads one post. Blocks until done and returns the finished job (see below); with `wait: false` it returns the queued job at once. Fails with `Download failed (<error_code>): …` |
| `download_status` | args `{id}`: one download job; without `id` the last 20 (`{downloads: [...]}`) |

`status`:

```json
{
  "running": true,
  "last_result": "running",           // null | running | success | failed | cancelled | interrupted
  "last_trigger": "api",              // cli | api | scheduler
  "last_started_at": "2026-10-24T20:00:00+00:00",
  "last_finished_at": null,
  "last_error": null,
  "step": 3, "step_count": 7, "step_label": "Download",
  "progress": 0.286,                  // 0..1
  "summary": {"sources": 12, "posts_new": 4},
  "log_file": "/logs/runs/20261024T200000Z-api.log",
  "scheduler": {"enabled": true, "interval_hours": 6.0, "next_run_at": "2026-10-25T02:00:00+00:00"},
  "reddit_cookies": {"file": "/config/reddit-cookies.json", "present": true,
                     "expires_at": "2027-01-21T10:00:00+00:00", "expired": false, "days_left": 88},
  "last_download": {"id": "3f2a9c1b7d4e", "status": "success", "...": "job as below, without log"},
  "version": "0.8.0"
}
```

### Single post download

Downloads one Reddit post (single image, video or gallery) with the agent's Reddit cookies and the same pipeline as the
sync: gallery-dl, Stash scan of the new files, one Stash gallery per post with images, and the performer whose Reddit
URL (`reddit.com/user/NAME` or `reddit.com/r/NAME`) matches the post's author or subreddit. The post is recorded in the
agent database, so the regular sync never downloads it again. Asking for a post that is already in the database
downloads nothing and returns the existing IDs (`already_downloaded: true`).

Accepted links: `reddit.com/r/SUB/comments/ID/…`, `reddit.com/user/NAME/comments/ID/…`, `reddit.com/comments/ID`,
`reddit.com/gallery/ID`, `redd.it/ID` (any subdomain such as `old.` or `m.`) and app share links
`reddit.com/r/SUB/s/CODE`. Direct media links (`i.redd.it`, `v.redd.it`) are rejected; send the post link.

Downloads run one at a time, independent of the sync. A second request for a link that is still queued or running
returns the same job. The last 50 jobs are kept in `data/post-downloads.json`.

Job:

```json
{
  "id": "3f2a9c1b7d4e",
  "url": "https://www.reddit.com/r/pics/comments/abc123/title/",
  "status": "success",                // queued | running | success | failed | interrupted
  "created_at": "…", "started_at": "…", "finished_at": "…",
  "step": 5, "step_count": 5, "step_label": null, "progress": 1.0,
  "error": null,
  "error_code": null,                 // see below
  "result": {
    "reddit_id": "t3_abc123",
    "post_url": "https://www.reddit.com/r/pics/comments/abc123/title/",
    "title": "…",
    "source": "someone",
    "already_downloaded": false,
    "scene_ids": [],
    "image_ids": ["101", "102"],
    "gallery_id": "55",               // null when the post has no images
    "performer_id": "7",              // null when no performer has a matching Reddit URL
    "files": 2,
    "not_imported": 0                 // files Stash had not indexed yet; the next sync retries them
  },
  "log": ["--- 1/5 Check link ---", "…"]
}
```

`error_code`:

| Code | Meaning |
|---|---|
| `invalid_url` | not a Reddit post link (the API answers HTTP 400 before queueing) |
| `cookies_expired` | the `reddit_session` cookie is past its expiry date; export fresh cookies |
| `cookies_missing` | Reddit refused the request and no login cookies are configured |
| `reddit_blocked` | Reddit refused the request (HTTP 403/429, network block) although cookies are set; often expired cookies |
| `not_found` | the post does not exist, was deleted, or a share link does not lead to a post |
| `no_media` | the post has nothing gallery-dl can download (e.g. text post) |
| `download_failed` | gallery-dl failed or timed out |
| `stash_error` | Stash was not reachable or rejected a request |
| `internal` | unexpected error, see the agent log |

## Agent HTTP API

Everything except `/api/health` needs `Authorization: Bearer <AGENT_TOKEN>` when a token is set.

| Method | Path | |
|---|---|---|
| GET | `/api/health` | liveness, version |
| GET | `/api/status` | status as above |
| GET / PUT | `/api/config` | schedule, body `{enabled, interval_hours}` |
| POST | `/api/sync` | start a sync (202; 409 if one is running) |
| POST | `/api/sync/cancel` | cancel it (202; 409 if none) |
| GET | `/api/logs?lines=200` | tail of the current or last run log |
| POST | `/api/download` | download one post, body `{"url": "…", "wait": false}`. 202 with the queued job; with `wait: true` it blocks until the job ends (200, max. 30 min). 400 for a link that is not a Reddit post. |
| GET | `/api/download/{id}` | one download job (404 if unknown) |
| GET | `/api/downloads?limit=20` | the last download jobs, newest first |

```bash
curl -H "Authorization: Bearer $AGENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://www.reddit.com/r/pics/comments/abc123/", "wait": true}' http://localhost:8787/api/download
```

Each run writes its own log to `logs/runs/` (the last 30 are kept).

## Command line

```bash
docker compose run --rm reddit-stash-agent COMMAND
```

| Command | |
|---|---|
| `sync` | the whole pipeline (locks against parallel runs, updates the status) |
| `doctor` | check configuration and connections |
| `sync_reddit_sources`, `rss_scan`, `download`, `import_reddit`, `reconcile_reddit_files`, `gallery_sync`, `link_reddit_performers` | single steps |
| `stash_scan` | start a Stash scan of the download folder |
| `stash_stats` | counts from the agent database |
| `test_rss user NAME` / `test_rss subreddit NAME` | show the first posts of a feed |
| `download_post URL` | download one post and import it into Stash (same as `/api/download`, prints the result) |
| `test_gallerydl URL` | download one URL |

Set `dry_run: true` to print the gallery and performer changes instead of writing them.

## Security

- Keep `AGENT_TOKEN` set. Without it, anyone who reaches port 8787 can start syncs and change the schedule.
  If Stash runs on the same host, publish the port only on the needed interface.
- The Stash API key and Reddit cookies stay in `.env` / `config/` and are git-ignored. Never commit them.
- The plugin authenticates to Stash with the session Stash gives it; it stores no Stash credentials.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
```

CI runs the same checks. Pushes to `main` publish the Docker image and the plugin source (GitHub Pages).

## License

[MIT](LICENSE)
