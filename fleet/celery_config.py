"""
Celery configuration for fleet management tasks.
"""

from celery.schedules import crontab

# Fleet-specific task routing
FLEET_TASK_ROUTES = {
    'fleet.tasks.process_vehicle_telemetry': {'queue': 'fleet_high'},
    'fleet.tasks.schedule_maintenance_checks': {'queue': 'fleet_medium'},
    'fleet.tasks.update_vehicle_locations': {'queue': 'fleet_high'},
    'fleet.tasks.check_vehicle_health': {'queue': 'fleet_medium'},
    'fleet.tasks.generate_maintenance_alerts': {'queue': 'fleet_medium'},
    'fleet.tasks.cleanup_old_telemetry_data': {'queue': 'fleet_low'},
    'fleet.tasks.calculate_vehicle_utilization': {'queue': 'fleet_low'},
    'fleet.tasks.optimize_fleet_distribution': {'queue': 'fleet_low'},
}

# Periodic task schedule for fleet management
FLEET_BEAT_SCHEDULE = {
    # Schedule maintenance checks daily at 1 AM
    'schedule-maintenance-checks': {
        'task': 'fleet.tasks.schedule_maintenance_checks',
        'schedule': crontab(hour=1, minute=0),
    },
    
    # Check vehicle health every 10 minutes
    'check-vehicle-health': {
        'task': 'fleet.tasks.check_vehicle_health',
        'schedule': crontab(minute='*/10'),
    },
    
    # Generate maintenance alerts every 30 minutes
    'generate-maintenance-alerts': {
        'task': 'fleet.tasks.generate_maintenance_alerts',
        'schedule': crontab(minute='*/30'),
    },
    
    # Clean up old telemetry data daily at 3 AM
    'cleanup-old-telemetry-data': {
        'task': 'fleet.tasks.cleanup_old_telemetry_data',
        'schedule': crontab(hour=3, minute=0),
    },
    
    # Calculate vehicle utilization every hour
    'calculate-vehicle-utilization': {
        'task': 'fleet.tasks.calculate_vehicle_utilization',
        'schedule': crontab(minute=0),
    },
    
    # Optimize fleet distribution every 4 hours
    'optimize-fleet-distribution': {
        'task': 'fleet.tasks.optimize_fleet_distribution',
        'schedule': crontab(minute=0, hour='*/4'),
    },
}