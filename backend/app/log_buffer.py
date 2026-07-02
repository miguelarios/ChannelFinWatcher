"""In-memory ring buffer of recent log records (US-014: logging access).

Docker logs remain the primary troubleshooting channel; this buffer exposes
the most recent records over the API so the web UI (or curl) can inspect
them without shell access to the host. Bounded deque = fixed memory cost.
"""

import logging
import threading
from collections import deque
from typing import List, Optional
from app.time_utils import utc_from_timestamp

BUFFER_SIZE = 500


class RingBufferHandler(logging.Handler):
    """Logging handler that keeps the last BUFFER_SIZE records in memory."""

    def __init__(self):
        super().__init__()
        self._lock_buffer = threading.Lock()
        self._records = deque(maxlen=BUFFER_SIZE)

    def emit(self, record: logging.LogRecord):
        try:
            with self._lock_buffer:
                self._records.append({
                    "timestamp": utc_from_timestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                })
        except Exception:
            # Never let log capture break the application
            pass

    def recent(self, limit: int = 100, level: Optional[str] = None) -> List[dict]:
        """Most recent records, newest first, optionally filtered by min level."""
        min_levelno = logging.getLevelName(level.upper()) if level else logging.NOTSET
        if not isinstance(min_levelno, int):
            min_levelno = logging.NOTSET

        with self._lock_buffer:
            records = list(self._records)

        if min_levelno > logging.NOTSET:
            records = [
                r for r in records
                if logging.getLevelName(r["level"]) >= min_levelno
            ]
        return list(reversed(records))[:limit]


# Global handler instance; attached to the root logger in main.py
log_buffer_handler = RingBufferHandler()
