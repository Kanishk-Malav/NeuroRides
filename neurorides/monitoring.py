"""
System monitoring and health check utilities.
"""

import time
import psutil
import logging
from datetime import datetime, timedelta
from django.db import connection, connections
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from celery import current_app as celery_app

logger = logging.getLogger('neurorides.monitoring')


class SystemHealthChecker:
    """
    Comprehensive system health checker.
    """
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'redis': self._check_redis,
            'celery': self._check_celery,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
            'cpu': self._check_cpu,
            'external_services': self._check_external_services,
        }
    
    def run_all_checks(self):
        """Run all health checks and return results."""
        results = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {},
            'summary': {
                'total_checks': len(self.checks),
                'passed': 0,
                'failed': 0,
                'warnings': 0,
            }
        }
        
        for check_name, check_func in self.checks.items():
            try:
                start_time = time.time()
                check_result = check_func()
                duration = (time.time() - start_time) * 1000
                
                check_result['duration_ms'] = round(duration, 2)
                results['checks'][check_name] = check_result
                
                # Update summary
                if check_result['status'] == 'healthy':
                    results['summary']['passed'] += 1
                elif check_result['status'] == 'warning':
                    results['summary']['warnings'] += 1
                else:
                    results['summary']['failed'] += 1
                    results['overall_status'] = 'unhealthy'
                
            except Exception as e:
                logger.error(f"Health check {check_name} failed with exception: {e}")
                results['checks'][check_name] = {
                    'status': 'error',
                    'message': f'Check failed with exception: {str(e)}',
                    'duration_ms': 0,
                }
                results['summary']['failed'] += 1
                results['overall_status'] = 'unhealthy'
        
        # Set overall status to warning if there are warnings but no failures
        if results['summary']['warnings'] > 0 and results['summary']['failed'] == 0:
            results['overall_status'] = 'warning'
        
        return results
    
    def _check_database(self):
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test primary database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            query_time = (time.time() - start_time) * 1000
            
            # Check connection pool status
            db_connections = len(connections.all())
            
            # Get database size (PostgreSQL specific)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                               pg_database_size(current_database()) as size_bytes
                    """)
                    db_size_info = cursor.fetchone()
                    db_size = db_size_info[0] if db_size_info else 'Unknown'
                    db_size_bytes = db_size_info[1] if db_size_info else 0
            except Exception:
                db_size = 'Unknown'
                db_size_bytes = 0
            
            status = 'healthy'
            message = 'Database is accessible'
            
            if query_time > 1000:  # Query took more than 1 second
                status = 'warning'
                message = f'Database query is slow ({query_time:.2f}ms)'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'query_time_ms': round(query_time, 2),
                    'active_connections': db_connections,
                    'database_size': db_size,
                    'database_size_bytes': db_size_bytes,
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Database connection failed: {str(e)}',
                'details': {}
            }
    
    def _check_redis(self):
        """Check Redis connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test Redis connection
            cache.set('health_check', 'ok', 60)
            result = cache.get('health_check')
            
            if result != 'ok':
                return {
                    'status': 'error',
                    'message': 'Redis cache test failed',
                    'details': {}
                }
            
            response_time = (time.time() - start_time) * 1000
            
            # Get Redis info if available
            try:
                from django_redis import get_redis_connection
                redis_conn = get_redis_connection("default")
                redis_info = redis_conn.info()
                
                memory_usage = redis_info.get('used_memory_human', 'Unknown')
                connected_clients = redis_info.get('connected_clients', 0)
                
            except Exception:
                memory_usage = 'Unknown'
                connected_clients = 0
            
            status = 'healthy'
            message = 'Redis is accessible'
            
            if response_time > 500:  # Response took more than 500ms
                status = 'warning'
                message = f'Redis response is slow ({response_time:.2f}ms)'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'response_time_ms': round(response_time, 2),
                    'memory_usage': memory_usage,
                    'connected_clients': connected_clients,
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Redis connection failed: {str(e)}',
                'details': {}
            }
    
    def _check_celery(self):
        """Check Celery worker status."""
        try:
            # Get active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            
            if not active_workers:
                return {
                    'status': 'error',
                    'message': 'No active Celery workers found',
                    'details': {}
                }
            
            # Get worker statistics
            stats = inspect.stats()
            
            total_workers = len(active_workers)
            total_active_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            # Check for failed tasks in the last hour
            try:
                from celery.events.state import State
                state = State()
                failed_tasks = len([task for task in state.tasks.values() 
                                  if task.state == 'FAILURE' and 
                                  task.timestamp and 
                                  task.timestamp > time.time() - 3600])
            except Exception:
                failed_tasks = 0
            
            status = 'healthy'
            message = f'{total_workers} Celery workers active'
            
            if total_workers < 2:  # Minimum recommended workers
                status = 'warning'
                message = f'Only {total_workers} Celery worker(s) active (recommended: 2+)'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'active_workers': total_workers,
                    'active_tasks': total_active_tasks,
                    'failed_tasks_last_hour': failed_tasks,
                    'worker_stats': stats,
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Celery check failed: {str(e)}',
                'details': {}
            }
    
    def _check_disk_space(self):
        """Check disk space usage."""
        try:
            disk_usage = psutil.disk_usage('/')
            
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            status = 'healthy'
            message = f'Disk usage: {usage_percent:.1f}%'
            
            if usage_percent > 90:
                status = 'error'
                message = f'Critical disk usage: {usage_percent:.1f}%'
            elif usage_percent > 80:
                status = 'warning'
                message = f'High disk usage: {usage_percent:.1f}%'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'total_gb': round(total_gb, 2),
                    'used_gb': round(used_gb, 2),
                    'free_gb': round(free_gb, 2),
                    'usage_percent': round(usage_percent, 1),
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Disk space check failed: {str(e)}',
                'details': {}
            }
    
    def _check_memory(self):
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            
            total_gb = memory.total / (1024**3)
            used_gb = memory.used / (1024**3)
            available_gb = memory.available / (1024**3)
            usage_percent = memory.percent
            
            status = 'healthy'
            message = f'Memory usage: {usage_percent:.1f}%'
            
            if usage_percent > 90:
                status = 'error'
                message = f'Critical memory usage: {usage_percent:.1f}%'
            elif usage_percent > 80:
                status = 'warning'
                message = f'High memory usage: {usage_percent:.1f}%'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'total_gb': round(total_gb, 2),
                    'used_gb': round(used_gb, 2),
                    'available_gb': round(available_gb, 2),
                    'usage_percent': round(usage_percent, 1),
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Memory check failed: {str(e)}',
                'details': {}
            }
    
    def _check_cpu(self):
        """Check CPU usage."""
        try:
            # Get CPU usage over 1 second interval
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            status = 'healthy'
            message = f'CPU usage: {cpu_percent:.1f}%'
            
            if cpu_percent > 90:
                status = 'error'
                message = f'Critical CPU usage: {cpu_percent:.1f}%'
            elif cpu_percent > 80:
                status = 'warning'
                message = f'High CPU usage: {cpu_percent:.1f}%'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'usage_percent': round(cpu_percent, 1),
                    'cpu_count': cpu_count,
                    'load_avg_1min': round(load_avg[0], 2),
                    'load_avg_5min': round(load_avg[1], 2),
                    'load_avg_15min': round(load_avg[2], 2),
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'CPU check failed: {str(e)}',
                'details': {}
            }
    
    def _check_external_services(self):
        """Check external service connectivity."""
        try:
            import requests
            
            services = {
                'stripe': 'https://api.stripe.com/v1',
                # Add other external services as needed
            }
            
            results = {}
            overall_status = 'healthy'
            
            for service_name, url in services.items():
                try:
                    start_time = time.time()
                    response = requests.get(url, timeout=5)
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status_code < 400:
                        results[service_name] = {
                            'status': 'healthy',
                            'response_time_ms': round(response_time, 2),
                            'status_code': response.status_code,
                        }
                    else:
                        results[service_name] = {
                            'status': 'error',
                            'response_time_ms': round(response_time, 2),
                            'status_code': response.status_code,
                        }
                        overall_status = 'warning'
                        
                except Exception as e:
                    results[service_name] = {
                        'status': 'error',
                        'error': str(e),
                    }
                    overall_status = 'warning'
            
            return {
                'status': overall_status,
                'message': f'Checked {len(services)} external services',
                'details': results
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'External services check failed: {str(e)}',
                'details': {}
            }


