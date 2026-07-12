# syntax=docker/dockerfile:1
# =============================================================================
# Financial Suite - production image
# =============================================================================
# Pinned to CPython 3.12 (slim) so every dependency installs from a prebuilt
# manylinux wheel. This is the deterministic fix for the Render build failure
# where the native runtime defaulted to Python 3.14, for which `tokenizers`
# has no wheel and pip tried to compile it from source with maturin/Rust on a
# read-only filesystem.
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Install ONLY prebuilt wheels for these native-extension packages. On
    # cp312 the wheels exist, so this never triggers a Rust/maturin build; if a
    # wheel were ever missing the build fails fast and loudly instead of
    # silently invoking the Rust toolchain.
    PIP_ONLY_BINARY=tokenizers,safetensors,torch

WORKDIR /app

RUN pip install --upgrade pip

# Dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the shared library + every mounted sub-application + the entrypoint.
COPY common ./common
COPY app ./app
COPY advisor ./advisor
COPY coach ./coach
COPY budget ./budget
COPY savings ./savings
COPY rag ./rag
COPY market ./market
COPY server.py ./server.py

# Create non-root user and ensure ChromaDB persistence directory is writable.
RUN useradd --create-home --uid 10001 appuser && \
    mkdir -p /app/.chroma && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Docker-level health check (Render uses /livez from render.yaml instead).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/livez').status==200 else 1)"

# --timeout-graceful-shutdown lets in-flight requests finish (and the parent
# lifespan release pooled HTTP clients) before the worker is killed.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "25", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
