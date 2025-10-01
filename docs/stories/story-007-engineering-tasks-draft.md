## Section 2: Engineering Tasks

### Task Breakdown
*Each task follows INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

---

### **LAYER 1: DATABASE FOUNDATION**

#### 1. ✅ [DB-001] Add Scheduler Configuration Keys to ApplicationSettings
- **Description:** Initialize the 5 required scheduler configuration keys in ApplicationSettings table with default values. This provides the data foundation for all scheduler functionality without requiring schema changes.
- **Estimation:** 2-4 hours
- **Dependencies:** ApplicationSettings model with proper indexes, Alembic migration infrastructure configured
- **Acceptance Criteria:**
  - [x] `cron_schedule` key created with default value `"0 0 * * *"` (daily at midnight)
  - [x] `scheduler_enabled` key created with default value `"true"`
  - [x] `scheduler_running` key created with default value `"false"`
  - [x] `scheduler_last_run` key created with default value `NULL`
  - [x] `scheduler_next_run` key created with default value `NULL`
  - [x] All keys have descriptive `description` field populated
  - [x] Database query confirms all 5 keys exist after initialization
  - [x] Settings can be queried via existing ApplicationSettings API
  - [x] **Database Initialization:**
    - [x] Database migration script created in `backend/alembic/versions/d4e9f5a6b7c8_add_scheduler_settings.py`
    - [x] Migration uses `INSERT OR IGNORE` to prevent duplicate key errors on re-run
    - [x] Migration includes `downgrade()` function for rollback
    - [x] Migration tested on existing database with channels (upgrade scenario)
    - [x] Rollback migration tested and confirmed working
    - [ ] Migration tested on empty database (fresh install scenario) - deferred to integration testing
    - [ ] Migration documented in `docs/database-migrations.md` with version number - deferred
    - [ ] ApplicationSettings query performance verified (<1ms for scheduler keys) - deferred to performance testing
  - [ ] **Default Value Validation:**
    - [ ] Default cron_schedule `"0 0 * * *"` validated using APScheduler `CronTrigger.from_crontab()` - will be validated in BE-002
    - [ ] Unit test confirms default schedule is parseable and generates valid next_run times - will be tested in TEST-001
    - [ ] Database constraint prevents NULL values for `scheduler_enabled` (must be "true" or "false") - not applicable (TEXT column allows NULL, validation at application layer)

---

### **LAYER 2: CORE BACKEND SERVICES**

#### 2. ✅ [BE-001] Implement SchedulerService with SQLite Persistence
- **Description:** Create production-ready `scheduler_service.py` implementing the SchedulerService class with APScheduler, SQLite job store, and Docker persistence. This is the core scheduler infrastructure that manages all scheduled jobs and survives container restarts.
- **Estimation:** 1-2 days
- **Dependencies:** Task 1 (DB-001)
- **Reference:** Lines 1463-1634 in Reference Materials
- **Acceptance Criteria:**
  - [ ] SchedulerService class created in `backend/app/scheduler_service.py`
  - [ ] SQLAlchemyJobStore configured with `sqlite:///data/scheduler_jobs.db`
  - [ ] AsyncIOScheduler configured with UTC timezone
  - [ ] Job defaults set: `coalesce=True`, `max_instances=1`, `misfire_grace_time=300`
  - [ ] `start()` method loads cron schedule from ApplicationSettings on startup
  - [ ] `shutdown()` method gracefully stops scheduler with `wait=True`
  - [ ] `update_download_schedule(cron_expression)` method adds/updates main download job
  - [ ] `get_schedule_status()` method returns current scheduler state and job info
  - [ ] Event listeners log job execution success/failure events
  - [ ] Scheduler recovers persisted jobs after Docker container restart
  - [ ] Unit tests verify scheduler initialization and job management

#### 3. ✅ [BE-002] Implement Cron Expression Validation Utilities
- **Description:** Create `cron_validation.py` with production-ready cron validation using APScheduler's native CronTrigger. Includes input sanitization, next run calculation, and human-readable formatting. No external dependencies needed - APScheduler handles everything.
- **Estimation:** 1 day
- **Dependencies:** None (independent utility module)
- **Reference:** Lines 1637-1751 in Reference Materials
- **Acceptance Criteria:**
  - [x] `validate_cron_expression(cron_expr)` function returns `(is_valid, error_message, trigger)`
  - [x] Input sanitization using regex `[^0-9\s,\-\*/]` applied before validation
  - [x] APScheduler CronTrigger.from_crontab() used for native validation
  - [x] Minimum 5-minute interval enforced (reject `*/1` and `*` minute patterns)
  - [x] Clear error messages returned for all invalid expression types
  - [x] `calculate_next_runs(cron_expr, count=5)` returns list of next N datetime objects
  - [x] `get_cron_schedule_info(cron_expr)` returns comprehensive dict with next_run, next_5_runs, time_until_next
  - [x] `_describe_cron_schedule(cron_expr)` converts common patterns to human-readable strings
  - [x] Manual tests verify 6+ valid expressions accept correctly
  - [x] Manual tests verify 9 invalid expressions reject with clear messages
  - [x] Security tests confirm 4 injection attempts blocked (SQL, XSS, command, variable)
  - [x] Default database cron_schedule "0 0 * * *" validated successfully
  - [ ] Unit tests (formal test suite) - deferred to TEST-001

