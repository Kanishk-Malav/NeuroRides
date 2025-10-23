#!/bin/bash

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COVERAGE_MIN=80
REPORT_DIR="$PROJECT_DIR/test_reports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Help function
show_help() {
    cat << EOF
NeuroRides Test Runner

Usage: $0 [OPTIONS] [TEST_TYPE]

TEST_TYPES:
    all                 Run all tests (default)
    unit               Run unit tests only
    integration        Run integration tests only
    api                Run API tests only
    security           Run security tests only
    performance        Run performance tests only
    deployment         Run deployment tests only
    load               Run load tests only
    coverage           Run tests with coverage report

OPTIONS:
    -h, --help         Show this help message
    -v, --verbose      Verbose output
    -f, --failfast     Stop on first failure
    -k, --keepdb       Keep test database
    -p, --parallel     Run tests in parallel
    --no-migrations    Skip migrations during tests
    --coverage-min N   Minimum coverage percentage (default: $COVERAGE_MIN)
    --report-dir DIR   Test report directory (default: $REPORT_DIR)

Examples:
    $0                 # Run all tests
    $0 unit            # Run unit tests only
    $0 coverage        # Run tests with coverage
    $0 -v -f api       # Run API tests with verbose output, stop on first failure
    $0 --parallel integration  # Run integration tests in parallel

EOF
}

# Parse command line arguments
VERBOSE=""
FAILFAST=""
KEEPDB=""
PARALLEL=""
NO_MIGRATIONS=""
TEST_TYPE="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="--verbosity=2"
            shift
            ;;
        -f|--failfast)
            FAILFAST="--failfast"
            shift
            ;;
        -k|--keepdb)
            KEEPDB="--keepdb"
            shift
            ;;
        -p|--parallel)
            PARALLEL="--parallel"
            shift
            ;;
        --no-migrations)
            NO_MIGRATIONS="--nomigrations"
            shift
            ;;
        --coverage-min)
            COVERAGE_MIN="$2"
            shift 2
            ;;
        --report-dir)
            REPORT_DIR="$2"
            shift 2
            ;;
        all|unit|integration|api|security|performance|deployment|load|coverage)
            TEST_TYPE="$1"
            shift
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Setup
cd "$PROJECT_DIR"
mkdir -p "$REPORT_DIR"

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    warn "Virtual environment not detected. Attempting to activate..."
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        log "Activated virtual environment"
    else
        warn "No virtual environment found. Proceeding with system Python..."
    fi
fi

# Check dependencies
log "Checking test dependencies..."
python -c "import coverage, django" 2>/dev/null || {
    error "Missing test dependencies. Install with: pip install coverage django"
    exit 1
}

# Set Django settings
export DJANGO_SETTINGS_MODULE="neurorides.settings"

# Function to run Django tests
run_django_tests() {
    local test_path="$1"
    local extra_args="$2"
    
    log "Running Django tests: $test_path"
    
    python manage.py test $test_path \
        $VERBOSE \
        $FAILFAST \
        $KEEPDB \
        $PARALLEL \
        $NO_MIGRATIONS \
        $extra_args
}

# Function to run tests with coverage
run_with_coverage() {
    local test_path="$1"
    
    log "Running tests with coverage: $test_path"
    
    # Start coverage
    coverage erase
    
    coverage run --source='.' manage.py test $test_path \
        $VERBOSE \
        $FAILFAST \
        $KEEPDB \
        $NO_MIGRATIONS
    
    # Generate coverage report
    log "Generating coverage report..."
    coverage report --show-missing
    coverage html -d "$REPORT_DIR/coverage_html"
    coverage xml -o "$REPORT_DIR/coverage.xml"
    
    # Check coverage threshold
    COVERAGE_PERCENT=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')
    
    if [[ -n "$COVERAGE_PERCENT" ]]; then
        if (( $(echo "$COVERAGE_PERCENT >= $COVERAGE_MIN" | bc -l) )); then
            log "Coverage check passed: ${COVERAGE_PERCENT}% >= ${COVERAGE_MIN}%"
        else
            error "Coverage check failed: ${COVERAGE_PERCENT}% < ${COVERAGE_MIN}%"
            exit 1
        fi
    else
        warn "Could not determine coverage percentage"
    fi
}

# Function to run linting
run_linting() {
    log "Running code quality checks..."
    
    # Python linting
    if command -v flake8 &> /dev/null; then
        log "Running flake8..."
        flake8 . --exclude=venv,migrations --max-line-length=120 --output-file="$REPORT_DIR/flake8.txt" || warn "Flake8 found issues"
    fi
    
    if command -v black &> /dev/null; then
        log "Checking code formatting with black..."
        black --check --diff . --exclude="/(venv|migrations)/" || warn "Black formatting issues found"
    fi
    
    if command -v isort &> /dev/null; then
        log "Checking import sorting with isort..."
        isort --check-only --diff . || warn "Import sorting issues found"
    fi
}

