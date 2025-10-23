#!/bin/bash
set -e

# NeuroRides Restore Script
# This script restores backups of the database and media files

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR=${BACKUP_DIR:-./backups}
TIMESTAMP=$1

# Load environment variables
if [ -f .env ]; then
    source .env
fi

DB_NAME=${DB_NAME:-neurorides}
DB_USER=${DB_USER:-neurorides}

echo -e "${BLUE}🔄 Starting NeuroRides restore process${NC}"

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

# Check if timestamp is provided
if [ -z "$TIMESTAMP" ]; then
    print_error "Usage: $0 <timestamp>"
    echo -e "${BLUE}Available backups:${NC}"
    ls -la "$BACKUP_DIR"/backup_manifest_*.txt 2>/dev/null | sed 's/.*backup_manifest_\(.*\)\.txt/  \1/' || echo "  No backups found"
    exit 1
fi

# Check if backup files exist
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"
MEDIA_BACKUP_FILE="$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz"
STATIC_BACKUP_FILE="$BACKUP_DIR/static_backup_$TIMESTAMP.tar.gz"
MANIFEST_FILE="$BACKUP_DIR/backup_manifest_$TIMESTAMP.txt"

if [ ! -f "$DB_BACKUP_FILE" ]; then
    print_error "Database backup file not found: $DB_BACKUP_FILE"
    exit 1
fi

if [ ! -f "$MANIFEST_FILE" ]; then
    print_warning "Backup manifest not found: $MANIFEST_FILE"
else
    print_status "Found backup manifest: $MANIFEST_FILE"
    echo -e "${BLUE}Backup Details:${NC}"
    cat "$MANIFEST_FILE"
    echo
fi

# Confirmation prompt
echo -e "${YELLOW}⚠ WARNING: This will overwrite the current database and media files!${NC}"
echo -e "${YELLOW}⚠ Make sure you have a current backup before proceeding.${NC}"
echo -e "${BLUE}Do you want to continue? (yes/no):${NC}"
read -r confirmation

if [ "$confirmation" != "yes" ]; then
    print_status "Restore cancelled by user"
    exit 0
fi

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    print_warning "Docker containers are not running. Starting them..."
    docker-compose up -d db redis
    
    # Wait for database to be ready
    print_status "Waiting for database to be ready..."
    timeout=60
    counter=0
    while ! docker-compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
        if [ $counter -ge $timeout ]; then
            print_error "Database failed to start within $timeout seconds"
            exit 1
        fi
        sleep 1
        counter=$((counter + 1))
    done
fi

# Stop web services during restore
print_status "Stopping web services..."
docker-compose stop web celery_worker celery_beat nginx flower 2>/dev/null || true

# Restore database
print_status "Restoring database from $DB_BACKUP_FILE..."

# Drop existing connections
docker-compose exec -T db psql -U "$DB_USER" -d postgres -c "
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" > /dev/null 2>&1 || true

# Drop and recreate database
docker-compose exec -T db psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" > /dev/null
docker-compose exec -T db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;" > /dev/null

# Restore database from backup
gunzip -c "$DB_BACKUP_FILE" | docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" > /dev/null

if [ $? -eq 0 ]; then
    print_status "Database restored successfully"
else
    print_error "Database restore failed"
    exit 1
fi

# Restore media files
if [ -f "$MEDIA_BACKUP_FILE" ]; then
    print_status "Restoring media files from $MEDIA_BACKUP_FILE..."
    
    # Remove existing media files
    docker-compose run --rm web rm -rf /app/media/* 2>/dev/null || true
    
    # Restore media files
    docker-compose run --rm -T web tar -xzf - -C /app < "$MEDIA_BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        print_status "Media files restored successfully"
    else
        print_warning "Media files restore failed"
    fi
else
    print_warning "Media backup file not found, skipping media restore"
fi

# Restore static files (optional)
if [ -f "$STATIC_BACKUP_FILE" ]; then
    print_status "Restoring static files from $STATIC_BACKUP_FILE..."
    
    # Remove existing static files
    docker-compose run --rm web rm -rf /app/staticfiles/* 2>/dev/null || true
    
    # Restore static files
    docker-compose run --rm -T web tar -xzf - -C /app < "$STATIC_BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        print_status "Static files restored successfully"
    else
        print_warning "Static files restore failed, will regenerate"
        # Regenerate static files
        docker-compose run --rm web python manage.py collectstatic --noinput
    fi
else
    print_warning "Static backup file not found, regenerating static files"
    docker-compose run --rm web python manage.py collectstatic --noinput
fi

# Run migrations to ensure database is up to date
print_status "Running database migrations..."
docker-compose run --rm web python manage.py migrate

# Start all services
print_status "Starting all services..."
docker-compose up -d

# Wait for web service to be ready
print_status "Waiting for web service to be ready..."
timeout=60
counter=0
while ! curl -f http://localhost:8000/health/ > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        print_error "Web service failed to start within $timeout seconds"
        docker-compose logs web
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

echo -e "\n${GREEN}🎉 Restore completed successfully!${NC}"
echo -e "${BLUE}Restored from backup:${NC}"
echo -e "  • Timestamp: $TIMESTAMP"
echo -e "  • Database: $DB_BACKUP_FILE"
echo -e "  • Media: $MEDIA_BACKUP_FILE"
echo -e "  • Static: $STATIC_BACKUP_FILE"

echo -e "\n${BLUE}Services Status:${NC}"
docker-compose ps

echo -e "\n${BLUE}Next Steps:${NC}"
echo -e "  • Verify application functionality: http://localhost"
echo -e "  • Check admin interface: http://localhost/admin/"
echo -e "  • Review logs: docker-compose logs -f"