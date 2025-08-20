# US-008: Active Download Progress

## Story Description

As a user, I want to see real-time progress of currently downloading videos so that I know the system is working and can estimate completion time.

## Context

Download progress visibility is crucial for user confidence and system transparency. Users need to know when downloads are active, which videos are being processed, and how long until completion. This is especially important for long-running downloads.

## Value

Provides confidence that downloads are progressing and enables monitoring of system activity with realistic completion expectations.

## Detailed Acceptance Criteria

### Core Progress Display
- [ ] Shows currently active downloads with channel name, video title, and progress percentage
- [ ] Progress updates in real-time without page refresh (WebSocket integration)
- [ ] Displays estimated time remaining for each download
- [ ] Shows "No active downloads" message when system is idle
- [ ] Maximum 3-second delay between progress updates

### Download Information
- [ ] Video title truncated appropriately for display
- [ ] Channel name clearly associated with each download
- [ ] File size information (downloaded/total)
- [ ] Download speed (MB/s or KB/s)
- [ ] Queue position for pending downloads

### Visual Design
- [ ] Progress bars with smooth animations
- [ ] Clear visual hierarchy for multiple simultaneous downloads
- [ ] Color coding for different download states (active, pending, completing)
- [ ] Responsive design for mobile viewing
- [ ] Loading indicators during progress updates

### Real-time Features
- [ ] Live progress updates via WebSocket connection
- [ ] Automatic removal of completed downloads from active view
- [ ] Queue updates when new downloads begin
- [ ] Connection status indicator for WebSocket health
- [ ] Graceful fallback to periodic polling if WebSocket fails

### Queue Management Display
- [ ] Show upcoming downloads in queue with position
- [ ] Estimated start time for queued downloads
- [ ] Ability to see total queue length
- [ ] Clear distinction between active and queued downloads

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create ActiveDownloads component with real-time updates
- [ ] Implement WebSocket client for progress subscriptions
- [ ] Design DownloadProgressBar component with smooth animations
- [ ] Add queue display component for pending downloads
- [ ] Create fallback polling mechanism for WebSocket failures
- [ ] Implement connection status indicators

### Backend (FastAPI)
- [ ] Create WebSocket endpoint for download progress streaming
- [ ] Integrate with yt-dlp progress hooks for real-time data
- [ ] Implement download queue management system
- [ ] Add progress tracking storage (in-memory with persistence)
- [ ] Create RESTful endpoint as WebSocket fallback

### Download System Integration
- [ ] Modify download engine to report progress events
- [ ] Add progress hooks to yt-dlp integration
- [ ] Implement download queue with status tracking
- [ ] Add estimated time calculation based on download speed
- [ ] Create download session management

### WebSocket Infrastructure
- [ ] Set up WebSocket connection management
- [ ] Implement client reconnection logic
- [ ] Add authentication/authorization for WebSocket connections
- [ ] Handle connection cleanup when downloads complete
- [ ] Add WebSocket health monitoring

### Progress Calculation
- [ ] Parse yt-dlp progress information accurately
- [ ] Calculate download speed and ETA
- [ ] Handle variable file sizes and multiple format downloads
- [ ] Smooth progress reporting to avoid UI jitter

## Technical Considerations

### Real-time Performance
- Optimize WebSocket message frequency to balance responsiveness and performance
- Implement message throttling to prevent UI overwhelming
- Use efficient data structures for progress tracking
- Minimize memory usage for long-running downloads

### Connection Reliability
- Handle WebSocket disconnections gracefully
- Implement automatic reconnection with exponential backoff
- Provide visual feedback for connection issues
- Maintain progress state during temporary disconnections

### Download Integration
- Hook into yt-dlp progress callbacks without performance impact
- Track progress across multiple simultaneous downloads
- Handle download failures and error states appropriately
- Coordinate with existing download scheduler

### Error Handling
- Display meaningful error messages for failed downloads
- Handle network interruptions during progress reporting
- Recover gracefully from corrupted progress data
- Provide user actions for stuck or failed downloads

## Dependencies

### Prerequisites
- Download system with yt-dlp integration
- WebSocket infrastructure setup
- Real-time messaging capabilities
- Download queue management system

### Related Stories
- US-007: Channel Status Dashboard (may show download activity)
- US-009: Download History View (receives completed downloads)
- US-011: System Logging Access (logs download progress events)

## Definition of Done

### Functional Requirements
- [ ] Real-time progress displayed for all active downloads
- [ ] Progress updates occur within 3-second maximum delay
- [ ] Estimated completion times are reasonably accurate
- [ ] Queue status shows pending downloads clearly

### Technical Requirements
- [ ] WebSocket connections maintain stability during long downloads
- [ ] Progress tracking integrates seamlessly with yt-dlp
- [ ] System performance remains stable with multiple simultaneous downloads
- [ ] Fallback mechanism works when WebSocket unavailable

### Quality Assurance
- [ ] Test progress display with various download sizes and speeds
- [ ] Verify real-time updates work consistently across browsers
- [ ] Test WebSocket reconnection scenarios
- [ ] Confirm mobile interface shows progress appropriately

### User Experience
- [ ] Progress information is clear and informative
- [ ] Visual design handles multiple downloads without clutter
- [ ] Loading states provide appropriate feedback
- [ ] Error states are communicated clearly to users

### Documentation
- [ ] WebSocket API documented with message formats
- [ ] Progress calculation methods documented
- [ ] Integration points with download system documented
- [ ] Troubleshooting guide for progress display issues