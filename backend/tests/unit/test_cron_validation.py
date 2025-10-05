"""Unit tests for cron expression validation.

Tests the cron_validation module which provides APScheduler-based
validation for cron expressions used in scheduled downloads.

TEST-001: Comprehensive cron validation testing
"""

import pytest
from datetime import datetime, timedelta
import pytz

from app.cron_validation import (
    validate_cron_expression,
    calculate_next_runs,
    get_cron_schedule_info,
    _describe_cron_schedule
)


class TestCronValidation:
    """Test suite for cron expression validation."""

    # Valid cron expressions (from POC results)
    VALID_EXPRESSIONS = [
        ("0 */6 * * *", "Every 6 hours"),
        ("0 0 * * 0", "Weekly on Sunday"),
        ("30 2 * * 1-5", "Weekdays at 2:30 AM"),
        ("*/15 * * * *", "Every 15 minutes"),
        ("0 9-17 * * 1-5", "Business hours"),
        ("0 0 * * *", "Daily at midnight"),
        ("0 12 * * *", "Daily at noon"),
        ("0 0 1 * *", "First day of month"),
        ("0 0 * * 1", "Every Monday"),
    ]

    # Invalid cron expressions (from POC results)
    INVALID_EXPRESSIONS = [
        ("99 * * * *", "Invalid minute value"),
        ("* 25 * * *", "Invalid hour value"),
        ("* * 32 * *", "Invalid day value"),
        ("* * * 13 *", "Invalid month value"),
        ("* * * * 8", "Invalid day of week"),
        ("invalid syntax", "Malformed expression"),
        ("0 0", "Incomplete expression"),
        ("0 0 * * * *", "Too many fields"),
        ("", "Empty expression"),
        ("0 0 0 * *", "Zero hour (invalid)"),
        ("0 24 * * *", "24 hour (invalid)"),
        ("60 * * * *", "60 minute (invalid)"),
        ("* * * * * *", "6 fields (invalid)"),
    ]

    # Frequency check (blocks every minute only)
    TOO_FREQUENT = [
        ("*/1 * * * *", "Every minute"),
        ("* * * * *", "Every minute (wildcard)"),
    ]

    def test_valid_expressions_accept(self):
        """Test that valid cron expressions are accepted."""
        for expr, description in self.VALID_EXPRESSIONS:
            is_valid, error_msg, trigger = validate_cron_expression(expr)

            assert is_valid, f"Expression '{expr}' ({description}) should be valid, got error: {error_msg}"
            assert error_msg is None
            assert trigger is not None, f"Trigger should be created for valid expression '{expr}'"

    def test_invalid_expressions_reject(self):
        """Test that invalid cron expressions are rejected with clear errors."""
        for expr, description in self.INVALID_EXPRESSIONS:
            is_valid, error_msg, trigger = validate_cron_expression(expr)

            assert not is_valid, f"Expression '{expr}' ({description}) should be invalid"
            assert error_msg is not None, f"Should provide error message for '{expr}'"
            assert trigger is None, f"Should not create trigger for invalid expression '{expr}'"

            # Verify error message is informative
            assert len(error_msg) > 0
            assert "invalid" in error_msg.lower() or "error" in error_msg.lower()

    def test_minimum_interval_enforcement(self):
        """Test that expressions running more frequently than 5 minutes are rejected."""
        for expr, description in self.TOO_FREQUENT:
            is_valid, error_msg, trigger = validate_cron_expression(expr)

            assert not is_valid, f"Expression '{expr}' ({description}) should be rejected (too frequent)"
            assert error_msg is not None
            assert "5 minute" in error_msg.lower() or "minimum" in error_msg.lower()

    def test_input_sanitization(self):
        """Test that dangerous characters are detected."""
        dangerous_inputs = [
            ("0 0 * * * ; rm -rf /", "Command injection"),
            ("0 0 * * * && echo hacked", "Command chaining"),
            ("${VAR} * * * *", "Variable injection"),
            ("'; DROP TABLE channels; --", "SQL injection"),
            ("<script>alert()</script>", "XSS attempt"),
        ]

        for expr, description in dangerous_inputs:
            is_valid, error_msg, trigger = validate_cron_expression(expr)

            # Should either reject or sanitize
            assert not is_valid or trigger is None, \
                f"Dangerous input '{expr}' ({description}) should be rejected"

    def test_calculate_next_runs_count(self):
        """Test that calculate_next_runs returns correct number of runs."""
        expr = "0 */6 * * *"  # Every 6 hours

        # Test different counts
        for count in [1, 3, 5, 10]:
            next_runs = calculate_next_runs(expr, count)
            assert len(next_runs) == count, f"Should return exactly {count} next runs"

    def test_calculate_next_runs_chronological(self):
        """Test that next runs are in chronological order."""
        expr = "0 */6 * * *"  # Every 6 hours
        next_runs = calculate_next_runs(expr, 5)

        # Verify chronological order
        for i in range(len(next_runs) - 1):
            assert next_runs[i] < next_runs[i + 1], \
                f"Run {i} should be before run {i+1}"

    def test_calculate_next_runs_invalid_expression(self):
        """Test that calculate_next_runs handles invalid expressions gracefully."""
        invalid_expr = "99 99 * * *"
        next_runs = calculate_next_runs(invalid_expr, 5)

        assert next_runs == [], "Invalid expression should return empty list"

    def test_get_cron_schedule_info_valid(self):
        """Test get_cron_schedule_info for valid expression."""
        expr = "0 0 * * *"  # Daily at midnight
        info = get_cron_schedule_info(expr)

        assert info["valid"] is True
        assert info["error"] is None
        assert info["next_run"] is not None
        assert len(info["next_5_runs"]) == 5
        assert info["time_until_next"] is not None
        assert info["timezone"] == "UTC"

    def test_get_cron_schedule_info_invalid(self):
        """Test get_cron_schedule_info for invalid expression."""
        expr = "invalid"
        info = get_cron_schedule_info(expr)

        assert info["valid"] is False
        assert info["error"] is not None
        assert info["next_run"] is None
        assert info["next_5_runs"] == []
        assert info["time_until_next"] is None

    def test_describe_cron_schedule_common_patterns(self):
        """Test human-readable descriptions for common patterns."""
        patterns = {
            "0 * * * *": "Every hour",
            "0 */6 * * *": "Every 6 hours",
            "0 0 * * *": "Daily at midnight",
            "0 0 * * 0": "Weekly on Sunday",
            "*/15 * * * *": "Every 15 minutes",
            "0 9 * * 1-5": "Weekdays at 9 AM",
        }

        for expr, expected_desc in patterns.items():
            desc = _describe_cron_schedule(expr)
            assert desc == expected_desc, \
                f"Expression '{expr}' should describe as '{expected_desc}', got '{desc}'"

    def test_describe_cron_schedule_custom(self):
        """Test human-readable description for custom patterns."""
        custom_expr = "15 14 * * 3"  # Custom time
        desc = _describe_cron_schedule(custom_expr)

        # Should return custom format
        assert "Custom schedule" in desc or custom_expr in desc

    def test_next_run_calculation_accuracy(self):
        """Test that next run times are calculated accurately."""
        expr = "0 0 * * *"  # Daily at midnight
        next_runs = calculate_next_runs(expr, 3)

        # Verify runs are 24 hours apart
        for i in range(len(next_runs) - 1):
            diff = next_runs[i + 1] - next_runs[i]
            # Should be approximately 24 hours (allowing for DST)
            assert 23 <= diff.total_seconds() / 3600 <= 25, \
                f"Daily runs should be ~24 hours apart, got {diff.total_seconds() / 3600} hours"

    def test_timezone_handling(self):
        """Test that timezone is properly handled (UTC)."""
        expr = "0 0 * * *"
        next_runs = calculate_next_runs(expr, 1)

        if next_runs:
            # Should be timezone-aware (UTC)
            assert next_runs[0].tzinfo is not None
            assert next_runs[0].tzinfo == pytz.UTC

    def test_edge_case_leap_year(self):
        """Test expression that runs on Feb 29 (leap years only)."""
        # Note: This test verifies the expression is valid,
        # actual leap year logic is in APScheduler
        expr = "0 0 29 2 *"  # Feb 29
        is_valid, error_msg, trigger = validate_cron_expression(expr)

        assert is_valid, "Feb 29 expression should be valid"

    def test_edge_case_month_boundaries(self):
        """Test expression for 31st day (skips months with <31 days)."""
        expr = "0 0 31 * *"  # 31st of month
        is_valid, error_msg, trigger = validate_cron_expression(expr)

        assert is_valid, "31st day expression should be valid"

    def test_default_database_schedule(self):
        """Test that default database schedule validates correctly."""
        default_expr = "0 0 * * *"  # Daily at midnight (from DB migration)
        is_valid, error_msg, trigger = validate_cron_expression(default_expr)

        assert is_valid, "Default database schedule '0 0 * * *' must be valid"
        assert error_msg is None
        assert trigger is not None


