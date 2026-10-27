from pathlib import Path

from personal_agent.memory import MemoryStore, build_memory_context
from personal_agent.tools.memory import create_memory_tools


def test_memory_save_creates_file_and_index(tmp_path: Path):
    store = MemoryStore(tmp_path)
    result = store.save("API preference", "Preferred model provider", "Use DeepSeek API.", "user")
    assert "memory saved" in result
    assert (tmp_path / ".memory" / "api-preference.md").exists()
    assert "API preference" in (tmp_path / ".memory" / "MEMORY.md").read_text(encoding="utf-8")


def test_memory_search_returns_relevant_records(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.save("API preference", "Provider preference", "Use DeepSeek API.", "user")
    store.save("Testing rule", "Project test rule", "Always run pytest.", "project")
    assert [item.name for item in store.search("DeepSeek provider")] == ["API preference"]
    assert "pytest" in store.format_results("testing")


def test_memory_tools_save_and_recall(tmp_path: Path):
    store = MemoryStore(tmp_path)
    tools = {tool.name: tool.handler for tool in create_memory_tools(store)}
    assert "memory saved" in tools["remember"]({"name": "x", "description": "A fact", "body": "Keep x", "type": "project"})
    assert "Keep x" in tools["recall_memory"]({"query": "fact"})


def test_memory_context_marks_records_as_background(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.save("Preference", "User preference", "Use tabs.", "user")
    context = build_memory_context(store, "What indentation preference do I have?")
    assert "background context" in context
    assert "Use tabs" in context
