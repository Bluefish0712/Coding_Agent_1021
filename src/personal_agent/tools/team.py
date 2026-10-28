from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ..team import TeamRuntime
from .registry import ToolDefinition


def create_team_tools(runtime: TeamRuntime) -> list[ToolDefinition]:
    def spawn(args: dict[str, Any]) -> str:
        try:
            teammate = runtime.spawn(str(args.get("role", "")), str(args.get("task", "")))
            return json.dumps(asdict(teammate), ensure_ascii=False)
        except ValueError as exc:
            return f"team error: {exc}"

    def send(args: dict[str, Any]) -> str:
        try:
            runtime.send(str(args.get("recipient", "")), str(args.get("message", "")))
            return "Message sent."
        except ValueError as exc:
            return f"team error: {exc}"

    def list_team(_args: dict[str, Any]) -> str:
        return "\n".join(f"{item.name} [{item.status}] role={item.role} task={item.current_task}" for item in runtime.list_teammates()) or "No teammates found."

    def schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}

    return [
        ToolDefinition("spawn_teammate", schema("spawn_teammate", "Spawn a persistent teammate after the user confirms the team plan.", {"role": {"type": "string"}, "task": {"type": "string"}}, ["role", "task"]), spawn),
        ToolDefinition("send_teammate", schema("send_teammate", "Send a follow-up task or message to a teammate.", {"recipient": {"type": "string"}, "message": {"type": "string"}}, ["recipient", "message"]), send),
        ToolDefinition("list_teammates", schema("list_teammates", "List teammates and their current lifecycle state.", {}, []), list_team),
    ]
