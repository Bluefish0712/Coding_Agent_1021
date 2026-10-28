from datetime import datetime
from pathlib import Path

from personal_agent.scheduler import CronScheduler, cron_matches, validate_cron
from personal_agent.tools.scheduler import create_scheduler_tools


def test_cron_matching_and_validation():
    assert cron_matches("0 9 * * *", datetime(2026, 10, 28, 9, 0))
    assert not cron_matches("0 9 * * *", datetime(2026, 10, 28, 9, 1))
    assert cron_matches("*/5 * * * *", datetime(2026, 10, 28, 9, 10))
    validate_cron("0 9 * * 1-5")


def test_scheduler_persists_lists_and_cancels(tmp_path: Path):
    scheduler = CronScheduler(tmp_path)
    job = scheduler.schedule("*/5 * * * *", "run tests")
    assert (tmp_path / ".scheduled_tasks.json").exists()
    assert scheduler.list_jobs()[0].id == job.id
    assert scheduler.cancel(job.id)
    assert scheduler.list_jobs() == []


def test_scheduler_tools_validate_cron(tmp_path: Path):
    tools = {tool.name: tool.handler for tool in create_scheduler_tools(CronScheduler(tmp_path))}
    result = tools["schedule_cron"]({"cron": "bad", "prompt": "test"})
    assert "cron error" in result
