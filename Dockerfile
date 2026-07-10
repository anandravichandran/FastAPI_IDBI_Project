# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_UPGRADE_STRATEGY=only-if-needed

WORKDIR /app

# Upgrade pip first — newer resolvers handle deep dependency graphs better.
# The build log reports pip 25.3 → 26.1.2 is available.
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./
# Phase 1 — lightweight core framework (fastapi, uvicorn, pydantic, httpx, jwt).
# These resolve quickly and establish a stable base.
RUN pip install --no-cache-dir \
    fastapi uvicorn python-multipart pydantic pydantic-settings httpx PyJWT pypdf
# Phase 2 — sentence-transformers (torch, transformers, huggingface-hub).
# Heavy but has well-trodden, mutually-compatible dep paths.
RUN pip install --no-cache-dir sentence-transformers
# Phase 3 — chromadb (numpy, pandas, protobuf, grpcio, onnxruntime).
# Chromadb depends on tokenizers<=0.20.3 which has no cp314 wheel, so pip
# builds it from source via maturin/Rust.  Render's build env has a read-only
# /usr/local/cargo, so point CARGO_HOME at a writable temp dir.
ENV CARGO_HOME=/tmp/cargo
RUN mkdir -p $CARGO_HOME && pip install --no-cache-dir tokenizers==0.20.3
RUN pip install --no-cache-dir chromadb
# Phase 4 — openbb (the deepest tree: pandas, numpy, scipy, plotly, dash, ...).
# Installed last so the resolver only has 3 new packages' constraints to satisfy
# against an already-resolved set of installed packages.
RUN pip install --no-cache-dir openbb

# Copy all sub-application packages and the unified entrypoint.
COPY common ./common
COPY advisor ./advisor
COPY coach ./coach
COPY budget ./budget
COPY savings ./savings
COPY rag ./rag
COPY market ./market
COPY server.py ./server.py

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/livez').status==200 else 1)"

# --timeout-graceful-shutdown lets in-flight requests finish (and the parent
# lifespan release pooled HTTP clients) before the worker is killed.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "25", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
