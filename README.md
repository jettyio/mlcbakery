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
- PostgreSQL 15+
- Docker and Docker Compose (for running the server)

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/mlcbakery.git
   cd mlcbakery
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your database credentials and other configuration.

5. Initialize the database:
   ```bash
   # Create the database
   createdb mlcbakery

   # Run migrations
   alembic upgrade heads
   ```

### Running Tests

1. Create a test database:
   ```bash
   createdb mlcbakery_test
   ```

2. Run the test suite:
   ```bash
   pytest
   ```

   For verbose output:
   ```bash
   pytest -v
   ```

   To run specific test files:
   ```bash
   pytest tests/test_datasets.py -v
   ```

## Running the Server

### Using Docker Compose

1. Build and start the services:
   ```bash
   docker-compose up --build
   ```

2. Initialize the database:
   ```bash
   # Connect to the PostgreSQL container
   docker-compose exec db psql -U postgres

   # Create the database
   CREATE DATABASE mlcbakery;

   # Exit psql
   \q

   # Run migrations
   docker-compose exec app alembic upgrade head
   ```

3. The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
mlcbakery/
├── alembic/              # Database migrations
├── mlcbakery/           # Main application package
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── api/            # API routes
│   └── core/           # Core functionality
├── tests/              # Test suite
├── docker-compose.yml  # Docker services configuration
├── Dockerfile         # Application container definition
└── requirements.txt   # Production dependencies
```

## Database Schema

The application uses the following main tables:
- `collections`: Groups related datasets
- `datasets`: Stores dataset information
- `entities`: Tracks various entities in the system
- `activities`: Records activities and operations
- `agents`: Manages system agents
- `was_generated_by`: Links datasets to activities
- `was_associated_with`: Links activities to agents

## Resetting the database
```
docker compose exec db psql -U postgres -d mlcbakery -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec web alembic -c alembic.ini upgrade heads
```

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests to ensure everything passes
4. Submit a pull request

## License

MIT