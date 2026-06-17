#!/usr/bin/env bash
# Build and run the API + demo site in Docker, then open it in the browser.
#
#   ./run.sh         build, run, and open http://localhost:8080
#   ./run.sh stop    stop and remove the container
#
# Requires Docker. The data must be built first (uv run refresh-reps).
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="irl-reps"
NAME="irl-reps-demo"
PORT="${PORT:-8080}"
URL="http://localhost:${PORT}"

open_browser() {
  if command -v open >/dev/null 2>&1; then open "$1"          # macOS
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" # Linux
  fi
}

# Ensure the Docker daemon is running; start it if possible, then wait.
ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Install Docker Desktop first." >&2
    exit 1
  fi
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  echo "Docker daemon not running. Starting it…"
  if command -v open >/dev/null 2>&1; then
    open -a Docker >/dev/null 2>&1 || true   # macOS: Docker Desktop
  elif command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start docker >/dev/null 2>&1 || true  # Linux
  fi

  printf "Waiting for Docker"
  for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      echo " — ready."
      return 0
    fi
    printf "."; sleep 1
  done

  echo
  echo "Docker did not start. Start it manually and retry." >&2
  exit 1
}

ensure_docker

if [ "${1:-}" = "stop" ]; then
  docker rm -f "$NAME" >/dev/null 2>&1 && echo "Stopped $NAME." || echo "Nothing to stop."
  exit 0
fi

if [ ! -f data/processed/boundaries.parquet ] || [ ! -f data/representatives.db ]; then
  echo "Missing data. Build it first:  uv run refresh-reps" >&2
  exit 1
fi

echo "Building image…"
docker build -t "$IMAGE" .

echo "Starting container on port ${PORT}…"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "${PORT}:7860" "$IMAGE" >/dev/null

printf "Waiting for the API"
for _ in $(seq 1 30); do
  if curl -fs "${URL}/health" >/dev/null 2>&1; then
    echo " — ready."
    echo "Open: ${URL}"
    open_browser "$URL"
    echo "Stop with: ./run.sh stop"
    exit 0
  fi
  printf "."; sleep 1
done

echo
echo "API did not become ready. Logs:" >&2
docker logs "$NAME" | tail -20 >&2
exit 1
