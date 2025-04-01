# MLCBakery Web Client

This is the web interface for MLCBakery, providing a user-friendly way to view dataset metadata and previews.

## Setup

1. Install the webclient dependencies:
```bash
poetry install --with webclient
```

## Running the Web Interface

To start the Streamlit interface:

```bash
poetry run streamlit run mlcbakery/webclient/dataset_viewer.py
```

## Usage

Access the web interface at `http://localhost:8501` and provide the collection and dataset names as URL parameters:

```
http://localhost:8501/?collection=my_collection&dataset=my_dataset
```

The interface will display:
- Basic dataset information (format, metadata version, creation date)
- Data path
- Preview information (if available)
- Detailed metadata in JSON format (if available)
- Dataset preview (supports image and text previews)

## Development

The webclient is built using Streamlit and is part of the MLCBakery project. It's designed to be an optional component, so users who don't need the web interface can install MLCBakery without the webclient dependencies. 