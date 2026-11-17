from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor

from .deepseek_client import DeepSeekClient


class WorkflowInputError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowMeta:
    name: str
    description: str
    phases: tuple[str, ...] = ()


@dataclass
class WorkflowRun:
    run_id: str
    workflow: str
    args: dict[str, Any]
    status: str = "running"
    phase: str = "starting"
    progress: list[dict[str, Any]] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    agent_calls: int = 0


class WorkflowJournal:
    def __init__(self, path: Path):
        self.path = path
        self.cache: dict[str, Any] = {}
        self._lock = threading.Lock()
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    self.cache[item["key"]] = item["value"]

    def cached(self, key: str) -> tuple[bool, Any]:
        return (key in self.cache, self.cache.get(key))

    def record(self, key: str, value: Any) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")
                handle.flush()
            self.cache[key] = value


class WorkflowContext:
    def __init__(self, runner: Callable[[str, dict[str, Any] | None], Any], run: WorkflowRun, journal: WorkflowJournal):
        self.runner = runner
        self.run = run
        self.journal = journal

    def phase(self, title: str) -> None:
        self.run.phase = title
        self.run.progress.append({"type": "phase", "title": title})

    def log(self, message: str) -> None:
        self.run.progress.append({"type": "log", "message": message})

    def agent(self, prompt: str, *, schema: dict[str, Any] | None = None, label: str = "agent") -> Any:
        basis = json.dumps([label, prompt, schema], sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(basis.encode("utf-8")).hexdigest()
        hit, value = self.journal.cached(key)
        if hit:
            self.run.progress.append({"type": "agent", "label": label, "status": "cached"})
            return value
        self.run.progress.append({"type": "agent", "label": label, "status": "started"})
        self.run.agent_calls += 1
        value = self.runner(prompt, schema)
        if schema is not None:
            value = self._validate_json(value, schema)
        self.journal.record(key, value)
        self.run.progress.append({"type": "agent", "label": label, "status": "completed"})
        return value

    def parallel(self, calls: list[Callable[[], Any]]) -> list[Any]:
        with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
            futures = [pool.submit(call) for call in calls]
            return [future.result() for future in futures]

    def pipeline(self, items: list[Any], *stages: Callable[..., Any]) -> list[Any]:
        def process(item: Any, index: int) -> Any:
            value = item
            for stage in stages:
                value = stage(value, item, index)
            return value
        with ThreadPoolExecutor(max_workers=max(1, len(items))) as pool:
            futures = [pool.submit(process, item, index) for index, item in enumerate(items)]
            return [future.result() for future in futures]

    @staticmethod
    def _validate_json(value: Any, schema: dict[str, Any]) -> Any:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise WorkflowInputError(f"agent output is not valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowInputError("structured agent output must be a JSON object")
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise WorkflowInputError(f"agent output missing required fields: {', '.join(missing)}")
        properties = schema.get("properties", {})
        for key, definition in properties.items():
            if key not in value:
                continue
            expected = definition.get("type")
            actual = value[key]
            valid = {
                "string": lambda v: isinstance(v, str),
                "boolean": lambda v: isinstance(v, bool),
                "array": lambda v: isinstance(v, list),
                "object": lambda v: isinstance(v, dict),
                "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
                "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            }.get(expected, lambda _v: True)
            if not valid(actual):
                raise WorkflowInputError(f"agent output field {key!r} must be {expected}")
        return value


class WorkflowRuntime:
    NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

    def __init__(self, workspace: Path, runner: Callable[[str, dict[str, Any] | None], Any]):
        self.root = workspace.resolve() / ".workflows"
        self.runner = runner
        self._lock = threading.Lock()

    def run(self, workflow: Callable, meta: WorkflowMeta, args: dict[str, Any] | None = None, resume_from_run_id: str | None = None) -> WorkflowRun:
        self._validate_meta(meta)
        arguments = args or {}
        self.root.mkdir(parents=True, exist_ok=True)
        run_id = resume_from_run_id or f"run_{secrets.token_hex(6)}"
        snapshot = self.root / f"{run_id}.json"
        journal_path = self.root / f"{run_id}.journal.jsonl"
        if resume_from_run_id:
            self._validate_run_id(run_id)
            if not snapshot.is_file():
                raise WorkflowInputError(f"workflow run not found: {run_id}")
            saved = json.loads(snapshot.read_text(encoding="utf-8"))
            if saved["workflow"] != meta.name or saved["args"] != arguments:
                raise WorkflowInputError("resume workflow name and args must match the saved run")
            run = WorkflowRun(**saved)
            run.status, run.error = "running", None
            run.agent_calls = 0
        else:
            run = WorkflowRun(run_id, meta.name, arguments)
        journal = WorkflowJournal(journal_path)
        self._save(snapshot, run)
        context = WorkflowContext(self.runner, run, journal)
        try:
            run.result = workflow(context, arguments)
            run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
        self._save(snapshot, run)
        return run

    def load_run(self, run_id: str) -> WorkflowRun:
        self._validate_run_id(run_id)
        path = self.root / f"{run_id}.json"
        if not path.is_file():
            raise WorkflowInputError(f"workflow run not found: {run_id}")
        return WorkflowRun(**json.loads(path.read_text(encoding="utf-8")))

    def _save(self, path: Path, run: WorkflowRun) -> None:
        with self._lock:
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(run), ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)

    def _validate_meta(self, meta: WorkflowMeta) -> None:
        if not isinstance(meta, WorkflowMeta) or not meta.name or not meta.description:
            raise WorkflowInputError("workflow metadata requires name and description")
        if not self.NAME_RE.fullmatch(meta.name):
            raise WorkflowInputError("workflow name must be a 1-64 character safe slug")
        if not all(isinstance(phase, str) and phase for phase in meta.phases):
            raise WorkflowInputError("workflow phases must be non-empty strings")

    def _validate_run_id(self, run_id: str) -> None:
        if not re.fullmatch(r"run_[0-9a-f]{12}", run_id):
            raise WorkflowInputError("invalid workflow run ID")


FINDINGS_SCHEMA = {"type": "object", "properties": {"findings": {"type": "array"}}, "required": ["findings"]}
REVIEW_META = WorkflowMeta("review-changes", "Review code changes across multiple dimensions", ("Review", "Summary"))


def review_changes(ctx: WorkflowContext, args: dict[str, Any]) -> dict[str, Any]:
    changes = str(args.get("changes", ""))
    dimensions = args.get("dimensions", ["correctness", "security", "tests"])
    ctx.phase("Review")

    def inspect(dimension: str) -> dict[str, Any]:
        return ctx.agent(
            f"Review the following code changes for {dimension} issues. Return JSON with a findings array.\n\n{changes}",
            schema=FINDINGS_SCHEMA,
            label=f"review:{dimension}",
        )

    reviews = ctx.parallel([lambda dimension=dimension: inspect(dimension) for dimension in dimensions])
    findings = [finding for review in reviews for finding in review["findings"]]
    ctx.phase("Summary")
    ctx.log(f"Collected {len(findings)} findings across {len(dimensions)} review dimensions")
    return {"findings": findings, "dimensions": dimensions}


def create_workflow_runner(client: DeepSeekClient) -> Callable[[str, dict[str, Any] | None], Any]:
    def runner(prompt: str, schema: dict[str, Any] | None) -> Any:
        messages = [{"role": "user", "content": prompt}]
        response = client.chat(messages)
        content = response.message.get("content") or "{}"
        if schema is not None:
            return content
        return content
    return runner
