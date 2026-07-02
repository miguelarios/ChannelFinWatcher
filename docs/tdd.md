## Technical Design Document (TDD)

### 1. Title & Metadata
- ChannelFinWatcher — YouTube Recent Video Downloader
- Original design: 2025-07-27
- Reflects the **as-built** system (all PRD user stories US-001–US-016 implemented)

> **Reading note:** This document describes what is actually built. Items that
> were considered but not implemented are collected in
> [§15 Future Roadmap](#15-future-roadmap) rather than mixed into the design.

### 2. Summary / Scope
- Refer to PRD in file @prd.md

### 3. Background / Context
- Technical/business context
- Previous solutions or related systems

### 4. Goals & Constraints
- Maintain the same parameters used in the bash script that uses yt-dlp to download. That script is referenced in the References section below.
- Download thumbnails and json metadata just like the script below does
- Keep file and folder naming the same to be compatible with jellyfin

### 5. Architecture Overview

#### Deployment Architecture
- **Production (single container)**: The published image
  (`ghcr.io/miguelarios/channelfinwatcher`) runs both the FastAPI backend
  (port 8000) and the NextJS frontend (port 3000) in one container, managed by
  **supervisor**. `ffmpeg` and Node.js 20 are baked in (Node is required by
  yt-dlp's EJS JavaScript decoding). Built from the root `Dockerfile`.
- **Development (multi-container)**: `docker-compose.dev.yml` runs the backend
  and frontend as separate hot-reloading containers with bind mounts.
- **Shared Volumes**: `data/` (SQLite DBs, `config.yaml`, `cookies.txt`),
  `media/` (downloaded videos), `temp/` (download staging).

#### Two-Tier FastAPI + NextJS Architecture
- **Frontend Layer**: NextJS React application (pages router). The frontend also
  hosts thin API proxy routes under `pages/api/v1/*` that forward to the backend.
- **Backend Layer**: FastAPI REST API. Blocking work (yt-dlp, ffmpeg, filesystem
  scans) runs off the event loop via `asyncio.to_thread` / sync route handlers.
- **Application Layer**: Core business logic with background task processing via
  APScheduler (SQLite-persisted jobs, survives restarts).
- **Data Layer**: SQLite database (Alembic-managed schema) plus a YAML mirror
  of settings.

#### Component Integration Model
- The NextJS frontend calls the FastAPI backend over REST (via its proxy routes).
- Live download progress is surfaced by yt-dlp progress hooks writing to an
  in-memory store, which the UI reads by polling `/downloads/active` (~every 1–2s)
  and which is also exposed as a Server-Sent Events stream at
  `/downloads/progress/stream` for direct API consumers.
- The background scheduler runs independently of web requests.

#### Configuration-Database Hybrid Model
- **SQLite Database**: **Source of truth** for channels and settings, plus all
  runtime/operational state.
- **YAML Configuration** (`data/config.yaml`): A mirror of channels and settings,
  written from the database for backup/transparency and readable back as a
  fallback (e.g. if an advanced user edits it directly).
- **File System**: Media storage maintaining the Jellyfin-compatible layout.

### 6. Detailed Design

#### Data Models / Schema
**SQLite Database Schema** (see `backend/app/models.py`):
- **channels**: Channel definitions and settings — `url`, `channel_id`, `name`,
  `limit`, `enabled`, `quality_preset`, `schedule_override`, metadata/NFO
  tracking fields, and timestamps.
- **downloads**: Per-video download records — `video_id`, `title`, `status`
  (pending/downloading/completed/failed), `file_path`, `file_size`,
  `file_exists`, `deleted_at` (soft-delete for cleanup), `retry_count`, and
  timestamps.
- **download_history**: One row per download run (global or per-channel) —
  `videos_found`, `videos_downloaded`, `videos_skipped`, `videos_failed`,
  `status`, `run_date`, `completed_at`, `error_message`.
- **application_settings**: Key/value store for all global settings and runtime
  flags (e.g. `default_video_limit`, `default_quality_preset`, `cron_schedule`,
  `scheduler_enabled`, `nfo_enabled`, `notification_url`, and the
  `*_running` overlap-prevention locks).
- APScheduler jobs persist in a separate `data/scheduler_jobs.db`.

> Schema changes are applied by **Alembic migrations** on startup, not by
> `create_all`.

**YAML Configuration Structure** (`data/config.yaml`, mirror of the DB):
```yaml
channels:
  - url: "https://www.youtube.com/@ChannelName"
    limit: 10
    enabled: true
    quality_preset: "best"          # best | 2160p | 1080p | 720p | 480p
    schedule_override: "0 6 * * *"  # optional per-channel cron

settings:
  default_video_limit: 10
  default_quality_preset: "best"
  cron_schedule: "0 */6 * * *"      # global download schedule
  scheduler_enabled: true
  nfo_enabled: true
  nfo_overwrite_existing: false
  notification_url: ""              # Apprise URL; blank disables
```
Paths (`media_dir`, `temp_dir`, `cookies_file`) are configured via environment
variables, not YAML — see [§7 Tech Stack](#7-tech-stack) and the
[Configuration Reference](configuration.md).

#### File Organization
**Directory Structure:**
```
/media/
  ChannelName [channel_id]/
    YYYY/
      ChannelName - upload_date - title [video_id]/
        ChannelName - upload_date - title [video_id].mkv
        ChannelName - upload_date - title [video_id].info.json
        ChannelName - upload_date - title [video_id].webp
```

#### Core Algorithms
- **Recent Video Detection**: A lightweight `extract_flat` yt-dlp query lists the
  channel's most recent uploads; Shorts and live streams are filtered out at
  extraction time. The configured `limit` bounds how many are kept.
- **Duplicate Prevention**: `should_download_video()` decides per video using the
  **database + disk state** (not an `archive.txt`): already-completed videos with
  a file on disk are skipped; missing files are re-downloaded; orphaned files on
  disk are re-indexed into the database.
- **Quality Selection**: `quality_preset` maps to a yt-dlp format string
  (`QUALITY_FORMATS`) with graceful fallback to best-available; unknown presets
  fall back to `best`.
- **Automatic Cleanup**: After a run, videos beyond the channel `limit` are
  soft-deleted (files removed, DB row kept with `deleted_at` for history),
  oldest / metadata-less first.
- **Configuration Synchronization**: Database is authoritative; setting changes
  are mirrored to `config.yaml`.

#### Retry Policy
- **Within a run**: transient failures (network/timeout/rate-limit, classified by
  `utils.is_retryable_error`) retry up to `WITHIN_RUN_RETRIES` (2) extra times
  with a short backoff.
- **Across runs**: `retry_count` increments per failed run; after
  `MAX_AUTO_RETRIES` (5) a video stops being auto-attempted. A manual retry
  (`POST /downloads/{id}/retry`) resets the counter.
- **Channel level**: the scheduled job retries a whole channel on transient
  errors and isolates failures so one bad channel never stops the run.

#### Overlap Prevention
- A database-flag lock (`application_settings`, `{job}_running` keys) prevents
  overlapping runs across the global job, per-channel jobs, manual triggers, and
  reindex. Stale locks are cleared on startup. See `overlap_prevention.py`.

#### Error Handling and Edge Cases
- Channel-level errors: skip and continue with the next channel; a failed run is
  still recorded in `download_history`.
- Invalid channels: deleted/private channels are handled gracefully.
- All blocking yt-dlp/ffmpeg/filesystem work runs off the async event loop.

#### Live Progress Capabilities
- **Progress store**: yt-dlp `progress_hooks` write percent/speed/ETA for each
  active video into an in-memory, thread-safe store (`progress_store.py`).
  Entries are added on start and always removed on completion/failure.
- **Polling**: the dashboard's *Active Downloads* panel polls `/downloads/active`.
- **Server-Sent Events**: `/downloads/progress/stream` emits a JSON snapshot each
  second for direct API consumers. (The bundled UI polls rather than consuming
  SSE because the Next.js pages-router proxy buffers streaming responses.)

#### State Management
- **Frontend State**: React component state; data fetched via the frontend's
  `/api/v1/*` proxy routes. (React Query is a dependency but not broadly used —
  see [§15 Future Roadmap](#15-future-roadmap).)
- **Backend State**: SQLite for persistent data and runtime locks; the in-memory
  progress store and log ring-buffer for ephemeral state.
- **Time convention**: all timestamps are **naive UTC** end-to-end, produced via
  `app/time_utils.py` (`utc_now()` / `utc_from_timestamp()`); the frontend
  appends `Z` when parsing.

### 7. Tech Stack

#### Backend Framework
- **Python 3.11** with **FastAPI** (REST API) and **Uvicorn** (ASGI server)
- **SQLite** via **SQLAlchemy**, schema managed by **Alembic** migrations
- **APScheduler**: automated downloads; jobs persisted to SQLite so they survive
  container restarts
- **Pydantic v2**: request/response validation and serialization

#### Frontend Framework
- **NextJS** (pages router) with **TypeScript** and **TailwindCSS**
- **lucide-react** for icons
- React Query is installed but currently only lightly used (see roadmap)

#### Key Libraries
- **yt-dlp** (`[default]` extra, incl. EJS/Node.js JS decoding): downloading and
  metadata extraction
- **ffmpeg**: muxing to `.mkv`, thumbnail/subtitle/metadata embedding
- **PyYAML**: YAML config read/write
- **apprise**: failure-notification delivery (implemented; Discord, ntfy,
  Telegram, email, and many more)
- **Environment paths** are read from env vars via Pydantic settings
  (`app/config.py`)

### 8. Third-Party Dependencies

#### Critical Dependencies
- **yt-dlp**: Core dependency for YouTube downloading and interactions
  - Specific parameters: `bv*+ba/b` format, mkv output, embedded metadata
  - Output template for Jellyfin compatibility
  - Cookie support for age-restricted content
  - Subtitle downloads (en/es) and thumbnail embedding

#### Supporting Libraries
- **FastAPI Dependencies**: uvicorn, pydantic, python-multipart for file uploads
- **NextJS Dependencies**: react, react-dom, next for frontend framework
- **Real-time Libraries**: websockets (Python), socket.io-client (NextJS) for live updates
- **UI Libraries**: tailwindcss, headlessui for modern component styling
- **apprise**: Notification system for alerts and status updates
- **APScheduler**: Background task scheduling
- **PyYAML**: Configuration file management

#### Operational Dependencies
- **Docker**: Containerization and deployment platform
- **YouTube Platform**: External service availability
- **File System**: Persistent storage for media and configuration

### 9. Security & Privacy

#### Authentication Approach
- **No Authentication**: Simplified design for trusted local network environment
- **Deployment Context**: Personal homelab server with controlled access
- **Security Model**: Network-level security and physical access control

#### Privacy Considerations
- **Local Data**: All downloads and metadata stored locally
- **No External Analytics**: No data transmission beyond YouTube downloads
- **Configuration Privacy**: YAML files contain only public channel URLs

### 10. Testing Strategy
- **Backend**: pytest suite (unit + integration) using an in-memory SQLite
  database and FastAPI's `TestClient`; yt-dlp/network calls are mocked. Covers
  the API, download pipeline, retry policy, scheduling, cleanup, progress store,
  health checks, notifications, and the log buffer.
- **Frontend**: Jest + React Testing Library component tests with mocked
  `fetch`; TypeScript is type-checked (`tsc --noEmit`).
- **CI**: builds both images and runs an automated review on every PR (see
  `docs/CI-CD-EXPLAINED.md`).
- Run locally: `cd backend && python -m pytest` and `cd frontend && npx jest`.
  See [docs/testing-guide.md](testing-guide.md).

### 11. Monitoring & Observability

#### Logging Strategy
- **Application Logging**: Python `logging`, INFO by default.
- **Docker Logs**: Primary troubleshooting channel.
- **In-app Log Buffer**: The last 500 records are kept in an in-memory
  ring-buffer handler and served at `GET /api/v1/logs/recent` (filterable by
  level) so logs are reachable without shell access.

#### Notification System (implemented)
- **Apprise Integration**: `notification_service.py`. A single Apprise URL
  (`notification_url` setting) fans out to any supported service.
- **Trigger**: best-effort notification when scheduled/per-channel runs have
  failures. Dispatch runs off the event loop and never affects downloads.
- **Configuration & Test**: `GET/PUT /settings/notifications` and
  `POST /settings/notifications/test`, plus a Settings-page UI.

#### System Monitoring
- **Deep Health Check**: `GET /health` verifies database connectivity, yt-dlp
  importability/version, `ffmpeg`/`ffprobe` presence, media-volume capacity
  (flagged at ≥90%), and scheduler liveness (enabled but silent >48h = stale).
  Returns `healthy`/`degraded` with an explicit `problems` list, always HTTP 200
  so container healthchecks measure reachability.
- **Cookie Health**: `GET /settings/cookies-status` reports the YouTube cookie
  file's presence and age (stale at 30 days) — expired cookies are the most
  common silent breakage.
- **Storage Monitoring**: The dashboard shows per-channel and total storage plus
  a capacity gauge with an 80% warning banner.
- **Status Dashboard**: Channel health cards, live download progress, and
  scheduler status.

### 12. Migration Plan
- **Schema migrations**: Alembic migrations in `backend/alembic/versions/` run
  automatically on startup (`command.upgrade(cfg, "head")`), so existing
  databases upgrade in place. New columns ship with server defaults for safe
  in-place upgrades.

### 13. Risks & Alternatives Considered
- **YouTube breakage** is the main operational risk (extraction changes, bot
  detection). Mitigations: cookie support with age warnings, yt-dlp `[default]`
  EJS decoding, `/health` surfacing yt-dlp availability, and per-video retry.
- **Single-process concurrency**: blocking work is offloaded with
  `asyncio.to_thread`; SQLite uses a busy timeout and cross-thread sessions are
  used sequentially (documented in `database.py`).

### 15. Future Roadmap

Considered but **not implemented** — tracked here so the design above stays
strictly as-built:

- **WebSocket transport** for live updates. Today the UI polls `/downloads/active`
  and an SSE stream exists for API consumers; a WebSocket push channel was in the
  original design but is not built.
- **Authentication / multi-user**. The app is intentionally single-user for a
  trusted LAN (a PRD non-goal). Note: `GET /settings/notifications` and
  `GET /settings/cookies-status` return values that can look secret-shaped
  (webhook URLs, file paths); revisit masking if remote access is ever added.
- **React Query adoption** across the frontend to replace hand-rolled
  fetch/loading/error state (the dependency is present but underused).
- **Storage trends & projections** (daily/weekly growth, time-until-full),
  charts, and per-channel storage export.
- **Bandwidth / concurrent-download limits** and custom metadata templates.

### 14. References.

#### Youtube Download Script

```
#!/bin/bash

set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

media="/media"
temp="/temp"
categories_dir="/app/categories"
cookie="/app/cookies.txt"

if [ ! -d ${media} ]; then
    echo "Media directory not mounted"
    exit 1
fi

if [ ! -d ${temp} ]; then
    echo "Temp directory not mounted"
    exit 1
fi

if [ ! -d ${categories_dir} ]; then
    echo "Categories directory not found at ${categories_dir}"
    exit 1
fi

# Function to download videos for a specific category
download_category() {
    local category=$1
    local category_path="${media}/${category}/"
    local temp_path="${temp}/${category}/"
    local category_file="${categories_dir}/${category}.txt"
    
    if [ ! -f "${category_file}" ]; then
        echo "Category file ${category_file} not found. Skipping."
        return
    fi
    
    yt-dlp \
    --paths "temp:${temp_path}" \
    --paths "home:${category_path}" \
    --output "%(channel)s [%(channel_id)s]/%(upload_date>%Y)s/%(channel)s - %(upload_date)s - %(title)s [%(id)s]/%(channel)s - %(upload_date)s - %(title)s [%(id)s].%(ext)s" \
    -f bv*+ba/b \
    --embed-thumbnail \
    --write-thumbnail \
    --write-subs \
    --write-auto-sub \
    --sub-langs "en,es",-live_chat \
    --embed-subs \
    --write-info-json \
    --parse-metadata "description:(?s)(?P<meta_comment>.+)" \
    --parse-metadata "upload_date:(?s)(?P<meta_DATE_RELEASED>.+)" \
    --parse-metadata "uploader:%(meta_ARTIST)s" \
    --embed-metadata \
    --add-metadata \
    --merge-output-format mkv \
    --download-archive "archive.txt" \
    --cookies ${cookie} \
    --batch-file "${category_file}"
}

# Get list of categories from the categories directory
categories=($(find ${categories_dir} -name '*.txt' -exec basename {} .txt \;))

if [ ${#categories[@]} -eq 0 ]; then
    echo "No category files found in ${categories_dir}"
    exit 1
fi

echo "Found categories: ${categories[*]}"

# Download videos for each category
for category in "${categories[@]}"; do
    echo "Processing category: ${category}"
    download_category "$category"
done

# Remove all files and subdirectories under the temp video folder safely
if [ -d "${temp}" ]; then
    rm -rf "${temp:?}"/*
fi

echo "Download process completed."
```