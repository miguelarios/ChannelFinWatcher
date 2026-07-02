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

Create a `config.yaml` file:

```yaml
channels:
  - url: "https://www.youtube.com/@ChannelName"
    limit: 10
    enabled: true

settings:
  schedule: "0 */6 * * *"  # Every 6 hours
  media_dir: "/media"
```

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

# Edit for production use (IMPORTANT: change test paths and ports)
nano docker-compose.yml
# Change:
#   - ./test/data -> ./data
#   - ./test/media -> ./media
#   - ./test/temp -> ./temp
#   - ports 3333:3000 -> 3000:3000 (or your preferred port)
#   - ports 8001:8000 -> 8000:8000 (optional, for API access)
#   - TZ to your timezone

# Start the application
docker compose up -d

# Access web UI at http://localhost:3000
```

### Directory Structure

- **data/**: SQLite databases, config.yaml, and cookies.txt
- **media/**: Downloaded videos (organized for Jellyfin)
- **temp/**: Temporary download staging (use fast SSD for performance)

**📘 Full deployment guide**: See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Architecture

- **Backend**: FastAPI with SQLAlchemy, APScheduler, and WebSocket support
- **Frontend**: NextJS with TypeScript, TailwindCSS, and React Query  
- **Database**: SQLite for development, configurable for production
- **Real-time**: WebSocket connections for live updates
- **Deployment**: Multi-container Docker setup with persistent volumes

## Development Resources

See [CLAUDE.md](CLAUDE.md) for development workflow and [docs/](docs/) for detailed requirements.

## Status

🚧 **In Development** - Core functionality being implemented

---

*Personal project optimized for local deployment with minimal operational overhead.*