"""
Fleet management models for NeuroRides platform.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

User = get_user_model()


class Vehicle(models.Model):
    """Vehicle model for autonomous fleet management."""
    
    class Status(models.TextChoices):
        IDLE = 'idle', _('Idle')
        ASSIGNED = 'assigned', _('Assigned')
        IN_RIDE = 'in_ride', _('In Ride')
        MAINTENANCE = 'maintenance', _('Maintenance')
        OFFLINE = 'offline', _('Offline')
    
    class VehicleType(models.TextChoices):
        SEDAN = 'sedan', _('Sedan')
        SUV = 'suv', _('SUV')
        COMPACT = 'compact', _('Compact')
        LUXURY = 'luxury', _('Luxury')
    
    # Basic vehicle information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license_plate = models.CharField(
        max_length=20,
        unique=True,
        help_text=_('Vehicle license plate number')
    )
    model = models.CharField(
        max_length=100,
        help_text=_('Vehicle model (e.g., Tesla Model 3)')
    )
    manufacturer = models.CharField(
        max_length=50,
        default='Tesla',
        help_text=_('Vehicle manufacturer')
    )
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(2020), MaxValueValidator(2030)],
        help_text=_('Manufacturing year')
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.SEDAN,
        help_text=_('Type of vehicle')
    )
    
    # Status and location
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OFFLINE,
        help_text=_('Current vehicle status')
    )
    
    # Location fields (using FloatField for SQLite compatibility)
    # Will be converted to PostGIS PointField later
    current_latitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_('Current latitude coordinate')
    )
    current_longitude = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_('Current longitude coordinate')
    )
    
    # Vehicle metrics
    battery_level = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Current battery level percentage')
    )
    mileage = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        help_text=_('Total mileage in kilometers')
    )
    
    # Capacity and features
    passenger_capacity = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text=_('Maximum passenger capacity')
    )
    has_wheelchair_access = models.BooleanField(
        default=False,
        help_text=_('Vehicle has wheelchair accessibility')
    )
    has_child_seat = models.BooleanField(
        default=False,
        help_text=_('Vehicle has child seat available')
    )
    
    # Maintenance information
    last_maintenance = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date of last maintenance')
    )
    next_maintenance_due = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date when next maintenance is due')
    )
    maintenance_mileage_threshold = models.FloatField(
        default=10000.0,
        help_text=_('Mileage threshold for maintenance (km)')
    )
    
    # Operational metrics
    total_rides = models.PositiveIntegerField(
        default=0,
        help_text=_('Total number of rides completed')
    )
    total_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Total revenue generated')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Last time vehicle sent telemetry data')
    )
    
    # Assignment tracking (will be added when rides app is implemented)
    # current_ride = models.ForeignKey(
    #     'rides.Ride',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='assigned_vehicle',
    #     help_text=_('Currently assigned ride')
    # )
    
    class Meta:
        db_table = 'fleet_vehicle'
        verbose_name = _('Vehicle')
        verbose_name_plural = _('Vehicles')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['license_plate']),
            models.Index(fields=['current_latitude', 'current_longitude']),
            models.Index(fields=['battery_level']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['next_maintenance_due']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.license_plate} - {self.model} ({self.get_status_display()})"
    
    @property
    def is_available(self):
        """Check if vehicle is available for assignment."""
        return (
            self.status == self.Status.IDLE and
            self.battery_level >= 20 and  # Minimum battery level
            self.current_latitude is not None and
            self.current_longitude is not None
        )
    
    @property
    def needs_maintenance(self):
        """Check if vehicle needs maintenance."""
        if self.next_maintenance_due and self.next_maintenance_due <= timezone.now():
            return True
        if self.mileage >= self.maintenance_mileage_threshold:
            return True
        return False
    
    @property
    def is_online(self):
        """Check if vehicle is online (sent data recently)."""
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen).total_seconds() < 300  # 5 minutes
    
    @property
    def current_location(self):
        """Get current location as tuple."""
        if self.current_latitude is not None and self.current_longitude is not None:
            return (self.current_latitude, self.current_longitude)
        return None
    
    def update_location(self, latitude, longitude):
        """Update vehicle location."""
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_seen = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'last_seen'])
    
    def update_battery(self, battery_level):
        """Update battery level."""
        self.battery_level = max(0, min(100, battery_level))
        self.last_seen = timezone.now()
        self.save(update_fields=['battery_level', 'last_seen'])
    
    def assign_to_ride(self, ride):
        """Assign vehicle to a ride."""
        self.status = self.Status.ASSIGNED
        # self.current_ride = ride  # Will be enabled when rides app is implemented
        self.save(update_fields=['status'])
    
    def start_ride(self):
        """Mark vehicle as in ride."""
        self.status = self.Status.IN_RIDE
        self.save(update_fields=['status'])
    
    def complete_ride(self, ride_distance=0, ride_revenue=0):
        """Complete current ride and update metrics."""
        from decimal import Decimal
        
        self.status = self.Status.IDLE
        # self.current_ride = None  # Will be enabled when rides app is implemented
        self.total_rides += 1
        self.mileage += ride_distance
        
        # Ensure ride_revenue is Decimal for proper addition
        if isinstance(ride_revenue, (int, float)):
            ride_revenue = Decimal(str(ride_revenue))
        elif ride_revenue is None:
            ride_revenue = Decimal('0')
        
        # Ensure total_revenue is also Decimal
        if not isinstance(self.total_revenue, Decimal):
            self.total_revenue = Decimal(str(self.total_revenue or 0))
        
        self.total_revenue += ride_revenue
        
        self.save(update_fields=[
            'status', 'total_rides', 
            'mileage', 'total_revenue'
        ])
    
    def set_maintenance_mode(self):
        """Set vehicle to maintenance mode."""
        self.status = self.Status.MAINTENANCE
        # self.current_ride = None  # Will be enabled when rides app is implemented
        self.save(update_fields=['status'])
    
    def complete_maintenance(self):
        """Complete maintenance and return to service."""
        self.status = self.Status.IDLE
        self.last_maintenance = timezone.now()
        # Schedule next maintenance (3 months or 5000km, whichever comes first)
        self.next_maintenance_due = timezone.now() + timezone.timedelta(days=90)
        self.maintenance_mileage_threshold = self.mileage + 5000
        self.save(update_fields=[
            'status', 'last_maintenance', 'next_maintenance_due',
            'maintenance_mileage_threshold'
        ])


class VehicleTelemetry(models.Model):
    """Vehicle telemetry data for real-time monitoring."""
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='telemetry_data',
        help_text=_('Vehicle this telemetry belongs to')
    )
    
    # Location data
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_('Latitude coordinate')
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_('Longitude coordinate')
    )
    
    # Motion data
    speed = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(200)],
        help_text=_('Current speed in km/h')
    )
    heading = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(360)],
        help_text=_('Direction heading in degrees')
    )
    
    # Vehicle status
    battery_level = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Battery level percentage')
    )
    
    # Environmental data
    temperature = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Internal temperature in Celsius')
    )
    
    # System status
    engine_status = models.CharField(
        max_length=20,
        choices=[
            ('running', _('Running')),
            ('idle', _('Idle')),
            ('charging', _('Charging')),
            ('error', _('Error')),
        ],
        default='idle',
        help_text=_('Engine/motor status')
    )
    
    # Diagnostic data
    diagnostic_codes = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Diagnostic trouble codes')
    )
    
    # Passenger information
    passenger_count = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(8)],
        help_text=_('Current number of passengers')
    )
    
    # Timestamps
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When this telemetry data was recorded')
    )
    
    class Meta:
        db_table = 'fleet_vehicletelemetry'
        verbose_name = _('Vehicle Telemetry')
        verbose_name_plural = _('Vehicle Telemetry Data')
        indexes = [
            models.Index(fields=['vehicle', '-timestamp']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['battery_level']),
            models.Index(fields=['speed']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.vehicle.license_plate} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Override save to update vehicle location and status."""
        super().save(*args, **kwargs)
        
        # Update vehicle's current location and battery
        self.vehicle.update_location(self.latitude, self.longitude)
        self.vehicle.update_battery(self.battery_level)