#### 4. ✅ [BE-003] Implement Overlap Prevention Mechanism
- **Description:** Create `overlap_prevention.py` with context manager for database flag-based job locking. Prevents concurrent scheduler executions using ApplicationSettings flags with automatic cleanup and error recovery.
- **Estimation:** 1 day
- **Dependencies:** Task 1 (DB-001)
- **Reference:** Lines 1753-1879 in Reference Materials
- **Acceptance Criteria:**
  - [ ] `scheduler_lock(db, job_name)` context manager created
  - [ ] Context manager checks `{job_name}_running` flag before acquiring lock
  - [ ] JobAlreadyRunningError exception raised if lock already held
  - [ ] Lock acquisition sets flag to `"true"` atomically with database commit
  - [ ] `_update_last_run_timestamp(db, job_name)` called on successful lock acquisition
  - [ ] Lock released in `finally` block regardless of exceptions
  - [ ] Rollback logic handles database errors during cleanup
  - [ ] `JobAlreadyRunningError` exception class defined
  - [ ] Unit tests verify lock acquisition and release flow
  - [ ] Unit tests verify cleanup occurs even on exceptions
  - [ ] Integration tests verify two concurrent job attempts result in one execution
  - [ ] **Stale Lock Recovery:**
    - [ ] `SchedulerService.start()` checks for stale `scheduler_running` flags on initialization
    - [ ] Flag considered stale if set to `"true"` AND `last_run` timestamp >2 hours old
    - [ ] Stale flags automatically cleared on startup with WARNING log message
    - [ ] Log message includes: `"Detected stale scheduler lock from [timestamp]. Clearing lock and resuming."`
    - [ ] If `last_run` timestamp missing, flag cleared if `updated_at` >2 hours old
    - [ ] Recovery logic documented in `overlap_prevention.py` docstring
    - [ ] Unit test simulates stale flag and verifies clearance
    - [ ] Integration test simulates crash scenario:
      1. Start job, verify `scheduler_running="true"`
      2. Kill container (`docker kill`)
      3. Restart container
      4. Verify scheduler starts successfully
      5. Verify stale flag cleared with warning log
      6. Verify next scheduled job executes normally

#### 5. ✅ [BE-004] Implement Scheduled Download Job with Error Handling
- **Description:** Create `scheduled_download_job.py` implementing the main async job function that processes all enabled channels with three-tier error handling. Integrates with existing video_download_service and uses overlap prevention mechanism.
- **Estimation:** 1-2 days
- **Dependencies:** Task 2 (BE-001), Task 4 (BE-003), existing video_download_service
- **Reference:** Lines 1987-2194 in Reference Materials
- **Acceptance Criteria:**
  - [ ] `scheduled_download_job()` async function created
  - [ ] Uses `scheduler_lock(db, "scheduled_downloads")` context manager
  - [ ] Queries all enabled channels: `db.query(Channel).filter(Channel.enabled == True).all()`
  - [ ] Skips execution with log message if no enabled channels found
  - [ ] Processes each channel sequentially with individual try-except blocks
  - [ ] Calls `video_download_service.process_channel_downloads(channel, db)` for each channel
  - [ ] Individual channel failures don't stop processing of remaining channels
  - [ ] `_process_channel_with_recovery(channel, db)` implements retry logic (max 2 retries)
  - [ ] `_is_retryable_error(error_message)` determines if errors should be retried
  - [ ] `_create_failed_history_record(channel_id, error_message, db)` logs failures
  - [ ] `_update_job_statistics(summary, db)` stores job summary in ApplicationSettings
  - [ ] Job summary includes: total_channels, successful_channels, failed_channels, total_videos, duration
  - [ ] JobAlreadyRunningError caught and logged as warning (not error)
  - [ ] All exceptions caught at top level to prevent scheduler disruption
  - [ ] Unit tests verify error isolation between channels
  - [ ] Integration tests verify complete job execution with mixed success/failure channels

