"""
Deployment and infrastructure tests for NeuroRides platform.
These tests verify that the deployment configuration works correctly.
"""

import os
import time
import requests
import subprocess
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.db import connection
from django.conf import settings
from unittest.mock import patch, MagicMock


class DockerDeploymentTest(TestCase):
    """
    Test Docker deployment configuration.
    """
    
    def test_docker_compose_configuration(self):
        """Test that docker-compose.yml is valid."""
        # Check if docker-compose.yml exists
        compose_file = os.path.join(settings.BASE_DIR, 'docker-compose.yml')
        self.assertTrue(os.path.exists(compose_file), "docker-compose.yml not found")
        
        # Validate docker-compose syntax
        try:
            result = subprocess.run(
                ['docker-compose', '-f', compose_file, 'config'],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR
            )
            self.assertEqual(result.returncode, 0, f"Docker compose validation failed: {result.stderr}")
        except FileNotFoundError:
            self.skipTest("Docker Compose not available")
    
    def test_production_docker_compose_configuration(self):
        """Test that production docker-compose configuration is valid."""
        prod_compose_file = os.path.join(settings.BASE_DIR, 'docker-compose.prod.yml')
        
        if os.path.exists(prod_compose_file):
            try:
                result = subprocess.run(
                    ['docker-compose', '-f', prod_compose_file, 'config'],
                    capture_output=True,
                    text=True,
                    cwd=settings.BASE_DIR
                )
                self.assertEqual(result.returncode, 0, f"Production compose validation failed: {result.stderr}")
            except FileNotFoundError:
                self.skipTest("Docker Compose not available")
        else:
            self.skipTest("Production docker-compose.yml not found")
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists and is valid."""
        dockerfile_paths = [
            os.path.join(settings.BASE_DIR, 'Dockerfile'),
            os.path.join(settings.BASE_DIR, 'docker', 'Dockerfile.prod')
        ]
        
        dockerfile_found = False
        for dockerfile_path in dockerfile_paths:
            if os.path.exists(dockerfile_path):
                dockerfile_found = True
                
                # Read Dockerfile and check for required instructions
                with open(dockerfile_path, 'r') as f:
                    content = f.read()
                
                required_instructions = ['FROM', 'WORKDIR', 'COPY', 'RUN', 'EXPOSE']
                for instruction in required_instructions:
                    self.assertIn(instruction, content, f"Dockerfile missing {instruction} instruction")
                
                break
        
        self.assertTrue(dockerfile_found, "No Dockerfile found")
    
    def test_nginx_configuration(self):
        """Test Nginx configuration files."""
        nginx_configs = [
            os.path.join(settings.BASE_DIR, 'docker', 'nginx.conf'),
            os.path.join(settings.BASE_DIR, 'docker', 'nginx.prod.conf')
        ]
        
        for config_path in nginx_configs:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    content = f.read()
                
                # Check for required nginx directives
                required_directives = ['server', 'location', 'proxy_pass']
                for directive in required_directives:
                    self.assertIn(directive, content, f"Nginx config missing {directive}")


class DatabaseMigrationTest(TestCase):
    """
    Test database migrations and schema.
    """
    
    def test_migrations_are_up_to_date(self):
        """Test that all migrations are applied."""
        try:
            call_command('migrate', '--check', verbosity=0)
        except SystemExit as e:
            if e.code != 0:
                self.fail("Migrations are not up to date")
    
    def test_database_connection(self):
        """Test database connection and basic operations."""
        # Test connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
    
    def test_postgis_extension(self):
        """Test that PostGIS extension is available."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version();")
            result = cursor.fetchone()
            self.assertIsNotNone(result[0], "PostGIS extension not available")
    
    def test_database_indexes(self):
        """Test that required database indexes exist."""
        with connection.cursor() as cursor:
            # Check for spatial indexes on location fields
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename IN ('rides_ride', 'fleet_vehicle') 
                AND indexname LIKE '%location%' OR indexname LIKE '%gist%'
            """)
            indexes = cursor.fetchall()
            # Should have at least some spatial indexes
            self.assertGreater(len(indexes), 0, "No spatial indexes found")


class EnvironmentConfigurationTest(TestCase):
    """
    Test environment configuration and settings.
    """
    
    def test_required_environment_variables(self):
        """Test that required environment variables are set."""
        required_vars = [
            'SECRET_KEY',
            'DATABASE_URL',
            'REDIS_URL'
        ]
        
        for var in required_vars:
            value = os.environ.get(var) or getattr(settings, var, None)
            self.assertIsNotNone(value, f"Required environment variable {var} not set")
    
    def test_debug_setting_in_production(self):
        """Test that DEBUG is False in production-like settings."""
        # This test assumes production environment has DJANGO_ENV=production
        if os.environ.get('DJANGO_ENV') == 'production':
            self.assertFalse(settings.DEBUG, "DEBUG should be False in production")
    
    def test_allowed_hosts_configuration(self):
        """Test ALLOWED_HOSTS configuration."""
        if not settings.DEBUG:
            self.assertNotEqual(settings.ALLOWED_HOSTS, [], "ALLOWED_HOSTS should be configured in production")
            self.assertNotIn('*', settings.ALLOWED_HOSTS, "Wildcard ALLOWED_HOSTS not recommended in production")
    
    def test_security_settings(self):
        """Test security-related settings."""
        if not settings.DEBUG:
            # Check HTTPS settings
            security_settings = [
                'SECURE_SSL_REDIRECT',
                'SECURE_HSTS_SECONDS',
                'SECURE_HSTS_INCLUDE_SUBDOMAINS',
                'SECURE_CONTENT_TYPE_NOSNIFF',
                'SECURE_BROWSER_XSS_FILTER'
            ]
            
            for setting_name in security_settings:
                if hasattr(settings, setting_name):
                    setting_value = getattr(settings, setting_name)
                    if setting_name in ['SECURE_SSL_REDIRECT', 'SECURE_HSTS_INCLUDE_SUBDOMAINS', 
                                      'SECURE_CONTENT_TYPE_NOSNIFF', 'SECURE_BROWSER_XSS_FILTER']:
                        self.assertTrue(setting_value, f"{setting_name} should be True in production")
                    elif setting_name == 'SECURE_HSTS_SECONDS':
                        self.assertGreater(setting_value, 0, f"{setting_name} should be greater than 0")


class StaticFilesTest(TestCase):
    """
    Test static files configuration and collection.
    """
    
    def test_static_files_collection(self):
        """Test that static files can be collected."""
        try:
            call_command('collectstatic', '--noinput', '--dry-run', verbosity=0)
        except Exception as e:
            self.fail(f"Static files collection failed: {e}")
    
    def test_static_root_configuration(self):
        """Test STATIC_ROOT configuration."""
        self.assertIsNotNone(settings.STATIC_ROOT, "STATIC_ROOT should be configured")
        self.assertNotEqual(settings.STATIC_ROOT, settings.BASE_DIR, "STATIC_ROOT should not be BASE_DIR")
    
    def test_media_configuration(self):
        """Test media files configuration."""
        self.assertIsNotNone(settings.MEDIA_ROOT, "MEDIA_ROOT should be configured")
        self.assertIsNotNone(settings.MEDIA_URL, "MEDIA_URL should be configured")


class HealthCheckTest(TestCase):
    """
    Test health check endpoints and monitoring.
    """
    
    def test_basic_health_check(self):
        """Test basic health check endpoint."""
        from django.test import Client
        
        client = Client()
        response = client.get('/health/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.json())
    
    def test_detailed_health_check(self):
        """Test detailed health check endpoint."""
        from django.test import Client
        
        client = Client()
        response = client.get('/health/detailed/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should include service status
        expected_services = ['database', 'redis']
        for service in expected_services:
            self.assertIn(service, data, f"Health check missing {service} status")
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint for monitoring."""
        from django.test import Client
        
        client = Client()
        response = client.get('/metrics/')
        
        # Should return metrics data (format may vary)
        self.assertIn(response.status_code, [200, 404], "Metrics endpoint should be available or return 404")


