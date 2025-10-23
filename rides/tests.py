"""
Tests for rides app.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
from decimal import Decimal

from .models import Ride, RideRequest, ServiceArea, RideFareCalculator
from fleet.models import Vehicle

User = get_user_model()


class RideModelTest(TestCase):
    """Test Ride model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider',
            email='rider@test.com',
            phone_number='+1234567890',
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
        
        self.ride_data = {
            'rider': self.rider,
            'pickup_latitude': 19.0760,
            'pickup_longitude': 72.8777,
            'pickup_address': 'CST Station',
            'destination_latitude': 19.0544,
            'destination_longitude': 72.8311,
            'destination_address': 'Gateway of India',
            'passenger_count': 2,
            'fare_estimate': Decimal('150.00')
        }
    
    def test_create_ride(self):
        """Test ride creation."""
        ride = Ride.objects.create(**self.ride_data)
        
        self.assertEqual(ride.rider, self.rider)
        self.assertEqual(ride.status, Ride.Status.REQUESTED)
        self.assertEqual(ride.passenger_count, 2)
        self.assertIsNotNone(ride.id)  # UUID should be generated
        self.assertIsNotNone(ride.requested_at)
    
    def test_ride_string_representation(self):
        """Test ride string representation."""
        ride = Ride.objects.create(**self.ride_data)
        expected = f"Ride {ride.id} - {self.rider.username} ({ride.get_status_display()})"
        self.assertEqual(str(ride), expected)
    
    def test_ride_location_properties(self):
        """Test location property methods."""
        ride = Ride.objects.create(**self.ride_data)
        
        pickup_location = ride.pickup_location
        self.assertEqual(pickup_location, (19.0760, 72.8777))
        
        destination_location = ride.destination_location
        self.assertEqual(destination_location, (19.0544, 72.8311))
    
    def test_ride_is_active_property(self):
        """Test is_active property."""
        ride = Ride.objects.create(**self.ride_data)
        
        # Should be active when requested
        self.assertTrue(ride.is_active)
        
        # Should be active when assigned
        ride.status = Ride.Status.ASSIGNED
        self.assertTrue(ride.is_active)
        
        # Should not be active when completed
        ride.status = Ride.Status.COMPLETED
        self.assertFalse(ride.is_active)
        
        # Should not be active when cancelled
        ride.status = Ride.Status.CANCELLED
        self.assertFalse(ride.is_active)
    
    def test_ride_can_be_cancelled_property(self):
        """Test can_be_cancelled property."""
        ride = Ride.objects.create(**self.ride_data)
        
        # Can be cancelled when requested
        self.assertTrue(ride.can_be_cancelled)
        
        # Can be cancelled when assigned
        ride.status = Ride.Status.ASSIGNED
        self.assertTrue(ride.can_be_cancelled)
        
        # Can be cancelled during pickup
        ride.status = Ride.Status.PICKUP
        self.assertTrue(ride.can_be_cancelled)
        
        # Cannot be cancelled when in progress
        ride.status = Ride.Status.IN_PROGRESS
        self.assertFalse(ride.can_be_cancelled)
        
        # Cannot be cancelled when completed
        ride.status = Ride.Status.COMPLETED
        self.assertFalse(ride.can_be_cancelled)
    
    def test_calculate_distance(self):
        """Test distance calculation."""
        ride = Ride.objects.create(**self.ride_data)
        
        distance = ride.calculate_distance()
        
        # Distance between CST and Gateway of India should be around 2-6 km
        self.assertGreater(distance, 1.0)
        self.assertLess(distance, 10.0)
    
    def test_assign_vehicle(self):
        """Test vehicle assignment."""
        ride = Ride.objects.create(**self.ride_data)
        
        ride.assign_vehicle(self.vehicle)
        
        self.assertEqual(ride.vehicle, self.vehicle)
        self.assertEqual(ride.status, Ride.Status.ASSIGNED)
        self.assertIsNotNone(ride.assigned_at)
        
        # Vehicle should also be updated
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'assigned')
    
    def test_ride_workflow(self):
        """Test complete ride workflow."""
        ride = Ride.objects.create(**self.ride_data)
        
        # Assign vehicle
        ride.assign_vehicle(self.vehicle)
        self.assertEqual(ride.status, Ride.Status.ASSIGNED)
        
        # Start pickup
        ride.start_pickup()
        self.assertEqual(ride.status, Ride.Status.PICKUP)
        self.assertIsNotNone(ride.pickup_started_at)
        
        # Confirm pickup
        ride.confirm_pickup()
        self.assertEqual(ride.status, Ride.Status.IN_PROGRESS)
        self.assertIsNotNone(ride.picked_up_at)
        
        # Complete ride
        ride.complete_ride(actual_distance_km=2.5, final_fare=Decimal('175.00'))
        self.assertEqual(ride.status, Ride.Status.COMPLETED)
        self.assertIsNotNone(ride.completed_at)
        self.assertEqual(ride.actual_distance_km, 2.5)
        self.assertEqual(ride.final_fare, Decimal('175.00'))
    
    def test_cancel_ride(self):
        """Test ride cancellation."""
        ride = Ride.objects.create(**self.ride_data)
        ride.assign_vehicle(self.vehicle)
        
        ride.cancel_ride(
            reason=Ride.CancellationReason.USER_CANCELLED,
            notes='Changed my mind'
        )
        
        self.assertEqual(ride.status, Ride.Status.CANCELLED)
        self.assertEqual(ride.cancellation_reason, Ride.CancellationReason.USER_CANCELLED)
        self.assertEqual(ride.cancellation_notes, 'Changed my mind')
        self.assertIsNotNone(ride.cancelled_at)
        
        # Vehicle should be freed up
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'idle')
    
    def test_ride_duration_properties(self):
        """Test duration calculation properties."""
        ride = Ride.objects.create(**self.ride_data)
        
        # Set up timestamps
        base_time = timezone.now()
        ride.requested_at = base_time
        ride.picked_up_at = base_time + timedelta(minutes=10)
        ride.completed_at = base_time + timedelta(minutes=40)
        ride.save()
        
        # Test ride duration (pickup to completion)
        duration = ride.duration
        self.assertEqual(duration.total_seconds(), 30 * 60)  # 30 minutes
        
        # Test total duration (request to completion)
        total_duration = ride.total_duration
        self.assertEqual(total_duration.total_seconds(), 40 * 60)  # 40 minutes