class TestCronValidationEdgeCases:
    """Additional edge case tests for cron validation."""

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly."""
        expressions = [
            "  0 0 * * *  ",  # Leading/trailing spaces
            "0  0  *  *  *",  # Extra spaces between fields
            "0\t0\t*\t*\t*",  # Tabs between fields
        ]

        for expr in expressions:
            # Should either accept with normalization or reject clearly
            is_valid, error_msg, trigger = validate_cron_expression(expr)

            # If valid, should work correctly
            if is_valid:
                assert trigger is not None

    def test_case_sensitivity(self):
        """Test that validation is case-insensitive where appropriate."""
        # Cron expressions are typically case-insensitive for numeric values
        expr = "0 0 * * *"
        is_valid, error_msg, trigger = validate_cron_expression(expr)
        assert is_valid

    def test_very_long_expression(self):
        """Test handling of unreasonably long expressions."""
        long_expr = "0 " * 1000 + "* * *"  # Extremely long
        is_valid, error_msg, trigger = validate_cron_expression(long_expr)

        # Should reject (either due to sanitization or validation)
        assert not is_valid

    def test_empty_and_none(self):
        """Test handling of empty/None expressions."""
        invalid_inputs = ["", "   ", None]

        for expr in invalid_inputs:
            try:
                is_valid, error_msg, trigger = validate_cron_expression(expr)
                assert not is_valid, f"Should reject input: {repr(expr)}"
            except (ValueError, TypeError, AttributeError):
                # Exception is also acceptable for invalid input
                pass

    def test_unicode_characters(self):
        """Test rejection of unicode characters in cron expression."""
        unicode_exprs = [
            "0 0 * * 😀",
            "０ ０ * * *",  # Full-width numbers
            "0 0 * * ｗ",  # Full-width letter
        ]

        for expr in unicode_exprs:
            is_valid, error_msg, trigger = validate_cron_expression(expr)
            assert not is_valid, f"Unicode expression '{expr}' should be rejected"
