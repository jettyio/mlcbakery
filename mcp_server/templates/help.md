# MLC Bakery MCP Tool Instructions

This document outlines how to use the available tools to interact with the MLC Bakery datasets.

## 1. Searching for Datasets

To find datasets based on keywords or topics:

1.  **Use the dataset search tool.** Provide a query string relevant to the datasets you are looking for.
    *   Example: If you're looking for datasets about images, you might search with the query "images" or "image classification".
2.  **Review the results.** The tool will return a list of datasets matching your query, including their names and potentially other relevant details.

*Relevant Tool: Search for datasets using a query string (`mlcbakery://search-datasets/{query}`)*

## 2. Getting and Viewing a Dataset Preview

To download and view a preview of a specific dataset:

1.  **Identify the dataset:** You need the `collection` name and `dataset` name. You might find these using the search tool (Workflow 1) or the list datasets tool (`mlcbakery://datasets/`).
2.  **Get the preview download URL:** Use the tool designed to provide a download URL for the dataset preview, specifying the `collection` and `dataset` name.
    *   Example: For a dataset named `my_images` in the `computer_vision` collection, request the URL for `computer_vision/my_images`.
3.  **Download the Parquet file:** Use the obtained URL to download the preview file. This file will be in Parquet format.
4.  **(External Step) Render the data:** Load the downloaded `.parquet` file using a library like `pandas` in Python to view its contents as a DataFrame.
    ```python
    import pandas as pd

    # Assuming 'preview.parquet' is the downloaded file
    df = pd.read_parquet('preview.parquet')
    print(df.head())
    ```

*Relevant Tool: Get a download URL for a dataset preview (`mlcbakery://datasets-preview-url/{collection}/{dataset}`)*

## 3. Reviewing Dataset Metadata

To examine the detailed metadata (in Croissant format) for a specific dataset:

1.  **Identify the dataset:** You need the `collection` name and `dataset` name.
2.  **Request the metadata:** Use the tool designed to fetch the Croissant metadata, providing the `collection` and `dataset` name.
    *   Example: Request metadata for `computer_vision/my_images`.
3.  **Inspect the JSON-LD:** The tool will return the Croissant metadata as a JSON-LD object. You can review this structure to understand the dataset's fields, distributions, record sets, etc.

*Relevant Tool: Get the Croissant dataset metadata (`mlcbakery://dataset/{collection}/{dataset}/mlcroissant`)*

## 4. Validating Croissant Metadata

To validate the croissant metadata for a dataset, POST the file to `{_BAKERY_HOST}/datasets/mlcroissant-validation` .
Example python code:
```
json_file = io.BytesIO(json.dumps(json_data).encode('utf-8'))
files = {'file': ('metadata.json', json_file, 'application/json')}
response = self._request("POST", endpoint, files=files, headers={})
report = response.json()
```