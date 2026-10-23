from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    """The single place that describes and dispatches local tools."""

    def __init__(self, definitions: list[ToolDefinition] | None = None):
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"tool already registered: {definition.name}")
        schema_name = definition.schema.get("function", {}).get("name")
        if schema_name != definition.name:
            raise ValueError("tool definition name and schema name must match")
        self._definitions[definition.name] = definition

    def schemas(self) -> list[dict[str, Any]]:
        return [definition.schema for definition in self._definitions.values()]

    def execute_call(self, call: dict[str, Any]) -> str:
        function = call.get("function", {})
        name = function.get("name")
        definition = self._definitions.get(name)
        if definition is None:
            return f"tool error: unknown tool {name!r}"
        try:
            arguments = json.loads(function.get("arguments") or "{}")
            if not isinstance(arguments, dict):
                return "tool error: arguments must be a JSON object"
            return definition.handler(arguments)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return f"tool error: invalid arguments: {exc}"

