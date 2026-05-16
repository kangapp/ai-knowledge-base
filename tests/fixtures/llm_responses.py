import json

GITHUB_ANALYZE_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({
        "title": "llama.cpp",
        "summary": "高性能 LLM 推理框架",
        "tags": ["LLM", "Open Source"],
        "language": "en",
        "relevance_score": 85
    })}}],
    "usage": {"prompt_tokens": 420, "completion_tokens": 88}
}

REVIEWER_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 35, "reason": "核心 LLM 推理"},
            "content_depth": {"score": 25, "reason": "有技术细节"},
            "info_density": {"score": 12, "reason": "有新信息"},
            "timeliness": {"score": 13, "reason": "本周发布"}
        },
        "verdict": "approved",
        "retry_feedback": None
    })}}],
    "usage": {"prompt_tokens": 300, "completion_tokens": 120}
}