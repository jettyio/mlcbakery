# MLC Bakery MCP Server

This server implements the Model Context Protocol (MCP) to provide tools for interacting with the MLC Bakery API. It allows MCP-compatible clients, such as AI assistants, to easily access MLC Bakery functionalities.

## Use Cases & Features

The server exposes the following tools:

*   **Search Datasets:** Find datasets in MLC Bakery based on a search query.
*   **Get Dataset Preview URL:** Obtain a URL to download a preview of a specific dataset.
*   **Get Croissant Metadata:** Retrieve the ML Croissant metadata (`metadata.jsonld`) for a dataset.
*   **Validate Croissant Metadata:** Validate the structure and content of a Croissant metadata JSON object.
*   **Get Help:** Display help information related to the MLC Bakery API and the available tools.

## Compatibility

This MCP server can be used with various clients that support the Model Context Protocol, including extensions available for editors like:

*   VS Code
*   Cursor

## Connecting

To connect your MCP client to this server, add the following endpoint:

```
https://mcp.jetty.io/sse
```
