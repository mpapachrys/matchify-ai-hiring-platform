# ─────────────────────────────────────────────────────────────
# calendar-mcp — interview scheduling assistant.
#
# Small, single stage: this isn't a public-facing service, just an internal
# sidecar apps/api calls over the compose network. Secrets (.env,
# .gcp-saved-tokens.json) are bind-mounted at runtime, never baked in here.
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# tzdata (OS-level) so datetime.now().astimezone() inside mcp_bridge.py
# resolves the same Athens offset/DST rules that interview_api.py's own
# zoneinfo("Europe/Athens") uses — "13:00" must mean the same instant on
# both sides of the create_event call. tzdata is pinned as a Python package
# too (requirements.txt) as a fallback if the OS database is ever stripped.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Athens

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY run_server.py interview_api.py agent.py ./

RUN useradd --create-home --uid 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/health').status==200 else 1)"

CMD ["uvicorn", "interview_api:app", "--host", "0.0.0.0", "--port", "8090"]
