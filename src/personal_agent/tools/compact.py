from __future__ import annotations

from .registry import ToolDefinition


COMPACT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "compact",
        "description": "Archive earlier conversation context and keep a compact recent history.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def create_compact_tools() -> list[ToolDefinition]:
    def compact(_args: dict) -> str:
        return "compaction requested; the agent will compact context after this tool batch"

    return [ToolDefinition("compact", COMPACT_SCHEMA, compact)]
