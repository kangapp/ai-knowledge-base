import os
import pytest
from src.core.config import load_llm_config, load_sources_config, load_agents_config


def test_load_llm_config(sample_llm_yaml):
    cfg = load_llm_config(sample_llm_yaml)
    assert "deepseek" in cfg.providers
    assert cfg.providers["deepseek"].base_url == "https://api.deepseek.com/v1"
    assert cfg.providers["deepseek"].supports_json_mode is True


def test_load_sources_config(sample_sources_yaml):
    cfg = load_sources_config(sample_sources_yaml)
    assert len(cfg.sources) == 1
    assert cfg.sources[0].type == "rss"
    assert cfg.sources[0].config["url"] == "https://www.anthropic.com/blog/feed.xml"


def test_load_agents_config(sample_agents_yaml):
    cfg = load_agents_config(sample_agents_yaml)
    assert "github_analyzer" in cfg.agents
    assert cfg.agents["github_analyzer"].model.primary.provider == "deepseek"
    assert len(cfg.agents["github_analyzer"].model.fallback) == 1
    assert cfg.budget.monthly == 10.0


def test_env_interpolation(sample_llm_yaml, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
    cfg = load_llm_config(sample_llm_yaml)
    assert cfg.providers["deepseek"].api_key == "sk-test-123"


def test_missing_env_var_raises(sample_llm_yaml, monkeypatch):
    # 确保环境变量未设置
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(KeyError, match="DEEPSEEK_API_KEY"):
        load_llm_config(sample_llm_yaml)
