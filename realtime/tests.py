"""
Tests for real-time WebSocket functionality.
"""

import json
import asyncio
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator, ChannelsLiveServerTestCase
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from unittest.mock import patch, MagicMock

from rides.models import Ride
from fleet.models import Vehicle, VehicleTelemetry
from dispatch.models import DispatchRequest, DispatchAlgorithmConfig
from .consumers import RideTrackingConsumer, FleetMonitoringConsumer, NotificationConsumer
from .services import RideTrackingService, FleetMonitoringService
from .fleet_monitoring import FleetAnalytics, FleetAlertManager

User = get_user_model()


class WebSocketTestCase(TestCase):
    """Base test case for WebSocket tests."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='testpass123',
            phone_number='+1234567890',
            role=User.Role.RIDER
        )
        
        self.operator = User.objects.create_user(
            username='operator1',
            email='operator1@example.com',
            password='testpass123',
            phone_number='+1234567891',
            role=User.Role.OPERATOR
        )
        
        self.ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            pickup_address='123 Main St, San Francisco, CA',
            destination_address='456 Oak St, San Francisco, CA',
            status=Ride.Status.REQUESTED
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST123',
            model='Tesla Model 3',
            year=2023,
            battery_level=80,
            status=Vehicle.Status.IDLE,
            current_latitude=37.7749,
            current_longitude=-122.4194
        )


class RideTrackingConsumerTest(WebSocketTestCase):
    """Test RideTrackingConsumer."""
    
    async def test_ride_tracking_connection_authorized(self):
        """Test authorized connection to ride tracking."""
        communicator = WebsocketCommunicator(
            RideTrackingConsumer.as_asgi(),
            f"/ws/rides/{self.ride.id}/"
        )
        
        # Set user in scope
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive initial ride data
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'ride_status')
        self.assertIn('data', response)
        self.assertEqual(response['data']['id'], str(self.ride.id))
        
        await communicator.disconnect()
    
    async def test_ride_tracking_connection_unauthorized(self):
        """Test unauthorized connection to ride tracking."""
        # Create another user
        other_user = await database_sync_to_async(User.objects.create_user)(
            username='other_rider',
            email='other@example.com',
            password='testpass123',
            phone_number='+1234567892',
            role=User.Role.RIDER
        )
        
        communicator = WebsocketCommunicator(
            RideTrackingConsumer.as_asgi(),
            f"/ws/rides/{self.ride.id}/"
        )
        
        # Set unauthorized user in scope
        communicator.scope['user'] = other_user
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_ride_tracking_ping_pong(self):
        """Test ping-pong functionality."""
        communicator = WebsocketCommunicator(
            RideTrackingConsumer.as_asgi(),
            f"/ws/rides/{self.ride.id}/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial ride data
        await communicator.receive_json_from()
        
        # Send ping
        await communicator.send_json_to({
            'type': 'ping'
        })
        
        # Should receive pong
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        self.assertIn('data', response)
        
        await communicator.disconnect()


class FleetMonitoringConsumerTest(WebSocketTestCase):
    """Test FleetMonitoringConsumer."""
    
    async def test_fleet_monitoring_connection_authorized(self):
        """Test authorized connection to fleet monitoring."""
        communicator = WebsocketCommunicator(
            FleetMonitoringConsumer.as_asgi(),
            "/ws/fleet/"
        )
        
        # Set operator user in scope
        communicator.scope['user'] = self.operator
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive initial fleet data
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'fleet_status')
        self.assertIn('data', response)
        self.assertIn('summary', response['data'])
        self.assertIn('vehicles', response['data'])
        
        await communicator.disconnect()
    
    async def test_fleet_monitoring_connection_unauthorized(self):
        """Test unauthorized connection to fleet monitoring."""
        communicator = WebsocketCommunicator(
            FleetMonitoringConsumer.as_asgi(),
            "/ws/fleet/"
        )
        
        # Set rider user in scope (not authorized)
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_fleet_monitoring_vehicle_filter(self):
        """Test vehicle filtering functionality."""
        communicator = WebsocketCommunicator(
            FleetMonitoringConsumer.as_asgi(),
            "/ws/fleet/"
        )
        
        communicator.scope['user'] = self.operator
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial fleet data
        await communicator.receive_json_from()
        
        # Send filter request
        await communicator.send_json_to({
            'type': 'vehicle_filter',
            'status': 'idle'
        })
        
        # Should receive filtered vehicles
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'filtered_vehicles')
        self.assertIn('data', response)
        self.assertIn('vehicles', response['data'])
        
        await communicator.disconnect()


class NotificationConsumerTest(WebSocketTestCase):
    """Test NotificationConsumer."""
    
    async def test_notification_connection(self):
        """Test connection to notification consumer."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send ping
        await communicator.send_json_to({
            'type': 'ping'
        })
        
        # Should receive pong
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        
        await communicator.disconnect()


