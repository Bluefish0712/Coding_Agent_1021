from __future__ import annotations

from typing import Any

from ..mcp import MCPManager, normalize_mcp_name
from .registry import ToolDefinition, ToolRegistry


def create_mcp_tools(manager: MCPManager, registry: ToolRegistry) -> list[ToolDefinition]:
    def connect(args: dict[str, Any]) -> str:
        result = manager.connect(str(args.get("server", "")))
        if result.startswith("Connected"):
            _register_discovered(manager, registry)
        return result

    schema = {"type": "function", "function": {"name": "connect_mcp", "description": "Connect an MCP server and discover its tools.", "parameters": {"type": "object", "properties": {"server": {"type": "string"}}, "required": ["server"], "additionalProperties": False}}}
    return [ToolDefinition("connect_mcp", schema, connect)]


def _register_discovered(manager: MCPManager, registry: ToolRegistry) -> None:
    origins: dict[str, tuple[str, str]] = {}
    for server, client, tool in manager.discovered():
        safe_server = normalize_mcp_name(server)
        safe_tool = normalize_mcp_name(tool.name)
        name = f"mcp__{safe_server}__{safe_tool}"
        if len(name) > 64:
            raise ValueError(f"MCP tool name too long: {name}")
        previous = origins.get(name)
        if previous and previous != (server, tool.name):
            raise ValueError(f"MCP tool name collision: {name}")
        origins[name] = (server, tool.name)
        if name in registry.names():
            continue
        schema = {"type": "function", "function": {"name": name, "description": tool.description, "parameters": tool.input_schema}}
        registry.register(ToolDefinition(name, schema, lambda args, c=client, raw=tool.name: c.call_tool(raw, args)))
