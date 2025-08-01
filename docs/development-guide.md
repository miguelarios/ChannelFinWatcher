# ChannelFinWatcher Development Guide

This guide contains project-specific development commands and workflows for ChannelFinWatcher.

## Development Environment

### Docker Development Commands

For consistent testing environment across different machines:

```bash
# Start development server with Docker
docker compose -f docker-compose.dev.yml up

# Start with rebuild (after dependency changes)
docker compose -f docker-compose.dev.yml up --build

# Run in background (detached mode)
docker compose -f docker-compose.dev.yml up -d

# Stop and clean up containers
docker compose -f docker-compose.dev.yml down

# View logs
docker compose -f docker-compose.dev.yml logs -f
```

## Code Quality Tools

All development tooling runs via Docker to ensure consistency across environments:

### Python Backend

```bash
# Format and fix Python code
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh format-python-fix

# Check Python formatting (without fixing)
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh format-python

# Lint Python code
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh lint-python

# Run all Python checks
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh check-all
```

### Frontend TypeScript/React

```bash
# Format and fix frontend code
docker compose -f docker-compose.dev.yml exec frontend npm run format

# Check frontend formatting
docker compose -f docker-compose.dev.yml exec frontend npm run format:check

# Lint frontend code
docker compose -f docker-compose.dev.yml exec frontend npm run lint

# Auto-fix frontend linting issues
docker compose -f docker-compose.dev.yml exec frontend npm run lint:fix
```

### Combined Commands

```bash
# Fix all formatting issues (Python only via script)
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh fix-all

# Help - see all available commands
docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh help
```

## API Documentation

FastAPI provides interactive API documentation out of the box:

### Documentation URLs
- **Swagger UI**: http://localhost:8000/docs - Interactive API testing
- **ReDoc**: http://localhost:8000/redoc - Clean documentation view  
- **OpenAPI Spec**: http://localhost:8000/api/v1/openapi.json - Raw specification

### Development Workflow
1. Start the development environment
2. Access Swagger UI at http://localhost:8000/docs
3. Test API endpoints directly in the browser
4. Use the OpenAPI spec for frontend TypeScript type generation

## Database Operations

### Migrations with Alembic

```bash
# Create a new migration
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

# View migration history
docker compose -f docker-compose.dev.yml exec backend alembic history

# Downgrade to previous migration
docker compose -f docker-compose.dev.yml exec backend alembic downgrade -1
```

### Database Access

```bash
# Access SQLite database directly
docker compose -f docker-compose.dev.yml exec backend sqlite3 /app/data/channelfinwatcher.db

# Run SQL queries via container
docker compose -f docker-compose.dev.yml exec backend sqlite3 /app/data/channelfinwatcher.db ".tables"
```

## Technology Stack Rationale

### Why FastAPI + NextJS + Docker?
- **FastAPI**: Modern Python web framework with automatic OpenAPI documentation
- **NextJS**: React framework with TypeScript support and excellent developer experience
- **Docker**: Consistent development environment across different machines
- **SQLite**: Simple database perfect for personal use, easy PostgreSQL migration path

### Why These Development Tools?
- **Black + isort**: Eliminates Python style debates, consistent formatting
- **Flake8**: Catches Python logical errors and style violations
- **Prettier + ESLint**: Frontend code consistency and error prevention
- **Docker-based tooling**: Same tool versions for all developers, no local installs needed

## Project Structure

```
ChannelFinWatcher/
├── backend/                 # FastAPI application
│   ├── app/                # Application code
│   ├── alembic/            # Database migrations
│   ├── config/             # Configuration files
│   ├── data/               # SQLite database storage
│   └── media/              # Downloaded video storage
├── frontend/               # NextJS application
│   └── src/                # React components and pages
├── docs/                   # Project documentation
├── scripts/                # Development scripts
└── docker-compose.dev.yml  # Development Docker configuration
```

## Common Development Tasks

### Adding a New API Endpoint
1. Add route to `backend/app/api.py`
2. Update Pydantic schemas in `backend/app/schemas.py` 
3. Add database models if needed in `backend/app/models.py`
4. Test endpoint at http://localhost:8000/docs
5. Update frontend API client if needed

### Adding a New Frontend Component
1. Create component in `frontend/src/components/`
2. Follow existing TypeScript patterns
3. Use TailwindCSS for styling
4. Add to routing in `frontend/src/pages/` if needed

### Database Schema Changes
1. Update SQLAlchemy models in `backend/app/models.py`
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review generated migration file
4. Apply migration: `alembic upgrade head`