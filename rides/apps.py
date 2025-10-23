"""
Apps configuration for rides app.
"""

from django.apps import AppConfig


class RidesConfig(AppConfig):
    """Configuration for rides app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rides'
    verbose_name = 'Ride Management'
    
    def ready(self):
        """Import signals when app is ready."""
        import rides.signals  # noqa