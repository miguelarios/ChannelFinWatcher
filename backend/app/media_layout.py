"""
Media library layout: where downloaded videos live and what they are named.

This is the single source of truth for the on-disk layout. yt-dlp uses the
templates below to name new downloads, the NFO service uses episode_numbers()
to write matching <season>/<episode> tags, and the layout migration CLI uses
both to rename files written under the old layout.

Layout:
    Channel [UCxxxx]/
      Season 2021/
        season.nfo
        S2021E12071530 - Video Title [videoid]/
          S2021E12071530 - Video Title [videoid].mkv
          S2021E12071530 - Video Title [videoid].nfo / .info.json / .webp / ...

Why this naming?
- Jellyfin (and Infuse, which reads Jellyfin's metadata) orders episodes by
  season and episode number. Without an episode number, same-season episodes
  have no reliable order.
- Season = upload year, so each year becomes one Jellyfin season.
- Episode = upload month/day/hour/minute (MMDDHHMM, UTC). It depends only on
  the video itself, so it never changes when cleanup deletes older videos, and
  two uploads on the same day still sort in upload order.
- "Season YYYY" is the folder name Jellyfin documents (a bare "2021" also
  works in Jellyfin, so legacy folders are still recognized here).
- The trailing [videoid] is how the app finds its files on disk; Jellyfin
  strips bracketed text from display titles.
- Each video keeps its own folder because cleanup deletes a video by removing
  its parent folder (see scheduled_download_job.py).
"""

import re
from datetime import datetime, timezone
from typing import Optional, Tuple

# Channel folder (unchanged from the original layout)
CHANNEL_DIR_TEMPLATE = '%(channel)s [%(channel_id)s]'

# Season folder: "Season 2021"
SEASON_DIR_TEMPLATE = 'Season %(upload_date>%Y)s'

# Episode basename: "S2021E12071530 - Title [id]".
# Falls back to MMDD0000 when yt-dlp has no upload timestamp for the video.
EPISODE_NAME_TEMPLATE = (
    'S%(upload_date>%Y)s'
    'E%(timestamp>%m%d%H%M,upload_date>%m%d0000)s'
    ' - %(title)s [%(id)s]'
)

# Path of a video relative to its channel folder
EPISODE_RELATIVE_TEMPLATE = (
    f'{SEASON_DIR_TEMPLATE}/{EPISODE_NAME_TEMPLATE}/{EPISODE_NAME_TEMPLATE}.%(ext)s'
)

# Full yt-dlp output template (relative to the media root)
OUTPUT_TEMPLATE = f'{CHANNEL_DIR_TEMPLATE}/{EPISODE_RELATIVE_TEMPLATE}'

_SEASON_DIR_RE = re.compile(r'^(?:Season )?(\d{4})$')


def season_dir_name(year: int) -> str:
    """Folder name for a year-based season, e.g. 2021 -> "Season 2021"."""
    return f'Season {year}'


def parse_season_dir(name: str) -> Optional[int]:
    """
    Return the season year for a season folder name, or None if it isn't one.

    Accepts the current "Season 2021" form and the legacy bare "2021" form so
    NFO generation keeps working on libraries that haven't been migrated.
    """
    match = _SEASON_DIR_RE.match(name)
    return int(match.group(1)) if match else None


def episode_numbers(info: dict) -> Optional[Tuple[int, int]]:
    """
    Compute (season, episode) for a video from its yt-dlp metadata.

    Mirrors EPISODE_NAME_TEMPLATE so NFO tags always match the filename:
    - season  = year of upload_date
    - episode = MMDDHHMM of the UTC upload timestamp, or MMDD0000 when the
                timestamp is missing

    Returns None when upload_date is missing or malformed.
    """
    upload_date = info.get('upload_date')
    try:
        day = datetime.strptime(str(upload_date), '%Y%m%d')
    except (TypeError, ValueError):
        return None

    timestamp = info.get('timestamp')
    if isinstance(timestamp, (int, float)):
        uploaded = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        episode = int(uploaded.strftime('%m%d%H%M'))
    else:
        episode = int(day.strftime('%m%d')) * 10000

    return day.year, episode