class WebSocketUtilsTest(WebSocketTestCase):
    """Test WebSocket utility functions."""
    
    def test_notifier_initialization(self):
        """Test WebSocketNotifier initialization."""
        from .utils import WebSocketNotifier
        
        notifier = WebSocketNotifier()
        self.assertIsNotNone(notifier.channel_layer)
    
    def test_notification_functions(self):
        """Test notification utility functions."""
        from .utils import (
            notify_ride_status_change,
            notify_vehicle_assignment,
            notify_vehicle_location_update,
            notify_user
        )
        
        # These functions should not raise exceptions
        notify_ride_status_change(str(self.ride.id), 'assigned')
        
        vehicle_data = {
            'id': str(self.vehicle.id),
            'license_plate': self.vehicle.license_plate,
            'model': self.vehicle.model
        }
        notify_vehicle_assignment(str(self.ride.id), vehicle_data)
        notify_vehicle_location_update(str(self.ride.id), vehicle_data)
        
        notify_user(self.rider.id, 'test', 'Test Title', 'Test message')
        
        # If we get here without exceptions, the functions work
        self.assertTrue(True)


class RideTrackingServiceTest(WebSocketTestCase):
    """Test RideTrackingService functionality."""
    
    def test_get_ride_tracking_data(self):
        """Test getting comprehensive ride tracking data."""
        # Create dispatch request
        algorithm_config = DispatchAlgorithmConfig.objects.create(
            name='test_algorithm',
            is_active=True,
            priority=1
        )
        
        dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            status=DispatchRequest.Status.ASSIGNED,
            assigned_vehicle=self.vehicle,
            algorithm_used='test_algorithm'
        )
        
        tracking_data = RideTrackingService.get_ride_tracking_data(str(self.ride.id))
        
        self.assertIsNotNone(tracking_data)
        self.assertIn('ride', tracking_data)
        self.assertIn('rider', tracking_data)
        self.assertIn('vehicle', tracking_data)
        self.assertIn('dispatch_info', tracking_data)
        
        self.assertEqual(tracking_data['ride']['id'], str(self.ride.id))
        self.assertEqual(tracking_data['vehicle']['license_plate'], self.vehicle.license_plate)
    
    def test_calculate_eta(self):
        """Test ETA calculation."""
        eta = RideTrackingService.calculate_eta(
            37.7749, -122.4194,  # Vehicle location
            37.7849, -122.4094   # Pickup location
        )
        
        self.assertIn('distance_km', eta)
        self.assertIn('eta_minutes', eta)
        self.assertIn('arrival_time', eta)
        self.assertGreater(eta['eta_minutes'], 0)


