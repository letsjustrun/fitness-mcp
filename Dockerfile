# Dockerfile for Render (and any other Docker-based host).
#
# Render's free Web Service builds from this image and runs the CMD below.
# On other hosts (Fly.io, a VM, etc.) the same image is a clean starting
# point — the CMD respects $PORT so no change is needed.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv>=0.5"

WORKDIR /app

# Copy only what the installer needs (anything else is excluded via .dockerignore).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN uv pip install --system --no-cache-dir .

# Hosting defaults: Render injects $PORT; bind to 0.0.0.0 so the edge proxy
# can reach us. SQLite cache goes under /tmp because most hosts don't give
# us a persistent disk — cache-aside sync handles the rebuild transparently.
ENV FITNESS_MCP_HTTP_HOST=0.0.0.0 \
    FITNESS_MCP_HTTP_PATH=/mcp \
    FITNESS_MCP_LOG_LEVEL=INFO \
    FITNESS_MCP_DB_PATH=/tmp/fitness_mcp/data.db

RUN mkdir -p /tmp/fitness_mcp

# Render's health check hits /healthz on the assigned port.
EXPOSE 10000

# Shell form so $PORT is expanded at container start.
CMD fitness-mcp --http --host 0.0.0.0 --port ${PORT:-10000}
