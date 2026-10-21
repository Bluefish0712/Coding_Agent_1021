from __future__ import annotations

import argparse
import sys

from .config import load_settings


def doctor() -> int:
    settings = load_settings()
    print(f"model: {settings.model}")
    print(f"base_url: {settings.base_url}")
    print(f"api_key: {'configured' if settings.api_key else 'missing'}")
    return 0 if settings.api_key else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="coding-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check local Phase 0 configuration")
    args = parser.parse_args()
    if args.command == "doctor":
        return doctor()
    return 2


if __name__ == "__main__":
    sys.exit(main())

