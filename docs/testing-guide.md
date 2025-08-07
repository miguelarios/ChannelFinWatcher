# Testing Guide

This document provides comprehensive guidance on using the testing framework established in **Story 000 - Infrastructure Setup**. The testing infrastructure supports both backend (FastAPI + SQLAlchemy) and frontend (NextJS + React) testing through Docker containers.

## Table of Contents

- [Overview](#overview)
- [Backend Testing](#backend-testing)
- [Frontend Testing](#frontend-testing)
- [Running Tests](#running-tests)
- [Writing New Tests](#writing-new-tests)
- [Coverage Reports](#coverage-reports)
- [Troubleshooting](#troubleshooting)

## Overview

### Testing Philosophy

**Why Testing Matters for ChannelFinWatcher:**
- **Data Integrity**: YouTube channel monitoring involves complex data relationships
- **User Experience**: Inline editing, validation, and error handling require thorough testing
- **Reliability**: Automated downloads and scheduling must work consistently
- **Maintainability**: As we add new features, tests ensure existing functionality doesn't break

### Testing Architecture

```
backend/
├── tests/
│   ├── conftest.py           # Shared test fixtures and database setup
│   ├── unit/                 # Fast tests for individual components
│   │   └── test_models.py    # Database model tests
│   └── integration/          # Tests for API endpoints and workflows
│       ├── test_api.py       # Channel management API tests
│       └── test_health.py    # Health check endpoint tests
└── pytest.ini               # Test configuration

frontend/
├── src/__tests__/
│   └── components/           # Component testing directory
│       ├── Header.test.tsx   # Navigation and branding tests
│       └── ChannelsList.test.tsx  # Channel management UI tests
├── jest.config.js           # Jest configuration for NextJS
├── jest.setup.js            # Global test setup
└── __mocks__/               # Mock files for assets
```

## Backend Testing

### Technology Stack

- **pytest**: Primary testing framework with async support
- **FastAPI TestClient**: HTTP client for API testing
- **SQLAlchemy + SQLite (in-memory)**: Isolated test database
- **coverage.py**: Code coverage measurement
- **httpx**: HTTP client for external API mocking

### Test Categories

#### 1. Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation

**Example - Model Testing**:
```python
def test_create_channel_with_required_fields(self, db_session):
    channel = Channel(
        url="https://www.youtube.com/@TestChannel",
        channel_id="UC12345678901234567890",
        name="Test Channel"
    )
    db_session.add(channel)
    db_session.commit()
    
    # Verify creation and defaults
    assert channel.id is not None
    assert channel.limit == 10  # Default limit
    assert channel.enabled is True
```

#### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test API endpoints and database interactions

**Example - API Testing**:
```python
@patch('app.youtube_service.youtube_service.extract_channel_info')
def test_create_channel_success(self, mock_extract, test_client):
    # Mock external YouTube service
    mock_extract.return_value = (True, {"channel_id": "UC123", "name": "Test"}, None)
    
    response = test_client.post("/api/v1/channels", json={
        "url": "https://www.youtube.com/@TestChannel",
        "limit": 15
    })
    
    assert response.status_code == 200
    assert response.json()["name"] == "Test"
```

### Test Database Configuration

**Key Features**:
- **Complete Isolation**: Each test gets a fresh in-memory SQLite database
- **No Cleanup Required**: Database is destroyed automatically after tests
- **Fast Execution**: In-memory database operations are extremely fast
- **Consistent State**: No test pollution between runs

**Configuration** (`tests/conftest.py`):
```python
@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session for testing."""
    TestingSessionLocal = sessionmaker(bind=db_engine)
    session = TestingSessionLocal()
    
    # Initialize required settings
    default_limit_setting = ApplicationSettings(
        key="default_video_limit", value="10"
    )
    session.add(default_limit_setting)
    session.commit()
    
    yield session
    session.close()
```

## Frontend Testing

### Technology Stack

- **Jest**: Test runner and assertion library
- **React Testing Library**: Component testing utilities
- **@testing-library/user-event**: User interaction simulation
- **@testing-library/jest-dom**: Custom DOM matchers

### Test Categories

#### 1. Component Tests

**Purpose**: Test React component behavior and user interactions

**Example - Header Component**:
```typescript
it('calls onViewChange when navigation button is clicked', () => {
  render(<Header currentView="dashboard" onViewChange={mockOnViewChange} />)
  
  const settingsButton = screen.getByRole('button', { name: /settings/i })
  fireEvent.click(settingsButton)
  
  expect(mockOnViewChange).toHaveBeenCalledWith('settings')
})
```

#### 2. Integration Tests

**Purpose**: Test component interaction with APIs

**Example - API Integration**:
```typescript
it('successfully updates limit via API', async () => {
  // Mock successful API response
  (fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve({ id: 1, limit: 15 })
  })
  
  // User interaction
  const user = userEvent.setup()
  await user.click(editButton)
  await user.clear(input)
  await user.type(input, '15{Enter}')
  
  // Verify API call
  expect(fetch).toHaveBeenCalledWith('/api/v1/channels/1', {
    method: 'PUT',
    body: JSON.stringify({ limit: 15 })
  })
})
```

## Running Tests

### Backend Tests

```bash
# Start development environment
docker compose -f docker-compose.dev.yml up -d

# Run all backend tests
docker compose -f docker-compose.dev.yml exec backend python -m pytest

# Run specific test categories
docker compose -f docker-compose.dev.yml exec backend python -m pytest tests/unit/ -v
docker compose -f docker-compose.dev.yml exec backend python -m pytest tests/integration/ -v

# Run specific test files
docker compose -f docker-compose.dev.yml exec backend python -m pytest tests/unit/test_models.py -v

# Run with coverage
docker compose -f docker-compose.dev.yml exec backend python -m pytest --cov=app --cov-report=html
```

### Frontend Tests

```bash
# Run frontend tests (after building frontend container)
docker compose -f docker-compose.dev.yml exec frontend npm test

# Run tests in watch mode (for development)
docker compose -f docker-compose.dev.yml exec frontend npm run test:watch

# Run with coverage
docker compose -f docker-compose.dev.yml exec frontend npm run test:coverage
```

### Test Output Examples

**Successful Backend Test Run**:
```
============================= test session starts ==============================
tests/unit/test_models.py::TestChannelModel::test_create_channel_with_required_fields PASSED
tests/unit/test_models.py::TestChannelModel::test_channel_unique_constraints PASSED
tests/integration/test_api.py::TestChannelsAPI::test_list_channels_empty PASSED
======================== 8 passed in 0.04s =========================
```

## Writing New Tests

### Backend Test Patterns

#### 1. Model Tests

**When to Write**: For any new SQLAlchemy model or model modifications

**Template**:
```python
class TestYourModel:
    def test_create_with_required_fields(self, db_session):
        # Test basic creation
        pass
    
    def test_unique_constraints(self, db_session):
        # Test constraint violations
        pass
    
    def test_relationships(self, db_session):
        # Test foreign key relationships
        pass
```

#### 2. API Tests

**When to Write**: For any new endpoint or endpoint modifications

**Template**:
```python
class TestYourAPI:
    def test_endpoint_success(self, test_client):
        # Test successful operation
        pass
    
    def test_endpoint_validation_error(self, test_client):
        # Test input validation
        pass
    
    def test_endpoint_not_found(self, test_client):
        # Test error handling
        pass
```

### Frontend Test Patterns

#### 1. Component Tests

**When to Write**: For any new React component or significant modifications

**Template**:
```typescript
describe('YourComponent', () => {
  it('renders correctly with required props', () => {
    // Test basic rendering
  })
  
  it('handles user interactions', async () => {
    // Test clicks, input changes, etc.
  })
  
  it('displays error states appropriately', () => {
    // Test error handling
  })
})
```

#### 2. API Integration Tests

**When to Write**: When components interact with backend APIs

**Template**:
```typescript
it('handles API success response', async () => {
  // Mock successful API response
  (fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(expectedData)
  })
  
  // User interaction that triggers API call
  // Assertions about UI updates
})
```

### Test Data Management

#### Backend Fixtures

Use `conftest.py` for shared test data:

```python
@pytest.fixture
def sample_channel_data():
    return {
        "url": "https://www.youtube.com/@TestChannel",
        "channel_id": "UC12345678901234567890",
        "name": "Test Channel",
        "limit": 10,
        "enabled": True
    }
```

#### Frontend Test Data

Create reusable mock data:

```typescript
const mockChannels = [
  {
    id: 1,
    name: "Test Channel",
    url: "https://www.youtube.com/@TestChannel",
    limit: 10,
    enabled: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  }
]
```

## Coverage Reports

### Backend Coverage

**Generate Report**:
```bash
docker compose -f docker-compose.dev.yml exec backend python -m pytest --cov=app --cov-report=html --cov-report=term
```

**View HTML Report**:
- Open `backend/htmlcov/index.html` in your browser
- Navigate through modules to see line-by-line coverage

**Coverage Targets**:
- **Models**: 95%+ (critical data integrity)
- **API Endpoints**: 90%+ (user-facing functionality)
- **Utility Functions**: 85%+ (supporting logic)

### Frontend Coverage

**Generate Report**:
```bash
docker compose -f docker-compose.dev.yml exec frontend npm run test:coverage
```

**View Report**:
- Coverage summary appears in terminal
- Detailed report in `frontend/coverage/lcov-report/index.html`

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors

**Problem**: Test dependencies not installed in container

**Solution**: Rebuild containers after adding new test dependencies
```bash
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up --build -d
```

#### 2. Database connection errors

**Problem**: Test database configuration issues

**Solution**: Check that `conftest.py` properly initializes test database
- Verify in-memory SQLite URL: `sqlite:///:memory:`
- Ensure `Base.metadata.create_all()` is called

#### 3. Frontend test timeouts

**Problem**: Async operations in component tests

**Solution**: Use proper async/await patterns
```typescript
// Wrong
fireEvent.click(button)
expect(screen.getByText('Updated')).toBeInTheDocument()

// Correct
await user.click(button)
await waitFor(() => {
  expect(screen.getByText('Updated')).toBeInTheDocument()
})
```

#### 4. Mock not working

**Problem**: External API calls not properly mocked

**Solution**: Ensure mocks are imported and configured correctly
```typescript
// At top of test file
global.fetch = jest.fn()

// In test
(fetch as jest.Mock).mockResolvedValueOnce({...})
```

### Performance Tips

1. **Use `scope="function"` for test fixtures** to ensure isolation
2. **Mock external services** to avoid network delays
3. **Prefer unit tests over integration tests** for faster feedback
4. **Use `--maxfail=1`** to stop on first failure during development

### Debugging Tests

#### Backend Debugging
```bash
# Run with verbose output and stop on first failure
docker compose -f docker-compose.dev.yml exec backend python -m pytest -v -s --maxfail=1

# Run specific test with debugging
docker compose -f docker-compose.dev.yml exec backend python -m pytest tests/unit/test_models.py::TestChannelModel::test_create_channel_with_required_fields -v -s
```

#### Frontend Debugging
```bash
# Run tests with debugging output
docker compose -f docker-compose.dev.yml exec frontend npm test -- --verbose

# Run specific test file
docker compose -f docker-compose.dev.yml exec frontend npm test -- Header.test.tsx
```

## Best Practices

### General Testing Guidelines

1. **Test Behavior, Not Implementation**: Focus on what the user sees and does
2. **Use Descriptive Test Names**: `test_create_channel_applies_default_limit_when_none_specified`
3. **Arrange-Act-Assert Pattern**: Clear test structure
4. **One Assertion Per Test**: Makes failures easier to debug
5. **Mock External Dependencies**: YouTube API, file system, etc.

### Backend Specific

1. **Use Transactions**: Each test gets a clean database state
2. **Test Edge Cases**: Validation errors, constraint violations
3. **Mock YouTube Service**: Never make real API calls in tests
4. **Test Both Success and Error Paths**: Happy path + error handling

### Frontend Specific

1. **Test User Interactions**: Clicks, typing, form submissions
2. **Use `screen.getByRole()`**: More accessible and robust selectors
3. **Test Async Behavior**: Use `waitFor()` for async operations
4. **Mock API Calls**: Control responses for predictable testing

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build and test backend
        run: |
          docker compose -f docker-compose.dev.yml up --build -d backend
          docker compose -f docker-compose.dev.yml exec -T backend python -m pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
        with:
          file: ./backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest  
    steps:
      - uses: actions/checkout@v2
      - name: Build and test frontend
        run: |
          docker compose -f docker-compose.dev.yml up --build -d frontend
          docker compose -f docker-compose.dev.yml exec -T frontend npm test -- --coverage --watchAll=false
```

---

This testing infrastructure provides a solid foundation for developing ChannelFinWatcher with confidence. Each new feature should include corresponding tests to ensure reliability and maintainability as the application grows.