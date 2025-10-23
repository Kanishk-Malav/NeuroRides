"""
Tests for fleet management Celery tasks.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .tasks import (
    process_vehicle_telemetry,
    schedule_maintenance_checks,
    update_vehicle_locations,
    check_vehicle_health,
    generate_maintenance_alerts,
    cleanup_old_telemetry_data,
    calculate_vehicle_utilization,
    optimize_fleet_distribution
)
from .models import Vehicle, VehicleTelemetry, MaintenanceSchedule


class FleetTasksTestCase(TestCase):
    """Test case for fleet management tasks."""
    
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
        
        self.telemetry_data = {
            'latitude': 37.7849,
            'longitude': -122.4094,
            'speed': 25.5,
            'battery_level': 75,
            'fuel_level': None,
            'engine_temperature': 85,
            'odometer_reading': 15000,
            'diagnostic_codes': []
        }
    
    def test_process_vehicle_telemetry_success(self):
        """Test successful vehicle telemetry processing."""
        # Execute task
        result = process_vehicle_telemetry(str(self.vehicle.id), self.telemetry_data)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['vehicle_id'], str(self.vehicle.id))
        self.assertIn('telemetry_id', result)
        self.assertEqual(len(result['alerts']), 0)
        
        # Verify telemetry record was created
        telemetry = VehicleTelemetry.objects.get(id=result['telemetry_id'])
        self.assertEqual(telemetry.vehicle, self.vehicle)
        self.assertEqual(telemetry.latitude, 37.7849)
        self.assertEqual(telemetry.battery_level, 75)
        
        # Verify vehicle was updated
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.current_latitude, 37.7849)
        self.assertEqual(self.vehicle.battery_level, 75)
    
    def test_process_vehicle_telemetry_low_battery_alert(self):
        """Test vehicle telemetry processing with low battery alert."""
        # Set low battery level
        self.telemetry_data['battery_level'] = 10
        
        # Execute task
        result = process_vehicle_telemetry(str(self.vehicle.id), self.telemetry_data)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('low_battery', result['alerts'])
        
        # Verify vehicle battery level was updated
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.battery_level, 10)
    
    def test_process_vehicle_telemetry_high_temperature_alert(self):
        """Test vehicle telemetry processing with high temperature alert."""
        # Set high engine temperature
        self.telemetry_data['engine_temperature'] = 110
        
        # Execute task
        result = process_vehicle_telemetry(str(self.vehicle.id), self.telemetry_data)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('high_temperature', result['alerts'])
    
    def test_process_vehicle_telemetry_diagnostic_error(self):
        """Test vehicle telemetry processing with diagnostic errors."""
        # Set diagnostic codes
        self.telemetry_data['diagnostic_codes'] = ['P0001', 'P0002']
        
        # Execute task
        result = process_vehicle_telemetry(str(self.vehicle.id), self.telemetry_data)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('diagnostic_error', result['alerts'])
        
        # Verify vehicle status was changed to maintenance
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'maintenance')
    
    def test_process_vehicle_telemetry_vehicle_not_found(self):
        """Test vehicle telemetry processing with non-existent vehicle."""
        # Execute task with non-existent vehicle ID
        result = process_vehicle_telemetry('non-existent-id', self.telemetry_data)
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Vehicle not found')
    
    @patch('fleet.tasks.MaintenanceService')
    def test_schedule_maintenance_checks(self, mock_maintenance_service):
        """Test maintenance scheduling."""
        # Mock service response
        mock_service_instance = mock_maintenance_service.return_value
        mock_service_instance.schedule_routine_maintenance.return_value = {
            'success': True,
            'scheduled': 5,
            'vehicles_checked': 20
        }
        
        # Execute task
        result = schedule_maintenance_checks()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['scheduled'], 5)
        
        # Verify service was called
        mock_service_instance.schedule_routine_maintenance.assert_called_once()
    
    def test_update_vehicle_locations(self):
        """Test vehicle location updates."""
        # Create a stale vehicle (last seen > 10 minutes ago)
        stale_vehicle = Vehicle.objects.create(
            license_plate='STALE123',
            make='Tesla',
            model='Model S',
            vehicle_type='sedan',
            status='assigned',
            current_latitude=37.7749,
            current_longitude=-122.4194,
            battery_level=60,
            is_active=True,
            last_seen=timezone.now() - timedelta(minutes=15)
        )
        
        # Execute task
        result = update_vehicle_locations()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['stale_vehicles'], 1)
        self.assertEqual(len(result['alerts']), 1)
        
        # Verify alert details
        alert = result['alerts'][0]
        self.assertEqual(alert['vehicle_id'], str(stale_vehicle.id))
        self.assertEqual(alert['alert_type'], 'communication_lost')
    
    @patch('fleet.tasks.FleetManagementService')
    def test_check_vehicle_health(self, mock_fleet_service):
        """Test vehicle health checks."""
        # Mock service response
        mock_service_instance = mock_fleet_service.return_value
        mock_service_instance.check_fleet_health.return_value = {
            'total_vehicles': 10,
            'healthy_vehicles': 8,
            'vehicle_health': [
                {
                    'vehicle_id': str(self.vehicle.id),
                    'license_plate': 'TEST123',
                    'health_score': 60,  # Below threshold
                    'issues': ['Low battery', 'Overdue maintenance']
                }
            ]
        }
        
        # Execute task
        result = check_vehicle_health()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['vehicles_checked'], 10)
        self.assertEqual(result['healthy_vehicles'], 8)
        self.assertEqual(len(result['alerts']), 1)
        
        # Verify alert details
        alert = result['alerts'][0]
        self.assertEqual(alert['health_score'], 60)
        self.assertEqual(alert['severity'], 'medium')
    
    @patch('fleet.tasks.MaintenanceService')
    def test_generate_maintenance_alerts(self, mock_maintenance_service):
        """Test maintenance alert generation."""
        # Mock service response
        mock_service_instance = mock_maintenance_service.return_value
        mock_service_instance.generate_maintenance_alerts.return_value = [
            {
                'vehicle_id': str(self.vehicle.id),
                'alert_type': 'overdue_maintenance',
                'priority': 'high',
                'message': 'Vehicle overdue for maintenance'
            },
            {
                'vehicle_id': 'other-vehicle-id',
                'alert_type': 'scheduled_maintenance',
                'priority': 'medium',
                'message': 'Maintenance scheduled for tomorrow'
            }
        ]
        
        # Execute task
        result = generate_maintenance_alerts()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['total_alerts'], 2)
        self.assertEqual(result['critical_alerts'], 0)  # No critical alerts in mock data
        
        # Verify service was called
        mock_service_instance.generate_maintenance_alerts.assert_called_once()
    
    def test_cleanup_old_telemetry_data(self):
        """Test cleanup of old telemetry data."""
        # Create old telemetry data (older than 30 days)
        old_telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=37.7749,
            longitude=-122.4194,
            speed=20.0,
            battery_level=70,
            timestamp=timezone.now() - timedelta(days=35)
        )
        
        # Create recent telemetry data
        recent_telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=37.7849,
            longitude=-122.4094,
            speed=25.0,
            battery_level=75,
            timestamp=timezone.now() - timedelta(days=5)
        )
        
        # Execute task
        result = cleanup_old_telemetry_data()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_records'], 1)
        
        # Verify old data was deleted but recent data remains
        self.assertFalse(VehicleTelemetry.objects.filter(id=old_telemetry.id).exists())
        self.assertTrue(VehicleTelemetry.objects.filter(id=recent_telemetry.id).exists())
    
    @patch('fleet.tasks.FleetManagementService')
    def test_calculate_vehicle_utilization(self, mock_fleet_service):
        """Test vehicle utilization calculation."""
        # Mock service response
        mock_service_instance = mock_fleet_service.return_value
        mock_service_instance.calculate_utilization_metrics.return_value = {
            'fleet_utilization_rate': 0.75,
            'vehicle_utilization': [
                {
                    'vehicle_id': str(self.vehicle.id),
                    'utilization_rate': 0.25  # Low utilization
                },
                {
                    'vehicle_id': 'other-vehicle-id',
                    'utilization_rate': 0.85  # Good utilization
                }
            ]
        }
        
        # Execute task
        result = calculate_vehicle_utilization()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['fleet_utilization_rate'], 0.75)
        self.assertEqual(result['vehicles_analyzed'], 2)
        self.assertEqual(result['low_utilization_vehicles'], 1)
        
        # Verify service was called
        mock_service_instance.calculate_utilization_metrics.assert_called_once()
    
    @patch('fleet.tasks.FleetManagementService')
    def test_optimize_fleet_distribution(self, mock_fleet_service):
        """Test fleet distribution optimization."""
        # Mock service response
        mock_service_instance = mock_fleet_service.return_value
        mock_service_instance.optimize_fleet_distribution.return_value = {
            'recommendations': [
                {
                    'vehicle_id': str(self.vehicle.id),
                    'current_location': 'Downtown',
                    'recommended_location': 'Airport',
                    'reason': 'Higher demand expected'
                }
            ],
            'potential_improvement': 15.5,
            'current_efficiency': 72.3
        }
        
        # Execute task
        result = optimize_fleet_distribution()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['recommendations'], 1)
        self.assertEqual(result['potential_improvement'], 15.5)
        self.assertEqual(result['current_efficiency'], 72.3)
        
        # Verify service was called
        mock_service_instance.optimize_fleet_distribution.assert_called_once()


class FleetTaskRetryTestCase(TestCase):
    """Test case for fleet task retry logic."""
    
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
            is_active=True
        )
        
        self.telemetry_data = {
            'latitude': 37.7849,
            'longitude': -122.4094,
            'speed': 25.5,
            'battery_level': 75,
            'diagnostic_codes': []
        }
    
    def test_process_vehicle_telemetry_retry_logic(self):
        """Test vehicle telemetry processing retry logic on failure."""
        # Create a mock task with retry capability
        task_mock = MagicMock()
        task_mock.request.retries = 0
        task_mock.max_retries = 3
        task_mock.retry.side_effect = Exception("Retry called")
        
        # Mock VehicleTelemetry.objects.create to raise exception
        with patch('fleet.tasks.VehicleTelemetry.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            # Execute task and expect retry to be called
            with self.assertRaises(Exception) as context:
                process_vehicle_telemetry.__wrapped__(
                    task_mock, str(self.vehicle.id), self.telemetry_data
                )
            
            self.assertEqual(str(context.exception), "Retry called")
            task_mock.retry.assert_called_once()
    
    def test_process_vehicle_telemetry_max_retries_exceeded(self):
        """Test vehicle telemetry processing when max retries are exceeded."""
        # Create a mock task that has exceeded max retries
        task_mock = MagicMock()
        task_mock.request.retries = 3
        task_mock.max_retries = 3
        
        # Mock VehicleTelemetry.objects.create to raise exception
        with patch('fleet.tasks.VehicleTelemetry.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            # Execute task
            result = process_vehicle_telemetry.__wrapped__(
                task_mock, str(self.vehicle.id), self.telemetry_data
            )
            
            # Verify result indicates failure
            self.assertFalse(result['success'])
            self.assertIn('Task failed after retries', result['error'])


class FleetTaskIntegrationTestCase(TestCase):
    """Integration tests for fleet management tasks."""
    
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
    
    def test_telemetry_processing_and_cleanup_integration(self):
        """Test integration between telemetry processing and cleanup."""
        # Process telemetry data
        telemetry_data = {
            'latitude': 37.7849,
            'longitude': -122.4094,
            'speed': 25.5,
            'battery_level': 75,
            'diagnostic_codes': []
        }
        
        # Process telemetry
        result = process_vehicle_telemetry(str(self.vehicle.id), telemetry_data)
        self.assertTrue(result['success'])
        
        # Verify telemetry record was created
        telemetry = VehicleTelemetry.objects.get(id=result['telemetry_id'])
        self.assertEqual(telemetry.vehicle, self.vehicle)
        
        # Make telemetry record old
        telemetry.timestamp = timezone.now() - timedelta(days=35)
        telemetry.save()
        
        # Run cleanup
        cleanup_result = cleanup_old_telemetry_data()
        self.assertTrue(cleanup_result['success'])
        self.assertEqual(cleanup_result['deleted_records'], 1)
        
        # Verify telemetry record was deleted
        self.assertFalse(VehicleTelemetry.objects.filter(id=telemetry.id).exists())
    
    @patch('fleet.tasks.FleetManagementService')
    @patch('fleet.tasks.MaintenanceService')
    def test_health_check_and_maintenance_integration(self, mock_maintenance_service, mock_fleet_service):
        """Test integration between health checks and maintenance scheduling."""
        # Mock fleet service to return unhealthy vehicle
        mock_fleet_instance = mock_fleet_service.return_value
        mock_fleet_instance.check_fleet_health.return_value = {
            'total_vehicles': 1,
            'healthy_vehicles': 0,
            'vehicle_health': [
                {
                    'vehicle_id': str(self.vehicle.id),
                    'license_plate': 'TEST123',
                    'health_score': 45,  # Unhealthy
                    'issues': ['Low battery', 'Overdue maintenance']
                }
            ]
        }
        
        # Mock maintenance service
        mock_maintenance_instance = mock_maintenance_service.return_value
        mock_maintenance_instance.schedule_routine_maintenance.return_value = {
            'success': True,
            'scheduled': 1,
            'vehicles_checked': 1
        }
        
        # Run health check
        health_result = check_vehicle_health()
        self.assertTrue(health_result['success'])
        self.assertEqual(len(health_result['alerts']), 1)
        
        # Run maintenance scheduling
        maintenance_result = schedule_maintenance_checks()
        self.assertTrue(maintenance_result['success'])
        self.assertEqual(maintenance_result['scheduled'], 1)
        
        # Verify both services were called
        mock_fleet_instance.check_fleet_health.assert_called_once()
        mock_maintenance_instance.schedule_routine_maintenance.assert_called_once()