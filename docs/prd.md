## Product Requirements Document (PRD) Outline

### 1. Title & Metadata
- ChannelFinWatcher
- Date: 2025-07-27

### 2. Overview / Executive Summary
Application that monitors specific YouTube channels periodically and downloads the most recent videos to always have the latest videos in an offline or personal library. Application organizes the videos to be used with Jellyfin.

### 3. Problem Statement
This app allows someone to keep the latest videos (i.e. perhaps the latest 50 videos) for a specific youtube channel so that you can watch it offline or on your own media application of choice. This avoid the issue of having old videos and you have to periodically save URLs for specific videos to batch download them later. Now you can monitor channels and download videos without a user having to remember to do this.

### 4. Goals & Non-Goals
- In-scope functionality / User Goals: What's in it for the user?
    - Add new YouTube Channels
    - Monitor and periodically download videos
    - Erase old videos to avoid filling up storage
    - Ease of deployment with docker
    - Simple webUI dashboard
- Out-of-scope explicitly noted / Non-Goals: What's out of scope?
    - Authentication
    - No overengineering
    - This is for a personal project so doesn't have to be perfect and production ready at first

### 5. User Stories / Use Cases

The user stories are organized into categories and are documented in detail in the `/docs/stories/` directory:

#### Foundation
- **[Story-000: Infrastructure Setup](stories/story-000-infrastructure-setup.md)** - Core technical infrastructure and project foundation

#### Core Channel Management
- **[US-001: Add Channel via Web UI](stories/story-001-add-channel-web-ui.md)** - Add YouTube channels through web interface
- **[US-002: Configure Channel Video Limit](stories/story-002-configure-channel-video-limit.md)** - Set per-channel video retention limits  
- **[US-003: Set Global Default Video Limit](stories/story-003-set-global-default-video-limit.md)** - Configure default limits for new channels
- **[US-004: Toggle Channel Enable/Disable](stories/story-004-toggle-channel-enable-disable.md)** - Temporarily pause channel monitoring
- **[US-005: Automatic Video Cleanup](stories/story-005-automatic-video-cleanup.md)** - Auto-delete old videos when limits exceeded
- **[US-006: YAML Configuration Management](stories/story-006-yaml-configuration-management.md)** - File-based configuration for advanced users

**US-012: Remove/Delete Channels**
- **Story**: As a user, I want to delete channels from monitoring so that I can remove channels I no longer want to track
- **Value**: Provides complete CRUD functionality for channel management
- **Acceptance Criteria**:
  - User can delete channels via web UI with confirmation dialog
  - Deletion removes channel from database and YAML configuration
  - User can choose to preserve or delete existing downloaded videos
  - Bulk deletion available for multiple channels
  - Deleted channels can be re-added without conflicts

**US-013: Manual Download Trigger**
- **Story**: As a user, I want to manually trigger downloads for specific channels so that I can get new videos immediately without waiting
- **Value**: Provides user control over download timing for urgent content updates
- **Acceptance Criteria**:
  - User can trigger immediate download for individual channels
  - Manual downloads respect channel settings (limits, quality, enabled status)
  - Progress is visible in real-time during manual downloads
  - Manual triggers don't interfere with scheduled downloads
  - User receives confirmation when manual download completes

**US-014: Channel Health Management**
- **Story**: As a user, I want the system to detect and handle unhealthy channels so that dead or private channels don't cause system issues
- **Value**: Maintains system reliability by handling YouTube channel changes gracefully
- **Acceptance Criteria**:
  - System detects deleted, private, or inaccessible channels
  - Users are notified when channels become unavailable
  - Unhealthy channels are automatically disabled but not deleted
  - Users can manually verify and re-enable recovered channels
  - Health check runs periodically and logs status changes

**US-015: Download Quality Configuration**
- **Story**: As a user, I want to configure video quality settings per channel so that I can optimize storage vs quality based on content type
- **Value**: Enables storage optimization while maintaining quality for important content
- **Acceptance Criteria**:
  - User can select quality presets per channel (best, 1080p, 720p, 480p)
  - Global default quality setting applies to new channels
  - Quality changes take effect on next download cycle
  - System falls back gracefully when preferred quality unavailable
  - Quality settings sync between web UI and YAML configuration

**US-016: Schedule Configuration**
- **Story**: As a user, I want to set custom download schedules per channel so that I can optimize download timing based on channel activity
- **Value**: Reduces unnecessary system load while ensuring timely updates for active channels
- **Acceptance Criteria**:
  - User can set custom cron schedules per channel (daily, weekly, hourly)
  - Global default schedule applies to channels without custom settings
  - Schedule changes take effect immediately for future downloads
  - Visual schedule indicator shows next expected download time
  - Schedule overrides are clearly marked in channel listings

