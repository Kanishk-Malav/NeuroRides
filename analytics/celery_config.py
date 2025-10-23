"""
Celery configuration for analytics tasks.
"""

from celery.schedules import crontab

# Analytics-specific task routing
ANALYTICS_TASK_ROUTES = {
    'analytics.tasks.aggregate_daily_analytics': {'queue': 'analytics_high'},
    'analytics.tasks.aggregate_hourly_analytics': {'queue': 'analytics_high'},
    'analytics.tasks.aggregate_weekly_analytics': {'queue': 'analytics_medium'},
    'analytics.tasks.cleanup_old_analytics_data': {'queue': 'analytics_low'},
    'analytics.tasks.generate_scheduled_report': {'queue': 'analytics_medium'},
    'analytics.tasks.calculate_performance_metrics': {'queue': 'analytics_medium'},
    'analytics.tasks.generate_daily_summary_report': {'queue': 'analytics_low'},
}

# Periodic task schedule for analytics
ANALYTICS_BEAT_SCHEDULE = {
    # Aggregate daily analytics at 2:30 AM
    'aggregate-daily-analytics': {
        'task': 'analytics.tasks.aggregate_daily_analytics',
        'schedule': crontab(hour=2, minute=30),
    },
    
    # Aggregate hourly analytics every hour at 5 minutes past
    'aggregate-hourly-analytics': {
        'task': 'analytics.tasks.aggregate_hourly_analytics',
        'schedule': crontab(minute=5),
    },
    
    # Weekly aggregation on Mondays at 3 AM
    'aggregate-weekly-analytics': {
        'task': 'analytics.tasks.aggregate_weekly_analytics',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),
    },
    
    # Clean up old data monthly on the 1st at 4 AM
    'cleanup-old-analytics-data': {
        'task': 'analytics.tasks.cleanup_old_analytics_data',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),
    },
    
    # Calculate performance metrics every 5 minutes
    'calculate-performance-metrics': {
        'task': 'analytics.tasks.calculate_performance_metrics',
        'schedule': crontab(minute='*/5'),
    },
    
    # Generate daily summary at 6 AM
    'generate-daily-summary-report': {
        'task': 'analytics.tasks.generate_daily_summary_report',
        'schedule': crontab(hour=6, minute=0),
    },
}