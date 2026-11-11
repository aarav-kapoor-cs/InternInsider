"""
MCP server: the same 5 tools, offered to OTHER AI apps.

MCP (Model Context Protocol) is a standard way for an AI app to discover and
call tools. LangGraph is how OUR agent uses the tools. MCP is how SOMEONE
ELSE'S agent (Claude Desktop, an IDE assistant) can use them, without us
writing anything specific for that app.

Run it:   python -m app.mcp_server
It talks over stdin/stdout ("stdio"), so it prints nothing. The AI app starts
this process itself and exchanges JSON messages with it.
"""
from mcp.server import MCPServer

from app.tools import ALL_TOOLS

server = MCPServer("InternInsider")

for function in ALL_TOOLS:
    # Registers the function. Its name, docstring and type hints become the
    # tool description that the other AI app sees.
    server.tool()(function)

if __name__ == "__main__":
    server.run()  # stdio transport by default
