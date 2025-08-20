# Video Download User Guide

This guide explains how the video download system works and how to troubleshoot common issues.

## How Download Behavior Works

### Automatic Download Process

**Triggered After Metadata**: Video downloads automatically start after successful channel metadata extraction during channel creation

**Sequential Processing**: Downloads happen one video at a time per channel to avoid overwhelming your system and respecting YouTube's rate limits

**Recent Videos Only**: Uses lightweight flat-playlist queries to get the most recent X videos (based on your channel limit setting) efficiently

**Duplicate Prevention**: Uses `archive.txt` to remember what's already downloaded - won't re-download the same video

**Smart Skipping**: If a channel has 50 videos but your limit is 10, only downloads the 10 most recent ones

**Optimized Querying**: Uses the equivalent of `yt-dlp --flat-playlist` for fast video discovery without triggering bot detection

### Manual Download Triggers

- Click the download button (⬇️) on any channel card in the web UI
- Downloads start immediately and you'll see status updates
- Green success message shows how many videos were downloaded
- Red error message shows if something went wrong

### File Organization

Videos are organized in a Jellyfin-compatible structure:

```
/media/
  Channel Name [CHANNEL_ID]/
    2025/
      Channel Name - 20250120 - Video Title [VIDEO_ID]/
        Channel Name - 20250120 - Video Title [VIDEO_ID].mkv
        Channel Name - 20250120 - Video Title [VIDEO_ID].info.json
        Channel Name - 20250120 - Video Title [VIDEO_ID].webp (thumbnail)
        Channel Name - 20250120 - Video Title [VIDEO_ID].en.vtt (subtitles)
```

### What Gets Downloaded

- ✅ Best available video quality (or your configured preference)
- ✅ Audio track merged into single file
- ✅ Video thumbnail as separate image
- ✅ Video metadata (title, description, upload date)
- ✅ English and Spanish subtitles when available
- ✅ All embedded in the video file for media server compatibility

## Troubleshooting Common Issues

### "Channel is disabled" Error

**Problem**: Trying to download from a disabled channel

**Solution**: Enable the channel in the web UI first, then try downloading

### "Channel not found" Error

**Problem**: Channel ID doesn't exist in your database

**Solution**: Add the channel through the web UI before trying to download

### "Network error while starting download"

**Problem**: Internet connection or YouTube accessibility issues

**Solution**: 
- Check your internet connection
- Try again in a few minutes (YouTube may be rate limiting)
- Verify the channel URL is still valid

### "Video unavailable" Errors

**Problem**: Individual videos are private, deleted, or geo-blocked

**Solution**: This is normal - the system will skip unavailable videos and continue downloading others

### Downloads Take Forever

**Problem**: Large videos or slow internet

**Solution**: 
- This is normal for high-quality videos
- Check Docker logs for progress: `docker compose -f docker-compose.dev.yml logs backend`
- Consider lowering quality preset for faster downloads

### "Storage space" Issues

**Problem**: Not enough disk space for downloads

**Solution**:
- Clean up old videos manually
- Reduce channel limits to keep fewer videos
- Monitor storage in your Docker host system

### Age-Restricted Content

**Problem**: Can't download age-restricted videos

**Solution**: 
- Export cookies from your browser when logged into YouTube
- Save as `cookies.txt` in the config directory
- Restart the application

### "HTTP Error 403: Forbidden" in Logs

**Problem**: Seeing repeated `[download] Got error: HTTP Error 403: Forbidden` in logs

**Cause**: YouTube is blocking requests due to rate limiting or bot detection

**Solutions**:
1. **Use Cookies**: Export cookies from your browser (see Age-Restricted Content above) - most effective solution
2. **Wait and Retry**: Often resolves itself after 5-10 minutes
3. **Reduce Frequency**: Space out channel additions and download triggers
4. **Check Rate Limits**: Avoid rapid successive download attempts

**Note**: The system uses optimized flat-playlist queries to minimize bot detection during video discovery. The download phase uses full anti-bot headers and retry logic. Individual 403 errors don't stop the overall process - the system will continue and skip problematic videos.

**Recent Improvements**: The system now separates lightweight video querying from heavy video downloading, significantly reducing 403 errors during the discovery phase.

## Monitoring Downloads

### Checking Download Status

**Web UI**: Green/red status messages appear at the bottom of channel list

**API**: `GET /api/v1/channels/{id}/downloads` for detailed history

**Logs**: `docker compose -f docker-compose.dev.yml logs backend` for technical details

### Understanding Download History

**Videos Found**: How many recent videos the channel has

**Videos Downloaded**: How many were actually downloaded (new ones)

**Videos Skipped**: How many were already downloaded previously

**Status**: `completed` (success), `failed` (error), `running` (in progress)

## API Usage Examples

### Manual Download Triggers

```bash
# Trigger download for specific channel
curl -X POST http://localhost:8000/api/v1/channels/1/download

# Check download status  
curl http://localhost:8000/api/v1/channels/1/downloads

# View download history
curl http://localhost:8000/api/v1/channels/1/download-history
```

### Response Examples

**Successful Download Trigger**:
```json
{
  "success": true,
  "videos_downloaded": 3,
  "error_message": null,
  "download_history_id": 456
}
```

**No New Videos**:
```json
{
  "success": true,
  "videos_downloaded": 0,
  "error_message": null,
  "download_history_id": 457
}
```

**Download Failure**:
```json
{
  "success": false,
  "videos_downloaded": 0,
  "error_message": "Channel not found",
  "download_history_id": null
}
```