from __future__ import annotations

from typing import Any
from pathlib import Path

from .deepseek_client import DeepSeekClient, DeepSeekError
from .tools.clock import GET_TIME_SCHEMA, get_time
from .tools.filesystem import create_filesystem_tools
from .tools.command import create_command_tools
from .tools.registry import ToolDefinition, ToolRegistry
from .tools.permissions import PermissionPolicy
from .tools.todo import create_todo_tools
from .tools.subagent import create_subagent_tools
from .skills import SkillLoader
from .tools.skills import create_skill_tools
from .tools.compact import create_compact_tools
from .context import ContextCompactor
from .memory import MemoryStore
from .tools.memory import create_memory_tools
from .tasks import TaskStore
from .tools.tasks import create_task_tools
from .background import BackgroundManager
from .scheduler import CronScheduler
from .tools.scheduler import create_scheduler_tools
from .team import TeamRuntime
from .tools.team import create_team_tools


class AgentLoop:
    def __init__(self, client: DeepSeekClient, *, max_turns: int = 8, registry: ToolRegistry | None = None, workspace: Path | None = None, permission_policy: PermissionPolicy | None = None, before_hooks=None, after_hooks=None, error_hooks=None, include_subagent: bool = True, skill_loader: SkillLoader | None = None, system_prompt: str | None = None, compactor: ContextCompactor | None = None, memory_store: MemoryStore | None = None, task_store: TaskStore | None = None, scheduler: CronScheduler | None = None, team_runtime: TeamRuntime | None = None):
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.client = client
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self.compactor = compactor or ContextCompactor(workspace or Path.cwd())
        self.background = BackgroundManager(workspace or Path.cwd())
        self.scheduler = scheduler
        self.team_runtime = team_runtime
        default_tools = [ToolDefinition(name="get_time", schema=GET_TIME_SCHEMA, handler=get_time)]
        default_tools.extend(create_filesystem_tools(workspace or Path.cwd()))
        default_tools.extend(create_command_tools(workspace or Path.cwd(), self.background))
        todo_tools, _ = create_todo_tools()
        default_tools.extend(todo_tools)
        if include_subagent:
            default_tools.extend(create_subagent_tools(client, workspace=workspace or Path.cwd(), max_turns=max_turns, permission_policy=permission_policy, before_hooks=before_hooks, after_hooks=after_hooks, error_hooks=error_hooks))
        if skill_loader is not None:
            default_tools.extend(create_skill_tools(skill_loader))
        default_tools.extend(create_compact_tools())
        if memory_store is not None:
            default_tools.extend(create_memory_tools(memory_store))
        if task_store is not None:
            default_tools.extend(create_task_tools(task_store))
        if scheduler is not None:
            default_tools.extend(create_scheduler_tools(scheduler))
        if team_runtime is not None:
            default_tools.extend(create_team_tools(team_runtime))
        self.registry = registry or ToolRegistry(default_tools, permission_policy=permission_policy, before_hooks=before_hooks, after_hooks=after_hooks, error_hooks=error_hooks)

    def run(self, user_input: str) -> str:
        messages: list[dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_input})

        for _ in range(self.max_turns):
            notifications = self.background.collect()
            for notification in notifications:
                messages.append({"role": "user", "content": notification})
            if self.scheduler is not None:
                for job in self.scheduler.consume():
                    messages.append({"role": "user", "content": f"[Scheduled {job.id}] {job.prompt}"})
            messages = self.compactor.prepare(messages, user_input)
            response = self.client.chat(messages, tools=self.registry.schemas())
            assistant_message = response.message
            messages.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls", [])
            if not tool_calls:
                return assistant_message.get("content") or ""

            compact_requested = False
            for call in tool_calls:
                result = self.registry.execute_call(call)
                compact_requested = compact_requested or call.get("function", {}).get("name") == "compact"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
            if compact_requested:
                messages = self.compactor.compact(messages, user_input, reason="requested")

        raise DeepSeekError(f"agent stopped after {self.max_turns} turns")

