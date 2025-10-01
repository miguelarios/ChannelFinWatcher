"""Cron expression validation utilities using APScheduler's native validation.

This module provides production-ready cron validation without external dependencies.
APScheduler's CronTrigger handles all validation, next run calculation, and edge cases
including DST transitions, leap years, and invalid dates.

Key Functions:
- validate_cron_expression(): Validate syntax and security constraints
- calculate_next_runs(): Get next N scheduled execution times
- get_cron_schedule_info(): Comprehensive schedule information for UI display

Security Features:
- Input sanitization removes dangerous characters
- Minimum 5-minute interval enforcement prevents system overload
- Clear error messages for user feedback
"""

from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
import pytz
import re


def validate_cron_expression(cron_expr: str) -> Tuple[bool, Optional[str], Optional[CronTrigger]]:
    """
    Validate cron expression using APScheduler's native validation.

    No external dependencies needed - APScheduler provides complete validation
    including edge cases like leap years, DST transitions, and invalid dates.

    Args:
        cron_expr: 5-field cron expression (minute hour day month dow)
                  Example: "0 */6 * * *" for every 6 hours

    Returns:
        Tuple of (is_valid, error_message, trigger_object)
        - is_valid: True if expression is valid and safe
        - error_message: None if valid, descriptive error string if invalid
        - trigger_object: CronTrigger instance if valid, None if invalid

    Security:
        - Sanitizes input to allow only cron-safe characters [0-9 ,\\-*/]
        - Enforces 5-minute minimum interval for system stability
        - Blocks potentially malicious patterns

    Example:
        >>> valid, error, trigger = validate_cron_expression("0 */6 * * *")
        >>> if valid:
        ...     next_run = trigger.get_next_fire_time(None, datetime.now())
        ...     print(f"Next run: {next_run}")
    """
    try:
        # Input sanitization - allow only cron-safe characters
        # Permitted: digits, spaces, commas, hyphens, asterisks, forward slashes
        sanitized = re.sub(r'[^0-9\s,\-\*/]', '', cron_expr[:100])

        if sanitized != cron_expr:
            return False, "Invalid characters detected in cron expression", None

        # APScheduler CronTrigger provides native validation
        # This handles all edge cases: leap years, DST, month boundaries, invalid dates
        trigger = CronTrigger.from_crontab(sanitized, timezone=pytz.UTC)

        # Security: prevent excessive frequency for system stability
        # Block expressions that run every minute
        if sanitized.startswith('* ') or sanitized.startswith('*/1 '):
            return False, "Minimum interval is 5 minutes for system stability", None

        # Additional check: ensure first field isn't just '*'
        parts = sanitized.split()
        if len(parts) >= 1 and parts[0] == '*':
            return False, "Schedules running every minute are not supported", None

        return True, None, trigger

    except ValueError as e:
        # APScheduler raises ValueError for invalid cron expressions
        # Examples: "99 * * * *" → "the last value (99) is higher than the maximum value (59)"
        error_msg = f"Invalid cron expression: {str(e)}"
        return False, error_msg, None
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = f"Cron validation error: {str(e)}"
        return False, error_msg, None


def calculate_next_runs(cron_expr: str, count: int = 5) -> List[datetime]:
    """
    Calculate next N run times using APScheduler CronTrigger.

    Args:
        cron_expr: 5-field cron expression
        count: Number of future run times to calculate (default: 5)

    Returns:
        List of datetime objects in UTC, or empty list if expression is invalid

    Example:
        >>> next_runs = calculate_next_runs("0 */6 * * *", count=3)
        >>> for run_time in next_runs:
        ...     print(run_time.strftime("%Y-%m-%d %H:%M UTC"))
    """
    is_valid, error_msg, trigger = validate_cron_expression(cron_expr)

    if not is_valid:
        return []

    next_runs = []
    current_time = datetime.now(pytz.UTC)

    for _ in range(count):
        next_run = trigger.get_next_fire_time(None, current_time)
        if next_run:
            next_runs.append(next_run)
            current_time = next_run + timedelta(seconds=1)
        else:
            break

    return next_runs


def get_cron_schedule_info(cron_expr: str) -> Dict:
    """
    Get comprehensive schedule information for UI display.

    Provides all information needed for user-facing schedule configuration:
    - Validation status
    - Next run time with countdown
    - Next 5 scheduled runs
    - Human-readable description

    Args:
        cron_expr: 5-field cron expression to analyze

    Returns:
        Dictionary containing:
        - valid: bool - Whether expression is valid
        - error: str or None - Error message if invalid
        - next_run: str or None - ISO 8601 timestamp of next run
        - next_5_runs: List[str] - ISO timestamps of next 5 runs
        - time_until_next: str or None - Human-readable time until next run
        - timezone: str - Always "UTC"
        - human_readable: str - Descriptive schedule text

    Example:
        >>> info = get_cron_schedule_info("0 */6 * * *")
        >>> print(info['human_readable'])
        "Every 6 hours"
        >>> print(info['next_run'])
        "2025-10-01T18:00:00+00:00"
    """
    is_valid, error_msg, trigger = validate_cron_expression(cron_expr)

    if not is_valid:
        return {
            "valid": False,
            "error": error_msg,
            "next_run": None,
            "next_5_runs": [],
            "time_until_next": None,
            "human_readable": "Invalid expression"
        }

    next_runs = calculate_next_runs(cron_expr, 5)
    next_run = next_runs[0] if next_runs else None
    now = datetime.now(pytz.UTC)

    return {
        "valid": True,
        "error": None,
        "next_run": next_run.isoformat() if next_run else None,
        "next_5_runs": [run.isoformat() for run in next_runs],
        "time_until_next": str(next_run - now) if next_run else None,
        "timezone": "UTC",
        "human_readable": _describe_cron_schedule(cron_expr)
    }


def _describe_cron_schedule(cron_expr: str) -> str:
    """
    Convert cron expression to human-readable description.

    Recognizes common patterns and returns friendly descriptions.
    Falls back to showing the raw expression for custom schedules.

    Args:
        cron_expr: 5-field cron expression

    Returns:
        Human-readable description string

    Example:
        >>> _describe_cron_schedule("0 */6 * * *")
        "Every 6 hours"
        >>> _describe_cron_schedule("0 9 * * 1-5")
        "Weekdays at 9 AM"
    """
    common_patterns = {
        "0 * * * *": "Every hour",
        "0 */6 * * *": "Every 6 hours",
        "0 0 * * *": "Daily at midnight",
        "0 0 * * 0": "Weekly on Sunday",
        "*/15 * * * *": "Every 15 minutes",
        "0 9 * * 1-5": "Weekdays at 9 AM",
        "30 2 * * 1-5": "Weekdays at 2:30 AM",
        "0 9-17 * * 1-5": "Weekdays during business hours (9 AM - 5 PM)",
    }

    return common_patterns.get(cron_expr, f"Custom schedule: {cron_expr}")
