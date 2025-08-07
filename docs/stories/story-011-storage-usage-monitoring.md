# US-010: Storage Usage Monitoring

## Story Description

As a user, I want to see current storage usage by channel so that I can make informed decisions about video limits and cleanup.

## Context

Storage management is critical for long-term system operation. Users need visibility into how much disk space each channel consumes, total usage, and remaining capacity to make informed decisions about video limits and identify storage-heavy channels.

## Value

Prevents storage issues and helps optimize disk space allocation by providing clear visibility into storage consumption patterns.

## Detailed Acceptance Criteria

### Core Storage Display
- [ ] Shows total storage used by all channels
- [ ] Displays storage breakdown by individual channel
- [ ] Shows available disk space remaining on the system
- [ ] Updates storage information every 5 minutes automatically
- [ ] Provides visual warnings when storage exceeds 80% capacity

### Channel Storage Breakdown
- [ ] Storage usage per channel in GB/MB with percentage
- [ ] Average file size per video for each channel
- [ ] Number of videos vs storage consumed ratio
- [ ] Storage trend over time (increasing/decreasing)
- [ ] Largest channels highlighted for attention

### System Storage Overview
- [ ] Total disk space and available space
- [ ] Storage usage trend (daily/weekly growth)
- [ ] Projected time until disk full at current rate
- [ ] Storage efficiency metrics (videos per GB)
- [ ] Critical storage warnings and recommendations

### Visual Representations
- [ ] Pie chart showing storage by channel
- [ ] Progress bars for individual channel usage
- [ ] Storage capacity gauge for overall system
- [ ] Color coding for storage levels (green/yellow/red)
- [ ] Responsive charts for mobile viewing

### Interactive Features
- [ ] Click channel to see detailed storage breakdown
- [ ] Sort channels by storage usage (highest first)
- [ ] Filter out disabled channels from storage calculations
- [ ] Export storage report for external analysis
- [ ] Quick actions to adjust video limits based on storage

## Engineering Tasks

### Frontend (NextJS)
- [ ] Create StorageMonitoring component with charts and gauges
- [ ] Implement ChannelStorageBreakdown component
- [ ] Add interactive charts using charting library (Chart.js or similar)
- [ ] Create storage warning components and notifications
- [ ] Add responsive design for storage visualizations
- [ ] Implement auto-refresh for storage data

### Backend (FastAPI)
- [ ] Create GET /api/storage/overview endpoint
- [ ] Create GET /api/storage/channels endpoint for per-channel breakdown
- [ ] Implement disk space calculation utilities
- [ ] Add storage trend calculation and projections
- [ ] Create storage warning threshold detection
- [ ] Add caching for expensive storage calculations

### Storage Calculation System
- [ ] Implement recursive directory size calculation
- [ ] Add file system monitoring for real-time usage
- [ ] Calculate storage per channel accurately
- [ ] Track storage changes over time for trends
- [ ] Handle symbolic links and junction points correctly

### Database Integration
- [ ] Create storage_snapshots table for historical tracking
- [ ] Add storage metrics to channel records
- [ ] Implement periodic storage data collection
- [ ] Store storage warnings and threshold breaches
- [ ] Add indexes for efficient storage queries

### Caching and Performance
- [ ] Cache storage calculations to avoid expensive file system operations
- [ ] Implement incremental storage updates
- [ ] Use background tasks for storage scanning
- [ ] Optimize file system access patterns
- [ ] Add storage calculation scheduling

## Technical Considerations

### File System Performance
- Minimize file system traversal frequency
- Use efficient directory scanning techniques
- Cache results appropriately to avoid repeated calculations
- Handle large directory structures without blocking UI

### Accuracy vs Performance
- Balance between storage accuracy and calculation speed
- Implement smart caching strategies
- Use file system events to trigger recalculations
- Provide "last updated" timestamps for transparency

### Cross-Platform Compatibility
- Handle different file systems (NTFS, ext4, APFS, etc.)
- Account for file system overhead and metadata
- Handle permissions and access issues gracefully
- Ensure accurate disk space reporting across platforms

### Real-time Updates
- Implement efficient storage change detection
- Use WebSocket for real-time storage warnings
- Update storage displays without full page refresh
- Handle storage changes during active downloads

## Dependencies

### Prerequisites
- File system access to media directories
- Channel management system for per-channel calculations
- Real-time update infrastructure (WebSocket)
- Charting library integration

### Related Stories
- US-005: Automatic Video Cleanup (uses storage info for cleanup decisions)
- US-002: Configure Channel Video Limit (informed by storage usage)
- US-007: Channel Status Dashboard (may include basic storage info)

## Definition of Done

### Functional Requirements
- [ ] Storage usage displayed accurately for system and per-channel
- [ ] Automatic updates every 5 minutes without user intervention
- [ ] Visual warnings appear when storage exceeds 80% capacity
- [ ] Storage trend information helps with capacity planning

### Technical Requirements
- [ ] Storage calculations complete within 30 seconds for typical installations
- [ ] Real-time updates work without significant performance impact
- [ ] Caching reduces file system operations appropriately
- [ ] Cross-platform compatibility verified on target systems

### Quality Assurance
- [ ] Test storage calculations with various directory structures
- [ ] Verify accuracy by comparing with system tools (du, dir)
- [ ] Test warning thresholds with simulated storage conditions
- [ ] Confirm mobile responsiveness for storage charts

### User Experience
- [ ] Storage information is clear and actionable
- [ ] Visual representations help identify storage issues quickly
- [ ] Warnings provide specific recommendations for action
- [ ] Interactive features help users manage storage effectively

### Documentation
- [ ] Storage calculation methods documented
- [ ] API endpoints documented with response formats
- [ ] Storage warning thresholds and meanings documented
- [ ] Troubleshooting guide for storage calculation issues