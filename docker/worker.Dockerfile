FROM python:3.11-slim

WORKDIR /app

# Node/npx is needed at runtime for the MCP filesystem server integration
# (tools/mcp_client.py launches it via `npx -y @modelcontextprotocol/server-filesystem`).
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

CMD ["celery", "-A", "api.celery_app.celery_app", "worker", "--loglevel=info"]
