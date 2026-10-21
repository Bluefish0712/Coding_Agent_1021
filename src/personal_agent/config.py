from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    timeout_seconds: float = 60.0


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file)
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
    timeout = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60"))
    return Settings(api_key=api_key, base_url=base_url, model=model, timeout_seconds=timeout)

