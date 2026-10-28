from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


def _field_matches(value: int, field: str, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        part = part.strip()
        if part == "*":
            return True
        if part.startswith("*/"):
            step = int(part[2:])
            if step < 1:
                return False
            return (value - minimum) % step == 0
        if "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            if start <= value <= end:
                return True
        elif int(part) == value:
            return True
    return False


def cron_matches(expression: str, moment: datetime) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, weekday = fields
    return (
        _field_matches(moment.minute, minute, 0, 59)
        and _field_matches(moment.hour, hour, 0, 23)
        and _field_matches(moment.day, day, 1, 31)
        and _field_matches(moment.month, month, 1, 12)
        and _field_matches((moment.weekday() + 1) % 7, weekday, 0, 6)
    )


def validate_cron(expression: str) -> None:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron must have five fields: minute hour day month weekday")
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    for field, (minimum, maximum) in zip(fields, ranges):
        for part in field.split(","):
            if part == "*":
                continue
            if part.startswith("*/"):
                if not part[2:].isdigit() or int(part[2:]) < 1:
                    raise ValueError(f"invalid cron step: {part}")
                continue
            values = part.split("-", 1)
            if not all(value.isdigit() for value in values) or not all(minimum <= int(value) <= maximum for value in values):
                raise ValueError(f"invalid cron value: {part}")


@dataclass
class CronJob:
    id: str
    cron: str
    prompt: str
    recurring: bool = True
    durable: bool = True
    pending_delivery: bool = False
    last_fired: str | None = None


class CronScheduler:
    def __init__(self, workspace: Path):
        self.path = workspace.resolve() / ".scheduled_tasks.json"
        self.jobs: dict[str, CronJob] = {}
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._load()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._save()

    def schedule(self, cron: str, prompt: str, recurring: bool = True, durable: bool = True) -> CronJob:
        validate_cron(cron)
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        job = CronJob(f"cron_{secrets.token_hex(4)}", cron, prompt.strip(), recurring, durable)
        with self._lock:
            self.jobs[job.id] = job
            self._save_locked()
        return job

    def list_jobs(self) -> list[CronJob]:
        with self._lock:
            return list(self.jobs.values())

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self.jobs:
                return False
            del self.jobs[job_id]
            self._queue = [item for item in self._queue if item != job_id]
            self._save_locked()
            return True

    def consume(self) -> list[CronJob]:
        with self._lock:
            jobs = [self.jobs[job_id] for job_id in self._queue if job_id in self.jobs]
            self._queue.clear()
            for job in jobs:
                job.pending_delivery = False
                if not job.recurring:
                    self.jobs.pop(job.id, None)
            self._save_locked()
            return jobs

    def _run(self) -> None:
        while not self._stop.wait(1):
            now = datetime.now()
            marker = now.strftime("%Y-%m-%d %H:%M")
            with self._lock:
                for job in self.jobs.values():
                    if job.pending_delivery or job.last_fired == marker:
                        continue
                    if cron_matches(job.cron, now):
                        job.pending_delivery = True
                        job.last_fired = marker
                        self._queue.append(job.id)
                self._save_locked()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.jobs = {item["id"]: CronJob(**item) for item in data}
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
            print(f"warning: could not load scheduled tasks: {exc}")

    def _save(self) -> None:
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        durable = [asdict(job) for job in self.jobs.values() if job.durable]
        self.path.write_text(json.dumps(durable, ensure_ascii=False, indent=2), encoding="utf-8")
