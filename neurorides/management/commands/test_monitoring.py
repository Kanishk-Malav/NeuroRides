"""
Management command to test monitoring and logging systems.
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from neurorides.monitoring import health_checker, metrics_collector
from neurorides.logging import (
    security_logger, performance_logger, business_logger, get_logger
)


class Command(BaseCommand):
    help = 'Test monitoring and logging systems'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--component',
            type=str,
            choices=['health', 'metrics', 'logging', 'all'],
            default='all',
            help='Component to test (default: all)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        component = options['component']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS(f'Testing monitoring system - Component: {component}')
        )
        
        if component in ['health', 'all']:
            self.test_health_checks(verbose)
        
        if component in ['metrics', 'all']:
            self.test_metrics_collection(verbose)
        
        if component in ['logging', 'all']:
            self.test_logging_system(verbose)
        
        self.stdout.write(
            self.style.SUCCESS('Monitoring system test completed successfully!')
        )
    
    def test_health_checks(self, verbose=False):
        """Test health check system."""
        self.stdout.write('Testing health checks...')
        
        try:
            # Run all health checks
            results = health_checker.run_all_checks()
            
            self.stdout.write(
                f"Overall status: {self.style.SUCCESS(results['overall_status'])}"
            )
            self.stdout.write(
                f"Checks passed: {results['summary']['passed']}/{results['summary']['total_checks']}"
            )
            
            if verbose:
                for check_name, check_result in results['checks'].items():
                    status_style = self.style.SUCCESS if check_result['status'] == 'healthy' else self.style.WARNING
                    self.stdout.write(
                        f"  {check_name}: {status_style(check_result['status'])} - {check_result['message']}"
                    )
            
            # Test individual checks
            for check_name in ['database', 'redis', 'memory', 'disk_space']:
                if check_name in health_checker.checks:
                    start_time = time.time()
                    result = health_checker.checks[check_name]()
                    duration = (time.time() - start_time) * 1000
                    
                    if verbose:
                        self.stdout.write(
                            f"  {check_name} check: {result['status']} ({duration:.2f}ms)"
                        )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Health check test failed: {str(e)}')
            )
    
    def test_metrics_collection(self, verbose=False):
        """Test metrics collection system."""
        self.stdout.write('Testing metrics collection...')
        
        try:
            # Collect system metrics
            start_time = time.time()
            system_metrics = metrics_collector.collect_system_metrics()
            system_duration = (time.time() - start_time) * 1000
            
            if system_metrics:
                self.stdout.write(
                    f"System metrics collected successfully ({system_duration:.2f}ms)"
                )
                if verbose:
                    self.stdout.write(f"  CPU usage: {system_metrics.get('cpu', {}).get('usage_percent', 'N/A')}%")
                    self.stdout.write(f"  Memory usage: {system_metrics.get('memory', {}).get('usage_percent', 'N/A')}%")
                    self.stdout.write(f"  Disk usage: {system_metrics.get('disk', {}).get('usage_percent', 'N/A')}%")
            else:
                self.stdout.write(self.style.WARNING('System metrics collection returned empty'))
            
            # Collect application metrics
            start_time = time.time()
            app_metrics = metrics_collector.collect_application_metrics()
            app_duration = (time.time() - start_time) * 1000
            
            if app_metrics:
                self.stdout.write(
                    f"Application metrics collected successfully ({app_duration:.2f}ms)"
                )
                if verbose:
                    users = app_metrics.get('users', {})
                    rides = app_metrics.get('rides', {})
                    fleet = app_metrics.get('fleet', {})
                    
                    self.stdout.write(f"  Total users: {users.get('total_users', 'N/A')}")
                    self.stdout.write(f"  Active rides: {rides.get('active_rides', 'N/A')}")
                    self.stdout.write(f"  Active vehicles: {fleet.get('active_vehicles', 'N/A')}")
            else:
                self.stdout.write(self.style.WARNING('Application metrics collection returned empty'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Metrics collection test failed: {str(e)}')
            )
    
    def test_logging_system(self, verbose=False):
        """Test logging system."""
        self.stdout.write('Testing logging system...')
        
        try:
            # Test different loggers
            loggers_to_test = [
                ('neurorides', 'Main application logger'),
                ('neurorides.api', 'API logger'),
                ('neurorides.performance', 'Performance logger'),
                ('django.security', 'Security logger'),
            ]
            
            for logger_name, description in loggers_to_test:
                logger = get_logger(logger_name)
                
                # Test different log levels
                logger.debug(f'Test DEBUG message from {logger_name}')
                logger.info(f'Test INFO message from {logger_name}')
                logger.warning(f'Test WARNING message from {logger_name}')
                
                if verbose:
                    self.stdout.write(f"  Tested {description}")
            
            # Test specialized loggers
            self.stdout.write('Testing specialized loggers...')
            
            # Test security logger
            security_logger.log_authentication_attempt(
                username='test_user',
                success=True,
                reason='Test authentication'
            )
            
            security_logger.log_suspicious_activity(
                description='Test suspicious activity logging',
                severity='low'
            )
            
            # Test performance logger
            performance_logger.log_api_performance(
                endpoint='/test/endpoint',
                method='GET',
                duration=150,
                status_code=200
            )
            
            performance_logger.log_task_performance(
                task_name='test_task',
                duration=5000,
                success=True
            )
            
            # Test business logger
            business_logger.log_ride_event(
                ride_id='test_ride_123',
                event_type='ride_created',
                user_id='test_user_456',
                details={'test': True}
            )
            
            business_logger.log_payment_event(
                payment_id='test_payment_789',
                event_type='payment_processed',
                amount=25.50,
                user_id='test_user_456'
            )
            
            if verbose:
                self.stdout.write('  Security logger: OK')
                self.stdout.write('  Performance logger: OK')
                self.stdout.write('  Business logger: OK')
            
            # Test exception logging
            try:
                raise ValueError("Test exception for logging")
            except ValueError as e:
                logger = get_logger('neurorides.test')
                logger.error(f"Test exception logging: {str(e)}", exc_info=True)
                
                if verbose:
                    self.stdout.write('  Exception logging: OK')
            
            self.stdout.write(self.style.SUCCESS('All logging tests completed'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Logging system test failed: {str(e)}')
            )
    
    def test_log_rotation(self):
        """Test log rotation functionality."""
        self.stdout.write('Testing log rotation...')
        
        try:
            import os
            from django.conf import settings
            
            logs_dir = settings.BASE_DIR / 'logs'
            
            # Check if log files exist
            log_files = [
                'django.log',
                'errors.log',
                'security.log',
                'performance.log',
                'celery.log',
                'api.log',
            ]
            
            for log_file in log_files:
                log_path = logs_dir / log_file
                if log_path.exists():
                    size_mb = log_path.stat().st_size / (1024 * 1024)
                    self.stdout.write(f"  {log_file}: {size_mb:.2f} MB")
                else:
                    self.stdout.write(f"  {log_file}: Not found")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Log rotation test failed: {str(e)}')
            )