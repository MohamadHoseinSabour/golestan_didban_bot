# Multi-stage Dockerfile for Golestan Divar Bot
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into a virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "python-telegram-bot[socks]>=21.0" \
    "httpx[http2,socks]>=0.27" \
    "tenacity>=9.0" \
    "pydantic>=2.7" \
    "pydantic-settings>=2.2" \
    "pyyaml>=6.0" \
    "aiosqlite>=0.20" \
    "pytz>=2024.1" \
    "structlog>=24.1"

# --- Final Production Stage ---
FROM python:3.12-slim AS runner

WORKDIR /app

# Environment settings
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=Asia/Tehran

# Copy installed venv
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged user
RUN groupadd -g 10001 botgroup && \
    useradd -u 10001 -g botgroup -s /bin/sh -m botuser

# Copy application source
COPY src/ /app/src/
COPY config.example.yaml /app/config.example.yaml
COPY config.example.yaml /app/config.yaml

# Set up data and log directories with proper permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R botuser:botgroup /app

# Install package in editable/pth mode
RUN echo "/app/src" > /opt/venv/lib/python3.12/site-packages/divar_bot.pth

USER botuser

ENTRYPOINT ["python", "-m", "divar_bot"]
CMD []

