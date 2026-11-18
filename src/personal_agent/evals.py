from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .agent_loop import AgentLoop
from .deepseek_client import ChatResponse
from .tools.permissions import PermissionPolicy


@dataclass(frozen=True)
class EvalTask:
    id: str
    prompt: str
    files: dict[str, str]
    checks: tuple[dict[str, Any], ...]
    tags: tuple[str, ...] = ()
    max_turns: int = 8
    timeout_seconds: float = 120.0


class EvaluationExecutionError(RuntimeError):
    def __init__(self, message: str, *, tool_calls: int = 0, usage: dict[str, Any] | None = None):
        super().__init__(message)
        self.tool_calls = tool_calls
        self.usage = usage or {}


def load_tasks(path: Path) -> list[EvalTask]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("evaluation dataset must be a JSON array")
    tasks: list[EvalTask] = []
    seen: set[str] = set()
    for raw in data:
        task = EvalTask(
            id=str(raw["id"]), prompt=str(raw["prompt"]), files=dict(raw.get("files", {})),
            checks=tuple(raw.get("checks", [])), tags=tuple(raw.get("tags", [])),
            max_turns=int(raw.get("max_turns", 8)), timeout_seconds=float(raw.get("timeout_seconds", 120)),
        )
        if not task.id or task.id in seen:
            raise ValueError(f"evaluation task id is empty or duplicated: {task.id!r}")
        if not task.prompt.strip() or not task.checks:
            raise ValueError(f"task {task.id!r} needs a prompt and at least one check")
        if task.max_turns < 1 or task.timeout_seconds <= 0:
            raise ValueError(f"task {task.id!r} has invalid resource limits")
        for relative in task.files:
            _validate_relative_path(relative, f"task {task.id!r} fixture")
        for check in task.checks:
            if check.get("type") not in CHECKS:
                raise ValueError(f"task {task.id!r} uses unsupported check type: {check.get('type')!r}")
            if "path" in check:
                _validate_relative_path(str(check["path"]), f"task {task.id!r} check")
        tasks.append(task)
        seen.add(task.id)
    return tasks


def _validate_relative_path(relative: str, label: str) -> None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label} has unsafe path: {relative!r}")


def _check_file_contains(workspace: Path, check: dict[str, Any]) -> tuple[bool, str]:
    path = workspace / str(check["path"])
    if not path.is_file():
        return False, f"missing file: {check['path']}"
    expected = str(check["text"])
    ok = expected in path.read_text(encoding="utf-8", errors="replace")
    return ok, "expected text found" if ok else f"expected text not found in {check['path']}"


def _check_file_absent(workspace: Path, check: dict[str, Any]) -> tuple[bool, str]:
    path = workspace / str(check["path"])
    ok = not path.exists()
    return ok, "file remains absent" if ok else f"unexpected file created: {check['path']}"


def _check_command(workspace: Path, check: dict[str, Any]) -> tuple[bool, str]:
    command = check.get("argv")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        return False, "command check requires argv as a string array"
    try:
        result = subprocess.run(command, cwd=workspace, capture_output=True, text=True,
                                timeout=float(check.get("timeout_seconds", 30)), shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"command check failed: {type(exc).__name__}: {exc}"
    expected = int(check.get("exit_code", 0))
    ok = result.returncode == expected
    detail = f"exit code {result.returncode}; expected {expected}"
    if not ok and result.stderr:
        detail += f"; stderr: {result.stderr[-500:]}"
    return ok, detail


CHECKS: dict[str, Callable[[Path, dict[str, Any]], tuple[bool, str]]] = {
    "file_contains": _check_file_contains,
    "file_absent": _check_file_absent,
    "command": _check_command,
}


def validate_task(task: EvalTask, workspace: Path) -> list[dict[str, Any]]:
    results = []
    for check in task.checks:
        try:
            ok, detail = CHECKS[check["type"]](workspace, check)
        except (KeyError, OSError, ValueError) as exc:
            ok, detail = False, f"invalid check: {type(exc).__name__}: {exc}"
        results.append({"type": check["type"], "passed": ok, "detail": detail})
    return results


class _NoopCompactor:
    def prepare(self, messages: list[dict[str, Any]], _user_input: str) -> list[dict[str, Any]]:
        return messages

    def compact(self, messages: list[dict[str, Any]], _user_input: str, *, reason: str = "requested") -> list[dict[str, Any]]:
        return messages


class _DatasetClient:
    """Deterministic scripted client for offline end-to-end AgentLoop evaluations."""

    settings = type("SettingsInfo", (), {"model": "dataset-fixture", "api_key": "", "base_url": "offline"})()

    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)
        self.calls = 0
        self.tool_calls = 0

    def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        if self.calls >= len(self.responses):
            raise RuntimeError("offline scripted model response queue exhausted")
        response = self.responses[self.calls]
        self.calls += 1
        self.tool_calls += len(response.get("tool_calls", []))
        return ChatResponse(response, "tool_calls" if response.get("tool_calls") else "stop", {})

    def close(self) -> None:
        pass


