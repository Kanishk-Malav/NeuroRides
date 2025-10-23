"""
URL configuration for realtime app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RideTrackingViewSet, FleetMonitoringViewSet, NotificationViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'ride-tracking', RideTrackingViewSet, basename='ride-tracking')
router.register(r'fleet-monitoring', FleetMonitoringViewSet, basename='fleet-monitoring')
router.register(r'notifications', NotificationViewSet, basename='notifications')

app_name = 'realtime'

urlpatterns = [
    path('api/realtime/', include(router.urls)),
]