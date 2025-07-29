# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChannelFinWatcher is a YouTube channel monitoring and video downloading application designed for personal use. It periodically downloads the most recent videos from specified YouTube channels to maintain an offline library organized for Jellyfin media server.

## Development Workflow & Preferences

### Extended Thinking
For complex problems, I may ask you to think deeper:
- "think" - standard analysis
- "think hard" - more thorough consideration
- "think harder" - deep architectural analysis
- "ultrathink" - maximum reasoning for critical decisions

### Educational Development Approach
When working on this project, always explain the "why" behind technical decisions:

#### Explain Technical Choices
- **Why we chose this technology stack** (FastAPI + NextJS + Docker)
- **Why we structure code this way** (separation of concerns, testability)
- **Why we use specific patterns** (dependency injection, health checks, migrations)
- **Why we configure things certain ways** (environment variables, mount points)

#### Teaching Moments
- **Before implementing**: Explain what we're about to build and why
- **During implementation**: Call out key patterns and best practices
- **After testing**: Explain what the tests validate and why it matters
- **When debugging**: Show thought process for diagnosing issues

#### Architecture Explanations
- **Database design decisions**: Why these tables, relationships, indexes
- **API design patterns**: Why REST + WebSocket, how endpoints relate
- **Docker strategies**: Why multi-service, volume mounts vs named volumes
- **Configuration management**: Why YAML + database hybrid approach

#### Code Quality Teaching
- **Show alternative approaches**: "We could do X, but Y is better because..."
- **Explain trade-offs**: Performance vs simplicity, flexibility vs constraints
- **Point out common pitfalls**: Things that often go wrong and how to avoid them
- **Highlight debugging techniques**: How to trace issues, useful commands

#### Real-world Context
- **Connect to larger patterns**: How this relates to microservices, 12-factor apps
- **Production considerations**: What would change for larger scale deployment
- **Maintenance implications**: How these choices affect long-term maintenance

The goal is to make each development session a learning opportunity, not just completing tasks.

## Development Commands

## Docker Development Commands

For consistent testing environment across different machines:

```bash
# Start development server with Docker
docker compose -f docker-compose.dev.yml up

# Start with rebuild (after dependency changes)
docker compose -f docker-compose.dev.yml up --build

# Run in background (detached mode)
docker compose -f docker-compose.dev.yml up -d

# Stop and clean up containers
docker compose -f docker-compose.dev.yml down

# View logs
docker compose -f docker-compose.dev.yml logs -f
```

## Git Workflow

### Daily Workflow
Every time you make meaningful changes (aim for commits every 30-60 minutes):
```bash
# What changed?
git status

# Review the actual changes before committing (great learning moment!)
git diff

# Stage all changes (or use git add <specific-files> for selective staging)
git add .

# Commit with descriptive message
git commit -m "feat: implement quick split calculator"

# Push to GitHub for backup and collaboration
git push
```

### Example Commit Messages
```bash
git commit -m "feat: implement quick split calculator"
git commit -m "fix: handle zero tabs edge case"
git commit -m "style: improve mobile responsiveness"
git commit -m "refactor: extract calculation logic to utils"
git commit -m "docs: add JSDoc comments to QuickSplit component"
```

### Commit Message Format
- `feat:` - new features
- `fix:` - bug fixes
- `refactor:` - code improvements
- `style:` - UI/styling changes
- `docs:` - documentation updates
- `test:` - test additions/changes

### Story Completion
After each user story is fully implemented and tested:
```bash
# Create a tag for the milestone
git tag -a v0.1-story-1 -m "Complete Story 1: Quick even split"

# Push changes and tags
git push origin main --tags
```

### GitHub CLI Integration (when installed)
```bash
# Create issue for next story
gh issue create --title "Story 2: Photo OCR" --body "Implement receipt photo capture and OCR"

# Create PR for review
gh pr create --title "feat: add quick split functionality" --body "Implements Story 1"

# Check workflow status
gh workflow view
```

### Branching Strategy (optional)
```bash
# Create feature branch for each story
git checkout -b feature/story-1-quick-split

# After completion and review
git checkout main
git merge feature/story-1-quick-split
```

## Architecture

