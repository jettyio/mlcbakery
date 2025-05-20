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

### Example code:
```
import pandas as pd
import requests
import io
response = requests.get('{_BAKERY_HOST}/datasets/{collection}/{dataset}/preview')
if response.status_code == 200:
    df = pd.read_parquet(io.BytesIO(response.content))
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

## 5. Creating MLCommons Croissant Files

MLCommons Croissant ([https://arxiv.org/html/2403.19546v2](https://arxiv.org/html/2403.19546v2)) is a metadata format for ML datasets. While using the [online editor](https://huggingface.co/spaces/MLCommons/croissant-editor) is recommended, you can also create the JSON-LD file manually:

1.  **Basic Setup:** Create a JSON file with `@context` pointing to the Croissant vocabulary and `@type` set to `sc:Dataset`.
2.  **Dataset Metadata:** Add top-level keys for `name`, `description`, `license`, `url`, etc.
3.  **Resources (`distribution`):** Define each data file (URL or path) using the `distribution` array. Specify `contentUrl`, `encodingFormat`, `sha256`, etc., for each file object.
4.  **Structure (`recordSet`):** Define one or more `recordSet`s. Each `recordSet` contains `field`s (columns/attributes).
5.  **Fields (`field`):** For each `field`, define its `name`, `description`, `dataType` (e.g., `sc:Text`, `sc:ImageObject`). Link it to the data using `source`, specifying the `distribution` and extraction method (e.g., `extract.column` for CSVs).
6.  **Semantics:** Add semantic meaning to fields where applicable.

Refer to the official Croissant specification ([https://mlcommons.org/croissant/1.0](https://mlcommons.org/croissant/1.0)) for full details on available properties and structure.