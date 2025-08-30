# US-004: Toggle Channel Enable/Disable

## Story Description

As a user, I want to temporarily disable a channel without deleting it so that I can pause downloads while keeping the configuration.

## Context

Users may want to temporarily stop downloading from certain channels (vacation, storage constraints, content changes) without losing the channel configuration and download history. This provides flexible control over active monitoring.

## Value

Provides flexible control over which channels are actively monitored while preserving configuration and history.

## Detailed Acceptance Criteria

### Core Functionality
- [ ] User can toggle channel status via web UI toggle switch
- [ ] Disabled channels are skipped during download cycles
- [ ] Disabled channels remain visible in UI with clear visual indication
- [ ] Status change takes effect immediately for future downloads
- [ ] Channel files and download history remain intact when disabled

### User Interface
- [ ] Toggle switch clearly indicates enabled/disabled state
- [ ] Visual distinction between enabled and disabled channels (opacity, color, icon)
- [ ] Toggle state changes immediately upon user interaction
- [ ] Disabled channels show "Paused" or similar status indicator
- [ ] Bulk enable/disable functionality for multiple channels

### System Behavior
- [ ] Download scheduler skips disabled channels entirely
- [ ] Disabled channels do not appear in active download queue
- [ ] Re-enabling channels resumes normal download behavior
- [ ] Channel statistics continue to display when disabled
- [ ] Status persists across application restarts

### Status Indication
- [ ] Clear visual feedback for enabled vs disabled state
- [ ] Last download time preserved while disabled
- [ ] Status visible in channel list and detail views
- [ ] Filter option to show only enabled or disabled channels

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create ChannelToggle component with accessible toggle switch
- [ ] Implement immediate state updates without page refresh
- [ ] Add visual styling for disabled channels (grayed out, etc.)
- [ ] Create bulk actions interface for multiple channel toggles
- [ ] Add confirmation dialog for bulk disable operations

### Backend (FastAPI)
- [ ] Create PATCH /api/channels/{id}/status endpoint
- [ ] Add enabled boolean field to channel model
- [ ] Update download scheduler to filter enabled channels only
- [ ] Sync status changes to YAML configuration file
- [ ] Add bulk status update endpoint for multiple channels

### Database
- [ ] Add enabled boolean column to channels table (default true)
- [ ] Create database index on enabled status for efficient filtering
- [ ] Update existing records to set enabled=true as default

### Download System Integration
- [ ] Modify channel retrieval logic to filter by enabled status
- [ ] Update scheduling logic to skip disabled channels
- [ ] Ensure proper logging when channels are skipped due to disabled status

## Technical Considerations

### State Management
- Ensure toggle state reflects database state accurately
- Handle optimistic updates with fallback on API failures
- Manage loading states during toggle operations

### Performance
- Efficient filtering of enabled channels in download loops
- Minimize database queries when checking channel status
- Cache enabled status for high-frequency operations

### Configuration Sync
- Keep YAML file synchronized with database status changes
- Handle conflicts when YAML manually edited while app running
- Ensure consistent status representation across systems

## Dependencies

### Prerequisites
- US-001: Add Channel via Web UI (provides channel management foundation)
- Channel listing and display functionality
- Download scheduling system

### Dependent Stories
- US-005: Automatic Video Cleanup (respects enabled status)
- US-007: Channel Status Dashboard (displays status information)

## Definition of Done

### Functional Requirements
- [ ] User can toggle channel enabled/disabled status through web interface
- [ ] Disabled channels are excluded from download cycles automatically
- [ ] Channel status is clearly indicated in all UI locations
- [ ] Status changes are persisted in database and YAML configuration

### Technical Requirements
- [ ] Toggle operations complete within 500ms
- [ ] Download scheduler correctly filters enabled channels only
- [ ] Database queries efficiently filter by status using indexes
- [ ] YAML configuration stays synchronized with status changes

### Quality Assurance
- [ ] Test toggle functionality with single and multiple channels
- [ ] Verify disabled channels are skipped during download cycles
- [ ] Test status persistence across application restarts
- [ ] Confirm visual indicators work correctly in all browsers

### User Experience
- [ ] Toggle controls are intuitive and accessible
- [ ] Visual feedback clearly distinguishes enabled/disabled states
- [ ] Bulk operations provide appropriate confirmation dialogs
- [ ] Status changes provide immediate visual feedback

### Documentation
- [ ] API endpoints documented with status toggle examples
- [ ] UI component usage documented for developers
- [ ] Configuration file format includes enabled/disabled syntax