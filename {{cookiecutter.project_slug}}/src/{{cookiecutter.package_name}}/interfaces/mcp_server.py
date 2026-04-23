"""MCP server exposing agent tools via Model Context Protocol.

Allows this agent's tools to be used by Claude Desktop, other MCP
clients, or composed into multi-agent systems.

Run with::

    {{ cookiecutter.project_slug }}-mcp          # via script entry point
    uv run mcp run {{ cookiecutter.package_name }}.interfaces.mcp_server:mcp  # via mcp CLI
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from {{ cookiecutter.package_name }}.agents.conversational import TOOL_REGISTRY

mcp = FastMCP("{{ cookiecutter.project_name }}")

# Dynamically register each tool from the agent's tool registry.
# FastMCP uses the function signature and docstring to generate the
# MCP tool schema automatically.
for _name, _fn in TOOL_REGISTRY.items():
    mcp.tool(name=_name)(_fn)


def main() -> None:
    """Entry point for the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
