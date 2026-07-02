from fastapi import APIRouter, HTTPException
from pathlib import Path
import yaml

router = APIRouter(prefix="/api/config")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def _mask_config(config_type: str, parsed: dict) -> dict:
    if config_type != "llm":
        return parsed
    for provider in parsed.get("providers", {}).values():
        if "api_key" in provider:
            provider["api_key"] = "***"
    return parsed


@router.get("/{config_type}")
async def get_config(config_type: str):
    if config_type not in ("llm", "sources", "agents"):
        raise HTTPException(400, "无效的配置类型")

    paths = {
        "llm": CONFIG_DIR / "llm.yaml",
        "sources": CONFIG_DIR / "sources.yaml",
        "agents": CONFIG_DIR / "agents.yaml",
    }

    path = paths[config_type]
    try:
        raw = path.read_text()
        parsed = yaml.safe_load(raw) or {}
    except Exception as e:
        raise HTTPException(500, f"加载配置失败: {e}")

    return {
        "code": 0,
        "data": {
            "raw": raw,
            "parsed": _mask_config(config_type, parsed),
        },
        "message": "ok"
    }
