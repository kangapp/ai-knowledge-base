import pytest
from pathlib import Path


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    return d


@pytest.fixture
def sample_llm_yaml(config_dir):
    p = config_dir / "llm.yaml"
    p.write_text("""
providers:
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    supports_json_mode: true
    models:
      - id: deepseek-chat
        price_per_1k_in: 0.000014
        price_per_1k_out: 0.000028
        max_tokens: 8192
""")
    return p


@pytest.fixture
def sample_sources_yaml(config_dir):
    p = config_dir / "sources.yaml"
    p.write_text("""
sources:
  - id: rss_anthropic
    name: Anthropic Blog
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * *"
    max_items: 5
    config:
      url: "https://www.anthropic.com/blog/feed.xml"
""")
    return p


@pytest.fixture
def sample_agents_yaml(config_dir):
    p = config_dir / "agents.yaml"
    p.write_text("""
agents:
  github_analyzer:
    model:
      primary: {provider: deepseek, model: deepseek-chat}
      fallback: [{provider: openai, model: gpt-4o-mini}]
    params: {temperature: 0.3, max_tokens: 2048}
    prompt: prompts/github_analyzer.md
    budget_weight: 1.0
budget:
  monthly: 10.0
  soft_limit: 0.8
  hard_limit: 1.0
""")
    return p
