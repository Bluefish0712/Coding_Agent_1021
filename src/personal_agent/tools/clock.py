from datetime import datetime
from typing import Any


GET_TIME_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Return the current local date and time.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def get_time(_: dict[str, Any]) -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

