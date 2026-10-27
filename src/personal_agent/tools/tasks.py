from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ..tasks import TaskStore
from .registry import ToolDefinition


def create_task_tools(store: TaskStore) -> list[ToolDefinition]:
    def create(args: dict[str, Any]) -> str:
        try:
            return json.dumps(asdict(store.create(str(args.get("subject", "")), str(args.get("description", "")))), ensure_ascii=False)
        except ValueError as exc:
            return f"task error: {exc}"

    def list_tasks(_args: dict[str, Any]) -> str:
        return "\n".join(f"{task.id} [{task.status}] {task.subject} blocked_by={task.blocked_by}" for task in store.list()) or "No tasks found."

    def get(args: dict[str, Any]) -> str:
        try:
            return json.dumps(asdict(store.get(str(args.get("task_id", "")))), ensure_ascii=False, indent=2)
        except ValueError as exc:
            return f"task error: {exc}"

    def update(args: dict[str, Any]) -> str:
        try:
            task = store.update_dependencies(str(args.get("task_id", "")), [str(item) for item in args.get("blocked_by", [])])
            return f"Updated {task.id}: blocked_by={task.blocked_by}"
        except (ValueError, TypeError) as exc:
            return f"task error: {exc}"

    def claim(args: dict[str, Any]) -> str:
        try:
            task = store.claim(str(args.get("task_id", "")), str(args.get("owner", "agent")))
            return f"Claimed {task.id} ({task.subject})"
        except ValueError as exc:
            return f"task error: {exc}"

    def complete(args: dict[str, Any]) -> str:
        try:
            task = store.complete(str(args.get("task_id", "")), str(args.get("owner", "agent")))
            return f"Completed {task.id} ({task.subject})"
        except ValueError as exc:
            return f"task error: {exc}"

    def schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}

    return [
        ToolDefinition("create_task", schema("create_task", "Create a persistent task and return its generated ID.", {"subject": {"type": "string"}, "description": {"type": "string"}}, ["subject"]), create),
        ToolDefinition("list_tasks", schema("list_tasks", "List persistent tasks and their statuses.", {}, []), list_tasks),
        ToolDefinition("get_task", schema("get_task", "Get one persistent task by ID.", {"task_id": {"type": "string"}}, ["task_id"]), get),
        ToolDefinition("update_task", schema("update_task", "Set task dependencies using existing task IDs.", {"task_id": {"type": "string"}, "blocked_by": {"type": "array", "items": {"type": "string"}}}, ["task_id", "blocked_by"]), update),
        ToolDefinition("claim_task", schema("claim_task", "Claim an unblocked pending task.", {"task_id": {"type": "string"}, "owner": {"type": "string"}}, ["task_id"]), claim),
        ToolDefinition("complete_task", schema("complete_task", "Complete a task owned by the current agent.", {"task_id": {"type": "string"}, "owner": {"type": "string"}}, ["task_id"]), complete),
    ]
