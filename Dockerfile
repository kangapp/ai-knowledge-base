FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY src/ ./src/
RUN mkdir -p /app/data /app/output && apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]