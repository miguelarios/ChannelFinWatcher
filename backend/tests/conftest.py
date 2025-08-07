"""Test configuration and fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models import ApplicationSettings
from main import app


# In-memory SQLite database for testing
# Why we use in-memory database:
# - Completely isolated from development/production data
# - Extremely fast test execution
# - Automatic cleanup after test completion
# - No test pollution between test runs
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh database engine for each test function.
    
    This ensures complete test isolation - each test gets a clean database
    with no leftover data from previous tests.
    """
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Required for in-memory SQLite with multiple connections
        echo=False  # Set to True for SQL query debugging
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session for testing.
    
    This fixture:
    - Creates a fresh session for each test
    - Automatically rolls back transactions after each test
    - Ensures no test data persists between tests
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=db_engine
    )
    session = TestingSessionLocal()
    
    # Initialize required application settings
    # This ensures tests have the expected default configuration
    default_limit_setting = ApplicationSettings(
        key="default_video_limit",
        value="10",
        description="Default number of videos to keep per channel"
    )
    session.add(default_limit_setting)
    session.commit()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_client(db_session):
    """Create a test client with database dependency override.
    
    This fixture:
    - Replaces the real database with our test database
    - Allows testing API endpoints in complete isolation
    - Maintains proper dependency injection patterns
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Session cleanup handled by db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_channel_data():
    """Sample channel data for testing.
    
    This provides consistent test data across multiple test functions
    and makes tests more readable by centralizing test data.
    """
    return {
        "url": "https://www.youtube.com/@MrsRachel",
        "channel_id": "UC12345678901234567890",
        "name": "Mrs. Rachel - Toddler Learning Videos",
        "limit": 15,
        "enabled": True,
        "quality_preset": "best"
    }


@pytest.fixture
def sample_channel_create_data():
    """Sample channel creation data for API testing."""
    return {
        "url": "https://www.youtube.com/@TestChannel",
        "limit": 20,
        "enabled": True,
        "quality_preset": "1080p",
        "schedule_override": None
    }