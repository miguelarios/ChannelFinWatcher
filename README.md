# ChannelFinWatcher

A YouTube channel monitoring application that automatically downloads the most recent videos from specified channels to maintain an offline library organized for Jellyfin media server.

## Overview

ChannelFinWatcher periodically monitors YouTube channels and downloads only the most recent X videos (configurable per channel), automatically cleaning up older videos to maintain storage limits. Perfect for keeping up with your favorite channels without manual intervention.

## Key Features

- **Recent Videos Only**: Downloads last X videos per channel, not entire history
- **Auto-cleanup**: Removes older videos when limits are exceeded
- **Dual Configuration**: Manage channels via YAML config or web interface
- **Channel Control**: Enable/disable channels without removal
- **Storage Monitoring**: Track disk usage and system health
- **Jellyfin Compatible**: Maintains proper file organization and metadata

## Quick Start

```bash
# Clone repository
git clone https://github.com/miguelarios/ChannelFinWatcher.git
cd ChannelFinWatcher

# Start with Docker (coming soon)
docker compose up
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

## Development

See [CLAUDE.md](CLAUDE.md) for development workflow and [docs/](docs/) for detailed requirements.

## Status

🚧 **In Development** - Core functionality being implemented

---

*Personal project optimized for local deployment with minimal operational overhead.*