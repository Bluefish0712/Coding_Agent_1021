from __future__ import annotations

from typing import Any, Callable


ApprovalCallback = Callable[[str, dict[str, Any]], bool]


class PermissionPolicy:
    """Small tool-level policy: read-only tools are allowed; risky tools ask."""

    RISKY_TOOLS = frozenset({"write_file", "apply_patch", "run_command", "run_tests"})

    def __init__(self, approval_callback: ApprovalCallback | None = None):
        self.approval_callback = approval_callback

    def allow(self, tool_name: str | None, arguments: dict[str, Any]) -> bool:
        if tool_name not in self.RISKY_TOOLS:
            return True
        if self.approval_callback is None:
            return False
        return bool(self.approval_callback(tool_name or "<unknown>", arguments))