# Function to run security checks
run_security_checks() {
    log "Running security checks..."
    
    # Django security check
    python manage.py check --deploy || warn "Django security check found issues"
    
    # Safety check for known vulnerabilities
    if command -v safety &> /dev/null; then
        log "Running safety check..."
        safety check --output text --file requirements.txt > "$REPORT_DIR/safety.txt" || warn "Safety check found vulnerabilities"
    fi
    
    # Bandit security linter
    if command -v bandit &> /dev/null; then
        log "Running bandit security scan..."
        bandit -r . -x venv,tests -f json -o "$REPORT_DIR/bandit.json" || warn "Bandit found security issues"
    fi
}

# Function to check database
check_database() {
    log "Checking database connection..."
    
    python manage.py check --database default || {
        error "Database check failed"
        exit 1
    }
    
    log "Running migration check..."
    python manage.py makemigrations --check --dry-run || {
        error "Migrations are not up to date"
        exit 1
    }
}

# Function to run performance tests
run_performance_tests() {
    log "Running performance tests..."
    
    # Set performance test settings
    export DJANGO_SETTINGS_MODULE="neurorides.settings.test_performance"
    
    python -c "
import os
import django
from django.conf import settings
from django.test.utils import get_runner

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neurorides.settings')
django.setup()

from tests.test_comprehensive import run_performance_tests
success = run_performance_tests()
exit(0 if success else 1)
"
}

# Function to run load tests
run_load_tests() {
    log "Running load tests..."
    
    python -c "
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neurorides.settings')
django.setup()

from tests.test_deployment import run_load_tests
success = run_load_tests()
exit(0 if success else 1)
"
}

# Main execution
log "Starting NeuroRides test suite..."
log "Test type: $TEST_TYPE"
log "Report directory: $REPORT_DIR"

# Pre-test checks
check_database

case $TEST_TYPE in
    "all")
        log "Running all tests..."
        run_linting
        run_security_checks
        run_django_tests "" ""
        run_performance_tests
        log "All tests completed successfully!"
        ;;
    
    "unit")
        log "Running unit tests..."
        run_django_tests "accounts.tests rides.tests fleet.tests dispatch.tests payments.tests analytics.tests realtime.tests" ""
        ;;
    
    "integration")
        log "Running integration tests..."
        run_django_tests "tests.test_comprehensive.EndToEndRideWorkflowTest tests.test_comprehensive.IntegrationWithExternalServicesTest" ""
        ;;
    
    "api")
        log "Running API tests..."
        run_django_tests "tests.test_api" ""
        ;;
    
    "security")
        log "Running security tests..."
        run_security_checks
        run_django_tests "tests.test_comprehensive.SecurityAndPermissionsTest" ""
        ;;
    
    "performance")
        log "Running performance tests..."
        run_performance_tests
        ;;
    
    "deployment")
        log "Running deployment tests..."
        run_django_tests "tests.test_deployment" ""
        ;;
    
    "load")
        log "Running load tests..."
        run_load_tests
        ;;
    
    "coverage")
        log "Running tests with coverage..."
        run_with_coverage ""
        ;;
    
    *)
        error "Unknown test type: $TEST_TYPE"
        show_help
        exit 1
        ;;
esac

# Generate test summary
log "Generating test summary..."
cat > "$REPORT_DIR/test_summary.txt" << EOF
NeuroRides Test Summary
======================
Date: $(date)
Test Type: $TEST_TYPE
Project Directory: $PROJECT_DIR
Report Directory: $REPORT_DIR

Test Results:
- Django Tests: $(if [[ -f "$REPORT_DIR/django_tests.log" ]]; then echo "Available"; else echo "Not run"; fi)
- Coverage Report: $(if [[ -f "$REPORT_DIR/coverage.xml" ]]; then echo "Available"; else echo "Not run"; fi)
- Security Scan: $(if [[ -f "$REPORT_DIR/bandit.json" ]]; then echo "Available"; else echo "Not run"; fi)
- Code Quality: $(if [[ -f "$REPORT_DIR/flake8.txt" ]]; then echo "Available"; else echo "Not run"; fi)

Reports Location: $REPORT_DIR
EOF

log "Test summary saved to: $REPORT_DIR/test_summary.txt"
log "Test execution completed successfully!"

# Open coverage report if available
if [[ -f "$REPORT_DIR/coverage_html/index.html" ]] && command -v open &> /dev/null; then
    info "Opening coverage report..."
    open "$REPORT_DIR/coverage_html/index.html"
fi