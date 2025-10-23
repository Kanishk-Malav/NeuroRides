"""
Celery configuration for dispatch tasks.
"""

from celery.schedules import crontab

# Dispatch-specific task routing
DISPATCH_TASK_ROUTES = {
    'dispatch.tasks.process_dispatch_request': {'queue': 'dispatch_high'},
    'dispatch.tasks.process_dispatch_queue': {'queue': 'dispatch_medium'},
    'dispatch.tasks.cleanup_expired_dispatch_requests': {'queue': 'dispatch_low'},
    'dispatch.tasks.retry_failed_dispatch_requests': {'queue': 'dispatch_low'},
    'dispatch.tasks.generate_daily_dispatch_metrics': {'queue': 'dispatch_low'},
    'dispatch.tasks.monitor_dispatch_performance': {'queue': 'dispatch_low'},
    'dispatch.tasks.update_vehicle_assignments': {'queue': 'dispatch_medium'},
}

# Periodic task schedule for dispatch
DISPATCH_BEAT_SCHEDULE = {
    # Process dispatch queue every 30 seconds
    'process-dispatch-queue': {
        'task': 'dispatch.tasks.process_dispatch_queue',
        'schedule': 30.0,
        'kwargs': {'max_requests': 20},
    },
    
    # Clean up expired requests every 5 minutes
    'cleanup-expired-requests': {
        'task': 'dispatch.tasks.cleanup_expired_dispatch_requests',
        'schedule': crontab(minute='*/5'),
    },
    
    # Retry failed requests every 10 minutes
    'retry-failed-requests': {
        'task': 'dispatch.tasks.retry_failed_dispatch_requests',
        'schedule': crontab(minute='*/10'),
    },
    
    # Generate daily metrics at 1 AM
    'generate-daily-metrics': {
        'task': 'dispatch.tasks.generate_daily_dispatch_metrics',
        'schedule': crontab(hour=1, minute=0),
    },
    
    # Monitor performance every 15 minutes
    'monitor-performance': {
        'task': 'dispatch.tasks.monitor_dispatch_performance',
        'schedule': crontab(minute='*/15'),
    },
    
    # Update vehicle assignments every 2 minutes
    'update-vehicle-assignments': {
        'task': 'dispatch.tasks.update_vehicle_assignments',
        'schedule': crontab(minute='*/2'),
    },
}