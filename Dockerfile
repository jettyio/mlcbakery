FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry and uvicorn
RUN pip install poetry uvicorn

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install dependencies using poetry
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# Install the application in development mode
RUN pip install -e .

# Set Python path
ENV PYTHONPATH=/app

# Command to run the application
CMD ["poetry", "run", "uvicorn", "mlcbakery.main:app", "--host", "0.0.0.0", "--port", "8000"]
