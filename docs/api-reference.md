# API Reference

ChannelFinWatcher exposes a REST API served by the FastAPI backend. This
reference is generated from the current implementation (`backend/app/api.py`,
`backend/main.py`).

- **Base URL**: `http://<host>:8000`
- **Prefix**: all endpoints below are under `/api/v1` **except** `/` and
  `/health`, which are served at the root.
- **Auth**: none. The app is designed for a single user on a trusted LAN.
- **Interactive docs**: live Swagger UI at `/docs` and ReDoc at `/redoc`; the
  raw OpenAPI schema is at `/api/v1/openapi.json`.
- **Timestamps**: ISO-8601 **naive UTC** (no offset). Clients should treat them
  as UTC.

The bundled web UI does not call these directly; it calls thin Next.js proxy
routes under `/api/v1/*` (in `frontend/src/pages/api/`) that forward here.

---

## System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API info and links to docs. |
| `GET` | `/health` | Deep health check (see below). |
| `GET` | `/api/v1/logs/recent` | Recent in-memory log records. |

### `GET /health`
Always returns **HTTP 200** (so container healthchecks measure reachability);
the payload carries the diagnosis.

```json
{
  "status": "healthy",              // or "degraded"
  "problems": [],                    // human-readable issues when degraded
  "service": "ChannelFinWatcher",
  "version": "…",
  "database": "connected",
  "directories": { "...": { "exists": true, "writable": true } },
  "tools": { "yt_dlp_version": "…", "ffmpeg": true, "ffprobe": true },
  "disk": { "total_bytes": 0, "free_bytes": 0, "usage_percent": 42.0 },
  "scheduler": { "enabled": true, "last_run": "…", "stale": false }
}
```
`degraded` is reported for: DB unreachable, yt-dlp not importable, ffmpeg
missing, disk ≥90% full, media volume unreadable, or scheduler enabled but
silent for >48h.

### `GET /api/v1/logs/recent`
Query: `limit` (1–500, default 100), `level` (`DEBUG|INFO|WARNING|ERROR|CRITICAL`,
returns that level and above). → `{ "logs": [{timestamp, level, logger, message}], "count": N }`

---

## Channels

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/channels` | List all channels with summary counts. |
| `POST` | `/api/v1/channels` | Add a channel (extracts metadata, starts initial download). |
| `GET` | `/api/v1/channels/{id}` | Get one channel. |
| `PUT` | `/api/v1/channels/{id}` | Update channel settings (partial). |
| `DELETE` | `/api/v1/channels/{id}` | Remove a channel (optionally its media). |
| `POST` | `/api/v1/channels/{id}/refresh-metadata` | Re-fetch metadata + images. |
| `POST` | `/api/v1/channels/{id}/reindex` | Sync DB with files on disk. |
| `POST` | `/api/v1/channels/{id}/download` | Manually trigger a download run. |
| `POST` | `/api/v1/channels/{id}/nfo/regenerate` | Regenerate NFO files for the channel. |

### `POST /api/v1/channels`
Body:
```json
{
  "url": "https://www.youtube.com/@ChannelName",
  "limit": 10,                 // optional; omit to use the global default
  "enabled": true,             // optional (default true)
  "quality_preset": "1080p",   // optional; omit to use the global default
  "schedule_override": "0 6 * * *"  // optional per-channel cron
}
```
`quality_preset` must be one of `best|2160p|1080p|720p|480p` (else 422). An
invalid `schedule_override` cron returns 400. Duplicate channels return 400.

### `PUT /api/v1/channels/{id}`
Any subset of `name`, `limit`, `enabled`, `quality_preset`, `schedule_override`.
Changing `schedule_override`/`enabled` re-syncs the per-channel scheduler job.

### `DELETE /api/v1/channels/{id}`
Query: `delete_media` (bool, default `false`). Deletes the DB record and,
optionally, the channel's media directory.

### `POST /api/v1/channels/{id}/reindex`
Protected by an application-level lock; returns **409** if a reindex is already
running. → stats `{ found, missing, added, skipped, errors }`.

### `POST /api/v1/channels/{id}/download`
Runs immediately when idle (**200**), or queues behind a running scheduled job
(**202**, with queue `position`). 400 if the channel is disabled.

---

## Downloads

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/downloads` | Global download history across channels (filter + paginate). |
| `GET` | `/api/v1/downloads/{id}` | One download record. |
| `POST` | `/api/v1/downloads/{id}/retry` | Retry a failed download (resets its retry budget). |
| `GET` | `/api/v1/downloads/active` | Snapshot of in-flight downloads with live progress. |
| `GET` | `/api/v1/downloads/progress/stream` | Server-Sent Events stream of active-download snapshots. |
| `GET` | `/api/v1/channels/{id}/downloads` | Per-channel download records (paginated). |
| `GET` | `/api/v1/channels/{id}/download-history` | Per-channel run history. |

### `GET /api/v1/downloads`
Query: `channel_id`, `status` (`pending|downloading|completed|failed`),
`limit` (1–200, default 50), `offset`. → `{ downloads: [...], total }`. Each item
includes `channel_name`, `file_exists`, `deleted_at`, `retry_count`. An invalid
`status` returns 400; an unknown `channel_id` returns an empty list (not 404).

