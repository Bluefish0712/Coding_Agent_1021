from __future__ import annotations

from typing import Any

from .registry import ToolDefinition


TODO_WRITE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "todo_write",
        "description": "Replace the agent's current task list and report progress.",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "content": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        },
                        "required": ["id", "content", "status"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["todos"],
            "additionalProperties": False,
        },
    },
}


VALID_STATUSES = {"pending", "in_progress", "completed"}


def create_todo_tools() -> tuple[list[ToolDefinition], list[dict[str, Any]]]:
    state: list[dict[str, Any]] = []

    def todo_write(args: dict[str, Any]) -> str:
        todos = args.get("todos")
        if not isinstance(todos, list):
            return "todo error: todos must be an array"
        validated: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in todos:
            if not isinstance(item, dict):
                return "todo error: every todo must be an object"
            todo_id = str(item.get("id", "")).strip()
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "")).strip()
            if not todo_id or not content:
                return "todo error: each todo needs a non-empty id and content"
            if todo_id in seen:
                return f"todo error: duplicate id {todo_id!r}"
            if status not in VALID_STATUSES:
                return f"todo error: invalid status {status!r}"
            seen.add(todo_id)
            validated.append({"id": todo_id, "content": content, "status": status})

        state.clear()
        state.extend(validated)
        counts = {status: sum(item["status"] == status for item in state) for status in VALID_STATUSES}
        lines = [f"Todo list updated: {len(state)} item(s)"]
        lines.append(f"completed={counts['completed']}, in_progress={counts['in_progress']}, pending={counts['pending']}")
        lines.extend(f"[{item['status']}] {item['id']}: {item['content']}" for item in state)
        return "\n".join(lines)

    return [ToolDefinition("todo_write", TODO_WRITE_SCHEMA, todo_write)], state
