"""
Apps configuration for realtime app.
"""

from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    """Configuration for realtime app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'realtime'
    verbose_name = 'Real-time Communication'
    
    def ready(self):
        """Import signals when app is ready."""
        import realtime.signals  # noqa