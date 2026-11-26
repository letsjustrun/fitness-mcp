# Dockerfile for Hugging Face Spaces (SDK: Docker, free CPU tier).
#
# Build context expectation: the repo root. The HF Space runs this image and
# routes HTTPS at https://<user>-<space>.hf.space to the container's port 7860,
# which is the HF convention and what the server is configured to listen on.
#
# Secrets (GARMIN_PERSONAL_API_KEY, FITNESS_MCP_HTTP_BEARER_TOKENS) are set
# in the Space's "Variables and secrets" UI — never bake them into the image.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# TLS + build-time wheels occasionally need git
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv>=0.5"

WORKDIR /app

# Minimal copy — only what the installer needs. Tests, docs, .github, dxt/ etc.
# are excluded via .dockerignore.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN uv pip install --system --no-cache-dir .

# HF Spaces convention: expose 7860, listen on 0.0.0.0.
# SQLite goes under /tmp because the free tier is ephemeral; cache-aside
# rebuilds on first call after a restart, which is fine.
ENV FITNESS_MCP_HTTP_HOST=0.0.0.0 \
    FITNESS_MCP_HTTP_PORT=7860 \
    FITNESS_MCP_HTTP_PATH=/mcp \
    FITNESS_MCP_LOG_LEVEL=INFO \
    FITNESS_MCP_DB_PATH=/tmp/fitness_mcp/data.db

RUN mkdir -p /tmp/fitness_mcp && chmod 1777 /tmp/fitness_mcp

EXPOSE 7860

CMD ["fitness-mcp", "--http"]
