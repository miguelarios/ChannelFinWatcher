# Channel Metadata Management - Technical Specification

## Overview

This document provides technical specifications for the Channel Metadata Management feature (Story 004), including JSON structure, API endpoints, troubleshooting guide, and implementation details.

## Architecture

### Components

1. **YouTubeService** (`app/youtube_service.py`)
   - Extended with `extract_channel_metadata_full()` method
   - Optimizes metadata by removing 'entries' key (24MB → 5KB)
   - Implements filesystem-safe naming for directories

2. **ImageService** (`app/image_service.py`) 
   - Secure image download with URL validation
   - Supports cover (avatar_uncropped) and backdrop (banner_uncropped) images
   - File type checking and size limits

3. **MetadataService** (`app/metadata_service.py`)
   - Orchestrates complete metadata workflow
   - Implements error recovery and rollback mechanisms
   - Handles partial failures gracefully

4. **Database Schema Extensions**
   - New fields added to `channels` table for metadata tracking
   - Migration: `c3d8f2e5a9b4_add_metadata_management_fields_to_channels.py`

## Database Schema

### New Fields in `channels` Table

```sql
-- Metadata management fields
metadata_path VARCHAR(500)           -- Path to channel metadata JSON file
directory_path VARCHAR(500)          -- Path to channel directory  
last_metadata_update TIMESTAMP       -- Last metadata extraction
metadata_status VARCHAR(20)          -- pending, completed, failed, refreshing
cover_image_path VARCHAR(500)        -- Path to cover image
backdrop_image_path VARCHAR(500)     -- Path to backdrop image

-- Index for efficient status queries
CREATE INDEX idx_channel_metadata_status ON channels(metadata_status);
```

### Metadata Status Values

- `pending`: Metadata extraction not yet started
- `refreshing`: Metadata extraction in progress
- `completed`: Metadata successfully extracted and saved
- `failed`: Metadata extraction failed with errors

## Directory Structure

### Media Directory Layout

```
/media/
├── Channel Name [channel_id]/                    # Show folder for media server
│   ├── Channel Name [channel_id].info.json      # Optimized channel metadata (~5KB)
│   ├── cover.ext                                 # Channel avatar (from avatar_uncropped)
│   ├── backdrop.ext                              # Channel banner (from banner_uncropped)
│   └── [Future: video files and NFO files]
```

### Example Directory

```
/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/
├── Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg].info.json
├── cover.jpg
└── backdrop.jpg
```

## JSON Metadata Structure

### Optimized Channel Metadata

The metadata JSON file contains complete channel information with the `entries` key removed for size optimization:

```json
{
  "id": "UCG2CL6EUjG8TVT1Tpl9nJdg",
  "channel": "Ms Rachel - Toddler Learning Videos", 
  "channel_id": "UCG2CL6EUjG8TVT1Tpl9nJdg",
  "title": "Ms Rachel - Toddler Learning Videos - Videos",
  "channel_follower_count": 16100000,
  "description": "Toddler Learning Videos and Baby Learning Videos...",
  "tags": ["toddler learning video", "preschool", "ms rachel"],
  "thumbnails": [
    {
      "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIU...",
      "id": "banner_uncropped",
      "preference": -5
    },
    {
      "url": "https://yt3.googleusercontent.com/C2nKGvtlPIpTO80s...",
      "id": "avatar_uncropped", 
      "preference": 1
    }
  ],
  "uploader_id": "@msrachel",
  "uploader_url": "https://www.youtube.com/@msrachel",
  "uploader": "Ms Rachel - Toddler Learning Videos",
  "channel_url": "https://www.youtube.com/channel/UCG2CL6EUjG8TVT1Tpl9nJdg",
  "_type": "playlist",
  "extractor_key": "YoutubeTab",
  "extractor": "youtube:tab", 
  "webpage_url": "https://www.youtube.com/@msrachel/videos",
  "epoch": 1754539997,
  "_version": {
    "version": "2025.07.21",
    "release_git_head": "9951fdd0d08b655cb1af8cd7f32a3fb7e2b1324e",
    "repository": "yt-dlp/yt-dlp"
  }
}
```

### Key Optimizations

- **Size Reduction**: Removing `entries` reduces file size from ~24MB to ~5KB
- **Essential Data Preserved**: All channel metadata retained except video list
- **Timestamp Tracking**: `epoch` field tracks when metadata was extracted
- **Direct Thumbnail Access**: `avatar_uncropped` and `banner_uncropped` URLs directly available

## API Endpoints

### Channel Creation (Enhanced)

```http
POST /api/v1/channels
```

**Enhanced Behavior**: Now triggers automatic metadata processing after channel creation.

**Request Body**:
```json
{
  "url": "https://www.youtube.com/@msrachel",
  "limit": 10,
  "enabled": true,
  "quality_preset": "best"
}
```

