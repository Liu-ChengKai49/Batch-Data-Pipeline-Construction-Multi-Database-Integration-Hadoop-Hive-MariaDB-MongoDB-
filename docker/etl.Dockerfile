# ---- Stage 1: builder ----
FROM python:3.11-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# (Optional) compile deps; keep slim – only install when you need compiled wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# 1) Base deps first for better caching
COPY docker/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 2) Install your project from pyproject.toml (optionally with extras)
#    Set EXTRAS=dev at build time if you really need dev extras in the image.
ARG EXTRAS=""
COPY pyproject.toml ./pyproject.toml
COPY src/ ./src
RUN . /opt/venv/bin/activate && \
    if [ -n "$EXTRAS" ]; then \
        pip install --no-cache-dir ".[${EXTRAS}]"; \
    else \
        pip install --no-cache-dir .; \
    fi

# Sanity import to fail fast if dependencies are missing
RUN . /opt/venv/bin/activate && python -c "import batch_pipeline"

# ---- Stage 2: runtime (non-root, small) ----
FROM python:3.11-slim-bookworm AS runtime
ARG VERSION="0.0.0"
ARG REVISION="dev"
ARG REPO_URL="https://github.com/owner/repo"
ARG TITLE="batch-etl"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Non-root runtime user
ARG APP_UID=10001
RUN adduser --uid ${APP_UID} --disabled-password --gecos "" appuser

# Copy only the virtualenv; code is already installed into it as a proper wheel
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER appuser

# OCI labels (CI will add/override more via metadata-action)
LABEL org.opencontainers.image.title="${TITLE}" \
      org.opencontainers.image.description="Batch ETL for TW-stock pipeline" \
      org.opencontainers.image.source="${REPO_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"

# Default entrypoint for one-shot ETL runs; change if you run a service
ENTRYPOINT ["python", "-m", "batch_pipeline.etl"]