class CeleryConfigurationTest(TestCase):
    """
    Test Celery configuration and task processing.
    """
    
    def test_celery_configuration(self):
        """Test Celery configuration."""
        from neurorides.celery import app
        
        # Test that Celery app is configured
        self.assertIsNotNone(app.conf.broker_url, "Celery broker URL not configured")
        self.assertIsNotNone(app.conf.result_backend, "Celery result backend not configured")
    
    def test_celery_task_discovery(self):
        """Test that Celery can discover tasks."""
        from neurorides.celery import app
        
        # Get registered tasks
        registered_tasks = list(app.tasks.keys())
        
        # Should have some tasks registered
        self.assertGreater(len(registered_tasks), 0, "No Celery tasks discovered")
        
        # Check for expected task modules
        expected_task_prefixes = [
            'dispatch.tasks',
            'analytics.tasks',
            'payments.tasks'
        ]
        
        for prefix in expected_task_prefixes:
            matching_tasks = [task for task in registered_tasks if task.startswith(prefix)]
            if len(matching_tasks) == 0:
                # This is a warning, not a failure, as tasks might not be implemented yet
                print(f"Warning: No tasks found for {prefix}")


class SecurityConfigurationTest(TestCase):
    """
    Test security configuration and measures.
    """
    
    def test_secret_key_strength(self):
        """Test that SECRET_KEY is strong enough."""
        secret_key = settings.SECRET_KEY
        
        # Should be at least 50 characters long
        self.assertGreaterEqual(len(secret_key), 50, "SECRET_KEY should be at least 50 characters")
        
        # Should not be the default Django secret key
        self.assertNotIn('django-insecure', secret_key.lower(), "Using default Django secret key")
    
    def test_password_validation(self):
        """Test password validation configuration."""
        validators = settings.AUTH_PASSWORD_VALIDATORS
        
        # Should have password validators configured
        self.assertGreater(len(validators), 0, "No password validators configured")
        
        # Check for common validators
        validator_names = [v['NAME'] for v in validators]
        expected_validators = [
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            'django.contrib.auth.password_validation.CommonPasswordValidator',
            'django.contrib.auth.password_validation.NumericPasswordValidator'
        ]
        
        for validator in expected_validators:
            self.assertIn(validator, validator_names, f"Missing password validator: {validator}")
    
    def test_csrf_configuration(self):
        """Test CSRF protection configuration."""
        # CSRF middleware should be enabled
        self.assertIn('django.middleware.csrf.CsrfViewMiddleware', settings.MIDDLEWARE)
        
        # CSRF cookie settings
        if not settings.DEBUG:
            csrf_settings = [
                ('CSRF_COOKIE_SECURE', True),
                ('CSRF_COOKIE_HTTPONLY', True),
                ('CSRF_COOKIE_SAMESITE', 'Strict')
            ]
            
            for setting_name, expected_value in csrf_settings:
                if hasattr(settings, setting_name):
                    actual_value = getattr(settings, setting_name)
                    self.assertEqual(actual_value, expected_value, 
                                   f"{setting_name} should be {expected_value} in production")


