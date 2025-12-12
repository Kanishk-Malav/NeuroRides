# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for building
# CRITICAL: Add libssl-dev for proper SSL/SNI support with Neon
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    curl \
    libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Install runtime dependencies
# CRITICAL: Install postgresql-client-15 or newer for proper SNI support
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gnupg \
    wget && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client-15 \
    gdal-bin \
    libgdal-dev \
    curl \
    nginx \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set work directory
WORKDIR /app

# Create directories with proper permissions
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R app:app /app

# Copy project files
COPY --chown=app:app . /app/

# Copy nginx configuration if exists
RUN if [ -f docker/nginx.conf ]; then cp docker/nginx.conf /etc/nginx/sites-available/default; fi

# Collect static files
RUN python manage.py collectstatic --noinput

# Create entrypoint script if exists
RUN if [ -f docker/entrypoint.sh ]; then \
    cp docker/entrypoint.sh /entrypoint.sh && \
    chmod +x /entrypoint.sh; \
    else \
    echo '#!/bin/bash\nexec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh; \
    fi

# Switch to app user
USER app

# Health check (FIX the URL to match your actual endpoint)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "100", "--timeout", "30", "--keep-alive", "2", "neurorides.wsgi:application"]