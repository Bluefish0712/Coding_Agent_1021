from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ContextCompactor:
    """Deterministically archive old messages and keep a recoverable recent window."""

    def __init__(self, workspace: Path, *, max_messages: int = 20, max_chars: int = 30_000):
        self.workspace = workspace.resolve()
        self.max_messages = max_messages
        self.max_chars = max_chars

    @staticmethod
    def estimate_chars(messages: list[dict[str, Any]]) -> int:
        return len(json.dumps(messages, ensure_ascii=False, default=str))

    def prepare(self, messages: list[dict[str, Any]], active_request: str) -> list[dict[str, Any]]:
        if len(messages) <= self.max_messages and self.estimate_chars(messages) <= self.max_chars:
            return messages
        return self.compact(messages, active_request, reason="automatic")

    def compact(self, messages: list[dict[str, Any]], active_request: str, *, reason: str = "manual") -> list[dict[str, Any]]:
        transcript = self._write_transcript(messages)
        if len(messages) <= 4:
            return messages

        keep_tail = max(4, self.max_messages // 2)
        tail_start = max(1, len(messages) - keep_tail)
        # Never leave a tool result without the assistant tool call that requested it.
        if tail_start < len(messages) and messages[tail_start].get("role") == "tool":
            tail_start -= 1
        head = messages[:1] if messages and messages[0].get("role") == "system" else []
        marker = {
            "role": "user",
            "content": (
                f"[Context compacted: {reason}; archived {tail_start - len(head)} message(s) at {transcript}]\n"
                f"Current user request: {active_request}"
            ),
        }
        return [*head, marker, *messages[tail_start:]]

    def _write_transcript(self, messages: list[dict[str, Any]]) -> str:
        directory = self.workspace / ".transcripts"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = directory / f"transcript-{stamp}.json"
        path.write_text(json.dumps(messages, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return str(path.relative_to(self.workspace))
