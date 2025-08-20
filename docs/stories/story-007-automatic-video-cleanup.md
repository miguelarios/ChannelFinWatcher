# US-005: Automatic Video Cleanup

## Story Description

As a user, I want old videos automatically deleted when channel limits are exceeded so that my storage doesn't fill up.

## Context

This is a critical storage management feature that maintains the "recent videos only" principle. When new videos are downloaded and exceed the configured limit, the system should automatically remove the oldest videos to stay within the limit.

## Value

Maintains storage efficiency without manual intervention, ensuring users always have the most recent content without storage concerns.

## Detailed Acceptance Criteria

### Core Functionality
- [ ] System automatically deletes oldest videos when channel limit is exceeded
- [ ] Deletion occurs after successful new video downloads
- [ ] Process preserves the most recent X videos as configured per channel
- [ ] Cleanup respects per-channel video limits (not global)
- [ ] Only enabled channels participate in cleanup process

### Cleanup Logic
- [ ] Videos sorted by upload date (oldest first) for deletion
- [ ] Entire video folders removed (video file, metadata, thumbnails)
- [ ] Process handles partial downloads and corrupted files gracefully
- [ ] Cleanup logs detail which videos were removed and why
- [ ] Failed deletions are logged but don't stop the process

### Safety Measures
- [ ] Cleanup only runs after successful new downloads
- [ ] Minimum of 1 video always preserved per channel
- [ ] Confirmation that files exist before attempting deletion
- [ ] Atomic operations to prevent partial cleanup states
- [ ] Rollback capability if cleanup fails mid-process

### Monitoring and Logging
- [ ] Cleanup activity visible in download logs
- [ ] Storage space freed reported after cleanup
- [ ] Failed deletions logged with error details
- [ ] Cleanup statistics available in web interface

## Engineering Tasks

### Backend Core Logic
- [ ] Create VideoCleanupService with cleanup orchestration
- [ ] Implement video discovery and sorting by upload date
- [ ] Add safe file deletion with verification
- [ ] Create cleanup transaction management for rollback
- [ ] Add comprehensive error handling and logging

### Database Integration
- [ ] Update download records when videos are cleaned up
- [ ] Track cleanup history for auditing purposes
- [ ] Maintain referential integrity between channels and downloads
- [ ] Add cleanup_history table for audit trail

### File System Operations
- [ ] Implement safe recursive directory deletion
- [ ] Verify file/directory existence before deletion
- [ ] Handle permission errors and disk space issues
- [ ] Cleanup empty parent directories after video removal

### Integration with Download System
- [ ] Trigger cleanup after successful channel downloads
- [ ] Pass channel configuration to cleanup service
- [ ] Integrate cleanup into download workflow
- [ ] Handle cleanup failures gracefully without stopping downloads

### Monitoring and Reporting
- [ ] Add cleanup metrics to system status
- [ ] Create cleanup summary for web interface
- [ ] Log cleanup operations with sufficient detail
- [ ] Track storage space freed by cleanup operations

## Technical Considerations

### File System Safety
- Use absolute paths to prevent accidental deletions
- Verify file ownership before deletion
- Handle concurrent access during cleanup
- Implement proper error recovery for failed operations

### Performance
- Minimize disk I/O during video discovery
- Batch file operations where possible
- Avoid cleanup during active downloads
- Optimize directory scanning for large video collections

### Error Handling
- Continue cleanup even if individual files fail to delete
- Log detailed error information for troubleshooting
- Implement retry logic for transient failures
- Provide recovery mechanisms for partial cleanup states

## Dependencies

### Prerequisites
- US-002: Configure Channel Video Limit (provides cleanup thresholds)
- US-004: Toggle Channel Enable/Disable (determines eligible channels)
- Download system with video organization structure
- File system access with appropriate permissions

### Dependent Stories
- US-010: Storage Usage Monitoring (reports cleanup effectiveness)
- US-011: System Logging Access (provides cleanup audit trail)

## Definition of Done

### Functional Requirements
- [ ] Videos are automatically deleted when channel limits exceeded
- [ ] Cleanup preserves most recent videos according to configured limits
- [ ] Process handles errors gracefully without data corruption
- [ ] Cleanup activity is properly logged and auditable

### Technical Requirements
- [ ] Cleanup completes within 30 seconds for typical channel sizes
- [ ] File deletion operations are atomic and safe
- [ ] Database consistency maintained during cleanup operations
- [ ] Error recovery handles all failure scenarios

### Quality Assurance
- [ ] Test cleanup with various video limit configurations
- [ ] Verify correct video ordering (oldest deleted first)
- [ ] Test error scenarios (permission issues, disk full, corrupted files)
- [ ] Confirm cleanup statistics accuracy

### Safety and Reliability
- [ ] No accidental deletion of wrong files or directories
- [ ] Proper error handling prevents data corruption
- [ ] Cleanup logs provide sufficient audit trail
- [ ] Recovery procedures documented for cleanup failures

### Documentation
- [ ] Cleanup logic and safety measures documented
- [ ] File system requirements and permissions documented
- [ ] Error codes and recovery procedures documented
- [ ] Cleanup configuration options explained