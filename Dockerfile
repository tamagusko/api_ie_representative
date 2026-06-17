# Irish TD lookup API — container image.
#
# Strategy: the static boundary index (data/processed/boundaries.parquet, ~1.5 MB)
# is baked in; current TDs are re-fetched from the Oireachtas API at build time,
# so every (re)build ships fresh representative data. The container then boots in
# seconds and serves with no network. The committed representatives.db is a
# fail-soft fallback used only if the API is unreachable during a build.
#
# A scheduled factory rebuild (.github/workflows/refresh-space.yml) is what makes
# this refresh happen monthly on Hugging Face Spaces.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IRL_REPS_DATA_DIR=/app/data

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies + the package itself (gives `refresh-reps` and the app).
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# Bake the static boundary index + overrides, plus the last-known TD database.
# The committed DB lets the refresh below fail soft (carry forward) if the
# Oireachtas API is unreachable at build time.
COPY data/processed/boundaries.parquet ./data/processed/boundaries.parquet
COPY data/representatives.db ./data/representatives.db
COPY data/overrides.yaml ./data/overrides.yaml

# Re-fetch current TDs at build time so every (re)build ships fresh data.
# Boundaries are static between reviews, so skip the heavy GeoJSON ETL.
RUN refresh-reps --skip-boundaries

# Hugging Face Spaces (and most PaaS) route to this port; override with --port.
EXPOSE 7860

# Run as a non-root user; the app only reads its data (SQLite opened read-only).
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "--factory", "irl_reps.api.app:create_app", \
     "--host", "0.0.0.0", "--port", "7860"]
