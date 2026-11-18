from personal_agent.knowledge import ProjectKnowledgeIndex


def test_index_chunks_markdown_and_python_with_citations_and_ignores_private_runtime_data(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / ".agent-data").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Permissions\nRisky actions need approval before execution.\n", encoding="utf-8")
    (tmp_path / "src" / "permissions.py").write_text("def require_approval(action):\n    return action.is_risky\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_TOKEN=do-not-index", encoding="utf-8")
    (tmp_path / ".agent-data" / "private.md").write_text("SECRET_TOKEN do-not-index", encoding="utf-8")

    index = ProjectKnowledgeIndex(tmp_path)
    assert index.build() >= 2
    results = index.search("risky actions approval")

    assert results
    assert results[0].chunk.path == "docs/guide.md"
    formatted = index.format_results("risky actions approval")
    assert "docs/guide.md:" in formatted
    assert "SECRET_TOKEN" not in formatted


def test_search_can_filter_by_path_and_empty_query_returns_no_results(tmp_path):
    (tmp_path / "a.md").write_text("# Alpha\nVector search notes", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("# Beta\nVector search details", encoding="utf-8")
    index = ProjectKnowledgeIndex(tmp_path)
    index.build()
    assert all(item.chunk.path.startswith("sub/") for item in index.search("vector search", path_prefix="sub"))
    assert index.search("  ") == []


def test_search_stable_across_index_rebuilds(tmp_path):
    (tmp_path / "readme.md").write_text("# Agent loop\nTool calls return observations to the model.", encoding="utf-8")
    first = ProjectKnowledgeIndex(tmp_path)
    first.build()
    second = ProjectKnowledgeIndex(tmp_path)
    second.build()
    assert [(r.chunk.path, r.score) for r in first.search("tool calls observations")] == [
        (r.chunk.path, r.score) for r in second.search("tool calls observations")]
