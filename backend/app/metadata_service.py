"""Metadata management service with comprehensive error handling and recovery."""
import os
import re
import logging
import shutil
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from pathlib import Path
from sqlalchemy.orm import Session

from app.youtube_service import youtube_service
from app.image_service import image_service
from app.models import Channel
from app.config import get_settings

logger = logging.getLogger(__name__)


class MetadataService:
    """
    Service for managing channel metadata with comprehensive error handling.
    
    This service orchestrates the complete metadata extraction workflow:
    1. Extract channel metadata using YouTubeService
    2. Create organized directory structure
    3. Download cover and backdrop images
    4. Handle errors and partial failures gracefully
    5. Provide rollback mechanisms for failed operations
    
    Key Features:
    - Comprehensive error handling and rollback
    - Partial failure recovery (metadata succeeds, images fail)
    - Duplicate channel detection
    - Directory structure validation
    - Atomic operations where possible
    """
    
    def __init__(self):
        """Initialize metadata service with required dependencies."""
        self.settings = get_settings()
        self.media_root = self.settings.media_dir
    
    def process_channel_metadata(self, db: Session, channel: Channel, url: str) -> Tuple[bool, List[str]]:
        """
        Process complete metadata extraction workflow for a channel.
        
        This is the main entry point for metadata processing. It handles
        the complete workflow including error recovery and rollback.
        
        Args:
            db: Database session
            channel: Channel model instance
            url: YouTube channel URL
            
        Returns:
            Tuple of (success, error_messages)
        """
        errors = []
        rollback_actions = []
        
        try:
            # Update status to processing
            channel.metadata_status = "refreshing"
            db.commit()
            
            # Step 1: Create directory structure
            directory_success, directory_path, directory_error = self._create_channel_directory(url)
            if not directory_success:
                errors.append(f"Directory creation failed: {directory_error}")
                channel.metadata_status = "failed"
                db.commit()
                return False, errors
            
            rollback_actions.append(('remove_directory', directory_path))
            
            # Step 2: Extract and save metadata
            metadata_success, metadata, metadata_error = youtube_service.extract_channel_metadata_full(url, directory_path)
            if not metadata_success:
                errors.append(f"Metadata extraction failed: {metadata_error}")
                self._rollback_operations(rollback_actions)
                channel.metadata_status = "failed"
                db.commit()
                return False, errors
            
            # Step 3: Check for duplicate channel_id
            extracted_channel_id = metadata.get('channel_id') or metadata.get('id')
            if not extracted_channel_id:
                errors.append("Could not extract channel ID from metadata")
                self._rollback_operations(rollback_actions)
                channel.metadata_status = "failed"
                db.commit()
                return False, errors
            
            # Check for duplicates (excluding current channel)
            duplicate_check = db.query(Channel).filter(
                Channel.channel_id == extracted_channel_id,
                Channel.id != channel.id
            ).first()
            
            if duplicate_check:
                errors.append(f"Channel already being monitored: {duplicate_check.name}")
                self._rollback_operations(rollback_actions)
                channel.metadata_status = "failed"
                db.commit()
                return False, errors
            
            # Step 4: Download images (non-blocking - partial failure allowed)
            image_success, image_paths, image_errors = image_service.download_channel_images(metadata, directory_path)
            if not image_success:
                logger.warning(f"Image download failed for channel {channel.id}: {image_errors}")
                # Don't fail the entire operation, just log warnings
                errors.extend([f"Image download: {err}" for err in image_errors])
            
            # Step 5: Update channel record with successful metadata
            self._update_channel_record(db, channel, metadata, directory_path, image_paths)
            
            # Clear rollback actions since operation succeeded
            rollback_actions.clear()
            
            logger.info(f"Successfully processed metadata for channel: {channel.name} ({channel.channel_id})")
            return True, errors  # May have image warnings but overall success
            
        except Exception as e:
            logger.error(f"Unexpected error processing metadata for channel {channel.id}: {e}")
            errors.append(f"Unexpected error: {e}")
            
            # Rollback any partial operations
            self._rollback_operations(rollback_actions)
            
            # Update channel status
            channel.metadata_status = "failed"
            db.commit()
            
            return False, errors
    
    def refresh_channel_metadata(self, db: Session, channel: Channel) -> Tuple[bool, List[str]]:
        """
        Refresh metadata for existing channel without removing directory.
        
        Args:
            db: Database session
            channel: Existing channel to refresh
            
        Returns:
            Tuple of (success, error_messages)
        """
        errors = []
        
        try:
            # Ensure directory exists
            if not channel.directory_path or not os.path.exists(channel.directory_path):
                logger.warning(f"Directory missing for channel {channel.id}, creating new one")
                return self.process_channel_metadata(db, channel, channel.url)
            
            # Update status
            channel.metadata_status = "refreshing"
            db.commit()
            
            # Extract fresh metadata
            metadata_success, metadata, metadata_error = youtube_service.extract_channel_metadata_full(
                channel.url, channel.directory_path
            )
            
            if not metadata_success:
                errors.append(f"Metadata refresh failed: {metadata_error}")
                channel.metadata_status = "failed"
                db.commit()
                return False, errors
            
            # Download fresh images (overwrite existing)
            image_success, image_paths, image_errors = image_service.download_channel_images(
                metadata, channel.directory_path
            )
            
            if not image_success:
                logger.warning(f"Image refresh failed for channel {channel.id}: {image_errors}")
                errors.extend([f"Image refresh: {err}" for err in image_errors])
            
            # Update channel record
            self._update_channel_record(db, channel, metadata, channel.directory_path, image_paths)
            
            logger.info(f"Successfully refreshed metadata for channel: {channel.name}")
            return True, errors
            
        except Exception as e:
            logger.error(f"Unexpected error refreshing metadata for channel {channel.id}: {e}")
            channel.metadata_status = "failed"
            db.commit()
            return False, [f"Unexpected error: {e}"]
    
    def _create_channel_directory(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create organized directory structure for channel.
        
        Args:
            url: YouTube channel URL
            
        Returns:
            Tuple of (success, directory_path, error_message)
        """
        try:
            # Extract basic channel info to get name and ID
            success, channel_info, error = youtube_service.extract_channel_info(url)
            if not success:
                return False, None, f"Could not extract channel info: {error}"
            
            channel_name = channel_info['name']
            channel_id = channel_info['channel_id']
            
            # Generate directory name preserving original characters
            # Only remove characters that are truly unsafe for filesystems
            safe_name = re.sub(r'[<>:"/\\|?*]', '', channel_name)
            safe_name = re.sub(r'\.+$', '', safe_name)  # Remove trailing dots
            safe_name = safe_name.strip()
            directory_name = f"{safe_name} [{channel_id}]"
            directory_path = os.path.join(self.media_root, directory_name)
            
            # Create directory
            os.makedirs(directory_path, exist_ok=True)
            
            # Validate directory was created and is writable
            if not os.path.exists(directory_path):
                return False, None, "Directory was not created successfully"
            
            if not os.access(directory_path, os.W_OK):
                return False, None, "Directory is not writable"
            
            logger.info(f"Created channel directory: {directory_path}")
            return True, directory_path, None
            
        except Exception as e:
            logger.error(f"Error creating channel directory: {e}")
            return False, None, f"Directory creation error: {e}"
    
    def _update_channel_record(self, db: Session, channel: Channel, metadata: Dict, 
                              directory_path: str, image_paths: Dict[str, Optional[str]]):
        """
        Update channel database record with metadata information.
        
        Args:
            db: Database session
            channel: Channel model instance
            metadata: Extracted metadata
            directory_path: Path to channel directory
            image_paths: Paths to downloaded images
        """
        try:
            # Update channel fields
            channel.channel_id = metadata.get('channel_id') or metadata.get('id')
            channel.name = metadata.get('channel') or metadata.get('title')
            
            # Metadata paths
            channel.directory_path = directory_path
            
            # Find metadata JSON file
            safe_name = youtube_service._make_filesystem_safe(channel.name)
            metadata_filename = f"{safe_name} [{channel.channel_id}].info.json"
            channel.metadata_path = os.path.join(directory_path, metadata_filename)
            
            # Image paths
            channel.cover_image_path = image_paths.get('cover')
            channel.backdrop_image_path = image_paths.get('backdrop')
            
            # Status and timestamp
            channel.metadata_status = "completed"
            channel.last_metadata_update = datetime.utcnow()
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating channel record: {e}")
            db.rollback()
            raise
    
    def _rollback_operations(self, rollback_actions: List[Tuple[str, str]]):
        """
        Execute rollback operations to clean up partial failures.
        
        Args:
            rollback_actions: List of (action_type, path) tuples
        """
        for action_type, path in reversed(rollback_actions):  # Reverse order for proper cleanup
            try:
                if action_type == 'remove_directory' and os.path.exists(path):
                    shutil.rmtree(path)
                    logger.info(f"Rolled back directory creation: {path}")
                elif action_type == 'remove_file' and os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Rolled back file creation: {path}")
            except Exception as e:
                logger.error(f"Error during rollback of {action_type} for {path}: {e}")
    
    def validate_directory_structure(self, directory_path: str) -> Tuple[bool, List[str]]:
        """
        Validate that directory structure is correct and accessible.
        
        Args:
            directory_path: Path to validate
            
        Returns:
            Tuple of (valid, error_messages)
        """
        errors = []
        
        if not directory_path:
            errors.append("Directory path is empty")
            return False, errors
        
        if not os.path.exists(directory_path):
            errors.append(f"Directory does not exist: {directory_path}")
            return False, errors
        
        if not os.path.isdir(directory_path):
            errors.append(f"Path is not a directory: {directory_path}")
            return False, errors
        
        if not os.access(directory_path, os.R_OK):
            errors.append(f"Directory is not readable: {directory_path}")
        
        if not os.access(directory_path, os.W_OK):
            errors.append(f"Directory is not writable: {directory_path}")
        
        # Check if path is within media root for security
        try:
            real_path = os.path.realpath(directory_path)
            real_media_root = os.path.realpath(self.media_root)
            
            if not real_path.startswith(real_media_root):
                errors.append(f"Directory is outside media root: {directory_path}")
        except Exception as e:
            errors.append(f"Error validating path security: {e}")
        
        return len(errors) == 0, errors


# Global instance
metadata_service = MetadataService()