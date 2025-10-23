"""
Tests for fleet management app.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
import uuid

from .models import Vehicle, VehicleTelemetry, MaintenanceRecord
from .services import MaintenanceScheduler, FleetAnalytics, VehicleLocationService

User = get_user_model()


class VehicleModelTest(TestCase):
    """Test Vehicle model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle_data = {
            'license_plate': 'TEST001',
            'model': 'Tesla Model 3',
            'manufacturer': 'Tesla',
            'year': 2023,
            'vehicle_type': Vehicle.VehicleType.SEDAN,
            'current_latitude': 19.0760,
            'current_longitude': 72.8777,
            'battery_level': 85,
            'passenger_capacity': 4,
        }
    
    def test_create_vehicle(self):
        """Test vehicle creation."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        self.assertEqual(vehicle.license_plate, 'TEST001')
        self.assertEqual(vehicle.model, 'Tesla Model 3')
        self.assertEqual(vehicle.status, Vehicle.Status.OFFLINE)  # Default status
        self.assertEqual(vehicle.battery_level, 85)
        self.assertIsNotNone(vehicle.id)  # UUID should be generated
    
    def test_vehicle_string_representation(self):
        """Test vehicle string representation."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        expected = f"{vehicle.license_plate} - {vehicle.model} ({vehicle.get_status_display()})"
        self.assertEqual(str(vehicle), expected)
    
    def test_vehicle_is_available_property(self):
        """Test is_available property."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        # Should not be available initially (status is OFFLINE)
        self.assertFalse(vehicle.is_available)
        
        # Set to idle with good battery and location
        vehicle.status = Vehicle.Status.IDLE
        vehicle.battery_level = 50
        vehicle.save()
        self.assertTrue(vehicle.is_available)
        
        # Low battery should make it unavailable
        vehicle.battery_level = 15
        vehicle.save()
        self.assertFalse(vehicle.is_available)
        
        # No location should make it unavailable
        vehicle.battery_level = 50
        vehicle.current_latitude = None
        vehicle.save()
        self.assertFalse(vehicle.is_available)
    
    def test_vehicle_needs_maintenance_property(self):
        """Test needs_maintenance property."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        # Initially should not need maintenance
        self.assertFalse(vehicle.needs_maintenance)
        
        # Set maintenance due date in the past
        vehicle.next_maintenance_due = timezone.now() - timedelta(days=1)
        vehicle.save()
        self.assertTrue(vehicle.needs_maintenance)
        
        # Reset and test mileage threshold
        vehicle.next_maintenance_due = timezone.now() + timedelta(days=30)
        vehicle.mileage = 15000
        vehicle.maintenance_mileage_threshold = 10000
        vehicle.save()
        self.assertTrue(vehicle.needs_maintenance)
    
    def test_vehicle_is_online_property(self):
        """Test is_online property."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        # No last_seen should be offline
        self.assertFalse(vehicle.is_online)
        
        # Recent last_seen should be online
        vehicle.last_seen = timezone.now()
        vehicle.save()
        self.assertTrue(vehicle.is_online)
        
        # Old last_seen should be offline
        vehicle.last_seen = timezone.now() - timedelta(minutes=10)
        vehicle.save()
        self.assertFalse(vehicle.is_online)
    
    def test_update_location(self):
        """Test update_location method."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        new_lat, new_lng = 19.1000, 72.9000
        vehicle.update_location(new_lat, new_lng)
        
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.current_latitude, new_lat)
        self.assertEqual(vehicle.current_longitude, new_lng)
        self.assertIsNotNone(vehicle.last_seen)
    
    def test_vehicle_status_transitions(self):
        """Test vehicle status transition methods."""
        vehicle = Vehicle.objects.create(**self.vehicle_data)
        
        # Test assign to ride
        vehicle.assign_to_ride(None)  # No actual ride object for now
        self.assertEqual(vehicle.status, Vehicle.Status.ASSIGNED)
        
        # Test start ride
        vehicle.start_ride()
        self.assertEqual(vehicle.status, Vehicle.Status.IN_RIDE)
        
        # Test complete ride
        initial_rides = vehicle.total_rides
        initial_mileage = vehicle.mileage
        vehicle.complete_ride(ride_distance=10, ride_revenue=25.50)
        
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.IDLE)
        self.assertEqual(vehicle.total_rides, initial_rides + 1)
        self.assertEqual(vehicle.mileage, initial_mileage + 10)
        
        # Test maintenance mode
        vehicle.set_maintenance_mode()
        self.assertEqual(vehicle.status, Vehicle.Status.MAINTENANCE)
        
        # Test complete maintenance
        vehicle.complete_maintenance()
        self.assertEqual(vehicle.status, Vehicle.Status.IDLE)
        self.assertIsNotNone(vehicle.last_maintenance)


