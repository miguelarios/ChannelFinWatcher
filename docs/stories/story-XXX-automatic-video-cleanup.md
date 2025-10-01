# User Story: Automatic Video Cleanup

## Section 1: Story Definition

### Feature
Automatic deletion of oldest videos when channel limits are exceeded to maintain storage efficiency

### User Story
- **As a** user
- **I want** old videos automatically deleted when channel limits are exceeded
- **So that** my storage doesn't fill up

### Context
This is a critical storage management feature that maintains the "recent videos only" principle. When new videos are downloaded and exceed the configured limit, the system should automatically remove the oldest videos to stay within the limit.

### Functional Requirements

#### [ ] Scenario: Automatic cleanup after successful downloads - Happy Path
- **Given** a channel has 10 videos and is configured for maximum 5 videos
  - And new videos are available for download
  - And the download process completes successfully
- **When** the cleanup process runs
  - And videos are sorted by upload date (oldest first)
- **Then** the 6 oldest videos should be deleted
  - And exactly 5 most recent videos should remain
  - But minimum of 1 video is always preserved per channel

#### [ ] Scenario: Cleanup with partial downloads and corrupted files
- **Given** a channel contains some corrupted or partially downloaded videos
- **When** the cleanup process encounters these files
- **Then** corrupted files should be handled gracefully and removed
  - And the cleanup process should continue with remaining files

#### [ ] Scenario: Cleanup failure scenarios
- **Given** cleanup process encounters permission errors or disk space issues
- **When** individual file deletions fail
- **Then** failed deletions should be logged with error details
  - And cleanup should continue with remaining files
  - But rollback capability should be available if cleanup fails mid-process

### Non-functional Requirements
- **Performance:** Cleanup completes within 30 seconds for typical channel sizes
- **Security:** Use absolute paths to prevent accidental deletions, verify file ownership before deletion
- **Reliability:** Atomic operations to prevent partial cleanup states, comprehensive error handling and logging
- **Usability:** Cleanup activity visible in download logs, cleanup statistics available in web interface

### Dependencies
- **Blocked by:** US-002: Configure Channel Video Limit (provides cleanup thresholds), US-004: Toggle Channel Enable/Disable (determines eligible channels)
- **Blocks:** US-010: Storage Usage Monitoring (reports cleanup effectiveness), US-011: System Logging Access (provides cleanup audit trail)

### Engineering TODOs
- [ ] Research safe file deletion patterns and atomic operations
- [ ] Investigate rollback mechanisms for failed cleanup operations
- [ ] Determine optimal video discovery and sorting algorithms for large collections

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*
*Note: Not all task categories will be applicable to every story*

#### 1. [ ] Create VideoCleanupService - Backend Work
- **Description:** Core cleanup orchestration service with video discovery and sorting by upload date
- **Estimation:** 4-6 hours
- **Acceptance Criteria:** 
  - [ ] VideoCleanupService implements cleanup orchestration logic
  - [ ] Video discovery and sorting by upload date functionality
  - [ ] Safe file deletion with verification before deletion

#### 2. [ ] Database Integration - Database Work
- **Description:** Update download records, track cleanup history, maintain referential integrity
- **Estimation:** 3-4 hours
- **Acceptance Criteria:** 
  - [ ] Download records updated when videos are cleaned up
  - [ ] Cleanup history tracked for auditing purposes
  - [ ] Add cleanup_history table for audit trail

#### 3. [ ] File System Operations - Backend Work
- **Description:** Safe recursive directory deletion with error handling
- **Estimation:** 4-5 hours
- **Acceptance Criteria:** 
  - [ ] Safe recursive directory deletion implemented
  - [ ] File/directory existence verification before deletion
  - [ ] Handle permission errors and disk space issues gracefully

#### 4. [ ] Integration with Download System - Integration Work
- **Description:** Trigger cleanup after successful downloads, integrate into download workflow
- **Estimation:** 3-4 hours
- **Acceptance Criteria:** 
  - [ ] Cleanup triggered after successful channel downloads
  - [ ] Channel configuration passed to cleanup service
  - [ ] Cleanup failures handled gracefully without stopping downloads

#### 5. [ ] Cleanup Testing - Testing Work
- **Description:** Comprehensive testing of cleanup scenarios including edge cases and error conditions
- **Estimation:** 4-5 hours
- **Acceptance Criteria:** 
  - [ ] Test cleanup with various video limit configurations
  - [ ] Test error scenarios (permission issues, disk full, corrupted files)
  - [ ] Verify correct video ordering (oldest deleted first)

#### 6. [ ] Monitoring and Logging - Backend Work
- **Description:** Add cleanup metrics, logging, and web interface reporting
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] Cleanup metrics added to system status
  - [ ] Detailed cleanup operation logging
  - [ ] Storage space freed tracking and reporting

---

## Definition of Done

### Must Have
- [ ] Videos are automatically deleted when channel limits exceeded
- [ ] Cleanup preserves most recent videos according to configured limits
- [ ] Process handles errors gracefully without data corruption

### Should Have  
- [ ] Cleanup completes within 30 seconds for typical channel sizes
- [ ] File deletion operations are atomic and safe
- [ ] Cleanup activity is properly logged and auditable

### Notes for Future
Potential optimizations: batch file operations, minimize disk I/O during video discovery, optimize directory scanning for large video collections. Consider implementing cleanup scheduling to avoid conflicts with active downloads.

---

## Reference Materials

*Include any code, configurations, or research needed for Claude Code to implement this story without looking elsewhere.*

### Core Functional Requirements
- System automatically deletes oldest videos when channel limit is exceeded
- Deletion occurs after successful new video downloads
- Process preserves the most recent X videos as configured per channel
- Cleanup respects per-channel video limits (not global)
- Only enabled channels participate in cleanup process

### Cleanup Logic Requirements
- Videos sorted by upload date (oldest first) for deletion
- Entire video folders removed (video file, metadata, thumbnails)
- Process handles partial downloads and corrupted files gracefully
- Cleanup logs detail which videos were removed and why
- Failed deletions are logged but don't stop the process

### Safety Measures
- Cleanup only runs after successful new downloads
- Minimum of 1 video always preserved per channel
- Confirmation that files exist before attempting deletion
- Atomic operations to prevent partial cleanup states
- Rollback capability if cleanup fails mid-process

### File System Safety Guidelines
```bash
# Use absolute paths to prevent accidental deletions
# Verify file ownership before deletion
# Handle concurrent access during cleanup
# Implement proper error recovery for failed operations
```

### Performance Considerations
- Minimize disk I/O during video discovery
- Batch file operations where possible
- Avoid cleanup during active downloads
- Optimize directory scanning for large video collections

### Error Handling Requirements
- Continue cleanup even if individual files fail to delete
- Log detailed error information for troubleshooting
- Implement retry logic for transient failures
- Provide recovery mechanisms for partial cleanup states