class MaintenanceRecord(models.Model):
    """Maintenance record for vehicles."""
    
    class MaintenanceType(models.TextChoices):
        ROUTINE = 'routine', _('Routine Maintenance')
        REPAIR = 'repair', _('Repair')
        INSPECTION = 'inspection', _('Inspection')
        UPGRADE = 'upgrade', _('Upgrade')
        EMERGENCY = 'emergency', _('Emergency Repair')
    
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        help_text=_('Vehicle being maintained')
    )
    
    maintenance_type = models.CharField(
        max_length=20,
        choices=MaintenanceType.choices,
        help_text=_('Type of maintenance')
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text=_('Maintenance status')
    )
    
    # Scheduling
    scheduled_date = models.DateTimeField(
        help_text=_('Scheduled maintenance date')
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When maintenance actually started')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When maintenance was completed')
    )
    
    # Details
    description = models.TextField(
        help_text=_('Description of maintenance work')
    )
    notes = models.TextField(
        blank=True,
        help_text=_('Additional notes from technician')
    )
    
    # Costs
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Estimated maintenance cost')
    )
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Actual maintenance cost')
    )
    
    # Personnel
    technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'operator'},
        help_text=_('Technician assigned to this maintenance')
    )
    
    # Mileage at maintenance
    mileage_at_maintenance = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Vehicle mileage at time of maintenance')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fleet_maintenancerecord'
        verbose_name = _('Maintenance Record')
        verbose_name_plural = _('Maintenance Records')
        indexes = [
            models.Index(fields=['vehicle', '-scheduled_date']),
            models.Index(fields=['status']),
            models.Index(fields=['maintenance_type']),
            models.Index(fields=['scheduled_date']),
        ]
        ordering = ['-scheduled_date']
    
    def __str__(self):
        return f"{self.vehicle.license_plate} - {self.get_maintenance_type_display()} ({self.scheduled_date.date()})"
    
    def start_maintenance(self):
        """Start the maintenance work."""
        self.status = self.Status.IN_PROGRESS
        self.started_at = timezone.now()
        self.mileage_at_maintenance = self.vehicle.mileage
        self.save(update_fields=['status', 'started_at', 'mileage_at_maintenance'])
        
        # Set vehicle to maintenance mode
        self.vehicle.set_maintenance_mode()
    
    def complete_maintenance(self, actual_cost=None, notes=''):
        """Complete the maintenance work."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if actual_cost is not None:
            self.actual_cost = actual_cost
        if notes:
            self.notes = notes
        self.save(update_fields=['status', 'completed_at', 'actual_cost', 'notes'])
        
        # Return vehicle to service
        self.vehicle.complete_maintenance()
    
    @property
    def duration(self):
        """Get maintenance duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_overdue(self):
        """Check if maintenance is overdue."""
        return (
            self.status == self.Status.SCHEDULED and
            self.scheduled_date < timezone.now()
        )