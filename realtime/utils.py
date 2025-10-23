"""
Utility functions for WebSocket communication.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebSocketNotifier:
    """Utility class for sending WebSocket notifications."""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def send_to_group(self, group_name: str, message_type: str, data: Dict[str, Any]):
        """Send message to a WebSocket group."""
        if not self.channel_layer:
            logger.warning("Channel layer not configured")
            return
        
        message = {
            'type': message_type.replace('.', '_'),  # Convert dots to underscores for method names
            'data': {
                **data,
                'timestamp': timezone.now().isoformat()
            }
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(group_name, message)
            logger.debug(f"Sent {message_type} to group {group_name}")
        except Exception as e:
            logger.error(f"Failed to send message to group {group_name}: {str(e)}")
    
    def send_to_user(self, user_id: int, message_type: str, data: Dict[str, Any]):
        """Send message to a specific user."""
        group_name = f'user_{user_id}_notifications'
        self.send_to_group(group_name, message_type, data)
    
    def send_ride_update(self, ride_id: str, message_type: str, data: Dict[str, Any]):
        """Send ride-related update."""
        group_name = f'ride_{ride_id}'
        self.send_to_group(group_name, message_type, data)
    
    def send_fleet_update(self, message_type: str, data: Dict[str, Any]):
        """Send fleet-related update."""
        group_name = 'fleet_monitoring'
        self.send_to_group(group_name, message_type, data)
    
    def send_notification_to_riders(self, message_type: str, data: Dict[str, Any]):
        """Send notification to all riders."""
        group_name = 'rider_notifications'
        self.send_to_group(group_name, message_type, data)
    
    def send_notification_to_operators(self, message_type: str, data: Dict[str, Any]):
        """Send notification to all operators."""
        group_name = 'operator_notifications'
        self.send_to_group(group_name, message_type, data)
    
    def send_notification_to_admins(self, message_type: str, data: Dict[str, Any]):
        """Send notification to all admins."""
        group_name = 'admin_notifications'
        self.send_to_group(group_name, message_type, data)


# Global notifier instance
notifier = WebSocketNotifier()


def notify_ride_status_change(ride_id: str, status: str, additional_data: Optional[Dict] = None):
    """Notify about ride status change."""
    data = {
        'ride_id': ride_id,
        'status': status,
        'message': f'Ride status changed to {status}'
    }
    
    if additional_data:
        data.update(additional_data)
    
    notifier.send_ride_update(ride_id, 'ride_status_update', data)


def notify_vehicle_assignment(ride_id: str, vehicle_data: Dict[str, Any]):
    """Notify about vehicle assignment to ride."""
    data = {
        'ride_id': ride_id,
        'vehicle': vehicle_data,
        'message': f'Vehicle {vehicle_data.get("license_plate")} assigned to your ride'
    }
    
    notifier.send_ride_update(ride_id, 'ride_assignment_update', data)


def notify_vehicle_location_update(ride_id: str, vehicle_data: Dict[str, Any]):
    """Notify about vehicle location update."""
    data = {
        'ride_id': ride_id,
        'vehicle': vehicle_data,
        'message': 'Vehicle location updated'
    }
    
    notifier.send_ride_update(ride_id, 'vehicle_location_update', data)


def notify_vehicle_status_change(vehicle_id: str, status: str, additional_data: Optional[Dict] = None):
    """Notify about vehicle status change."""
    data = {
        'vehicle_id': vehicle_id,
        'status': status,
        'message': f'Vehicle status changed to {status}'
    }
    
    if additional_data:
        data.update(additional_data)
    
    notifier.send_fleet_update('vehicle_status_update', data)


def notify_vehicle_telemetry_update(vehicle_data: Dict[str, Any]):
    """Notify about vehicle telemetry update."""
    data = {
        'vehicle': vehicle_data,
        'message': 'Vehicle telemetry updated'
    }
    
    notifier.send_fleet_update('vehicle_telemetry_update', data)


def notify_maintenance_alert(vehicle_id: str, alert_type: str, message: str, additional_data: Optional[Dict] = None):
    """Notify about maintenance alert."""
    data = {
        'vehicle_id': vehicle_id,
        'alert_type': alert_type,
        'message': message,
        'severity': additional_data.get('severity', 'medium') if additional_data else 'medium'
    }
    
    if additional_data:
        data.update(additional_data)
    
    notifier.send_fleet_update('maintenance_alert', data)
    notifier.send_notification_to_operators('maintenance_alert', data)


def notify_user(user_id: int, message_type: str, title: str, message: str, additional_data: Optional[Dict] = None):
    """Send notification to specific user."""
    data = {
        'title': title,
        'message': message,
        'type': message_type
    }
    
    if additional_data:
        data.update(additional_data)
    
    notifier.send_to_user(user_id, 'notification', data)


def notify_system_alert(message: str, severity: str = 'info', target_roles: Optional[List[str]] = None):
    """Send system-wide alert."""
    data = {
        'message': message,
        'severity': severity,
        'type': 'system_alert'
    }
    
    # Send to specific roles or all users
    if target_roles:
        for role in target_roles:
            if role == 'rider':
                notifier.send_notification_to_riders('system_alert', data)
            elif role == 'operator':
                notifier.send_notification_to_operators('system_alert', data)
            elif role == 'admin':
                notifier.send_notification_to_admins('system_alert', data)
    else:
        # Send to all roles
        notifier.send_notification_to_riders('system_alert', data)
        notifier.send_notification_to_operators('system_alert', data)
        notifier.send_notification_to_admins('system_alert', data)