---

### **LAYER 3: API ENDPOINTS**

#### 6. ✅ [BE-005] Create Scheduler Management API Endpoints
- **Description:** Add 4 new API endpoints to settings router for scheduler configuration and monitoring. Provides frontend interface for all scheduler operations with validation and error handling.
- **Estimation:** 1 day
- **Dependencies:** Task 2 (BE-001), Task 3 (BE-002)
- **Reference:** Lines 1882-1982 in Reference Materials (FastAPI integration section)
- **Acceptance Criteria:**
  - [ ] `GET /api/v1/scheduler/status` endpoint returns current scheduler state
  - [ ] Status response includes: enabled, schedule, next_run, last_run, scheduler_running flag
  - [ ] `POST /api/v1/scheduler/schedule` endpoint accepts new cron expression
  - [ ] Schedule update validates expression using `validate_cron_expression()`
  - [ ] Returns 400 error with clear message if validation fails
  - [ ] Successful update saves to ApplicationSettings and calls `scheduler_service.update_download_schedule()`
  - [ ] Returns next 5 run times after successful update
  - [ ] `PUT /api/v1/scheduler/enable` endpoint toggles scheduler_enabled flag
  - [ ] `GET /api/v1/scheduler/next-runs?expression={cron}` validates and returns next runs without saving
  - [ ] All endpoints include proper error handling with appropriate HTTP status codes
  - [ ] API responses follow existing schema patterns (success, error_message fields)
  - [ ] OpenAPI documentation automatically generated for all new endpoints
  - [ ] Unit tests verify each endpoint's success and error paths
  - [ ] Integration tests verify end-to-end flows with database

#### 7. ✅ [BE-006] Integrate Scheduler into FastAPI Lifespan
- **Description:** Modify `backend/app/main.py` to add scheduler initialization and shutdown to FastAPI lifespan context manager. Ensures scheduler starts with application and shuts down gracefully.
- **Estimation:** 4 hours
- **Dependencies:** Task 2 (BE-001)
- **Reference:** Lines 1884-1931 in Reference Materials
- **Acceptance Criteria:**
  - [ ] Import `scheduler_service` from `app.scheduler_service`
  - [ ] Modify existing `lifespan(app)` context manager or create if missing
  - [ ] Call `await scheduler_service.start()` in startup section
  - [ ] Log successful scheduler start with recovered job count
  - [ ] Call `await scheduler_service.shutdown()` in finally/shutdown section
  - [ ] Log scheduler shutdown completion
  - [ ] Handle exceptions during scheduler start/stop with clear error messages
  - [ ] Scheduler start failure prevents application from starting (raises exception)
  - [ ] Scheduler shutdown errors logged but don't prevent app shutdown
  - [ ] Integration tests verify scheduler starts when Docker container starts
  - [ ] Integration tests verify scheduler persists jobs after container restart

#### 8. ✅ [BE-007] Coordinate Manual Trigger with Scheduler Lock
- **Description:** Modify existing manual trigger endpoint (`POST /channels/{id}/download`) to coordinate with scheduler lock mechanism. Ensures manual triggers respect `scheduler_running` flag and queue requests when scheduled job is active. This implements Story 007 scenario "Manual trigger during scheduled run" (lines 76-81).
- **Estimation:** 1 day
- **Dependencies:** Task 4 (BE-003 - overlap prevention), existing manual trigger endpoint
- **Acceptance Criteria:**
  - [ ] **Lock Coordination:**
    - [ ] POST /channels/{id}/download checks `scheduler_running` flag before execution
    - [ ] Uses same overlap prevention mechanism as BE-003 (scheduler_lock context manager)
    - [ ] If scheduler_running="true", returns 202 Accepted (not 200 OK)
    - [ ] If scheduler_running="false", executes immediately and returns 200 OK
  - [ ] **Queue Mechanism:**
    - [ ] Queue implemented using ApplicationSettings table with key `manual_trigger_queue`
    - [ ] Queue value stores JSON array: `[{"channel_id": 123, "user": "manual", "timestamp": "2025-09-29T10:30:00Z"}]`
    - [ ] New manual requests appended to queue array when scheduler active
    - [ ] Queue persists across container restarts
  - [ ] **Response Handling:**
    - [ ] 202 response body: `{"status": "queued", "message": "Scheduled job in progress. Manual download queued.", "position": 1}`
    - [ ] 200 response body: `{"status": "completed", "success": true, "videos_downloaded": 5}`
    - [ ] Response schema documented in OpenAPI spec
  - [ ] **Queue Processing:**
    - [ ] `scheduled_download_job()` in BE-004 checks queue after completing scheduled channels
    - [ ] Processes queued manual requests in FIFO order
    - [ ] Each queued request executed with same error handling as scheduled downloads
    - [ ] Queue cleared after all requests processed
    - [ ] Failed queued requests logged but don't stop queue processing
  - [ ] **Timeout Handling:**
    - [ ] Manual requests older than 30 minutes removed from queue with warning
    - [ ] Timeout check runs at job start before processing queue
    - [ ] User receives error via DownloadHistory if request timed out
  - [ ] **Testing:**
    - [ ] Unit test verifies queue serialization/deserialization
    - [ ] Integration test: Manual trigger during scheduled run returns 202
    - [ ] Integration test: Queued request executes after scheduled job completes
    - [ ] Integration test: Multiple queued requests processed in order
    - [ ] Integration test: Timeout removes stale requests
  - [ ] **Documentation:**
    - [ ] API documentation updated with 202 response example
    - [ ] Queue mechanism documented in code comments
    - [ ] User guide notes manual triggers may be queued during scheduled runs

