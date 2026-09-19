# Community default Dockerfile for Volvox Trader (x86_64 or arm64).
# Bundles Ollama + the bot loop + the dashboard in one container.
# Build:  docker build -t volvox-trader .
# Run:    docker run -d -p 8079:8079 -v volvox-data:/app/logs volvox-trader
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./
COPY ai_trader ./ai_trader
COPY config ./config
COPY .env.example ./
RUN pip install --no-cache-dir .

COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV OLLAMA_MODEL=qwen2.5:3b DASH_HOST=0.0.0.0 DASH_PORT=8079
EXPOSE 8079 11434

ENTRYPOINT ["docker-entrypoint.sh"]