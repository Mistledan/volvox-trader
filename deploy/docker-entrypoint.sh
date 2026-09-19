#!/usr/bin/env bash
# Container entrypoint: start Ollama, pull the model, then run the bot + dashboard.
set -e

ollama serve &
until ollama list >/dev/null 2>&1; do sleep 2; done

if ! ollama list | grep -q "${OLLAMA_MODEL}"; then
  echo "Pulling ${OLLAMA_MODEL}..."
  ollama pull "${OLLAMA_MODEL}"
fi

python -m ai_trader.dashboard &
exec python -m ai_trader.main --config config/production.yaml --run