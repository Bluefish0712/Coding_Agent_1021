from personal_agent.config import load_settings


def test_defaults_without_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    settings = load_settings(env_file=tmp_path / "missing.env")
    assert settings.api_key == ""
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-flash"

