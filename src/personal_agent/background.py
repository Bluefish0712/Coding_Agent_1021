from __future__ import annotations

import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackgroundTask:
    task_id: str
    command: str
    status: str = "running"
    result: str = ""


class BackgroundManager:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.tasks: dict[str, BackgroundTask] = {}
        self._ready: list[str] = []
        self._lock = threading.Lock()

    def start(self, command: str, timeout: float, max_chars: int) -> str:
        task_id = f"bg_{uuid.uuid4().hex[:8]}"
        task = BackgroundTask(task_id, command)
        with self._lock:
            self.tasks[task_id] = task
        threading.Thread(target=self._run, args=(task_id, timeout, max_chars), daemon=True).start()
        return task_id

    def _run(self, task_id: str, timeout: float, max_chars: int) -> None:
        task = self.tasks[task_id]
        try:
            completed = subprocess.run(task.command, cwd=self.workspace, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            output = (completed.stdout or "") + (completed.stderr or "")
            if len(output) > max_chars:
                output = output[:max_chars] + "\n(output truncated)"
            status = "completed" if completed.returncode == 0 else "failed"
            result = f"exit_code: {completed.returncode}\n{output}".rstrip()
        except subprocess.TimeoutExpired:
            status, result = "failed", f"background command timed out after {timeout:g}s"
        except Exception as exc:
            status, result = "failed", f"background error: {type(exc).__name__}: {exc}"
        with self._lock:
            task.status = status
            task.result = result
            self._ready.append(task_id)

    def collect(self) -> list[str]:
        with self._lock:
            ready = self._ready[:]
            self._ready.clear()
            return [f"<task_notification id='{task_id}' status='{self.tasks[task_id].status}'>\n{self.tasks[task_id].result}\n</task_notification>" for task_id in ready]