#### Monitoring & Status  
- **[US-007: Channel Status Dashboard](stories/story-007-channel-status-dashboard.md)** - Centralized channel overview and health monitoring
- **[US-008: Active Download Progress](stories/story-008-active-download-progress.md)** - Real-time download progress and queue status
- **[US-009: Download History View](stories/story-009-download-history-view.md)** - Historical record of completed downloads
- **[US-010: Storage Usage Monitoring](stories/story-010-storage-usage-monitoring.md)** - Storage consumption tracking and alerts
- **[US-011: System Logging Access](stories/story-011-system-logging-access.md)** - Troubleshooting through Docker logs

Each story file contains:
- Detailed acceptance criteria and context
- Engineering tasks broken down by component
- Technical considerations and dependencies  
- Definition of done with quality requirements

### 6. Requirements

#### Functional Requirements (FRs)
- **Channel Management**:
  - Add/remove channels via webUI and YAML configuration
  - Enable/disable channels temporarily without removal
  - Set video download limits per channel (e.g., last 5, 10, 20 videos)
  - Store channel metadata and configuration settings
- **Download Behavior**:
  - Download only the most recent X videos from each channel
  - Skip videos already downloaded (avoid duplicates)
  - Handle first-run scenarios by downloading exactly X most recent videos
  - Maintain consistent file organization for media server compatibility
- **Scheduling & Automation**:
  - Run downloads automatically on configurable schedules
  - Support manual trigger for immediate downloads
  - Process channels sequentially to avoid overload
  - Prevent overlapping download runs
- **Monitoring & Interface**:
  - Display active download progress and status
  - Show download history and recent activity
  - Provide system status overview in webUI
  - Allow configuration management through both webUI and YAML
- **Error Handling**:
  - Continue processing remaining channels if one fails
  - Retry failed downloads on subsequent runs
  - Log errors clearly for troubleshooting

#### Non-Functional Requirements (NFRs)
- **Performance**: Efficient resource usage during idle and download periods
- **Reliability**: Graceful handling of network interruptions and system restarts
- **Usability**: Simple configuration and monitoring through web interface
- **Maintainability**: Clear logging and error reporting for troubleshooting
- **Deployment**: Easy setup and deployment in containerized environment

### 7. User Flows / UX Considerations
- Step-by-step journey, including entry point, core flow, edge cases
- UI/UX highlights, Diagrams, mockups, Figma links, wireframes
- Navigation

### 8. Narrative
This is an app for perhaps a busy dad that just wants to keep a list of the most recent vidoes (20 or 30) of a few YouTube Channels like Mrs. Rachel so that his kids can have something to watch and its not super old stuff.

### 9. Dependencies & Assumptions

#### Dependencies
- **YouTube Platform**: Continued availability and API access for video downloads
- **User Environment**: Docker-capable system with sufficient storage space
- **Network Connectivity**: Reliable internet connection for video downloads
- **User Skills**: Basic familiarity with YAML configuration and docker deployment

#### Assumptions
- **Personal Use**: Application designed for trusted local network environment
- **No Authentication Required**: Single-user or small team usage in controlled environment
- **Storage Management**: User responsible for monitoring and managing disk space
- **Configuration Comfort**: Users comfortable with file-based configuration management

### 10. Success Metrics

#### Functional Success Indicators
- **Download Accuracy**: Successfully downloads only the most recent X videos from configured channels
- **Automation Reliability**: Runs automatically on schedule without manual intervention
- **File Organization**: Maintains proper file structure compatible with media server applications
- **User Visibility**: Provides clear status information about downloads and system health
- **Error Recovery**: Handles failures gracefully and retries on subsequent runs

#### User Experience Success
- **Ease of Setup**: Users can configure and deploy within reasonable time
- **Configuration Simplicity**: Channel management through both webUI and YAML is intuitive
- **Monitoring Clarity**: Download status and history are easily accessible and understandable

### 11. Milestones & Sequencing

#### Phase 1: Core Foundation
- **Scope**: Essential functionality for basic operation
- **Deliverables**:
  - Channel management system (add/remove/configure)
  - Recent video detection algorithm
  - Basic download engine
  - Simple scheduling capability
  - YAML configuration system

#### Phase 2: Production Ready
- **Scope**: Reliability and user interface
- **Deliverables**:
  - Comprehensive error handling and retry logic
  - Web UI for monitoring and management
  - Logging and status reporting
  - Testing with real-world channels
  - Deployment documentation

#### Phase 3: Polish & Enhancement
- **Scope**: User experience improvements
- **Deliverables**:
  - Interface usability improvements
  - Advanced filtering and search capabilities
  - Statistics and reporting features
  - Help documentation and troubleshooting guides

### 12. Open Questions / Risks
- Known unknowns
- Areas that need validation