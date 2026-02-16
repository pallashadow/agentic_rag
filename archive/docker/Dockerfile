# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency metadata first for better caching
COPY pyproject.toml README.md ./
COPY lib/ ./lib/

# Install Python dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Copy application code
COPY server.py .
COPY prompt.json .

# Cloud Run: pass config via env vars / Secret Manager, don't bake local .env into the image.

# Expose port (Cloud Run will set PORT env variable)
ENV PORT=8080

# Run the application
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips="*"

