import json

import httpx
import pytest

from personal_agent.agent_loop import AgentLoop
from personal_agent.config import Settings
from personal_agent.deepseek_client import DeepSeekClient, DeepSeekError


def test_loop_executes_tool_and_returns_final_answer():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, json={
                "choices": [{"message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "get_time", "arguments": "{}"},
                    }],
                }, "finish_reason": "tool_calls"}],
            })
        tool_messages = [m for m in requests[1]["messages"] if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_1"
        assert tool_messages[0]["content"]
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "The time is available."}, "finish_reason": "stop"}],
        })

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = DeepSeekClient(Settings(api_key="test-key"), http_client=http_client)
    try:
        answer = AgentLoop(client).run("What time is it?")
        assert answer == "The time is available."
        assert len(requests) == 2
    finally:
        http_client.close()


def test_loop_stops_after_max_turns():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "get_time", "arguments": "{}"},
            }]}, "finish_reason": "tool_calls"}],
        })

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = DeepSeekClient(Settings(api_key="test-key"), http_client=http_client)
    try:
        with pytest.raises(DeepSeekError, match="stopped after 1 turns"):
            AgentLoop(client, max_turns=1).run("loop")
    finally:
        http_client.close()

