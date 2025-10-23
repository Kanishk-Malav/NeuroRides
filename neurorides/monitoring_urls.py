"""
URL configuration for monitoring and health check endpoints.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Basic health check endpoints
    path('health/', views.health_check, name='health_check'),
    path('health/detailed/', views.health_detailed, name='health_detailed'),
    path('health/ready/', views.readiness_check, name='readiness_check'),
    path('health/live/', views.liveness_check, name='liveness_check'),
    
    # Monitoring endpoints (admin only)
    path('monitoring/metrics/', views.metrics, name='metrics'),
    path('monitoring/system-info/', views.system_info, name='system_info'),
    path('monitoring/dashboard/', views.MonitoringDashboardView.as_view(), name='monitoring_dashboard'),
]