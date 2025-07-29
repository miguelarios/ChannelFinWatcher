# US-002: Configure Channel Video Limit

## Story Description

As a user, I want to set how many recent videos to keep per channel so that I control storage usage for each channel individually.

## Context

Different channels have varying content value and storage requirements. Some channels might warrant keeping 50 recent videos while others only need 5. This per-channel customization prevents storage waste while ensuring important content is preserved.

## Value

Prevents storage overflow while allowing per-channel customization based on content importance and viewing patterns.

## Detailed Acceptance Criteria

### Core Functionality
- [ ] User can modify video limit for any existing channel
- [ ] Video limit accepts values between 1-100
- [ ] Changes take effect on the next download cycle
- [ ] Current video limit is always visible in channel list
- [ ] System preserves user-set limits across restarts

### User Interface
- [ ] In-line editing of video limit in channel dashboard
- [ ] Input validation with immediate feedback
- [ ] Clear visual indication when limit is modified
- [ ] Undo capability for accidental changes

### Validation Rules
- [ ] Minimum limit: 1 video
- [ ] Maximum limit: 100 videos
- [ ] Non-numeric values rejected with clear error
- [ ] Zero and negative values prevented

### System Behavior
- [ ] Modified limits apply to future download cycles only
- [ ] Existing videos beyond new limit are not immediately deleted
- [ ] Auto-cleanup respects new limits on next download

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create EditableVideoLimit component with inline editing
- [ ] Implement input validation and error display
- [ ] Add number input controls with min/max constraints
- [ ] Create confirmation dialog for significant limit reductions
- [ ] Add visual feedback for unsaved changes

### Backend (FastAPI)
- [ ] Create PATCH /api/channels/{id}/limit endpoint
- [ ] Add input validation for video limit values
- [ ] Update database record with new limit
- [ ] Sync changes to YAML configuration file
- [ ] Return updated channel data in response

### Database
- [ ] Add video_limit column to channels table with default value
- [ ] Create database constraint for limit range (1-100)
- [ ] Add index on video_limit for efficient queries

## Technical Considerations

### Data Validation
- Use Pydantic models for request validation
- Implement both frontend and backend validation
- Provide consistent error messages across both layers

### Configuration Sync
- Update YAML file when limits change via web UI
- Ensure YAML takes precedence on application restart
- Handle concurrent modifications appropriately

### Performance
- Batch limit updates if user modifies multiple channels
- Avoid unnecessary database queries during editing
- Optimize channel list refresh after changes

## Dependencies

### Prerequisites
- US-001: Add Channel via Web UI (provides channel management foundation)
- Basic channel listing functionality
- Database schema with channels table

### Dependent Stories
- US-005: Automatic Video Cleanup (uses video limits for deletion logic)
- US-003: Global Default Video Limit (provides default values)

## Definition of Done

### Functional Requirements
- [ ] User can modify video limits for any channel through web interface
- [ ] Input validation prevents invalid values (< 1, > 100, non-numeric)
- [ ] Changes are persisted in database and YAML configuration
- [ ] Modified limits take effect on subsequent download cycles

### Technical Requirements
- [ ] API endpoint responds within 1 second for limit updates
- [ ] Input validation works consistently on frontend and backend
- [ ] Database constraints prevent invalid limit values
- [ ] YAML configuration stays synchronized with database changes

### Quality Assurance
- [ ] Test limit modifications with edge values (1, 100, invalid inputs)
- [ ] Verify limits are respected in download logic (integration test)
- [ ] Test concurrent limit modifications from multiple browser tabs
- [ ] Confirm mobile interface usability for limit editing

### Documentation
- [ ] API endpoint documented with validation rules
- [ ] Component props and validation logic documented
- [ ] Configuration file format documented with limit specifications