from __future__ import annotations

from typing import Any
from pathlib import Path

from .deepseek_client import DeepSeekClient, DeepSeekError
from .tools.clock import GET_TIME_SCHEMA, get_time
from .tools.filesystem import create_filesystem_tools
from .tools.command import create_command_tools
from .tools.registry import ToolDefinition, ToolRegistry
from .tools.permissions import PermissionPolicy
from .tools.todo import create_todo_tools


class AgentLoop:
    def __init__(self, client: DeepSeekClient, *, max_turns: int = 8, registry: ToolRegistry | None = None, workspace: Path | None = None, permission_policy: PermissionPolicy | None = None, before_hooks=None, after_hooks=None, error_hooks=None):
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.client = client
        self.max_turns = max_turns
        default_tools = [ToolDefinition(name="get_time", schema=GET_TIME_SCHEMA, handler=get_time)]
        default_tools.extend(create_filesystem_tools(workspace or Path.cwd()))
        default_tools.extend(create_command_tools(workspace or Path.cwd()))
        todo_tools, _ = create_todo_tools()
        default_tools.extend(todo_tools)
        self.registry = registry or ToolRegistry(default_tools, permission_policy=permission_policy, before_hooks=before_hooks, after_hooks=after_hooks, error_hooks=error_hooks)

    def run(self, user_input: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]

        for _ in range(self.max_turns):
            response = self.client.chat(messages, tools=self.registry.schemas())
            assistant_message = response.message
            messages.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls", [])
            if not tool_calls:
                return assistant_message.get("content") or ""

            for call in tool_calls:
                result = self.registry.execute_call(call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        raise DeepSeekError(f"agent stopped after {self.max_turns} turns")

