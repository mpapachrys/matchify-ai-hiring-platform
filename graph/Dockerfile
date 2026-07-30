# ── base: dependency layer, cached until requirements.txt changes ──
#
# Build context MUST be the repo root, not graph/ — unlike apps/api's
# Dockerfile (context ./apps/api), graph.main runs as a package
# (`python -m graph.main`) and every internal module does absolute
# `from graph.xxx import ...` imports assuming repo root is on PYTHONPATH.
# Build with: docker build -f graph/Dockerfile -t matchify/graph .  (from repo root)
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# ── runtime: baked source, non-root ──
#
# No dev stage: graph/ has no in-Docker hot-reload workflow today (developed
# via the hiring-platform conda env directly), and this image is prod-only
# (see docker-compose.prod.yml) — nothing to mirror
# docker-compose.override.yml's bind-mount pattern for.
#
# No HEALTHCHECK: apps/api's hits an HTTP /health endpoint, which doesn't
# exist for a polling worker. `restart: unless-stopped` in
# docker-compose.prod.yml already handles process-death recovery, which is
# the thing that actually matters here.
FROM base AS runtime
COPY graph/ ./graph/

RUN useradd --create-home --uid 1001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "graph.main", "--watch"]
