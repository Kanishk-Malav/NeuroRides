"""
Ride booking and management models for NeuroRides platform.
"""

import uuid
import math
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Ride(models.Model):
    """Ride model for booking and tracking rides."""
    
    class Status(models.TextChoices):
        REQUESTED = 'requested', _('Requested')
        ASSIGNED = 'assigned', _('Assigned')
        PICKUP = 'pickup', _('En Route to Pickup')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    class CancellationReason(models.TextChoices):
        USER_CANCELLED = 'user_cancelled', _('User Cancelled')
        DRIVER_CANCELLED = 'driver_cancelled', _('Driver Cancelled')
        NO_DRIVER = 'no_driver', _('No Driver Available')
        SYSTEM_ERROR = 'system_error', _('System Error')
        PAYMENT_FAILED = 'payment_failed', _('Payment Failed')
    
    # Basic ride information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rides',
        help_text=_('User who booked the ride')
    )
    vehicle = models.ForeignKey(
        'fleet.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rides',
        help_text=_('Assigned vehicle')
    )
    
    # Location information (using FloatField for SQLite compatibility)
    pickup_latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_('Pickup location latitude')
    )
    pickup_longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_('Pickup location longitude')
    )
    pickup_address = models.CharField(
        max_length=500,
        blank=True,
        help_text=_('Pickup address description')
    )
    
    destination_latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_('Destination latitude')
    )
    destination_longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_('Destination longitude')
    )
    destination_address = models.CharField(
        max_length=500,
        blank=True,
        help_text=_('Destination address description')
    )
    
    # Ride status and timing
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
        help_text=_('Current ride status')
    )
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    pickup_started_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Fare and payment
    fare_estimate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Estimated fare before ride')
    )
    final_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Final fare after ride completion')
    )
    
    # Distance and duration
    estimated_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Estimated distance in kilometers')
    )
    actual_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Actual distance traveled in kilometers')
    )
    estimated_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Estimated duration in minutes')
    )
    actual_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Actual duration in minutes')
    )
    
    # Cancellation information
    cancellation_reason = models.CharField(
        max_length=20,
        choices=CancellationReason.choices,
        null=True,
        blank=True,
        help_text=_('Reason for cancellation')
    )
    cancellation_notes = models.TextField(
        blank=True,
        help_text=_('Additional cancellation notes')
    )
    
    # Special requirements
    passenger_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text=_('Number of passengers')
    )
    requires_wheelchair_access = models.BooleanField(
        default=False,
        help_text=_('Requires wheelchair accessible vehicle')
    )
    requires_child_seat = models.BooleanField(
        default=False,
        help_text=_('Requires child seat')
    )
    
    # Ride notes and preferences
    pickup_notes = models.TextField(
        blank=True,
        help_text=_('Special pickup instructions')
    )
    ride_notes = models.TextField(
        blank=True,
        help_text=_('Special ride instructions')
    )
    
    # Rating and feedback
    rider_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rider rating (1-5 stars)')
    )
    rider_feedback = models.TextField(
        blank=True,
        help_text=_('Rider feedback')
    )
    
    class Meta:
        db_table = 'rides_ride'
        verbose_name = _('Ride')
        verbose_name_plural = _('Rides')
        indexes = [
            models.Index(fields=['rider', '-requested_at']),
            models.Index(fields=['vehicle', '-requested_at']),
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['pickup_latitude', 'pickup_longitude']),
            models.Index(fields=['destination_latitude', 'destination_longitude']),
            models.Index(fields=['requested_at']),
        ]
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Ride {self.id} - {self.rider.username} ({self.get_status_display()})"
    
    @property
    def pickup_location(self):
        """Get pickup location as tuple."""
        return (self.pickup_latitude, self.pickup_longitude)
    
    @property
    def destination_location(self):
        """Get destination location as tuple."""
        return (self.destination_latitude, self.destination_longitude)
    
    @property
    def duration(self):
        """Get ride duration if completed."""
        if self.picked_up_at and self.completed_at:
            return self.completed_at - self.picked_up_at
        return None
    
    @property
    def total_duration(self):
        """Get total duration from request to completion."""
        if self.completed_at:
            return self.completed_at - self.requested_at
        return None
    
    @property
    def is_active(self):
        """Check if ride is currently active."""
        return self.status in [
            self.Status.REQUESTED,
            self.Status.ASSIGNED,
            self.Status.PICKUP,
            self.Status.IN_PROGRESS
        ]
    
    @property
    def can_be_cancelled(self):
        """Check if ride can be cancelled."""
        return self.status in [
            self.Status.REQUESTED,
            self.Status.ASSIGNED,
            self.Status.PICKUP
        ]
    
    def calculate_distance(self):
        """Calculate straight-line distance between pickup and destination."""
        return self._haversine_distance(
            self.pickup_latitude, self.pickup_longitude,
            self.destination_latitude, self.destination_longitude
        )
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def assign_vehicle(self, vehicle):
        """Assign a vehicle to this ride."""
        if self.status != self.Status.REQUESTED:
            raise ValueError("Can only assign vehicle to requested rides")
        
        self.vehicle = vehicle
        self.status = self.Status.ASSIGNED
        self.assigned_at = timezone.now()
        self.save(update_fields=['vehicle', 'status', 'assigned_at'])
        
        # Update vehicle status
        vehicle.assign_to_ride(self)
    
    def start_pickup(self):
        """Mark ride as en route to pickup."""
        if self.status != self.Status.ASSIGNED:
            raise ValueError("Can only start pickup for assigned rides")
        
        self.status = self.Status.PICKUP
        self.pickup_started_at = timezone.now()
        self.save(update_fields=['status', 'pickup_started_at'])
    
    def confirm_pickup(self):
        """Confirm passenger pickup and start ride."""
        if self.status != self.Status.PICKUP:
            raise ValueError("Can only confirm pickup for rides en route to pickup")
        
        self.status = self.Status.IN_PROGRESS
        self.picked_up_at = timezone.now()
        self.save(update_fields=['status', 'picked_up_at'])
        
        # Update vehicle status
        if self.vehicle:
            self.vehicle.start_ride()
    
    def complete_ride(self, actual_distance_km=None, final_fare=None):
        """Complete the ride."""
        if self.status != self.Status.IN_PROGRESS:
            raise ValueError("Can only complete rides in progress")
        
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        
        if actual_distance_km is not None:
            self.actual_distance_km = actual_distance_km
        
        if final_fare is not None:
            self.final_fare = final_fare
        else:
            # Use fare estimate if no final fare provided
            self.final_fare = self.fare_estimate
        
        # Calculate actual duration
        if self.picked_up_at:
            duration = self.completed_at - self.picked_up_at
            self.actual_duration_minutes = int(duration.total_seconds() / 60)
        
        self.save(update_fields=[
            'status', 'completed_at', 'actual_distance_km', 
            'final_fare', 'actual_duration_minutes'
        ])
        
        # Update vehicle status and metrics
        if self.vehicle:
            self.vehicle.complete_ride(
                ride_distance=self.actual_distance_km or 0,
                ride_revenue=self.final_fare or 0
            )
    
    def cancel_ride(self, reason, notes='', cancelled_by=None):
        """Cancel the ride."""
        if not self.can_be_cancelled:
            raise ValueError(f"Cannot cancel ride with status {self.status}")
        
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.cancellation_notes = notes
        
        self.save(update_fields=[
            'status', 'cancelled_at', 'cancellation_reason', 'cancellation_notes'
        ])
        
        # Free up the vehicle if assigned
        if self.vehicle and self.vehicle.status in ['assigned', 'in_ride']:
            self.vehicle.status = 'idle'
            self.vehicle.save(update_fields=['status'])


