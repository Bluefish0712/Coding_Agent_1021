from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .permissions import PermissionPolicy


ToolHandler = Callable[[dict[str, Any]], str]
ToolHook = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    """The single place that describes and dispatches local tools."""

    def __init__(
        self,
        definitions: list[ToolDefinition] | None = None,
        *,
        permission_policy: PermissionPolicy | None = None,
        before_hooks: list[ToolHook] | None = None,
        after_hooks: list[ToolHook] | None = None,
        error_hooks: list[ToolHook] | None = None,
    ):
        self._definitions: dict[str, ToolDefinition] = {}
        self.permission_policy = permission_policy or PermissionPolicy()
        self.before_hooks = before_hooks or []
        self.after_hooks = after_hooks or []
        self.error_hooks = error_hooks or []
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
            if not self.permission_policy.allow(name, arguments):
                message = f"permission denied for tool {name!r}"
                self._run_hooks(self.error_hooks, name, arguments)
                return f"tool error: {message}"
            self._run_hooks(self.before_hooks, name, arguments)
            result = definition.handler(arguments)
            self._run_hooks(self.after_hooks, name, arguments)
            return result
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self._run_hooks(self.error_hooks, name, {})
            return f"tool error: invalid arguments: {exc}"
        except Exception as exc:
            self._run_hooks(self.error_hooks, name, {})
            return f"tool error: {type(exc).__name__}: {exc}"

    @staticmethod
    def _run_hooks(hooks: list[ToolHook], name: str | None, arguments: dict[str, Any]) -> None:
        for hook in hooks:
            hook(name or "<unknown>", arguments)

