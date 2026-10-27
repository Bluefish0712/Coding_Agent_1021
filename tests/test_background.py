import time
from pathlib import Path

from personal_agent.background import BackgroundManager
from personal_agent.tools.command import create_command_tools


def test_background_command_returns_immediately_and_collects_result(tmp_path: Path):
    manager = BackgroundManager(tmp_path)
    tools = {tool.name: tool.handler for tool in create_command_tools(tmp_path, manager)}
    result = tools["run_command"]({"command": "python -c \"print('background ok')\"", "run_in_background": True})
    assert "Background task bg_" in result
    deadline = time.time() + 3
    notifications = []
    while time.time() < deadline and not notifications:
        notifications = manager.collect()
        time.sleep(0.02)
    assert notifications
    assert "background ok" in notifications[0]


def test_run_command_remains_synchronous_by_default(tmp_path: Path):
    manager = BackgroundManager(tmp_path)
    tools = {tool.name: tool.handler for tool in create_command_tools(tmp_path, manager)}
    result = tools["run_command"]({"command": "python -c \"print('sync ok')\""})
    assert "exit_code: 0" in result
    assert "sync ok" in result
