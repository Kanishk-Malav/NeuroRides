"""
Celery configuration for real-time WebSocket tasks.
"""

from celery.schedules import crontab

# Real-time task routing
REALTIME_TASK_ROUTES = {
    'realtime.tasks.periodic_fleet_health_check': {'queue': 'realtime_monitoring'},
    'realtime.tasks.broadcast_fleet_status': {'queue': 'realtime_high'},
    'realtime.tasks.check_fleet_alerts': {'queue': 'realtime_high'},
    'realtime.tasks.calculate_fleet_metrics': {'queue': 'realtime_medium'},
    'realtime.tasks.process_vehicle_telemetry_batch': {'queue': 'realtime_high'},
    'realtime.tasks.cleanup_old_websocket_data': {'queue': 'realtime_low'},
}

# Periodic task schedule for real-time monitoring
REALTIME_BEAT_SCHEDULE = {
    # Fleet health check every 5 minutes
    'fleet-health-check': {
        'task': 'realtime.tasks.periodic_fleet_health_check',
        'schedule': crontab(minute='*/5'),
    },
    
    # Broadcast fleet status every 30 seconds
    'broadcast-fleet-status': {
        'task': 'realtime.tasks.broadcast_fleet_status',
        'schedule': 30.0,
    },
    
    # Check fleet alerts every 2 minutes
    'check-fleet-alerts': {
        'task': 'realtime.tasks.check_fleet_alerts',
        'schedule': crontab(minute='*/2'),
    },
    
    # Calculate fleet metrics every minute
    'calculate-fleet-metrics': {
        'task': 'realtime.tasks.calculate_fleet_metrics',
        'schedule': 60.0,
    },
    
    # Clean up old data daily at 2 AM
    'cleanup-old-websocket-data': {
        'task': 'realtime.tasks.cleanup_old_websocket_data',
        'schedule': crontab(hour=2, minute=0),
    },
}