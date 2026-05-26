# syntax=docker/dockerfile:1

# ---- builder ----------------------------------------------------------------
# Installs Python deps + the project into /install. build-essential is only
# needed here (for asyncpg, bcrypt, etc.) and never ships in the runtime image.
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir --prefix=/install .


# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim

# curl is used by the HEALTHCHECK. ~1MB.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 app

WORKDIR /app

# Installed deps + the app package from the builder stage.
COPY --from=builder /install /usr/local

# Alembic config and migrations aren't part of the installed package.
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini ./

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8001}/api/health" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
