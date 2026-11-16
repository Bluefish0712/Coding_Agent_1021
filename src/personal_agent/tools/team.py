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
        return "\n".join(f"{item.name} [{item.status}] role={item.role} task={item.current_task} plan={item.plan_status}" for item in runtime.list_teammates()) or "No teammates found."

    def worktree(args: dict[str, Any]) -> str:
        try:
            path = runtime.create_worktree(str(args.get("name", "")), str(args.get("task_id", "")))
            return f"Worktree created: {path}"
        except ValueError as exc:
            return f"team error: {exc}"

    def request_plan(args: dict[str, Any]) -> str:
        try:
            return runtime.request_plan(str(args.get("recipient", "")), str(args.get("plan", "")))
        except ValueError as exc:
            return f"team error: {exc}"

    def approve_plan(args: dict[str, Any]) -> str:
        try:
            return runtime.approve_plan(str(args.get("recipient", "")), bool(args.get("approved", False)), str(args.get("feedback", "")))
        except ValueError as exc:
            return f"team error: {exc}"

    def shutdown(args: dict[str, Any]) -> str:
        try:
            return runtime.request_shutdown(str(args.get("recipient", "")))
        except ValueError as exc:
            return f"team error: {exc}"

    def schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}

    return [
        ToolDefinition("spawn_teammate", schema("spawn_teammate", "Spawn a persistent teammate after the user confirms the team plan.", {"role": {"type": "string"}, "task": {"type": "string"}}, ["role", "task"]), spawn),
        ToolDefinition("send_teammate", schema("send_teammate", "Send a follow-up task or message to a teammate.", {"recipient": {"type": "string"}, "message": {"type": "string"}}, ["recipient", "message"]), send),
        ToolDefinition("list_teammates", schema("list_teammates", "List teammates and their current lifecycle state.", {}, []), list_team),
        ToolDefinition("create_task_worktree", schema("create_task_worktree", "Create and bind a Git worktree to an unclaimed task.", {"name": {"type": "string"}, "task_id": {"type": "string"}}, ["name", "task_id"]), worktree),
        ToolDefinition("request_teammate_plan", schema("request_teammate_plan", "Request a teammate plan before modifying work.", {"recipient": {"type": "string"}, "plan": {"type": "string"}}, ["recipient", "plan"]), request_plan),
        ToolDefinition("approve_teammate_plan", schema("approve_teammate_plan", "Approve or reject a teammate plan.", {"recipient": {"type": "string"}, "approved": {"type": "boolean"}, "feedback": {"type": "string"}}, ["recipient", "approved"]), approve_plan),
        ToolDefinition("shutdown_teammate", schema("shutdown_teammate", "Request graceful shutdown of one teammate.", {"recipient": {"type": "string"}}, ["recipient"]), shutdown),
    ]
