"""In-memory store of active download progress (US-010).

Fed by yt-dlp progress hooks from the download worker (a thread), read by
API handlers (event loop / threadpool). A plain dict guarded by a lock is
sufficient: writes are frequent but tiny, readers only take snapshots, and
the store intentionally holds only *active* downloads — completed/failed
downloads live in the database, not here.

Deliberately not persisted: progress is ephemeral by nature, and a restart
mid-download means the download restarts anyway.
"""

import logging
import threading
from typing import Dict, List, Optional
from app.time_utils import utc_now

logger = logging.getLogger(__name__)


class DownloadProgressStore:
    """Thread-safe registry of currently-downloading videos.

    Entries are keyed by video_id alone. A given video can only be
    mid-download once at a time by construction, so the key is unique for
    progress purposes. The one edge to know about: if the same video appears
    in two channels' feeds AND downloads ever run concurrently (today the
    shared scheduler lock keeps them sequential), the second start() would
    overwrite the first entry's channel attribution in the display.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active: Dict[str, dict] = {}

    def start(self, video_id: str, channel_id: int, channel_name: str, title: str):
        """Register a download as active (called before yt-dlp starts)."""
        with self._lock:
            self._active[video_id] = {
                "video_id": video_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "title": title,
                "status": "starting",
                "percent": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": None,
                "speed": None,
                "eta_seconds": None,
                "started_at": utc_now().isoformat(),
                "updated_at": utc_now().isoformat(),
            }

    def update(self, video_id: str, **fields):
        """Merge progress fields for an active download (no-op if unknown)."""
        with self._lock:
            entry = self._active.get(video_id)
            if entry is None:
                return
            entry.update(fields)
            entry["updated_at"] = utc_now().isoformat()

    def finish(self, video_id: str):
        """Remove a download from the active set (success or failure)."""
        with self._lock:
            self._active.pop(video_id, None)

    def snapshot(self) -> List[dict]:
        """Copy of all active downloads, oldest first."""
        with self._lock:
            return sorted(
                (dict(entry) for entry in self._active.values()),
                key=lambda e: e["started_at"],
            )

    def make_progress_hook(self, video_id: str):
        """Build a yt-dlp progress hook bound to one video.

        yt-dlp calls the hook per fragment/file with a dict whose 'status' is
        'downloading' or 'finished'. A single video triggers multiple file
        downloads (video + audio streams), so percent resets between files —
        acceptable for a progress display.
        """
        def hook(d: dict):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded = d.get("downloaded_bytes") or 0
                    percent = (downloaded / total * 100) if total else 0.0
                    self.update(
                        video_id,
                        status="downloading",
                        percent=round(percent, 1),
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                        speed=d.get("speed"),
                        eta_seconds=d.get("eta"),
                    )
                elif d.get("status") == "finished":
                    # File finished; yt-dlp may still merge/embed metadata
                    self.update(video_id, status="processing", percent=100.0)
            except Exception as e:
                # A progress-display failure must never break the download
                logger.debug(f"Progress hook error for {video_id}: {e}")

        return hook


# Global instance shared by the download worker and API handlers
download_progress_store = DownloadProgressStore()