class VehicleTelemetryModelTest(TestCase):
    """Test VehicleTelemetry model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            manufacturer='Tesla',
            year=2023,
            current_latitude=19.0760,
            current_longitude=72.8777,
        )
    
    def test_create_telemetry(self):
        """Test telemetry creation."""
        telemetry = VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=19.0800,
            longitude=72.8800,
            speed=45.5,
            heading=180.0,
            battery_level=75,
            temperature=22.5,
            engine_status='running',
            passenger_count=2
        )
        
        self.assertEqual(telemetry.vehicle, self.vehicle)
        self.assertEqual(telemetry.latitude, 19.0800)
        self.assertEqual(telemetry.speed, 45.5)
        self.assertEqual(telemetry.battery_level, 75)
    
    def test_telemetry_updates_vehicle(self):
        """Test that telemetry creation updates vehicle location."""
        initial_lat = self.vehicle.current_latitude
        initial_battery = self.vehicle.battery_level
        
        VehicleTelemetry.objects.create(
            vehicle=self.vehicle,
            latitude=19.1000,
            longitude=72.9000,
            speed=30.0,
            heading=90.0,
            battery_level=80,
            engine_status='running'
        )
        
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.current_latitude, 19.1000)
        self.assertEqual(self.vehicle.current_longitude, 72.9000)
        self.assertEqual(self.vehicle.battery_level, 80)


class MaintenanceRecordModelTest(TestCase):
    """Test MaintenanceRecord model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            manufacturer='Tesla',
            year=2023,
        )
        
        self.operator = User.objects.create_user(
            username='operator',
            email='operator@test.com',
            phone_number='+1234567890',
            role=User.Role.OPERATOR,
            password='testpass123'
        )
    
    def test_create_maintenance_record(self):
        """Test maintenance record creation."""
        scheduled_date = timezone.now() + timedelta(days=1)
        
        record = MaintenanceRecord.objects.create(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=scheduled_date,
            description='Routine maintenance check',
            estimated_cost=200.00,
            technician=self.operator
        )
        
        self.assertEqual(record.vehicle, self.vehicle)
        self.assertEqual(record.status, MaintenanceRecord.Status.SCHEDULED)
        self.assertEqual(record.estimated_cost, 200.00)
        self.assertFalse(record.is_overdue)
    
    def test_maintenance_record_overdue(self):
        """Test overdue maintenance detection."""
        past_date = timezone.now() - timedelta(days=1)
        
        record = MaintenanceRecord.objects.create(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=past_date,
            description='Overdue maintenance',
            estimated_cost=200.00
        )
        
        self.assertTrue(record.is_overdue)
    
    def test_start_maintenance(self):
        """Test starting maintenance."""
        record = MaintenanceRecord.objects.create(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=timezone.now() + timedelta(days=1),
            description='Test maintenance',
            estimated_cost=200.00
        )
        
        record.start_maintenance()
        
        self.assertEqual(record.status, MaintenanceRecord.Status.IN_PROGRESS)
        self.assertIsNotNone(record.started_at)
        self.assertIsNotNone(record.mileage_at_maintenance)
        
        # Vehicle should be in maintenance mode
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.MAINTENANCE)
    
    def test_complete_maintenance(self):
        """Test completing maintenance."""
        record = MaintenanceRecord.objects.create(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=timezone.now(),
            description='Test maintenance',
            estimated_cost=200.00
        )
        
        record.start_maintenance()
        record.complete_maintenance(actual_cost=250.00, notes='Completed successfully')
        
        self.assertEqual(record.status, MaintenanceRecord.Status.COMPLETED)
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.actual_cost, 250.00)
        self.assertEqual(record.notes, 'Completed successfully')
        
        # Vehicle should be back to idle
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.IDLE)