class RideFareCalculatorTest(TestCase):
    """Test RideFareCalculator functionality."""
    
    def test_basic_fare_calculation(self):
        """Test basic fare calculation."""
        fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            estimated_duration_minutes=20,
            vehicle_type='sedan'
        )
        
        # Base fare + distance + time
        expected = (
            RideFareCalculator.BASE_FARE +
            Decimal('5.0') * RideFareCalculator.RATE_PER_KM +
            Decimal('20') * RideFareCalculator.RATE_PER_MINUTE
        )
        
        self.assertEqual(fare, expected)
    
    def test_vehicle_type_multipliers(self):
        """Test vehicle type multipliers."""
        base_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            vehicle_type='sedan'
        )
        
        luxury_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            vehicle_type='luxury'
        )
        
        # Luxury should be 1.5x more expensive
        self.assertAlmostEqual(
            float(luxury_fare),
            float(base_fare) * 1.5,
            places=2
        )
    
    def test_special_requirements_surcharge(self):
        """Test special requirements surcharge."""
        base_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0
        )
        
        wheelchair_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            requires_wheelchair_access=True
        )
        
        child_seat_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            requires_child_seat=True
        )
        
        both_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            requires_wheelchair_access=True,
            requires_child_seat=True
        )
        
        # Check surcharges
        self.assertEqual(
            wheelchair_fare - base_fare,
            RideFareCalculator.WHEELCHAIR_SURCHARGE
        )
        
        self.assertEqual(
            child_seat_fare - base_fare,
            RideFareCalculator.CHILD_SEAT_SURCHARGE
        )
        
        self.assertEqual(
            both_fare - base_fare,
            RideFareCalculator.WHEELCHAIR_SURCHARGE + RideFareCalculator.CHILD_SEAT_SURCHARGE
        )
    
    def test_surge_pricing(self):
        """Test surge pricing multiplier."""
        base_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            surge_multiplier=1.0
        )
        
        surge_fare = RideFareCalculator.calculate_fare_estimate(
            distance_km=5.0,
            surge_multiplier=2.0
        )
        
        # Surge fare should be double
        self.assertAlmostEqual(
            float(surge_fare),
            float(base_fare) * 2.0,
            places=2
        )


