from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_loop import AgentLoop
from .config import Settings
from .deepseek_client import DeepSeekClient
from .memory import MemoryStore, build_memory_context
from .mcp import MCPManager
from .scheduler import CronScheduler
from .skills import SkillLoader, build_system_prompt
from .tasks import TaskStore
from .team import TeamRuntime
from .tools.permissions import PermissionPolicy


class AgentHarness:
    """Builds and owns the integrated runtime used by the Lead agent."""

    def __init__(self, settings: Settings, workspace: Path, approval_callback=None):
        self.settings = settings
        self.workspace = workspace.resolve()
        self.client = DeepSeekClient(settings)
        self.approval_callback = approval_callback or (lambda _name, _args: False)
        self.skills = SkillLoader(self.workspace / "skills")
        self.skills.scan()
        self.memory = MemoryStore(self.workspace)
        self.tasks = TaskStore(self.workspace)
        self.scheduler = CronScheduler(self.workspace)
        self.mcp = MCPManager()
        self._closed = False

        def run_teammate(name: str, task: str) -> str:
            prompt = f"你是持久队友 {name}。请独立完成下面的任务，并只返回结果摘要：\n{task}"
            return AgentLoop(
                self.client,
                workspace=self.workspace,
                permission_policy=PermissionPolicy(self.approval_callback),
                include_subagent=False,
            ).run(prompt)

        self.team = TeamRuntime(self.workspace, run_teammate, self.tasks)
        self.scheduler.start()

    def build_agent(self, prompt: str) -> AgentLoop:
        system_prompt = (
            build_system_prompt(self.workspace, self.skills)
            + "\n\n"
            + build_memory_context(self.memory, prompt)
            + "\n\n"
            + self._runtime_context()
        )
        return AgentLoop(
            self.client,
            workspace=self.workspace,
            permission_policy=PermissionPolicy(self.approval_callback),
            skill_loader=self.skills,
            memory_store=self.memory,
            task_store=self.tasks,
            scheduler=self.scheduler,
            team_runtime=self.team,
            mcp_manager=self.mcp,
            system_prompt=system_prompt,
        )

    def _runtime_context(self) -> str:
        connected = ", ".join(sorted(self.mcp.clients)) or "none"
        return f"Integrated runtime: tasks, background, cron, teams, and MCP are enabled. Connected MCP servers: {connected}."

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.team.shutdown()
        self.scheduler.stop()
        self.client.close()

    def __enter__(self) -> "AgentHarness":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()
