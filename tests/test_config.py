import os
from pathlib import Path

import pytest
from src.core.config import load_llm_config, load_sources_config, load_agents_config


def test_load_llm_config(sample_llm_yaml):
    cfg = load_llm_config(sample_llm_yaml)
    assert "minimax" in cfg.providers
    assert cfg.providers["minimax"].base_url == "https://api.minimax.chat/v1"
    assert cfg.providers["minimax"].supports_json_mode is False


def test_load_sources_config(sample_sources_yaml):
    cfg = load_sources_config(sample_sources_yaml)
    assert len(cfg.sources) == 1
    assert cfg.sources[0].type == "rss"
    assert cfg.sources[0].config["url"] == "https://www.anthropic.com/blog/feed.xml"


def test_load_agents_config(sample_agents_yaml):
    cfg = load_agents_config(sample_agents_yaml)
    assert "github_analyzer" in cfg.agents
    assert cfg.agents["github_analyzer"].model.primary.provider == "minimax"
    assert len(cfg.agents["github_analyzer"].model.fallback) == 0
    assert cfg.budget.monthly == 10.0


def test_project_minimax_model_is_m3(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-placeholder")

    llm_cfg = load_llm_config(Path("config/llm.yaml"))
    agent_cfg = load_agents_config(Path("config/agents.yaml"))

    minimax_models = {model.id for model in llm_cfg.providers["minimax"].models}
    assert "MiniMax-M3" in minimax_models
    assert "MiniMax-M2.7" not in minimax_models

    minimax_agent_models = {
        agent.model.primary.model
        for agent in agent_cfg.agents.values()
        if agent.model.primary.provider == "minimax"
    }
    assert minimax_agent_models == {"MiniMax-M3"}
