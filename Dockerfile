# syntax=docker/dockerfile:1.4
# Unified Multi-stage Dockerfile for Task Engine Services
# Targets: api, worker, scheduler
# Meets SRS §16.1

FROM python:3.14-slim AS builder
WORKDIR /build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/build/.venv
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim AS base
WORKDIR /app
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
COPY --from=builder /build/.venv /app/.venv
COPY src/ /app/src/
COPY alembic.ini /app/alembic.ini
COPY scripts/ /app/scripts/
RUN chown -R appuser:appgroup /app
USER appuser

# Target: API
FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 /app/scripts/healthcheck.py api || exit 1
ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Target: Worker
FROM base AS worker
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 /app/scripts/healthcheck.py worker || exit 1
ENTRYPOINT ["python3", "-m", "src.sdk.cli", "worker", "start"]
CMD ["--queues", "default", "--concurrency", "4"]

# Target: Scheduler
FROM base AS scheduler
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 /app/scripts/healthcheck.py scheduler || exit 1
ENTRYPOINT ["python3", "-m", "src.sdk.cli", "scheduler", "start"]
