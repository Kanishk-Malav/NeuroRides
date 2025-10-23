"""
Apps configuration for fleet app.
"""

from django.apps import AppConfig


class FleetConfig(AppConfig):
    """Configuration for fleet app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fleet'
    verbose_name = 'Fleet Management'
    
    def ready(self):
        """Import signals when app is ready."""
        import fleet.signals  # noqa