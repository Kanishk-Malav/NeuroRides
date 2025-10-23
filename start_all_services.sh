#!/bin/bash

# NeuroRides Platform Startup Script
# This script helps you start all services for development

echo "🚀 Starting NeuroRides Platform Services"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to start a service in background
start_service() {
    local service_name=$1
    local command=$2
    local port=$3
    local log_file=$4
    
    echo -e "${BLUE}Starting $service_name...${NC}"
    
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use. $service_name might already be running.${NC}"
    else
        echo "Running: $command"
        nohup $command > $log_file 2>&1 &
        local pid=$!
        echo $pid > "${service_name}.pid"
        echo -e "${GREEN}✅ $service_name started (PID: $pid, Port: $port)${NC}"
        echo "   Log file: $log_file"
    fi
    echo ""
}

# Create logs directory
mkdir -p logs

echo "📋 Service Overview:"
echo "   Backend (Django):  http://localhost:8000"
echo "   Frontend (React):  http://localhost:3000"
echo "   Database:          SQLite (db.sqlite3)"
echo "   Redis (optional):  redis://localhost:6379"
echo ""

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: manage.py not found. Please run this script from the NeuroRides directory."
    exit 1
fi

# Start Redis (optional but recommended)
echo -e "${BLUE}Checking Redis...${NC}"
if command -v redis-server &> /dev/null; then
    if ! check_port 6379; then
        echo "Starting Redis server..."
        start_service "redis" "redis-server" 6379 "logs/redis.log"
    else
        echo -e "${YELLOW}⚠️  Redis is already running on port 6379${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  Redis not installed. Background tasks won't work. Install with: brew install redis${NC}"
    echo ""
fi

# Start Django Backend
start_service "django" "python manage.py runserver 8000" 8000 "logs/django.log"

# Wait a moment for Django to start
sleep 3

# Start Frontend
if [ -d "frontend" ]; then
    cd frontend
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "${BLUE}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    cd ..
    start_service "frontend" "cd frontend && npm start" 3000 "logs/frontend.log"
else
    echo -e "${YELLOW}⚠️  Frontend directory not found. Skipping frontend startup.${NC}"
    echo ""
fi

# Optional: Start Celery Worker (if Redis is available)
if check_port 6379; then
    start_service "celery" "celery -A neurorides worker -l info" 0 "logs/celery.log"
fi

echo "🎉 All services started!"
echo ""
echo "📱 Access Points:"
echo "   🌐 Frontend:    http://localhost:3000"
echo "   🔧 Backend:     http://localhost:8000"
echo "   👨‍💼 Admin Panel: http://localhost:8000/admin"
echo "   ❤️  Health:     http://localhost:8000/health"
echo ""
echo "🔑 Default Login (admin panel):"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "📊 To stop all services, run: ./stop_all_services.sh"
echo "📋 To view logs: tail -f logs/[service].log"
echo ""
echo "⏳ Services are starting up... Please wait 30-60 seconds for everything to be ready."