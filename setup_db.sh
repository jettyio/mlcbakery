#!/bin/bash

# Check if DATABASE_URL is provided
if [ -z "$1" ]; then
    echo "Usage: ./setup_db.sh <DATABASE_URL>"
    echo "Example: ./setup_db.sh postgresql://username:password@host:5432/dbname"
    exit 1
fi

# Set the database URL
export DATABASE_URL="$1"

# Update alembic.ini with the new database URL
sed -i '' "s|sqlalchemy.url = .*|sqlalchemy.url = $DATABASE_URL|" alembic.ini

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "Database setup complete!" 