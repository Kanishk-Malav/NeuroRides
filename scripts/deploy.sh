#!/bin/bash
set -e

# NeuroRides Deployment Script
# This script handles the deployment of the NeuroRides application

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.yml"
COMPOSE_OVERRIDE=""

# Set compose override based on environment
case $ENVIRONMENT in
    "production")
        COMPOSE_OVERRIDE="-f docker-compose.prod.yml"
        ;;
    "staging")
        COMPOSE_OVERRIDE="-f docker-compose.staging.yml"
        ;;
    "development")
        COMPOSE_OVERRIDE=""
        ;;
    *)
        echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'. Use: production, staging, or development${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}🚀 Starting NeuroRides deployment for $ENVIRONMENT environment${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install it and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please update the .env file with your configuration before continuing."
        echo -e "${YELLOW}Press Enter to continue after updating .env file...${NC}"
        read
    else
        print_error ".env.example file not found. Please create a .env file with your configuration."
        exit 1
    fi
fi

# Validate required environment variables
print_status "Validating environment configuration..."
source .env

required_vars=("SECRET_KEY" "DB_PASSWORD" "REDIS_PASSWORD")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        print_error "Required environment variable $var is not set in .env file"
        exit 1
    fi
done

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p docker/ssl
mkdir -p docker/nginx-logs

# Pull latest images
print_status "Pulling latest Docker images..."
docker-compose $COMPOSE_OVERRIDE pull

# Build application image
print_status "Building application image..."
docker-compose $COMPOSE_OVERRIDE build --no-cache

# Stop existing containers
print_status "Stopping existing containers..."
docker-compose $COMPOSE_OVERRIDE down

# Start database and Redis first
print_status "Starting database and Redis..."
docker-compose $COMPOSE_OVERRIDE up -d db redis

# Wait for database to be ready
print_status "Waiting for database to be ready..."
timeout=60
counter=0
while ! docker-compose $COMPOSE_OVERRIDE exec -T db pg_isready -U neurorides -d neurorides > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        print_error "Database failed to start within $timeout seconds"
        exit 1
    fi
    sleep 1
    counter=$((counter + 1))
done

# Wait for Redis to be ready
print_status "Waiting for Redis to be ready..."
counter=0
while ! docker-compose $COMPOSE_OVERRIDE exec -T redis redis-cli ping > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        print_error "Redis failed to start within $timeout seconds"
        exit 1
    fi
    sleep 1
    counter=$((counter + 1))
done

# Run database migrations
print_status "Running database migrations..."
docker-compose $COMPOSE_OVERRIDE run --rm web python manage.py migrate

# Collect static files
print_status "Collecting static files..."
docker-compose $COMPOSE_OVERRIDE run --rm web python manage.py collectstatic --noinput

# Create superuser if in development
if [ "$ENVIRONMENT" = "development" ]; then
    print_status "Creating superuser for development..."
    docker-compose $COMPOSE_OVERRIDE run --rm web python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@neurorides.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"
fi

# Start all services
print_status "Starting all services..."
docker-compose $COMPOSE_OVERRIDE up -d

# Wait for web service to be ready
print_status "Waiting for web service to be ready..."
counter=0
while ! curl -f http://localhost:8000/health/ > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        print_error "Web service failed to start within $timeout seconds"
        docker-compose $COMPOSE_OVERRIDE logs web
        exit 1
    fi
    sleep 2
    counter=$((counter + 2))
done

# Run health checks
print_status "Running health checks..."
health_response=$(curl -s http://localhost:8000/health/detailed/)
if echo "$health_response" | grep -q '"overall_status": "healthy"'; then
    print_status "All health checks passed"
else
    print_warning "Some health checks failed. Check the logs for details."
    echo "$health_response" | jq '.' 2>/dev/null || echo "$health_response"
fi

# Show service status
print_status "Deployment completed! Service status:"
docker-compose $COMPOSE_OVERRIDE ps

echo -e "\n${GREEN}🎉 NeuroRides deployment completed successfully!${NC}"
echo -e "${BLUE}Services:${NC}"
echo -e "  • Web Application: http://localhost"
echo -e "  • Admin Interface: http://localhost/admin/"
echo -e "  • API Documentation: http://localhost/api/schema/"
echo -e "  • Health Check: http://localhost/health/"
echo -e "  • Monitoring Dashboard: http://localhost/monitoring/dashboard/"

if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "  • Flower (Celery Monitor): http://localhost:5555/"
    echo -e "\n${YELLOW}Development credentials:${NC}"
    echo -e "  • Admin: admin / admin123"
    echo -e "  • Flower: admin / flower123"
fi

echo -e "\n${BLUE}Useful commands:${NC}"
echo -e "  • View logs: docker-compose $COMPOSE_OVERRIDE logs -f"
echo -e "  • Stop services: docker-compose $COMPOSE_OVERRIDE down"
echo -e "  • Restart services: docker-compose $COMPOSE_OVERRIDE restart"
echo -e "  • Run management command: docker-compose $COMPOSE_OVERRIDE exec web python manage.py <command>"