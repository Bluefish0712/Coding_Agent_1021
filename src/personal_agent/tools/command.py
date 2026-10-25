from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .registry import ToolDefinition


def create_command_tools(workspace: Path) -> list[ToolDefinition]:
    workspace = workspace.resolve()

    def run_command(args: dict[str, Any]) -> str:
        command = str(args["command"])
        timeout = min(float(args.get("timeout_seconds", 60)), 300)
        max_chars = min(int(args.get("max_chars", 12_000)), 50_000)
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return f"command timed out after {timeout:g}s: {exc.cmd}"
        output = (completed.stdout or "") + (completed.stderr or "")
        if len(output) > max_chars:
            output = output[:max_chars] + "\n(output truncated)"
        return f"exit_code: {completed.returncode}\n{output}".rstrip()

    def run_tests(args: dict[str, Any]) -> str:
        command = args.get("command", "python -m pytest")
        return run_command({
            "command": command,
            "timeout_seconds": args.get("timeout_seconds", 120),
            "max_chars": args.get("max_chars", 20_000),
        })

    def git_diff(args: dict[str, Any]) -> str:
        return run_command({
            "command": "git diff -- " + str(args.get("path", "")),
            "timeout_seconds": 30,
            "max_chars": args.get("max_chars", 20_000),
        })

    return [
        ToolDefinition("run_command", {
            "type": "function", "function": {"name": "run_command", "description": "Run a command in the workspace and return its exit code and output.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "number"}, "max_chars": {"type": "integer"}}, "required": ["command"], "additionalProperties": False}},
        }, run_command),
        ToolDefinition("run_tests", {
            "type": "function", "function": {"name": "run_tests", "description": "Run the project's test command and return the result.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "number"}, "max_chars": {"type": "integer"}}, "additionalProperties": False}},
        }, run_tests),
        ToolDefinition("git_diff", {
            "type": "function", "function": {"name": "git_diff", "description": "Show Git diff for workspace changes.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer"}}, "additionalProperties": False}},
        }, git_diff),
    ]

