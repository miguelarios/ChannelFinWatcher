"""Test-specific configuration for the application."""
import os
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class TestSettings(BaseSettings):
    """
    Test-specific application settings.
    
    This configuration ensures tests run in complete isolation from
    development and production environments. Key differences:
    - Uses in-memory SQLite for maximum speed and isolation
    - Disables external service integrations
    - Reduces logging verbosity to focus on test results
    - Bypasses authentication for testing simplicity
    """
    
    # === DATABASE CONFIGURATION ===
    # In-memory SQLite provides complete isolation and maximum speed
    # Each test process gets its own database that's destroyed after tests complete
    database_url: str = Field(
        default="sqlite:///:memory:",
        description="Test database URL - in-memory SQLite for isolation"
    )
    
    # === API CONFIGURATION ===
    # Test-specific API settings
    api_title: str = Field(
        default="ChannelFinWatcher API (TEST)",
        description="API title for test environment"
    )
    
    api_version: str = Field(
        default="0.1.0-test",
        description="API version for test environment"  
    )
    
    # Disable OpenAPI docs in tests to reduce overhead
    docs_url: Optional[str] = Field(
        default=None,
        description="OpenAPI docs URL (disabled in tests)"
    )
    
    # === EXTERNAL SERVICE MOCKING ===
    # These settings help control external dependencies during testing
    
    youtube_api_enabled: bool = Field(
        default=False,
        description="Disable real YouTube API calls in tests"
    )
    
    file_operations_enabled: bool = Field(
        default=False, 
        description="Disable actual file downloads in tests"
    )
    
    yaml_config_enabled: bool = Field(
        default=False,
        description="Disable YAML file operations in tests"
    )
    
    # === LOGGING CONFIGURATION ===
    # Reduce log noise during testing unless debugging
    log_level: str = Field(
        default="WARNING",
        description="Log level for tests (WARNING to reduce noise)"
    )
    
    # === PERFORMANCE SETTINGS ===
    # Optimize for test speed
    connection_pool_size: int = Field(
        default=1,
        description="Small connection pool for tests"
    )
    
    # Shorter timeouts for faster test failures
    request_timeout_seconds: int = Field(
        default=5,
        description="Short timeout for test requests"
    )
    
    # === TEST-SPECIFIC FEATURES ===
    # Settings that only apply during testing
    
    test_mode: bool = Field(
        default=True,
        description="Flag indicating test environment"
    )
    
    mock_youtube_responses: bool = Field(
        default=True,
        description="Use mocked YouTube responses instead of real API calls"
    )
    
    skip_migrations: bool = Field(
        default=True,
        description="Skip Alembic migrations in tests (use create_all instead)"
    )
    
    class Config:
        env_prefix = "TEST_"
        case_sensitive = False


# Global test settings instance
test_settings = TestSettings()


def get_test_database_url() -> str:
    """
    Get the test database URL.
    
    This function provides a consistent way to access the test database URL
    across the test suite. It can be extended to support different test
    database configurations based on environment variables.
    
    Returns:
        str: Database URL for testing (in-memory SQLite by default)
    """
    # Allow override via environment variable for CI/CD pipelines
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if test_db_url:
        return test_db_url
    
    return test_settings.database_url


def is_test_environment() -> bool:
    """
    Check if we're currently running in test environment.
    
    This function helps other parts of the application detect test mode
    and adjust behavior accordingly (e.g., disable external API calls).
    
    Returns:
        bool: True if running in test environment
    """
    return (
        test_settings.test_mode or
        "pytest" in os.environ.get("_", "") or
        "PYTEST_CURRENT_TEST" in os.environ
    )