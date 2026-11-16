from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from .tasks import TaskStore, Task
from .worktrees import WorktreeManager


@dataclass
class TeamMessage:
    sender: str
    recipient: str
    content: str
    message_type: str = "message"
    metadata: dict | None = None


class MessageBus:
    """A small file-backed mailbox used to keep agent conversations separate."""

    def __init__(self, workspace: Path):
        self.root = workspace.resolve() / ".mailboxes"
        self._condition = threading.Condition()

    def _path(self, agent: str) -> Path:
        if not agent or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in agent):
            raise ValueError("invalid agent name")
        return self.root / f"{agent}.jsonl"

    def send(self, sender: str, recipient: str, content: str, message_type: str = "message", metadata: dict | None = None) -> None:
        message = TeamMessage(sender, recipient, content, message_type, metadata or {})
        with self._condition:
            self.root.mkdir(parents=True, exist_ok=True)
            with self._path(recipient).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(message), ensure_ascii=False) + "\n")
            self._condition.notify_all()

    def read(self, agent: str) -> list[TeamMessage]:
        with self._condition:
            path = self._path(agent)
            if not path.is_file():
                return []
            messages = [TeamMessage(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            path.unlink(missing_ok=True)
            return messages

    def wait(self, agent: str, timeout: float | None = None) -> list[TeamMessage]:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not self._path(agent).is_file():
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return []
                self._condition.wait(remaining)
            return self.read(agent)

    def read_lead(self) -> list[TeamMessage]:
        return self.read("lead")


@dataclass
class Teammate:
    name: str
    role: str
    status: str = "idle"
    current_task: str | None = None
    task_id: str | None = None
    plan_status: str = "not_required"


class TeamRuntime:
    """Lead-owned runtime for spawning and messaging persistent teammates."""

    def __init__(self, workspace: Path, worker: Callable[[str, str], str], task_store: TaskStore | None = None):
        self.bus = MessageBus(workspace)
        self.worker = worker
        self.task_store = task_store
        self.worktrees = WorktreeManager(workspace, task_store) if task_store else None
        self.plans: dict[str, str] = {}
        self.teammates: dict[str, Teammate] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def spawn(self, role: str, initial_task: str) -> Teammate:
        role = role.strip()
        initial_task = initial_task.strip()
        if not role or not initial_task:
            raise ValueError("role and initial_task must not be empty")
        with self._lock:
            name = f"teammate_{secrets.token_hex(3)}"
            teammate = Teammate(name, role, "working", initial_task)
            self.teammates[name] = teammate
            thread = threading.Thread(target=self._run, args=(name, initial_task), daemon=True)
            self._threads[name] = thread
            thread.start()
            return teammate

    def send(self, recipient: str, content: str) -> None:
        with self._lock:
            if recipient not in self.teammates:
                raise ValueError(f"teammate not found: {recipient}")
        self.bus.send("lead", recipient, content)

    def list_teammates(self) -> list[Teammate]:
        with self._lock:
            return list(self.teammates.values())

    def consume_lead_inbox(self) -> list[TeamMessage]:
        return self.bus.read_lead()

    def claim_next_task(self, owner: str) -> Task | None:
        if self.task_store is None:
            return None
        for task in self.task_store.list():
            if task.status != "pending" or self.task_store.incomplete_dependencies(task):
                continue
            try:
                return self.task_store.claim(task.id, owner)
            except ValueError:
                continue
        return None

    def create_worktree(self, name: str, task_id: str) -> Path:
        if self.worktrees is None:
            raise ValueError("task store is not configured")
        return self.worktrees.create(name, task_id)

    def request_plan(self, teammate: str, plan: str) -> str:
        with self._lock:
            item = self.teammates.get(teammate)
            if item is None:
                raise ValueError(f"teammate not found: {teammate}")
            item.plan_status = "pending"
            self.plans[teammate] = plan.strip()
        self.bus.send("lead", teammate, plan, "plan_request")
        return f"plan request sent to {teammate}"

    def approve_plan(self, teammate: str, approved: bool, feedback: str = "") -> str:
        with self._lock:
            item = self.teammates.get(teammate)
            if item is None:
                raise ValueError(f"teammate not found: {teammate}")
            item.plan_status = "approved" if approved else "rejected"
        self.bus.send("lead", teammate, "approved" if approved else "rejected", "plan_approval_response", {"feedback": feedback})
        return f"plan {item.plan_status}: {teammate}"

    def request_shutdown(self, teammate: str) -> str:
        with self._lock:
            if teammate not in self.teammates:
                raise ValueError(f"teammate not found: {teammate}")
        self.bus.send("lead", teammate, "shutdown", "shutdown_request", {"request_id": f"shutdown_{secrets.token_hex(4)}"})
        return f"shutdown requested: {teammate}"

    def shutdown(self) -> None:
        self._stop.set()
        for name in list(self.teammates):
            self.bus.send("lead", name, "shutdown", "shutdown_request")
        for thread in self._threads.values():
            thread.join(timeout=1)

    def _run(self, name: str, initial_task: str) -> None:
        task = initial_task
        while not self._stop.is_set():
            with self._lock:
                self.teammates[name].status = "working"
                plan_status = self.teammates[name].plan_status
            if plan_status in {"pending", "rejected"}:
                time.sleep(0.1)
                continue
            result = self.worker(name, task)
            self.bus.send(name, "lead", result, "result")
            with self._lock:
                self.teammates[name].status = "idle"
                self.teammates[name].current_task = None
            messages = self.bus.wait(name, timeout=0.5)
            for message in messages:
                if message.message_type == "shutdown_request":
                    self.bus.send(name, "lead", "teammate stopped", "shutdown_response")
                    return
                if message.message_type == "plan_request":
                    with self._lock:
                        self.teammates[name].plan_status = "pending"
                    continue
                if message.message_type == "plan_approval_response":
                    with self._lock:
                        self.teammates[name].plan_status = "approved" if message.content == "approved" else "rejected"
                    continue
                if message.content.strip():
                    task = message.content
                    break
            else:
                claimed = self.claim_next_task(name) if self.teammates[name].plan_status == "not_required" else None
                if claimed is not None:
                    task = f"{claimed.subject}\n{claimed.description}".strip()

