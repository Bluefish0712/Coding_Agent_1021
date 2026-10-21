import httpx
import pytest

from personal_agent.config import Settings
from personal_agent.deepseek_client import DeepSeekClient, DeepSeekError


def make_client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    settings = Settings(api_key="test-key")
    return DeepSeekClient(settings, http_client=http_client), http_client


def test_chat_sends_native_deepseek_payload():
    def handler(request):
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = request.read().decode()
        assert '"model":"deepseek-flash"' in body
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 3},
        })

    client, http_client = make_client(handler)
    try:
        response = client.chat([{"role": "user", "content": "hi"}])
        assert response.message["content"] == "hello"
        assert response.finish_reason == "stop"
    finally:
        http_client.close()


def test_chat_parses_tool_call():
    def handler(request):
        payload = request.read().decode()
        assert "tools" in payload
        return httpx.Response(200, json={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"README.md"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        })

    client, http_client = make_client(handler)
    try:
        response = client.chat(
            [{"role": "user", "content": "read README"}],
            tools=[{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
        )
        assert response.finish_reason == "tool_calls"
        assert response.message["tool_calls"][0]["function"]["name"] == "read_file"
    finally:
        http_client.close()


def test_http_error_is_wrapped():
    client, http_client = make_client(lambda request: httpx.Response(401, text="bad key"))
    try:
        with pytest.raises(DeepSeekError, match="HTTP 401"):
            client.chat([{"role": "user", "content": "hi"}])
    finally:
        http_client.close()

