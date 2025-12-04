"""
Health check URL configuration.
"""

from django.urls import path
from .health import (
    health_check,
    health_check_detailed,
    readiness_check,
    liveness_check
)

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('health/detailed/', health_check_detailed, name='health_check_detailed'),
    path('health/ready/', readiness_check, name='readiness_check'),
    path('health/live/', liveness_check, name='liveness_check'),
]
