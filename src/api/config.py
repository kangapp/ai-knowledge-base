from fastapi import APIRouter, HTTPException
from pathlib import Path
from ..core.config import load_llm_config, load_sources_config, load_agents_config

router = APIRouter(prefix="/api/config")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@router.get("/{config_type}")
async def get_config(config_type: str):
    if config_type not in ("llm", "sources", "agents"):
        raise HTTPException(400, "无效的配置类型")

    loaders = {
        "llm": (load_llm_config, CONFIG_DIR / "llm.yaml"),
        "sources": (load_sources_config, CONFIG_DIR / "sources.yaml"),
        "agents": (load_agents_config, CONFIG_DIR / "agents.yaml"),
    }

    loader, path = loaders[config_type]
    try:
        config = loader(path)
    except Exception as e:
        raise HTTPException(500, f"加载配置失败: {e}")

    with open(path) as f:
        raw = f.read()

    return {
        "code": 0,
        "data": {
            "raw": raw,
            "parsed": config.model_dump(),
        },
        "message": "ok"
    }