---

### **LAYER 4: FRONTEND UI**

#### 9. ✅ [FE-001] Add Cron Scheduler Section to Settings Page
- **Description:** Extend Settings page component to display cron scheduler configuration below the default video limit setting. Include input field, validation feedback, enable/disable toggle, and next runs display with conditional rendering based on channel count.
- **Estimation:** 1-2 days
- **Dependencies:** Task 6 (BE-005), Task 8 (BE-007 - for 202 status handling)
- **Acceptance Criteria:**
  - [ ] Cron scheduler section added to Settings.tsx below default video limit
  - [ ] Section displays current cron expression fetched from `GET /scheduler/status`
  - [ ] Editable text input field for cron expression (when channels exist)
  - [ ] Input field disabled and grayed out when no channels exist
  - [ ] Real-time validation feedback using `GET /scheduler/next-runs?expression={input}`
  - [ ] Validation runs on input blur or 500ms debounce after typing stops
  - [ ] Error messages display clearly below input field when expression is invalid
  - [ ] Success state shows next 5 scheduled run times in user-friendly format
  - [ ] "Save Schedule" button disabled when expression is invalid or unchanged
  - [ ] Save button calls `POST /scheduler/schedule` and shows success/error feedback
  - [ ] Enable/disable toggle reflects `scheduler_enabled` setting
  - [ ] Toggle calls `PUT /scheduler/enable` with immediate visual feedback
  - [ ] Common cron pattern examples provided (e.g., "0 */6 * * *" for every 6 hours)
  - [ ] Help text explains cron format with link to external cron documentation
  - [ ] Responsive design works on mobile and desktop
  - [ ] Loading states shown during API calls
  - [ ] Component tests verify rendering and user interactions
  - [ ] E2E tests verify save and toggle flows
  - [ ] **Default Schedule Display:**
    - [ ] On first load with no saved `cron_schedule` in database, displays default `"0 0 * * *"`
    - [ ] Default schedule shown with visual indicator: badge/label reading "Default: Daily at Midnight"
    - [ ] Input field pre-populated with `"0 0 * * *"` (not empty placeholder)
    - [ ] User can immediately edit default value without separate "create schedule" step
    - [ ] Visual indicator changes from "Default" to "Custom" after user modifies value
    - [ ] Save button shows "Save Schedule" (not "Create Schedule") even for first save
    - [ ] Component test verifies default display when `GET /scheduler/status` returns null schedule
    - [ ] Component test verifies "Default" badge displays correctly
    - [ ] E2E test verifies first-time user sees pre-populated default schedule

#### 10. ✅ [FE-002] Add Scheduler Status Display to Dashboard
- **Description:** Add scheduler status widget to Dashboard page showing current schedule, last run, next run, and recent activity summary. Provides at-a-glance monitoring without navigating to settings.
- **Estimation:** 1 day
- **Dependencies:** Task 6 (BE-005)
- **Acceptance Criteria:**
  - [ ] Scheduler status widget added to Dashboard.tsx
  - [ ] Widget displays current cron schedule in human-readable format
  - [ ] Last successful run timestamp shown with relative time (e.g., "2 hours ago")
  - [ ] Next scheduled run time shown with countdown timer
  - [ ] Current status indicator: "Active", "Paused", "Running Job", "No Schedule"
  - [ ] Recent failures displayed with count and error messages (last 5)
  - [ ] Visual indicator shows scheduler_running flag status
  - [ ] Link to Settings page for configuration changes
  - [ ] Widget refreshes status every 30 seconds using polling or WebSocket
  - [ ] Loading state shown while fetching initial data
  - [ ] Error state shown if API call fails with retry button
  - [ ] Widget adapts to available space (collapsible on mobile)
  - [ ] Component tests verify rendering for different status states
  - [ ] E2E tests verify real-time updates

