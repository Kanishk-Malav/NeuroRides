#!/bin/bash

# NeuroRides Monitoring Script
# This script provides real-time monitoring of the application

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check service health
check_service_health() {
    local service_name=$1
    local health_url=$2
    
    if curl -f -s "$health_url" > /dev/null 2>&1; then
        print_status "$service_name is healthy"
        return 0
    else
        print_error "$service_name is unhealthy"
        return 1
    fi
}

# Function to get container stats
get_container_stats() {
    local container_name=$1
    
    if docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        stats=$(docker stats "$container_name" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}")
        echo "$stats" | tail -n +2
    else
        echo "Container not running"
    fi
}

# Main monitoring function
monitor_system() {
    clear
    echo -e "${BLUE}🔍 NeuroRides System Monitor${NC}"
    echo -e "${BLUE}================================${NC}"
    echo "Last updated: $(date)"
    echo

    # Check Docker containers
    echo -e "${BLUE}📦 Container Status:${NC}"
    docker-compose ps
    echo

    # Check service health
    echo -e "${BLUE}🏥 Health Checks:${NC}"
    check_service_health "Web Application" "http://localhost:8000/health/"
    check_service_health "Database" "http://localhost:8000/health/detailed/" || true
    check_service_health "Nginx" "http://localhost/health/" || true
    echo

    # Container resource usage
    echo -e "${BLUE}📊 Resource Usage:${NC}"
    echo -e "${YELLOW}Container\t\tCPU\t\tMemory\t\tNetwork\t\tDisk${NC}"
    echo "------------------------------------------------------------------------"
    
    containers=("neurorides_web" "neurorides_db" "neurorides_redis" "neurorides_celery_worker" "neurorides_nginx")
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            stats=$(get_container_stats "$container")
            echo -e "$container\t$stats"
        else
            echo -e "$container\t${RED}Not running${NC}"
        fi
    done
    echo

    # System resources
    echo -e "${BLUE}🖥️  System Resources:${NC}"
    
    # CPU usage
    cpu_usage=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo "N/A")
    echo -e "CPU Usage: $cpu_usage%"
    
    # Memory usage
    if command -v free &> /dev/null; then
        memory_info=$(free -h | grep "Mem:")
        echo -e "Memory: $memory_info"
    elif command -v vm_stat &> /dev/null; then
        # macOS
        memory_pressure=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk '{print $5}' | sed 's/%//' || echo "N/A")
        echo -e "Memory Free: $memory_pressure%"
    fi
    
    # Disk usage
    disk_usage=$(df -h / | tail -1 | awk '{print $5}')
    echo -e "Disk Usage: $disk_usage"
    echo

    # Recent logs
    echo -e "${BLUE}📝 Recent Logs (last 10 lines):${NC}"
    echo -e "${YELLOW}Web Application:${NC}"
    docker-compose logs --tail=5 web 2>/dev/null | tail -5 || echo "No logs available"
    
    echo -e "${YELLOW}Celery Worker:${NC}"
    docker-compose logs --tail=5 celery_worker 2>/dev/null | tail -5 || echo "No logs available"
    echo

    # Application metrics
    echo -e "${BLUE}📈 Application Metrics:${NC}"
    metrics_response=$(curl -s http://localhost:8000/monitoring/metrics/ 2>/dev/null || echo '{"error": "Metrics unavailable"}')
    
    if echo "$metrics_response" | grep -q '"application"'; then
        # Parse and display key metrics
        echo "$metrics_response" | jq -r '
            .application | 
            "Active Users Today: \(.users.active_users_today // "N/A")",
            "Active Rides: \(.rides.active_rides // "N/A")",
            "Active Vehicles: \(.fleet.active_vehicles // "N/A")",
            "Fleet Utilization: \(.fleet.utilization_rate // "N/A")%",
            "Payment Success Rate: \(.payments.success_rate // "N/A")%"
        ' 2>/dev/null || echo "Metrics parsing failed"
    else
        echo "Application metrics unavailable"
    fi
    echo

    # Queue status
    echo -e "${BLUE}🔄 Queue Status:${NC}"
    if docker ps --format "{{.Names}}" | grep -q "neurorides_celery_worker"; then
        queue_info=$(docker-compose exec -T celery_worker celery -A neurorides inspect active 2>/dev/null || echo "Queue info unavailable")
        if echo "$queue_info" | grep -q "OK"; then
            active_tasks=$(echo "$queue_info" | grep -c "uuid" 2>/dev/null || echo "0")
            echo "Active tasks: $active_tasks"
        else
            echo "Queue status unavailable"
        fi
    else
        print_error "Celery worker not running"
    fi
}

# Function for continuous monitoring
continuous_monitor() {
    while true; do
        monitor_system
        echo -e "\n${BLUE}Press Ctrl+C to exit. Refreshing in 30 seconds...${NC}"
        sleep 30
    done
}

# Function to show help
show_help() {
    echo -e "${BLUE}NeuroRides Monitoring Script${NC}"
    echo
    echo "Usage: $0 [option]"
    echo
    echo "Options:"
    echo "  -c, --continuous    Continuous monitoring (refreshes every 30 seconds)"
    echo "  -h, --help         Show this help message"
    echo "  -s, --status       Show current status (default)"
    echo "  -l, --logs         Show recent logs"
    echo "  -m, --metrics      Show application metrics"
    echo
    echo "Examples:"
    echo "  $0                 # Show current status"
    echo "  $0 --continuous    # Continuous monitoring"
    echo "  $0 --logs          # Show recent logs"
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}📝 Recent Application Logs${NC}"
    echo -e "${BLUE}=========================${NC}"
    
    services=("web" "celery_worker" "celery_beat" "db" "redis")
    
    for service in "${services[@]}"; do
        echo -e "\n${YELLOW}$service logs:${NC}"
        docker-compose logs --tail=10 "$service" 2>/dev/null || echo "No logs available for $service"
    done
}

# Function to show detailed metrics
show_metrics() {
    echo -e "${BLUE}📈 Detailed Application Metrics${NC}"
    echo -e "${BLUE}===============================${NC}"
    
    metrics_response=$(curl -s http://localhost:8000/monitoring/metrics/ 2>/dev/null)
    
    if [ $? -eq 0 ] && echo "$metrics_response" | grep -q '"system"'; then
        echo "$metrics_response" | jq '.' 2>/dev/null || echo "$metrics_response"
    else
        print_error "Failed to retrieve metrics. Is the application running?"
    fi
}

# Parse command line arguments
case "${1:-}" in
    -c|--continuous)
        continuous_monitor
        ;;
    -h|--help)
        show_help
        ;;
    -l|--logs)
        show_logs
        ;;
    -m|--metrics)
        show_metrics
        ;;
    -s|--status|"")
        monitor_system
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac