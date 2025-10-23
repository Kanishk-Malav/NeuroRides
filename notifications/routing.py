"""
WebSocket URL routing for notifications app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/ride/(?P<ride_id>\w+)/$', consumers.RideTrackingConsumer.as_asgi()),
    re_path(r'ws/fleet/$', consumers.FleetMonitoringConsumer.as_asgi()),
]