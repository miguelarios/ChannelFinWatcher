# US-003: Set Global Default Video Limit

## Story Description

As a user, I want to configure a default video limit that applies to new channels so that I don't have to set limits individually each time.

## Context

Users typically have a preferred number of videos to keep across most channels. Setting a global default eliminates repetitive configuration while still allowing per-channel customization when needed.

## Value

Streamlines channel addition process with sensible defaults, reducing configuration overhead for users.

## Detailed Acceptance Criteria

### Core Functionality
- [ ] User can set global default video limit in application settings
- [ ] Default limit accepts values between 1-100 videos
- [ ] New channels automatically receive the configured default limit
- [ ] Existing channels remain unchanged when default is modified
- [ ] Default setting persists across application restarts

### Settings Interface
- [ ] Global default accessible through settings page/modal
- [ ] Current default value clearly displayed
- [ ] Input validation with immediate feedback
- [ ] Save confirmation with success message

### Default Application
- [ ] New channels use global default at creation time
- [ ] Manual channel additions via web UI apply default
- [ ] YAML-configured channels without explicit limits use default
- [ ] Default is applied before channel appears in monitoring list

### System Behavior
- [ ] Default value initialized to 10 videos on first run
- [ ] Setting changes do not affect existing channels
- [ ] Default persists in both database and YAML configuration

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create GlobalSettings component with default limit configuration
- [ ] Add settings page/modal accessible from navigation
- [ ] Implement number input with validation for default limit
- [ ] Display current default value in channel addition forms
- [ ] Add visual indication when using default vs custom limits

### Backend (FastAPI)
- [ ] Create GET/PUT /api/settings/default-video-limit endpoints
- [ ] Add application settings table/configuration storage
- [ ] Update channel creation logic to apply default limit
- [ ] Sync default setting to YAML configuration
- [ ] Add migration to set initial default value

### Database
- [ ] Create application_settings table for global configuration
- [ ] Add default_video_limit setting with initial value of 10
- [ ] Modify channel creation to reference default setting
- [ ] Add constraint validation for default limit range

## Technical Considerations

### Configuration Management
- Store global settings in separate database table
- Sync settings between database and YAML configuration
- Handle settings initialization on first application run

### Channel Creation Integration
- Modify channel creation flow to check for default limit
- Ensure consistent application across web UI and YAML imports
- Provide clear indication when default is being used

### Backward Compatibility
- Handle existing installations without breaking changes
- Migrate existing channels to maintain current behavior
- Set sensible default for new installations

## Dependencies

### Prerequisites
- Basic application settings infrastructure
- Channel creation workflow established
- Database schema for configuration storage

### Dependent Stories
- US-001: Add Channel via Web UI (applies default limit during creation)
- US-002: Configure Channel Video Limit (uses default as starting point)

### Related Stories
- US-006: YAML Configuration Management (synchronizes default settings)

## Definition of Done

### Functional Requirements
- [ ] User can configure global default video limit through settings interface
- [ ] Default limit is applied to all new channels automatically
- [ ] Existing channels are unaffected by default limit changes
- [ ] Default setting persists across application restarts and deployments

### Technical Requirements
- [ ] Settings API endpoints respond within 1 second
- [ ] Default limit validation matches individual channel validation (1-100)
- [ ] Database migration handles existing installations gracefully
- [ ] YAML configuration includes and respects default setting

### Quality Assurance
- [ ] Test default application during channel creation via web UI
- [ ] Verify existing channels unchanged when default is modified
- [ ] Test settings persistence across application restart
- [ ] Validate edge cases (minimum/maximum default values)

### User Experience
- [ ] Settings interface is intuitive and discoverable
- [ ] Clear indication when channels are using default vs custom limits
- [ ] Success feedback when default setting is saved
- [ ] Helpful tooltips explaining default limit behavior

### Documentation
- [ ] Settings API endpoints documented with examples
- [ ] Configuration file format includes default limit documentation
- [ ] User guide explains default limit concept and usage