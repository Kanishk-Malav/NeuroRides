# NeuroRides Testing Guide

## Overview

This guide covers the comprehensive testing strategy for the NeuroRides platform, including unit tests, integration tests, API tests, security tests, and deployment tests.

## Table of Contents

1. [Testing Strategy](#testing-strategy)
2. [Test Types](#test-types)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Continuous Integration](#continuous-integration)
6. [Performance Testing](#performance-testing)
7. [Security Testing](#security-testing)
8. [Deployment Testing](#deployment-testing)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Testing Strategy

The NeuroRides platform follows a comprehensive testing strategy that includes:

- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test component interactions and workflows
- **API Tests**: Test REST API endpoints and responses
- **Security Tests**: Test authentication, authorization, and security measures
- **Performance Tests**: Test system performance and scalability
- **Deployment Tests**: Test deployment configuration and infrastructure

### Testing Pyramid

```
    /\
   /  \     E2E Tests (Few)
  /____\
 /      \   Integration Tests (Some)
/__________\ Unit Tests (Many)
```

## Test Types

### Unit Tests

Unit tests focus on testing individual components in isolation:

```python
# Example: Testing a model method
class RideModelTest(TestCase):
    def test_fare_calculation(self):
        ride = Ride.objects.create(
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            distance_km=5.2
        )
        
        expected_fare = ride.calculate_fare()
        self.assertGreater(expected_fare, 0)
        self.assertIsInstance(expected_fare, Decimal)
```

**Location**: Individual app `tests.py` files
- `accounts/tests.py`
- `rides/tests.py`
- `fleet/tests.py`
- `dispatch/tests.py`
- `payments/tests.py`
- `analytics/tests.py`
- `realtime/tests.py`

### Integration Tests

Integration tests verify that different components work together:

```python
# Example: Testing complete ride workflow
class RideWorkflowIntegrationTest(APITestCase):
    def test_complete_ride_lifecycle(self):
        # 1. Create ride request
        # 2. Dispatch vehicle
        # 3. Update ride status
        # 4. Process payment
        # 5. Verify analytics
        pass
```

**Location**: `tests/test_comprehensive.py`

### API Tests

API tests verify REST endpoint functionality:

```python
# Example: Testing ride creation API
class RidesAPITest(APITestCase):
    def test_create_ride(self):
        self.client.force_authenticate(user=self.rider)
        
        ride_data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094
        }
        
        response = self.client.post('/api/rides/', ride_data)
        self.assertEqual(response.status_code, 201)
```

**Location**: `tests/test_api.py`

### Security Tests

Security tests verify authentication, authorization, and data protection:

```python
# Example: Testing role-based access control
class SecurityTest(APITestCase):
    def test_rider_cannot_access_fleet_endpoints(self):
        self.client.force_authenticate(user=self.rider)
        response = self.client.get('/api/fleet/vehicles/')
        self.assertEqual(response.status_code, 403)
```

**Location**: `tests/test_comprehensive.py` (SecurityAndPermissionsTest)

### Performance Tests

Performance tests verify system performance under load:

```python
# Example: Testing API response times
class PerformanceTest(APITestCase):
    def test_api_response_times(self):
        start_time = time.time()
        response = self.client.get('/api/rides/')
        duration = (time.time() - start_time) * 1000
        
        self.assertLess(duration, 1000)  # Should respond within 1 second
```

**Location**: `tests/test_comprehensive.py` (PerformanceAndScalabilityTest)

### Deployment Tests

Deployment tests verify infrastructure and configuration:

```python
# Example: Testing Docker configuration
class DockerDeploymentTest(TestCase):
    def test_docker_compose_configuration(self):
        compose_file = os.path.join(settings.BASE_DIR, 'docker-compose.yml')
        self.assertTrue(os.path.exists(compose_file))
```

**Location**: `tests/test_deployment.py`

## Running Tests

### Using Django Test Runner

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts

# Run specific test class
python manage.py test accounts.tests.UserModelTest

# Run specific test method
python manage.py test accounts.tests.UserModelTest.test_user_creation

# Run with verbose output
python manage.py test --verbosity=2

# Run in parallel
python manage.py test --parallel

# Keep test database
python manage.py test --keepdb
```

### Using Test Runner Script

The project includes a comprehensive test runner script:

```bash
# Run all tests
./scripts/run_tests.sh

# Run specific test types
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh api
./scripts/run_tests.sh security
./scripts/run_tests.sh performance
./scripts/run_tests.sh deployment

# Run with coverage
./scripts/run_tests.sh coverage

# Run with options
./scripts/run_tests.sh -v -f unit  # Verbose, fail fast
./scripts/run_tests.sh --parallel integration
```

### Test Runner Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output |
| `-f, --failfast` | Stop on first failure |
| `-k, --keepdb` | Keep test database |
| `-p, --parallel` | Run tests in parallel |
| `--no-migrations` | Skip migrations during tests |
| `--coverage-min N` | Minimum coverage percentage |
| `--report-dir DIR` | Test report directory |

## Test Coverage

### Measuring Coverage

```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run --source='.' manage.py test

# Generate coverage report
coverage report --show-missing

# Generate HTML coverage report
coverage html

# Generate XML coverage report (for CI)
coverage xml
```

### Coverage Targets

| Component | Target Coverage |
|-----------|----------------|
| Models | 95%+ |
| Views/APIs | 90%+ |
| Services | 90%+ |
| Utilities | 85%+ |
| Overall | 80%+ |

### Coverage Configuration

Create `.coveragerc` file:

```ini
[run]
source = .
omit = 
    */venv/*
    */migrations/*
    */tests/*
    manage.py
    */settings/*
    */wsgi.py
    */asgi.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class .*\(Protocol\):
    @(abc\.)?abstractmethod

[html]
directory = test_reports/coverage_html
```

## Continuous Integration

### GitHub Actions Workflow

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgis/postgis:14-3.2
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: neurorides_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y gdal-bin libgdal-dev
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install coverage
    
    - name: Set up environment
      run: |
        cp .env.example .env.test
        echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/neurorides_test" >> .env.test
        echo "REDIS_URL=redis://localhost:6379/0" >> .env.test
    
    - name: Run migrations
      run: python manage.py migrate
      env:
        DJANGO_SETTINGS_MODULE: neurorides.settings.test
    
    - name: Run tests with coverage
      run: |
        coverage run --source='.' manage.py test
        coverage xml
      env:
        DJANGO_SETTINGS_MODULE: neurorides.settings.test
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Run security checks
      run: |
        python manage.py check --deploy
        pip install safety bandit
        safety check
        bandit -r . -x venv,tests
      env:
        DJANGO_SETTINGS_MODULE: neurorides.settings.test
```

### Pre-commit Hooks

Install pre-commit hooks to run tests before commits:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: django-tests
        name: Django Tests
        entry: python manage.py test --failfast
        language: system
        pass_filenames: false
        always_run: true
EOF

# Install hooks
pre-commit install
```

## Performance Testing

### Load Testing with Locust

Create `locustfile.py`:

```python
from locust import HttpUser, task, between
import json

class NeuroRidesUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login
        response = self.client.post("/api/accounts/login/", json={
            "username": "testuser",
            "password": "testpass123"
        })
        
        if response.status_code == 200:
            self.token = response.json()["token"]
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
    
    @task(3)
    def view_rides(self):
        self.client.get("/api/rides/")
    
    @task(1)
    def create_ride(self):
        self.client.post("/api/rides/", json={
            "pickup_latitude": 37.7749,
            "pickup_longitude": -122.4194,
            "pickup_address": "123 Test St",
            "destination_latitude": 37.7849,
            "destination_longitude": -122.4094,
            "destination_address": "456 Test Ave",
            "ride_type": "standard"
        })
    
    @task(2)
    def health_check(self):
        self.client.get("/health/")
```

Run load tests:

```bash
# Install locust
pip install locust

# Run load test
locust -f locustfile.py --host=http://localhost:8000

# Run headless load test
locust -f locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 2 --run-time 1m --headless
```

### Database Performance Testing

```python
class DatabasePerformanceTest(TestCase):
    def test_ride_query_performance(self):
        # Create test data
        for i in range(1000):
            Ride.objects.create(
                rider=self.rider,
                pickup_latitude=37.7749 + (i * 0.001),
                pickup_longitude=-122.4194,
                destination_latitude=37.7849,
                destination_longitude=-122.4094,
                status='completed'
            )
        
        # Test query performance
        start_time = time.time()
        rides = list(Ride.objects.filter(status='completed')[:20])
        duration = time.time() - start_time
        
        self.assertLess(duration, 0.1)  # Should complete within 100ms
        self.assertEqual(len(rides), 20)
```

## Security Testing

### Authentication Testing

```python
class AuthenticationSecurityTest(APITestCase):
    def test_jwt_token_expiration(self):
        # Test that expired tokens are rejected
        pass
    
    def test_password_strength_requirements(self):
        # Test password validation
        weak_passwords = ['123', 'password', 'abc123']
        for password in weak_passwords:
            response = self.client.post('/api/accounts/register/', {
                'username': 'testuser',
                'password': password,
                'email': 'test@example.com'
            })
            self.assertEqual(response.status_code, 400)
    
    def test_rate_limiting(self):
        # Test that rate limiting works
        for i in range(100):
            response = self.client.post('/api/accounts/login/', {
                'username': 'invalid',
                'password': 'invalid'
            })
            if response.status_code == 429:
                break
        else:
            self.fail("Rate limiting not triggered")
```

### Input Validation Testing

```python
class InputValidationTest(APITestCase):
    def test_sql_injection_prevention(self):
        malicious_input = "'; DROP TABLE rides; --"
        response = self.client.post('/api/rides/', {
            'pickup_address': malicious_input,
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094
        })
        
        # Should either reject or sanitize
        self.assertIn(response.status_code, [400, 201])
        
        if response.status_code == 201:
            ride = Ride.objects.get(id=response.data['id'])
            self.assertNotIn('DROP TABLE', ride.pickup_address)
```

### OWASP Security Testing

Use tools like:

- **Bandit**: Static security analysis for Python
- **Safety**: Check for known security vulnerabilities
- **OWASP ZAP**: Web application security scanner

```bash
# Install security tools
pip install bandit safety

# Run security scans
bandit -r . -x venv,tests
safety check
```

## Deployment Testing

### Infrastructure Testing

```python
class InfrastructureTest(TestCase):
    def test_database_connection(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
    
    def test_redis_connection(self):
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 30)
        value = cache.get('test_key')
        self.assertEqual(value, 'test_value')
    
    def test_static_files_collection(self):
        from django.core.management import call_command
        call_command('collectstatic', '--noinput', '--dry-run')
```

### Configuration Testing

```python
class ConfigurationTest(TestCase):
    def test_environment_variables(self):
        required_vars = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
        for var in required_vars:
            self.assertIsNotNone(
                os.environ.get(var) or getattr(settings, var, None),
                f"Required environment variable {var} not set"
            )
    
    def test_security_settings(self):
        if not settings.DEBUG:
            self.assertTrue(settings.SECURE_SSL_REDIRECT)
            self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)
```

## Best Practices

### Test Organization

1. **Group related tests**: Use test classes to group related functionality
2. **Descriptive names**: Use clear, descriptive test method names
3. **One assertion per test**: Focus each test on a single behavior
4. **Setup and teardown**: Use setUp() and tearDown() methods properly

### Test Data Management

```python
class RideTestCase(TestCase):
    def setUp(self):
        """Create common test data."""
        self.rider = User.objects.create_user(
            username='testrider',
            email='rider@test.com',
            password='testpass123',
            role='rider'
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST123',
            make='Tesla',
            model='Model 3',
            status='idle'
        )
    
    def create_ride(self, **kwargs):
        """Helper method to create test rides."""
        defaults = {
            'rider': self.rider,
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'status': 'requested'
        }
        defaults.update(kwargs)
        return Ride.objects.create(**defaults)
```

### Mocking External Services

```python
class PaymentTest(APITestCase):
    @patch('payments.services.PaymentService.process_payment')
    def test_successful_payment(self, mock_payment):
        mock_payment.return_value = {
            'success': True,
            'transaction_id': 'txn_123',
            'status': 'completed'
        }
        
        response = self.client.post('/api/payments/', {
            'ride_id': str(self.ride.id),
            'amount': '25.00',
            'payment_method': 'credit_card'
        })
        
        self.assertEqual(response.status_code, 201)
        mock_payment.assert_called_once()
```

### Test Performance

1. **Use setUpClass**: For expensive setup operations
2. **Database optimization**: Use transactions and fixtures
3. **Parallel execution**: Run tests in parallel when possible
4. **Test isolation**: Ensure tests don't depend on each other

```python
class OptimizedTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Expensive setup operations
        cls.bulk_create_test_data()
    
    @classmethod
    def bulk_create_test_data(cls):
        # Create test data in bulk
        users = [
            User(username=f'user{i}', email=f'user{i}@test.com')
            for i in range(100)
        ]
        User.objects.bulk_create(users)
```

## Troubleshooting

### Common Test Issues

#### Database Issues

```bash
# Reset test database
python manage.py flush --settings=neurorides.settings.test

# Run migrations
python manage.py migrate --settings=neurorides.settings.test

# Check database connection
python manage.py dbshell --settings=neurorides.settings.test
```

#### Test Isolation Issues

```python
# Use transaction rollback
from django.test import TransactionTestCase

class IsolatedTest(TransactionTestCase):
    def test_something(self):
        # Test that requires transaction control
        pass
```

#### Performance Issues

```bash
# Run tests with profiling
python -m cProfile -o profile.stats manage.py test

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

### Debugging Tests

```python
import pdb

class DebugTest(TestCase):
    def test_something(self):
        # Set breakpoint
        pdb.set_trace()
        
        # Your test code
        result = some_function()
        self.assertEqual(result, expected)
```

### Test Environment Issues

```bash
# Check test settings
python manage.py diffsettings --settings=neurorides.settings.test

# Verify test database
python manage.py check --database default --settings=neurorides.settings.test

# Test specific app
python manage.py test accounts --settings=neurorides.settings.test --verbosity=2
```

## Test Reporting

### Generate Test Reports

```bash
# Run tests with XML output
python manage.py test --verbosity=2 > test_results.txt 2>&1

# Generate coverage report
coverage html -d test_reports/coverage

# Generate JUnit XML for CI
pip install django-nose
# Add to settings: TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
python manage.py test --with-xunit --xunit-file=test_reports/junit.xml
```

### Continuous Monitoring

Set up monitoring for:

- Test execution time trends
- Coverage percentage over time
- Test failure rates
- Performance regression detection

---

This testing guide provides comprehensive coverage of testing strategies and practices for the NeuroRides platform. Regular testing ensures code quality, reliability, and maintainability.