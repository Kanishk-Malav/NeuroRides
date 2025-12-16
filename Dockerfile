# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for building
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    postgresql-client \
    gdal-bin \
    libgdal-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set work directory
WORKDIR /app

# Create directories with proper permissions
RUN mkdir -p /app/staticfiles /app/media /app/logs \
    && chown -R app:app /app

# Copy project files
COPY --chown=app:app . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Run migrations\n\
python manage.py migrate --noinput\n\
\n\
# Start Gunicorn with Cloud Run PORT\n\
exec gunicorn neurorides.wsgi:application \\\n\
    --bind 0.0.0.0:\$PORT \\\n\
    --workers 3 \\\n\
    --worker-class sync \\\n\
    --timeout 120 \\\n\
    --access-logfile - \\\n\
    --error-logfile -' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Switch to app user
USER app

# Health check - Use $PORT variable
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:\$PORT/health/ || exit 1

# Cloud Run automatically exposes port, no need for EXPOSE
# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]