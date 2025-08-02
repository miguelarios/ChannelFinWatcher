# User Story: Configure Channel Video Limit

## Section 1: Story Definition

### Feature
Per-channel video limit configuration with inline editing interface

### User Story
- **As a** YouTube channel watcher
- **I want** to set how many recent videos to keep per channel
- **So that** I can control storage usage for each channel individually based on content importance

### Functional Requirements

#### [x] Scenario: Edit video limit via inline editing
- **Given** I have channels added to my monitoring list
  - And the channel list is displayed in the web UI
  - And each channel shows its current video limit
- **When** I click on a channel's video limit field
  - And I modify the limit value to a number between 1-100
  - And I save the change
- **Then** the limit is updated in the database
  - And the change is reflected immediately in the UI
  - And the new limit takes effect on the next download cycle

#### [x] Scenario: Validate video limit input ranges
- **Given** I am editing a channel's video limit
- **When** I enter a value outside the range of 1-100
  - And I attempt to save
- **Then** I receive a clear validation error message
  - And the invalid value is rejected
  - And I can correct the input without losing other changes

#### [x] Scenario: Handle video limit reduction gracefully  
- **Given** I have a channel with 50 videos downloaded
  - And the current limit is 50
- **When** I reduce the limit to 20
  - And I confirm the change
- **Then** the limit is updated successfully
  - And existing videos beyond the new limit are NOT immediately deleted
  - But auto-cleanup will respect the new limit on next download cycle

#### [x] Scenario: Auto-select text for easy number replacement
- **Given** I want to change a channel's limit from 10 to 9
  - And the channel is displayed in the channel list
- **When** I click on the limit display text or edit icon
  - And the inline editor appears
- **Then** all text in the number input is automatically selected
  - And I can immediately type "9" to replace "10"
  - And the old value is completely replaced without manual deletion

### Non-functional Requirements
- **Performance:** Limit updates complete within 1 second
- **Security:** Input validation prevents SQL injection and XSS attacks
- **Reliability:** Failed limit updates don't corrupt channel data
- **Usability:** Inline editing is intuitive with clear visual feedback and auto-text selection for efficient number entry

### Engineering TODOs
- [x] Database schema supports video limits (completed - Channel.limit column exists)
- [x] Backend API supports limit updates (completed - PUT /channels/{id} exists)
- [x] Frontend inline editing component implemented
- [x] YAML configuration sync when limits change via UI
- [x] UX enhancements: auto-text selection and clickable limit display

---

## Section 2: Engineering Tasks

### Task Breakdown

#### 1. [x] Database Schema - Video Limit Support
- **Description:** Add video_limit column to channels table with constraints
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] Channel model has limit column with default value of 10
  - [x] Database constraint enforces range 1-100
  - [x] Column is indexed for efficient queries

#### 2. [x] Backend API - Channel Update Endpoint  
- **Description:** API endpoint to update channel settings including video limit
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] PUT /channels/{id} endpoint accepts limit updates
  - [x] Pydantic validation enforces 1-100 range
  - [x] Returns updated channel data in response

#### 3. [x] Frontend Component - Inline Limit Editor
- **Description:** React component for editing video limits inline in channel list
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] Click on limit value enables inline editing mode
  - [x] Number input with min=1, max=100 constraints
  - [x] Save/cancel buttons with keyboard shortcuts (Enter/Escape)
  - [x] Visual feedback during editing (highlight, loading states)
  - [x] Optimistic UI updates with rollback on error
  - [x] Auto-select text for easy number replacement

#### 4. [x] Frontend Integration - Connect UI to API
- **Description:** Wire inline editor to backend API calls
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] PUT request sent when user saves limit change
  - [x] Error handling displays user-friendly messages
  - [x] Loading state prevents multiple simultaneous updates
  - [x] Success confirmation provides immediate feedback

#### 5. [x] Backend Enhancement - YAML Configuration Sync
- **Description:** Sync limit changes from web UI to YAML configuration file
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] YAML file updated when limit changed via API
  - [x] Handles concurrent access to YAML file safely
  - [x] Maintains YAML file structure and comments

#### 6. [x] Frontend Enhancement - User Experience Improvements
- **Description:** Polish the editing experience with better UX
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] Confirmation dialog for significant limit reductions (>50% decrease)
  - [x] Undo capability for accidental changes
  - [x] Clickable limit display with hover effects
  - [x] Visual indication of unsaved changes
  - [ ] Bulk edit capability for multiple channels (deferred to future story)

#### 7. [x] Testing - Comprehensive Test Coverage
- **Description:** Manual testing and API validation for limit editing functionality
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] Manual testing of inline editing behavior completed
  - [x] API endpoint validation tested (range checking, error handling)
  - [x] Integration testing verified limit changes persist to database and YAML
  - [x] End-to-end workflow tested via docker containers

#### 8. [x] Documentation - API and Component Documentation
- **Description:** Document the limit editing functionality
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] API endpoint documented with validation rules
  - [x] Component props and methods documented
  - [x] User guide updated with limit editing instructions

#### 9. [x] UX Enhancement - Auto-select Text When Editing
- **Description:** Improve number input UX with automatic text selection and clickable limit display
- **Estimation:** Completed ✅
- **Acceptance Criteria:** 
  - [x] Auto-select all text when entering edit mode using useRef + useEffect
  - [x] onFocus fallback handler to select text on direct input click
  - [x] Make limit display text clickable (not just edit icon)
  - [x] Add hover effects and tooltips for better discoverability
  - [x] Users can immediately type new values without manual text deletion

