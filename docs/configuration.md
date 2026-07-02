# Configuration Reference

ChannelFinWatcher can be configured three ways, in order of how most users will
interact with it:

1. **Web UI** — the normal way. Everything below (except container paths) is
   editable under **Settings** and per-channel controls.
2. **`config.yaml`** — a mirror of the database written to `data/config.yaml`,
   for backup, transparency, and advanced/bulk editing.
3. **Environment variables** — container-level paths and runtime config.

> **The database is the source of truth.** Settings changed in the UI are saved
> to the DB and mirrored to `config.yaml`. If a setting is missing from the DB,
> the value in `config.yaml` is used as a fallback; otherwise a built-in default
> applies.

---

## Global settings

These live in the database (`application_settings` table) and mirror to the
`settings:` block of `config.yaml`. All are editable from the **Settings** page.

| Setting | Default | Values | Purpose |
|---------|---------|--------|---------|
| `default_video_limit` | `10` | 1–100 | Videos kept per channel, applied to **new** channels. |
| `default_quality_preset` | `best` | `best`, `2160p`, `1080p`, `720p`, `480p` | Quality applied to **new** channels. |
| `cron_schedule` | `0 */6 * * *` | 5-field cron (≥5 min interval) | Global download schedule. |
| `scheduler_enabled` | `true` | bool | Master switch for automatic downloads. |
| `nfo_enabled` | `true` | bool | Generate Jellyfin `.nfo` files during downloads. |
| `nfo_overwrite_existing` | `false` | bool | Overwrite existing NFO files on regeneration. |
| `notification_url` | `""` | Apprise URL | Failure notifications; blank disables. See [Notifications](#notifications). |

Changing a default (limit/quality) affects **new** channels only; existing
channels keep their per-channel value.

---

## Per-channel settings

Set when adding a channel and editable afterward (channel list / kebab menu).
They mirror to the `channels:` block of `config.yaml`.

| Field | Default | Values | Purpose |
|-------|---------|--------|---------|
| `url` | — | YouTube channel URL | `@handle`, `/channel/UC…`, `/c/…`, `/user/…` all accepted. |
| `limit` | global default | 1–100 | Videos to keep for this channel. |
| `enabled` | `true` | bool | Pause monitoring without deleting. |
| `quality_preset` | global default | preset list above | Download quality for this channel. |
| `schedule_override` | none | 5-field cron | Run this channel on its own schedule instead of the global one. Blank = use global. |

### `config.yaml` example
```yaml
channels:
  - url: "https://www.youtube.com/@MrsRachel"
    limit: 20
    enabled: true
    quality_preset: "1080p"
    schedule_override: "0 6 * * *"   # 6am daily; omit to use the global schedule

settings:
  default_video_limit: 10
  default_quality_preset: "best"
  cron_schedule: "0 */6 * * *"
  scheduler_enabled: true
  nfo_enabled: true
  nfo_overwrite_existing: false
  notification_url: "ntfy://ntfy.sh/my-topic"
```

---

## Quality presets

`quality_preset` maps to a yt-dlp format string:

| Preset | Behavior |
|--------|----------|
| `best` | Best available video + audio. |
| `2160p` / `1080p` / `720p` / `480p` | Best at or below that height, **falling back** to best-available if nothing qualifies. |

Unknown values fall back to `best`. Changes take effect on the next download.

---

## Scheduling

- **Global**: `cron_schedule` runs all channels that have **no** override.
- **Per-channel**: a `schedule_override` moves that channel onto its own job.
- Cron is standard 5-field (`minute hour day month weekday`); the minimum
  interval is 5 minutes. The UI validates expressions live and previews the next
  runs (backed by `GET /api/v1/scheduler/validate`).
- Runs never overlap — a shared lock serializes the global job, per-channel jobs,
  manual triggers, and reindex.

---

## Notifications

Failure notifications use [Apprise](https://github.com/caronc/apprise): one URL
fans out to many services. Set it under **Settings → Failure Notifications** or
via `notification_url`. Examples:

| Service | Example URL |
|---------|-------------|
| ntfy | `ntfy://ntfy.sh/my-topic` |
| Discord | `discord://webhook_id/webhook_token` |
| Telegram | `tgram://bot_token/chat_id` |
| Email | `mailto://user:pass@gmail.com` |

The URL is validated before saving, and a **Test** button sends a sample. A
notification is sent (best-effort) when a scheduled or per-channel run has
failures; it never affects downloading. See the full list at the Apprise wiki.

---

## YouTube cookies

Some videos (age-restricted, or when YouTube demands sign-in) require cookies.
Place a Netscape-format cookie file at `data/cookies.txt`. **Settings** shows
whether it's present and its age (flagged **stale at 30 days** — YouTube session
cookies expire within weeks, and expired cookies are the most common cause of
downloads suddenly failing).

---

## Environment variables

Read by `backend/app/config.py` (Pydantic settings). Defaults target the
in-container paths used by the published image; you normally only set `TZ`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TZ` | `UTC` | Timezone for the scheduler (e.g. `America/Chicago`). |
| `DATABASE_URL` | `sqlite:////app/data/app.db` | Main database. |
| `MEDIA_DIR` | `/app/media` | Downloaded videos. |
| `TEMP_DIR` | `/app/temp` | Download staging (use fast/SSD storage). |
| `CONFIG_FILE` | `/app/data/config.yaml` | YAML config path. |
| `COOKIES_FILE` | `/app/data/cookies.txt` | YouTube cookie file. |
| `SCHEDULER_DATABASE_URL` | `sqlite:////app/data/scheduler_jobs.db` | APScheduler job store. |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Backend bind address. |
| `DEBUG` | `true` | Verbose logging / yt-dlp verbosity. |

Container volumes (`data/`, `media/`, `temp/`) map these paths to the host — see
the [Deployment Guide](DEPLOYMENT.md).

---

## Where each setting is stored

| Kind | Store | Example |
|------|-------|---------|
| Container paths, timezone | Environment variables | `TZ`, `MEDIA_DIR` |
| Global app settings | DB `application_settings` (mirrored to `config.yaml`) | `cron_schedule`, `notification_url` |
| Per-channel settings | DB `channels` (mirrored to `config.yaml`) | `limit`, `quality_preset` |
| Runtime locks/flags | DB `application_settings` | `scheduled_downloads_running` |
| Scheduler jobs | `data/scheduler_jobs.db` | per-channel cron jobs |