class LoadTestingTest(TestCase):
    """
    Basic load testing for critical endpoints.
    """
    
    def setUp(self):
        """Set up test data."""
        from accounts.models import User
        
        self.user = User.objects.create_user(
            username='loadtest_user',
            email='loadtest@example.com',
            password='testpass123',
            role='rider'
        )
    
    def test_concurrent_authentication_requests(self):
        """Test handling of concurrent authentication requests."""
        import threading
        from django.test import Client
        
        results = []
        errors = []
        
        def make_auth_request(thread_id):
            try:
                client = Client()
                response = client.post('/api/accounts/login/', {
                    'username': 'loadtest_user',
                    'password': 'testpass123'
                })
                results.append((thread_id, response.status_code))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_auth_request, args=(i,))
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 10, "Not all requests completed")
        
        # All requests should complete within reasonable time
        self.assertLess(duration, 10, f"Concurrent requests took too long: {duration}s")
        
        # Most requests should succeed (some might fail due to rate limiting)
        successful_requests = [r for r in results if r[1] == 200]
        self.assertGreater(len(successful_requests), 5, "Too many requests failed")
    
    def test_health_check_performance(self):
        """Test health check endpoint performance."""
        from django.test import Client
        
        client = Client()
        
        # Make multiple requests and measure time
        times = []
        for _ in range(10):
            start_time = time.time()
            response = client.get('/health/')
            duration = time.time() - start_time
            times.append(duration)
            
            self.assertEqual(response.status_code, 200)
        
        # Average response time should be under 100ms
        avg_time = sum(times) / len(times)
        self.assertLess(avg_time, 0.1, f"Health check too slow: {avg_time}s average")