**Response** (includes new metadata fields):
```json
{
  "id": 1,
  "url": "https://www.youtube.com/@msrachel",
  "name": "Ms Rachel - Toddler Learning Videos",
  "channel_id": "UCG2CL6EUjG8TVT1Tpl9nJdg",
  "limit": 10,
  "enabled": true,
  "metadata_status": "completed",
  "metadata_path": "/media/Ms Rachel.../Ms Rachel... [UCG2CL6E...].info.json",
  "directory_path": "/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]",
  "cover_image_path": "/media/Ms Rachel.../cover.jpg",
  "backdrop_image_path": "/media/Ms Rachel.../backdrop.jpg",
  "last_metadata_update": "2025-08-10T12:00:00Z",
  "created_at": "2025-08-10T12:00:00Z",
  "updated_at": "2025-08-10T12:00:00Z"
}
```

### Metadata Refresh (New)

```http
POST /api/v1/channels/{channel_id}/refresh-metadata
```

**Description**: Refresh channel metadata, update JSON file, and redownload images.

**Response**:
```json
{
  "message": "Channel metadata refreshed successfully",
  "warnings": ["Image download: Network timeout for backdrop image"]
}
```

**Error Response**:
```json
{
  "detail": "Metadata refresh failed: Channel is private or does not exist"
}
```

## Error Handling

### Error Categories

1. **Network Errors**
   - YouTube API unavailable
   - Image download timeouts
   - Connection failures

2. **Content Errors**  
   - Private or deleted channels
   - Invalid channel URLs
   - Missing thumbnails

3. **System Errors**
   - Disk space exhaustion
   - Permission errors
   - Invalid file paths

4. **Security Errors**
   - Malicious URLs
   - Path traversal attempts
   - Oversized files

### Error Recovery Patterns

#### Rollback Mechanism
```python
rollback_actions = [
    ('remove_directory', '/media/channel_dir'),
    ('remove_file', '/media/channel_dir/metadata.json')
]
# Automatically rolled back on failure
```

#### Partial Failure Handling
- **Metadata succeeds, images fail**: Channel marked as `completed` with warnings
- **Directory creation fails**: Complete rollback, channel marked as `failed`
- **Duplicate channel detected**: Rollback with clear error message

#### Retry Logic
- Network timeouts: Automatic retry with exponential backoff
- Transient errors: Up to 3 retry attempts
- Permanent errors: Immediate failure with clear messaging

## Security Measures

### URL Validation
```python
# Only allow YouTube domains
allowed_domains = [
    'yt3.googleusercontent.com',
    'i.ytimg.com', 
    'yt3.ggpht.com'
]

# Must use HTTPS
if parsed.scheme != 'https':
    return False
```

### File System Security
```python
# Sanitize channel names for filesystem
def make_filesystem_safe(name, max_length=100):
    # Remove problematic characters: <>:"/\|?*
    # Collapse multiple spaces
    # Truncate to reasonable length
    # Validate path stays within media root
```

