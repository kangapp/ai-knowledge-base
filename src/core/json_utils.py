import json
import re
from typing import Any


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract the first complete JSON object from noisy LLM output."""
    text = _strip_thinking(raw)
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise ValueError("LLM output is not valid JSON")


def _strip_thinking(raw: str) -> str:
    text = raw.strip()
    for _ in range(10):
        new_text = re.sub(r"<think>[\s\S]*?(?:</think>|】)", "", text).strip()
        if new_text == text:
            break
        text = new_text
    return text
