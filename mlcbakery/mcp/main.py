import argparse

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

from mlcbakery.mcp import tools


from mcp.server.session import ServerSession

####################################################################################
# Temporary monkeypatch which avoids crashing when a POST message is received
# before a connection has been initialized, e.g: after a deployment.
# pylint: disable-next=protected-access
old__received_request = ServerSession._received_request


async def _received_request(self, *args, **kwargs):
    try:
        return await old__received_request(self, *args, **kwargs)
    except RuntimeError:
        pass


# pylint: disable-next=protected-access
ServerSession._received_request = _received_request
####################################################################################

mcp = FastMCP("MLC-Bakery-MPC")


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]


mcp.tool("validate-croissant", description="Validate a Croissant metadata file")(
    tools.validate_croissant
)
mcp.tool("download-dataset", description="download a dataset")(tools.download_dataset)
mcp.tool(
    "datasets-preview-url", description="get a download url for a dataset preview"
)(tools.get_dataset_preview_url)
mcp.tool("search-datasets", description="Search for datasets using a query string")(
    tools.search_datasets_tool
)
mcp.tool("help", description="Get help for the MLC Bakery API")(tools.get_help)
mcp.tool("dataset/mlcroissant", description="Get the Croissant dataset template")(
    tools.get_dataset_metadata
)

if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # noqa: WPS437

    parser = argparse.ArgumentParser(description="Run MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    mcp.settings.port = args.port
    mcp.settings.host = args.host
    # mcp.run(transport="sse")
    mcp.run(transport="streamable-http")
