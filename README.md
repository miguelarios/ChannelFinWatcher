# ChannelFinWatcher

A YouTube channel monitoring application that automatically downloads the most recent videos from specified channels to maintain an offline library organized for Jellyfin media server.

Built with **FastAPI backend** and **NextJS frontend** for modern, real-time user experience.

## Overview

ChannelFinWatcher periodically monitors YouTube channels and downloads only the most recent X videos (configurable per channel), automatically cleaning up older videos to maintain storage limits. Perfect for keeping up with your favorite channels without manual intervention.

## Key Features

- **Recent Videos Only**: Downloads last X videos per channel, not entire history
- **Real-time Updates**: Live progress tracking via WebSocket connections
- **Auto-cleanup**: Removes older videos when limits are exceeded
- **Dual Configuration**: Manage channels via YAML config or web interface
- **Channel Control**: Enable/disable channels without removal
- **Storage Monitoring**: Track disk usage and system health
- **Jellyfin Compatible**: Maintains proper file organization and metadata
- **Docker Development**: 100% containerized development environment

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

For production deployment, use host mount points:

```bash
# Copy and modify production compose file
cp docker-compose.prod.yml docker-compose.yml

# Edit docker-compose.yml to set your host paths:
# - /your/server/data:/app/data
# - /your/server/config:/app/config  
# - /your/server/media:/app/media
# - /your/server/temp:/app/temp

# Deploy
docker compose up -d
```

### Required Host Directories

Create these directories on your server:
- **data/**: SQLite database and application state
- **config/**: YAML configuration files  
- **media/**: Downloaded videos (organized for Jellyfin)
- **temp/**: Temporary files during downloads

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