#### 11. ✅ [FE-003] Implement Real-time Validation Feedback
- **Description:** Create reusable validation feedback component that shows cron expression validity in real-time with clear error messages, next run previews, and visual indicators. Enhances user experience during schedule configuration.
- **Estimation:** 4-6 hours
- **Dependencies:** Task 9 (FE-001)
- **Acceptance Criteria:**
  - [ ] ValidationFeedback component created in `frontend/src/components/`
  - [ ] Component accepts props: `expression`, `isValidating`, `validationResult`
  - [ ] Shows loading spinner during validation API call
  - [ ] Displays green checkmark icon for valid expressions
  - [ ] Displays red X icon for invalid expressions
  - [ ] Error messages shown in red text below input
  - [ ] Next 5 run times displayed in formatted list for valid expressions
  - [ ] Time until next run shown in human-readable format (e.g., "in 3 hours")
  - [ ] Validation debounced to avoid excessive API calls
  - [ ] Component reusable for future cron configuration features
  - [ ] Accessibility: proper ARIA labels and focus management
  - [ ] Component tests verify rendering for all states
  - [ ] Storybook story created showing all validation states

---

### **LAYER 5: INTEGRATION & TESTING**

#### 12. ✅ [TEST-001] Write Unit Tests for Scheduler Components
- **Description:** Comprehensive unit test coverage for all scheduler service components including cron validation, overlap prevention, and scheduler service methods. Ensures individual components work correctly in isolation.
- **Estimation:** 1-2 days
- **Dependencies:** Tasks 2-5 (all backend service implementations)
- **Acceptance Criteria:**
  - [ ] Test file created: `backend/tests/test_cron_validation.py`
  - [ ] Test file created: `backend/tests/test_overlap_prevention.py`
  - [ ] Test file created: `backend/tests/test_scheduler_service.py`
  - [ ] Test file created: `backend/tests/test_scheduled_download_job.py`
  - [ ] **Cron Validation Tests:**
    - [ ] Test 9 valid cron expressions accept correctly
    - [ ] Test 13 invalid expressions reject with specific error messages
    - [ ] Test minimum interval enforcement (reject */1 patterns)
    - [ ] Test input sanitization removes dangerous characters
    - [ ] Test next run calculation returns correct datetime objects
    - [ ] Test human-readable description generation
  - [ ] **Overlap Prevention Tests:**
    - [ ] Test lock acquisition sets database flag correctly
    - [ ] Test JobAlreadyRunningError raised when lock held
    - [ ] Test lock released in finally block
    - [ ] Test cleanup occurs even on exceptions
    - [ ] Test last_run timestamp updated on successful acquisition
  - [ ] **Scheduler Service Tests:**
    - [ ] Test scheduler initialization with correct configuration
    - [ ] Test update_download_schedule() adds/updates job
    - [ ] Test get_schedule_status() returns correct state
    - [ ] Test event listeners triggered on job execution
    - [ ] Test graceful shutdown completes running jobs
  - [ ] **Scheduled Job Tests:**
    - [ ] Test channel processing loop with mock channels
    - [ ] Test individual channel failure doesn't stop processing
    - [ ] Test retry logic for transient errors
    - [ ] Test statistics collection and storage
    - [ ] Test JobAlreadyRunningError handling
  - [ ] All tests use proper mocking for database and external dependencies
  - [ ] Test coverage ≥85% for scheduler components
  - [ ] All tests pass in CI/CD pipeline

