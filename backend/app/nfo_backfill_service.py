"""
NFO Backfill Background Job Service

This service handles retroactive NFO file generation for existing channels that
were added before the NFO generation feature was implemented.

Why Backfill?
=============
The NFO generation feature is now integrated into the download workflow (Story 008),
but existing channels (from before this feature) need their NFO files generated
retroactively. The database migration sets nfo_last_generated = NULL for all
existing channels, which serves as a flag indicating "needs backfill".

Architecture:
=============
- Sequential processing (one channel at a time to avoid disk I/O overload)
- Idempotent (can be run multiple times safely - only processes NULL channels)
- Resumable (interrupted jobs can continue from where they left off)
- Progress tracking (in-memory state + database timestamps)
- Pause/resume functionality (global flag checked before each channel)

Key Design Decisions:
=====================
1. Sequential Processing: Process one channel at a time to prevent disk I/O overload
2. Database Flag: nfo_last_generated = NULL indicates "needs backfill"
3. Atomic Completion: Only mark channel as completed after all NFOs generated
4. Error Isolation: One channel failure doesn't stop the entire job
5. Reuse NFOService: Don't duplicate NFO generation logic

Integration:
============
This service integrates with:
- NFOService: Reuses existing NFO generation logic
- APScheduler: Runs as a background job (async execution)
- Database: Tracks progress via nfo_last_generated timestamp
- API: Exposes control endpoints for start/pause/resume/status

Usage:
======
    from app.nfo_backfill_service import nfo_backfill_service

    # Start backfill job
    await nfo_backfill_service.start_backfill()

    # Check status
    status = nfo_backfill_service.get_status()

    # Pause/resume
    nfo_backfill_service.pause()
    await nfo_backfill_service.resume()
"""

import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Channel, ApplicationSettings
from app.nfo_service import get_nfo_service

logger = logging.getLogger(__name__)


