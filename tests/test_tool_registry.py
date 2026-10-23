import pytest

from personal_agent.tools.registry import ToolDefinition, ToolRegistry


def schema(name):
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def test_registry_exposes_schema_and_executes_handler():
    registry = ToolRegistry([
        ToolDefinition("echo", schema("echo"), lambda args: args["value"]),
    ])

    assert registry.schemas() == [schema("echo")]
    assert registry.execute_call({
        "function": {"name": "echo", "arguments": '{"value":"ok"}'},
    }) == "ok"


def test_registry_rejects_duplicate_or_mismatched_tools():
    registry = ToolRegistry([ToolDefinition("echo", schema("echo"), lambda _: "ok")])
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolDefinition("echo", schema("echo"), lambda _: "again"))
    with pytest.raises(ValueError, match="must match"):
        ToolRegistry([ToolDefinition("other", schema("echo"), lambda _: "bad")])


def test_registry_returns_tool_errors():
    registry = ToolRegistry([ToolDefinition("echo", schema("echo"), lambda _: "ok")])
    assert "unknown tool" in registry.execute_call({"function": {"name": "missing", "arguments": "{}"}})
    assert "arguments must be a JSON object" in registry.execute_call({"function": {"name": "echo", "arguments": "[]"}})