#### 13. ✅ [TEST-002] Write Integration Tests for End-to-End Flows
- **Description:** Integration test suite covering complete scheduler flows from API calls through job execution to database updates. Tests interaction between all scheduler components in realistic scenarios.
- **Estimation:** 2-3 days
- **Dependencies:** Tasks 2-8 (all backend implementations including BE-007)
- **Acceptance Criteria:**
  - [ ] Test file created: `backend/tests/integration/test_scheduler_integration.py`
  - [ ] **Scenario: Default Schedule Setup**
    - [ ] Test GET /scheduler/status returns default "0 0 * * *"
    - [ ] Test scheduler enabled when channels exist
    - [ ] Test scheduler disabled indicator when no channels exist
  - [ ] **Scenario: Schedule Update Flow**
    - [ ] Test POST /scheduler/schedule with valid expression updates database
    - [ ] Test scheduler job updated with new trigger
    - [ ] Test next_run times calculated correctly
    - [ ] Test invalid expression returns 400 error
  - [ ] **Scenario: Scheduled Job Execution**
    - [ ] Test job triggers on schedule (mock time advancement)
    - [ ] Test all enabled channels processed sequentially
    - [ ] Test disabled channels skipped
    - [ ] Test DownloadHistory records created for each channel
    - [ ] Test Channel.last_check timestamps updated
    - [ ] Test job statistics stored in ApplicationSettings
  - [ ] **Scenario: Overlap Prevention**
    - [ ] Test second job attempt skipped when first running
    - [ ] Test warning logged about overlap
    - [ ] Test scheduler_running flag cleared after completion
    - [ ] Test flag cleared even if job fails
  - [ ] **Scenario: Error Recovery**
    - [ ] Test individual channel failure continues processing others
    - [ ] Test transient errors trigger retry logic
    - [ ] Test permanent errors logged without retry
    - [ ] Test failed channels recorded in DownloadHistory
  - [ ] **Scenario: Manual Trigger During Scheduled Run**
    - [ ] Test manual download request queued when scheduler running
    - [ ] Test appropriate message returned to user
    - [ ] Test manual download executes after scheduled job completes
  - [ ] All tests use real database (SQLite test database)
  - [ ] Tests clean up after themselves (delete test data)
  - [ ] All integration tests pass in CI/CD pipeline

#### 14. ✅ [TEST-003] Verify Docker Persistence and Recovery
- **Description:** Docker-specific integration tests verifying that scheduler jobs persist across container restarts and recover correctly. Validates production deployment behavior in containerized environment.
- **Estimation:** 1 day
- **Dependencies:** Task 7 (BE-006)
- **Acceptance Criteria:**
  - [ ] Test script created: `backend/tests/docker/test_persistence.sh`
  - [ ] Test documentation created: `docs/testing-guide.md` section for Docker tests
  - [ ] **Scenario: Job Persistence Across Restart**
    - [ ] Test creates scheduler with cron job via API
    - [ ] Test records job ID and next_run_time before shutdown
    - [ ] Test stops Docker container gracefully
    - [ ] Test starts Docker container
    - [ ] Test verifies job recovered with same ID
    - [ ] Test verifies next_run_time maintained correctly
  - [ ] **Scenario: Database Flag Recovery**
    - [ ] Test simulates crash while scheduler_running=true
    - [ ] Test verifies flag cleared on startup (or implements recovery logic)
    - [ ] Test ensures new jobs can execute after recovery
  - [ ] **Scenario: Multiple Restart Cycles**
    - [ ] Test performs 3 consecutive restart cycles
    - [ ] Test verifies job persists through all cycles
    - [ ] Test verifies no job duplication occurs
  - [ ] **Scenario: Configuration Persistence**
    - [ ] Test updates cron schedule via API
    - [ ] Test restarts container
    - [ ] Test verifies new schedule loaded on startup
    - [ ] Test verifies old POC jobs cleaned up/replaced
  - [ ] All Docker tests documented in testing guide
  - [ ] Docker tests run in CI/CD using docker-compose.test.yml
  - [ ] Test cleanup removes test containers and volumes

---

### **LAYER 6: DOCUMENTATION**

#### 15. ✅ [DOC-001] Create User Guide for Cron Configuration
- **Description:** Comprehensive user documentation explaining how to configure cron schedules, understand cron syntax, use the Settings UI, and troubleshoot common issues. Makes scheduler feature accessible to users with varying technical backgrounds.
- **Estimation:** 4-6 hours
- **Dependencies:** Task 8 (FE-001)
- **Acceptance Criteria:**
  - [ ] Documentation file created: `docs/user-guides/cron-scheduling-guide.md`
  - [ ] **Introduction Section:**
    - [ ] Overview of automated scheduling feature
    - [ ] Benefits of scheduled downloads
    - [ ] Link to cron expression learning resources
  - [ ] **Cron Syntax Explanation:**
    - [ ] 5-field format explained (minute hour day month dow)
    - [ ] Value ranges for each field documented
    - [ ] Special characters explained (*, -, ,, /)
    - [ ] 10+ common pattern examples with explanations
  - [ ] **Configuration Instructions:**
    - [ ] Step-by-step guide to accessing Settings page
    - [ ] Instructions for entering cron expression
    - [ ] Explanation of validation feedback
    - [ ] Instructions for saving and enabling schedule
    - [ ] Screenshots of Settings UI (annotated)
  - [ ] **Monitoring Section:**
    - [ ] How to view current schedule status
    - [ ] Understanding next run times
    - [ ] Checking last run results
    - [ ] Accessing download history
  - [ ] **Troubleshooting:**
    - [ ] Common error messages and solutions
    - [ ] "Invalid expression" resolution steps
    - [ ] "No channels enabled" explanation
    - [ ] "Schedule not running" debugging
    - [ ] How to view Docker logs for errors
  - [ ] **FAQ Section:**
    - [ ] What happens if schedule runs while manual download active?
    - [ ] How to temporarily pause scheduled downloads?
    - [ ] What's the minimum allowed frequency? (5 minutes)
    - [ ] How to see which videos were downloaded?
  - [ ] Examples for common use cases:
    - [ ] Download every 6 hours: `0 */6 * * *`
    - [ ] Download daily at 2 AM: `0 2 * * *`
    - [ ] Download weekdays at 6 PM: `0 18 * * 1-5`
  - [ ] Documentation accessible from Settings UI via help link
  - [ ] Documentation reviewed for clarity and completeness