### Core Components
- **FastAPI Backend**: REST API with WebSocket support for real-time updates
- **NextJS Frontend**: Modern React-based web interface with TypeScript
- **Download Engine**: yt-dlp wrapper with progress tracking and recent video detection
- **Channel Management**: CRUD operations for YouTube channel subscriptions with YAML configuration, including enable/disable functionality
- **Auto-deletion System**: Automatically removes older videos to maintain configured limits per channel
- **Scheduling System**: APScheduler integration for automated downloads
- **Storage Management**: Monitoring and reporting of disk space usage
- **SQLite Database**: Runtime state storage and download history
- **YAML Configuration**: Source of truth for channel definitions and system settings

### Technology Stack
- **FastAPI**: High-performance backend framework with automatic OpenAPI documentation
- **NextJS**: React framework with TypeScript for modern, responsive frontend
- **yt-dlp** for YouTube downloading and interactions
- **SQLite** for data storage
- **APScheduler** for background task scheduling
- **WebSockets** for real-time communication between frontend and backend
- **TailwindCSS** for utility-first styling
- **apprise** for notifications (planned)

### File Organization
The application maintains the existing yt-dlp file structure:
```
/media/
  ChannelName [channel_id]/
    YYYY/
      ChannelName - upload_date - title [video_id]/
        ChannelName - upload_date - title [video_id].mkv
```

## Configuration

### YAML Configuration Structure
```yaml
channels:
  - url: "https://www.youtube.com/c/ChannelName"
    limit: 10
    enabled: true
    schedule_override: "0 */6 * * *"
    quality_preset: "best"
  - url: "https://www.youtube.com/@ChannelHandle"  
    limit: 5
    enabled: false  # Channel temporarily disabled

settings:
  schedule: "0 * * * *"  # Default cron expression
  media_dir: "/media"
  temp_dir: "/temp"
  cookie_file: "/app/cookies.txt"
  notifications:
    enabled: false
    webhook_url: ""
```

### yt-dlp Parameters
The application preserves these specific yt-dlp parameters from the reference script:
- Format: `bv*+ba/b` with mkv output
- Embeds thumbnails, subtitles, and metadata
- Uses custom output template for Jellyfin compatibility
- Supports cookies.txt for age-restricted content
- Downloads info JSON and subtitles in en/es

## Development Approach

### Implementation Phases
1. **Infrastructure Setup**: FastAPI backend, NextJS frontend, Docker development environment
2. **Core Foundation**: YAML config, basic channel management, manual downloads
3. **Automation Layer**: Scheduler integration, automated detection, background processing
4. **Real-time Features**: WebSocket integration, live progress tracking, status updates
5. **User Experience**: Interface polish, filtering, statistics, documentation

### Key Design Principles
- **Modern Architecture**: FastAPI + NextJS provides scalable, maintainable foundation
- **Real-time Updates**: WebSocket integration for live download progress and status
- **Local network optimization**: No authentication required for trusted environment
- **Configuration-driven**: YAML file as source of truth with database for runtime state
- **Recent videos only**: Downloads last X videos per channel, not entire history
- **Automatic cleanup**: Auto-deletion maintains configured video limits per channel
- **Storage awareness**: Built-in storage monitoring and management capabilities

## File Structure Notes
- Configuration file synchronization with database occurs on startup
- Database stores runtime state and historical data
- Configuration file takes precedence over database state
- Media files organized maintaining existing naming conventions
- Auto-deletion removes oldest videos when channel limits are exceeded

## User Stories Reference
The project requirements are tracked through numbered user stories (US-001 through US-011) in docs/prd.md. Key user stories include:
- Channel management with enable/disable functionality (US-001, US-004)
- Video limit configuration per channel and globally (US-002, US-003)
- Auto-deletion to maintain video limits (US-005)
- YAML configuration management (US-006)
- Web UI monitoring and status (US-007, US-008, US-009)
- Storage usage monitoring (US-010)

## Deployment
- **Multi-service Docker Compose**: Separate containers for backend and frontend with shared volumes
- **Backend Container**: FastAPI application with Python dependencies and yt-dlp
- **Frontend Container**: NextJS application with Node.js runtime
- **Shared Volumes**: SQLite database, media directory, and configuration files
- **Network Configuration**: Internal Docker network with frontend proxying API requests
- **Alternative Single Container**: Option for combined build with nginx serving static files

This is a personal project optimized for local deployment with minimal operational overhead.