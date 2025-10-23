"""
Tests for dispatch app.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from accounts.models import User
from rides.models import Ride
from fleet.models import Vehicle
from .models import DispatchRequest, DispatchAlgorithmConfig, DispatchMetrics
from .queue import DispatchQueue
from .services import DispatchService
# from .algorithms import NearestVehicleAlgorithm, WeightedVehicleAlgorithm

User = get_user_model()


class DispatchRequestModelTest(TestCase):
    """Test DispatchRequest model."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='testpass123',
            role=User.Role.RIDER
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
            license_plate='ABC123',
            model='Tesla Model 3',
            year=2023,
            battery_level=80,
            status=Vehicle.Status.IDLE,
            current_latitude=37.7749,
            current_longitude=-122.4194
        )
    
    def test_dispatch_request_creation(self):
        """Test dispatch request creation."""
        dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL
        )
        
        self.assertEqual(dispatch_request.status, DispatchRequest.Status.PENDING)
        self.assertEqual(dispatch_request.retry_count, 0)
        self.assertIsNotNone(dispatch_request.expires_at)
        self.assertFalse(dispatch_request.is_expired)
    
    def test_dispatch_request_expiration(self):
        """Test dispatch request expiration."""
        # Create expired request
        dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL,
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        self.assertTrue(dispatch_request.is_expired)
        
        # Test expire_request method
        dispatch_request.expire_request()
        self.assertEqual(dispatch_request.status, DispatchRequest.Status.EXPIRED)
    
    def test_dispatch_request_assignment(self):
        """Test dispatch request assignment."""
        dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL
        )
        
        # Assign vehicle
        dispatch_request.processing_started_at = timezone.now()
        dispatch_request.assigned_vehicle = self.vehicle
        dispatch_request.status = DispatchRequest.Status.ASSIGNED
        dispatch_request.assigned_at = timezone.now()
        dispatch_request.algorithm_used = 'nearest'
        dispatch_request.save()
        
        self.assertEqual(dispatch_request.status, DispatchRequest.Status.ASSIGNED)
        self.assertEqual(dispatch_request.assigned_vehicle, self.vehicle)
        self.assertIsNotNone(dispatch_request.processing_duration)
    
    def test_dispatch_request_failure(self):
        """Test dispatch request failure."""
        dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL
        )
        
        # Mark as failed
        dispatch_request.status = DispatchRequest.Status.FAILED
        dispatch_request.failure_reason = 'No vehicles available'
        dispatch_request.retry_count = 1
        dispatch_request.save()
        
        self.assertEqual(dispatch_request.status, DispatchRequest.Status.FAILED)
        self.assertEqual(dispatch_request.failure_reason, 'No vehicles available')
        self.assertEqual(dispatch_request.retry_count, 1)


class DispatchAlgorithmConfigModelTest(TestCase):
    """Test DispatchAlgorithmConfig model."""
    
    def test_algorithm_config_creation(self):
        """Test algorithm configuration creation."""
        config = DispatchAlgorithmConfig.objects.create(
            name='test_algorithm',
            is_active=True,
            priority=1,
            max_search_radius_km=10.0,
            max_vehicles_to_consider=20,
            min_battery_level=25,
            distance_weight=0.5,
            battery_weight=0.3,
            efficiency_weight=0.1,
            availability_weight=0.1,
            max_processing_time_seconds=30
        )
        
        self.assertEqual(config.name, 'test_algorithm')
        self.assertTrue(config.is_active)
        self.assertEqual(config.priority, 1)
        self.assertEqual(config.max_search_radius_km, 10.0)
    
    def test_get_active_algorithm(self):
        """Test getting active algorithm."""
        # Create multiple algorithms
        DispatchAlgorithmConfig.objects.create(
            name='algorithm1',
            is_active=True,
            priority=1
        )
        
        DispatchAlgorithmConfig.objects.create(
            name='algorithm2',
            is_active=True,
            priority=2
        )
        
        DispatchAlgorithmConfig.objects.create(
            name='algorithm3',
            is_active=False,
            priority=3
        )
        
        # Get active algorithms (highest priority first)
        active_algorithms = DispatchAlgorithmConfig.objects.filter(
            is_active=True
        ).order_by('-priority')
        
        self.assertEqual(active_algorithms.count(), 2)
        self.assertEqual(active_algorithms.first().name, 'algorithm2')  # Highest priority active


