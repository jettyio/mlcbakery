# MLC Bakery

A Python-based service for managing ML model provenance and lineage, built with FastAPI and SQLAlchemy. Support for Croissant metadata validation.

## Features

- Dataset management with collection support
- Entity tracking
- Activity logging
- Provenance relationships tracking
- RESTful API endpoints

## Running with Docker

1.  **Set up Environment Variables:**
    Create a `.env` file in the project root by copying the example:
    ```bash
    cp env.example .env
    ```

2. **Start docker containers:**
    The bakery relies on a postgres database and Typesense for search. The MCP server makes REST calls to the API server, which then calls the persistence layer.
    ```
    docker compose up -d
    ```

3.  **Run Database Migrations:**
    Apply the latest database schema using Alembic. `uv run` executes commands within the project's managed environment.
    ```bash
    docker compose exec db psql -U postgres -c "create DATABASE mlcbakery;"
    docker compose exec api alembic upgrade head
    ```
## Access the bakery
By default, the API will be available on localhost.
-   Swagger UI: `http://bakery.localhost/docs`
-   ReDoc: `http://bakery.localhost/redoc`
-   Streamable MCP HTTP: `http://mcp.localhost/mcp` (you may need to add this to your `/etc/hosts` for local development)

## Running the Server (Locally)

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Development steps

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:jettyio/mlcbakery.git
    cd mlcbakery
    ```

2.  **Install Dependencies:**
    `uv` uses `pyproject.toml` to manage dependencies. It will automatically create a virtual environment if one doesn't exist.
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    ```
    pip install poetry uvicorn
    uv run poetry install --no-interaction --no-ansi --no-root --with mcp
    ```
Start the FastAPI application using uvicorn:
```bash
# Make sure your .env file is present for the DATABASE_URL
uv run uvicorn mlcbakery.main:app --reload --host 0.0.0.0 --port 8000
```

### Authentication
The Bakery is setup to authenticate requests with two methods: JWT Tokens and a "Master Admin Token". Both are configured in the ENV variables (.env file). Both JWT tokens and the Master Admin Token should be provided as "Bearer" Authorization header values.

- ADMIN_AUTH_TOKEN: A fixed value that is the token a user would need to provide to have admin permissions (unrestricted access to all resources).
- JWT_VERIFICATION_STRATEGY: The URL of a trusted JWT token issuer, such as Clerk. We have a development instance of Clerk running that you can use in conjunction with the Spot application. You can sign up for an account via Spot, or contact jon@jetty.io or grayden@graydens.ca for access to the Clerk admin portal.

### Running Tests

The tests are configured to run against a PostgreSQL database defined by the `DATABASE_URL` environment variable. You can use the same database as your development environment or configure a separate test database in your `.env` file if preferred (adjust connection string as needed).

```bash
# Ensure DATABASE_URL is set in your environment or .env file
uv run pytest
```
