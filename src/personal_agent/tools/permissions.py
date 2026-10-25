from __future__ import annotations

from typing import Any, Callable
import re


ApprovalCallback = Callable[[str, dict[str, Any]], bool]


class PermissionPolicy:
    """Small tool-level policy: read-only tools are allowed; risky tools ask."""

    RISKY_TOOLS = frozenset({"write_file", "apply_patch", "run_command", "run_tests"})
    _DANGEROUS_COMMAND = re.compile(
        r"(?i)(?:^|[;&|()\n])\s*(?:del|erase|rmdir|rd|rm|sudo|shutdown|reboot|format|mkfs|diskpart)\b"
    )
    _UNSAFE_LINUX = re.compile(r"(?i)(?:/workspace|/dev/|2>/dev/null|\btail\s+-?)")

    def __init__(self, approval_callback: ApprovalCallback | None = None):
        self.approval_callback = approval_callback

    def allow(self, tool_name: str | None, arguments: dict[str, Any]) -> bool:
        reason = self.hard_deny_reason(tool_name, arguments)
        if reason is not None:
            return False
        if tool_name not in self.RISKY_TOOLS:
            return True
        if self.approval_callback is None:
            return False
        return bool(self.approval_callback(tool_name or "<unknown>", arguments))

    @classmethod
    def hard_deny_reason(cls, tool_name: str | None, arguments: dict[str, Any]) -> str | None:
        if tool_name in {"run_command", "run_tests"}:
            command = str(arguments.get("command", ""))
            if cls._DANGEROUS_COMMAND.search(command):
                return "destructive or system command"
            if cls._UNSAFE_LINUX.search(command):
                return "Linux-only path or shell syntax is not allowed on this Windows workspace"
        return None
