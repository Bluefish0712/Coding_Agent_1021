from pathlib import Path

from personal_agent.workflow import (
    REVIEW_META,
    WorkflowContext,
    WorkflowInputError,
    WorkflowJournal,
    WorkflowMeta,
    WorkflowRun,
    WorkflowRuntime,
    review_changes,
)


def test_workflow_runs_parallel_agents_and_journals_results(tmp_path: Path):
    calls = []

    def runner(prompt, schema):
        calls.append(prompt)
        return '{"findings": []}'

    runtime = WorkflowRuntime(tmp_path, runner)
    first = runtime.run(review_changes, REVIEW_META, {"changes": "diff"})
    assert first.status == "completed"
    assert first.agent_calls == 3
    assert len(calls) == 3
    resumed = runtime.run(review_changes, REVIEW_META, {"changes": "diff"}, first.run_id)
    assert resumed.status == "completed"
    assert resumed.agent_calls == 0
    assert len(calls) == 3


def test_workflow_failure_can_resume_from_completed_steps(tmp_path: Path):
    count = 0

    def runner(prompt, schema):
        nonlocal count
        count += 1
        if count == 2:
            return "not json"
        return '{"findings": []}'

    runtime = WorkflowRuntime(tmp_path, runner)
    failed = runtime.run(review_changes, REVIEW_META, {"changes": "diff"})
    assert failed.status == "failed"
    # All parallel calls are launched before the invalid response is observed.
    assert failed.agent_calls == 3
    resumed = runtime.run(review_changes, REVIEW_META, {"changes": "diff"}, failed.run_id)
    assert resumed.status == "completed"
    assert resumed.agent_calls == 1
    assert count == 4


def test_workflow_rejects_unsafe_metadata_and_mismatched_resume(tmp_path: Path):
    runtime = WorkflowRuntime(tmp_path, lambda prompt, schema: '{"findings": []}')
    try:
        runtime.run(review_changes, WorkflowMeta("../bad", "bad"), {})
        assert False
    except WorkflowInputError:
        pass
    run = runtime.run(review_changes, REVIEW_META, {"changes": "a"})
    try:
        runtime.run(review_changes, REVIEW_META, {"changes": "b"}, run.run_id)
        assert False
    except WorkflowInputError as exc:
        assert "must match" in str(exc)
