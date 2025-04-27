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

To check if a given Croissant metadata JSON structure is valid according to the standard:

1.  **Prepare the metadata:** Have the Croissant metadata available as a JSON object (Python dictionary). This could be metadata you've created or modified.
2.  **Use the validation tool:** Provide the JSON object to the validation tool.
3.  **Review the validation report:** The tool will return a report indicating whether the metadata is valid. If there are errors or warnings, the report will provide details on what needs to be corrected.

*Relevant Tool: Validate MLCommons Croissant metadata JSON (`mlcbakery://validate-croissant-ds/`)*

---

You can also use the `mlcbakery://help` tool to get general help information.
