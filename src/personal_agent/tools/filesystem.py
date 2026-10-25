from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import ToolDefinition


def _resolve(workspace: Path, user_path: str) -> Path:
    candidate = (workspace / user_path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("path is outside the workspace") from exc
    return candidate


def create_filesystem_tools(workspace: Path) -> list[ToolDefinition]:
    workspace = workspace.resolve()

    def list_directory(args: dict[str, Any]) -> str:
        path = _resolve(workspace, args.get("path", "."))
        if not path.is_dir():
            raise ValueError("path is not a directory")
        entries = []
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
            marker = "/" if child.is_dir() else ""
            entries.append(f"{child.name}{marker}")
        return "\n".join(entries) or "(empty directory)"

    def read_file(args: dict[str, Any]) -> str:
        path = _resolve(workspace, args["path"])
        if not path.is_file():
            raise ValueError("path is not a file")
        max_chars = min(int(args.get("max_chars", 20_000)), 100_000)
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def search_text(args: dict[str, Any]) -> str:
        query = str(args["query"])
        if not query:
            raise ValueError("query must not be empty")
        root = _resolve(workspace, args.get("path", "."))
        if not root.is_dir():
            raise ValueError("search path is not a directory")
        matches: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file() or any(part.startswith(".") for part in path.relative_to(workspace).parts):
                continue
            try:
                for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if query.lower() in line.lower():
                        relative = path.relative_to(workspace)
                        matches.append(f"{relative}:{line_number}: {line[:300]}")
                        if len(matches) >= 100:
                            return "\n".join(matches) + "\n(search results truncated)"
            except OSError:
                continue
        return "\n".join(matches) or "(no matches)"

    return [
        ToolDefinition("list_directory", {
            "type": "function", "function": {"name": "list_directory", "description": "List entries in a workspace directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "additionalProperties": False}},
        }, list_directory),
        ToolDefinition("read_file", {
            "type": "function", "function": {"name": "read_file", "description": "Read a UTF-8 text file in the workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["path"], "additionalProperties": False}},
        }, read_file),
        ToolDefinition("search_text", {
            "type": "function", "function": {"name": "search_text", "description": "Search text in workspace files.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "path": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
        }, search_text),
    ]

