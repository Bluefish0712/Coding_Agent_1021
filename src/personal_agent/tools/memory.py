from __future__ import annotations

from typing import Any

from ..memory import MemoryStore
from .registry import ToolDefinition


def create_memory_tools(store: MemoryStore) -> list[ToolDefinition]:
    def remember(args: dict[str, Any]) -> str:
        return store.save(str(args.get("name", "")), str(args.get("description", "")), str(args.get("body", "")), str(args.get("type", "project")))

    def recall_memory(args: dict[str, Any]) -> str:
        return store.format_results(str(args.get("query", "")), int(args.get("limit", 5)))

    return [
        ToolDefinition("remember", {"type": "function", "function": {"name": "remember", "description": "Save a durable memory.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "body": {"type": "string"}, "type": {"type": "string", "enum": sorted(MemoryStore.VALID_TYPES)}}, "required": ["name", "description", "body"], "additionalProperties": False}}}, remember),
        ToolDefinition("recall_memory", {"type": "function", "function": {"name": "recall_memory", "description": "Search durable memories relevant to a query.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"], "additionalProperties": False}}}, recall_memory),
    ]
