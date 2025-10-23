"""
WebSocket consumers for real-time communication.
"""

import json
import logging
from typing import Dict, Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

from rides.models import Ride
from fleet.models import Vehicle
from accounts.models import User

logger = logging.getLogger(__name__)

User = get_user_model()


class BaseConsumer(AsyncWebsocketConsumer):
    """Base consumer with common functionality."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.groups = []
    
    async def connect(self):
        """Handle WebSocket connection."""
        # Get user from scope (set by AuthMiddlewareStack)
        self.user = self.scope["user"]
        
        if isinstance(self.user, AnonymousUser):
            logger.warning("Anonymous user attempted WebSocket connection")
            await self.close()
            return
        
        # Perform authentication and authorization
        if not await self.authenticate_user():
            logger.warning(f"User {self.user.username} failed WebSocket authentication")
            await self.close()
            return
        
        # Join groups
        await self.join_groups()
        
        # Accept connection
        await self.accept()
        
        logger.info(f"WebSocket connected: {self.user.username} ({self.__class__.__name__})")
        
        # Send initial data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave groups
        await self.leave_groups()
        
        logger.info(f"WebSocket disconnected: {self.user.username if self.user else 'Unknown'} ({self.__class__.__name__})")
    
    async def authenticate_user(self):
        """Authenticate and authorize user. Override in subclasses."""
        return True
    
    async def join_groups(self):
        """Join WebSocket groups. Override in subclasses."""
        pass
    
    async def leave_groups(self):
        """Leave WebSocket groups."""
        for group_name in self.groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)
    
    async def send_initial_data(self):
        """Send initial data after connection. Override in subclasses."""
        pass
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type:
                handler_name = f'handle_{message_type}'
                handler = getattr(self, handler_name, None)
                
                if handler:
                    await handler(data)
                else:
                    await self.send_error(f"Unknown message type: {message_type}")
            else:
                await self.send_error("Message type is required")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]):
        """Send a message to the WebSocket."""
        await self.send(text_data=json.dumps({
            'type': message_type,
            'data': data,
            'timestamp': self.get_timestamp()
        }))
    
    async def send_error(self, error_message: str):
        """Send an error message to the WebSocket."""
        await self.send_message('error', {'message': error_message})
    
    def get_timestamp(self):
        """Get current timestamp."""
        from django.utils import timezone
        return timezone.now().isoformat()


class RideTrackingConsumer(BaseConsumer):
    """WebSocket consumer for ride tracking."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ride_id = None
        self.ride = None
    
    async def authenticate_user(self):
        """Authenticate user for ride tracking."""
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        
        try:
            # Get ride and check permissions
            self.ride = await database_sync_to_async(Ride.objects.get)(id=self.ride_id)
            
            # Check if user is the rider or an operator/admin
            if (self.user == self.ride.rider or 
                self.user.is_operator or 
                self.user.is_admin_user):
                return True
            else:
                logger.warning(f"User {self.user.username} unauthorized for ride {self.ride_id}")
                return False
                
        except ObjectDoesNotExist:
            logger.warning(f"Ride {self.ride_id} not found")
            return False
    
    async def join_groups(self):
        """Join ride-specific group."""
        group_name = f'ride_{self.ride_id}'
        self.groups.append(group_name)
        await self.channel_layer.group_add(group_name, self.channel_name)
    
    async def send_initial_data(self):
        """Send initial ride data."""
        ride_data = await self.get_ride_data()
        await self.send_message('ride_status', ride_data)
    
    @database_sync_to_async
    def get_ride_data(self):
        """Get current ride data."""
        self.ride.refresh_from_db()
        
        data = {
            'id': str(self.ride.id),
            'status': self.ride.status,
            'pickup_address': self.ride.pickup_address,
            'destination_address': self.ride.destination_address,
            'estimated_fare': float(self.ride.estimated_fare) if self.ride.estimated_fare else None,
            'created_at': self.ride.created_at.isoformat(),
        }
        
        # Add vehicle data if assigned
        if hasattr(self.ride, 'assigned_vehicle') and self.ride.assigned_vehicle:
            vehicle = self.ride.assigned_vehicle
            data['vehicle'] = {
                'id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'model': vehicle.model,
                'current_latitude': vehicle.current_latitude,
                'current_longitude': vehicle.current_longitude,
                'battery_level': vehicle.battery_level,
            }
        
        return data
    
    async def handle_ping(self, data):
        """Handle ping messages."""
        await self.send_message('pong', {'message': 'Connection alive'})
    
    # Group message handlers
    async def ride_status_update(self, event):
        """Handle ride status updates from group."""
        await self.send_message('ride_status_update', event['data'])
    
    async def vehicle_location_update(self, event):
        """Handle vehicle location updates from group."""
        await self.send_message('vehicle_location_update', event['data'])
    
    async def ride_assignment_update(self, event):
        """Handle ride assignment updates from group."""
        await self.send_message('ride_assignment_update', event['data'])


