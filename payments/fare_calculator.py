"""
Fare calculation service for NeuroRides platform.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from datetime import datetime, time
from django.utils import timezone
from django.conf import settings

from rides.models import Ride
from fleet.models import Vehicle

logger = logging.getLogger(__name__)


class FareCalculator:
    """Service for calculating ride fares."""
    
    # Base fare configuration
    BASE_FARE = Decimal('2.50')
    PER_KM_RATE = Decimal('1.20')
    PER_MINUTE_RATE = Decimal('0.25')
    
    # Surge pricing multipliers
    PEAK_HOUR_MULTIPLIER = Decimal('1.5')
    HIGH_DEMAND_MULTIPLIER = Decimal('2.0')
    
    # Vehicle type multipliers
    VEHICLE_TYPE_MULTIPLIERS = {
        Vehicle.VehicleType.COMPACT: Decimal('1.0'),
        Vehicle.VehicleType.SEDAN: Decimal('1.2'),
        Vehicle.VehicleType.SUV: Decimal('1.5'),
        Vehicle.VehicleType.LUXURY: Decimal('2.0'),
    }
    
    # Time-based pricing
    PEAK_HOURS = [
        (time(7, 0), time(9, 30)),   # Morning rush
        (time(17, 0), time(19, 30)), # Evening rush
    ]
    
    # Minimum and maximum fare limits
    MIN_FARE = Decimal('3.00')
    MAX_FARE = Decimal('200.00')
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_fare(self, ride: Ride, vehicle: Optional[Vehicle] = None) -> Dict[str, Any]:
        """Calculate fare for a ride."""
        try:
            # Get distance and duration
            distance_km = self._get_ride_distance(ride)
            duration_minutes = self._get_ride_duration(ride)
            
            # Calculate base fare components
            base_fare = self.BASE_FARE
            distance_fare = distance_km * self.PER_KM_RATE
            time_fare = duration_minutes * self.PER_MINUTE_RATE
            
            # Calculate subtotal
            subtotal = base_fare + distance_fare + time_fare
            
            # Apply vehicle type multiplier
            vehicle_multiplier = self._get_vehicle_multiplier(vehicle)
            subtotal *= vehicle_multiplier
            
            # Apply surge pricing
            surge_multiplier = self._get_surge_multiplier(ride)
            subtotal *= surge_multiplier
            
            # Apply taxes and fees
            taxes_and_fees = self._calculate_taxes_and_fees(subtotal)
            
            # Calculate total fare
            total_fare = subtotal + taxes_and_fees
            
            # Apply fare limits
            total_fare = max(self.MIN_FARE, min(total_fare, self.MAX_FARE))
            
            # Round to 2 decimal places
            total_fare = total_fare.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            return {
                'success': True,
                'fare_breakdown': {
                    'base_fare': float(base_fare),
                    'distance_fare': float(distance_fare),
                    'time_fare': float(time_fare),
                    'subtotal': float(subtotal / surge_multiplier / vehicle_multiplier),
                    'vehicle_multiplier': float(vehicle_multiplier),
                    'surge_multiplier': float(surge_multiplier),
                    'taxes_and_fees': float(taxes_and_fees),
                    'total_fare': float(total_fare),
                },
                'distance_km': float(distance_km),
                'duration_minutes': float(duration_minutes),
                'vehicle_type': vehicle.vehicle_type if vehicle else None,
                'surge_active': surge_multiplier > 1,
            }
            
        except Exception as e:
            self.logger.error(f"Fare calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fare_breakdown': None,
            }
    
    def estimate_fare(self, pickup_lat: float, pickup_lng: float,
                     destination_lat: float, destination_lng: float,
                     vehicle_type: Optional[str] = None) -> Dict[str, Any]:
        """Estimate fare for a potential ride."""
        try:
            # Calculate estimated distance
            distance_km = self._calculate_distance(
                pickup_lat, pickup_lng, destination_lat, destination_lng
            )
            
            # Estimate duration (assuming average speed of 30 km/h)
            duration_minutes = (distance_km / 30) * 60
            
            # Calculate base fare components
            base_fare = self.BASE_FARE
            distance_fare = distance_km * self.PER_KM_RATE
            time_fare = duration_minutes * self.PER_MINUTE_RATE
            
            # Calculate subtotal
            subtotal = base_fare + distance_fare + time_fare
            
            # Apply vehicle type multiplier
            vehicle_multiplier = self.VEHICLE_TYPE_MULTIPLIERS.get(
                vehicle_type, Decimal('1.0')
            )
            subtotal *= vehicle_multiplier
            
            # Apply current surge pricing
            surge_multiplier = self._get_current_surge_multiplier()
            subtotal *= surge_multiplier
            
            # Apply taxes and fees
            taxes_and_fees = self._calculate_taxes_and_fees(subtotal)
            
            # Calculate total fare
            total_fare = subtotal + taxes_and_fees
            
            # Apply fare limits
            total_fare = max(self.MIN_FARE, min(total_fare, self.MAX_FARE))
            
            # Round to 2 decimal places
            total_fare = total_fare.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Calculate fare range (±20%)
            fare_min = (total_fare * Decimal('0.8')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            fare_max = (total_fare * Decimal('1.2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            return {
                'success': True,
                'estimated_fare': float(total_fare),
                'fare_range': {
                    'min': float(fare_min),
                    'max': float(fare_max),
                },
                'fare_breakdown': {
                    'base_fare': float(base_fare),
                    'distance_fare': float(distance_fare),
                    'time_fare': float(time_fare),
                    'subtotal': float(subtotal / surge_multiplier / vehicle_multiplier),
                    'vehicle_multiplier': float(vehicle_multiplier),
                    'surge_multiplier': float(surge_multiplier),
                    'taxes_and_fees': float(taxes_and_fees),
                },
                'distance_km': float(distance_km),
                'estimated_duration_minutes': float(duration_minutes),
                'vehicle_type': vehicle_type,
                'surge_active': surge_multiplier > 1,
            }
            
        except Exception as e:
            self.logger.error(f"Fare estimation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'estimated_fare': None,
            }
    
    def _get_ride_distance(self, ride: Ride) -> Decimal:
        """Get actual ride distance."""
        if ride.actual_distance_km:
            return Decimal(str(ride.actual_distance_km))
        elif ride.estimated_distance_km:
            return Decimal(str(ride.estimated_distance_km))
        else:
            # Calculate distance from coordinates
            return self._calculate_distance(
                ride.pickup_latitude,
                ride.pickup_longitude,
                ride.destination_latitude,
                ride.destination_longitude
            )
    
    def _get_ride_duration(self, ride: Ride) -> Decimal:
        """Get actual ride duration in minutes."""
        if ride.actual_duration_minutes:
            return Decimal(str(ride.actual_duration_minutes))
        elif ride.estimated_duration_minutes:
            return Decimal(str(ride.estimated_duration_minutes))
        elif ride.picked_up_at and ride.completed_at:
            # Calculate actual duration
            duration = ride.completed_at - ride.picked_up_at
            return Decimal(str(duration.total_seconds() / 60))
        else:
            # Estimate duration based on distance
            distance_km = self._get_ride_distance(ride)
            return (distance_km / 30) * 60  # Assuming 30 km/h average speed
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> Decimal:
        """Calculate distance between two points using Haversine formula."""
        from math import radians, cos, sin, asin, sqrt
        
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        
        # Haversine formula
        dlng = lng2 - lng1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * asin(sqrt(a))
        
        # Radius of earth in kilometers
        r = 6371
        
        distance = c * r
        return Decimal(str(round(distance, 2)))
    
    def _get_vehicle_multiplier(self, vehicle: Optional[Vehicle]) -> Decimal:
        """Get vehicle type multiplier."""
        if not vehicle:
            return Decimal('1.0')
        
        return self.VEHICLE_TYPE_MULTIPLIERS.get(
            vehicle.vehicle_type, Decimal('1.0')
        )
    
    def _get_surge_multiplier(self, ride: Ride) -> Decimal:
        """Get surge pricing multiplier for a ride."""
        # Check if ride was during peak hours
        if self._is_peak_hour(ride.requested_at):
            return self.PEAK_HOUR_MULTIPLIER
        
        # Check for high demand (simplified logic)
        if self._is_high_demand_period(ride.requested_at):
            return self.HIGH_DEMAND_MULTIPLIER
        
        return Decimal('1.0')
    
    def _get_current_surge_multiplier(self) -> Decimal:
        """Get current surge pricing multiplier."""
        now = timezone.now()
        
        # Check if current time is peak hour
        if self._is_peak_hour(now):
            return self.PEAK_HOUR_MULTIPLIER
        
        # Check for current high demand
        if self._is_high_demand_period(now):
            return self.HIGH_DEMAND_MULTIPLIER
        
        return Decimal('1.0')
    
    def _is_peak_hour(self, dt: datetime) -> bool:
        """Check if datetime is during peak hours."""
        current_time = dt.time()
        
        for start_time, end_time in self.PEAK_HOURS:
            if start_time <= current_time <= end_time:
                return True
        
        return False
    
    def _is_high_demand_period(self, dt: datetime) -> bool:
        """Check if datetime is during high demand period."""
        # Simplified logic - check if there are many pending rides
        from rides.models import Ride
        
        # Count rides requested in the last 30 minutes
        thirty_minutes_ago = dt - timezone.timedelta(minutes=30)
        recent_rides = Ride.objects.filter(
            requested_at__gte=thirty_minutes_ago,
            status__in=[Ride.Status.REQUESTED, Ride.Status.ASSIGNED]
        ).count()
        
        # If more than 10 rides in 30 minutes, consider it high demand
        return recent_rides > 10
    
    def _calculate_taxes_and_fees(self, subtotal: Decimal) -> Decimal:
        """Calculate taxes and fees."""
        # Service fee (5% of subtotal)
        service_fee = subtotal * Decimal('0.05')
        
        # Tax (8% of subtotal + service fee)
        tax = (subtotal + service_fee) * Decimal('0.08')
        
        return service_fee + tax
    
    def get_fare_breakdown_explanation(self) -> Dict[str, str]:
        """Get explanation of fare components."""
        return {
            'base_fare': f'Base fare: ${self.BASE_FARE}',
            'distance_rate': f'Distance rate: ${self.PER_KM_RATE} per km',
            'time_rate': f'Time rate: ${self.PER_MINUTE_RATE} per minute',
            'service_fee': 'Service fee: 5% of subtotal',
            'tax': 'Tax: 8% of subtotal + service fee',
            'vehicle_types': {
                'compact': f'Compact: {self.VEHICLE_TYPE_MULTIPLIERS[Vehicle.VehicleType.COMPACT]}x',
                'sedan': f'Sedan: {self.VEHICLE_TYPE_MULTIPLIERS[Vehicle.VehicleType.SEDAN]}x',
                'suv': f'SUV: {self.VEHICLE_TYPE_MULTIPLIERS[Vehicle.VehicleType.SUV]}x',
                'luxury': f'Luxury: {self.VEHICLE_TYPE_MULTIPLIERS[Vehicle.VehicleType.LUXURY]}x',
            },
            'surge_pricing': {
                'peak_hours': f'Peak hours: {self.PEAK_HOUR_MULTIPLIER}x',
                'high_demand': f'High demand: {self.HIGH_DEMAND_MULTIPLIER}x',
            },
            'limits': {
                'minimum': f'Minimum fare: ${self.MIN_FARE}',
                'maximum': f'Maximum fare: ${self.MAX_FARE}',
            }
        }