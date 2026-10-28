from pathlib import Path

from personal_agent.team import MessageBus, TeamRuntime


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
