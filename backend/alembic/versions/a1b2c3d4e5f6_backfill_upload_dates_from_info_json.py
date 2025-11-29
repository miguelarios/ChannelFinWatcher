"""Backfill upload_date from info.json files

This migration reads existing .info.json files created by yt-dlp during video downloads
and populates the upload_date field for Download records that have NULL or empty values.

The issue: Some older downloads have NULL/empty upload_date, which causes the cleanup
logic to incorrectly delete newly downloaded videos instead of the oldest ones.

The fix: Read the upload_date from each video's .info.json file and update the database.

Revision ID: a1b2c3d4e5f6
Revises: f9g8h7i6j5k4
Create Date: 2025-11-29 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text
import json
from pathlib import Path


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f9g8h7i6j5k4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Populate upload_date from info.json files for existing videos.

    This migration:
    1. Queries Download records with NULL or empty upload_date
    2. Locates the corresponding .info.json file for each video
    3. Reads the upload_date from the JSON metadata
    4. Updates the database record with the correct upload date
    5. Handles errors gracefully (missing files, parse errors)
    """
    connection = op.get_bind()

    # Query downloads with NULL or empty upload_date that have completed successfully
    result = connection.execute(
        text("""
            SELECT id, file_path, video_id
            FROM downloads
            WHERE (upload_date IS NULL OR upload_date = '')
              AND file_path IS NOT NULL
              AND status = 'completed'
        """)
    )

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for row in result:
        download_id = row[0]
        file_path = row[1]
        video_id = row[2]

        # Derive info.json path from video file path
        # Pattern: /path/to/video.mkv -> /path/to/video.info.json
        info_json_path = None
        video_extensions = ['.mkv', '.mp4', '.webm', '.m4v', '.avi']

        for ext in video_extensions:
            if file_path and file_path.endswith(ext):
                info_json_path = file_path.replace(ext, '.info.json')
                break

        # If no extension matched, try appending .info.json directly
        if not info_json_path:
            info_json_path = f"{file_path}.info.json" if file_path else None

        # Skip if we couldn't determine a path
        if not info_json_path:
            print(f"  Skipped: No file_path for video_id {video_id}")
            skipped_count += 1
            continue

        # Try to read and parse the info.json file
        try:
            info_path = Path(info_json_path)
            if info_path.exists():
                with open(info_path, 'r', encoding='utf-8') as f:
                    info_data = json.load(f)
                    upload_date = info_data.get('upload_date')

                    if upload_date:
                        # Update database with the extracted upload_date
                        connection.execute(
                            text("""
                                UPDATE downloads
                                SET upload_date = :upload_date
                                WHERE id = :id
                            """),
                            {"upload_date": upload_date, "id": download_id}
                        )
                        updated_count += 1
                    else:
                        print(f"  Skipped: No upload_date in info.json for video_id {video_id}")
                        skipped_count += 1
            else:
                print(f"  Skipped: info.json not found at {info_json_path}")
                skipped_count += 1

        except json.JSONDecodeError as e:
            print(f"  Error: JSON parse failed for video_id {video_id}: {e}")
            error_count += 1

        except IOError as e:
            print(f"  Error: Could not read file for video_id {video_id}: {e}")
            error_count += 1

        except Exception as e:
            print(f"  Error: Unexpected error for video_id {video_id}: {e}")
            error_count += 1

    # Print summary
    print(f"\nBackfill Migration Complete:")
    print(f"  ✓ {updated_count} videos updated with upload_date")
    print(f"  ⊘ {skipped_count} videos skipped (file not found or no date in JSON)")
    print(f"  ✗ {error_count} videos had errors during processing")
    print(f"  Total: {updated_count + skipped_count + error_count} videos processed")


def downgrade() -> None:
    """Optionally set upload_date back to NULL for backfilled videos.

    Note: This downgrade is a no-op because:
    1. The data we populated came from legitimate sources (info.json files)
    2. Reverting would lose valuable metadata
    3. There's no harm in keeping the upload dates even if rolling back
    4. Re-running the migration would produce the same results

    If you really need to clear backfilled dates, you would run:
    UPDATE downloads SET upload_date = NULL WHERE upload_date IS NOT NULL;
    """
    # Intentionally empty - we keep the backfilled data
    pass
