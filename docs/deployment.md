# NeuroRides Platform Deployment Guide

## Overview

This guide covers the complete deployment process for the NeuroRides platform, from development to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Production Configuration](#production-configuration)
6. [SSL/TLS Setup](#ssltls-setup)
7. [Monitoring Setup](#monitoring-setup)
8. [Backup and Recovery](#backup-and-recovery)
9. [Scaling](#scaling)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 50GB SSD
- **OS**: Ubuntu 20.04+ or CentOS 8+
- **Network**: Public IP with ports 80, 443 accessible

#### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 100GB+ SSD
- **OS**: Ubuntu 22.04 LTS
- **Network**: Load balancer with multiple instances

### Software Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    curl \
    wget \
    git \
    nginx \
    postgresql \
    postgresql-contrib \
    postgresql-14-postgis-3 \
    redis-server \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    certbot \
    python3-certbot-nginx
```

### Docker Installation

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

## Environment Setup

### Environment Variables

Create environment configuration files for different environments:

#### Development (.env.development)
```bash
# Django Settings
DEBUG=True
SECRET_KEY=your-development-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DATABASE_URL=postgresql://neurorides:password@localhost:5432/neurorides_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Payment Gateways (Sandbox)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...

# Email (Development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Logging
LOG_LEVEL=DEBUG
```

#### Staging (.env.staging)
```bash
# Django Settings
DEBUG=False
SECRET_KEY=your-staging-secret-key
ALLOWED_HOSTS=staging.neurorides.com

# Database
DATABASE_URL=postgresql://neurorides:secure_password@db:5432/neurorides_staging

# Redis
REDIS_URL=redis://redis:6379/0

# Payment Gateways (Sandbox)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...

# Email
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=postmaster@mg.neurorides.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True

# Storage (Optional)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=neurorides-staging

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
```

#### Production (.env.production)
```bash
# Django Settings
DEBUG=False
SECRET_KEY=your-production-secret-key-very-long-and-secure
ALLOWED_HOSTS=neurorides.com,www.neurorides.com

# Database
DATABASE_URL=postgresql://neurorides:very_secure_password@db:5432/neurorides_prod

# Redis
REDIS_URL=redis://redis:6379/0

# Payment Gateways (Live)
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...

# Email
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=postmaster@mg.neurorides.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True

# Storage
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=neurorides-production

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Logging
LOG_LEVEL=WARNING
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project

# Monitoring
PROMETHEUS_METRICS_ENABLED=True
```

## Docker Deployment

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgis/postgis:14-3.2
    environment:
      POSTGRES_DB: neurorides_prod
      POSTGRES_USER: neurorides
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - neurorides_network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - neurorides_network
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    env_file:
      - .env.production
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    networks:
      - neurorides_network
    depends_on:
      - db
      - redis
    restart: unless-stopped

  celery:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    command: celery -A neurorides worker -l info
    env_file:
      - .env.production
    volumes:
      - media_volume:/app/media
    networks:
      - neurorides_network
    depends_on:
      - db
      - redis
    restart: unless-stopped

  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    command: celery -A neurorides beat -l info
    env_file:
      - .env.production
    networks:
      - neurorides_network
    depends_on:
      - db
      - redis
    restart: unless-stopped

  nginx:
    build:
      context: ./docker
      dockerfile: Dockerfile.nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./docker/nginx/ssl:/etc/nginx/ssl
    networks:
      - neurorides_network
    depends_on:
      - web
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  neurorides_network:
    driver: bridge
```

### Production Dockerfile

Create `docker/Dockerfile.prod`:

```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "neurorides.wsgi:application"]
```

### Nginx Configuration

Create `docker/nginx.prod.conf`:

```nginx
upstream web {
    server web:8000;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name neurorides.com www.neurorides.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name neurorides.com www.neurorides.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Client Max Body Size
    client_max_body_size 100M;

    # Static Files
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # WebSocket Support
    location /ws/ {
        proxy_pass http://web;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # API and Admin
    location / {
        proxy_pass http://web;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health Check
    location /health/ {
        proxy_pass http://web;
        access_log off;
    }
}
```

### Deployment Script

Create `scripts/deploy.sh`:

```bash
#!/bin/bash

set -e

# Configuration
REPO_URL="https://github.com/your-org/neurorides-platform.git"
DEPLOY_DIR="/opt/neurorides"
BACKUP_DIR="/opt/backups"
ENV_FILE=".env.production"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    error "Docker is not installed"
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed"
fi

# Create backup
create_backup() {
    log "Creating backup..."
    
    BACKUP_NAME="neurorides-backup-$(date +%Y%m%d-%H%M%S)"
    BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
    
    mkdir -p "$BACKUP_PATH"
    
    # Backup database
    if docker-compose -f docker-compose.prod.yml ps db | grep -q "Up"; then
        log "Backing up database..."
        docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U neurorides neurorides_prod > "$BACKUP_PATH/database.sql"
    fi
    
    # Backup media files
    if [ -d "$DEPLOY_DIR/media" ]; then
        log "Backing up media files..."
        cp -r "$DEPLOY_DIR/media" "$BACKUP_PATH/"
    fi
    
    # Backup environment file
    if [ -f "$DEPLOY_DIR/$ENV_FILE" ]; then
        cp "$DEPLOY_DIR/$ENV_FILE" "$BACKUP_PATH/"
    fi
    
    log "Backup created at $BACKUP_PATH"
}

# Deploy application
deploy() {
    log "Starting deployment..."
    
    # Create deployment directory
    sudo mkdir -p "$DEPLOY_DIR"
    sudo chown $USER:$USER "$DEPLOY_DIR"
    
    # Clone or update repository
    if [ -d "$DEPLOY_DIR/.git" ]; then
        log "Updating repository..."
        cd "$DEPLOY_DIR"
        git fetch origin
        git reset --hard origin/main
    else
        log "Cloning repository..."
        git clone "$REPO_URL" "$DEPLOY_DIR"
        cd "$DEPLOY_DIR"
    fi
    
    # Check if environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        warn "Environment file $ENV_FILE not found. Please create it before deployment."
        cp .env.example "$ENV_FILE"
        error "Please configure $ENV_FILE and run deployment again."
    fi
    
    # Build and start services
    log "Building Docker images..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    
    log "Starting services..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be ready
    log "Waiting for services to be ready..."
    sleep 30
    
    # Run migrations
    log "Running database migrations..."
    docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate
    
    # Collect static files
    log "Collecting static files..."
    docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput
    
    # Create initial data if needed
    log "Creating initial data..."
    docker-compose -f docker-compose.prod.yml exec -T web python manage.py create_initial_users --skip-existing
    
    log "Deployment completed successfully!"
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Check if services are running
    if ! docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        error "Some services are not running"
    fi
    
    # Check application health
    if ! curl -f http://localhost/health/ > /dev/null 2>&1; then
        error "Application health check failed"
    fi
    
    log "Health check passed!"
}

# Rollback function
rollback() {
    warn "Rolling back to previous version..."
    
    # Stop current services
    docker-compose -f docker-compose.prod.yml down
    
    # Restore from latest backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | head -n1)
    if [ -z "$LATEST_BACKUP" ]; then
        error "No backup found for rollback"
    fi
    
    log "Restoring from backup: $LATEST_BACKUP"
    
    # Restore database
    if [ -f "$BACKUP_DIR/$LATEST_BACKUP/database.sql" ]; then
        docker-compose -f docker-compose.prod.yml up -d db
        sleep 10
        docker-compose -f docker-compose.prod.yml exec -T db psql -U neurorides -d neurorides_prod < "$BACKUP_DIR/$LATEST_BACKUP/database.sql"
    fi
    
    # Restore media files
    if [ -d "$BACKUP_DIR/$LATEST_BACKUP/media" ]; then
        rm -rf "$DEPLOY_DIR/media"
        cp -r "$BACKUP_DIR/$LATEST_BACKUP/media" "$DEPLOY_DIR/"
    fi
    
    # Start services
    docker-compose -f docker-compose.prod.yml up -d
    
    log "Rollback completed"
}

# Main execution
case "${1:-deploy}" in
    "deploy")
        create_backup
        deploy
        health_check
        ;;
    "backup")
        create_backup
        ;;
    "rollback")
        rollback
        ;;
    "health")
        health_check
        ;;
    *)
        echo "Usage: $0 {deploy|backup|rollback|health}"
        exit 1
        ;;
esac

log "Script completed successfully!"
```

Make the script executable:

```bash
chmod +x scripts/deploy.sh
```

## Manual Deployment

### Database Setup

```bash
# Install PostgreSQL with PostGIS
sudo apt install postgresql postgresql-contrib postgresql-14-postgis-3

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE neurorides_prod;
CREATE USER neurorides WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE neurorides_prod TO neurorides;
ALTER USER neurorides CREATEDB;
\q
EOF

# Enable PostGIS extension
sudo -u postgres psql -d neurorides_prod << EOF
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
\q
EOF
```

### Application Setup

```bash
# Create application directory
sudo mkdir -p /opt/neurorides
sudo chown $USER:$USER /opt/neurorides
cd /opt/neurorides

# Clone repository
git clone https://github.com/your-org/neurorides-platform.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env.production
# Edit .env.production with production values

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create initial data
python manage.py create_initial_users
```

### Systemd Services

Create systemd service files for the application:

#### Django Application Service

Create `/etc/systemd/system/neurorides.service`:

```ini
[Unit]
Description=NeuroRides Django Application
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=neurorides
Group=neurorides
WorkingDirectory=/opt/neurorides
Environment=PATH=/opt/neurorides/venv/bin
EnvironmentFile=/opt/neurorides/.env.production
ExecStart=/opt/neurorides/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 4 --worker-class gevent neurorides.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Celery Worker Service

Create `/etc/systemd/system/neurorides-celery.service`:

```ini
[Unit]
Description=NeuroRides Celery Worker
After=network.target redis.service

[Service]
Type=exec
User=neurorides
Group=neurorides
WorkingDirectory=/opt/neurorides
Environment=PATH=/opt/neurorides/venv/bin
EnvironmentFile=/opt/neurorides/.env.production
ExecStart=/opt/neurorides/venv/bin/celery -A neurorides worker -l info
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Celery Beat Service

Create `/etc/systemd/system/neurorides-celery-beat.service`:

```ini
[Unit]
Description=NeuroRides Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=exec
User=neurorides
Group=neurorides
WorkingDirectory=/opt/neurorides
Environment=PATH=/opt/neurorides/venv/bin
EnvironmentFile=/opt/neurorides/.env.production
ExecStart=/opt/neurorides/venv/bin/celery -A neurorides beat -l info
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable neurorides neurorides-celery neurorides-celery-beat
sudo systemctl start neurorides neurorides-celery neurorides-celery-beat
```

## SSL/TLS Setup

### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d neurorides.com -d www.neurorides.com

# Test automatic renewal
sudo certbot renew --dry-run

# Set up automatic renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
```

### Manual SSL Certificate

If using a custom SSL certificate:

```bash
# Create SSL directory
sudo mkdir -p /etc/nginx/ssl

# Copy certificate files
sudo cp your-certificate.crt /etc/nginx/ssl/fullchain.pem
sudo cp your-private-key.key /etc/nginx/ssl/privkey.pem

# Set proper permissions
sudo chmod 600 /etc/nginx/ssl/privkey.pem
sudo chmod 644 /etc/nginx/ssl/fullchain.pem
```

## Monitoring Setup

### Prometheus and Grafana

Create `docker-compose.monitoring.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    networks:
      - monitoring

  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
```

### Log Management with ELK Stack

Create `docker-compose.elk.yml`:

```yaml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.8.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    networks:
      - elk

  logstash:
    image: docker.elastic.co/logstash/logstash:8.8.0
    ports:
      - "5044:5044"
    volumes:
      - ./monitoring/logstash/pipeline:/usr/share/logstash/pipeline
    networks:
      - elk
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.8.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    networks:
      - elk
    depends_on:
      - elasticsearch

volumes:
  elasticsearch_data:

networks:
  elk:
    driver: bridge
```

## Backup and Recovery

### Automated Backup Script

Create `scripts/backup.sh`:

```bash
#!/bin/bash

set -e

# Configuration
BACKUP_DIR="/opt/backups"
RETENTION_DAYS=30
DB_NAME="neurorides_prod"
DB_USER="neurorides"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate backup filename
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="neurorides_backup_$BACKUP_DATE"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

mkdir -p "$BACKUP_PATH"

echo "Starting backup: $BACKUP_NAME"

# Backup database
echo "Backing up database..."
if command -v docker-compose &> /dev/null; then
    # Docker deployment
    docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_PATH/database.sql"
else
    # Manual deployment
    sudo -u postgres pg_dump "$DB_NAME" > "$BACKUP_PATH/database.sql"
fi

# Backup media files
echo "Backing up media files..."
if [ -d "/opt/neurorides/media" ]; then
    cp -r /opt/neurorides/media "$BACKUP_PATH/"
fi

# Backup configuration
echo "Backing up configuration..."
if [ -f "/opt/neurorides/.env.production" ]; then
    cp /opt/neurorides/.env.production "$BACKUP_PATH/"
fi

# Compress backup
echo "Compressing backup..."
cd "$BACKUP_DIR"
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

# Clean old backups
echo "Cleaning old backups..."
find "$BACKUP_DIR" -name "neurorides_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_NAME.tar.gz"

# Upload to cloud storage (optional)
if [ ! -z "$AWS_S3_BUCKET" ]; then
    echo "Uploading to S3..."
    aws s3 cp "$BACKUP_DIR/$BACKUP_NAME.tar.gz" "s3://$AWS_S3_BUCKET/backups/"
fi
```

### Recovery Script

Create `scripts/restore.sh`:

```bash
#!/bin/bash

set -e

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Available backups:"
    ls -la /opt/backups/neurorides_backup_*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"
RESTORE_DIR="/tmp/neurorides_restore_$(date +%s)"

# Validate backup file
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Starting restore from: $BACKUP_FILE"

# Extract backup
echo "Extracting backup..."
mkdir -p "$RESTORE_DIR"
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR" --strip-components=1

# Stop services
echo "Stopping services..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.prod.yml down
else
    sudo systemctl stop neurorides neurorides-celery neurorides-celery-beat
fi

# Restore database
if [ -f "$RESTORE_DIR/database.sql" ]; then
    echo "Restoring database..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.prod.yml up -d db
        sleep 10
        docker-compose -f docker-compose.prod.yml exec -T db dropdb -U neurorides neurorides_prod --if-exists
        docker-compose -f docker-compose.prod.yml exec -T db createdb -U neurorides neurorides_prod
        docker-compose -f docker-compose.prod.yml exec -T db psql -U neurorides -d neurorides_prod < "$RESTORE_DIR/database.sql"
    else
        sudo -u postgres dropdb neurorides_prod --if-exists
        sudo -u postgres createdb neurorides_prod
        sudo -u postgres psql -d neurorides_prod < "$RESTORE_DIR/database.sql"
    fi
fi

# Restore media files
if [ -d "$RESTORE_DIR/media" ]; then
    echo "Restoring media files..."
    rm -rf /opt/neurorides/media
    cp -r "$RESTORE_DIR/media" /opt/neurorides/
fi

# Restore configuration
if [ -f "$RESTORE_DIR/.env.production" ]; then
    echo "Restoring configuration..."
    cp "$RESTORE_DIR/.env.production" /opt/neurorides/
fi

# Start services
echo "Starting services..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.prod.yml up -d
else
    sudo systemctl start neurorides neurorides-celery neurorides-celery-beat
fi

# Cleanup
rm -rf "$RESTORE_DIR"

echo "Restore completed successfully!"
```

### Automated Backup Schedule

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /opt/neurorides/scripts/backup.sh

# Weekly database optimization
0 3 * * 0 /opt/neurorides/scripts/optimize_db.sh
```

## Scaling

### Horizontal Scaling

#### Load Balancer Configuration

Create `docker-compose.scale.yml`:

```yaml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    env_file:
      - .env.production
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    networks:
      - neurorides_network
    depends_on:
      - db
      - redis
    restart: unless-stopped
    deploy:
      replicas: 3

  nginx:
    build:
      context: ./docker
      dockerfile: Dockerfile.nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./docker/nginx/ssl:/etc/nginx/ssl
    networks:
      - neurorides_network
    depends_on:
      - web
    restart: unless-stopped

# ... other services
```

#### Database Scaling

For database scaling, consider:

1. **Read Replicas**: Set up PostgreSQL read replicas
2. **Connection Pooling**: Use PgBouncer
3. **Partitioning**: Partition large tables by date

#### Redis Scaling

For Redis scaling:

1. **Redis Cluster**: Set up Redis cluster for high availability
2. **Separate Instances**: Use separate Redis instances for cache and sessions

### Vertical Scaling

#### Resource Optimization

Update Docker Compose resource limits:

```yaml
services:
  web:
    # ... other configuration
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  celery:
    # ... other configuration
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
```

## Troubleshooting

### Common Deployment Issues

#### Docker Issues

**Problem**: Container fails to start
```bash
# Check container logs
docker-compose -f docker-compose.prod.yml logs web

# Check container status
docker-compose -f docker-compose.prod.yml ps

# Restart specific service
docker-compose -f docker-compose.prod.yml restart web
```

#### Database Issues

**Problem**: Database connection errors
```bash
# Check database status
docker-compose -f docker-compose.prod.yml logs db

# Connect to database
docker-compose -f docker-compose.prod.yml exec db psql -U neurorides neurorides_prod

# Check database size
docker-compose -f docker-compose.prod.yml exec db psql -U neurorides -d neurorides_prod -c "SELECT pg_size_pretty(pg_database_size('neurorides_prod'));"
```

#### SSL Issues

**Problem**: SSL certificate errors
```bash
# Check certificate validity
openssl x509 -in /etc/nginx/ssl/fullchain.pem -text -noout

# Test SSL configuration
nginx -t

# Renew Let's Encrypt certificate
sudo certbot renew --force-renewal
```

#### Performance Issues

**Problem**: Slow response times
```bash
# Check system resources
htop
df -h
free -h

# Check application metrics
curl http://localhost/metrics/

# Check database performance
docker-compose -f docker-compose.prod.yml exec db psql -U neurorides -d neurorides_prod -c "SELECT * FROM pg_stat_activity;"
```

### Monitoring and Alerting

#### Health Check Script

Create `scripts/health_check.sh`:

```bash
#!/bin/bash

# Configuration
HEALTH_URL="http://localhost/health/"
ALERT_EMAIL="admin@neurorides.com"

# Check application health
if ! curl -f "$HEALTH_URL" > /dev/null 2>&1; then
    echo "Health check failed for $HEALTH_URL" | mail -s "NeuroRides Health Check Failed" "$ALERT_EMAIL"
    exit 1
fi

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "Disk usage is at ${DISK_USAGE}%" | mail -s "NeuroRides Disk Space Alert" "$ALERT_EMAIL"
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEMORY_USAGE" -gt 90 ]; then
    echo "Memory usage is at ${MEMORY_USAGE}%" | mail -s "NeuroRides Memory Alert" "$ALERT_EMAIL"
fi

echo "Health check passed"
```

#### Log Monitoring

Create `scripts/monitor_logs.sh`:

```bash
#!/bin/bash

# Monitor error logs
ERROR_COUNT=$(docker-compose -f docker-compose.prod.yml logs --since=1h web | grep -c "ERROR")

if [ "$ERROR_COUNT" -gt 10 ]; then
    echo "High error count detected: $ERROR_COUNT errors in the last hour" | mail -s "NeuroRides Error Alert" admin@neurorides.com
fi
```

### Recovery Procedures

#### Service Recovery

```bash
# Full service restart
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Database recovery
docker-compose -f docker-compose.prod.yml exec db pg_ctl restart

# Clear Redis cache
docker-compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL
```

#### Emergency Procedures

1. **Service Outage**: Follow the rollback procedure
2. **Data Corruption**: Restore from latest backup
3. **Security Breach**: Immediately change all secrets and passwords
4. **Performance Issues**: Scale up resources or enable maintenance mode

---

This deployment guide provides comprehensive instructions for deploying the NeuroRides platform in various environments. Always test deployments in staging before applying to production.