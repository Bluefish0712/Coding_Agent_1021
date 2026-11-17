from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from .deepseek_client import DeepSeekClient, DeepSeekError


@dataclass
class GoalDecision:
    action: str
    reason: str = ""


@dataclass
class GoalState:
    condition: str
    started_at: float
    evaluations: int = 0
    last_reason: str = ""
    status: str = "active"


class GoalEvaluator:
    def __init__(self, client: DeepSeekClient):
        self.client = client

    def evaluate(self, condition: str, messages: list[dict[str, Any]]) -> GoalDecision:
        evidence = self._conversation_excerpt(messages)
        prompt = (
            "You are a read-only goal evaluator. Decide whether the stated completion condition "
            "is proven by concrete evidence in the conversation. Claims without tool output are not proof. "
            "Return only JSON: {\"ok\": boolean, \"reason\": string, \"impossible\": boolean}.\n"
            f"Goal: {condition}\nConversation evidence:\n{evidence}"
        )
        response = self.client.chat([{"role": "user", "content": prompt}])
        content = response.message.get("content") or "{}"
        try:
            data = json.loads(content)
            if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
                raise ValueError("expected JSON object with boolean 'ok'")
            if not isinstance(data.get("impossible", False), bool):
                raise ValueError("'impossible' must be boolean")
            reason = str(data.get("reason", ""))
            if data["ok"]:
                return GoalDecision("complete", reason)
            if data.get("impossible"):
                return GoalDecision("impossible", reason)
            return GoalDecision("continue", reason or "The goal is not yet supported by the conversation evidence.")
        except (json.JSONDecodeError, ValueError) as exc:
            raise DeepSeekError(f"goal evaluator returned invalid JSON: {exc}") from exc

    @staticmethod
    def _conversation_excerpt(messages: list[dict[str, Any]], max_chars: int = 24000) -> str:
        rendered = []
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)
            rendered.append(f"[{role}] {content}")
        text = "\n".join(rendered)
        if len(text) <= max_chars:
            return text
        head = max_chars // 3
        return text[:head] + "\n...[middle omitted]...\n" + text[-(max_chars - head):]


class GoalController:
    def __init__(self, evaluator: GoalEvaluator, *, max_blocked_stops: int = 5):
        self.evaluator = evaluator
        self.max_blocked_stops = max_blocked_stops
        self.state: GoalState | None = None
        self._blocked_stops = 0

    def set(self, condition: str) -> GoalState:
        condition = condition.strip()
        if not condition:
            raise ValueError("goal condition must not be empty")
        self.state = GoalState(condition, time.time())
        self._blocked_stops = 0
        return self.state

    def clear(self) -> None:
        self.state = None
        self._blocked_stops = 0

    def status(self) -> dict[str, Any] | None:
        if self.state is None:
            return None
        result = asdict(self.state)
        result["elapsed_seconds"] = max(0, int(time.time() - self.state.started_at))
        return result

    def restore(self, state: dict[str, Any] | None) -> None:
        if not state or state.get("status") != "active":
            self.clear()
            return
        condition = state.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            self.clear()
            return
        self.state = GoalState(condition=condition, started_at=time.time())
        self._blocked_stops = 0

    def evaluate_after_turn(self, messages: list[dict[str, Any]], *, pending_background: bool = False) -> GoalDecision:
        if self.state is None:
            return GoalDecision("complete", "No active goal")
        if pending_background:
            return GoalDecision("defer", "Background work is still running; waiting for its result.")
        try:
            decision = self.evaluator.evaluate(self.state.condition, messages)
        except Exception as exc:
            self.state.last_reason = f"Goal evaluation failed: {exc}"
            self.state.status = "evaluation_error"
            return GoalDecision("stop", self.state.last_reason)
        self.state.evaluations += 1
        self.state.last_reason = decision.reason
        if decision.action in {"complete", "impossible"}:
            self.state.status = decision.action
            return decision
        self._blocked_stops += 1
        if self._blocked_stops >= self.max_blocked_stops:
            self.state.status = "needs_user"
            return GoalDecision("stop", f"Automatic continuation limit reached. Goal remains active. Last check: {decision.reason}")
        return decision
