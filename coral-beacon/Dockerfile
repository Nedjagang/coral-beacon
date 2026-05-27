FROM python:3.12-slim

# Install system deps for the Coral binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download Coral CLI binary (v0.3.0, x86_64 Linux)
RUN curl -fsSL \
    https://github.com/withcoral/coral/releases/download/v0.3.0/coral-x86_64-unknown-linux-gnu.tar.gz \
    -o /tmp/coral.tar.gz \
    && tar -xzf /tmp/coral.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/coral \
    && rm /tmp/coral.tar.gz

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Coral config (no secrets — those come from env vars at runtime)
ENV CORAL_CONFIG_DIR=/app/coral-config

# Default to Haiku for cost-effective demo runs
ENV LLM_MODE=haiku
ENV CORAL_TRANSPORT=subprocess

EXPOSE 8000

# start.sh registers the runbook source (idempotent) then launches uvicorn
CMD ["/app/scripts/start.sh"]
