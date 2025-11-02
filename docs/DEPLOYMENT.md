# ChannelFinWatcher Deployment Guide

This guide explains how to deploy ChannelFinWatcher in production using the pre-built Docker image from GitHub Container Registry.

## Table of Contents
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [Deployment Steps](#deployment-steps)
- [Updating to Latest Version](#updating-to-latest-version)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Quick Start

For those who want to get started immediately:

```bash
# Create directories
mkdir -p channelfinwatcher/{data,media,temp}
cd channelfinwatcher

# Create production docker-compose.yml
cat > docker-compose.yml << 'EOF'
name: ChannelFinWatcher

services:
  channelfinwatcher:
    container_name: channelfinwatcher
    image: ghcr.io/miguelarios/channelfinwatcher:latest
    restart: always
    environment:
      - TZ=America/Chicago  # Change to your timezone
    volumes:
      - ./data:/app/data
      - ./media:/app/media
      - ./temp:/app/temp
    ports:
      - 3000:3000
      - 8000:8000
    networks:
      - channelfinwatcher-net

networks:
  channelfinwatcher-net:
    name: channelfinwatcher-net
EOF

# Optional: Edit timezone (TZ=America/Chicago -> your timezone)
nano docker-compose.yml

# Start the application
docker compose up -d

# Access the web UI
# Open http://localhost:3000 in your browser
```

## Prerequisites

### Required
- **Docker Engine**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Storage Space**: At least 10GB free (more depending on video retention settings)
- **Network**: Internet connection for downloading videos

### Recommended
- **Fast Storage**: SSD for `/temp` directory improves download performance
- **Large Storage**: HDD with significant capacity for `/media` directory

### Verify Installation
```bash
docker --version  # Should show 20.10+
docker compose version  # Should show 2.0+
```

## Directory Structure

ChannelFinWatcher uses three main directories that persist data outside the container:

```
channelfinwatcher/
├── data/                          # Application data (REQUIRED)
│   ├── app.db                    # Main application database
│   ├── scheduler_jobs.db         # APScheduler jobs database
│   ├── config.yaml               # Auto-generated channel configuration
│   └── cookies.txt               # Optional: YouTube authentication
├── media/                         # Downloaded videos (REQUIRED)
│   └── [Channel Name] [ID]/
│       └── YYYY/
│           └── [Channel] - [Date] - [Title] [ID].mp4
├── temp/                          # Download staging (REQUIRED)
│   └── [temporary download files]
└── docker-compose.prod.yml        # Your deployment configuration
```

### Directory Purposes

**`/data`** - Application Data
- Contains SQLite databases and configuration
- **Backup this directory regularly** - it contains all your settings
- Size: Typically < 100MB
- Storage: Any reliable storage (SSD/HDD)

**`/media`** - Downloaded Videos
- Your video library, organized for media servers like Jellyfin
- Size: Can grow very large (10GB - 1TB+ depending on settings)
- Storage: Large capacity HDD recommended
- **This is your valuable content** - consider backup strategy

**`/temp`** - Download Staging
- Temporary files during active downloads
- Cleared automatically after successful downloads
- Size: Up to 2-3x your largest video size
- Storage: **Fast SSD highly recommended** for download performance

## Configuration

### Basic Configuration (docker-compose.yml)

The minimum required configuration:

```yaml
name: ChannelFinWatcher

services:
  channelfinwatcher:
    image: ghcr.io/miguelarios/channelfinwatcher:latest
    container_name: channelfinwatcher
    restart: always
    ports:
      - "3000:3000"
    volumes:
      - ./data:/app/data
      - ./media:/app/media
      - ./temp:/app/temp
    environment:
      - TZ=America/Chicago  # Set your timezone
    networks:
      - channelfinwatcher-net

networks:
  channelfinwatcher-net:
    name: channelfinwatcher-net
```

### Timezone Configuration

**Why it matters**: The scheduler uses your timezone for download timing.

Find your timezone:
```bash
# Linux/Mac
timedatectl
# or
cat /etc/timezone

# Common timezones:
# - America/New_York (EST/EDT)
# - America/Chicago (CST/CDT)
# - America/Los_Angeles (PST/PDT)
# - Europe/London
# - Asia/Tokyo
```

### User/Group ID Configuration (File Permissions)

**Why it matters**: Files created by the container need to be accessible on your host system.

**The problem**: By default, the container runs as UID/GID 1000. If your user has a different ID, you'll get permission errors when accessing downloaded files.

**Find your UID/GID:**
```bash
# Linux/Mac
id

# Example output:
# uid=1001(yourname) gid=1001(yourname) groups=1001(yourname),...
#     ^^^^               ^^^^
#     This is your PUID  This is your PGID
```

**Set in docker-compose.yml:**
```yaml
environment:
  - TZ=America/Chicago
  - PUID=1001  # Replace with your UID
  - PGID=1001  # Replace with your GID
```

**Common scenarios:**

| System | Typical UID/GID | Action |
|--------|----------------|--------|
| Ubuntu/Debian | 1000 | No change needed (default) |
| Multi-user Linux | 1001+ | Set to your UID/GID from `id` command |
| macOS | 501 | Set PUID=501, PGID=20 |
| Unraid/TrueNAS | Varies | Check with `id` command |

**What happens:**
1. Container starts with default UID 1000
2. Entrypoint script checks PUID/PGID environment variables
3. If different, updates the internal `appuser` to match
4. All files created will have your UID/GID
5. You can access/modify files without permission issues

### Port Configuration

Default ports:
- **3000**: Web UI (required for access)
- **8000**: Backend API (optional, for debugging/direct API access)

Change ports if needed:
```yaml
ports:
  - "8080:3000"  # Access UI at http://localhost:8080
  - "8001:8000"  # Access API at http://localhost:8001
```

## Deployment Steps

### Step 1: Create Project Directory

```bash
# Create main directory
mkdir -p channelfinwatcher
cd channelfinwatcher

# Create required subdirectories
mkdir -p data media temp
```

### Step 2: Create docker-compose.yml

Create a production-ready docker-compose.yml file:

```bash
cat > docker-compose.yml << 'EOF'
name: ChannelFinWatcher

services:
  channelfinwatcher:
    container_name: channelfinwatcher
    image: ghcr.io/miguelarios/channelfinwatcher:latest
    restart: always
    environment:
      - TZ=America/New_York  # Change to your timezone
    volumes:
      - ./data:/app/data
      - ./media:/app/media
      - ./temp:/app/temp
    ports:
      - 3000:3000
      - 8000:8000
    networks:
      - channelfinwatcher-net

networks:
  channelfinwatcher-net:
    name: channelfinwatcher-net
EOF
```

### Step 3: Customize Configuration (Optional)

You can edit the docker-compose.yml file to customize:

```bash
nano docker-compose.yml
```

**Common customizations:**

- **Timezone**: Change `TZ=America/New_York` to your timezone
- **Ports**: Change `3000:3000` to a different port if 3000 is already in use
- **UID/GID**: Add `PUID` and `PGID` environment variables for file permissions (see Advanced Configuration)
- **Resource limits**: Add resource limits to prevent high resource usage (see Advanced Configuration)

### Step 4: Start the Application

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Step 5: Access the Web UI

Open your browser and navigate to:
```
http://localhost:3000
```

Or if deployed on a server:
```
http://your-server-ip:3000
```

### Step 6: Add Your First Channel

1. In the web UI, go to "Channels" section
2. Paste a YouTube channel URL or ID
3. Configure video limit (e.g., keep latest 20 videos)
4. Enable the channel
5. Configure scheduler to run downloads automatically

## Updating to Latest Version

### Automatic Updates (Recommended)

```bash
cd channelfinwatcher

# Pull latest image
docker compose pull

# Recreate container with new image
docker compose up -d

# Verify update
docker compose logs
```

### Check for Updates

```bash
# See current version
docker inspect channelfinwatcher | grep Created

# Check for new releases
# Visit: https://github.com/miguelarios/ChannelFinWatcher/releases
```

### Rollback to Previous Version

```bash
# Stop current version
docker compose down

# Edit docker-compose.yml to specify version tag
# Change: image: ghcr.io/miguelarios/channelfinwatcher:latest
# To:     image: ghcr.io/miguelarios/channelfinwatcher:v1.0.0

# Start with specific version
docker compose up -d
```

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker compose logs
```

**Common issues:**
- Port already in use: Change ports in docker-compose.yml
- Permission denied: Check directory permissions
  ```bash
  sudo chown -R 1000:1000 data media temp
  ```

### Can't Access Web UI

**Check if container is running:**
```bash
docker compose ps
```

**Check if ports are accessible:**
```bash
curl http://localhost:3000
# Should return HTML content

# If on remote server, check firewall
sudo ufw allow 3000
```

### Downloads Not Working

**Check scheduler configuration:**
- In Web UI: Settings → Scheduler
- Ensure scheduler is enabled
- Verify at least one channel is enabled

**Check backend logs:**
```bash
docker compose logs channelfinwatcher | grep backend
```

**Verify yt-dlp is working:**
```bash
# Enter container
docker exec -it channelfinwatcher bash

# Test download manually
cd /app/backend
python -m yt_dlp --version
```

### Storage Issues

**Check available space:**
```bash
df -h ./data ./media ./temp
```

**Clean up old downloads:**
- In Web UI: Manually delete old videos
- Or adjust channel video limits to retain fewer videos

### Database Issues

**Backup database before troubleshooting:**
```bash
cp data/app.db data/app.db.backup
cp data/scheduler_jobs.db data/scheduler_jobs.db.backup
```

**Reset database (last resort):**
```bash
# Stop container
docker compose down

# Move old database
mv data/app.db data/app.db.old

# Start container (will create new database)
docker compose up -d
```

## Advanced Configuration

### Using Custom Cache Drive for /temp

If you have a fast cache drive (like an SSD):

```yaml
volumes:
  - ./data:/app/data
  - ./media:/app/media
  - /mnt/cache/channelfinwatcher:/app/temp  # Fast cache drive
```

### Reverse Proxy Configuration (Nginx)

**Why**: Access via domain name with HTTPS

```nginx
server {
    listen 80;
    server_name channelfinwatcher.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Running on Different Port

```yaml
ports:
  - "8080:3000"  # Access at http://localhost:8080
```

### YouTube Authentication (Age-Restricted Content)

Some videos require authentication. To handle these:

1. Export cookies from your browser (while logged into YouTube)
   - Use browser extension like "Get cookies.txt"
   - Export cookies for youtube.com

2. Place cookies file:
   ```bash
   cp cookies.txt channelfinwatcher/data/cookies.txt
   ```

3. Restart container:
   ```bash
   docker compose restart
   ```

### Resource Limits

Prevent container from consuming too many resources:

```yaml
services:
  channelfinwatcher:
    # ... other config ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Network Configuration

Connect to existing Docker network:

```yaml
networks:
  default:
    external: true
    name: your-existing-network
```

## Backup Strategy

### What to Backup

**Critical (must backup):**
- `/data/app.db` - All your settings and channel configurations
- `/data/scheduler_jobs.db` - Scheduled job information

**Optional (can be re-downloaded):**
- `/media/*` - Your video library (large, but can be re-downloaded)

**Not needed:**
- `/temp/*` - Temporary files

### Backup Script Example

```bash
#!/bin/bash
# backup-channelfinwatcher.sh

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Stop container for consistent backup
docker compose stop

# Backup databases
tar -czf "$BACKUP_DIR/channelfinwatcher_data_$DATE.tar.gz" data/

# Optional: Backup media (if storage allows)
# tar -czf "$BACKUP_DIR/channelfinwatcher_media_$DATE.tar.gz" media/

# Restart container
docker compose start

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "channelfinwatcher_data_*.tar.gz" -mtime +7 -delete
```

### Automated Backups with Cron

```bash
# Edit crontab
crontab -e

# Add backup job (daily at 3 AM)
0 3 * * * /path/to/backup-channelfinwatcher.sh >> /var/log/channelfinwatcher-backup.log 2>&1
```

## Monitoring

### Health Checks

The container includes built-in health checks:

```bash
# Check health status
docker inspect channelfinwatcher | grep -A 10 Health
```

### Resource Usage

```bash
# Monitor resources
docker stats channelfinwatcher
```

### Log Management

```bash
# View recent logs
docker compose logs --tail=100

# Follow logs in real-time
docker compose logs -f

# Filter logs for errors
docker compose logs | grep ERROR
```

## Getting Help

- **GitHub Issues**: https://github.com/miguelarios/ChannelFinWatcher/issues
- **Documentation**: https://github.com/miguelarios/ChannelFinWatcher/docs
- **Discussions**: https://github.com/miguelarios/ChannelFinWatcher/discussions

When reporting issues, include:
1. Docker version: `docker --version`
2. Container logs: `docker compose logs`
3. System info: OS, available storage, etc.