class MetricsCollector:
    """
    Collect system and application metrics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('neurorides.metrics')
    
    def collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'cpu': {
                    'usage_percent': cpu_percent,
                    'count': cpu_count,
                },
                'memory': {
                    'total_bytes': memory.total,
                    'used_bytes': memory.used,
                    'available_bytes': memory.available,
                    'usage_percent': memory.percent,
                },
                'disk': {
                    'total_bytes': disk.total,
                    'used_bytes': disk.used,
                    'free_bytes': disk.free,
                    'usage_percent': (disk.used / disk.total) * 100,
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv,
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {}
    
    def collect_application_metrics(self):
        """Collect application-level metrics."""
        try:
            from django.contrib.sessions.models import Session
            from accounts.models import User
            from rides.models import Ride
            from fleet.models import Vehicle
            from payments.models import Payment
            
            # Active sessions
            active_sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            ).count()
            
            # User metrics
            total_users = User.objects.count()
            active_users_today = User.objects.filter(
                last_login__date=timezone.now().date()
            ).count()
            
            # Ride metrics
            total_rides = Ride.objects.count()
            rides_today = Ride.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
            active_rides = Ride.objects.filter(
                status__in=['requested', 'assigned', 'pickup', 'in_progress']
            ).count()
            
            # Fleet metrics
            total_vehicles = Vehicle.objects.count()
            active_vehicles = Vehicle.objects.filter(
                is_active=True,
                status__in=['idle', 'assigned', 'in_ride']
            ).count()
            
            # Payment metrics
            payments_today = Payment.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
            successful_payments_today = Payment.objects.filter(
                created_at__date=timezone.now().date(),
                status='completed'
            ).count()
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'sessions': {
                    'active_sessions': active_sessions,
                },
                'users': {
                    'total_users': total_users,
                    'active_users_today': active_users_today,
                },
                'rides': {
                    'total_rides': total_rides,
                    'rides_today': rides_today,
                    'active_rides': active_rides,
                },
                'fleet': {
                    'total_vehicles': total_vehicles,
                    'active_vehicles': active_vehicles,
                    'utilization_rate': (active_vehicles / total_vehicles) * 100 if total_vehicles > 0 else 0,
                },
                'payments': {
                    'payments_today': payments_today,
                    'successful_payments_today': successful_payments_today,
                    'success_rate': (successful_payments_today / payments_today) * 100 if payments_today > 0 else 0,
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect application metrics: {e}")
            return {}
    
    def collect_all_metrics(self):
        """Collect all metrics."""
        system_metrics = self.collect_system_metrics()
        app_metrics = self.collect_application_metrics()
        
        return {
            'system': system_metrics,
            'application': app_metrics,
        }


# Global instances
health_checker = SystemHealthChecker()
metrics_collector = MetricsCollector()