### Size Limits
- **Image downloads**: 10MB maximum per file
- **Metadata JSON**: ~5KB after optimization  
- **Timeout limits**: 30 seconds for metadata extraction
- **Content-Type validation**: Only allow image/* mime types

## Performance Characteristics

### Metadata Extraction
- **Time**: < 30 seconds per channel (requirement)
- **Size optimization**: 24MB → 5KB (99.98% reduction)
- **Memory usage**: Streaming downloads for efficiency
- **Disk I/O**: Atomic file operations with rollback

### Image Downloads
- **Streaming**: 8KB chunks to manage memory
- **Parallel downloads**: Cover and backdrop downloaded concurrently
- **Graceful degradation**: Metadata succeeds even if images fail
- **Caching**: Images overwritten on refresh

## Troubleshooting Guide

### Common Issues

#### 1. Metadata Status Stuck on "Pending"

**Symptoms**: Channel shows `metadata_status: "pending"` indefinitely

**Diagnosis**:
```sql
SELECT id, name, metadata_status, last_metadata_update, created_at 
FROM channels 
WHERE metadata_status = 'pending' 
AND created_at < datetime('now', '-1 hour');
```

**Solutions**:
1. Check application logs for errors during channel creation
2. Manually trigger refresh: `POST /api/v1/channels/{id}/refresh-metadata`
3. Verify YouTube channel accessibility
4. Check disk space and permissions

#### 2. Directory Creation Failures

**Symptoms**: Error "Failed to create output directory"

**Diagnosis**:
```bash
# Check media directory permissions
ls -la /media/
df -h /media/  # Check disk space
```

**Solutions**:
1. Ensure media directory exists and is writable
2. Check available disk space
3. Verify user permissions for directory creation
4. Check for filesystem mount issues

#### 3. Image Download Failures

**Symptoms**: Metadata completed but missing cover/backdrop images

**Diagnosis**:
```sql
SELECT id, name, metadata_status, cover_image_path, backdrop_image_path
FROM channels 
WHERE metadata_status = 'completed' 
AND (cover_image_path IS NULL OR backdrop_image_path IS NULL);
```

**Solutions**:
1. Check network connectivity to YouTube CDN
2. Verify image URLs in metadata JSON file
3. Check firewall rules for outbound HTTPS
4. Manually refresh metadata to retry image downloads

#### 4. Duplicate Channel Detection

**Symptoms**: Error "Channel already being monitored"

**Diagnosis**:
```sql
SELECT url, name, channel_id FROM channels WHERE channel_id = 'UC123456789';
```

**Solutions**:
1. Verify that different URLs point to same channel
2. Remove duplicate entry if confirmed
3. Use different URL format if needed (/@handle vs /channel/UC...)

### Log Analysis

#### Key Log Messages

**Successful Metadata Processing**:
```
INFO - Successfully processed metadata for channel: Channel Name (UC123456789)
INFO - Saved channel metadata to: /media/Channel [UC123]/metadata.json  
INFO - Successfully downloaded cover image to: /media/Channel [UC123]/cover.jpg
```

**Error Conditions**:
```
ERROR - Metadata extraction failed: Channel is private or does not exist
ERROR - Image download failed: Network timeout after 30 seconds
WARNING - Image download failed for channel 123: [Network error downloading backdrop]
```

#### Debug Mode

Enable debug logging to see detailed workflow:
```python
import logging
logging.getLogger('app.metadata_service').setLevel(logging.DEBUG)
logging.getLogger('app.image_service').setLevel(logging.DEBUG)
```

### Recovery Procedures

#### Reset Channel Metadata
```sql
-- Reset failed channel for retry
UPDATE channels 
SET metadata_status = 'pending',
    metadata_path = NULL,
    directory_path = NULL, 
    cover_image_path = NULL,
    backdrop_image_path = NULL,
    last_metadata_update = NULL
WHERE id = 123;
```

#### Clean Up Orphaned Directories
```bash
# Find directories without corresponding database records
find /media -type d -name "*[UC*]" | while read dir; do
    channel_id=$(basename "$dir" | grep -o 'UC[^]]*')
    if ! psql -tqc "SELECT 1 FROM channels WHERE channel_id = '$channel_id'" | grep -q 1; then
        echo "Orphaned directory: $dir"
        # rm -rf "$dir"  # Uncomment to delete
    fi
done
```

## Testing Strategy

### Unit Tests
- **MetadataService**: `tests/unit/test_metadata_service.py`
- **ImageService**: `tests/unit/test_image_service.py`
- **YouTubeService**: Extensions tested in existing unit tests

### Integration Tests  
- **Complete Workflow**: `tests/integration/test_metadata_workflow.py`
- **API Endpoints**: Enhanced existing API tests
- **Error Scenarios**: Comprehensive failure mode testing

### Test Coverage Requirements
- **Unit tests**: >95% code coverage for new services
- **Integration tests**: All happy path and error scenarios
- **Performance tests**: Verify <30 second requirement
- **Security tests**: Path traversal, malicious URLs, oversized files

## Monitoring and Metrics

### Key Metrics to Track

1. **Success Rate**: Percentage of successful metadata extractions
2. **Processing Time**: Average time per metadata extraction  
3. **Error Distribution**: Breakdown of error types and frequencies
4. **Storage Usage**: Directory sizes and growth rates
5. **Image Download Success**: Success rate for cover/backdrop downloads

### Health Checks

```python
# Add to existing health check endpoint
def metadata_health_check():
    failed_count = db.query(Channel).filter(
        Channel.metadata_status == 'failed'
    ).count()
    
    stuck_count = db.query(Channel).filter(
        Channel.metadata_status == 'refreshing',
        Channel.last_metadata_update < datetime.utcnow() - timedelta(hours=1)
    ).count()
    
    return {
        'failed_metadata_count': failed_count,
        'stuck_metadata_count': stuck_count,
        'media_directory_exists': os.path.exists(settings.media_directory),
        'media_directory_writable': os.access(settings.media_directory, os.W_OK)
    }
```

## Future Enhancements

### Planned Improvements

1. **Metadata Refresh Scheduling**
   - Automatic periodic refresh (daily/weekly)
   - Configurable refresh intervals per channel
   - Batch processing for efficiency

2. **Enhanced Error Recovery**
   - Automatic retry with exponential backoff
   - Dead letter queue for persistent failures
   - Better error categorization and handling

3. **Performance Optimizations**  
   - Parallel metadata processing
   - Image CDN integration
   - Metadata caching strategies

4. **Additional Metadata**
   - Channel statistics tracking
   - Subscriber count history
   - Upload frequency analysis

### Migration Considerations

- **Backwards Compatibility**: New fields are nullable, existing code unaffected
- **Data Migration**: Existing channels will have `metadata_status = 'pending'`
- **Gradual Rollout**: Can enable metadata processing per channel
- **Storage Planning**: Estimate ~5KB per channel + image sizes (typically <500KB total)

## Conclusion

The Channel Metadata Management feature provides a robust, secure, and efficient system for organizing YouTube channel data. The implementation follows defensive coding practices with comprehensive error handling, security measures, and performance optimizations.

Key benefits:
- **Size Efficiency**: 99.98% reduction in metadata file size
- **Robust Error Handling**: Graceful failure modes with automatic rollback
- **Security Focus**: URL validation, path sanitization, size limits
- **Performance**: <30 second processing time per channel
- **Maintainability**: Comprehensive testing and documentation