class MaintenanceSchedulerTest(TestCase):
    """Test MaintenanceScheduler service."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            manufacturer='Tesla',
            year=2023,
            mileage=5000,
            maintenance_mileage_threshold=10000,
            next_maintenance_due=timezone.now() + timedelta(days=30)
        )
    
    def test_check_maintenance_requirements_no_maintenance_needed(self):
        """Test maintenance check when no maintenance is needed."""
        requirements = MaintenanceScheduler.check_maintenance_requirements(self.vehicle)
        
        self.assertFalse(requirements['needs_maintenance'])
        self.assertEqual(requirements['priority'], 'low')
        self.assertEqual(len(requirements['reasons']), 0)
    
    def test_check_maintenance_requirements_mileage_threshold(self):
        """Test maintenance check when mileage threshold is reached."""
        self.vehicle.mileage = 15000  # Above threshold
        self.vehicle.save()
        
        requirements = MaintenanceScheduler.check_maintenance_requirements(self.vehicle)
        
        self.assertTrue(requirements['needs_maintenance'])
        self.assertEqual(requirements['priority'], 'high')
        self.assertIn('Mileage threshold', requirements['reasons'][0])
    
    def test_check_maintenance_requirements_overdue(self):
        """Test maintenance check when maintenance is overdue."""
        self.vehicle.next_maintenance_due = timezone.now() - timedelta(days=1)
        self.vehicle.save()
        
        requirements = MaintenanceScheduler.check_maintenance_requirements(self.vehicle)
        
        self.assertTrue(requirements['needs_maintenance'])
        self.assertEqual(requirements['priority'], 'high')
        self.assertIn('overdue', requirements['reasons'][0])
    
    def test_schedule_maintenance(self):
        """Test scheduling maintenance."""
        scheduled_date = timezone.now() + timedelta(days=1)
        
        record = MaintenanceScheduler.schedule_maintenance(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=scheduled_date,
            description='Test maintenance',
            estimated_cost=200.00
        )
        
        self.assertIsInstance(record, MaintenanceRecord)
        self.assertEqual(record.vehicle, self.vehicle)
        self.assertEqual(record.status, MaintenanceRecord.Status.SCHEDULED)
    
    def test_schedule_maintenance_already_scheduled(self):
        """Test scheduling maintenance when already scheduled."""
        # Create existing maintenance
        MaintenanceRecord.objects.create(
            vehicle=self.vehicle,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            scheduled_date=timezone.now() + timedelta(days=1),
            description='Existing maintenance'
        )
        
        # Try to schedule another
        with self.assertRaises(ValueError):
            MaintenanceScheduler.schedule_maintenance(
                vehicle=self.vehicle,
                maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
                scheduled_date=timezone.now() + timedelta(days=2),
                description='New maintenance'
            )


class VehicleLocationServiceTest(TestCase):
    """Test VehicleLocationService."""
    
    def setUp(self):
        """Set up test data."""
        # Create vehicles at different locations in Mumbai
        self.vehicle1 = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            status=Vehicle.Status.IDLE,
            current_latitude=19.0760,  # Mumbai center
            current_longitude=72.8777,
            battery_level=80
        )
        
        self.vehicle2 = Vehicle.objects.create(
            license_plate='TEST002',
            model='Tesla Model S',
            status=Vehicle.Status.IDLE,
            current_latitude=19.1000,  # Slightly north
            current_longitude=72.9000,
            battery_level=70
        )
        
        self.vehicle3 = Vehicle.objects.create(
            license_plate='TEST003',
            model='Tesla Model X',
            status=Vehicle.Status.MAINTENANCE,  # Not available
            current_latitude=19.0500,  # Slightly south
            current_longitude=72.8500,
            battery_level=60
        )
    
    def test_calculate_distance(self):
        """Test distance calculation."""
        # Distance between Mumbai and Delhi (approximate)
        mumbai_lat, mumbai_lng = 19.0760, 72.8777
        delhi_lat, delhi_lng = 28.6139, 77.2090
        
        distance = VehicleLocationService.calculate_distance(
            mumbai_lat, mumbai_lng, delhi_lat, delhi_lng
        )
        
        # Should be approximately 1150-1200 km
        self.assertGreater(distance, 1100)
        self.assertLess(distance, 1300)
    
    def test_find_nearest_vehicles(self):
        """Test finding nearest vehicles."""
        # Search near vehicle1's location
        search_lat, search_lng = 19.0760, 72.8777
        
        nearest_vehicles = VehicleLocationService.find_nearest_vehicles(
            latitude=search_lat,
            longitude=search_lng,
            radius_km=10,
            available_only=True
        )
        
        # Should find vehicle1 and vehicle2 (both available)
        # vehicle3 is in maintenance so not available
        self.assertEqual(len(nearest_vehicles), 2)
        
        # Should be sorted by distance
        self.assertLessEqual(
            nearest_vehicles[0]['distance_km'],
            nearest_vehicles[1]['distance_km']
        )
        
        # First vehicle should be vehicle1 (closest)
        self.assertEqual(nearest_vehicles[0]['vehicle'], self.vehicle1)


class FleetAPITest(APITestCase):
    """Test fleet management API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.operator = User.objects.create_user(
            username='operator',
            email='operator@test.com',
            phone_number='+1234567890',
            role=User.Role.OPERATOR,
            password='testpass123'
        )
        
        self.rider = User.objects.create_user(
            username='rider',
            email='rider@test.com',
            phone_number='+1234567891',
            role=User.Role.RIDER,
            password='testpass123'
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            manufacturer='Tesla',
            year=2023,
            current_latitude=19.0760,
            current_longitude=72.8777,
            battery_level=85
        )
        
        self.client = APIClient()
    
    def test_vehicle_list_requires_authentication(self):
        """Test that vehicle list requires authentication."""
        url = reverse('fleet:vehicle-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_vehicle_list_requires_operator_role(self):
        """Test that vehicle list requires operator role."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('fleet:vehicle-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_vehicle_list_success(self):
        """Test successful vehicle list retrieval."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:vehicle-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['license_plate'], 'TEST001')
    
    def test_vehicle_create(self):
        """Test vehicle creation."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:vehicle-list')
        
        data = {
            'license_plate': 'TEST002',
            'model': 'Tesla Model S',
            'manufacturer': 'Tesla',
            'year': 2023,
            'vehicle_type': 'sedan',
            'passenger_capacity': 5,
            'current_latitude': 19.1000,
            'current_longitude': 72.9000
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vehicle.objects.count(), 2)
        
        new_vehicle = Vehicle.objects.get(license_plate='TEST002')
        self.assertEqual(new_vehicle.model, 'Tesla Model S')
    
    def test_vehicle_location_update(self):
        """Test vehicle location update."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:vehicle-location', kwargs={'vehicle_id': self.vehicle.id})
        
        data = {
            'latitude': 19.1000,
            'longitude': 72.9000
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.current_latitude, 19.1000)
        self.assertEqual(self.vehicle.current_longitude, 72.9000)
    
    def test_vehicle_status_update(self):
        """Test vehicle status update."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:vehicle-status', kwargs={'vehicle_id': self.vehicle.id})
        
        data = {
            'status': 'idle',
            'battery_level': 90
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.IDLE)
        self.assertEqual(self.vehicle.battery_level, 90)
    
    def test_telemetry_creation(self):
        """Test telemetry data creation."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:telemetry-list')
        
        data = {
            'vehicle_id': str(self.vehicle.id),
            'latitude': 19.0800,
            'longitude': 72.8800,
            'speed': 45.5,
            'heading': 180.0,
            'battery_level': 80,
            'temperature': 22.5,
            'engine_status': 'running',
            'passenger_count': 2
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VehicleTelemetry.objects.count(), 1)
        
        telemetry = VehicleTelemetry.objects.first()
        self.assertEqual(telemetry.vehicle, self.vehicle)
        self.assertEqual(telemetry.speed, 45.5)
    
    def test_maintenance_record_creation(self):
        """Test maintenance record creation."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:maintenance-list')
        
        scheduled_date = timezone.now() + timedelta(days=1)
        
        data = {
            'vehicle': self.vehicle.id,
            'maintenance_type': 'routine',
            'scheduled_date': scheduled_date.isoformat(),
            'description': 'Routine maintenance check',
            'estimated_cost': '200.00',
            'technician': self.operator.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MaintenanceRecord.objects.count(), 1)
        
        record = MaintenanceRecord.objects.first()
        self.assertEqual(record.vehicle, self.vehicle)
        self.assertEqual(record.maintenance_type, MaintenanceRecord.MaintenanceType.ROUTINE)
    
    def test_fleet_overview(self):
        """Test fleet overview endpoint."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('fleet:fleet-overview')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('stats', response.data)
        self.assertIn('status_distribution', response.data)
        self.assertIn('battery_distribution', response.data)
        self.assertIn('recent_alerts', response.data)
        
        # Check stats structure
        stats = response.data['stats']
        self.assertIn('total_vehicles', stats)
        self.assertIn('available_vehicles', stats)
        self.assertIn('online_vehicles', stats)


class FleetAnalyticsTest(TestCase):
    """Test fleet analytics functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.vehicle1 = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            status=Vehicle.Status.IDLE,
            battery_level=80,
            total_rides=100,
            total_revenue=5000.00
        )
        
        self.vehicle2 = Vehicle.objects.create(
            license_plate='TEST002',
            model='Tesla Model S',
            status=Vehicle.Status.IN_RIDE,
            battery_level=60,
            total_rides=150,
            total_revenue=7500.00
        )
        
        # Create some telemetry data
        VehicleTelemetry.objects.create(
            vehicle=self.vehicle1,
            latitude=19.0760,
            longitude=72.8777,
            speed=30.0,
            battery_level=80,
            engine_status='running'
        )
    
    def test_fleet_utilization(self):
        """Test fleet utilization calculation."""
        utilization = FleetAnalytics.get_fleet_utilization(days=7)
        
        self.assertEqual(utilization['total_vehicles'], 2)
        self.assertIn('utilization', utilization)
        
        # Check that all statuses are included
        for status_choice in Vehicle.Status.choices:
            status = status_choice[0]
            self.assertIn(status, utilization['utilization'])
    
    def test_maintenance_metrics(self):
        """Test maintenance metrics calculation."""
        # Create a maintenance record
        MaintenanceRecord.objects.create(
            vehicle=self.vehicle1,
            maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
            status=MaintenanceRecord.Status.COMPLETED,
            scheduled_date=timezone.now(),
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now(),
            estimated_cost=200.00,
            actual_cost=250.00
        )
        
        metrics = FleetAnalytics.get_maintenance_metrics(days=30)
        
        self.assertEqual(metrics['total_maintenance'], 1)
        self.assertEqual(metrics['completed_maintenance'], 1)
        self.assertEqual(metrics['completion_rate'], 100.0)
        self.assertEqual(metrics['total_estimated_cost'], 200.00)
        self.assertEqual(metrics['total_actual_cost'], 250.00)
        self.assertEqual(metrics['cost_variance'], 50.00)
    
    def test_vehicle_performance(self):
        """Test individual vehicle performance metrics."""
        performance = FleetAnalytics.get_vehicle_performance(self.vehicle1, days=30)
        
        self.assertEqual(performance['vehicle_id'], self.vehicle1.id)
        self.assertEqual(performance['license_plate'], 'TEST001')
        self.assertIn('avg_battery_level', performance)
        self.assertIn('telemetry_records', performance)
        self.assertEqual(performance['telemetry_records'], 1)