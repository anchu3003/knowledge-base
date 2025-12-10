## ---------- Builder stage: build wheels to speed up installs ----------
FROM python:3.11-slim AS builder

WORKDIR /wheels

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

# Pre-build wheels for all dependencies to reuse across layers
RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --no-cache-dir -r /tmp/requirements.txt -w /wheels


## ---------- Final stage: minimal runtime image ----------
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Reduce Python runtime noise and leverage non-interactive apt
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROMA_TELEMETRY_ENABLED=false \
    ANONYMIZED_TELEMETRY=false \
    CHROMA_SERVER_NO_ANALYTICS=1 \
    LANGCHAIN_TRACING_V2=false \
    LANGCHAIN_ENDPOINT="" \
    LANGCHAIN_TELEMETRY=false

# Install small set of runtime libraries often needed by scientific stacks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libstdc++6 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first, then install deps (prefer prebuilt wheels)
COPY requirements.txt /tmp/requirements.txt
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    || pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application source
COPY . .

# Create a non-root user and ensure writable data dirs
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/chroma_db /app/documents \
    && chown -R appuser:appuser /app

USER appuser

# Expose FastAPI port
EXPOSE 8000

# Default command: production-ready Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
