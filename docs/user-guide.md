# User Guide

Everything ChannelFinWatcher does, and how to use it. This covers the web
interface and how downloads behave. For deployment see the
[Deployment Guide](DEPLOYMENT.md); for settings details see the
[Configuration Reference](configuration.md).

## Contents
- [Quick start](#quick-start)
- [Dashboard](#dashboard)
- [Channels](#channels)
- [History](#history)
- [Settings](#settings)
- [How downloading works](#how-downloading-works)
- [Live progress](#live-progress)
- [Cookies](#youtube-cookies)
- [Notifications](#failure-notifications)
- [Troubleshooting](#troubleshooting)

---

## Quick start

1. Open the web UI (default `http://<host>:3333`).
2. Go to **Channels** and paste a YouTube channel URL (`@handle`,
   `/channel/UC…`, `/c/…`, or `/user/…` all work).
3. Optionally set a video limit and quality — or leave them to use the global
   defaults.
4. Click **Add Channel**. Metadata is fetched and the most recent videos begin
   downloading immediately.
5. Watch progress on the **Dashboard**.

By default a scheduled run every 6 hours keeps each channel's newest videos, and
older videos beyond each channel's limit are cleaned up automatically.

---

## Dashboard

The landing page — a live overview of the whole system.

- **Scheduler status** — whether automatic downloads are enabled, the schedule,
  and the next run.
- **Active Downloads** — live progress bars for anything downloading right now
  (title, channel, percent, size, speed, ETA). Hidden when nothing is running.
  See [Live progress](#live-progress).
- **Storage** — a capacity gauge for your media volume with an **80% warning
  banner**, plus how much space your videos use.
- **Library totals** — channel count, enabled count, total videos, total video
  storage.
- **Channel cards** — one per channel with a health dot:
  - 🟢 **Active** · 🔴 **Last run failed** · 🟡 **Never checked** · ⚪ **Disabled**
  - Shows videos vs limit (e.g. `8/10`), storage used, last-check time, a custom
    schedule indicator, and the last error if the most recent run failed.
- **Search / sort** the cards, quickly **enable/disable** a channel, and refresh.
  Auto-refreshes every 30 seconds.

---

## Channels

Add channels and manage each one. Per-channel actions live in the **⋮ (kebab)
menu** on each row:

| Action | What it does |
|--------|--------------|
| **Edit limit** | Click the limit to change how many videos are kept (1–100). Large reductions ask for confirmation before deleting. |
| **Quality** | Set this channel's download quality (`best`/`2160p`/`1080p`/`720p`/`480p`). Takes effect next download. |
| **Custom schedule** | Give this channel its own cron schedule instead of the global one — with live validation and a next-run preview. Clear it to return to the global schedule. |
| **Download recent videos** | Trigger a download run now. If a scheduled run is in progress, it's queued. |
| **Refresh metadata** | Re-fetch the channel's name, artwork, and info. |
| **Reindex media** | Reconcile the database with what's actually on disk (useful after manual file changes). |
| **Regenerate NFO files** | Rebuild Jellyfin `.nfo` metadata for the channel. |
| **Enable / disable** | Pause monitoring without deleting. Disabled channels are skipped by scheduled runs. |
| **Delete** | Remove the channel. You choose whether to also delete its media files. |

---

## History

A cross-channel record of every video download.

- **Filter** by channel and by status (completed, failed, downloading, pending).
- **Paginated**, newest first; each row shows the video (with a YouTube link),
  channel, status, size, and date.
- **Failed** rows show the error and a **Retry** button. Retrying resets that
  video's retry budget and re-attempts immediately.
- Videos removed by automatic cleanup show a **Cleaned up** badge (the history
  row is kept even after the file is deleted).

---

## Settings

Global configuration. See the [Configuration Reference](configuration.md) for
every value and its default.

- **Default Video Limit** — applied to new channels (1–100).
- **Default Video Quality** — applied to new channels.
- **Automatic Download Scheduler** — the global cron schedule (with live
  validation and next-run preview) and a master enable/disable switch.
- **NFO Generation** — toggle Jellyfin `.nfo` generation and whether
  regeneration overwrites existing files. A **backfill** tool generates NFO for
  channels added before NFO was enabled.
- **System Health & Alerts**:
  - **YouTube Cookies** — presence and age of your cookie file, with a warning
    when it's stale. See [Cookies](#youtube-cookies).
  - **Failure Notifications** — an Apprise URL plus a **Test** button. See
    [Notifications](#failure-notifications).

Changing a default affects **new** channels only; existing channels keep their
own settings.

---

## How downloading works

- **Recent videos only** — a fast, lightweight query lists a channel's newest
  uploads. **Shorts and live streams are filtered out.** Only the configured
  number of most-recent regular videos are kept.
- **No duplicates** — the app tracks what it has by database + files on disk.
  Already-downloaded videos are skipped; missing files are re-downloaded; files
  you added manually are picked up by **Reindex**.
- **Sequential** — videos and channels download one at a time to be gentle on
  your system and YouTube.
- **Automatic cleanup** — after a run, videos beyond a channel's limit are
  removed (oldest first). The history row is kept and marked *Cleaned up*.
- **Automatic retry**:
  - *Within a run*, transient failures (network/timeout/rate-limit) retry a
    couple of times with a short backoff.
  - *Across runs*, a video that keeps failing stops being retried automatically
    after 5 failed runs — use **Retry** in History to try again (which resets
    the counter).
- **Jellyfin layout** — files are organized as
  `Channel [id]/YYYY/Channel - date - title [id]/…` with the video (`.mkv`),
  `.info.json`, thumbnail, subtitles, and `.nfo` alongside.
- **Scheduling** — runs happen on the global schedule, except channels with a
  custom schedule which run on their own. You can always trigger a run manually.

---

## Live progress

While videos download, the **Active Downloads** panel on the dashboard shows a
progress bar per video with percent, transfer size, speed, and ETA. After the
transfer finishes, a video briefly shows **Processing** while yt-dlp muxes and
embeds metadata, then it disappears from the panel and appears in **History**.

The panel updates by polling every couple of seconds. Direct API consumers can
instead subscribe to a Server-Sent Events stream at
`GET /api/v1/downloads/progress/stream` (see the [API Reference](api-reference.md)).

---

## YouTube cookies

Some videos need you to be signed in (age-restricted content, or when YouTube
challenges the downloader). To enable those:

1. Export your YouTube cookies in **Netscape format** (e.g. a "Get cookies.txt"
   browser extension while logged into YouTube).
2. Save the file as `data/cookies.txt` next to your `docker-compose.yml`.
3. Restart the container.

**Settings → YouTube Cookies** shows whether the file is present and how old it
is. YouTube session cookies expire within weeks; the UI flags the file as
**stale at 30 days**. Expired cookies are the single most common reason
downloads suddenly start failing — re-export when you see the warning.

---

## Failure notifications

Get alerted when scheduled downloads fail. ChannelFinWatcher uses
[Apprise](https://github.com/caronc/apprise), so one URL can target Discord,
ntfy, Telegram, email, and dozens more.

1. **Settings → Failure Notifications**, paste an Apprise URL
   (e.g. `ntfy://ntfy.sh/my-topic`), and **Save**. The URL is validated first.
2. Click **Test** to send a sample.

A notification is sent (best-effort) when a scheduled or per-channel run has
failures. It never interferes with downloading. Leave the field blank to
disable. Example URLs are in the [Configuration Reference](configuration.md).

---

## Troubleshooting

**Downloads suddenly failing / "Sign in to confirm"** — your cookies are likely
expired. Check **Settings → YouTube Cookies** and re-export (see above).

**A specific video won't download** — open **History**, filter by **Failed**,
read the error, and click **Retry**. After 5 failed runs a video stops
auto-retrying until you retry it manually.

**Is the system healthy?** — `curl http://<host>:8000/health` reports database,
yt-dlp, ffmpeg, disk, and scheduler status (`healthy`/`degraded` with a
`problems` list).

**Where are the logs?** — `docker compose logs -f`, or the last 500 records via
`GET /api/v1/logs/recent`.

**Storage filling up** — the dashboard warns at 80%. Lower per-channel limits;
cleanup removes the excess on the next run.

**Scheduled runs not happening** — confirm the scheduler is **enabled** in
Settings, check the channel isn't disabled, and verify `TZ` is set correctly
(the schedule uses your timezone).

**Database is locked / concurrency** — rare; the app serializes runs and uses a
lock timeout. If a manual action returns **409**, a scheduled run is in
progress — try again when it finishes.

More: the [FAQ-style deployment troubleshooting](DEPLOYMENT.md#troubleshooting)
and [GitHub Issues](https://github.com/miguelarios/ChannelFinWatcher/issues).