class RideFareCalculator:
    """Service class for calculating ride fares."""
    
    # Base fare configuration
    BASE_FARE = Decimal('50.00')  # Base fare in INR
    RATE_PER_KM = Decimal('12.00')  # Rate per kilometer
    RATE_PER_MINUTE = Decimal('2.00')  # Rate per minute
    SURGE_MULTIPLIER = Decimal('1.0')  # Default surge multiplier
    
    # Special vehicle type multipliers
    VEHICLE_TYPE_MULTIPLIERS = {
        'sedan': Decimal('1.0'),
        'suv': Decimal('1.2'),
        'luxury': Decimal('1.5'),
        'compact': Decimal('0.9'),
    }
    
    # Special requirements surcharge
    WHEELCHAIR_SURCHARGE = Decimal('20.00')
    CHILD_SEAT_SURCHARGE = Decimal('10.00')
    
    @classmethod
    def calculate_fare_estimate(
        cls,
        distance_km,
        estimated_duration_minutes=None,
        vehicle_type='sedan',
        requires_wheelchair_access=False,
        requires_child_seat=False,
        surge_multiplier=None
    ):
        """Calculate fare estimate for a ride."""
        
        # Base calculation
        fare = cls.BASE_FARE
        
        # Distance component
        fare += Decimal(str(distance_km)) * cls.RATE_PER_KM
        
        # Time component (if provided)
        if estimated_duration_minutes:
            fare += Decimal(str(estimated_duration_minutes)) * cls.RATE_PER_MINUTE
        
        # Vehicle type multiplier
        vehicle_multiplier = cls.VEHICLE_TYPE_MULTIPLIERS.get(
            vehicle_type, Decimal('1.0')
        )
        fare *= vehicle_multiplier
        
        # Special requirements
        if requires_wheelchair_access:
            fare += cls.WHEELCHAIR_SURCHARGE
        
        if requires_child_seat:
            fare += cls.CHILD_SEAT_SURCHARGE
        
        # Surge pricing
        if surge_multiplier:
            fare *= Decimal(str(surge_multiplier))
        else:
            fare *= cls.SURGE_MULTIPLIER
        
        # Round to 2 decimal places
        return fare.quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_final_fare(
        cls,
        ride,
        actual_distance_km=None,
        actual_duration_minutes=None
    ):
        """Calculate final fare based on actual ride data."""
        
        # Use actual data if available, otherwise fall back to estimates
        distance = actual_distance_km or ride.estimated_distance_km or 0
        duration = actual_duration_minutes or ride.estimated_duration_minutes or 0
        
        vehicle_type = 'sedan'  # Default
        if ride.vehicle and hasattr(ride.vehicle, 'vehicle_type'):
            vehicle_type = ride.vehicle.vehicle_type
        
        return cls.calculate_fare_estimate(
            distance_km=distance,
            estimated_duration_minutes=duration,
            vehicle_type=vehicle_type,
            requires_wheelchair_access=ride.requires_wheelchair_access,
            requires_child_seat=ride.requires_child_seat
        )


