from __future__ import annotations

from pathlib import Path
from typing import Any

from .permissions import PermissionPolicy
from .registry import ToolDefinition, ToolHook


TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": "Delegate one focused subtask to a child agent with fresh conversation context and return its final summary.",
        "parameters": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
}


def create_subagent_tools(
    client: Any,
    *,
    workspace: Path,
    max_turns: int = 8,
    permission_policy: PermissionPolicy | None = None,
    before_hooks: list[ToolHook] | None = None,
    after_hooks: list[ToolHook] | None = None,
    error_hooks: list[ToolHook] | None = None,
) -> list[ToolDefinition]:
    def run_subagent(args: dict[str, Any]) -> str:
        prompt = str(args.get("prompt", "")).strip()
        if not prompt:
            return "task error: prompt must not be empty"

        # Local import avoids a module-level AgentLoop/subagent import cycle.
        from ..agent_loop import AgentLoop

        print("[Subagent started]")
        child = AgentLoop(
            client,
            max_turns=max_turns,
            workspace=workspace,
            permission_policy=permission_policy,
            before_hooks=before_hooks,
            after_hooks=after_hooks,
            error_hooks=error_hooks,
            include_subagent=False,
        )
        result = child.run(prompt)
        print("[Subagent done]")
        return f"Subagent result:\n{result or '(no summary)'}"

    return [ToolDefinition("task", TASK_SCHEMA, run_subagent)]
