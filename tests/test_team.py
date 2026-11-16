from pathlib import Path

from personal_agent.team import MessageBus, TeamRuntime
from personal_agent.tasks import TaskStore


def test_message_bus_round_trip(tmp_path: Path):
    bus = MessageBus(tmp_path)
    bus.send("lead", "alice", "hello")
    messages = bus.read("alice")
    assert messages[0].sender == "lead"
    assert messages[0].content == "hello"
    assert bus.read("alice") == []


def test_runtime_spawns_and_reports_result(tmp_path: Path):
    runtime = TeamRuntime(tmp_path, lambda name, task: f"{name} completed: {task}")
    teammate = runtime.spawn("tests", "run tests")
    messages = runtime.bus.wait("lead", timeout=2)
    assert teammate.name.startswith("teammate_")
    assert messages[0].message_type == "result"
    assert "run tests" in messages[0].content
    runtime.shutdown()


def test_idle_teammate_claims_ready_task(tmp_path: Path):
    store = TaskStore(tmp_path)
    store.create("shared task", "inspect the project")
    runtime = TeamRuntime(tmp_path, lambda name, task: f"done: {task}", store)
    teammate = runtime.spawn("worker", "initial task")
    runtime.bus.wait("lead", timeout=2)
    claimed = runtime.claim_next_task(teammate.name)
    assert claimed is not None
    assert any(task.status == "in_progress" and task.owner == teammate.name for task in store.list())
    runtime.shutdown()