class RideRequest(models.Model):
    """Model for tracking ride requests before they become rides."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        MATCHED = 'matched', _('Matched')
        EXPIRED = 'expired', _('Expired')
        CANCELLED = 'cancelled', _('Cancelled')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ride_requests'
    )
    
    # Location information
    pickup_latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    pickup_longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    destination_latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    destination_longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    
    # Request details
    passenger_count = models.PositiveIntegerField(default=1)
    requires_wheelchair_access = models.BooleanField(default=False)
    requires_child_seat = models.BooleanField(default=False)
    
    # Status and timing
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Matching information
    matched_ride = models.OneToOneField(
        Ride,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request'
    )
    
    class Meta:
        db_table = 'rides_riderequest'
        verbose_name = _('Ride Request')
        verbose_name_plural = _('Ride Requests')
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"RideRequest {self.id} - {self.rider.username} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """Set expiration time if not provided."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if request has expired."""
        return timezone.now() > self.expires_at
    
    def expire_request(self):
        """Mark request as expired."""
        self.status = self.Status.EXPIRED
        self.save(update_fields=['status'])
    
    def match_to_ride(self, ride):
        """Match this request to a ride."""
        self.status = self.Status.MATCHED
        self.matched_ride = ride
        self.save(update_fields=['status', 'matched_ride'])


class ServiceArea(models.Model):
    """Model for defining service areas where rides are available."""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Bounding box for the service area
    north_lat = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    south_lat = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    east_lng = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    west_lng = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    
    # Service configuration
    is_active = models.BooleanField(default=True)
    surge_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('1.0'),
        help_text=_('Current surge pricing multiplier')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'rides_servicearea'
        verbose_name = _('Service Area')
        verbose_name_plural = _('Service Areas')
    
    def __str__(self):
        return self.name
    
    def contains_location(self, latitude, longitude):
        """Check if a location is within this service area."""
        return (
            self.south_lat <= latitude <= self.north_lat and
            self.west_lng <= longitude <= self.east_lng
        )
    
    @classmethod
    def get_service_area_for_location(cls, latitude, longitude):
        """Get the service area that contains the given location."""
        for area in cls.objects.filter(is_active=True):
            if area.contains_location(latitude, longitude):
                return area
        return None