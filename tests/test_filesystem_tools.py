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


def test_write_file_creates_new_file_and_protects_existing_file(tmp_path):
    tools = handlers(tmp_path)
    assert "wrote" in tools["write_file"]({"path": "new.py", "content": "print('hi')"})
    with pytest.raises(ValueError, match="file exists"):
        tools["write_file"]({"path": "new.py", "content": "changed"})
    tools["write_file"]({"path": "new.py", "content": "changed", "overwrite": True})
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "changed"


def test_apply_patch_requires_one_unique_match(tmp_path):
    (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
    tools = handlers(tmp_path)
    assert "patched" in tools["apply_patch"]({"path": "hello.py", "old_text": "x = 1", "new_text": "x = 2"})
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "x = 2\n"
    with pytest.raises(ValueError, match="not found"):
        tools["apply_patch"]({"path": "hello.py", "old_text": "missing", "new_text": "x"})

