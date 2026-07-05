import json


def date_window_modifier(days: int) -> str:
    return f"-{max(days - 1, 0)} days"


def decode_json_field(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