def dry_run(path: Path, *, temp_root: Path | None = None) -> dict[str, Any]:
    tasks = load_tasks(path)
    outcomes = []
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix="coding-agent-eval-dry-", dir=temp_root) as temp:
            workspace = Path(temp)
            _write_fixtures(task, workspace)
            outcomes.append({"task_id": task.id, "check_count": len(task.checks), "fixture_count": len(task.files),
                             "validation_types": sorted({check["type"] for check in task.checks}), "status": "valid"})
    return {"dataset": str(path), "task_count": len(tasks), "tasks": outcomes}


def _write_fixtures(task: EvalTask, workspace: Path) -> None:
    for relative, content in task.files.items():
        target = (workspace / relative).resolve()
        target.relative_to(workspace.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_dataset(path: Path, *, workspace: Path, output: Path, settings: Any,
                task_ids: set[str] | None = None, repeats: int = 1,
                temp_root: Path | None = None,
                client_factory: Callable[[EvalTask], Any] | None = None,
                approval_callback: Callable[[str, dict[str, Any]], bool] | None = None) -> list[dict[str, Any]]:
    tasks = load_tasks(path)
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    selected = [task for task in tasks if task_ids is None or task.id in task_ids]
    if task_ids is not None and task_ids - {task.id for task in selected}:
        raise ValueError(f"unknown task ids: {sorted(task_ids - {task.id for task in selected})}")
    output.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    with output.open("a", encoding="utf-8") as stream:
        for task in selected:
            for repeat in range(1, repeats + 1):
                run_id = uuid.uuid4().hex
                started = time.monotonic()
                result: dict[str, Any] = {"schema_version": 1, "run_id": run_id, "task_id": task.id, "repeat": repeat,
                    "model": settings.model, "status": "failed", "tags": list(task.tags), "tool_calls": 0,
                    "token_usage": None, "cost": None}
                task_client = None
                with tempfile.TemporaryDirectory(prefix=f"eval-{task.id}-", dir=temp_root) as temp:
                    run_workspace = Path(temp) / "workspace"
                    shutil.copytree(workspace, run_workspace, ignore=shutil.ignore_patterns(
                        ".git", ".venv", ".env", "__pycache__", ".pytest_cache", ".pytest-run-*", ".workflow-debug", ".agent-data"))
                    _write_fixtures(task, run_workspace)
                    try:
                        response, tool_calls, usage, task_client = _invoke_agent(task, run_workspace, settings, client_factory=client_factory,
                                                 approval_callback=approval_callback)
                        checks = validate_task(task, run_workspace)
                        result.update({"status": "passed" if all(item["passed"] for item in checks) else "failed",
                                       "checks": checks, "final_response": response[:2000], "error": None,
                                       "tool_calls": tool_calls, "token_usage": usage or None})
                        git = subprocess.run(["git", "diff", "--no-index", "--", str(workspace), str(run_workspace)],
                                             capture_output=True, text=True, timeout=10, shell=False)
                        result["diff_excerpt"] = (git.stdout or "")[:8000]
                    except Exception as exc:
                        result.update({"error": f"{type(exc).__name__}: {exc}"[:1000],
                                       "error_class": _classify_execution_error(exc),
                                       "tool_calls": int(getattr(exc, "tool_calls", 0)),
                                       "token_usage": getattr(exc, "usage", None),
                                       "checks": validate_task(task, run_workspace)})
                result["duration_seconds"] = round(time.monotonic() - started, 3)
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                stream.flush()
                records.append(result)
    return records


def _invoke_agent(task: EvalTask, workspace: Path, settings: Any,
                  *, client_factory: Callable[[EvalTask], Any] | None = None,
                  approval_callback: Callable[[str, dict[str, Any]], bool] | None = None) -> tuple[str, int, dict[str, Any], Any]:
    from .deepseek_client import DeepSeekClient

    if client_factory is not None:
        client = client_factory(task)
    elif settings.api_key:
        client = DeepSeekClient(settings)
    else:
        raise ValueError("no model configured; inject a scripted client or use --real-model")
    try:
        policy = PermissionPolicy(approval_callback or (lambda name, _args: name in {"write_file", "apply_patch", "run_command"}))
        agent = AgentLoop(client, workspace=workspace, max_turns=task.max_turns,
                          compactor=_NoopCompactor(), permission_policy=policy)
        # Production model calls cannot be forcefully interrupted safely here; task timeout is enforced
        # by the HTTP client. Offline fixture is deterministic and side effect free beyond its workspace.
        response = agent.run(task.prompt)
        return response, int(getattr(client, "tool_calls", 0)), getattr(client, "usage", {}), client
    except Exception as exc:
        raise EvaluationExecutionError(f"{type(exc).__name__}: {exc}",
                                       tool_calls=int(getattr(client, "tool_calls", 0)),
                                       usage=getattr(client, "usage", {})) from exc
    finally:
        client.close()


def _classify_execution_error(error: Exception) -> str:
    message = str(error).lower()
    if "stopped after" in message or "turn limit" in message:
        return "turn_limit"
    if "timeout" in message:
        return "timeout"
    if "request failed" in message or "deepseek" in message:
        return "model_or_network_error"
    return "execution_error"


def scripted_client(responses: list[dict[str, Any]]) -> _DatasetClient:
    """Build an offline model double for tests and reproducible evaluation fixtures."""
    return _DatasetClient(responses)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    passed = sum(record.get("status") == "passed" for record in records)
    return {"runs": total, "passed": passed, "failed": total - passed,
            "pass_rate": round(passed / total, 4) if total else None,
            "mean_duration_seconds": round(sum(float(record.get("duration_seconds", 0)) for record in records) / total, 3) if total else None}


def evaluate_retrieval(dataset_path: Path, *, workspace: Path, top_k: int = 5) -> dict[str, Any]:
    from .knowledge import ProjectKnowledgeIndex

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    index = ProjectKnowledgeIndex(workspace)
    chunk_count = index.build()
    results = []
    reciprocal_ranks = []
    hits = 0
    for case in data:
        relevant = {str(path).replace("\\", "/") for path in case["relevant_paths"]}
        matches = index.search(str(case["query"]), top_k=top_k)
        ranked = [item.chunk.path for item in matches]
        rank = next((position for position, path in enumerate(ranked, 1) if path in relevant), None)
        if rank:
            hits += 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0.0)
        results.append({"id": case["id"], "query": case["query"], "expected_paths": sorted(relevant),
                        "retrieved_paths": ranked, "first_relevant_rank": rank, "hit": rank is not None})
    count = len(results)
    return {"dataset": str(dataset_path), "workspace": str(workspace), "chunk_count": chunk_count,
            "top_k": top_k, "queries": count, "recall_at_k": round(hits / count, 4) if count else None,
            "mrr": round(sum(reciprocal_ranks) / count, 4) if count else None, "results": results}