class DispatchQueueTest(TestCase):
    """Test DispatchQueue functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='testpass123',
            role=User.Role.RIDER
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
        
        self.dispatch_queue = DispatchQueue()
        
        # Create algorithm config for dispatch to work
        DispatchAlgorithmConfig.objects.create(
            name='nearest',
            is_active=True,
            priority=1,
            max_search_radius_km=10.0,
            max_vehicles_to_consider=10,
            min_battery_level=20
        )
    
    def test_add_ride_to_queue(self):
        """Test adding ride to dispatch queue."""
        dispatch_request = self.dispatch_queue.add_ride_to_queue(self.ride)
        
        self.assertIsInstance(dispatch_request, DispatchRequest)
        self.assertEqual(dispatch_request.ride, self.ride)
        # Status should be ASSIGNED since we have an available vehicle
        self.assertEqual(dispatch_request.status, DispatchRequest.Status.ASSIGNED)
        self.assertEqual(dispatch_request.assigned_vehicle, self.vehicle)
    
    def test_get_queue_status(self):
        """Test getting queue status."""
        # Add some requests to queue
        self.dispatch_queue.add_ride_to_queue(self.ride)
        
        status = self.dispatch_queue.get_queue_status()
        
        self.assertIn('pending_requests', status)
        self.assertIn('processing_requests', status)
        self.assertIn('total_active', status)
        self.assertIn('priority_distribution', status)
        # Since dispatch is working, there should be 0 pending requests
        self.assertEqual(status['pending_requests'], 0)


class DispatchServiceTest(TestCase):
    """Test DispatchService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='testpass123',
            role=User.Role.RIDER
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
            license_plate='ABC123',
            model='Tesla Model 3',
            year=2023,
            battery_level=80,
            status=Vehicle.Status.IDLE,
            current_latitude=37.7749,
            current_longitude=-122.4194
        )
        
        self.dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL
        )
        
        # Create algorithm config
        self.algorithm_config = DispatchAlgorithmConfig.objects.create(
            name='nearest',
            is_active=True,
            priority=1,
            max_search_radius_km=10.0,
            max_vehicles_to_consider=10,
            min_battery_level=20
        )
        
        self.dispatch_service = DispatchService()
    
    def test_process_single_dispatch_basic(self):
        """Test basic dispatch processing functionality."""
        # This test will be expanded when algorithms are implemented
        result = self.dispatch_service.get_dispatch_statistics(days=1)
        
        self.assertIn('total_requests', result)
        self.assertIn('successful_assignments', result)
        self.assertIn('success_rate', result)
    
    def test_cleanup_expired_requests(self):
        """Test cleanup of expired requests."""
        # Create a separate ride for this test
        expired_ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7849,
            pickup_longitude=-122.4094,
            destination_latitude=37.7949,
            destination_longitude=-122.3994,
            pickup_address='789 Test St, San Francisco, CA',
            destination_address='101 Test Ave, San Francisco, CA',
            status=Ride.Status.REQUESTED
        )
        
        # Create expired request
        expired_request = DispatchRequest.objects.create(
            ride=expired_ride,
            priority=DispatchRequest.Priority.NORMAL,
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        count = self.dispatch_service.cleanup_expired_requests()
        
        self.assertEqual(count, 1)
        
        expired_request.refresh_from_db()
        self.assertEqual(expired_request.status, DispatchRequest.Status.EXPIRED)
    
    def test_get_dispatch_statistics(self):
        """Test getting dispatch statistics."""
        # Create a separate ride for this test
        stats_ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7649,
            pickup_longitude=-122.4294,
            destination_latitude=37.7749,
            destination_longitude=-122.4194,
            pickup_address='555 Stats St, San Francisco, CA',
            destination_address='666 Stats Ave, San Francisco, CA',
            status=Ride.Status.REQUESTED
        )
        
        # Create some test data
        DispatchRequest.objects.create(
            ride=stats_ride,
            priority=DispatchRequest.Priority.NORMAL,
            status=DispatchRequest.Status.ASSIGNED,
            assigned_vehicle=self.vehicle,
            algorithm_used='nearest'
        )
        
        stats = self.dispatch_service.get_dispatch_statistics(days=1)
        
        self.assertIn('total_requests', stats)
        self.assertIn('successful_assignments', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('failed_assignments', stats)
        self.assertIn('expired_requests', stats)
        self.assertIn('average_processing_time_seconds', stats)


# Algorithm tests will be added when algorithms module is created