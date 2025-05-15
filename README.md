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
-   MCP: `http://mcp.localhost/sse` (you may need to add this to your `/etc/hosts` for local development)

## Running the Server (Locally)

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Development steps

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url> mlcbakery
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

## Resetting the database (Local Development)

If using a local PostgreSQL instance, you can drop and recreate the database:
```bash
docker compose exec db psql -U postgres -c "drop DATABASE mlcbakery;"
docker compose exec db psql -U postgres -c "create DATABASE mlcbakery;"
```


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

## Deployment (Docker Compose)

This project includes a `docker-compose.yml` file for easier deployment of the API, database, Streamlit viewer, and Caddy reverse proxy.

### Prerequisites
- Docker and Docker Compose installed.

### Steps

1.  **Configure Environment Variables:**
    The `docker-compose.yml` file sets a default `DATABASE_URL` pointing to the `db` service within the Docker network. However, you **must** configure the `ADMIN_AUTH_TOKEN` for the `api` service. You can do this by:
    *   **Creating a `.env` file:** Create a `.env` file in the project root and add the following line:
        ```env
        ADMIN_AUTH_TOKEN=your_secure_admin_token_here
        ```
        Docker Compose automatically loads `.env` files.
    *   **Modifying `docker-compose.yml`:** Directly add the `ADMIN_AUTH_TOKEN` under the `environment` section of the `api` service (less secure for secrets).
    *   **Passing at runtime:** Use the `-e` flag with `docker-compose up`, e.g., `ADMIN_AUTH_TOKEN=your_secure_admin_token_here docker-compose up -d`.

2.  **Build and Run Services:**
    Navigate to the project root directory and run:
    ```bash
    docker-compose up --build -d
    ```
    This will build the necessary images and start all services (api, mcp_server, streamlit, db, caddy) in the background.

3.  **Database Migrations:**
    Once the `db` and `api` containers are running, apply the database migrations by executing the `alembic` command inside the running `api` container:
    ```bash
    docker-compose exec api alembic upgrade head
    ```
    *Note: You might need to wait a few seconds for the database service to fully initialize before running migrations.*

4.  **Accessing Services:**
    *   **API:** The API will be accessible via the Caddy reverse proxy, typically at `http://localhost` or `http://<your-domain>` if configured in `Caddyfile`. Direct access (bypassing Caddy) is usually on port 8000 if mapped. Swagger UI: `http://localhost/docs` (or `/api/v1/docs` depending on Caddy setup).
    *   **Streamlit Viewer:** Accessible via Caddy, e.g., `http://streamlit.localhost`.
    *   **MCP Server:** Accessible via Caddy, e.g., `http://mcp.localhost`.
    *   **Caddy:** Handles reverse proxying based on `Caddyfile`. Modify `Caddyfile` and restart the `caddy` service (`docker-compose restart caddy`) to update domains or proxy configurations.

### Stopping Services

```bash
docker-compose down
```
To remove the volumes (including database data):
```bash
docker-compose down -v
```

### Important Notes

-   **`ADMIN_AUTH_TOKEN`:** This token is required for any mutable API operations (POST, PUT, PATCH, DELETE). Include it in requests as a Bearer token in the `Authorization` header (e.g., `Authorization: Bearer your_secure_admin_token_here`).
-   **`DATABASE_URL`:** Ensure the `api` and `streamlit` services can reach the database specified by `DATABASE_URL`. The default in `docker-compose.yml` assumes the `db` service within the same Docker network.

### Some useful commands

Add / drop the database:

Once the api server is running, migrate the schema:
```
docker compose exec api alembic -c alembic.ini upgrade heads
```