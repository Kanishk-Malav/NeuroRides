#!/bin/bash
set -e

# NeuroRides Backup Script
# This script creates backups of the database and media files

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR=${BACKUP_DIR:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-30}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
COMPOSE_FILE="docker-compose.yml"

# Load environment variables
if [ -f .env ]; then
    source .env
fi

DB_NAME=${DB_NAME:-neurorides}
DB_USER=${DB_USER:-neurorides}

echo -e "${BLUE}🔄 Starting NeuroRides backup process${NC}"

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

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    print_error "Docker containers are not running. Please start the application first."
    exit 1
fi

# Database backup
print_status "Creating database backup..."
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges > "$DB_BACKUP_FILE"

if [ $? -eq 0 ]; then
    print_status "Database backup created: $DB_BACKUP_FILE"
    
    # Compress the backup
    gzip "$DB_BACKUP_FILE"
    print_status "Database backup compressed: ${DB_BACKUP_FILE}.gz"
else
    print_error "Database backup failed"
    exit 1
fi

# Media files backup
print_status "Creating media files backup..."
MEDIA_BACKUP_FILE="$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz"

if docker-compose exec web test -d /app/media; then
    docker-compose exec -T web tar -czf - -C /app media > "$MEDIA_BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        print_status "Media files backup created: $MEDIA_BACKUP_FILE"
    else
        print_warning "Media files backup failed or no media files found"
    fi
else
    print_warning "No media directory found, skipping media backup"
fi

# Static files backup (optional)
print_status "Creating static files backup..."
STATIC_BACKUP_FILE="$BACKUP_DIR/static_backup_$TIMESTAMP.tar.gz"

if docker-compose exec web test -d /app/staticfiles; then
    docker-compose exec -T web tar -czf - -C /app staticfiles > "$STATIC_BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        print_status "Static files backup created: $STATIC_BACKUP_FILE"
    else
        print_warning "Static files backup failed"
    fi
fi

# Logs backup
print_status "Creating logs backup..."
LOGS_BACKUP_FILE="$BACKUP_DIR/logs_backup_$TIMESTAMP.tar.gz"

if [ -d "./logs" ] && [ "$(ls -A ./logs)" ]; then
    tar -czf "$LOGS_BACKUP_FILE" -C . logs
    print_status "Logs backup created: $LOGS_BACKUP_FILE"
else
    print_warning "No logs found, skipping logs backup"
fi

# Create backup manifest
MANIFEST_FILE="$BACKUP_DIR/backup_manifest_$TIMESTAMP.txt"
cat > "$MANIFEST_FILE" << EOF
NeuroRides Backup Manifest
Created: $(date)
Timestamp: $TIMESTAMP

Files included in this backup:
- Database: db_backup_$TIMESTAMP.sql.gz
- Media: media_backup_$TIMESTAMP.tar.gz
- Static: static_backup_$TIMESTAMP.tar.gz
- Logs: logs_backup_$TIMESTAMP.tar.gz

Database Info:
- Database Name: $DB_NAME
- Database User: $DB_USER
- Backup Size: $(du -h "${DB_BACKUP_FILE}.gz" 2>/dev/null | cut -f1 || echo "Unknown")

System Info:
- Hostname: $(hostname)
- Docker Compose Version: $(docker-compose --version)
- Backup Script Version: 1.0

Restore Instructions:
1. Stop the application: docker-compose down
2. Restore database: gunzip -c db_backup_$TIMESTAMP.sql.gz | docker-compose exec -T db psql -U $DB_USER -d $DB_NAME
3. Restore media: docker-compose exec -T web tar -xzf - -C /app < media_backup_$TIMESTAMP.tar.gz
4. Start the application: docker-compose up -d
EOF

print_status "Backup manifest created: $MANIFEST_FILE"

# Clean up old backups
if [ "$RETENTION_DAYS" -gt 0 ]; then
    print_status "Cleaning up backups older than $RETENTION_DAYS days..."
    
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.txt" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    print_status "Old backups cleaned up"
fi

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo -e "\n${GREEN}🎉 Backup completed successfully!${NC}"
echo -e "${BLUE}Backup Summary:${NC}"
echo -e "  • Timestamp: $TIMESTAMP"
echo -e "  • Location: $BACKUP_DIR"
echo -e "  • Total Size: $TOTAL_SIZE"
echo -e "  • Retention: $RETENTION_DAYS days"

echo -e "\n${BLUE}Backup Files:${NC}"
ls -la "$BACKUP_DIR"/*"$TIMESTAMP"* 2>/dev/null || echo "  No backup files found"

echo -e "\n${BLUE}Restore Command:${NC}"
echo -e "  ./scripts/restore.sh $TIMESTAMP"