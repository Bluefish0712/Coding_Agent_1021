from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .tasks import TaskStore


class WorktreeManager:
    """Creates task-bound Git worktrees; cleanup remains an explicit host action."""

    NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0, forty}$".replace(" forty", "39"))

    def __init__(self, workspace: Path, tasks: TaskStore):
        self.workspace = workspace.resolve()
        self.tasks = tasks
        self.root = self.workspace / ".worktrees"

    def create(self, name: str, task_id: str) -> Path:
        if not self.NAME.fullmatch(name):
            raise ValueError("invalid worktree name")
        task = self.tasks.get(task_id)
        if task.status != "pending" or task.owner is not None or task.worktree:
            raise ValueError("worktree requires an unowned pending task without a worktree")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / name
        branch = f"wt/{name}"
        if target.exists():
            raise ValueError(f"worktree already exists: {name}")
        try:
            subprocess.run(["git", "worktree", "add", "-b", branch, str(target)], cwd=self.workspace, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise ValueError(f"could not create worktree: {detail.strip()}") from exc
        task.worktree = str(target)
        self.tasks.save(task)
        return target
