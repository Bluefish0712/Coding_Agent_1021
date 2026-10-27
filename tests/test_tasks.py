from pathlib import Path

from personal_agent.tasks import TaskStore
from personal_agent.tools.tasks import create_task_tools


def test_tasks_persist_and_dependencies_unlock(tmp_path: Path):
    store = TaskStore(tmp_path)
    schema = store.create("setup schema")
    api = store.create("create API")
    store.update_dependencies(api.id, [schema.id])
    try:
        store.claim(api.id)
        assert False, "blocked task should not be claimable"
    except ValueError as exc:
        assert "blocked" in str(exc)
    store.claim(schema.id)
    store.complete(schema.id)
    store.claim(api.id)
    assert store.get(api.id).status == "in_progress"
    assert (tmp_path / ".tasks" / f"{schema.id}.json").exists()


def test_task_tool_create_list_and_complete(tmp_path: Path):
    tools = {tool.name: tool.handler for tool in create_task_tools(TaskStore(tmp_path))}
    created = tools["create_task"]({"subject": "write tests"})
    task_id = created.split('"id": "')[1].split('"', 1)[0]
    assert task_id.startswith("task_")
    assert task_id in tools["list_tasks"]({})
    assert "Claimed" in tools["claim_task"]({"task_id": task_id})
    assert "Completed" in tools["complete_task"]({"task_id": task_id})
