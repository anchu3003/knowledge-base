# syntax=docker/dockerfile:1
## KB-5.10 (trả TD-9): image từng **16,5 GB** vì 3 lý do đo được:
##   1. `torch` bản mặc định của PyPI = **CUDA** (`2.15.0+cu132`) kéo theo 15 gói `nvidia-*` ≈ **3,0 GB**
##   2. `/wheels` (3,0 GB) bị `COPY --from=builder` vào image cuối rồi **không xoá**
##   3. các layer pip/apt còn sót
## Cách sửa: cài **torch CPU** (`--index-url .../whl/cpu`) TRƯỚC, và dùng **bind mount** cho `/wheels`
## (wheels chỉ tồn tại trong lúc `RUN`, không thành layer) ⇒ image còn ~vài GB.

## ---------- Builder stage: build wheels to speed up installs ----------
FROM python:3.13-slim AS builder

WORKDIR /wheels

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

# KB-5.10: CPU-only torch. `--extra-index-url` vẫn để pip thấy CPU build khi resolve dependency của
# `sentence-transformers`, nhưng PEP 440 xếp `2.x.y+cpu` **thấp hơn** `2.x.y` (bản CUDA trên PyPI) ⇒ pip
# vẫn có thể chọn bản CUDA. Vì vậy sau khi build xong phải **xoá wheel torch không phải `+cpu`** khỏi
# /wheels (nếu không, stage cuối `--no-index --find-links` sẽ chọn bản CUDA).
ARG TORCH_CPU_INDEX=https://download.pytorch.org/whl/cpu

RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --no-cache-dir torch --index-url "${TORCH_CPU_INDEX}" -w /wheels \
    && pip wheel --no-cache-dir -r /tmp/requirements.txt -w /wheels --extra-index-url "${TORCH_CPU_INDEX}" \
    && ls /wheels | grep -E '^torch-2' | grep -v '+cpu' | sed 's|^|/wheels/|' | xargs -r rm -f \
    && ls /wheels | grep -E '^nvidia' | sed 's|^|/wheels/|' | xargs -r rm -f \
    && echo '--- torch wheels giữ lại ---' && ls /wheels | grep -E '^torch-'


## ---------- Final stage: minimal runtime image ----------
FROM python:3.13-slim

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

COPY requirements.txt /tmp/requirements.txt

# KB-5.10: cài torch **CPU** trước (bản `+cpu` không kéo `nvidia-*`). Sau bước này `pip install -r` thấy
# `torch>=…` đã thoả nên **không** tải lại bản CUDA.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# KB-5.10: `--mount=type=bind` ⇒ /wheels **không** vào layer (trước đây `COPY --from=builder` để lại 3,0 GB).
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
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

# Liveness probe (KB-3.4) — chỉ `/health`: rẻ, không chạm Chroma/provider.
# KHÔNG dùng `/ready?deep=true` trong healthcheck (mỗi 30s tốn 1 request quota).
# `--start-period` dài vì lần đầu phải tải embedding model (~30–60s trên CPU).
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Default command: production-ready Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
