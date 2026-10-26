from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .deepseek_client import DeepSeekClient, DeepSeekError
from .agent_loop import AgentLoop
from .tools.permissions import PermissionPolicy
from .skills import SkillLoader, build_system_prompt


def doctor() -> int:
    settings = load_settings()
    print(f"model: {settings.model}")
    print(f"base_url: {settings.base_url}")
    print(f"api_key: {'configured' if settings.api_key else 'missing'}")
    return 0 if settings.api_key else 1


def chat(prompt: str) -> int:
    settings = load_settings()
    try:
        client = DeepSeekClient(settings)
        try:
            response = client.chat([{"role": "user", "content": prompt}])
        finally:
            client.close()
    except DeepSeekError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(response.message.get("content", ""))
    return 0


def agent(prompt: str) -> int:
    settings = load_settings()
    try:
        client = DeepSeekClient(settings)
        try:
            workspace = Path.cwd()
            skill_loader = SkillLoader(workspace / "skills")
            skill_loader.scan()
            def approve(tool_name: str, arguments: dict) -> bool:
                details = f"{tool_name}({arguments})"
                return input(f"Allow tool {details}? [y/N] ").strip().lower() in {"y", "yes"}

            answer = AgentLoop(client, workspace=workspace, permission_policy=PermissionPolicy(approve), skill_loader=skill_loader, system_prompt=build_system_prompt(workspace, skill_loader)).run(prompt)
        finally:
            client.close()
    except (DeepSeekError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(answer)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="coding-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check local Phase 0 configuration")
    chat_parser = subparsers.add_parser("chat", help="send one prompt to DeepSeek")
    chat_parser.add_argument("prompt")
    agent_parser = subparsers.add_parser("agent", help="run the first tool-enabled agent loop")
    agent_parser.add_argument("prompt")
    args = parser.parse_args()
    if args.command == "doctor":
        return doctor()
    if args.command == "chat":
        return chat(args.prompt)
    if args.command == "agent":
        return agent(args.prompt)
    return 2


if __name__ == "__main__":
    sys.exit(main())