### `POST /api/v1/downloads/{id}/retry`
Only valid for `failed` downloads (else 400); 400 if the channel is disabled;
**409** if a scheduled job is running. Resets `retry_count`, re-attempts
immediately (with within-run retries), and returns
`{ success, error_message, download }`.

### `GET /api/v1/downloads/active`
`{ active: [{ video_id, channel_id, channel_name, title, status, percent,
downloaded_bytes, total_bytes, speed, eta_seconds, started_at }], count }`.
`status` is `starting` → `downloading` → `processing` (merge/embed).

### `GET /api/v1/downloads/progress/stream`
`text/event-stream`. Emits `data: {active, count}\n\n` once per second until the
client disconnects. (The bundled UI polls `/downloads/active` instead, because
the Next.js proxy buffers streaming responses.)

---

## Dashboard

### `GET /api/v1/dashboard`
Aggregated status for the dashboard in one round-trip:
```json
{
  "disk": { "total_bytes": 0, "used_bytes": 0, "free_bytes": 0,
            "usage_percent": 42.0, "warning": false },   // null if media dir unreadable
  "totals": { "channels": 3, "enabled_channels": 2, "videos": 40, "storage_bytes": 0 },
  "channels": [ {
    "id": 1, "name": "…", "url": "…", "enabled": true, "limit": 10,
    "quality_preset": "best", "schedule_override": null, "metadata_status": "completed",
    "video_count": 8, "storage_bytes": 0, "last_check": "…",
    "last_run_status": "completed", "last_run_date": "…", "last_run_error": null
  } ],
  "generated_at": "…"
}
```
`warning` is `true` at ≥80% disk usage. Channels are sorted most-recently-checked
first, never-checked last. Storage/counts come from the DB (completed downloads
still on disk), not a filesystem walk.

---

## Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET`/`PUT` | `/api/v1/settings/default-video-limit` | Default video limit for new channels (1–100). |
| `GET`/`PUT` | `/api/v1/settings/default-quality` | Default quality preset for new channels. |
| `GET`/`PUT` | `/api/v1/settings/nfo` | NFO generation settings (`enabled`, `overwrite_existing`). |
| `GET` | `/api/v1/settings/cookies-status` | YouTube cookie file presence/age. |
| `GET`/`PUT` | `/api/v1/settings/notifications` | Apprise notification URL. |
| `POST` | `/api/v1/settings/notifications/test` | Send a test notification. |

- **default-quality** `PUT` body `{ "quality": "1080p" }` — validated against the
  preset list (422 otherwise). Applies to new channels only.
- **cookies-status** → `{ present, path, size_bytes, modified_at, age_days, stale }`
  (`stale` at ≥30 days).
- **notifications** `PUT` body `{ "url": "ntfy://ntfy.sh/topic" }` — validated by
  Apprise (400 if unrecognized); blank disables. `test` returns 400 if none is
  configured, 502 if dispatch fails.

Settings changes are mirrored to `config.yaml`.

---

## Scheduler

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/scheduler/status` | Current schedule, next/last run, job count. |
| `POST` | `/api/v1/scheduler/schedule` | Set the global cron schedule. |
| `PUT` | `/api/v1/scheduler/enable` | Enable/disable the scheduler. |
| `GET` | `/api/v1/scheduler/validate` | Validate a cron expression (no save). |

- **schedule** `POST` body `{ "cron_expression": "0 */6 * * *" }` — 5-field cron;
  minimum interval 5 minutes. Returns next runs + a human-readable description.
- **validate** query `?expression=…` → `{ valid, error, next_run, next_5_runs,
  time_until_next, human_readable }`. Used for live validation in the UI (global
  schedule and per-channel overrides).
- **enable** `PUT` body `{ "enabled": true }`.

Channels with a `schedule_override` run on their own per-channel jobs; all
channels without one run on this global schedule.

---

## NFO (Jellyfin metadata)

NFO files are generated automatically during downloads. These endpoints manage
**backfill** for pre-existing libraries and manual regeneration.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/nfo/backfill/start` | Start backfilling NFO for channels missing it. |
| `POST` | `/api/v1/nfo/backfill/pause` | Pause the backfill job. |
| `POST` | `/api/v1/nfo/backfill/resume` | Resume the backfill job. |
| `GET` | `/api/v1/nfo/backfill/status` | Backfill progress/state. |
| `GET` | `/api/v1/nfo/backfill/needed` | Count of channels needing backfill. |
| `POST` | `/api/v1/channels/{id}/nfo/regenerate` | Regenerate NFO for one channel. |

---

## Status codes

- **200** success · **202** accepted/queued (manual download behind scheduler)
- **400** validation error · **404** not found · **409** conflict (a lock is held)
- **422** request-body schema validation (Pydantic) · **500** server error
- **502** downstream failure (notification dispatch) · **504** upstream timeout
  (returned by the frontend proxy for long operations)
