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


def test_project_sources_include_github_ai_devtools():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    source = sources["github_ai_devtools"]
    assert source.type == "github"
    assert source.enabled is True
    assert source.config["lookback_type"] == "pushed"
    assert source.config["lookback_days"] == 90
    assert source.config["min_stars"] == 100
    assert source.config["topics"] == []
    assert source.config["keywords"] == [
        "coding agent",
        "AI coding assistant",
        "code generation",
        "AI code review",
        "AI IDE",
    ]
    assert {
        "tutorial",
        "course",
        "awesome",
        "interview",
        "writeup",
        "write-ups",
    }.issubset(set(source.config["exclude_terms"]))


def test_project_sources_include_github_agent_infra():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    source = sources["github_agent_infra"]
    assert source.type == "github"
    assert source.enabled is True
    assert source.config["lookback_type"] == "pushed"
    assert source.config["lookback_days"] == 90
    assert source.config["min_stars"] == 100
    assert source.config["topics"] == ["ai-agent", "mcp", "web-scraper"]
    assert source.config["keywords"] == [
        "AI agent web access",
        "agent internet",
        "MCP browser",
        "youtube transcript agent",
        "twitter scraper agent",
    ]
    assert {
        "tutorial",
        "course",
        "awesome",
        "interview",
        "writeup",
    }.issubset(set(source.config["exclude_terms"]))


def test_project_sources_include_data_sources():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    data_ai = sources["github_data_ai"]
    assert data_ai.type == "github"
    assert data_ai.enabled is True
    assert data_ai.config["lookback_type"] == "pushed"
    assert data_ai.config["lookback_days"] == 90
    assert data_ai.config["min_stars"] == 50
    assert data_ai.config["topics"] == []
    assert data_ai.config["keywords"] == [
        "text-to-SQL",
        "natural language SQL",
        "AI SQL",
        "dbt copilot",
        "data agent",
    ]

    data_infra = sources["github_data_infra"]
    assert data_infra.type == "github"
    assert data_infra.enabled is True
    assert data_infra.config["lookback_type"] == "pushed"
    assert data_infra.config["lookback_days"] == 90
    assert data_infra.config["min_stars"] == 100
    assert data_infra.config["topics"] == []
    assert data_infra.config["keywords"] == [
        "dbt",
        "data lineage",
        "data catalog",
        "data quality",
        "analytics engineering",
    ]
    assert {
        "tutorial",
        "course",
        "awesome",
        "example",
        "template",
        "boilerplate",
    }.issubset(set(data_ai.config["exclude_terms"]))
    assert set(data_ai.config["exclude_terms"]) == set(data_infra.config["exclude_terms"])


def test_project_sources_include_recommended_ai_feeds():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    hf = sources["rss_huggingface"]
    assert hf.type == "rss"
    assert hf.enabled is True
    assert hf.config["url"] == "https://huggingface.co/blog/feed.xml"
    assert "agent" in hf.config["filter_keywords"]

    msr = sources["rss_microsoft_research"]
    assert msr.type == "rss"
    assert msr.enabled is True
    assert msr.config["url"] == "https://www.microsoft.com/en-us/research/feed/"
    assert "LLM" in msr.config["filter_keywords"]


def test_project_sources_include_hacker_news_ai():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    source = sources["hn_ai"]
    assert source.type == "hn"
    assert source.enabled is True
    assert source.config["api_url"] == "https://hn.algolia.com/api/v1/search_by_date"
    assert source.config["query"] == "AI OR LLM OR agent OR RAG OR MCP"
    assert source.config["filter_keywords"] == ["AI", "LLM", "agent", "RAG", "MCP", "OpenAI"]


def test_project_sources_disable_broken_feeds_and_use_official_producthunt_feed():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    assert sources["rss_huxiu"].enabled is False
    assert sources["rss_juejin"].enabled is False
    assert sources["rss_reuters"].enabled is False
    assert sources["rss_producthunt"].enabled is True
    assert sources["rss_producthunt"].config["url"] == "https://www.producthunt.com/feed"


def test_project_sources_include_initial_hotlist_sources():
    cfg = load_sources_config(Path("config/sources.yaml"))
    sources = {source.id: source for source in cfg.sources}

    expected = {
        "hotlist_aihot": ("aihot", None),
        "hotlist_juejin": ("juejin", "juejin.cn"),
        "hotlist_zhihu_ai": ("zhihu", "zhihu.com"),
    }
    for source_id, (platform_id, expected_domain) in expected.items():
        source = sources[source_id]
        assert source.type == "hotlist"
        assert source.enabled is True
        assert source.config["platform_id"] == platform_id
        assert source.config.get("expected_domain") == expected_domain
        assert source.config["filter_keywords"]

    assert sources["hotlist_zhihu_ai"].config["filter_scope"] == "title"
