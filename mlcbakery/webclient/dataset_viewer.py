import datetime as dt
import streamlit as st
from mlcbakery import bakery_client as bc
import os

_HOST = "https://bakery.jetty.io"
_ALL_DATASETS = []
_AUTH_TOKEN = os.getenv("BAKERY_AUTH_TOKEN")


def parse_url_path():
    """Parse the URL path to extract collection and dataset names."""
    query_params = st._get_query_params()
    collection_name, dataset_name = query_params.get("dataset", ["/"])[0].split("/")
    return collection_name, dataset_name


def _get_all_datasets(bakery_client: bc.Client):
    response = bakery_client._request("GET", "/datasets/")
    return [f"{item['collection_name']}/{item['name']}" for item in response.json()]


def main():
    global _ALL_DATASETS
    st.set_page_config(page_title="Dataset Metadata Viewer", layout="wide")
    dataset_name = st.session_state.get("dataset_name", None)
    collection_name = st.session_state.get("collection_name", None)

    if len(_ALL_DATASETS) == 0:
        bakery_client = bc.Client(_HOST, token=_AUTH_TOKEN)
        _ALL_DATASETS = _get_all_datasets(bakery_client)

    # Add sidebar for host configuration
    with st.sidebar:
        st.title("Dataset")
        collection_and_dataset = st.selectbox("Select a dataset", _ALL_DATASETS)
        if collection_and_dataset is None:
            return
        collection_name, dataset_name = collection_and_dataset.split("/")
        st.session_state["collection_name"] = collection_name
        st.session_state["dataset_name"] = dataset_name
        # st.rerun()
    st.title("MLC Bakery")

    st.title(f"Dataset: {collection_name}/{dataset_name}")

    bakery_dataset = bakery_client.get_dataset_by_name(collection_name, dataset_name)

    # dataset = bakery_dataset.metadata
    if not bakery_dataset:
        st.error("Dataset not found")
        return

    # parse the created_at:
    created_at = dt.datetime.strptime(
        bakery_dataset.created_at.split(".")[0], "%Y-%m-%dT%H:%M:%S"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Name", bakery_dataset.name)
        st.metric("Metadata Version", bakery_dataset.format or "N/A")
        st.metric("Created At", created_at.strftime("%Y-%m-%d %H:%M:%S"))

    with col2:
        st.metric("Origin", bakery_dataset.asset_origin)
        st.metric("Path", bakery_dataset.data_path)
        # data lineage:
        upstream_entities = bakery_client.get_upstream_entities(
            collection_name, dataset_name
        )
        st.write(upstream_entities)

    # Display detailed metadata if available
    if bakery_dataset.metadata:
        st.subheader("Croissant Metadata")
        st.write(bakery_dataset.metadata.metadata)

    if bakery_dataset.preview is not None:
        st.subheader("Preview")
        st.write(bakery_dataset.preview.head())

    st.write(bakery_dataset.long_description)


if __name__ == "__main__":
    main()
