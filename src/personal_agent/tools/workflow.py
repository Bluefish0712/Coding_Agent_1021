from __future__ import annotations

import json
from typing import Any

from ..workflow import REVIEW_META, WorkflowRuntime, review_changes
from .registry import ToolDefinition


def create_workflow_tools(runtime: WorkflowRuntime) -> list[ToolDefinition]:
    def run_workflow(args: dict[str, Any]) -> str:
        name = str(args.get("name", ""))
        if name != REVIEW_META.name:
            return f"workflow error: unknown workflow {name!r}"
        run = runtime.run(
            review_changes,
            REVIEW_META,
            args.get("args") or {},
            args.get("resume_from_run_id"),
        )
        return json.dumps({"run_id": run.run_id, "status": run.status, "phase": run.phase, "result": run.result, "error": run.error, "agent_calls": run.agent_calls, "progress": run.progress}, ensure_ascii=False)

    schema = {"type": "function", "function": {"name": "run_workflow", "description": "Run or resume a trusted, saved workflow by name.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "args": {"type": "object"}, "resume_from_run_id": {"type": "string"}}, "required": ["name"], "additionalProperties": False}}}
    return [ToolDefinition("run_workflow", schema, run_workflow)]
