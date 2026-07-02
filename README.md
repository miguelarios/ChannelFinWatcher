# ChannelFinWatcher

A YouTube channel monitoring application that automatically downloads the most recent videos from specified channels to maintain an offline library organized for Jellyfin media server.

Built with **FastAPI backend** and **NextJS frontend** for modern, real-time user experience.

## Overview

ChannelFinWatcher periodically monitors YouTube channels and downloads only the most recent X videos (configurable per channel), automatically cleaning up older videos to maintain storage limits. Perfect for keeping up with your favorite channels without manual intervention.

## Key Features

- **Recent Videos Only**: Downloads last X videos per channel, not entire history
- **Smart Content Filtering**: Automatically excludes YouTube Shorts and live streams, downloading only regular uploaded videos
- **Live Download Progress**: Real-time progress bars on the dashboard (polling), plus a Server-Sent Events stream for API consumers
- **Auto-cleanup**: Removes older videos when limits are exceeded
- **Automatic Retry**: Transient download failures retry with backoff; permanently failing videos stop after 5 attempts and can be retried manually from the History view
- **Quality Presets**: Per-channel video quality (best/2160p/1080p/720p/480p) with graceful fallback, plus a global default for new channels
- **Flexible Scheduling**: Global cron schedule plus optional per-channel schedule overrides with live cron validation
- **Status Dashboard**: Channel health cards, storage capacity gauge with 80% warnings, and library totals
- **Download History**: Cross-channel history with filtering, pagination, and one-click retry of failures
- **Failure Notifications**: Optional [Apprise](https://github.com/caronc/apprise) notifications (Discord, ntfy, Telegram, email, ...) when scheduled runs fail
- **Deep Health Checks**: `/health` verifies database, yt-dlp, ffmpeg, disk capacity, and scheduler liveness
- **Dual Configuration**: Manage channels via YAML config or web interface
- **Channel Control**: Enable/disable channels without removal
- **Jellyfin Compatible**: Maintains proper file organization and NFO metadata
- **Docker Development**: 100% containerized development environment

## Web Interface

- **Dashboard** — channel status cards (health, video count vs limit, storage, last check), live download progress, storage overview, scheduler status
- **Channels** — add channels, edit limits inline, set per-channel quality and custom cron schedules, refresh metadata, reindex media, regenerate NFO files
- **History** — every download across all channels with status/channel filters and retry buttons on failures
- **Settings** — default video limit and quality, global schedule with cron validation, NFO options, cookie file health, and failure notifications

## Quick Start (Docker Development)

**No local Python or Node.js installation required!**

```bash
# Clone repository
git clone https://github.com/miguelarios/ChannelFinWatcher.git
cd ChannelFinWatcher

# Start development environment
docker compose -f docker-compose.dev.yml up

# Access the application:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

## Configuration

Everything is configurable from the **web UI** — no file editing required. A
`config.yaml` is written to `data/config.yaml` and kept in sync with the
database, so advanced users can also edit it directly:

```yaml
channels:
  - url: "https://www.youtube.com/@ChannelName"
    limit: 10                      # Videos to keep for this channel
    enabled: true                  # Pause monitoring without removing
    quality_preset: "best"         # best | 2160p | 1080p | 720p | 480p
    schedule_override: "0 6 * * *" # Optional per-channel cron (omit to use global)

settings:
  default_video_limit: 10          # Applied to new channels
  default_quality_preset: "best"   # Applied to new channels
  cron_schedule: "0 */6 * * *"     # Global download schedule
  scheduler_enabled: true
  nfo_enabled: true                # Generate Jellyfin .nfo files
  notification_url: ""             # Apprise URL for failure alerts (blank = off)
```

> The database is the source of truth; the YAML file mirrors it for backup and
> transparency. See [docs/configuration.md](docs/configuration.md) for the full
> reference.

## File Organization

Videos are organized for Jellyfin compatibility:
```
/media/
  ChannelName [channel_id]/
    2024/
      ChannelName - 20241201 - Video Title [video_id]/
        ChannelName - 20241201 - Video Title [video_id].mkv
```

## Use Case

Ideal for busy parents who want to keep recent videos from educational channels like Mrs. Rachel available offline for kids, without accumulating old content or requiring manual management.

## Development Commands

All development happens inside Docker containers:

```bash
# View logs
docker compose -f docker-compose.dev.yml logs -f

# Access backend container
docker compose -f docker-compose.dev.yml exec backend bash

# Access frontend container  
docker compose -f docker-compose.dev.yml exec frontend sh

# Rebuild after dependency changes
docker compose -f docker-compose.dev.yml up --build

# Stop environment
docker compose -f docker-compose.dev.yml down
```

## Production Deployment

Deploy using pre-built Docker image from GitHub Container Registry:

```bash
# Create project directory
mkdir -p channelfinwatcher/{data,media,temp}
cd channelfinwatcher

# Download compose file
curl -O https://raw.githubusercontent.com/miguelarios/ChannelFinWatcher/main/docker-compose.yml

# Optional: adjust TZ and host ports for your environment
nano docker-compose.yml
#   - TZ: set your timezone (default America/Chicago)
#   - ports: 3333:3000 maps the web UI to host port 3333 (change as desired)
#   - ports: 8001:8000 exposes the API/docs (optional)

# Start the application
docker compose up -d

# Access web UI at http://localhost:3333
```

The shipped image is a **single container** that runs both the API (port 8000)
and the web UI (port 3000) under supervisor, with `ffmpeg` and Node.js
included. Volumes already point at `./data`, `./media`, and `./temp`.

### Directory Structure

- **data/**: SQLite databases, config.yaml, and cookies.txt
- **media/**: Downloaded videos (organized for Jellyfin)
- **temp/**: Temporary download staging (use fast SSD for performance)

**📘 Full deployment guide**: See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Architecture

- **Backend**: FastAPI with SQLAlchemy and APScheduler (SQLite-persisted jobs)
- **Frontend**: NextJS (pages router) with TypeScript and TailwindCSS
- **Database**: SQLite (schema managed by Alembic migrations)
- **Live updates**: yt-dlp progress hooks → in-memory store → 1s polling in the
  UI, plus a Server-Sent Events stream for API consumers
- **Deployment**: single production container (supervisor runs API + UI);
  multi-container Docker Compose for local development

See the [Technical Design Document](docs/tdd.md) for the full architecture and
[docs/api-reference.md](docs/api-reference.md) for the REST API.

## Documentation

- **[User Guide](docs/user-guide.md)** — every feature and how to use it
- **[Configuration Reference](docs/configuration.md)** — all settings (web UI, YAML, env)
- **[API Reference](docs/api-reference.md)** — every REST endpoint
- **[Deployment Guide](docs/DEPLOYMENT.md)** — production setup and updates
- **[Technical Design](docs/tdd.md)** — architecture and internals
- **[CLAUDE.md](CLAUDE.md)** — development workflow

## Roadmap

Ideas not yet implemented (contributions welcome):

- WebSocket transport for live updates (currently polling + SSE)
- Authentication / multi-user support (currently single-user, trusted-LAN)
- Storage-trend charts and disk-full projections
- Bandwidth / concurrent-download limits

---

*Personal project optimized for local deployment with minimal operational overhead.*