#### 16. ✅ [DOC-002] Update API Documentation
- **Description:** Update OpenAPI/Swagger documentation and API reference guide to include all new scheduler endpoints with complete request/response examples and error codes.
- **Estimation:** 2-3 hours
- **Dependencies:** Task 6 (BE-005), Task 8 (BE-007 - for 202 response docs)
- **Acceptance Criteria:**
  - [ ] FastAPI docstrings added to all scheduler endpoints with detailed descriptions
  - [ ] Request body schemas documented with field descriptions and examples
  - [ ] Response schemas documented with field descriptions and examples
  - [ ] Error responses documented with status codes and example messages
  - [ ] Pydantic models created for request/response validation where missing
  - [ ] OpenAPI tags added: `scheduler` tag for grouping endpoints
  - [ ] `/docs` endpoint (Swagger UI) displays scheduler endpoints correctly
  - [ ] `/redoc` endpoint (ReDoc) displays scheduler documentation
  - [ ] Example curl commands provided for each endpoint
  - [ ] Postman collection updated with scheduler endpoints
  - [ ] API versioning documented (`/api/v1/scheduler/*`)
  - [ ] Rate limiting and authentication requirements documented (if applicable)
  - [ ] API changelog updated with new v1.x release notes

#### 17. ✅ [DOC-003] Create Troubleshooting Guide
- **Description:** Comprehensive troubleshooting documentation covering common issues, diagnostic steps, log analysis, and recovery procedures specific to scheduler functionality.
- **Estimation:** 3-4 hours
- **Dependencies:** All implementation tasks completed
- **Acceptance Criteria:**
  - [ ] Documentation file created: `docs/troubleshooting/scheduler-issues.md`
  - [ ] **Common Issues Section:**
    - [ ] "Schedule not executing" - causes and solutions
    - [ ] "Invalid cron expression" - validation rules and examples
    - [ ] "Downloads not happening" - dependency checklist
    - [ ] "Overlap detected" - understanding and resolution
    - [ ] "Jobs lost after restart" - persistence verification
  - [ ] **Diagnostic Steps:**
    - [ ] How to check scheduler status via API
    - [ ] How to view scheduler logs in Docker
    - [ ] How to verify database flags and timestamps
    - [ ] How to confirm job registration
    - [ ] How to test cron expression validity
  - [ ] **Log Analysis:**
    - [ ] Example log entries for successful execution
    - [ ] Example log entries for common errors
    - [ ] How to grep/filter scheduler logs
    - [ ] Understanding log levels and their meanings
  - [ ] **Recovery Procedures:**
    - [ ] How to reset stuck scheduler_running flag
    - [ ] How to manually trigger download after failure
    - [ ] How to clear corrupted job store
    - [ ] How to restore from backup
    - [ ] When to restart Docker container
  - [ ] **Advanced Debugging:**
    - [ ] Accessing SQLite job store database
    - [ ] Inspecting ApplicationSettings table
    - [ ] Checking Docker volume mounts
    - [ ] Verifying APScheduler configuration
  - [ ] Links to relevant log files and configuration locations
  - [ ] Contact information or GitHub issue template for bugs
  - [ ] Documentation accessible from main docs index

---

### **TASK DEPENDENCIES & SEQUENCING**

