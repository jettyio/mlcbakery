#!/bin/bash

# Base URL for the API
BASE_URL="http://localhost:8000/api/v1"
# BASE_URL="https://api.mlcbakery.com/api/v1"

# Create a collection
echo "Creating a collection..."
COLLECTION_RESPONSE=$(curl -s -X POST "${BASE_URL}/collections/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "jon-test-collection",
    "description": "A test collection created via API"
  }')

# Extract collection ID from response
COLLECTION_ID=$(echo $COLLECTION_RESPONSE | jq -r '.id')
echo "Created collection with ID: $COLLECTION_ID"

# Create a dataset in the collection
echo "Creating a dataset..."
DATASET_RESPONSE=$(curl -s -X POST "${BASE_URL}/datasets/" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Titanic Dataset from Kaggle\",
    \"collection_id\": $COLLECTION_ID,
    \"generated_by_id\": 1,
    \"metadata_version\": \"1.0\",
    \"dataset_metadata\": {
      \"description\": \"A test dataset\",
      \"version\": \"1.0\"
    }
  }")

# Extract dataset ID from response
DATASET_ID=$(echo $DATASET_RESPONSE | jq -r '.id')
echo "Created dataset with ID: $DATASET_ID"

# Get the dataset
echo "Retrieving the dataset..."
curl -s -X GET "${BASE_URL}/datasets/${DATASET_ID}" | jq '.' 