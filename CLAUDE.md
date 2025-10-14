# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MLC Bakery is a machine learning data and model management system with provenance tracking, built with FastAPI and SQLAlchemy. It provides RESTful APIs for managing ML model lineage, datasets, collections, and activities with support for Croissant metadata validation.

## Architecture

The application follows a layered architecture:

1. **API Layer** (`mlcbakery/api/`) - FastAPI routers and endpoints organized by resource type
2. **Schema Layer** (`mlcbakery/schemas/`) - Pydantic models for request/response validation
3. **Model Layer** (`mlcbakery/models.py`) - SQLAlchemy ORM models for database entities
4. **Database Layer** (`mlcbakery/database.py`) - Database connection and session management
5. **Auth Layer** (`mlcbakery/auth/`) - Multiple authentication strategies (JWT, Admin Token, Passthrough)
6. **Storage Layer** (`mlcbakery/storage/`) - GCP storage integration for artifacts
7. **MCP Server** (`mlcbakery/mcp/`) - Model Context Protocol server implementation

Key architectural patterns:
- Async/await throughout for non-blocking I/O
- Dependency injection for database sessions and authentication
- Pydantic for data validation
- SQLAlchemy with async support for database operations
- OpenTelemetry instrumentation for observability

## Development Commands

### Setup and Installation
```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up environment variables
cp env.example .env

# Install Python 3.12 if needed
uv python install 3.12

# Install dependencies (use uv sync for more reliable installation)
uv sync --python 3.12
```

### Running the Application

**Local Development:**
```bash
# Run the FastAPI server with auto-reload
uv run uvicorn mlcbakery.main:app --reload --host 0.0.0.0 --port 8000
```

**Docker Development:**
```bash
# Start all services (postgres, typesense, api, mcp, caddy reverse proxy)
docker compose up -d

# Create database and run migrations
docker compose exec db psql -U postgres -c "create DATABASE mlcbakery;"
docker compose exec api alembic upgrade head
```

**Accessing the API:**
- With Docker:
  - Swagger UI: `http://bakery.localhost/docs`
  - ReDoc: `http://bakery.localhost/redoc`
  - MCP Server: `http://mcp.localhost/mcp`
  - Health check: `http://bakery.localhost/api/v1/health`
- Local development:
  - Swagger UI: `http://localhost:8000/docs`
  - Health check: `http://localhost:8000/api/v1/health`

### Database Management
```bash
# Create a new migration
uv run alembic revision --autogenerate -m "migration message"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=mlcbakery --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_collections.py

# Run a specific test
uv run pytest tests/test_collections.py::test_create_collection

# Run tests with verbose output
uv run pytest -v

# Run tests matching a pattern
uv run pytest -k "collection"
```

### Code Quality
```bash
# Format code with black
uv run black mlcbakery/ tests/

# Type checking with mypy
uv run mypy mlcbakery/

# Check black formatting without making changes
uv run black --check mlcbakery/ tests/
```

### CLI Tool
```bash
# The project includes a CLI tool for bakery operations
uv run bakery-cli --help

# Create a task
uv run bakery-cli create-task --collection <name> --name <task> --workflow-file <path>

# Get task details
uv run bakery-cli get-task --collection <name> --name <task>
```

## API Endpoints Structure

The API is versioned under `/api/v1/` with the following main resource endpoints:

- `/collections` - Collection management
- `/collections/{name}/entities/{entity_name}` - Entity management within collections
- `/collections/{name}/entities/{entity_name}/activities` - Activity tracking
- `/collections/{name}/entities/{entity_name}/relationships` - Entity relationships
- `/tasks` - Task management
- `/agents` - Agent management
- `/storage` - Storage operations
- `/api-keys` - API key management

All endpoints require authentication via Bearer token (JWT or Admin token) configured through environment variables.

## Environment Configuration

Required environment variables (see `env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `DATABASE_TEST_URL` - Optional separate test database connection string
- `ADMIN_AUTH_TOKEN` - Master admin token for unrestricted access
- `JWT_ISSUER_JWKS_URL` - JWT issuer JWKS URL for token validation (e.g., Clerk)
- `TYPESENSE_HOST`, `TYPESENSE_PORT`, `TYPESENSE_PROTOCOL`, `TYPESENSE_API_KEY`, `TYPESENSE_COLLECTION_NAME` - Typesense search service configuration
- `GCS_*` - Google Cloud Storage settings for artifact storage
- `OTEL_ENABLED` - Enable/disable OpenTelemetry instrumentation
- `IS_GCP_METRICS` - Use direct GCP exporters vs OTLP
- `ALLOWED_ORIGINS` - CORS allowed origins (comma-separated)

## Testing Strategy

Tests use pytest with async support and include:
- Automatic test database setup/teardown per test function
- Mocked GCS storage for testing storage operations
- Admin token authentication for test requests
- Isolated database transactions per test

Test database is configured via `DATABASE_TEST_URL` environment variable or defaults to the main `DATABASE_URL`.