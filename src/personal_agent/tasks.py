from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str = "pending"
    owner: str | None = None
    blocked_by: list[str] | None = None

    def __post_init__(self) -> None:
        if self.blocked_by is None:
            self.blocked_by = []


class TaskStore:
    VALID_STATUSES = {"pending", "in_progress", "completed"}

    def __init__(self, workspace: Path):
        self.root = workspace.resolve() / ".tasks"

    def create(self, subject: str, description: str = "") -> Task:
        subject = subject.strip()
        if not subject:
            raise ValueError("subject must not be empty")
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            task = Task(f"task_{secrets.token_hex(4)}", subject, description.strip())
            path = self.root / f"{task.id}.json"
            try:
                with path.open("x", encoding="utf-8") as handle:
                    json.dump(asdict(task), handle, ensure_ascii=False, indent=2)
                return task
            except FileExistsError:
                continue

    def get(self, task_id: str) -> Task:
        if not task_id.startswith("task_") or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in task_id):
            raise ValueError("invalid task id")
        path = self.root / f"{task_id}.json"
        if not path.is_file():
            raise ValueError(f"task not found: {task_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Task(**data)

    def save(self, task: Task) -> None:
        if task.status not in self.VALID_STATUSES:
            raise ValueError(f"invalid task status: {task.status}")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{task.id}.json").write_text(json.dumps(asdict(task), ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[Task]:
        if not self.root.is_dir():
            return []
        tasks = []
        for path in sorted(self.root.glob("task_*.json")):
            try:
                tasks.append(self.get(path.stem))
            except (ValueError, json.JSONDecodeError, TypeError):
                continue
        return tasks

    def incomplete_dependencies(self, task: Task) -> list[str]:
        incomplete = []
        for dependency_id in task.blocked_by or []:
            dependency = self.get(dependency_id)
            if dependency.status != "completed":
                incomplete.append(dependency_id)
        return incomplete

    def update_dependencies(self, task_id: str, blocked_by: list[str]) -> Task:
        task = self.get(task_id)
        if task.status != "pending" or task.owner is not None:
            raise ValueError("only an unowned pending task can be updated")
        unique = list(dict.fromkeys(blocked_by))
        if task_id in unique:
            raise ValueError("task cannot depend on itself")
        for dependency_id in unique:
            self.get(dependency_id)
        task.blocked_by = unique
        self.save(task)
        return task

    def claim(self, task_id: str, owner: str = "agent") -> Task:
        task = self.get(task_id)
        if task.status != "pending":
            raise ValueError(f"task is {task.status}, cannot claim")
        blocked = self.incomplete_dependencies(task)
        if blocked:
            raise ValueError(f"task is blocked by: {', '.join(blocked)}")
        task.owner, task.status = owner, "in_progress"
        self.save(task)
        return task

    def complete(self, task_id: str, owner: str = "agent") -> Task:
        task = self.get(task_id)
        if task.status != "in_progress":
            raise ValueError(f"task is {task.status}, cannot complete")
        if task.owner != owner:
            raise ValueError(f"task is owned by {task.owner}, not {owner}")
        task.status = "completed"
        self.save(task)
        return task
