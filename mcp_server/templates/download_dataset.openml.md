import openml
import pandas as pd

# Specify the OpenML dataset ID
# You can find dataset IDs at https://www.openml.org/search?type=data
# Example: 61 is the ID for the Iris dataset
dataset_id = {data_path}  # e.g., 61 for Iris

# Download the dataset from OpenML
openml_dataset = openml.datasets.get_dataset(dataset_id)
X, y, _, _ = openml_dataset.get_data(target=openml_dataset.default_target_attribute)

# Convert to a pandas DataFrame
# If the dataset has a default target attribute, it will be included as 'y'
df = pd.DataFrame(X)
if y is not None:
    df['target'] = y

print(df.head())