from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_settings
from .deepseek_client import DeepSeekClient, DeepSeekError
from .agent_loop import AgentLoop
from .harness import AgentHarness


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
        def approve(tool_name: str, arguments: dict) -> bool:
            details = f"{tool_name}({arguments})"
            return input(f"Allow tool {details}? [y/N] ").strip().lower() in {"y", "yes"}

        with AgentHarness(settings, Path.cwd(), approve) as harness:
            answer = harness.build_agent(prompt).run(prompt)
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
    eval_parser = subparsers.add_parser("eval", help="run or inspect the local Agent task dataset")
    eval_parser.add_argument("--dataset", type=Path, default=Path("evals/coding_agent_smoke.json"))
    eval_parser.add_argument("--dry-run", action="store_true", help="validate fixtures and checks without calling a model")
    eval_parser.add_argument("--real-model", action="store_true", help="explicitly run with the configured DeepSeek API")
    eval_parser.add_argument("--task", action="append", dest="task_ids", help="run only this task id; repeatable")
    eval_parser.add_argument("--repeats", type=int, default=1)
    eval_parser.add_argument("--output", type=Path, default=Path(".agent-data/evals/results.jsonl"))
    eval_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    eval_parser.add_argument("--temp-root", type=Path, default=Path(".agent-data/eval-tmp"))
    eval_parser.add_argument("--retrieval-dataset", type=Path, help="run retrieval Recall@k/MRR evaluation instead of Agent tasks")
    eval_parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.command == "doctor":
        return doctor()
    if args.command == "chat":
        return chat(args.prompt)
    if args.command == "agent":
        return agent(args.prompt)
    if args.command == "eval":
        from .evals import dry_run, evaluate_retrieval, run_dataset, summarize

        if args.retrieval_dataset:
            print(json.dumps(evaluate_retrieval(args.retrieval_dataset, workspace=args.workspace.resolve(), top_k=args.top_k), ensure_ascii=False, indent=2))
            return 0

        if args.dry_run == args.real_model:
            raise SystemExit("Choose exactly one: --dry-run or --real-model.")
        if args.dry_run:
            args.temp_root.mkdir(parents=True, exist_ok=True)
            print(json.dumps(dry_run(args.dataset, temp_root=args.temp_root.resolve()), ensure_ascii=False, indent=2))
            return 0
        if args.repeats < 1:
            raise SystemExit("--repeats must be at least 1")
        args.temp_root.mkdir(parents=True, exist_ok=True)
        records = run_dataset(args.dataset, workspace=args.workspace.resolve(), output=args.output,
                              settings=load_settings(), task_ids=set(args.task_ids) if args.task_ids else None,
                              repeats=args.repeats, temp_root=args.temp_root.resolve())
        print(json.dumps(summarize(records), ensure_ascii=False, indent=2))
        return 0 if all(record["status"] == "passed" for record in records) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())

