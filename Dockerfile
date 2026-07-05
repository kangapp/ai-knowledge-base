FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.22 /uv /usr/local/bin/uv
RUN mkdir -p /app/data /app/output \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY docs/analysis/ ./docs/analysis/
COPY src/ ./src/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
