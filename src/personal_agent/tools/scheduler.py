from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ..scheduler import CronScheduler
from .registry import ToolDefinition


def create_scheduler_tools(scheduler: CronScheduler) -> list[ToolDefinition]:
    def schedule(args: dict[str, Any]) -> str:
        try:
            job = scheduler.schedule(str(args.get("cron", "")), str(args.get("prompt", "")), bool(args.get("recurring", True)), bool(args.get("durable", True)))
            return json.dumps(asdict(job), ensure_ascii=False)
        except ValueError as exc:
            return f"cron error: {exc}"

    def list_crons(_args: dict[str, Any]) -> str:
        return "\n".join(f"{job.id}: {job.cron} -> {job.prompt} durable={job.durable}" for job in scheduler.list_jobs()) or "No cron jobs found."

    def cancel(args: dict[str, Any]) -> str:
        job_id = str(args.get("job_id", ""))
        return f"Cron job cancelled: {job_id}" if scheduler.cancel(job_id) else f"cron error: job not found: {job_id}"

    def schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}

    return [
        ToolDefinition("schedule_cron", schema("schedule_cron", "Schedule a prompt for a local cron expression.", {"cron": {"type": "string"}, "prompt": {"type": "string"}, "recurring": {"type": "boolean"}, "durable": {"type": "boolean"}}, ["cron", "prompt"]), schedule),
        ToolDefinition("list_crons", schema("list_crons", "List scheduled prompt jobs.", {}, []), list_crons),
        ToolDefinition("cancel_cron", schema("cancel_cron", "Cancel a scheduled prompt job.", {"job_id": {"type": "string"}}, ["job_id"]), cancel),
    ]
