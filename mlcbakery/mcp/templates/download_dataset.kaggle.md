import os
from kaggle.api.kaggle_api_extended import KaggleApi

# Optionally, set credentials via environment variables
# os.environ['KAGGLE_USERNAME'] = 'your_username'
# os.environ['KAGGLE_KEY'] = 'your_key'

# Initialize the Kaggle API
api = KaggleApi()
api.authenticate()

# Specify the dataset (format: 'owner/dataset-name')
dataset = '{data_path}'  # Example: Wine Reviews dataset

# Download the dataset to the current directory
api.dataset_download_files(dataset, path='.', unzip=True)

print(f"Dataset '{dataset}' downloaded and extracted.")
