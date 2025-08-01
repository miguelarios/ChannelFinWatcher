# User Story: Add New Channel

## Section 1: Story Definition

### Feature
Simple form to add YouTube channels for monitoring with configurable video limits

### User Story
- **As a** user
- **I want** to add YouTube channels through a simple web form
- **So that** I can start monitoring channels for new videos without technical setup

### Functional Requirements

#### [x] Scenario: Add Valid YouTube Channel - Happy Path
- **Given** the user is on the main page
  - And the "Add New Channel" form is visible
  - And the form has fields for "YouTube Channel URL" and "Number of Recent Videos to Download"
- **When** the user enters a valid YouTube channel URL (e.g., "https://www.youtube.com/@MrsRachel")
  - And enters a number for recent videos (e.g., "10")
  - And clicks the "+ Add Channel & Download Videos" button
- **Then** the system validates and extracts channel information
  - And a small rectangular card appears below the form showing the new channel
  - And the card displays channel name, URL, and video limit
  - And the channel is saved to the database
  - But no actual video downloading occurs yet (future feature)

#### [x] Scenario: Form Validation - Invalid Inputs
- **Given** the user is on the main page with the form visible
- **When** the user submits the form with empty URL field
  - Or enters an invalid URL format
  - Or enters non-numeric value for video count
- **Then** appropriate validation error messages are displayed
  - And the form is not submitted
  - And no database changes occur

#### [x] Scenario: Multiple Channel Addition
- **Given** the user has already added one channel successfully
- **When** the user adds another valid channel
- **Then** a new card appears below the previous one
  - And both channels are visible in the interface
  - And both channels are stored in the database

### Non-functional Requirements
- **Performance:** Form submission completes within 3 seconds for valid channels
- **Security:** Input validation prevents XSS and injection attacks
- **Reliability:** Database operations are atomic, failed additions don't leave partial data
- **Usability:** Clear visual feedback, intuitive form layout, mobile-responsive design

### Implementation Notes

#### Key Technical Decisions
- **YouTube URL Validation**: Supports multiple formats (/@handle, /c/channel, /channel/UC..., /user/username)
- **Metadata Extraction**: Uses yt-dlp to extract channel name and ID without downloading videos
- **Duplicate Prevention**: Checks channel_id (not just URL) to prevent duplicate channels with different URL formats
- **URL Normalization**: Backend normalizes URLs to consistent format while avoiding double-www issues

#### Channel Deduplication Strategy
The system prevents duplicate channels by checking the extracted YouTube channel_id rather than just the URL. This handles cases where the same channel can be accessed via multiple URL formats:
- `https://www.youtube.com/@ChannelName` 
- `https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxx`

When a duplicate is detected, users receive a clear message: "This channel is already being monitored as 'Channel Name' with URL: [existing_url]"

#### Engineering TODOs Completed
- ✅ Support multiple YouTube URL formats (/@handle, /c/channel, /channel/UC...)
- ✅ Use yt-dlp to extract channel metadata without downloading videos
- ✅ Design simple card component for channel display
- ✅ Implement robust duplicate detection via channel_id

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

#### 1. [x] Frontend Form Component - User Interface
- **Description:** Create "Add New Channel" form with two input fields and submit button, plus channel cards display
- **Estimation:** 2-3 hours
- **Acceptance Criteria:**
  - [x] Form has YouTube URL input field with proper validation
  - [x] Form has numeric input for "Number of Recent Videos to Download"
  - [x] Submit button labeled "+ Add Channel for Monitoring"
  - [x] Form validates inputs client-side before submission
  - [x] Channel cards display below form showing added channels
  - [x] Responsive design works on mobile and desktop

#### 2. [x] Backend API Endpoint - Channel Processing
- **Description:** Create POST endpoint to validate YouTube URLs, extract channel info, and store in database
- **Estimation:** 3-4 hours
- **Acceptance Criteria:**
  - [x] POST /api/v1/channels endpoint accepts URL and video_limit
  - [x] Validates YouTube URL format using regex patterns
  - [x] Uses yt-dlp to extract channel name and ID without downloading
  - [x] Stores channel information in database
  - [x] Returns channel data for frontend display
  - [x] Handles errors gracefully with proper HTTP status codes
  - [x] Prevents duplicate channels via channel_id checking

#### 3. [x] Database Schema - Channel Storage
- **Description:** Create channels table with necessary fields for basic channel information
- **Estimation:** 1-2 hours
- **Acceptance Criteria:**
  - [x] Channels table with id, url, name, channel_id, video_limit, created_at fields
  - [x] Unique constraint on channel_id to prevent duplicates (improved from URL-only)
  - [x] Database migration script created and tested
  - [x] Basic channel model created in SQLAlchemy

#### 4. [x] Integration & Testing - End-to-End Flow
- **Description:** Connect frontend form to backend API and verify complete user flow
- **Estimation:** 2-3 hours
- **Acceptance Criteria:**
  - [x] Form submission successfully calls backend API
  - [x] API response updates frontend display with new channel card
  - [x] Error handling works for invalid URLs and network failures
  - [x] Multiple channels can be added in sequence
  - [x] Database persists channel data correctly
  - [x] Manual testing with real YouTube channels confirms functionality
  - [x] Duplicate channel detection tested with different URL formats