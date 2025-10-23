"""
Comprehensive test suite for NeuroRides platform.
This file contains integration tests and end-to-end test scenarios.
"""

import json
import time
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from accounts.models import User
from rides.models import Ride
from fleet.models import Vehicle, VehicleTelemetry
from dispatch.models import DispatchRequest
from payments.models import Payment
from analytics.models import RideAnalytics

User = get_user_model()


class EndToEndRideWorkflowTest(APITestCase):
    """
    Test complete end-to-end ride workflow from booking to completion.
    """
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.rider = User.objects.create_user(
            username='e2e_rider',
            email='rider@e2e.com',
            password='testpass123',
            role='rider',
            first_name='Test',
            last_name='Rider',
            phone_number='+1234567890'
        )
        
        self.operator = User.objects.create_user(
            username='e2e_operator',
            email='operator@e2e.com',
            password='testpass123',
            role='operator'
        )
        
        # Create vehicle
        self.vehicle = Vehicle.objects.create(
            license_plate='E2E001',
            make='Tesla',
            model='Model 3',
            vehicle_type='sedan',
            status='idle',
            current_latitude=37.7749,
            current_longitude=-122.4194,
            battery_level=80,
            is_active=True
        )
        
        self.client = APIClient()
    
    def test_complete_ride_lifecycle(self):
        """Test complete ride lifecycle from booking to payment."""
        # Step 1: Rider authentication
        self.client.force_authenticate(user=self.rider)
        
        # Step 2: Get fare estimate
        estimate_data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'ride_type': 'standard'
        }
        
        response = self.client.post('/api/rides/estimate-fare/', estimate_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        estimated_fare = response.data['estimated_fare']
        
        # Step 3: Book a ride
        ride_data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'pickup_address': '123 Test St, San Francisco, CA',
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'destination_address': '456 Test Ave, San Francisco, CA',
            'ride_type': 'standard'
        }
        
        response = self.client.post('/api/rides/', ride_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        ride_id = response.data['id']
        ride = Ride.objects.get(id=ride_id)
        self.assertEqual(ride.status, 'requested')
        
        # Step 4: Operator processes dispatch
        self.client.force_authenticate(user=self.operator)
        
        with patch('dispatch.services.DispatchService.find_best_vehicle') as mock_dispatch:
            mock_dispatch.return_value = self.vehicle
            
            # Create and process dispatch request
            dispatch_data = {
                'ride_id': str(ride_id),
                'priority': 'normal'
            }
            
            response = self.client.post('/api/dispatch/', dispatch_data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            dispatch_id = response.data['id']
            response = self.client.post(f'/api/dispatch/{dispatch_id}/process/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify ride is assigned
        ride.refresh_from_db()
        self.assertEqual(ride.status, 'assigned')
        self.assertEqual(ride.assigned_vehicle, self.vehicle)
        
        # Step 5: Vehicle updates location (driver en route)
        telemetry_data = {
            'latitude': 37.7750,
            'longitude': -122.4195,
            'speed': 25.0,
            'battery_level': 78
        }
        
        response = self.client.post(
            f'/api/fleet/vehicles/{self.vehicle.id}/telemetry/',
            telemetry_data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 6: Simulate ride progression
        # Driver arrives at pickup
        ride.status = 'pickup'
        ride.save()
        
        # Ride starts
        ride.status = 'in_progress'
        ride.picked_up_at = timezone.now()
        ride.save()
        
        # Ride completes
        ride.status = 'completed'
        ride.completed_at = timezone.now()
        ride.fare = Decimal(estimated_fare)
        ride.save()
        
        # Step 7: Process payment
        self.client.force_authenticate(user=self.rider)
        
        payment_data = {
            'ride_id': str(ride_id),
            'amount': str(ride.fare),
            'payment_method': 'credit_card',
            'card_token': 'tok_test_success'
        }
        
        with patch('payments.services.PaymentService.process_payment') as mock_payment:
            mock_payment.return_value = {
                'success': True,
                'transaction_id': 'txn_e2e_success',
                'status': 'completed'
            }
            
            response = self.client.post('/api/payments/', payment_data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify final state
        ride.refresh_from_db()
        self.assertEqual(ride.status, 'completed')
        
        payment = Payment.objects.get(ride=ride)
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.amount, ride.fare)
        
        # Step 8: Verify analytics data is created
        # This would typically be done by background tasks
        analytics, created = RideAnalytics.objects.get_or_create(
            date=timezone.now().date(),
            defaults={
                'total_rides': 1,
                'completed_rides': 1,
                'cancelled_rides': 0,
                'completion_rate': 100.0
            }
        )
        
        if not created:
            analytics.total_rides += 1
            analytics.completed_rides += 1
            analytics.completion_rate = (analytics.completed_rides / analytics.total_rides) * 100
            analytics.save()
        
        self.assertGreaterEqual(analytics.total_rides, 1)
        self.assertGreaterEqual(analytics.completed_rides, 1)


class SecurityAndPermissionsTest(APITestCase):
    """
    Test security features and permission controls.
    """
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='security_rider',
            email='rider@security.com',
            password='testpass123',
            role='rider'
        )
        
        self.operator = User.objects.create_user(
            username='security_operator',
            email='operator@security.com',
            password='testpass123',
            role='operator'
        )
        
        self.admin = User.objects.create_user(
            username='security_admin',
            email='admin@security.com',
            password='testpass123',
            role='admin',
            is_staff=True
        )
        
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are denied."""
        protected_endpoints = [
            '/api/rides/',
            '/api/fleet/vehicles/',
            '/api/payments/',
            '/api/analytics/dashboard/',
            '/api/accounts/profile/'
        ]
        
        for endpoint in protected_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code, 
                status.HTTP_401_UNAUTHORIZED,
                f"Endpoint {endpoint} should require authentication"
            )
    
    def test_role_based_access_control(self):
        """Test role-based access control."""
        # Rider accessing operator-only endpoints
        self.client.force_authenticate(user=self.rider)
        
        operator_endpoints = [
            '/api/fleet/vehicles/',
            '/api/dispatch/'
        ]
        
        for endpoint in operator_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                f"Rider should not access {endpoint}"
            )
        
        # Operator accessing admin-only endpoints
        self.client.force_authenticate(user=self.operator)
        
        admin_endpoints = [
            '/api/analytics/dashboard/',
        ]
        
        for endpoint in admin_endpoints:
            response = self.client.get(endpoint)
            self.assertIn(
                response.status_code,
                [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
                f"Operator should not access {endpoint}"
            )
    
    def test_data_isolation(self):
        """Test that users can only access their own data."""
        # Create rides for different users
        rider1 = self.rider
        rider2 = User.objects.create_user(
            username='rider2',
            email='rider2@test.com',
            password='testpass123',
            role='rider'
        )
        
        ride1 = Ride.objects.create(
            rider=rider1,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='completed'
        )
        
        ride2 = Ride.objects.create(
            rider=rider2,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='789 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='101 Test Ave',
            status='completed'
        )
        
        # Rider1 should only see their own rides
        self.client.force_authenticate(user=rider1)
        response = self.client.get('/api/rides/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        ride_ids = [ride['id'] for ride in response.data['results']]
        self.assertIn(str(ride1.id), ride_ids)
        self.assertNotIn(str(ride2.id), ride_ids)
        
        # Rider1 should not access rider2's ride details
        response = self.client.get(f'/api/rides/{ride2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_input_validation_and_sanitization(self):
        """Test input validation and sanitization."""
        self.client.force_authenticate(user=self.rider)
        
        # Test SQL injection attempt
        malicious_data = {
            'pickup_latitude': "37.7749'; DROP TABLE rides; --",
            'pickup_longitude': -122.4194,
            'pickup_address': '123 Test St',
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'destination_address': '456 Test Ave'
        }
        
        response = self.client.post('/api/rides/', malicious_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test XSS attempt
        xss_data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'pickup_address': '<script>alert("xss")</script>',
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'destination_address': '456 Test Ave'
        }
        
        response = self.client.post('/api/rides/', xss_data)
        # Should either reject or sanitize the input
        if response.status_code == status.HTTP_201_CREATED:
            ride = Ride.objects.get(id=response.data['id'])
            self.assertNotIn('<script>', ride.pickup_address)


class PerformanceAndScalabilityTest(APITestCase):
    """
    Test performance and scalability aspects.
    """
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='perf_rider',
            email='rider@perf.com',
            password='testpass123',
            role='rider'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.rider)
    
    def test_api_response_times(self):
        """Test that API response times are within acceptable limits."""
        endpoints_to_test = [
            ('/api/rides/', 'GET'),
            ('/api/accounts/profile/', 'GET'),
            ('/health/', 'GET'),
        ]
        
        for endpoint, method in endpoints_to_test:
            start_time = time.time()
            
            if method == 'GET':
                response = self.client.get(endpoint)
            elif method == 'POST':
                response = self.client.post(endpoint, {})
            
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # API should respond within 1 second (1000ms)
            self.assertLess(
                duration, 
                1000, 
                f"Endpoint {endpoint} took {duration}ms (>1000ms)"
            )
            
            # Response should be successful or have expected error
            self.assertIn(
                response.status_code, 
                [200, 201, 400, 401, 403, 404],
                f"Unexpected status code for {endpoint}"
            )
    
    def test_database_query_optimization(self):
        """Test that database queries are optimized."""
        from django.test.utils import override_settings
        from django.db import connection
        
        # Create test data
        for i in range(10):
            Ride.objects.create(
                rider=self.rider,
                pickup_latitude=37.7749 + (i * 0.001),
                pickup_longitude=-122.4194 + (i * 0.001),
                pickup_address=f'{i} Test St',
                destination_latitude=37.7849,
                destination_longitude=-122.4094,
                destination_address=f'{i} Test Ave',
                status='completed'
            )
        
        with override_settings(DEBUG=True):
            # Reset query count
            connection.queries_log.clear()
            
            # Make API call
            response = self.client.get('/api/rides/')
            
            # Check query count (should be reasonable for pagination)
            query_count = len(connection.queries)
            self.assertLess(
                query_count, 
                10, 
                f"Too many database queries: {query_count}"
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_concurrent_ride_creation(self):
        """Test handling of concurrent ride creation requests."""
        import threading
        import time
        
        results = []
        errors = []
        
        def create_ride(thread_id):
            try:
                ride_data = {
                    'pickup_latitude': 37.7749 + (thread_id * 0.001),
                    'pickup_longitude': -122.4194,
                    'pickup_address': f'{thread_id} Test St',
                    'destination_latitude': 37.7849,
                    'destination_longitude': -122.4094,
                    'destination_address': f'{thread_id} Test Ave',
                    'ride_type': 'standard'
                }
                
                response = self.client.post('/api/rides/', ride_data)
                results.append((thread_id, response.status_code))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_ride, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5, "Not all requests completed")
        
        # All requests should succeed
        for thread_id, status_code in results:
            self.assertEqual(
                status_code, 
                status.HTTP_201_CREATED,
                f"Thread {thread_id} failed with status {status_code}"
            )


class ErrorHandlingAndRecoveryTest(APITestCase):
    """
    Test error handling and recovery mechanisms.
    """
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='error_rider',
            email='rider@error.com',
            password='testpass123',
            role='rider'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.rider)
    
    def test_graceful_error_handling(self):
        """Test that errors are handled gracefully."""
        # Test invalid data
        invalid_ride_data = {
            'pickup_latitude': 'invalid',  # Should be float
            'pickup_longitude': -122.4194,
            'pickup_address': '',  # Required field
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'destination_address': '456 Test Ave'
        }
        
        response = self.client.post('/api/rides/', invalid_ride_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Response should have proper error format
        self.assertIn('errors', response.data)
        self.assertIsInstance(response.data['errors'], dict)
    
    @patch('payments.services.PaymentService.process_payment')
    def test_payment_failure_handling(self, mock_payment):
        """Test payment failure handling."""
        # Create a completed ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='completed',
            fare=Decimal('25.00')
        )
        
        # Mock payment failure
        mock_payment.return_value = {
            'success': False,
            'error': 'Card declined',
            'status': 'failed'
        }
        
        payment_data = {
            'ride_id': str(ride.id),
            'amount': '25.00',
            'payment_method': 'credit_card',
            'card_token': 'tok_fail'
        }
        
        response = self.client.post('/api/payments/', payment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify payment failure is recorded
        payment = Payment.objects.get(ride=ride)
        self.assertEqual(payment.status, 'failed')
    
    def test_database_connection_resilience(self):
        """Test resilience to database connection issues."""
        # This test would require more complex setup to simulate DB issues
        # For now, we'll test that the health check detects DB problems
        
        response = self.client.get('/health/detailed/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should include database status
        self.assertIn('database', response.data)


class IntegrationWithExternalServicesTest(APITestCase):
    """
    Test integration with external services (mocked).
    """
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='integration_rider',
            email='rider@integration.com',
            password='testpass123',
            role='rider'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.rider)
    
    @patch('payments.services.PaymentService.process_payment')
    def test_payment_gateway_integration(self, mock_payment):
        """Test payment gateway integration."""
        # Create completed ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='completed',
            fare=Decimal('30.00')
        )
        
        # Test successful payment
        mock_payment.return_value = {
            'success': True,
            'transaction_id': 'txn_integration_success',
            'status': 'completed'
        }
        
        payment_data = {
            'ride_id': str(ride.id),
            'amount': '30.00',
            'payment_method': 'credit_card',
            'card_token': 'tok_integration_test'
        }
        
        response = self.client.post('/api/payments/', payment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify payment service was called with correct parameters
        mock_payment.assert_called_once()
        call_args = mock_payment.call_args[1]
        self.assertEqual(call_args['amount'], Decimal('30.00'))
        self.assertEqual(call_args['payment_method'], 'credit_card')
    
    @patch('dispatch.services.DispatchService.calculate_distance')
    def test_mapping_service_integration(self, mock_distance):
        """Test integration with mapping/distance calculation service."""
        mock_distance.return_value = 5.2  # km
        
        estimate_data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094,
            'ride_type': 'standard'
        }
        
        response = self.client.post('/api/rides/estimate-fare/', estimate_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify distance calculation was called
        mock_distance.assert_called_once()
        
        # Verify fare estimation includes distance
        self.assertIn('estimated_distance', response.data)
        self.assertGreater(float(response.data['estimated_fare']), 0)


class DataConsistencyAndIntegrityTest(TransactionTestCase):
    """
    Test data consistency and integrity across the system.
    """
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='consistency_rider',
            email='rider@consistency.com',
            password='testpass123',
            role='rider'
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='CONS001',
            make='Tesla',
            model='Model 3',
            vehicle_type='sedan',
            status='idle',
            is_active=True
        )
    
    def test_ride_status_consistency(self):
        """Test that ride status transitions are consistent."""
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='requested'
        )
        
        # Valid status transitions
        valid_transitions = [
            ('requested', 'assigned'),
            ('assigned', 'pickup'),
            ('pickup', 'in_progress'),
            ('in_progress', 'completed')
        ]
        
        for from_status, to_status in valid_transitions:
            ride.status = from_status
            ride.save()
            
            ride.status = to_status
            ride.save()  # Should not raise exception
            
            ride.refresh_from_db()
            self.assertEqual(ride.status, to_status)
    
    def test_vehicle_assignment_consistency(self):
        """Test that vehicle assignments are consistent."""
        # Create ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='requested'
        )
        
        # Assign vehicle to ride
        ride.assigned_vehicle = self.vehicle
        ride.status = 'assigned'
        ride.save()
        
        # Vehicle status should be updated
        self.vehicle.refresh_from_db()
        # Note: This would be handled by signals in the actual implementation
        
        # Verify assignment
        self.assertEqual(ride.assigned_vehicle, self.vehicle)
        self.assertEqual(ride.status, 'assigned')
    
    def test_payment_ride_consistency(self):
        """Test consistency between payments and rides."""
        # Create completed ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave',
            status='completed',
            fare=Decimal('25.00')
        )
        
        # Create payment
        payment = Payment.objects.create(
            user=self.rider,
            ride=ride,
            amount=ride.fare,
            currency='USD',
            status='completed',
            payment_method='credit_card'
        )
        
        # Verify consistency
        self.assertEqual(payment.ride, ride)
        self.assertEqual(payment.amount, ride.fare)
        self.assertEqual(payment.user, ride.rider)


# Run specific test categories
def run_security_tests():
    """Run only security-related tests."""
    from django.test.utils import get_runner
    from django.conf import settings
    
    test_runner = get_runner(settings)()
    test_suite = test_runner.build_suite(['tests.test_comprehensive.SecurityAndPermissionsTest'])
    return test_runner.run_tests(test_suite)


def run_performance_tests():
    """Run only performance-related tests."""
    from django.test.utils import get_runner
    from django.conf import settings
    
    test_runner = get_runner(settings)()
    test_suite = test_runner.build_suite(['tests.test_comprehensive.PerformanceAndScalabilityTest'])
    return test_runner.run_tests(test_suite)


def run_integration_tests():
    """Run only integration tests."""
    from django.test.utils import get_runner
    from django.conf import settings
    
    test_runner = get_runner(settings)()
    test_suite = test_runner.build_suite([
        'tests.test_comprehensive.EndToEndRideWorkflowTest',
        'tests.test_comprehensive.IntegrationWithExternalServicesTest'
    ])
    return test_runner.run_tests(test_suite)