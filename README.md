# MLC Bakery

A Python-based service for managing ML model provenance and lineage, built with FastAPI and SQLAlchemy.

## Features

- Dataset management with collection support
- Entity tracking
- Activity logging
- Agent management
- Provenance relationships tracking
- RESTful API endpoints

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- PostgreSQL (running locally or via Docker)

### Local Development Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url> mlcbakery
    cd mlcbakery
    ```

2.  **Install Dependencies:**
    `uv` uses `pyproject.toml` to manage dependencies. It will automatically create a virtual environment if one doesn't exist.
    ```bash
    # Install main, dev, and webclient dependencies in editable mode
    uv pip install -e .[dev,webclient]
    ```

3.  **Set up Environment Variables:**
    Create a `.env` file in the project root by copying the example:
    ```bash
    cp .env.example .env # Ensure .env.example exists and is up-to-date
    ```
    Edit `.env` with your local PostgreSQL connection details. The key variable is `DATABASE_URL`. Example for a user 'devuser' with password 'devpass' connecting to database 'mlcbakery_dev':
    ```env
    # .env
    DATABASE_URL=postgresql+asyncpg://devuser:devpass@localhost:5432/mlcbakery_dev
    ```
    *(Ensure your PostgreSQL server is running and the specified database exists and the user has permissions)*

4.  **Run Database Migrations:**
    Apply the latest database schema using Alembic. `uv run` executes commands within the project's managed environment.
    ```bash
    uv run alembic upgrade heads
    ```

### Running the Server (Locally)

Start the FastAPI application using uvicorn:
```bash
# Make sure your .env file is present for the DATABASE_URL
uv run uvicorn mlcbakery.main:app --reload --host 0.0.0.0 --port 8000
```
The API will be available at `http://localhost:8000` (or your machine's IP address).

-   Swagger UI: `http://localhost:8000/docs`
-   ReDoc: `http://localhost:8000/redoc`

### Running Tests

The tests are configured to run against a PostgreSQL database defined by the `DATABASE_URL` environment variable. You can use the same database as your development environment or configure a separate test database in your `.env` file if preferred (adjust connection string as needed).

```bash
# Ensure DATABASE_URL is set in your environment or .env file
uv run pytest
```

To run specific tests:
```bash
uv run pytest tests/test_activities.py -v
```

## Project Structure

```
mlcbakery/
├── alembic/              # Database migrations (Alembic)
├── .github/              # GitHub Actions workflows
├── mlcbakery/           # Main application package
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── api/            # API routes (FastAPI)
│   └── main.py         # FastAPI application entrypoint
├── tests/              # Test suite (pytest)
├── .env.example        # Example environment variables
├── alembic.ini         # Alembic configuration
├── pyproject.toml      # Project metadata and dependencies (uv/Poetry)
└── README.md           # This file
```

## Database Schema

Managed by Alembic migrations in the `alembic/versions` directory. The main tables include:
- `collections`
- `entities` (polymorphic base for datasets, models, etc.)
- `datasets`
- `trained_models`
- `activities`
- `agents`
- `activity_relationships` (tracks provenance)

## Resetting the database (Local Development)

If using a local PostgreSQL instance, you can drop and recreate the database:
```bash
# Example commands using psql
# Connect as a superuser or the database owner
dropdb mlcbakery_dev
createdb mlcbakery_dev

# Re-run migrations
uv run alembic upgrade heads
```
*Warning: This deletes all data in the development database.* 

## Contributing

1. Create a new branch for your feature (`git checkout -b feature/my-new-feature`)
2. Make your changes
3. Run tests to ensure everything passes (`uv run pytest`)
4. Commit your changes (`git commit -am 'Add some feature'`)
5. Push to the branch (`git push origin feature/my-new-feature`)
6. Submit a pull request

## License

MIT