class NFOBackfillService:
    """
    Service for retroactive NFO file generation on existing channels.

    Why a service class?
    - Encapsulates backfill state management (current channel, progress, pause flag)
    - Allows single global instance with shared state
    - Makes testing easier (can create test instances with mock dependencies)
    - Follows existing pattern in codebase (SchedulerService, VideoDownloadService)
    """

    def __init__(self):
        """
        Initialize backfill service with default state.

        State Management:
        - running: Whether backfill job is currently executing
        - paused: Whether job should pause before next channel
        - current_channel_id: ID of channel currently being processed
        - total_channels: Total channels needing backfill
        - channels_processed: Number of channels completed
        - files_created: Total NFO files created across all channels
        - files_skipped: Total NFO files skipped (already exist)
        - files_failed: Total NFO files that failed to generate
        """
        self.running = False
        self.paused = False
        self.current_channel_id: Optional[int] = None
        self.current_channel_name: Optional[str] = None
        self.total_channels = 0
        self.channels_processed = 0
        self.files_created = 0
        self.files_skipped = 0
        self.files_failed = 0
        self.started_at: Optional[datetime] = None

        logger.info("NFOBackfillService initialized")

    # =========================================================================
    # PUBLIC API - CONTROL METHODS
    # =========================================================================

    async def start_backfill(self) -> Dict:
        """
        Start the NFO backfill process.

        This is the main entry point for starting backfill. It:
        1. Checks if backfill is already running
        2. Queries channels needing backfill (nfo_last_generated IS NULL)
        3. Processes each channel sequentially
        4. Returns summary statistics

        Returns:
            dict: Status with total_channels count

        Raises:
            RuntimeError: If backfill is already running

        Why async?
        - Allows integration with FastAPI async endpoints
        - Enables use of asyncio for background job management
        - Matches pattern in scheduled_download_job.py (async def)
        """
        if self.running:
            raise RuntimeError("Backfill job is already running")

        if self.paused:
            # Resume from paused state instead of starting fresh
            return await self.resume()

        logger.info("Starting NFO backfill job")

        # Reset state
        self.running = True
        self.paused = False
        self.channels_processed = 0
        self.files_created = 0
        self.files_skipped = 0
        self.files_failed = 0
        self.started_at = datetime.utcnow()

        # Get database session
        db = SessionLocal()

        try:
            # Query channels needing backfill
            # Why WHERE nfo_last_generated IS NULL?
            # - Migration sets this to NULL for existing channels
            # - New channels also start with NULL
            # - After backfill completes, we set it to current timestamp
            # - This makes backfill idempotent (can run multiple times safely)
            channels = db.query(Channel).filter(
                Channel.nfo_last_generated == None
            ).all()

            self.total_channels = len(channels)

            if not channels:
                logger.info("No channels need NFO backfill")
                self.running = False
                return {
                    "status": "completed",
                    "total_channels": 0,
                    "message": "No channels need backfill"
                }

            logger.info(f"Found {len(channels)} channels needing NFO backfill")

            # Process each channel sequentially
            # Why sequential? Prevents disk I/O overload from parallel processing
            for channel in channels:
                # Check pause flag before each channel
                if self.paused:
                    logger.info(f"Backfill paused at channel {self.channels_processed}/{self.total_channels}")
                    return {
                        "status": "paused",
                        "total_channels": self.total_channels,
                        "channels_processed": self.channels_processed
                    }

                # Process this channel
                await self._process_channel(channel, db)

            # Job completed
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            logger.info(
                f"NFO backfill completed in {elapsed:.1f}s: "
                f"{self.channels_processed}/{self.total_channels} channels processed, "
                f"{self.files_created} files created, "
                f"{self.files_skipped} skipped, "
                f"{self.files_failed} failed"
            )

            return {
                "status": "completed",
                "total_channels": self.total_channels,
                "channels_processed": self.channels_processed,
                "files_created": self.files_created,
                "files_skipped": self.files_skipped,
                "files_failed": self.files_failed,
                "elapsed_seconds": elapsed
            }

        except Exception as e:
            logger.error(f"NFO backfill job failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "channels_processed": self.channels_processed,
                "total_channels": self.total_channels
            }

        finally:
            self.running = False
            self.current_channel_id = None
            self.current_channel_name = None
            db.close()

    def pause(self) -> Dict:
        """
        Pause the currently running backfill job.

        The job will finish processing the current channel and then pause
        before starting the next channel. This allows graceful interruption
        without leaving a channel in a half-processed state.

        Returns:
            dict: Current status with pause confirmation

        Why not stop immediately?
        - Ensures current channel completes fully
        - Prevents partial NFO generation (all or nothing per channel)
        - Maintains database consistency (transaction commits)
        """
        if not self.running:
            return {
                "status": "idle",
                "message": "Backfill is not running"
            }

        logger.info("Pausing NFO backfill job (will pause after current channel)")
        self.paused = True

        return {
            "status": "pausing",
            "message": "Backfill will pause after current channel completes",
            "current_channel": self.current_channel_name,
            "channels_processed": self.channels_processed,
            "total_channels": self.total_channels
        }

    async def resume(self) -> Dict:
        """
        Resume a paused backfill job.

        Resumes processing from where it left off. The idempotent nature
        of backfill (based on NULL timestamps) means we can safely restart
        even if interrupted unexpectedly.

        Returns:
            dict: Resume confirmation with status

        Why idempotent?
        - Only processes channels WHERE nfo_last_generated IS NULL
        - Completed channels have timestamps set, so they're skipped
        - Can resume safely even after crashes or restarts
        """
        if not self.paused:
            # Start fresh backfill if not currently paused
            return await self.start_backfill()

        logger.info("Resuming paused NFO backfill job")
        self.paused = False
        self.running = True

        # Continue processing (will pick up where we left off)
        return await self.start_backfill()

    def get_status(self) -> Dict:
        """
        Get current backfill job status.

        Provides comprehensive status information for monitoring and UI display.

        Returns:
            dict: Current status with progress details

        Why in-memory state?
        - Faster than database queries for frequently-checked status
        - No database overhead for UI polling
        - Cleared on service restart (status becomes stale anyway)
        """
        return {
            "running": self.running,
            "paused": self.paused,
            "current_channel_id": self.current_channel_id,
            "current_channel_name": self.current_channel_name,
            "total_channels": self.total_channels,
            "channels_processed": self.channels_processed,
            "channels_remaining": self.total_channels - self.channels_processed,
            "files_created": self.files_created,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "started_at": self.started_at.isoformat() if self.started_at else None
        }

    def get_channels_needing_backfill(self) -> int:
        """
        Get count of channels needing NFO backfill.

        Queries database for channels with nfo_last_generated = NULL.
        Useful for UI to show backfill status before starting.

        Returns:
            int: Number of channels needing backfill

        Why separate method?
        - Can be called before starting backfill
        - Doesn't require job to be running
        - Provides accurate count from database (not cached state)
        """
        db = SessionLocal()
        try:
            count = db.query(Channel).filter(
                Channel.nfo_last_generated == None
            ).count()
            return count
        finally:
            db.close()

    async def regenerate_channel_nfo(self, channel_id: int) -> Dict:
        """
        Regenerate all NFO files for a specific channel.

        This is a public method that allows regenerating NFO files for a single
        channel without running the full backfill job. Useful for:
        - Manual NFO regeneration via API
        - Fixing corrupted NFO files
        - Updating NFO files after metadata changes

        Args:
            channel_id: Database ID of channel to process

        Returns:
            Dict with results:
            {
                "success": bool,
                "channel_name": str,
                "files_created": int,
                "files_skipped": int,
                "files_failed": int,
                "error": Optional[str]
            }

        Example:
            result = await nfo_backfill_service.regenerate_channel_nfo(123)
            if result["success"]:
                print(f"Created {result['files_created']} NFO files")
        """
        db = SessionLocal()
        try:
            # Find channel
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel with ID {channel_id} not found",
                    "files_created": 0,
                    "files_skipped": 0,
                    "files_failed": 0
                }

            # Verify channel directory exists
            if not channel.directory_path or not os.path.exists(channel.directory_path):
                return {
                    "success": False,
                    "channel_name": channel.name,
                    "error": f"Channel directory not found: {channel.directory_path}",
                    "files_created": 0,
                    "files_skipped": 0,
                    "files_failed": 0
                }

            logger.info(f"Regenerating NFO files for channel: {channel.name} (ID: {channel_id})")

            # Query the overwrite setting from database
            overwrite_setting = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == 'nfo_overwrite_existing'
            ).first()
            overwrite = overwrite_setting.value == "true" if overwrite_setting else False

            logger.info(f"NFO overwrite setting: {overwrite}")

            # Track counters for this operation
            files_created = 0
            files_skipped = 0
            files_failed = 0
            # NEW: Track failed files with their error messages for detailed reporting
            failed_files = []

            channel_dir = channel.directory_path

            # Step 1: Generate tvshow.nfo (channel-level metadata)
            tvshow_success, tvshow_error = await self._generate_tvshow_nfo(channel, channel_dir, overwrite)
            if tvshow_success:
                files_created += 1
            elif tvshow_success is False:
                files_failed += 1
                failed_files.append({
                    "file": "tvshow.nfo",
                    "path": os.path.join(channel_dir, "tvshow.nfo"),
                    "error": tvshow_error or "Unknown error"
                })
            else:
                files_skipped += 1

            # Step 2: Generate season.nfo for each year directory
            year_dirs = self._discover_year_directories(channel_dir)
            for year_dir in year_dirs:
                season_success, season_error = await self._generate_season_nfo(year_dir, overwrite)
                if season_success:
                    files_created += 1
                elif season_success is False:
                    files_failed += 1
                    season_nfo_path = os.path.join(year_dir, "season.nfo")
                    failed_files.append({
                        "file": f"season.nfo ({os.path.basename(year_dir)})",
                        "path": season_nfo_path,
                        "error": season_error or "Unknown error"
                    })
                else:
                    files_skipped += 1

            # Step 3: Generate episode.nfo for each video
            video_info_files = self._discover_videos_for_backfill(channel_dir)
            logger.info(f"Found {len(video_info_files)} videos for channel {channel.name}")

            for info_json_path in video_info_files:
                episode_success, episode_error = await self._generate_episode_nfo(info_json_path, channel, overwrite)
                if episode_success:
                    files_created += 1
                elif episode_success is False:
                    files_failed += 1
                    # Get the video file path for better error reporting
                    video_path = self._get_video_file_path(info_json_path)
                    video_filename = os.path.basename(video_path) if video_path else info_json_path
                    failed_files.append({
                        "file": f"episode.nfo for {video_filename}",
                        "path": video_path or info_json_path,
                        "error": episode_error or "Unknown error"
                    })
                else:
                    # None means file already exists (skipped)
                    files_skipped += 1

            # Update timestamp to mark as regenerated
            channel.nfo_last_generated = datetime.utcnow()
            db.commit()

            # Enhanced logging: Show summary and details of failures
            logger.info(
                f"Completed NFO regeneration for channel {channel.name}: "
                f"{files_created} created, {files_skipped} skipped, {files_failed} failed"
            )

            # NEW: Log detailed failure information if there were any failures
            if failed_files:
                logger.error(f"Failed to generate {len(failed_files)} NFO file(s) for channel {channel.name}:")
                for failure in failed_files:
                    logger.error(f"  - {failure['file']}: {failure['error']}")
                    logger.error(f"    Path: {failure['path']}")

            return {
                "success": True,
                "channel_name": channel.name,
                "files_created": files_created,
                "files_skipped": files_skipped,
                "files_failed": files_failed,
                "error": None
            }

        except Exception as e:
            logger.error(f"Error regenerating NFO for channel {channel_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "files_created": 0,
                "files_skipped": 0,
                "files_failed": 0
            }
        finally:
            db.close()

    # =========================================================================
    # PRIVATE METHODS - INTERNAL PROCESSING
    # =========================================================================

    async def _process_channel(self, channel: Channel, db: Session) -> None:
        """
        Process NFO backfill for a single channel.

        This method:
        1. Generates tvshow.nfo (channel-level metadata)
        2. Discovers all year directories and generates season.nfo for each
        3. Discovers all videos and generates episode.nfo for each
        4. Updates nfo_last_generated timestamp if successful

        Args:
            channel: Channel database object
            db: Database session

        Why sequential steps?
        - tvshow.nfo first (establishes show metadata)
        - season.nfo for each year (establishes season structure)
        - episode.nfo for each video (establishes episode details)
        - This mirrors the Jellyfin metadata hierarchy

        Error Handling:
        - Logs errors but continues with remaining channels
        - Only sets timestamp if channel completes successfully
        - Individual file failures are logged but don't fail entire channel
        """
        self.current_channel_id = channel.id
        self.current_channel_name = channel.name

        logger.info(f"Processing NFO backfill for channel: {channel.name} (ID: {channel.id})")

        try:
            # Verify channel directory exists
            if not channel.directory_path or not os.path.exists(channel.directory_path):
                logger.warning(f"Channel directory not found for {channel.name}: {channel.directory_path}")
                self.channels_processed += 1
                return

            channel_dir = channel.directory_path

            # Initialize counters for this channel
            channel_files_created = 0
            channel_files_skipped = 0
            channel_files_failed = 0
            # Track failed files with error details for this channel
            failed_files = []

            # Step 1: Generate tvshow.nfo (channel-level metadata)
            tvshow_success, tvshow_error = await self._generate_tvshow_nfo(channel, channel_dir)
            if tvshow_success:
                channel_files_created += 1
            elif tvshow_success is False:
                channel_files_failed += 1
                failed_files.append({
                    "file": "tvshow.nfo",
                    "path": os.path.join(channel_dir, "tvshow.nfo"),
                    "error": tvshow_error or "Unknown error"
                })
            else:
                channel_files_skipped += 1

            # Step 2: Generate season.nfo for each year directory
            year_dirs = self._discover_year_directories(channel_dir)
            for year_dir in year_dirs:
                season_success, season_error = await self._generate_season_nfo(year_dir)
                if season_success:
                    channel_files_created += 1
                elif season_success is False:
                    channel_files_failed += 1
                    season_nfo_path = os.path.join(year_dir, "season.nfo")
                    failed_files.append({
                        "file": f"season.nfo ({os.path.basename(year_dir)})",
                        "path": season_nfo_path,
                        "error": season_error or "Unknown error"
                    })
                else:
                    channel_files_skipped += 1

            # Step 3: Generate episode.nfo for each video
            video_info_files = self._discover_videos_for_backfill(channel_dir)
            logger.info(f"Found {len(video_info_files)} videos for channel {channel.name}")

            for info_json_path in video_info_files:
                episode_success, episode_error = await self._generate_episode_nfo(info_json_path, channel)
                if episode_success:
                    channel_files_created += 1
                elif episode_success is False:
                    channel_files_failed += 1
                    video_path = self._get_video_file_path(info_json_path)
                    video_filename = os.path.basename(video_path) if video_path else info_json_path
                    failed_files.append({
                        "file": f"episode.nfo for {video_filename}",
                        "path": video_path or info_json_path,
                        "error": episode_error or "Unknown error"
                    })
                else:
                    # None means file already exists (skipped)
                    channel_files_skipped += 1

            # Update global counters
            self.files_created += channel_files_created
            self.files_skipped += channel_files_skipped
            self.files_failed += channel_files_failed

            # Mark channel as completed (set timestamp)
            # Why update here? Only after all NFO files generated successfully
            # (or with minimal failures - we still mark as done to avoid re-processing)
            channel.nfo_last_generated = datetime.utcnow()
            db.commit()

            logger.info(
                f"Completed NFO backfill for channel {channel.name}: "
                f"{channel_files_created} created, {channel_files_skipped} skipped, {channel_files_failed} failed"
            )

            # Log detailed failure information if there were any failures
            if failed_files:
                logger.error(f"Failed to generate {len(failed_files)} NFO file(s) for channel {channel.name}:")
                for failure in failed_files:
                    logger.error(f"  - {failure['file']}: {failure['error']}")
                    logger.error(f"    Path: {failure['path']}")

            self.channels_processed += 1

        except Exception as e:
            logger.error(f"Error processing channel {channel.name}: {e}")
            # Don't mark as completed - will be retried on next backfill run
            self.channels_processed += 1  # Still increment to continue with other channels

    async def _generate_tvshow_nfo(self, channel: Channel, channel_dir: str, overwrite: bool = False) -> tuple:
        """
        Generate tvshow.nfo for channel.

        Args:
            channel: Channel database object
            channel_dir: Path to channel directory
            overwrite: If True, overwrite existing NFO files; if False, skip existing files

        Returns:
            tuple: (success: Optional[bool], error: Optional[str])
                - (True, None) if successful
                - (False, error_msg) if failed
                - (None, None) if skipped (already exists and overwrite=False)
        """
        nfo_service = get_nfo_service()

        # Check if tvshow.nfo already exists
        tvshow_nfo_path = os.path.join(channel_dir, 'tvshow.nfo')
        if os.path.exists(tvshow_nfo_path) and not overwrite:
            logger.debug(f"tvshow.nfo already exists for {channel.name}, skipping")
            return (None, None)  # Skipped

        # Find channel metadata file
        # Why metadata_path? This is where channel .info.json is stored
        if not channel.metadata_path or not os.path.exists(channel.metadata_path):
            error_msg = f"Channel metadata not found: {channel.metadata_path}"
            logger.error(f"Failed to generate tvshow.nfo for {channel.name}: {error_msg}")
            return (False, error_msg)

        # Generate tvshow.nfo
        success, error = nfo_service.generate_tvshow_nfo(channel.metadata_path, channel_dir)

        if not success:
            logger.error(f"Failed to generate tvshow.nfo for {channel.name}: {error}")
            return (False, error)

        logger.debug(f"Generated tvshow.nfo for {channel.name}")
        return (True, None)

    async def _generate_season_nfo(self, year_dir: str, overwrite: bool = False) -> tuple:
        """
        Generate season.nfo for year directory.

        Args:
            year_dir: Path to year directory (e.g., "/media/.../2021/")
            overwrite: If True, overwrite existing NFO files; if False, skip existing files

        Returns:
            tuple: (success: Optional[bool], error: Optional[str])
                - (True, None) if successful
                - (False, error_msg) if failed
                - (None, None) if skipped (already exists and overwrite=False)
        """
        nfo_service = get_nfo_service()

        # Check if season.nfo already exists
        season_nfo_path = os.path.join(year_dir, 'season.nfo')
        if os.path.exists(season_nfo_path) and not overwrite:
            logger.debug(f"season.nfo already exists in {year_dir}, skipping")
            return (None, None)  # Skipped

        # Generate season.nfo
        success, error = nfo_service.generate_season_nfo(year_dir)

        if not success:
            logger.error(f"Failed to generate season.nfo for {year_dir}: {error}")
            return (False, error)

        logger.debug(f"Generated season.nfo for {year_dir}")
        return (True, None)

    async def _generate_episode_nfo(self, info_json_path: str, channel: Channel, overwrite: bool = False) -> tuple:
        """
        Generate episode.nfo for video.

        Args:
            info_json_path: Path to video .info.json file
            channel: Channel database object
            overwrite: If True, overwrite existing NFO files; if False, skip existing files

        Returns:
            tuple: (success: Optional[bool], error: Optional[str])
                - (True, None) if successful
                - (False, error_msg) if failed
                - (None, None) if skipped (already exists and overwrite=False)
        """
        nfo_service = get_nfo_service()

        # Derive video file path from info.json path
        # Example: video.info.json → video.mkv
        video_file_path = self._get_video_file_path(info_json_path)

        if not video_file_path:
            error_msg = f"No video file found for {info_json_path}"
            logger.error(f"Failed to generate episode.nfo: {error_msg}")
            return (False, error_msg)

        # Check if episode.nfo already exists
        nfo_path = video_file_path.replace('.mkv', '.nfo').replace('.mp4', '.nfo').replace('.webm', '.nfo')
        if os.path.exists(nfo_path) and not overwrite:
            logger.debug(f"episode.nfo already exists for {video_file_path}, skipping")
            return (None, None)  # Skipped

        # Generate episode.nfo
        success, error = nfo_service.generate_episode_nfo(video_file_path, channel)

        if not success:
            logger.error(f"Failed to generate episode.nfo for {video_file_path}: {error}")
            return (False, error)

        logger.debug(f"Generated episode.nfo for {video_file_path}")
        return (True, None)

    def _discover_year_directories(self, channel_dir: str) -> List[str]:
        """
        Discover all year directories in channel directory.

        Year directories are folders with 4-digit names (e.g., "2021", "2022").

        Args:
            channel_dir: Path to channel root directory

        Returns:
            list: Paths to year directories (sorted)

        Why year directories?
        - ChannelFinWatcher organizes videos by upload year
        - Each year becomes a "season" in Jellyfin
        - Need to generate season.nfo for each year
        """
        year_dirs = []

        if not os.path.exists(channel_dir):
            return year_dirs

        for item in os.listdir(channel_dir):
            item_path = os.path.join(channel_dir, item)

            # Check if it's a directory and has 4-digit name
            if os.path.isdir(item_path) and item.isdigit() and len(item) == 4:
                year_dirs.append(item_path)

        return sorted(year_dirs)

    def _discover_videos_for_backfill(self, channel_dir: str) -> List[str]:
        """
        Find all videos in channel directory that need NFO files.

        Implementation from story-008 docs (lines 700-740).

        Args:
            channel_dir: Absolute path to channel root directory

        Returns:
            list: Paths to .info.json files for all episodes (not channel metadata)

        Note:
            Only returns .info.json files that have corresponding video files.
            Skips channel-level info.json (which has no video file).

        Why this function?
        - Walks directory tree recursively to find all videos
        - Distinguishes episode .info.json (has video) from channel .info.json (no video)
        - Returns sorted list for consistent processing order
        """
        info_json_files = []

        # Walk channel directory recursively looking for .info.json files
        for root, dirs, files in os.walk(channel_dir):
            for file in files:
                # Skip hidden files and non-json files
                if not file.endswith('.info.json') or file.startswith('.'):
                    continue

                info_path = os.path.join(root, file)

                # Check if corresponding video file exists
                # Try common video extensions
                base_path = info_path.replace('.info.json', '')
                video_extensions = ['.mkv', '.mp4', '.webm', '.m4v']

                has_video = any(
                    os.path.exists(f"{base_path}{ext}")
                    for ext in video_extensions
                )

                if has_video:
                    info_json_files.append(info_path)

        return sorted(info_json_files)  # Consistent ordering

    def _get_video_file_path(self, info_json_path: str) -> Optional[str]:
        """
        Get video file path from .info.json path.

        Args:
            info_json_path: Path to .info.json file

        Returns:
            str: Path to video file, or None if not found

        Why try multiple extensions?
        - yt-dlp can download in various formats (mkv, mp4, webm, m4v)
        - Need to find the actual file regardless of extension
        """
        base_path = info_json_path.replace('.info.json', '')
        video_extensions = ['.mkv', '.mp4', '.webm', '.m4v']

        for ext in video_extensions:
            video_path = f"{base_path}{ext}"
            if os.path.exists(video_path):
                return video_path

        return None


# =========================================================================
# GLOBAL SERVICE INSTANCE
# =========================================================================

# Global backfill service instance (singleton pattern)
# Why singleton? Maintains shared state across API calls (running, paused, progress)
nfo_backfill_service = NFOBackfillService()
