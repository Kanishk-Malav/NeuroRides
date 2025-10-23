"""
WebSocket consumers for real-time notifications.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


class RideTrackingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for ride tracking updates."""
    
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f'ride_{self.ride_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        # Handle incoming WebSocket messages
        pass
    
    async def ride_status_update(self, event):
        """Send ride status update to WebSocket."""
        message = event['message']
        
        await self.send(text_data=json.dumps({
            'type': 'ride_status_update',
            'message': message
        }))
    
    async def vehicle_location_update(self, event):
        """Send vehicle location update to WebSocket."""
        message = event['message']
        
        await self.send(text_data=json.dumps({
            'type': 'vehicle_location_update',
            'message': message
        }))


class FleetMonitoringConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for fleet monitoring updates."""
    
    async def connect(self):
        self.room_group_name = 'fleet_monitoring'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        # Handle incoming WebSocket messages
        pass
    
    async def fleet_update(self, event):
        """Send fleet update to WebSocket."""
        message = event['message']
        
        await self.send(text_data=json.dumps({
            'type': 'fleet_update',
            'message': message
        }))
    
    async def maintenance_alert(self, event):
        """Send maintenance alert to WebSocket."""
        message = event['message']
        
        await self.send(text_data=json.dumps({
            'type': 'maintenance_alert',
            'message': message
        }))