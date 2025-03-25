FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Install poetry using uv
RUN uv pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install dependencies using uv
RUN poetry config installer.max-workers 10 && \
    poetry install --no-interaction --no-ansi

# Copy the rest of the application
COPY . .

# Run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 