import datetime as dt
import streamlit as st
from mlcbakery.webclient import client


def parse_url_path():
    """Parse the URL path to extract collection and dataset names."""
    query_params = st._get_query_params()
    collection_name, dataset_name = query_params.get("dataset", [""])[0].split("/")
    return collection_name, dataset_name


def _render_list_of_collections_datasets(bakery_client: client.BakeryClient):
    st.write("Collections")
    for collection in bakery_client.get_collections():
        _collection_name = collection["name"]
        st.write(f"## {_collection_name}")
        for dataset in bakery_client.get_datasets_by_collection(_collection_name):
            # Update session state when button is clicked
            if st.button(dataset["name"], key=f"{_collection_name}/{dataset['name']}"):
                st.session_state["collection_name"] = _collection_name
                st.session_state["dataset_name"] = dataset["name"]
                st.rerun()


def main():
    st.set_page_config(page_title="Dataset Metadata Viewer", layout="wide")

    # Add sidebar for host configuration
    with st.sidebar:
        st.title("Configuration")
        host = st.text_input(
            "Bakery Host",
            value="http://localhost:8000",
            help="Enter the host URL for the Bakery server",
        )
        st.session_state["collection_name"] = st.text_input(
            "Collection Name",
            value=st.session_state.get("collection_name", ""),
            help="Enter the name of the collection to view",
        )
        st.session_state["dataset_name"] = st.text_input(
            "Dataset Name",
            value=st.session_state.get("dataset_name", ""),
            help="Enter the name of the dataset to view",
        )
        bakery_client = client.BakeryClient(host)
    st.title("MLC Bakery")

    # Get collection and dataset from URL path
    dataset_name = st.session_state.get("dataset_name", None)
    collection_name = st.session_state.get("collection_name", None)
    print(collection_name, dataset_name)
    if not collection_name or not dataset_name:
        _render_list_of_collections_datasets(bakery_client)
        st.error("Please provide collection and dataset names in the URL path")
        st.info("Example: /my_collection/my_dataset")
        return

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
        st.metric("Data Path", bakery_dataset.data_path)
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
        st.write(bakery_dataset.preview)


if __name__ == "__main__":
    main()
