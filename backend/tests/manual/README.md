# Manual Testing Scripts

This directory contains manual testing scripts for the ChannelFinWatcher backend services. These scripts are designed to be run inside the Docker container for testing specific functionality.

## Available Tests

### 1. Metadata Extraction Comparison (`test_metadata_comparison.py`)

**Purpose**: Compare the two metadata extraction methods in YouTubeService to understand their differences in performance, data structure, and use cases.

**What it tests**:
- `extract_channel_info()` - Lightweight method using `extract_flat: True`
- `extract_channel_metadata_full()` - Comprehensive method using `extract_flat: False`

**Methods compared**:

| Method | extract_flat | Speed | Data Size | Use Case |
|--------|--------------|-------|-----------|----------|
| `extract_channel_info()` | `True` | Fast | Small (~1KB) | Basic validation, duplicate detection |
| `extract_channel_metadata_full()` | `False` | Slower | Large (~5KB after cleanup) | Complete metadata, file creation |

## Running the Tests

### Prerequisites
- Docker containers must be running (`docker compose -f docker-compose.dev.yml up`)
- Backend container should be accessible as `channelfinwatcher-backend-1`

### Commands

#### Run Metadata Comparison Test

```bash
# From host machine
docker exec -it channelfinwatcher-backend-1 python /app/tests/manual/test_metadata_comparison.py

# Or enter the container first
docker exec -it channelfinwatcher-backend-1 bash
cd /app/tests/manual
python test_metadata_comparison.py
```

#### View Generated Output Files

```bash
# View basic metadata output
docker exec -it channelfinwatcher-backend-1 cat /app/tests/manual/basic_info.json

# View full metadata output
docker exec -it channelfinwatcher-backend-1 cat /app/tests/manual/full_metadata.json

# Compare file sizes
docker exec -it channelfinwatcher-backend-1 ls -la /app/tests/manual/temp_metadata/
```

## Test Configuration

### Changing Test Channel

Edit the `TEST_CHANNEL_URL` variable in the test scripts:

```python
# Default
TEST_CHANNEL_URL = "https://www.youtube.com/@MrBeast"

# Change to any YouTube channel
TEST_CHANNEL_URL = "https://www.youtube.com/@MrsRachel"
TEST_CHANNEL_URL = "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw"  # YouTube handle
```

### Output Files

The metadata comparison test generates:

| File | Description | Location |
|------|-------------|----------|
| `basic_info.json` | Output from `extract_channel_info()` | `/app/tests/manual/` |
| `full_metadata.json` | Output from `extract_channel_metadata_full()` | `/app/tests/manual/` |
| `*.info.json` | yt-dlp generated metadata file | `/app/tests/manual/temp_metadata/` |

## Expected Results

### Performance Differences

**extract_channel_info()**:
- ⚡ Fast execution (typically < 2 seconds)
- 📦 Small data payload (~500-1000 characters)
- 🎯 Essential fields only (channel_id, name, subscriber_count)
- 🔧 Optimized for validation and duplicate detection

**extract_channel_metadata_full()**:
- 🐌 Slower execution (typically 3-10 seconds)
- 📋 Comprehensive data (~5000+ characters)
- 💾 Creates persistent JSON file
- 🎬 Full channel metadata for media server organization

### Field Comparison

**Common Fields**: Both methods provide these core fields:
- `channel_id` - YouTube's unique identifier
- `name` / `title` - Channel name
- `description` - Channel description

**Basic Only**: Fields unique to `extract_channel_info()`:
- Typically none (basic is a subset of full)

**Full Only**: Fields unique to `extract_channel_metadata_full()`:
- `epoch` - Timestamp of metadata extraction
- `uploader_id`, `uploader_url` - Additional uploader info
- `playlist_count` - Video count
- Various thumbnail URLs and technical metadata

## Troubleshooting

### Common Issues

1. **Container not found**:
   ```bash
   # Check container name
   docker ps
   # Use actual container name if different
   docker exec -it <actual-container-name> python /app/tests/manual/test_metadata_comparison.py
   ```

2. **Permission errors**:
   ```bash
   # Ensure test directory exists and is writable
   docker exec -it channelfinwatcher-backend-1 mkdir -p /app/tests/manual/temp_metadata
   ```

3. **Module import errors**:
   - Ensure you're running from inside the container where Python path is set up
   - Check that backend dependencies are installed

4. **YouTube access issues**:
   - Network connectivity problems
   - Rate limiting (wait and retry)
   - Private or deleted channels
   - Geoblocked content

### Debugging

Enable verbose logging by modifying the test script:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or check container logs:

```bash
# View backend container logs
docker logs channelfinwatcher-backend-1 -f
```

## Adding New Tests

To add new manual tests to this directory:

1. Create a new Python script following the naming convention `test_*.py`
2. Add proper docstrings and usage instructions
3. Update this README with the new test description
4. Ensure the test can run in the Docker environment
5. Include appropriate error handling and output formatting

### Test Script Template

```python
#!/usr/bin/env python3
"""
Description of what this test does.

Usage:
    docker exec -it channelfinwatcher-backend-1 python /app/tests/manual/test_example.py
"""

import sys
sys.path.insert(0, '/app')

from app.some_service import some_service

def main():
    print("🧪 Test Name")
    print("=" * 50)
    # Test implementation here

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
```