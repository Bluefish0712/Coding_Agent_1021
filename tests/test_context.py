import json
from pathlib import Path

from personal_agent.context import ContextCompactor


def test_compactor_archives_and_keeps_recent_messages(tmp_path: Path):
    messages = [{"role": "user", "content": "goal"}]
    messages.extend({"role": "assistant", "content": f"step {index}"} for index in range(8))
    compactor = ContextCompactor(tmp_path, max_messages=6, max_chars=10_000)
    compacted = compactor.prepare(messages, "goal")
    assert len(compacted) <= 6
    assert any("Context compacted" in str(message.get("content")) for message in compacted)
    archives = list((tmp_path / ".transcripts").glob("*.json"))
    assert len(archives) == 1
    assert json.loads(archives[0].read_text(encoding="utf-8"))[0]["content"] == "goal"


def test_compactor_keeps_tool_call_and_result_pair(tmp_path: Path):
    messages = [
        {"role": "user", "content": "goal"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "result"},
    ]
    messages.extend({"role": "assistant", "content": f"step {index}"} for index in range(8))
    compacted = ContextCompactor(tmp_path, max_messages=5).prepare(messages, "goal")
    for index, message in enumerate(compacted):
        if message.get("role") == "tool":
            assert index > 0
            assert compacted[index - 1].get("role") == "assistant"