class FleetMonitoringServiceTest(WebSocketTestCase):
    """Test FleetMonitoringService functionality."""
    
    def test_get_fleet_summary(self):
        """Test getting fleet summary statistics."""
        summary = FleetMonitoringService.get_fleet_summary()
        
        self.assertIn('total_vehicles', summary)
        self.assertIn('idle_vehicles', summary)
        self.assertIn('utilization_rate', summary)
        self.assertIn('availability_rate', summary)
        
        self.assertEqual(summary['total_vehicles'], 1)  # We have one test vehicle
        self.assertEqual(summary['idle_vehicles'], 1)   # Vehicle is idle
    
    def test_get_vehicle_list(self):
        """Test getting vehicle list."""
        vehicles = FleetMonitoringService.get_vehicle_list()
        
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0]['license_plate'], self.vehicle.license_plate)
        self.assertIn('telemetry', vehicles[0])
    
    def test_get_vehicle_list_with_filter(self):
        """Test getting filtered vehicle list."""
        vehicles = FleetMonitoringService.get_vehicle_list(status_filter='idle')
        
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0]['status'], 'idle')
    
    def test_get_maintenance_alerts(self):
        """Test getting maintenance alerts."""
        # Set vehicle to need maintenance
        self.vehicle.battery_level = 15  # Low battery
        self.vehicle.save()
        
        alerts = FleetMonitoringService.get_maintenance_alerts()
        
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0]['alert_type'], 'low_battery')


class FleetAnalyticsTest(WebSocketTestCase):
    """Test FleetAnalytics functionality."""
    
    def test_get_real_time_metrics(self):
        """Test getting real-time fleet metrics."""
        metrics = FleetAnalytics.get_real_time_metrics()
        
        self.assertIn('fleet_size', metrics)
        self.assertIn('status_distribution', metrics)
        self.assertIn('utilization_rate', metrics)
        self.assertIn('battery_alerts', metrics)
        
        self.assertEqual(metrics['fleet_size'], 1)
        self.assertEqual(metrics['status_distribution']['idle'], 1)
    
    def test_get_vehicle_performance_metrics(self):
        """Test getting vehicle performance metrics."""
        # Create some telemetry data
        VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=37.7749,
            longitude=-122.4194,
            speed=25.0,
            heading=90.0,
            battery_level=80
        )
        
        metrics = FleetAnalytics.get_vehicle_performance_metrics(str(self.vehicle.id))
        
        self.assertIsNotNone(metrics)
        self.assertIn('performance', metrics)
        self.assertIn('current_status', metrics)
        self.assertEqual(metrics['vehicle_id'], str(self.vehicle.id))
    
    def test_get_fleet_health_score(self):
        """Test calculating fleet health score."""
        health_score = FleetAnalytics.get_fleet_health_score()
        
        self.assertIn('health_score', health_score)
        self.assertIn('factors', health_score)
        self.assertIn('vehicle_counts', health_score)
        
        self.assertGreaterEqual(health_score['health_score'], 0)
        self.assertLessEqual(health_score['health_score'], 100)


class FleetAlertManagerTest(WebSocketTestCase):
    """Test FleetAlertManager functionality."""
    
    def test_check_and_send_alerts_low_battery(self):
        """Test checking and sending low battery alerts."""
        # Set vehicle to critical battery level
        self.vehicle.battery_level = 5
        self.vehicle.save()
        
        with patch('realtime.fleet_monitoring.notifier') as mock_notifier:
            alerts = FleetAlertManager.check_and_send_alerts()
            
            self.assertGreater(len(alerts), 0)
            self.assertEqual(alerts[0]['alert_type'], 'critical_battery')
            mock_notifier.send_fleet_update.assert_called()
    
    def test_send_fleet_status_broadcast(self):
        """Test sending fleet status broadcast."""
        with patch('realtime.fleet_monitoring.notifier') as mock_notifier:
            result = FleetAlertManager.send_fleet_status_broadcast()
            
            self.assertIn('metrics', result)
            self.assertIn('health_score', result)
            mock_notifier.send_fleet_update.assert_called_once()


