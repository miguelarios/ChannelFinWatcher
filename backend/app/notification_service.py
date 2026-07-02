"""Failure notifications via Apprise (operational hardening).

Apprise supports dozens of services (Discord, ntfy, Telegram, email, ...)
through a single URL syntax, which fits the homelab audience: one setting,
no per-service integration code. Notifications are strictly best-effort —
a notification failure must never affect download processing.

Setting: ApplicationSettings key 'notification_url' (blank/missing = disabled).
"""

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import ApplicationSettings

logger = logging.getLogger(__name__)

NOTIFICATION_URL_KEY = "notification_url"


def get_notification_url(db: Session) -> Optional[str]:
    """Read the configured Apprise URL (None when notifications are disabled)."""
    try:
        setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == NOTIFICATION_URL_KEY
        ).first()
        if setting and setting.value and setting.value.strip():
            return setting.value.strip()
    except Exception as e:
        logger.warning(f"Failed to read notification URL: {e}")
    return None


def validate_notification_url(url: str) -> Tuple[bool, Optional[str]]:
    """Check whether Apprise accepts the URL (without sending anything)."""
    try:
        import apprise
        client = apprise.Apprise()
        if client.add(url):
            return True, None
        return False, "Apprise did not recognize this notification URL format"
    except Exception as e:
        return False, f"Could not validate notification URL: {e}"


def send_notification(db: Session, title: str, body: str) -> bool:
    """Send a notification if configured. Best-effort: never raises.

    Returns True only when a notification was actually dispatched.
    """
    url = get_notification_url(db)
    if not url:
        return False

    try:
        import apprise
        client = apprise.Apprise()
        if not client.add(url):
            logger.warning("Configured notification URL was rejected by Apprise")
            return False
        result = client.notify(title=title, body=body)
        if not result:
            logger.warning("Notification dispatch reported failure")
        return bool(result)
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")
        return False
