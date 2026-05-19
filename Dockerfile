FROM python:3.11-slim

# Metadata
LABEL maintainer="voltstreamintelligence@gmail.com"
LABEL description="VoltStream AI — Autonomous Battery Dispatch for ERCOT"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker caches this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Create directories for persistent data
RUN mkdir -p /app/data/storage /app/logs

# Environment variables (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV VOLTSTREAM_MODE=demo
ENV VOLTSTREAM_DB_PATH=/app/data/storage/voltstream.db
ENV VOLTSTREAM_LOG_PATH=/app/logs/voltstream.log
ENV ERCOT_EMAIL=""
ENV ERCOT_PASSWORD=""
ENV ERCOT_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV VOLTSTREAM_WEBHOOK=""

# Health check — verify Python and core modules load
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "from core.orchestrator import Orchestrator; print('healthy')" || exit 1

# Default: run the orchestrator in demo mode (5 ticks)
# Override with: docker run voltstream python main.py status
CMD ["python", "main.py", "orchestrate"]
