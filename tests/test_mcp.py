from personal_agent.mcp import MCPManager, normalize_mcp_name
from personal_agent.tools.mcp import create_mcp_tools
from personal_agent.tools.registry import ToolRegistry


def test_mcp_connect_discovers_and_calls_tools():
    manager = MCPManager()
    registry = ToolRegistry()
    registry.register(create_mcp_tools(manager, registry)[0])
    assert "Discovered tools" in registry.execute_call({"function": {"name": "connect_mcp", "arguments": '{"server":"docs"}'}})
    names = [schema["function"]["name"] for schema in registry.schemas()]
    assert "mcp__docs__search" in names
    result = registry.execute_call({"function": {"name": "mcp__docs__search", "arguments": '{"query":"hooks"}'}})
    assert "Hooks" in result


def test_mcp_name_normalization():
    assert normalize_mcp_name("docs.one") == "docs_one"
