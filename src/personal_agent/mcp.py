from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Handler = Callable[..., Any]


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    read_only: bool = True


class MCPClient:
    """In-process MCP-shaped client: list tools and call a discovered tool."""

    def __init__(self, server_name: str, tools: list[MCPTool]):
        self.server_name = server_name
        self.tools = list(tools)
        self._handlers = {tool.name: tool.handler for tool in tools}

    def list_tools(self) -> list[MCPTool]:
        return list(self.tools)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"MCP error: unknown tool {tool_name!r}"
        try:
            return str(handler(**arguments))
        except Exception as exc:
            return f"MCP error: {type(exc).__name__}: {exc}"


def _docs_server() -> MCPClient:
    docs = {
        "agent loop": "The agent loop sends messages to the model, executes tool calls, and appends tool results.",
        "hooks": "Hooks run before, after, or when a tool fails.",
        "mcp": "MCP lets a host discover and call tools supplied by an external server.",
    }
    return MCPClient("docs", [
        MCPTool("search", "Search the connected documentation.", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}, lambda query: "\n".join(f"{key}: {value}" for key, value in docs.items() if query.lower() in key or query.lower() in value.lower()) or "No matching docs."),
        MCPTool("get_version", "Get the documentation API version.", {"type": "object", "properties": {}, "required": []}, lambda: "docs-api 1.0"),
    ])


def _deploy_server() -> MCPClient:
    return MCPClient("deploy", [
        MCPTool("status", "Read the current deployment status.", {"type": "object", "properties": {}, "required": []}, lambda: "web: healthy (simulated)"),
        MCPTool("trigger", "Trigger a deployment.", {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}, lambda service: f"deployment queued for {service}", read_only=False),
    ])


MOCK_SERVERS: dict[str, Callable[[], MCPClient]] = {"docs": _docs_server, "deploy": _deploy_server}


def normalize_mcp_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char == "_" else "_" for char in value)
    return safe.strip("_") or "server"


class MCPManager:
    def __init__(self):
        self.clients: dict[str, MCPClient] = {}

    def connect(self, server_name: str) -> str:
        if server_name in self.clients:
            return f"MCP server '{server_name}' already connected"
        factory = MOCK_SERVERS.get(server_name)
        if factory is None:
            return f"Unknown MCP server: {server_name}"
        self.clients[server_name] = factory()
        names = [tool.name for tool in self.clients[server_name].list_tools()]
        return f"Connected MCP server '{server_name}'. Discovered tools: {', '.join(names)}"

    def discovered(self) -> list[tuple[str, MCPClient, MCPTool]]:
        return [(name, client, tool) for name, client in self.clients.items() for tool in client.list_tools()]