class WebSocketIntegrationTest(TransactionTestCase):
    """Integration tests for WebSocket functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='testpass123',
            phone_number='+1234567890',
            role=User.Role.RIDER
        )
        
        self.operator = User.objects.create_user(
            username='operator1',
            email='operator1@example.com',
            password='testpass123',
            phone_number='+1234567891',
            role=User.Role.OPERATOR
        )
        
        self.ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            pickup_address='123 Main St, San Francisco, CA',
            destination_address='456 Oak St, San Francisco, CA',
            status=Ride.Status.REQUESTED
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST123',
            model='Tesla Model 3',
            year=2023,
            battery_level=80,
            status=Vehicle.Status.IDLE,
            current_latitude=37.7749,
            current_longitude=-122.4194
        )
    
    async def test_ride_tracking_message_flow(self):
        """Test complete message flow for ride tracking."""
        communicator = WebsocketCommunicator(
            RideTrackingConsumer.as_asgi(),
            f"/ws/rides/{self.ride.id}/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Receive initial ride data
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'ride_status')
        
        # Test ping-pong
        await communicator.send_json_to({'type': 'ping'})
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        
        await communicator.disconnect()
    
    async def test_fleet_monitoring_message_flow(self):
        """Test complete message flow for fleet monitoring."""
        communicator = WebsocketCommunicator(
            FleetMonitoringConsumer.as_asgi(),
            "/ws/fleet/"
        )
        
        communicator.scope['user'] = self.operator
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Receive initial fleet data
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'fleet_status')
        self.assertIn('summary', response['data'])
        
        # Test vehicle filtering
        await communicator.send_json_to({
            'type': 'vehicle_filter',
            'status': 'idle'
        })
        
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'filtered_vehicles')
        
        await communicator.disconnect()
    
    async def test_notification_message_flow(self):
        """Test notification message flow."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Test ping
        await communicator.send_json_to({'type': 'ping'})
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        
        await communicator.disconnect()


class WebSocketErrorHandlingTest(WebSocketTestCase):
    """Test WebSocket error handling."""
    
    async def test_invalid_json_handling(self):
        """Test handling of invalid JSON messages."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send invalid JSON
        await communicator.send_to(text_data="invalid json")
        
        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('Invalid JSON format', response['data']['message'])
        
        await communicator.disconnect()
    
    async def test_unknown_message_type_handling(self):
        """Test handling of unknown message types."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        communicator.scope['user'] = self.rider
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send unknown message type
        await communicator.send_json_to({'type': 'unknown_type'})
        
        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('Unknown message type', response['data']['message'])
        
        await communicator.disconnect()


class WebSocketPerformanceTest(WebSocketTestCase):
    """Test WebSocket performance and scalability."""
    
    async def test_multiple_connections(self):
        """Test handling multiple WebSocket connections."""
        communicators = []
        
        # Create multiple connections
        for i in range(5):
            communicator = WebsocketCommunicator(
                NotificationConsumer.as_asgi(),
                "/ws/notifications/"
            )
            communicator.scope['user'] = self.rider
            
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)
            communicators.append(communicator)
        
        # Send messages to all connections
        for communicator in communicators:
            await communicator.send_json_to({'type': 'ping'})
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'pong')
        
        # Disconnect all
        for communicator in communicators:
            await communicator.disconnect()
    
    def test_large_data_handling(self):
        """Test handling of large data payloads."""
        from .services import FleetMonitoringService
        
        # Create many vehicles to test large payload
        for i in range(50):
            Vehicle.objects.create(
                license_plate=f'TEST{i:03d}',
                model='Tesla Model 3',
                year=2023,
                battery_level=80,
                status=Vehicle.Status.IDLE,
                current_latitude=37.7749 + (i * 0.001),
                current_longitude=-122.4194 + (i * 0.001)
            )
        
        # Test getting large vehicle list
        vehicles = FleetMonitoringService.get_vehicle_list(limit=100)
        
        self.assertGreater(len(vehicles), 50)
        self.assertLessEqual(len(vehicles), 100)  # Should respect limit