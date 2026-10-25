from personal_agent.tools.permissions import PermissionPolicy
from personal_agent.tools.registry import ToolDefinition, ToolRegistry


def schema(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}


def call(name: str, arguments: str = "{}") -> dict:
    return {"id": "1", "function": {"name": name, "arguments": arguments}}


def test_risky_tool_is_denied_without_approval():
    registry = ToolRegistry([
        ToolDefinition("run_command", schema("run_command"), lambda _: "should not run")
    ])
    assert "permission denied" in registry.execute_call(call("run_command"))


def test_approval_and_hooks_wrap_tool_execution():
    events = []
    registry = ToolRegistry(
        [ToolDefinition("run_command", schema("run_command"), lambda _: "ok")],
        permission_policy=PermissionPolicy(lambda name, args: events.append(("approve", name)) or True),
        before_hooks=[lambda name, args: events.append(("before", name))],
        after_hooks=[lambda name, args: events.append(("after", name))],
    )
    assert registry.execute_call(call("run_command")) == "ok"
    assert events == [("approve", "run_command"), ("before", "run_command"), ("after", "run_command")]


def test_read_only_tool_is_allowed_by_default():
    registry = ToolRegistry([ToolDefinition("read_file", schema("read_file"), lambda _: "content")])
    assert registry.execute_call(call("read_file")) == "content"


def test_destructive_command_is_hard_denied_before_approval():
    registry = ToolRegistry(
        [ToolDefinition("run_command", schema("run_command"), lambda _: "must not run")],
        permission_policy=PermissionPolicy(lambda *_: True),
    )
    result = registry.execute_call(call("run_command", '{"command":"rmdir /s /q temp"}'))
    assert "destructive" in result


def test_linux_shell_command_is_hard_denied():
    registry = ToolRegistry(
        [ToolDefinition("run_tests", schema("run_tests"), lambda _: "must not run")],
        permission_policy=PermissionPolicy(lambda *_: True),
    )
    result = registry.execute_call(call("run_tests", '{"command":"cd /workspace; python -m pytest | tail -60"}'))
    assert "Linux-only" in result
