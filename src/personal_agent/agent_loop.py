from __future__ import annotations

from typing import Any

from .deepseek_client import DeepSeekClient, DeepSeekError
from .tools.clock import GET_TIME_SCHEMA, get_time
from .tools.registry import ToolDefinition, ToolRegistry


class AgentLoop:
    def __init__(self, client: DeepSeekClient, *, max_turns: int = 8, registry: ToolRegistry | None = None):
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.client = client
        self.max_turns = max_turns
        self.registry = registry or ToolRegistry([
            ToolDefinition(name="get_time", schema=GET_TIME_SCHEMA, handler=get_time),
        ])

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

