# Multi-stage Dockerfile — one image, three targets
FROM python:3.11-slim AS base

WORKDIR /app
RUN pip install --no-cache-dir pip --upgrade

COPY pyproject.toml .
COPY packages/ packages/
COPY apps/ apps/
COPY migrations/ migrations/
COPY alembic.ini .

RUN pip install --no-cache-dir .

# -- API target --
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -- Worker target --
FROM base AS worker
CMD ["python", "-m", "apps.worker.run"]

# -- Scheduler target --
FROM base AS scheduler
CMD ["python", "-m", "apps.scheduler.run"]
