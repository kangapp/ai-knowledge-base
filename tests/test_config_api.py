from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import config as config_api


def _client(config_dir: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(config_api, "CONFIG_DIR", config_dir)
    app = FastAPI()
    app.include_router(config_api.router)
    return TestClient(app, raise_server_exceptions=False)


def test_llm_config_view_does_not_require_env_secret(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "llm.yaml").write_text(
        """
providers:
  minimax:
    base_url: https://api.minimax.chat/v1
    api_key: ${MINIMAX_API_KEY}
    supports_json_mode: false
    models:
      - id: MiniMax-M3
        price_per_1k_in: 0.0003
        price_per_1k_out: 0.0012
        max_tokens: 8192
""".lstrip()
    )
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    response = _client(config_dir, monkeypatch).get("/api/config/llm")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    provider = body["data"]["parsed"]["providers"]["minimax"]
    assert provider["api_key"] == "***"
    assert provider["models"][0]["id"] == "MiniMax-M3"


def test_llm_config_view_masks_real_secret(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "llm.yaml").write_text(
        """
providers:
  minimax:
    base_url: https://api.minimax.chat/v1
    api_key: sk-real-secret
    models: []
""".lstrip()
    )

    response = _client(config_dir, monkeypatch).get("/api/config/llm")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["parsed"]["providers"]["minimax"]["api_key"] == "***"
    assert "sk-real-secret" in body["data"]["raw"]