```
LAYER 1 (Foundation):
  DB-001 (4 hours)
    ↓

LAYER 2 (Core Services) - Can be done in parallel:
  ├─ BE-001 (1-2 days) - depends on DB-001
  ├─ BE-002 (1 day) - independent
  ├─ BE-003 (1 day) - depends on DB-001
  └─ BE-004 (1-2 days) - depends on BE-001, BE-003
       ↓

LAYER 3 (API & Integration):
  ├─ BE-005 (1 day) - depends on BE-001, BE-002
  ├─ BE-006 (4 hours) - depends on BE-001
  └─ BE-007 (1 day) - depends on BE-003, existing manual trigger endpoint [NEW]
       ↓

LAYER 4 (Frontend) - Can be done in parallel:
  ├─ FE-001 (1-2 days) - depends on BE-005, BE-007
  ├─ FE-002 (1 day) - depends on BE-005
  └─ FE-003 (4-6 hours) - depends on FE-001
       ↓

LAYER 5 (Testing) - Can be done in parallel:
  ├─ TEST-001 (1-2 days) - depends on BE-001 through BE-004
  ├─ TEST-002 (2-3 days) - depends on BE-001 through BE-007 [UPDATED]
  └─ TEST-003 (1 day) - depends on BE-006
       ↓

LAYER 6 (Documentation) - Can be done in parallel:
  ├─ DOC-001 (4-6 hours) - depends on FE-001
  ├─ DOC-002 (2-3 hours) - depends on BE-005, BE-007
  └─ DOC-003 (3-4 hours) - depends on all implementation tasks
```

**Critical Path:** DB-001 → BE-001 → BE-004 → BE-007 → FE-001 → TEST-002

**Estimated Total Effort:** 13-18 days for single developer, 9-12 days with 2 developers

**Parallel Workstreams:**
- **Stream 1 (Backend):** DB-001 → BE-001 → BE-004 → BE-006 → TEST-002 → DOC-003
- **Stream 2 (Utilities & Integration):** BE-002 → BE-003 → BE-007 → TEST-001
- **Stream 3 (Frontend):** (waits for BE-005, BE-007) → FE-001 → FE-003 → FE-002 → DOC-001
- **Stream 4 (Validation):** TEST-003 → DOC-002

---

### **RISK MITIGATION & ALTERNATIVES**

#### **Risk: POC Code Adaptation**
- **Mitigation:** Reference code provided in story is production-ready. Follow patterns closely.
- **Alternative:** If issues arise, POC code can be run again for debugging comparison.

#### **Risk: Docker Volume Persistence Issues**
- **Mitigation:** TEST-003 verifies persistence before frontend work begins.
- **Alternative:** If SQLite issues occur, can fall back to PostgreSQL job store (requires docker-compose update).

#### **Risk: Frontend Validation UX Complexity**
- **Mitigation:** FE-003 creates reusable component isolating complexity.
- **Alternative:** Simplify to validation on save only (no real-time feedback) to reduce scope.

#### **Risk: Overlap Prevention Edge Cases**
- **Mitigation:** TEST-001 and TEST-002 specifically test concurrent scenarios.
- **Alternative:** If database flags unreliable, can add Redis-based locking (requires new service).

#### **Risk: Integration with Existing Download Service**
- **Mitigation:** video_download_service.process_channel_downloads() already tested in previous stories.
- **Alternative:** None needed - existing service is stable and designed for this use case.

---

### **MVP vs POST-MVP CONSIDERATIONS**

**MVP Scope (Required for Story Completion):**
- All tasks DB-001 through FE-003 (including BE-007 and real-time validation)
- TEST-001 and TEST-002 (core testing)
- DOC-001 (user guide)

**Post-MVP Enhancements (Nice to Have):**
- TEST-003 (Docker persistence testing) - can be manual testing initially
- DOC-002, DOC-003 (enhanced documentation) - can be basic initially
- Advanced monitoring dashboard widgets
- Per-channel schedule overrides (future story)
- Schedule history and analytics

**Recommended MVP Implementation Order:**
1. Complete LAYER 1 & 2 (database + backend services) - 3-4 days
2. Complete LAYER 3 (API integration including BE-007) - 2 days
3. Complete FE-001 and FE-003 (settings UI with real-time validation) - 2-3 days
4. Complete TEST-001, TEST-002 (core testing) - 3-4 days
5. Complete DOC-001 (user guide) - 0.5 days
6. **MVP Complete** - remaining tasks can be done incrementally

Total MVP Timeline: **8-12 days**

---

## Implementation Status

**Status:** ✅ Ready for Implementation
**Confidence Level:** High (85%+)
**Estimated Timeline:** 8-12 days for MVP

All critical requirements have been validated and acceptance criteria refined for production readiness.
