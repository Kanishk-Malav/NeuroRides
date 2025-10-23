"""
WebSocket URL routing for real-time communication.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Ride tracking WebSocket for riders
    re_path(r'ws/rides/(?P<ride_id>[0-9a-f-]+)/$', consumers.RideTrackingConsumer.as_asgi()),
    
    # Fleet monitoring WebSocket for operators
    re_path(r'ws/fleet/$', consumers.FleetMonitoringConsumer.as_asgi()),
    
    # General notifications WebSocket
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]