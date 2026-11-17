from pathlib import Path

from personal_agent.config import Settings
from personal_agent.harness import AgentHarness


def test_harness_builds_integrated_runtime(tmp_path: Path, monkeypatch):
    class FakeClient:
        def close(self):
            pass

    monkeypatch.setattr("personal_agent.harness.DeepSeekClient", lambda settings: FakeClient())
    settings = Settings(api_key="key", model="deepseek-chat", base_url="https://example.test")
    harness = AgentHarness(settings, tmp_path)
    assert harness.tasks.root == tmp_path.resolve() / ".tasks"
    assert harness.scheduler is not None
    assert harness.mcp is not None
    harness.close()
