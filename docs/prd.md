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
- [ ] **US-001**: As a user, I want to add a new channel to monitor so that I start downloading videos from that channel
- [ ] **US-002**: As a user, I want to add a fixed number of videos for a channel in particular to be downloaded so that I do not have too many videos for that particular channel
- [ ] **US-003**: As a user, I want to set the number of videos globally so that I can just add my channel and nothing more
- [ ] **US-004**: As a user, I want to temporarily disable a channel without removing it so that I can pause downloads when needed
- [ ] **US-005**: As a user, I want the system to automatically delete older videos when the configured limit is exceeded so that I only keep the most recent X videos per channel and don't fill up my storage
- [ ] **US-006**: As a user, i want to use a yaml config file to administer the channels I want to download so that it is easy to configure this app
- [ ] **US-007**: As a user, I want to have a webUI so that I can monitor each channel I am monitoring and details of each monitored channel in a simple webUI so I know at a glance what is going on
- [ ] **US-008**: As a user, I want to view in my webUI the active downloads so I know what is currently being download and everything is working
- [ ] **US-009**: As a user, i want to view the most recent downloads so I know what has been downloaded
- [ ] **US-010**: As a user, I want to see storage usage information so that I can manage disk space effectively
- [ ] **US-011**: As a user, I want to view logs in the docker log so I know how to begin debugging if there are issues.

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