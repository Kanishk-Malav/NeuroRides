"""
Tests for real-time WebSocket Celery tasks.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .tasks import (
    periodic_fleet_health_check,
    broadcast_fleet_status,
    check_fleet_alerts,
    calculate_fleet_metrics,
    process_vehicle_telemetry_batch,
    cleanup_old_websocket_data
)
from fleet.models import Vehicle, VehicleTelemetry


class RealtimeTasksTestCase(TestCase):
    """Test case for real-time WebSocket tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST123',
            make='Tesla',
            model='Model 3',
            vehicle_type='sedan',
            status='idle',
            current_latitude=37.7749,
            current_longitude=-122.4194,
            battery_level=80,
            is_active=True,
            last_seen=timezone.now()
        )
    
    @patch('realtime.tasks.run_fleet_health_check')
    def test_periodic_fleet_health_check_success(self, mock_health_check):
        """Test successful periodic fleet health check."""
        # Mock health check response
        mock_health_check.return_value = {
            'status': 'healthy',
            'total_vehicles': 10,
            'healthy_vehicles': 9,
            'unhealthy_vehicles': 1,
            'alerts': []
        }
        
        # Execute task
        result = periodic_fleet_health_check()
        
        # Verify result
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['total_vehicles'], 10)
        
        # Verify health check was called
        mock_health_check.assert_called_once()
    
    @patch('realtime.tasks.run_fleet_health_check')
    def test_periodic_fleet_health_check_failure(self, mock_health_check):
        """Test periodic fleet health check with failure."""
        # Mock health check to raise exception
        mock_health_check.side_effect = Exception("Health check failed")
        
        # Execute task
        result = periodic_fleet_health_check()
        
        # Verify result
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Health check failed')
    
    @patch('realtime.tasks.FleetAlertManager')
    def test_broadcast_fleet_status_success(self, mock_alert_manager):
        """Test successful fleet status broadcast."""
        # Mock alert manager response
        mock_alert_manager.send_fleet_status_broadcast.return_value = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'clients_notified': 5
        }
        
        # Execute task
        result = broadcast_fleet_status()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('timestamp', result)
        
        # Verify broadcast was called
        mock_alert_manager.send_fleet_status_broadcast.assert_called_once()
    
    @patch('realtime.tasks.FleetAlertManager')
    def test_broadcast_fleet_status_failure(self, mock_alert_manager):
        """Test fleet status broadcast with failure."""
        # Mock alert manager to raise exception
        mock_alert_manager.send_fleet_status_broadcast.side_effect = Exception("Broadcast failed")
        
        # Execute task
        result = broadcast_fleet_status()
        
        # Verify result
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Broadcast failed')
    
    @patch('realtime.tasks.FleetAlertManager')
    def test_check_fleet_alerts_success(self, mock_alert_manager):
        """Test successful fleet alerts check."""
        # Mock alert manager response
        mock_alert_manager.check_and_send_alerts.return_value = [
            {
                'vehicle_id': str(self.vehicle.id),
                'alert_type': 'low_battery',
                'severity': 'medium',
                'message': 'Vehicle battery is low'
            },
            {
                'vehicle_id': 'other-vehicle-id',
                'alert_type': 'maintenance_due',
                'severity': 'low',
                'message': 'Vehicle maintenance is due'
            }
        ]
        
        # Execute task
        result = check_fleet_alerts()
        
        # Verify result
        self.assertEqual(result['alerts_sent'], 2)
        self.assertEqual(len(result['alerts']), 2)
        
        # Verify alert manager was called
        mock_alert_manager.check_and_send_alerts.assert_called_once()
    
    @patch('realtime.tasks.FleetAlertManager')
    def test_check_fleet_alerts_failure(self, mock_alert_manager):
        """Test fleet alerts check with failure."""
        # Mock alert manager to raise exception
        mock_alert_manager.check_and_send_alerts.side_effect = Exception("Alert check failed")
        
        # Execute task
        result = check_fleet_alerts()
        
        # Verify result
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Alert check failed')
    
    @patch('realtime.tasks.FleetAnalytics')
    @patch('realtime.tasks.notify_system_alert')
    def test_calculate_fleet_metrics_healthy(self, mock_notify_alert, mock_analytics):
        """Test fleet metrics calculation with healthy fleet."""
        # Mock analytics responses
        mock_analytics.get_real_time_metrics.return_value = {
            'active_vehicles': 10,
            'utilization_rate': 0.85,
            'average_response_time': 3.5
        }
        
        mock_analytics.get_fleet_health_score.return_value = {
            'health_score': 85.5,
            'factors': {
                'vehicle_availability': 0.9,
                'maintenance_status': 0.8,
                'performance': 0.85
            }
        }
        
        # Execute task
        result = calculate_fleet_metrics()
        
        # Verify result
        self.assertIn('metrics', result)
        self.assertIn('health_score', result)
        self.assertEqual(result['health_score']['health_score'], 85.5)
        
        # Verify no alert was sent (health score > 70)
        mock_notify_alert.assert_not_called()
        
        # Verify analytics methods were called
        mock_analytics.get_real_time_metrics.assert_called_once()
        mock_analytics.get_fleet_health_score.assert_called_once()
    
    @patch('realtime.tasks.FleetAnalytics')
    @patch('realtime.tasks.notify_system_alert')
    def test_calculate_fleet_metrics_unhealthy(self, mock_notify_alert, mock_analytics):
        """Test fleet metrics calculation with unhealthy fleet."""
        # Mock analytics responses with low health score
        mock_analytics.get_real_time_metrics.return_value = {
            'active_vehicles': 5,
            'utilization_rate': 0.45,
            'average_response_time': 8.2
        }
        
        mock_analytics.get_fleet_health_score.return_value = {
            'health_score': 65.0,  # Below threshold
            'factors': {
                'vehicle_availability': 0.5,
                'maintenance_status': 0.7,
                'performance': 0.75
            }
        }
        
        # Execute task
        result = calculate_fleet_metrics()
        
        # Verify result
        self.assertIn('metrics', result)
        self.assertIn('health_score', result)
        self.assertEqual(result['health_score']['health_score'], 65.0)
        
        # Verify alert was sent (health score < 70)
        mock_notify_alert.assert_called_once()
        call_args = mock_notify_alert.call_args[0]
        self.assertIn('Fleet health score is low', call_args[0])
    
    @patch('realtime.tasks.VehicleTelemetryProcessor')
    def test_process_vehicle_telemetry_batch_success(self, mock_processor):
        """Test successful vehicle telemetry batch processing."""
        # Mock telemetry data
        telemetry_batch = [
            {
                'vehicle_id': str(self.vehicle.id),
                'latitude': 37.7849,
                'longitude': -122.4094,
                'speed': 25.5,
                'battery_level': 75
            },
            {
                'vehicle_id': 'other-vehicle-id',
                'latitude': 37.7949,
                'longitude': -122.3994,
                'speed': 30.0,
                'battery_level': 80
            }
        ]
        
        # Mock processor to succeed for all telemetry
        mock_processor.process_telemetry_update.return_value = None
        
        # Execute task
        result = process_vehicle_telemetry_batch(telemetry_batch)
        
        # Verify result
        self.assertEqual(result['processed'], 2)
        self.assertEqual(result['errors'], 0)
        
        # Verify processor was called for each telemetry update
        self.assertEqual(mock_processor.process_telemetry_update.call_count, 2)
    
    @patch('realtime.tasks.VehicleTelemetryProcessor')
    def test_process_vehicle_telemetry_batch_with_errors(self, mock_processor):
        """Test vehicle telemetry batch processing with some errors."""
        # Mock telemetry data
        telemetry_batch = [
            {
                'vehicle_id': str(self.vehicle.id),
                'latitude': 37.7849,
                'longitude': -122.4094,
                'speed': 25.5,
                'battery_level': 75
            },
            {
                'vehicle_id': 'invalid-vehicle-id',
                'latitude': 37.7949,
                'longitude': -122.3994,
                'speed': 30.0,
                'battery_level': 80
            }
        ]
        
        # Mock processor to succeed for first, fail for second
        def side_effect(telemetry_data):
            if telemetry_data['vehicle_id'] == 'invalid-vehicle-id':
                raise Exception("Vehicle not found")
            return None
        
        mock_processor.process_telemetry_update.side_effect = side_effect
        
        # Execute task
        result = process_vehicle_telemetry_batch(telemetry_batch)
        
        # Verify result
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['errors'], 1)
        self.assertEqual(len(result['error_details']), 1)
        self.assertEqual(result['error_details'][0]['vehicle_id'], 'invalid-vehicle-id')
    
    def test_cleanup_old_websocket_data(self):
        """Test cleanup of old WebSocket-related data."""
        # Create old telemetry data (older than 7 days)
        old_telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=37.7749,
            longitude=-122.4194,
            speed=20.0,
            battery_level=70,
            timestamp=timezone.now() - timedelta(days=10)
        )
        
        # Create recent telemetry data
        recent_telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=37.7849,
            longitude=-122.4094,
            speed=25.0,
            battery_level=75,
            timestamp=timezone.now() - timedelta(days=3)
        )
        
        # Execute task
        result = cleanup_old_websocket_data()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_telemetry_records'], 1)
        
        # Verify old data was deleted but recent data remains
        self.assertFalse(VehicleTelemetry.objects.filter(id=old_telemetry.id).exists())
        self.assertTrue(VehicleTelemetry.objects.filter(id=recent_telemetry.id).exists())
    
    def test_cleanup_old_websocket_data_failure(self):
        """Test cleanup of old WebSocket data with failure."""
        # Mock VehicleTelemetry.objects.filter to raise exception
        with patch('realtime.tasks.VehicleTelemetry.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            # Execute task
            result = cleanup_old_websocket_data()
            
            # Verify result
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Database error')


class RealtimeTaskIntegrationTestCase(TestCase):
    """Integration tests for real-time tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle1 = Vehicle.objects.create(
            license_plate='TEST123',
            make='Tesla',
            model='Model 3',
            vehicle_type='sedan',
            status='idle',
            current_latitude=37.7749,
            current_longitude=-122.4194,
            battery_level=80,
            is_active=True,
            last_seen=timezone.now()
        )
        
        self.vehicle2 = Vehicle.objects.create(
            license_plate='TEST456',
            make='Tesla',
            model='Model S',
            vehicle_type='sedan',
            status='assigned',
            current_latitude=37.7849,
            current_longitude=-122.4094,
            battery_level=15,  # Low battery
            is_active=True,
            last_seen=timezone.now()
        )
    
    @patch('realtime.tasks.VehicleTelemetryProcessor')
    def test_telemetry_processing_and_cleanup_integration(self, mock_processor):
        """Test integration between telemetry processing and cleanup."""
        # Mock processor
        mock_processor.process_telemetry_update.return_value = None
        
        # Process telemetry batch
        telemetry_batch = [
            {
                'vehicle_id': str(self.vehicle1.id),
                'latitude': 37.7849,
                'longitude': -122.4094,
                'speed': 25.5,
                'battery_level': 75
            }
        ]
        
        # Process telemetry
        telemetry_result = process_vehicle_telemetry_batch(telemetry_batch)
        self.assertEqual(telemetry_result['processed'], 1)
        
        # Create old telemetry record manually for cleanup test
        old_telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle1,
            latitude=37.7749,
            longitude=-122.4194,
            speed=20.0,
            battery_level=70,
            timestamp=timezone.now() - timedelta(days=10)
        )
        
        # Run cleanup
        cleanup_result = cleanup_old_websocket_data()
        self.assertTrue(cleanup_result['success'])
        self.assertEqual(cleanup_result['deleted_telemetry_records'], 1)
        
        # Verify old telemetry was deleted
        self.assertFalse(VehicleTelemetry.objects.filter(id=old_telemetry.id).exists())
    
    @patch('realtime.tasks.FleetAnalytics')
    @patch('realtime.tasks.FleetAlertManager')
    @patch('realtime.tasks.notify_system_alert')
    def test_metrics_and_alerts_integration(self, mock_notify_alert, mock_alert_manager, mock_analytics):
        """Test integration between metrics calculation and alert checking."""
        # Mock analytics for unhealthy fleet
        mock_analytics.get_real_time_metrics.return_value = {
            'active_vehicles': 2,
            'utilization_rate': 0.5,
            'average_response_time': 6.0
        }
        
        mock_analytics.get_fleet_health_score.return_value = {
            'health_score': 60.0,  # Unhealthy
            'factors': {
                'vehicle_availability': 0.6,
                'maintenance_status': 0.5,
                'performance': 0.7
            }
        }
        
        # Mock alert manager
        mock_alert_manager.check_and_send_alerts.return_value = [
            {
                'vehicle_id': str(self.vehicle2.id),
                'alert_type': 'low_battery',
                'severity': 'high',
                'message': 'Vehicle battery critically low'
            }
        ]
        
        # Calculate metrics (should trigger system alert)
        metrics_result = calculate_fleet_metrics()
        self.assertIn('health_score', metrics_result)
        self.assertEqual(metrics_result['health_score']['health_score'], 60.0)
        
        # Verify system alert was sent for low health score
        mock_notify_alert.assert_called_once()
        
        # Check fleet alerts
        alerts_result = check_fleet_alerts()
        self.assertEqual(alerts_result['alerts_sent'], 1)
        
        # Verify alert manager was called
        mock_alert_manager.check_and_send_alerts.assert_called_once()
    
    @patch('realtime.tasks.run_fleet_health_check')
    @patch('realtime.tasks.FleetAlertManager')
    def test_health_check_and_broadcast_integration(self, mock_alert_manager, mock_health_check):
        """Test integration between health check and status broadcast."""
        # Mock health check
        mock_health_check.return_value = {
            'status': 'degraded',
            'total_vehicles': 2,
            'healthy_vehicles': 1,
            'unhealthy_vehicles': 1,
            'alerts': [
                {
                    'vehicle_id': str(self.vehicle2.id),
                    'issue': 'low_battery'
                }
            ]
        }
        
        # Mock broadcast
        mock_alert_manager.send_fleet_status_broadcast.return_value = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'clients_notified': 3
        }
        
        # Run health check
        health_result = periodic_fleet_health_check()
        self.assertEqual(health_result['status'], 'degraded')
        self.assertEqual(health_result['unhealthy_vehicles'], 1)
        
        # Run status broadcast
        broadcast_result = broadcast_fleet_status()
        self.assertTrue(broadcast_result['success'])
        
        # Verify both functions were called
        mock_health_check.assert_called_once()
        mock_alert_manager.send_fleet_status_broadcast.assert_called_once()


class RealtimeTaskPerformanceTestCase(TestCase):
    """Performance tests for real-time tasks."""
    
    def setUp(self):
        """Set up test data."""
        # Create multiple vehicles for performance testing
        self.vehicles = []
        for i in range(10):
            vehicle = Vehicle.objects.create(
                license_plate=f'TEST{i:03d}',
                make='Tesla',
                model='Model 3',
                vehicle_type='sedan',
                status='idle',
                current_latitude=37.7749 + (i * 0.001),
                current_longitude=-122.4194 + (i * 0.001),
                battery_level=80 - (i * 2),
                is_active=True,
                last_seen=timezone.now()
            )
            self.vehicles.append(vehicle)
    
    @patch('realtime.tasks.VehicleTelemetryProcessor')
    def test_large_telemetry_batch_processing(self, mock_processor):
        """Test processing of large telemetry batches."""
        # Mock processor
        mock_processor.process_telemetry_update.return_value = None
        
        # Create large telemetry batch
        telemetry_batch = []
        for vehicle in self.vehicles:
            for j in range(10):  # 10 updates per vehicle
                telemetry_batch.append({
                    'vehicle_id': str(vehicle.id),
                    'latitude': vehicle.current_latitude + (j * 0.0001),
                    'longitude': vehicle.current_longitude + (j * 0.0001),
                    'speed': 20.0 + j,
                    'battery_level': vehicle.battery_level - j
                })
        
        # Process batch (100 telemetry updates)
        result = process_vehicle_telemetry_batch(telemetry_batch)
        
        # Verify all updates were processed
        self.assertEqual(result['processed'], 100)
        self.assertEqual(result['errors'], 0)
        
        # Verify processor was called for each update
        self.assertEqual(mock_processor.process_telemetry_update.call_count, 100)
    
    def test_cleanup_performance_with_large_dataset(self):
        """Test cleanup performance with large dataset."""
        # Create many old telemetry records
        old_telemetry_records = []
        for vehicle in self.vehicles:
            for j in range(50):  # 50 records per vehicle
                telemetry = VehicleTelemetry.objects.create(
                    vehicle=vehicle,
                    latitude=vehicle.current_latitude,
                    longitude=vehicle.current_longitude,
                    speed=20.0,
                    battery_level=70,
                    timestamp=timezone.now() - timedelta(days=10 + j)
                )
                old_telemetry_records.append(telemetry)
        
        # Run cleanup
        result = cleanup_old_websocket_data()
        
        # Verify cleanup was successful
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_telemetry_records'], 500)  # 10 vehicles * 50 records
        
        # Verify all old records were deleted
        for telemetry in old_telemetry_records:
            self.assertFalse(VehicleTelemetry.objects.filter(id=telemetry.id).exists())