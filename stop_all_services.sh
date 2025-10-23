#!/bin/bash

# NeuroRides Platform Stop Script
# This script stops all running services

echo "🛑 Stopping NeuroRides Platform Services"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file="${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "Stopping $service_name (PID: $pid)..."
            kill $pid
            sleep 2
            
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${RED}Force killing $service_name...${NC}"
                kill -9 $pid
            fi
            
            echo -e "${GREEN}✅ $service_name stopped${NC}"
        else
            echo -e "${RED}❌ $service_name (PID: $pid) not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${RED}❌ No PID file found for $service_name${NC}"
    fi
}

# Stop all services
stop_service "frontend"
stop_service "django"
stop_service "celery"
stop_service "redis"

# Also kill any remaining processes on our ports
echo ""
echo "🔍 Checking for remaining processes on ports..."

# Kill processes on specific ports
for port in 3000 8000 6379; do
    pid=$(lsof -ti:$port)
    if [ ! -z "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
done

echo ""
echo -e "${GREEN}🎉 All services stopped!${NC}"
echo ""
echo "📋 Log files are preserved in the logs/ directory"
echo "🚀 To start services again, run: ./start_all_services.sh"