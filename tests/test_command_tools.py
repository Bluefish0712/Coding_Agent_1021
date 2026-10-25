from pathlib import Path

from personal_agent.tools.command import create_command_tools


def handlers(tmp_path: Path):
    return {tool.name: tool.handler for tool in create_command_tools(tmp_path)}


def test_run_command_returns_exit_code_and_output(tmp_path):
    result = handlers(tmp_path)["run_command"]({"command": "python -c \"print('hello')\""})
    assert "exit_code: 0" in result
    assert "hello" in result


def test_run_tests_uses_requested_test_command(tmp_path):
    result = handlers(tmp_path)["run_tests"]({"command": "python -m pytest --version"})
    assert "exit_code:" in result


def test_run_tests_rejects_arbitrary_command(tmp_path):
    result = handlers(tmp_path)["run_tests"]({"command": "python -c \"print('not a test')\""})
    assert "only accepts" in result


def test_run_command_timeout_is_reported(tmp_path):
    result = handlers(tmp_path)["run_command"]({
        "command": "python -c \"import time; time.sleep(1)\"",
        "timeout_seconds": 0.05,
    })
    assert "timed out" in result

