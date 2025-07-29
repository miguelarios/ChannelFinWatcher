# US-007: Channel Status Dashboard

## Story Description

As a user, I want to view all monitored channels with their current status so that I can see which channels are active and their basic information at a glance.

## Context

The dashboard serves as the primary interface for monitoring channel health and activity. Users need to quickly assess which channels are functioning properly, when they were last checked, and identify any issues requiring attention.

## Value

Provides centralized overview of all channels and their health, enabling quick identification of issues and system status.

## Detailed Acceptance Criteria

### Core Display Features
- [ ] Dashboard shows all configured channels in organized list/grid view
- [ ] Each channel displays name, URL, status (enabled/disabled), video limit, and last check time
- [ ] Visual indicators clearly distinguish enabled vs disabled channels
- [ ] Channels sorted by most recently checked first
- [ ] Page loads in under 2 seconds with up to 50 channels

### Channel Information Display
- [ ] Channel name with fallback to URL if name unavailable
- [ ] Current video count vs configured limit (e.g., "8/10 videos")
- [ ] Last successful download timestamp
- [ ] Next scheduled check time
- [ ] Channel thumbnail/avatar when available

### Visual Design Elements
- [ ] Card-based layout for easy scanning
- [ ] Color coding for channel status (green=active, red=error, gray=disabled)
- [ ] Progress indicators for channels currently being processed
- [ ] Responsive design working on mobile and desktop
- [ ] Clear typography and accessible color contrast

### Interactive Features
- [ ] Click channel to view detailed information
- [ ] Quick actions available (enable/disable, edit limit)
- [ ] Bulk selection for mass operations
- [ ] Search/filter functionality for large channel lists
- [ ] Refresh button for manual status updates

### Status Indicators
- [ ] Last check time with relative formatting ("2 hours ago")
- [ ] Error indicators for channels with download failures
- [ ] "Never checked" status for newly added channels
- [ ] Download in progress indicator with spinner/progress bar

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create ChannelDashboard main component
- [ ] Design ChannelCard component for individual channel display
- [ ] Implement responsive grid/list layout
- [ ] Add loading states and skeleton components
- [ ] Create filtering and search functionality
- [ ] Add bulk selection and action controls

### Backend (FastAPI)
- [ ] Create GET /api/channels/dashboard endpoint
- [ ] Aggregate channel data with status information
- [ ] Include last check times and download statistics
- [ ] Add channel thumbnail URL extraction
- [ ] Implement pagination for large channel lists

### Data Aggregation
- [ ] Join channels with latest download status
- [ ] Calculate video counts per channel
- [ ] Determine next scheduled check times
- [ ] Aggregate error information for status display
- [ ] Format timestamps for consistent display

### Real-time Updates
- [ ] WebSocket integration for live status updates
- [ ] Auto-refresh channel information every 30 seconds
- [ ] Push notifications for status changes
- [ ] Update individual channel cards without full refresh

## Technical Considerations

### Performance Optimization
- Implement virtual scrolling for large channel lists
- Cache channel thumbnails and metadata
- Use pagination or lazy loading for scalability
- Optimize database queries with proper indexing

### Data Freshness
- Balance between real-time updates and system performance
- Implement efficient change detection for selective updates
- Handle stale data gracefully with appropriate indicators

### User Experience
- Ensure dashboard remains responsive during data loading
- Provide meaningful loading states and error messages
- Implement optimistic updates for user actions
- Maintain scroll position during automatic refreshes

## Dependencies

### Prerequisites
- US-001: Add Channel via Web UI (provides channel data)
- US-004: Toggle Channel Enable/Disable (provides status information)
- Basic routing and navigation structure
- WebSocket infrastructure for real-time updates

### Related Stories
- US-008: Active Download Progress (integrates download status)
- US-010: Storage Usage Monitoring (may include storage info per channel)

## Definition of Done

### Functional Requirements
- [ ] Dashboard displays all channels with essential information
- [ ] Visual indicators clearly show channel status and health
- [ ] Page performance meets 2-second load time requirement
- [ ] Interactive features work reliably across browsers

### Technical Requirements
- [ ] API endpoint efficiently aggregates channel data
- [ ] Real-time updates work without performance degradation
- [ ] Responsive design functions properly on mobile devices
- [ ] Database queries optimized for dashboard data retrieval

### Quality Assurance
- [ ] Test dashboard with various channel counts (1, 10, 50+ channels)
- [ ] Verify visual indicators accurately reflect channel status
- [ ] Test real-time updates during active download operations
- [ ] Confirm mobile responsiveness and touch interactions

### User Experience
- [ ] Dashboard provides clear overview without information overload
- [ ] Status indicators are intuitive and don't require explanation
- [ ] Quick actions are easily discoverable and functional
- [ ] Search and filtering help users manage large channel lists

### Documentation
- [ ] Dashboard component architecture documented
- [ ] API endpoint response format documented
- [ ] Status indicator meanings documented for users
- [ ] Performance considerations documented for developers