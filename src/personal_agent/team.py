from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


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


@dataclass
class Teammate:
    name: str
    role: str
    status: str = "idle"
    current_task: str | None = None


class TeamRuntime:
    """Lead-owned runtime for spawning and messaging persistent teammates."""

    def __init__(self, workspace: Path, worker: Callable[[str, str], str]):
        self.bus = MessageBus(workspace)
        self.worker = worker
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
                if message.content.strip():
                    task = message.content
                    break

