from pathlib import Path

import pytest

from personal_agent.tools.filesystem import create_filesystem_tools


def handlers(tmp_path: Path):
    return {tool.name: tool.handler for tool in create_filesystem_tools(tmp_path)}


def test_read_list_and_search_are_workspace_relative(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "hello.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    tools = handlers(tmp_path)

    assert "src/" in tools["list_directory"]({"path": "."})
    assert "return 'hi'" in tools["read_file"]({"path": "src/hello.py"})
    assert "src\\hello.py:2" in tools["search_text"]({"query": "return"}) or "src/hello.py:2" in tools["search_text"]({"query": "return"})


def test_filesystem_tools_reject_workspace_escape(tmp_path):
    tools = handlers(tmp_path)
    with pytest.raises(ValueError, match="outside the workspace"):
        tools["read_file"]({"path": "../secret.txt"})

