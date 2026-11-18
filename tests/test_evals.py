import json

import pytest

from personal_agent.evals import dry_run, load_tasks, run_dataset, scripted_client, summarize


def test_dataset_loads_and_offline_dry_run_checks_fixtures(tmp_path):
    dataset = tmp_path / "tasks.json"
    dataset.write_text(json.dumps([{
        "id": "sample", "prompt": "inspect", "files": {"a.txt": "hello"},
        "checks": [{"type": "file_contains", "path": "a.txt", "text": "hello"},
                   {"type": "file_absent", "path": "missing.txt"}],
    }]), encoding="utf-8")

    report = dry_run(dataset)

    assert report["task_count"] == 1
    assert report["tasks"][0]["status"] == "valid"


def test_dataset_rejects_duplicate_and_workspace_escape_paths(tmp_path):
    dataset = tmp_path / "tasks.json"
    base = {"prompt": "inspect", "checks": [{"type": "file_absent", "path": "x"}]}
    dataset.write_text(json.dumps([{**base, "id": "same"}, {**base, "id": "same"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicated"):
        load_tasks(dataset)
    dataset.write_text(json.dumps([{**base, "id": "escape", "files": {"../x": "bad"}}]), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe path"):
        load_tasks(dataset)


def test_offline_runner_uses_isolated_workspace_and_writes_jsonl(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_text("original", encoding="utf-8")
    dataset = tmp_path / "tasks.json"
    dataset.write_text(json.dumps([{
        "id": "offline", "prompt": "inspect", "files": {"fixture.txt": "hello"},
        "checks": [{"type": "file_contains", "path": "fixture.txt", "text": "hello"},
                   {"type": "file_contains", "path": "keep.txt", "text": "original"}],
    }]), encoding="utf-8")
    output = tmp_path / "results.jsonl"
    settings = type("Settings", (), {"api_key": "", "model": "offline"})()

    records = run_dataset(dataset, workspace=source, output=output, settings=settings,
                          client_factory=lambda _task: scripted_client([{"role": "assistant", "content": "inspected"}]))

    assert records[0]["status"] == "passed"
    assert (source / "fixture.txt").exists() is False
    stored = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert stored["task_id"] == "offline"
    assert summarize(records)["pass_rate"] == 1.0


def test_command_check_uses_argv_without_shell(tmp_path):
    dataset = tmp_path / "tasks.json"
    dataset.write_text(json.dumps([{
        "id": "cmd", "prompt": "inspect", "checks": [{"type": "command", "argv": ["python", "-c", "print('ok')"]}]
    }]), encoding="utf-8")
    report = dry_run(dataset)
    assert report["tasks"][0]["status"] == "valid"


def test_offline_agent_loop_executes_real_tool_and_verifier_catches_result(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    dataset = tmp_path / "tasks.json"
    dataset.write_text(json.dumps([{
        "id": "create-file", "prompt": "Create result.txt with hello.", "files": {},
        "checks": [{"type": "file_contains", "path": "result.txt", "text": "hello"}],
    }]), encoding="utf-8")
    output = tmp_path / "runs.jsonl"
    settings = type("Settings", (), {"api_key": "", "model": "scripted"})()

    def scripted(_task):
        return scripted_client([
            {"role": "assistant", "content": None, "tool_calls": [{
                "id": "write-1", "type": "function", "function": {"name": "write_file", "arguments": json.dumps({"path": "result.txt", "content": "hello"})}
            }]},
            {"role": "assistant", "content": "Created result.txt and verified its contents."},
        ])

    records = run_dataset(dataset, workspace=source, output=output, settings=settings, client_factory=scripted)
    assert records[0]["status"] == "passed"
    assert records[0]["checks"][0]["passed"]


def test_completion_claim_without_artifact_fails_verifier(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    dataset = tmp_path / "tasks.json"
    dataset.write_text(json.dumps([{
        "id": "completion-proof", "prompt": "Create result.txt with done.", "files": {},
        "checks": [{"type": "file_contains", "path": "result.txt", "text": "done"}],
    }]), encoding="utf-8")
    settings = type("Settings", (), {"api_key": "", "model": "scripted"})()
    records = run_dataset(dataset, workspace=source, output=tmp_path / "runs.jsonl", settings=settings,
                          client_factory=lambda _task: scripted_client([{"role": "assistant", "content": "Done!"}]))
    assert records[0]["status"] == "failed"
    assert "missing file" in records[0]["checks"][0]["detail"]


def test_retrieval_eval_reports_recall_and_mrr(tmp_path):
    from personal_agent.evals import evaluate_retrieval

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "agent.py").write_text("# Agent loop\nTool calls return observations to the model.", encoding="utf-8")
    dataset = tmp_path / "retrieval.json"
    dataset.write_text(json.dumps([{"id": "loop", "query": "tool calls observations model", "relevant_paths": ["src/agent.py"]}]), encoding="utf-8")
    report = evaluate_retrieval(dataset, workspace=tmp_path, top_k=3)
    assert report["queries"] == 1
    assert report["recall_at_k"] == 1.0
    assert report["mrr"] > 0
