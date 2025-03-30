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
    \"entity_type\": \"dataset\",
    \"data_path\": \"/data/titanic.csv\",
    \"format\": \"csv\",
    \"collection_id\": $COLLECTION_ID,
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

# Create a trained model
echo "Creating a trained model..."
MODEL_RESPONSE=$(curl -s -X POST "${BASE_URL}/trained_models/" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Titanic Survival Predictor\",
    \"entity_type\": \"trained_model\",
    \"model_path\": \"/models/titanic_survival.joblib\",
    \"framework\": \"scikit-learn\",
    \"collection_id\": $COLLECTION_ID,
    \"metadata_version\": \"1.0\",
    \"model_metadata\": {
      \"description\": \"A trained model for predicting Titanic passenger survival\",
      \"version\": \"1.0\",
      \"model_type\": \"RandomForestClassifier\",
      \"metrics\": {
        \"accuracy\": 0.82,
        \"precision\": 0.81,
        \"recall\": 0.79,
        \"f1_score\": 0.80
      }
    }
  }")

# Extract model ID from response
MODEL_ID=$(echo $MODEL_RESPONSE | jq -r '.id')
echo "Created model with ID: $MODEL_ID"

# Get the model
echo "Retrieving the model..."
curl -s -X GET "${BASE_URL}/trained_models/${MODEL_ID}" | jq '.'

# Create an agent
echo "Creating an agent..."
AGENT_RESPONSE=$(curl -s -X POST "${BASE_URL}/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Scientist",
    "type": "human"
  }')

# Extract agent ID from response
AGENT_ID=$(echo $AGENT_RESPONSE | jq -r '.id')
echo "Created agent with ID: $AGENT_ID"

# Get the agent
echo "Retrieving the agent..."
curl -s -X GET "${BASE_URL}/agents/${AGENT_ID}" | jq '.'

# Create an activity linking the dataset, model, and agent
echo "Creating an activity..."
ACTIVITY_RESPONSE=$(curl -s -X POST "${BASE_URL}/activities/" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Titanic Model Training\",
    \"input_dataset_ids\": [$DATASET_ID],
    \"output_model_id\": $MODEL_ID,
    \"agent_ids\": [$AGENT_ID]
  }")

# Extract activity ID from response
ACTIVITY_ID=$(echo $ACTIVITY_RESPONSE | jq -r '.id')
echo "Created activity with ID: $ACTIVITY_ID"

# Get the activity
echo "Retrieving the activity..."
curl -s -X GET "${BASE_URL}/activities/${ACTIVITY_ID}" | jq '.' 