class ServiceAreaTest(TestCase):
    """Test ServiceArea functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.mumbai_area = ServiceArea.objects.create(
            name='Mumbai',
            description='Mumbai metropolitan area',
            north_lat=19.2544,
            south_lat=18.8800,
            east_lng=72.9781,
            west_lng=72.7757,
            is_active=True,
            surge_multiplier=Decimal('1.2')
        )
    
    def test_contains_location(self):
        """Test location containment check."""
        # Location within Mumbai
        mumbai_center = (19.0760, 72.8777)
        self.assertTrue(
            self.mumbai_area.contains_location(*mumbai_center)
        )
        
        # Location outside Mumbai (Delhi)
        delhi_center = (28.6139, 77.2090)
        self.assertFalse(
            self.mumbai_area.contains_location(*delhi_center)
        )
    
    def test_get_service_area_for_location(self):
        """Test getting service area for location."""
        mumbai_center = (19.0760, 72.8777)
        area = ServiceArea.get_service_area_for_location(*mumbai_center)
        
        self.assertEqual(area, self.mumbai_area)
        
        # Location outside any service area
        delhi_center = (28.6139, 77.2090)
        area = ServiceArea.get_service_area_for_location(*delhi_center)
        
        self.assertIsNone(area)


class RideAPITest(APITestCase):
    """Test ride booking API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.rider = User.objects.create_user(
            username='rider',
            email='rider@test.com',
            phone_number='+1234567890',
            role=User.Role.RIDER,
            password='testpass123'
        )
        
        self.operator = User.objects.create_user(
            username='operator',
            email='operator@test.com',
            phone_number='+1234567891',
            role=User.Role.OPERATOR,
            password='testpass123'
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST001',
            model='Tesla Model 3',
            current_latitude=19.0760,
            current_longitude=72.8777,
            battery_level=85
        )
        
        # Create Mumbai service area
        self.service_area = ServiceArea.objects.create(
            name='Mumbai',
            north_lat=19.2544,
            south_lat=18.8800,
            east_lng=72.9781,
            west_lng=72.7757,
            is_active=True
        )
        
        self.client = APIClient()
    
    def test_fare_estimate_requires_authentication(self):
        """Test that fare estimate requires authentication."""
        url = reverse('rides:fare-estimate')
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_fare_estimate_requires_rider_role(self):
        """Test that fare estimate requires rider role."""
        self.client.force_authenticate(user=self.operator)
        url = reverse('rides:fare-estimate')
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_fare_estimate_success(self):
        """Test successful fare estimation."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:fare-estimate')
        
        data = {
            'pickup_latitude': 19.0760,
            'pickup_longitude': 72.8777,
            'destination_latitude': 19.0544,
            'destination_longitude': 72.8311,
            'passenger_count': 2
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('estimated_fare', response.data)
        self.assertIn('distance_km', response.data)
        self.assertIn('estimated_duration_minutes', response.data)
        self.assertIn('breakdown', response.data)
    
    def test_ride_booking_success(self):
        """Test successful ride booking."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-create')
        
        data = {
            'pickup_latitude': 19.0760,
            'pickup_longitude': 72.8777,
            'pickup_address': 'CST Station',
            'destination_latitude': 19.0544,
            'destination_longitude': 72.8311,
            'destination_address': 'Gateway of India',
            'passenger_count': 2,
            'pickup_notes': 'Near the main entrance'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('ride', response.data)
        self.assertEqual(response.data['message'], 'Ride booked successfully')
        
        # Check ride was created
        ride = Ride.objects.get(id=response.data['ride']['id'])
        self.assertEqual(ride.rider, self.rider)
        self.assertEqual(ride.status, Ride.Status.REQUESTED)
    
    def test_ride_booking_outside_service_area(self):
        """Test ride booking outside service area."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-create')
        
        data = {
            'pickup_latitude': 28.6139,  # Delhi coordinates
            'pickup_longitude': 77.2090,
            'destination_latitude': 19.0544,
            'destination_longitude': 72.8311,
            'passenger_count': 1
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pickup_location', response.data)
    
    def test_multiple_active_rides_not_allowed(self):
        """Test that users cannot have multiple active rides."""
        self.client.force_authenticate(user=self.rider)
        
        # Create first ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=19.0760,
            pickup_longitude=72.8777,
            destination_latitude=19.0544,
            destination_longitude=72.8311,
            fare_estimate=Decimal('150.00')
        )
        
        # Try to create second ride
        url = reverse('rides:ride-create')
        data = {
            'pickup_latitude': 19.1000,
            'pickup_longitude': 72.9000,
            'destination_latitude': 19.0800,
            'destination_longitude': 72.8800,
            'passenger_count': 1
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active ride', response.data['error'])
    
    def test_ride_detail_access(self):
        """Test ride detail access permissions."""
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=19.0760,
            pickup_longitude=72.8777,
            destination_latitude=19.0544,
            destination_longitude=72.8311,
            fare_estimate=Decimal('150.00')
        )
        
        # Rider can access their own ride
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-detail', kwargs={'id': ride.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(ride.id))
        
        # Operator can access any ride
        self.client.force_authenticate(user=self.operator)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_ride_cancellation(self):
        """Test ride cancellation."""
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=19.0760,
            pickup_longitude=72.8777,
            destination_latitude=19.0544,
            destination_longitude=72.8311,
            fare_estimate=Decimal('150.00')
        )
        
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-action', kwargs={'ride_id': ride.id})
        
        data = {
            'action': 'cancel',
            'cancellation_reason': 'user_cancelled',
            'cancellation_notes': 'Changed my mind'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Ride cancelled successfully')
        
        # Check ride was cancelled
        ride.refresh_from_db()
        self.assertEqual(ride.status, Ride.Status.CANCELLED)
        self.assertEqual(ride.cancellation_reason, Ride.CancellationReason.USER_CANCELLED)
    
    def test_ride_rating(self):
        """Test ride rating."""
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=19.0760,
            pickup_longitude=72.8777,
            destination_latitude=19.0544,
            destination_longitude=72.8311,
            fare_estimate=Decimal('150.00'),
            status=Ride.Status.COMPLETED
        )
        
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-action', kwargs={'ride_id': ride.id})
        
        data = {
            'action': 'rate',
            'rating': 5,
            'feedback': 'Great ride!'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Rating submitted successfully')
        
        # Check rating was saved
        ride.refresh_from_db()
        self.assertEqual(ride.rider_rating, 5)
        self.assertEqual(ride.rider_feedback, 'Great ride!')
    
    def test_active_ride_endpoint(self):
        """Test active ride endpoint."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:active-ride')
        
        # No active ride initially
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['has_active_ride'])
        self.assertIsNone(response.data['ride'])
        
        # Create active ride
        ride = Ride.objects.create(
            rider=self.rider,
            pickup_latitude=19.0760,
            pickup_longitude=72.8777,
            destination_latitude=19.0544,
            destination_longitude=72.8311,
            fare_estimate=Decimal('150.00')
        )
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_active_ride'])
        self.assertEqual(response.data['ride']['id'], str(ride.id))
    
    def test_ride_history(self):
        """Test ride history endpoint."""
        # Create some rides
        for i in range(3):
            Ride.objects.create(
                rider=self.rider,
                pickup_latitude=19.0760,
                pickup_longitude=72.8777,
                destination_latitude=19.0544,
                destination_longitude=72.8311,
                fare_estimate=Decimal('150.00'),
                status=Ride.Status.COMPLETED
            )
        
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:ride-history')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_nearby_vehicles(self):
        """Test nearby vehicles endpoint."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:nearby-vehicles')
        
        response = self.client.get(url, {
            'lat': 19.0760,
            'lng': 72.8777,
            'radius': 10
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vehicles', response.data)
        self.assertIn('count', response.data)
    
    def test_service_areas_endpoint(self):
        """Test service areas endpoint."""
        self.client.force_authenticate(user=self.rider)
        url = reverse('rides:service-areas')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('service_areas', response.data)
        self.assertEqual(len(response.data['service_areas']), 1)
        self.assertEqual(response.data['service_areas'][0]['name'], 'Mumbai')