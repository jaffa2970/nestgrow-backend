# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir setuptools -r requirements.txt

COPY . .

RUN bash build_cython.sh

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Moduli critici compilati (solo .so, nessun sorgente)
COPY --from=builder /app/app/*.so ./app/

# Moduli non critici in chiaro
COPY app/__init__.py ./app/
COPY app/messaging.py ./app/
COPY app/api/ ./app/api/
COPY app/core/ ./app/core/

# Alembic e configurazione
COPY alembic/ ./alembic/
COPY alembic.ini .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
