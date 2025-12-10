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
    nginx \
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

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/sites-available/default

# Collect static files
RUN python manage.py collectstatic --noinput

# Create entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "100", "--timeout", "30", "--keep-alive", "2", "neurorides.wsgi:application"]

FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 8080
CMD ["npm", "start"]
