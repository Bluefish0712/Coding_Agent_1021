from __future__ import annotations

from typing import Any

from ..skills import SkillLoader
from .registry import ToolDefinition


LOAD_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": "Load the full instructions for one available skill by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}


def create_skill_tools(loader: SkillLoader) -> list[ToolDefinition]:
    def load_skill(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        if not name:
            return "skill error: name must not be empty"
        return loader.load(name)

    return [ToolDefinition("load_skill", LOAD_SKILL_SCHEMA, load_skill)]
