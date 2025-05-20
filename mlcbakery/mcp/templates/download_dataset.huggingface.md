# Install if necessary
# !pip install datasets pandas

from datasets import load_dataset
import pandas as pd

# 1. Load a sample dataset from Hugging Face
dataset = load_dataset("{data_path}")

# The dataset has different splits (train, test)
print(dataset)

# 2. Take a look at a few examples
print("\nFirst few training examples:")
print(dataset["train"].select(range(5)))

# 3. Convert to a pandas DataFrame for easier exploration
df_train = pd.DataFrame(dataset["train"])

print("\nPandas DataFrame Head:")
print(df_train.head())

# 4. Simple exploration
print("\nBasic info:")
print(df_train.info())
