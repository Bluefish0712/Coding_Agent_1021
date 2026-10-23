from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .deepseek_client import DeepSeekClient, DeepSeekError


ToolHandler = Callable[[dict[str, Any]], str]


GET_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Return the current local date and time.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def get_time(_: dict[str, Any]) -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


class AgentLoop:
    def __init__(self, client: DeepSeekClient, *, max_turns: int = 8):
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.client = client
        self.max_turns = max_turns
        self.tools: dict[str, ToolHandler] = {"get_time": get_time}
        self.tool_schemas = [GET_TIME_TOOL]

    def run(self, user_input: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]

        for _ in range(self.max_turns):
            response = self.client.chat(messages, tools=self.tool_schemas)
            assistant_message = response.message
            messages.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls", [])
            if not tool_calls:
                return assistant_message.get("content") or ""

            for call in tool_calls:
                result = self._execute_tool_call(call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        raise DeepSeekError(f"agent stopped after {self.max_turns} turns")

    def _execute_tool_call(self, call: dict[str, Any]) -> str:
        function = call.get("function", {})
        name = function.get("name")
        handler = self.tools.get(name)
        if handler is None:
            return f"tool error: unknown tool {name!r}"
        try:
            arguments = json.loads(function.get("arguments") or "{}")
            if not isinstance(arguments, dict):
                return "tool error: arguments must be a JSON object"
            return handler(arguments)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return f"tool error: invalid arguments: {exc}"

