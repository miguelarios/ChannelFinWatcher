# User Story: Set Global Default Video Limit

## Section 1: Story Definition

### Feature
Global default video limit configuration - streamlines channel addition with consistent defaults while maintaining per-channel customization capability

### User Story
- **As a** system administrator/user
- **I want** to configure a default video limit that applies to new channels
- **So that** I don't have to set limits individually each time I add a channel and maintain consistency across my channel collection

### Functional Requirements

#### [x] Scenario: Configure Global Default Video Limit - Happy Path
- **Given** I am in the application settings interface
  - And the system has no previously configured default (first run)
  - And I have admin/configuration access
- **When** I set the global default video limit to 15 videos
  - And I save the settings
- **Then** the system displays a success confirmation
  - And the default limit is stored persistently
  - And all new channels will automatically use 15 as their video limit
  - But existing channels remain unchanged with their current limits

#### [x] Scenario: Default Applied to New Channel Creation
- **Given** the global default video limit is set to 20 videos
  - And I am adding a new YouTube channel
- **When** I create a new channel without specifying a custom limit
- **Then** the new channel automatically has a video limit of 20
  - And the channel list displays the limit as "20 (default)"
  - And I can still override this with a custom limit if needed

#### [x] Scenario: Invalid Default Limit Values
- **Given** I am configuring the global default video limit
- **When** I enter a value less than 1 or greater than 100
  - And I attempt to save the setting
- **Then** the system displays an error message "Default limit must be between 1 and 100 videos"
  - And the invalid value is not saved
  - And the previous valid default remains active

#### [x] Scenario: Default Persistence Across Restarts
- **Given** I have set a global default video limit of 25
  - And the setting has been saved successfully
- **When** the application is restarted
- **Then** the default limit remains 25
  - And new channels created after restart use the 25 video limit
  - And the settings interface displays 25 as the current default

### Non-functional Requirements
- **Performance:** Settings retrieval and updates complete within 1 second
- **Security:** Settings changes are validated and sanitized on both client and server side
- **Reliability:** Default settings persist across application restarts and container deployments
- **Usability:** Settings interface provides clear feedback and validation, discoverable from main navigation

### Engineering TODOs
- [x] Design application settings data model and storage approach
- [x] Determine synchronization strategy between database and YAML configuration
- [x] Plan migration strategy for existing installations

---

## Section 2: Engineering Tasks

### Task Breakdown

#### 1. [x] Database Schema for Application Settings
- **Description:** Create application_settings table to store global configuration values including default video limit
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [x] Create `application_settings` table with key-value storage
  - [x] Add `default_video_limit` setting with initial value of 10
  - [x] Include validation constraints (1-100 range)
  - [x] Create database migration script
  - [x] Test migration on clean and existing databases

#### 2. [x] Backend API for Settings Management
- **Description:** Implement FastAPI endpoints for retrieving and updating global settings
- **Estimation:** 3-4 hours
- **Acceptance Criteria:**
  - [x] Create GET `/api/settings/default-video-limit` endpoint
  - [x] Create PUT `/api/settings/default-video-limit` endpoint with validation
  - [x] Add Pydantic models for settings request/response
  - [x] Implement proper error handling and validation
  - [x] Add API documentation with examples

#### 3. [x] Frontend Settings Interface
- **Description:** Create settings page/modal for configuring global default video limit
- **Estimation:** 4-5 hours
- **Acceptance Criteria:**
  - [x] Create GlobalSettings component with number input
  - [x] Add settings page accessible from main navigation
  - [x] Implement real-time validation and error display
  - [x] Show success/error feedback after save attempts
  - [x] Include helpful tooltips explaining default behavior

#### 4. [x] Channel Creation Integration
- **Description:** Modify channel creation workflow to apply default limit automatically
- **Estimation:** 2-3 hours
- **Acceptance Criteria:**
  - [x] Update channel creation API to fetch and apply default limit
  - [x] Modify frontend channel creation forms to show default value
  - [x] Add visual indication when using default vs custom limits
  - [x] Ensure YAML import respects default for channels without explicit limits
  - [x] Test both web UI and YAML-based channel creation

#### 5. [x] YAML Configuration Synchronization
- **Description:** Sync default limit setting between database and YAML configuration
- **Estimation:** 3-4 hours
- **Acceptance Criteria:**
  - [x] Add default_video_limit field to YAML schema
  - [x] Implement bidirectional sync (YAML ↔ Database)
  - [x] Handle conflicts between YAML and database values
  - [x] Update YAML validation to include default limit
  - [x] Test configuration reload scenarios

#### 6. [x] Settings Initialization and Migration
- **Description:** Handle first-run initialization and existing installation migration
- **Estimation:** 2-3 hours
- **Acceptance Criteria:**
  - [x] Initialize default value of 10 on first application run
  - [x] Create migration for existing installations
  - [x] Ensure existing channels maintain current limits
  - [x] Handle edge cases for corrupted or missing settings
  - [x] Test upgrade scenarios from previous versions

#### 7. [x] Testing and Quality Assurance
- **Description:** Comprehensive testing of default limit functionality
- **Estimation:** 3-4 hours
- **Acceptance Criteria:**
  - [x] Unit tests for settings API endpoints
  - [x] Integration tests for channel creation with defaults
  - [x] Frontend component tests for settings interface
  - [x] End-to-end tests for default limit workflow
  - [x] Test persistence across application restarts