class FleetMonitoringConsumer(BaseConsumer):
    """WebSocket consumer for fleet monitoring."""
    
    async def authenticate_user(self):
        """Authenticate user for fleet monitoring."""
        # Only operators and admins can monitor fleet
        return self.user.is_operator or self.user.is_admin_user
    
    async def join_groups(self):
        """Join fleet monitoring groups."""
        group_name = 'fleet_monitoring'
        self.groups.append(group_name)
        await self.channel_layer.group_add(group_name, self.channel_name)
    
    async def send_initial_data(self):
        """Send initial fleet data."""
        fleet_data = await self.get_fleet_data()
        await self.send_message('fleet_status', fleet_data)
    
    @database_sync_to_async
    def get_fleet_data(self):
        """Get current fleet data."""
        vehicles = Vehicle.objects.all()
        
        fleet_summary = {
            'total_vehicles': vehicles.count(),
            'idle_vehicles': vehicles.filter(status=Vehicle.Status.IDLE).count(),
            'assigned_vehicles': vehicles.filter(status=Vehicle.Status.ASSIGNED).count(),
            'in_ride_vehicles': vehicles.filter(status=Vehicle.Status.IN_RIDE).count(),
            'maintenance_vehicles': vehicles.filter(status=Vehicle.Status.MAINTENANCE).count(),
            'offline_vehicles': vehicles.filter(status=Vehicle.Status.OFFLINE).count(),
        }
        
        # Get detailed vehicle data
        vehicle_list = []
        for vehicle in vehicles[:50]:  # Limit to 50 vehicles for performance
            vehicle_data = {
                'id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'model': vehicle.model,
                'status': vehicle.status,
                'battery_level': vehicle.battery_level,
                'current_latitude': vehicle.current_latitude,
                'current_longitude': vehicle.current_longitude,
                'last_seen': vehicle.last_seen.isoformat() if vehicle.last_seen else None,
            }
            vehicle_list.append(vehicle_data)
        
        return {
            'summary': fleet_summary,
            'vehicles': vehicle_list,
        }
    
    async def handle_ping(self, data):
        """Handle ping messages."""
        await self.send_message('pong', {'message': 'Fleet monitoring active'})
    
    async def handle_vehicle_filter(self, data):
        """Handle vehicle filtering requests."""
        status_filter = data.get('status')
        filtered_vehicles = await self.get_filtered_vehicles(status_filter)
        await self.send_message('filtered_vehicles', {'vehicles': filtered_vehicles})
    
    @database_sync_to_async
    def get_filtered_vehicles(self, status_filter=None):
        """Get filtered vehicle data."""
        vehicles = Vehicle.objects.all()
        
        if status_filter:
            vehicles = vehicles.filter(status=status_filter)
        
        vehicle_list = []
        for vehicle in vehicles[:100]:  # Limit for performance
            vehicle_data = {
                'id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'model': vehicle.model,
                'status': vehicle.status,
                'battery_level': vehicle.battery_level,
                'current_latitude': vehicle.current_latitude,
                'current_longitude': vehicle.current_longitude,
                'last_seen': vehicle.last_seen.isoformat() if vehicle.last_seen else None,
            }
            vehicle_list.append(vehicle_data)
        
        return vehicle_list
    
    # Group message handlers
    async def vehicle_status_update(self, event):
        """Handle vehicle status updates from group."""
        await self.send_message('vehicle_status_update', event['data'])
    
    async def vehicle_telemetry_update(self, event):
        """Handle vehicle telemetry updates from group."""
        await self.send_message('vehicle_telemetry_update', event['data'])
    
    async def maintenance_alert(self, event):
        """Handle maintenance alerts from group."""
        await self.send_message('maintenance_alert', event['data'])


class NotificationConsumer(BaseConsumer):
    """WebSocket consumer for general notifications."""
    
    async def join_groups(self):
        """Join user-specific notification group."""
        group_name = f'user_{self.user.id}_notifications'
        self.groups.append(group_name)
        await self.channel_layer.group_add(group_name, self.channel_name)
        
        # Join role-based groups
        if self.user.is_rider:
            await self.channel_layer.group_add('rider_notifications', self.channel_name)
            self.groups.append('rider_notifications')
        
        if self.user.is_operator:
            await self.channel_layer.group_add('operator_notifications', self.channel_name)
            self.groups.append('operator_notifications')
        
        if self.user.is_admin_user:
            await self.channel_layer.group_add('admin_notifications', self.channel_name)
            self.groups.append('admin_notifications')
    
    async def handle_ping(self, data):
        """Handle ping messages."""
        await self.send_message('pong', {'message': 'Notifications active'})
    
    # Group message handlers
    async def notification(self, event):
        """Handle general notifications from group."""
        await self.send_message('notification', event['data'])
    
    async def system_alert(self, event):
        """Handle system alerts from group."""
        await self.send_message('system_alert', event['data'])