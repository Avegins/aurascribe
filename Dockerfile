# AuraScribe MVP - Dockerfile
# Python 3.12 slim base
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies if required (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and assets
COPY src/ /app/src/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY pyproject.toml /app/

# Create a non-root user for security
RUN useradd -m -u 1000 aurascribe && \
    chown -R aurascribe:aurascribe /app
USER aurascribe

# Expose container port
EXPOSE 5000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:5000/health || exit 1

# Launch using Gunicorn WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "aurascribe.main:app"]

