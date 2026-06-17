# Irish TD lookup API — container image.
#
# Strategy: the processed boundary index (data/processed/boundaries.parquet, ~1.5 MB
# after ETL simplification) and the TD database are baked into the image, so
# the container boots in seconds with no network. Refresh them on the host with
# `uv run refresh-reps`, rebuild the image, redeploy.
#
# To instead rebuild the data INSIDE the image (self-contained, needs network at
# build time), drop the two data COPY lines and uncomment the refresh RUN below.

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

# Bake the prebuilt data (boundary index + representatives DB + overrides).
COPY data/processed/boundaries.parquet ./data/processed/boundaries.parquet
COPY data/representatives.db ./data/representatives.db
COPY data/overrides.yaml ./data/overrides.yaml

# --- Alternative: rebuild data at image-build time instead of baking it ---
# RUN uv run refresh-reps

# Hugging Face Spaces (and most PaaS) route to this port; override with --port.
EXPOSE 7860

# Run as a non-root user; the app only reads its data (SQLite opened read-only).
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "--factory", "irl_reps.api.app:create_app", \
     "--host", "0.0.0.0", "--port", "7860"]
