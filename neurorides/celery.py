"""
Celery configuration for NeuroRides project.
"""

import os
import logging
from celery import Celery
from celery.signals import (
    task_prerun, task_postrun, task_failure, task_retry,
    worker_ready, worker_shutdown
)
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neurorides.settings')

app = Celery('neurorides')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure logging
logger = logging.getLogger(__name__)


# Task monitoring and logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task execution start."""
    logger.info(f"Task {task.name} [{task_id}] started with args={args}, kwargs={kwargs}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Log task execution completion."""
    logger.info(f"Task {task.name} [{task_id}] completed with state={state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failures."""
    logger.error(f"Task {sender.name} [{task_id}] failed: {exception}")
    logger.error(f"Traceback: {traceback}")


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Log task retries."""
    logger.warning(f"Task {sender.name} [{task_id}] retrying: {reason}")


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Log when worker is ready."""
    logger.info(f"Celery worker {sender.hostname} is ready")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Log when worker shuts down."""
    logger.info(f"Celery worker {sender.hostname} is shutting down")


# Custom task base class with enhanced error handling
class BaseTask(app.Task):
    """Base task class with enhanced error handling and logging."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {self.name} [{task_id}] failed: {exc}")
        
        # Send failure notification if configured
        try:
            from realtime.utils import notify_admins
            notify_admins(
                'task_failed',
                f'Task Failed: {self.name}',
                f'Task {self.name} [{task_id}] failed with error: {str(exc)}',
                {
                    'task_name': self.name,
                    'task_id': task_id,
                    'error': str(exc),
                    'args': args,
                    'kwargs': kwargs,
                }
            )
        except Exception as e:
            logger.error(f"Failed to send task failure notification: {e}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {self.name} [{task_id}] retrying due to: {exc}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {self.name} [{task_id}] completed successfully")


# Set the base task class
app.Task = BaseTask


# Health check task
@app.task(bind=True)
def health_check(self):
    """Health check task to verify Celery is working."""
    try:
        from django.db import connection
        from django.core.cache import cache
        
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Test Redis connection
        cache.set('celery_health_check', 'ok', 60)
        cache_value = cache.get('celery_health_check')
        
        if cache_value != 'ok':
            raise Exception("Redis cache test failed")
        
        return {
            'status': 'healthy',
            'timestamp': self.request.id,
            'worker': self.request.hostname,
            'database': 'ok',
            'redis': 'ok',
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': self.request.id,
            'worker': self.request.hostname,
        }


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery functionality."""
    logger.info(f'Debug task executed: {self.request!r}')
    return {
        'message': 'Debug task completed',
        'request_id': self.request.id,
        'hostname': self.request.hostname,
        'timestamp': str(self.request.called_directly),
    }