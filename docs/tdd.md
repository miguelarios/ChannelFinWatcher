## Technical Design Document (TDD) Outline

### 1. Title & Metadata
- YouTube Recent Video Downloader
- Date: 2025-07-27

### 2. Summary / Scope
- Refer to PRD in file `prd.md`

### 3. Background / Context
- Technical/business context
- Previous solutions or related systems

### 4. Goals & Constraints
- Maintain the same parameters used in the bash script that uses yt-dlp to download. That script is referenced in the References section below.
- Download thumbnails and json metadata just like the script below does
- Keep file and folder naming the same to be compatible with jellyfin

### 5. Architecture Overview

#### Deployment Architecture
- Dockerfile and Docker compose to run this on a server
- Single container approach with persistent volumes
- SQLite database file on persistent volume
- Configuration mounted from host system

#### Single-Tier Streamlit Architecture
- **Presentation Layer**: Streamlit Dashboard providing unified interface for all operations
- **Application Layer**: Core business logic with integrated services in single application context
- **Data Layer**: SQLite database for runtime state and YAML configuration for settings

#### Component Integration Model
- UI components directly invoke business logic functions
- All operations share common database connection
- Services communicate through direct method calls
- Single process manages all functionality

#### Configuration-Database Hybrid Model
- **YAML Configuration**: Source of truth for channel definitions and system settings
- **SQLite Database**: Runtime state storage and operational data
- **File System**: Media storage maintaining existing organizational structure

### 6. Detailed Design

#### Data Models / Schema
**SQLite Database Schema:**
- **channels**: Channel definitions synchronized from YAML configuration
- **downloads**: Complete download history and status tracking
- **schedule_history**: Automated run tracking and performance metrics
- **system_state**: Runtime locks and operational status

**YAML Configuration Structure:**
```yaml
channels:
  - url: "https://www.youtube.com/c/ChannelName"
    limit: 10
    enabled: true
    schedule_override: "0 */6 * * *"
    quality_preset: "best"

settings:
  schedule: "0 * * * *"  # Default cron expression
  media_dir: "/media"
  temp_dir: "/temp"
  cookie_file: "/app/cookies.txt"
  notifications:
    enabled: false
    webhook_url: ""
```

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
- **Recent Video Detection**: Query channel feed, sort by upload date, apply configured limit
- **Duplicate Prevention**: Check against download history using video IDs
- **Configuration Synchronization**: Full sync between YAML file and database on startup

#### Error Handling and Edge Cases
- Channel-level errors: Skip and continue with next channel
- Network failures: Retry with exponential backoff
- Storage validation: Pre-check disk space before downloads
- Invalid channels: Handle deleted/private channels gracefully

#### State Management
- Streamlit session state for UI persistence
- SQLite database for permanent storage
- Direct file system access for media operations
- YAML configuration for settings management

### 7. Tech Stack

#### Core Framework
- **Python**: Primary application language
- **Streamlit**: Web framework for dashboard and user interface
- **SQLite**: Zero-configuration database for data persistence
- **APScheduler**: Pure Python scheduling solution for automated downloads

#### Key Libraries
- **yt-dlp**: YouTube downloading and metadata extraction
- **PyYAML**: YAML configuration file parsing and validation
- **apprise**: Notification system integration (planned)

### 8. Third-Party Dependencies

#### Critical Dependencies
- **yt-dlp**: Core dependency for YouTube downloading and interactions
  - Specific parameters: `bv*+ba/b` format, mkv output, embedded metadata
  - Output template for Jellyfin compatibility
  - Cookie support for age-restricted content
  - Subtitle downloads (en/es) and thumbnail embedding

#### Supporting Libraries
- **streamlit**: WebUI framework for dashboard interface
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
- No testing for now. 

### 11. Monitoring & Observability

#### Logging Strategy
- **Application Logging**: Structured logging for operational events
- **Download Progress**: Real-time progress tracking and completion status
- **Error Logging**: Detailed error context for troubleshooting
- **Docker Logs**: Centralized logging accessible through container logs

#### Notification System
- **Apprise Integration**: External notification capabilities
- **Event Types**: Download completion, errors, system status
- **Configuration**: Optional webhook and notification service setup

#### System Monitoring
- **Health Checks**: Basic application health endpoints
- **Resource Tracking**: Storage usage and download performance
- **Status Dashboard**: Real-time system status in web interface

### 12. Migration Plan
- Not applicable as this is a personal project

### 13. Risks & Alternatives Considered
- Not applicable, i think.

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