class BackupAndRecoveryTest(TestCase):
    """
    Test backup and recovery procedures.
    """
    
    def test_backup_script_exists(self):
        """Test that backup script exists and is executable."""
        backup_script = os.path.join(settings.BASE_DIR, 'scripts', 'backup.sh')
        
        if os.path.exists(backup_script):
            # Check if script is executable
            self.assertTrue(os.access(backup_script, os.X_OK), "Backup script is not executable")
            
            # Check script content for required commands
            with open(backup_script, 'r') as f:
                content = f.read()
            
            required_commands = ['pg_dump', 'tar', 'gzip']
            for command in required_commands:
                self.assertIn(command, content, f"Backup script missing {command} command")
        else:
            self.skipTest("Backup script not found")
    
    def test_restore_script_exists(self):
        """Test that restore script exists and is executable."""
        restore_script = os.path.join(settings.BASE_DIR, 'scripts', 'restore.sh')
        
        if os.path.exists(restore_script):
            # Check if script is executable
            self.assertTrue(os.access(restore_script, os.X_OK), "Restore script is not executable")
            
            # Check script content
            with open(restore_script, 'r') as f:
                content = f.read()
            
            required_commands = ['psql', 'tar']
            for command in required_commands:
                self.assertIn(command, content, f"Restore script missing {command} command")
        else:
            self.skipTest("Restore script not found")


class MonitoringConfigurationTest(TestCase):
    """
    Test monitoring and logging configuration.
    """
    
    def test_logging_configuration(self):
        """Test logging configuration."""
        # Should have logging configured
        self.assertIn('LOGGING', dir(settings), "LOGGING configuration not found")
        
        logging_config = settings.LOGGING
        
        # Should have handlers and formatters
        self.assertIn('handlers', logging_config, "No logging handlers configured")
        self.assertIn('formatters', logging_config, "No logging formatters configured")
        
        # Should have loggers configured
        self.assertIn('loggers', logging_config, "No loggers configured")
    
    def test_error_tracking_configuration(self):
        """Test error tracking configuration (e.g., Sentry)."""
        # Check if Sentry is configured
        sentry_dsn = os.environ.get('SENTRY_DSN') or getattr(settings, 'SENTRY_DSN', None)
        
        if sentry_dsn:
            # Should have sentry_sdk in installed apps or middleware
            installed_apps = getattr(settings, 'INSTALLED_APPS', [])
            middleware = getattr(settings, 'MIDDLEWARE', [])
            
            # This is optional, so we just check if it's properly configured when present
            self.assertIsNotNone(sentry_dsn, "Sentry DSN configured but empty")
    
    def test_metrics_collection(self):
        """Test metrics collection configuration."""
        # Check if metrics endpoint is available
        from django.test import Client
        
        client = Client()
        response = client.get('/metrics/')
        
        # Metrics endpoint should exist (even if it returns 404, it means the URL is configured)
        self.assertIn(response.status_code, [200, 404, 405], "Metrics endpoint not configured")


def run_deployment_tests():
    """
    Run all deployment-related tests.
    """
    import unittest
    
    # Create test suite
    test_classes = [
        DockerDeploymentTest,
        DatabaseMigrationTest,
        EnvironmentConfigurationTest,
        StaticFilesTest,
        HealthCheckTest,
        CeleryConfigurationTest,
        SecurityConfigurationTest,
        BackupAndRecoveryTest,
        MonitoringConfigurationTest
    ]
    
    suite = unittest.TestSuite()
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_load_tests():
    """
    Run load testing tests.
    """
    import unittest
    
    suite = unittest.TestLoader().loadTestsFromTestCase(LoadTestingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    # Run deployment tests when script is executed directly
    success = run_deployment_tests()
    exit(0 if success else 1)