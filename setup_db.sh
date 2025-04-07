#!/bin/bash

# Check if DATABASE_URL is provided
if [ -z "$1" ]; then
    echo "Usage: ./setup_db.sh <DATABASE_URL>"
    echo "Example: ./setup_db.sh postgresql://username:password@host:5432/dbname"
    exit 1
fi

# Set the database URL
export DATABASE_URL="$1"

# Extract database name from URL
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
DB_URL_WITHOUT_DB=$(echo $DATABASE_URL | sed "s/\/${DB_NAME}.*$//")

# Drop the database if it exists
echo "Dropping database if it exists..."
PGPASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p') psql -h $(echo $DATABASE_URL | sed -n 's/.*@\([^/]*\)\/.*/\1/p') -U $(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p') -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"

# Create a new database
echo "Creating new database..."
PGPASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p') psql -h $(echo $DATABASE_URL | sed -n 's/.*@\([^/]*\)\/.*/\1/p') -U $(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p') -d postgres -c "CREATE DATABASE ${DB_NAME};"

# Update alembic.ini with the new database URL
sed -i '' "s|sqlalchemy.url = .*|sqlalchemy.url = $DATABASE_URL|" alembic.ini

# Run migrations
echo "Running database migrations..."
alembic upgrade heads

echo "Database setup complete!" 