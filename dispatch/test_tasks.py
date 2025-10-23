"""
Tests for dispatch Celery tasks.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .tasks import (
    process_dispatch_request,
    process_dispatch_queue,
    cleanup_expired_dispatch_requests,
    retry_failed_dispatch_requests,
    generate_daily_dispatch_metrics,
    monitor_dispatch_performance,
    update_vehicle_assignments
)
from .models import DispatchRequest
from rides.models import Ride
from fleet.models import Vehicle
from accounts.models import User


class DispatchTasksTestCase(TestCase):
    """Test case for dispatch tasks."""
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='rider'
        )
        
        # Create test vehicle
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
        
        # Create test ride
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St, San Francisco, CA',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave, San Francisco, CA',
            status='requested',
            fare_estimate=15.50
        )
        
        # Create test dispatch request
        self.dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL,
            status=DispatchRequest.Status.PENDING,
            max_wait_time_minutes=10,
            requested_at=timezone.now()
        )
    
    @patch('dispatch.tasks.DispatchService')
    def test_process_dispatch_request_success(self, mock_dispatch_service):
        """Test successful dispatch request processing."""
        # Mock successful dispatch
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.process_single_dispatch.return_value = {
            'success': True,
            'vehicle_id': str(self.vehicle.id),
            'dispatch_request_id': str(self.dispatch_request.id)
        }
        
        # Execute task
        result = process_dispatch_request(str(self.dispatch_request.id))
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['vehicle_id'], str(self.vehicle.id))
        
        # Verify service was called
        mock_service_instance.process_single_dispatch.assert_called_once()
    
    @patch('dispatch.tasks.DispatchService')
    def test_process_dispatch_request_failure(self, mock_dispatch_service):
        """Test dispatch request processing failure."""
        # Mock failed dispatch
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.process_single_dispatch.return_value = {
            'success': False,
            'error': 'No available vehicles',
            'dispatch_request_id': str(self.dispatch_request.id)
        }
        
        # Execute task
        result = process_dispatch_request(str(self.dispatch_request.id))
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No available vehicles')
    
    def test_process_dispatch_request_not_found(self):
        """Test dispatch request processing with non-existent request."""
        # Execute task with non-existent ID
        result = process_dispatch_request('non-existent-id')
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_process_dispatch_request_expired(self):
        """Test dispatch request processing with expired request."""
        # Make request expired
        self.dispatch_request.requested_at = timezone.now() - timedelta(minutes=20)
        self.dispatch_request.max_wait_time_minutes = 10
        self.dispatch_request.save()
        
        # Execute task
        result = process_dispatch_request(str(self.dispatch_request.id))
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertIn('expired', result['error'])
    
    @patch('dispatch.tasks.DispatchQueue')
    def test_process_dispatch_queue(self, mock_dispatch_queue):
        """Test dispatch queue processing."""
        # Mock queue processing
        mock_queue_instance = mock_dispatch_queue.return_value
        mock_queue_instance.process_queue.return_value = {
            'processed': 5,
            'successful': 4,
            'failed': 1
        }
        
        # Execute task
        result = process_dispatch_queue(max_requests=10)
        
        # Verify result
        self.assertEqual(result['processed'], 5)
        self.assertEqual(result['successful'], 4)
        self.assertEqual(result['failed'], 1)
        
        # Verify queue was called with correct parameters
        mock_queue_instance.process_queue.assert_called_once_with(max_requests=10)
    
    @patch('dispatch.tasks.DispatchService')
    def test_cleanup_expired_dispatch_requests(self, mock_dispatch_service):
        """Test cleanup of expired dispatch requests."""
        # Mock cleanup service
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.cleanup_expired_requests.return_value = 3
        
        # Execute task
        result = cleanup_expired_dispatch_requests()
        
        # Verify result
        self.assertEqual(result['cleaned_up'], 3)
        self.assertIn('timestamp', result)
        
        # Verify service was called
        mock_service_instance.cleanup_expired_requests.assert_called_once()
    
    @patch('dispatch.tasks.DispatchService')
    def test_retry_failed_dispatch_requests(self, mock_dispatch_service):
        """Test retry of failed dispatch requests."""
        # Mock retry service
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.retry_failed_dispatches.return_value = 2
        
        # Execute task
        result = retry_failed_dispatch_requests()
        
        # Verify result
        self.assertEqual(result['retried'], 2)
        self.assertIn('timestamp', result)
        
        # Verify service was called
        mock_service_instance.retry_failed_dispatches.assert_called_once()
    
    @patch('dispatch.tasks.DispatchService')
    def test_generate_daily_dispatch_metrics(self, mock_dispatch_service):
        """Test daily dispatch metrics generation."""
        # Mock metrics service
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.generate_daily_metrics.return_value = [
            {'metric': 'total_requests', 'value': 100},
            {'metric': 'success_rate', 'value': 85.5}
        ]
        
        # Execute task
        result = generate_daily_dispatch_metrics('2023-12-01')
        
        # Verify result
        self.assertEqual(result['date'], '2023-12-01')
        self.assertEqual(result['metrics_generated'], 2)
        self.assertIn('timestamp', result)
        
        # Verify service was called
        mock_service_instance.generate_daily_metrics.assert_called_once()
    
    @patch('dispatch.tasks.DispatchService')
    @patch('dispatch.tasks.DispatchQueue')
    def test_monitor_dispatch_performance(self, mock_dispatch_queue, mock_dispatch_service):
        """Test dispatch performance monitoring."""
        # Mock service responses
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.get_dispatch_statistics.return_value = {
            'success_rate': 75.0,  # Below threshold
            'average_processing_time_seconds': 35.0,  # Above threshold
        }
        
        mock_queue_instance = mock_dispatch_queue.return_value
        mock_queue_instance.get_queue_status.return_value = {
            'pending_requests': 150,  # Above threshold
            'average_wait_time_seconds': 400.0,  # Above threshold
        }
        
        # Execute task
        result = monitor_dispatch_performance()
        
        # Verify result
        self.assertTrue(len(result['alerts']) > 0)
        self.assertIn('statistics', result)
        self.assertIn('queue_status', result)
        
        # Check that alerts were generated for the issues
        alert_types = [alert['type'] for alert in result['alerts']]
        self.assertIn('low_success_rate', alert_types)
        self.assertIn('slow_processing', alert_types)
        self.assertIn('large_queue', alert_types)
        self.assertIn('long_wait_time', alert_types)
    
    def test_update_vehicle_assignments(self):
        """Test vehicle assignment updates."""
        # Create assigned dispatch request
        self.dispatch_request.status = DispatchRequest.Status.ASSIGNED
        self.dispatch_request.assigned_vehicle = self.vehicle
        self.dispatch_request.save()
        
        # Set vehicle to idle (should be updated to assigned)
        self.vehicle.status = 'idle'
        self.vehicle.save()
        
        # Execute task
        result = update_vehicle_assignments()
        
        # Verify result
        self.assertEqual(result['updated'], 1)
        self.assertEqual(len(result['errors']), 0)
        
        # Verify vehicle status was updated
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'assigned')
    
    def test_update_vehicle_assignments_low_battery(self):
        """Test vehicle assignment updates with low battery vehicle."""
        # Create assigned dispatch request
        self.dispatch_request.status = DispatchRequest.Status.ASSIGNED
        self.dispatch_request.assigned_vehicle = self.vehicle
        self.dispatch_request.save()
        
        # Set vehicle to low battery
        self.vehicle.battery_level = 15
        self.vehicle.save()
        
        # Execute task
        result = update_vehicle_assignments()
        
        # Verify result - should not update due to low battery
        self.assertEqual(result['updated'], 0)
        
        # Verify vehicle status was not changed
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'idle')


class DispatchTaskRetryTestCase(TestCase):
    """Test case for dispatch task retry logic."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St, San Francisco, CA',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave, San Francisco, CA',
            status='requested',
            fare_estimate=15.50
        )
        
        self.dispatch_request = DispatchRequest.objects.create(
            ride=self.ride,
            priority=DispatchRequest.Priority.NORMAL,
            status=DispatchRequest.Status.PENDING,
            max_wait_time_minutes=10,
            requested_at=timezone.now()
        )
    
    @patch('dispatch.tasks.DispatchService')
    def test_process_dispatch_request_retry_logic(self, mock_dispatch_service):
        """Test dispatch request retry logic on failure."""
        # Mock service to raise exception
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.process_single_dispatch.side_effect = Exception("Service error")
        
        # Create a mock task with retry capability
        task_mock = MagicMock()
        task_mock.request.retries = 0
        task_mock.max_retries = 3
        task_mock.retry.side_effect = Exception("Retry called")
        
        # Execute task and expect retry to be called
        with self.assertRaises(Exception) as context:
            process_dispatch_request.__wrapped__(task_mock, str(self.dispatch_request.id))
        
        self.assertEqual(str(context.exception), "Retry called")
        task_mock.retry.assert_called_once()
    
    @patch('dispatch.tasks.DispatchService')
    def test_process_dispatch_request_max_retries_exceeded(self, mock_dispatch_service):
        """Test dispatch request when max retries are exceeded."""
        # Mock service to raise exception
        mock_service_instance = mock_dispatch_service.return_value
        mock_service_instance.process_single_dispatch.side_effect = Exception("Service error")
        
        # Create a mock task that has exceeded max retries
        task_mock = MagicMock()
        task_mock.request.retries = 3
        task_mock.max_retries = 3
        
        # Execute task
        result = process_dispatch_request.__wrapped__(task_mock, str(self.dispatch_request.id))
        
        # Verify result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('Task failed after retries', result['error'])
        
        # Verify dispatch request was marked as failed
        self.dispatch_request.refresh_from_db()
        self.assertEqual(self.dispatch_request.status, DispatchRequest.Status.FAILED)
        self.assertIn('Task failed after 3 retries', self.dispatch_request.failure_reason)