"""
Dispatch system models for NeuroRides platform.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class DispatchRequest(models.Model):
    """Model for tracking dispatch requests and assignments."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        ASSIGNED = 'assigned', _('Assigned')
        FAILED = 'failed', _('Failed')
        EXPIRED = 'expired', _('Expired')
    
    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        NORMAL = 'normal', _('Normal')
        HIGH = 'high', _('High')
        URGENT = 'urgent', _('Urgent')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.OneToOneField(
        'rides.Ride',
        on_delete=models.CASCADE,
        related_name='dispatch_request',
        help_text=_('Ride requesting dispatch')
    )
    
    # Request details
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_('Current dispatch status')
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        help_text=_('Dispatch priority level')
    )
    
    # Assignment details
    assigned_vehicle = models.ForeignKey(
        'fleet.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispatch_assignments',
        help_text=_('Vehicle assigned to this request')
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        help_text=_('When this dispatch request expires')
    )
    
    # Algorithm details
    algorithm_used = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('Algorithm used for vehicle assignment')
    )
    search_radius_km = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Search radius used for finding vehicles')
    )
    vehicles_considered = models.IntegerField(
        default=0,
        help_text=_('Number of vehicles considered for assignment')
    )
    
    # Failure tracking
    failure_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Reason for dispatch failure')
    )
    retry_count = models.IntegerField(
        default=0,
        help_text=_('Number of retry attempts')
    )
    
    class Meta:
        db_table = 'dispatch_dispatchrequest'
        verbose_name = _('Dispatch Request')
        verbose_name_plural = _('Dispatch Requests')
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispatch {self.id} - {self.ride.rider.username} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """Set expiration time if not provided."""
        if not self.expires_at:
            # Default expiration: 10 minutes for normal, 5 for urgent
            minutes = 5 if self.priority == self.Priority.URGENT else 10
            self.expires_at = timezone.now() + timedelta(minutes=minutes)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if dispatch request has expired."""
        return timezone.now() > self.expires_at
    
    @property
    def processing_duration(self):
        """Get processing duration if completed."""
        if self.processing_started_at and self.assigned_at:
            return self.assigned_at - self.processing_started_at
        return None
    
    def start_processing(self):
        """Mark dispatch as processing."""
        self.status = self.Status.PROCESSING
        self.processing_started_at = timezone.now()
        self.save(update_fields=['status', 'processing_started_at'])
    
    def assign_vehicle(self, vehicle, algorithm_used, search_radius=None, vehicles_considered=0):
        """Assign a vehicle to this dispatch request."""
        self.status = self.Status.ASSIGNED
        self.assigned_vehicle = vehicle
        self.assigned_at = timezone.now()
        self.algorithm_used = algorithm_used
        self.search_radius_km = search_radius
        self.vehicles_considered = vehicles_considered
        
        self.save(update_fields=[
            'status', 'assigned_vehicle', 'assigned_at', 
            'algorithm_used', 'search_radius_km', 'vehicles_considered'
        ])
        
        # Assign vehicle to ride
        self.ride.assign_vehicle(vehicle)
    
    def mark_failed(self, reason, retry=False):
        """Mark dispatch as failed."""
        self.status = self.Status.FAILED
        self.failure_reason = reason
        
        if retry:
            self.retry_count += 1
        
        self.save(update_fields=['status', 'failure_reason', 'retry_count'])
    
    def expire_request(self):
        """Mark request as expired."""
        self.status = self.Status.EXPIRED
        self.save(update_fields=['status'])


class DispatchAlgorithmConfig(models.Model):
    """Configuration for dispatch algorithms."""
    
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text=_('Algorithm name')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this algorithm is active')
    )
    priority = models.IntegerField(
        default=0,
        help_text=_('Algorithm priority (higher = preferred)')
    )
    
    # Algorithm parameters
    max_search_radius_km = models.FloatField(
        default=10.0,
        help_text=_('Maximum search radius in kilometers')
    )
    max_vehicles_to_consider = models.IntegerField(
        default=20,
        help_text=_('Maximum number of vehicles to consider')
    )
    min_battery_level = models.IntegerField(
        default=20,
        help_text=_('Minimum battery level for vehicle selection')
    )
    
    # Scoring weights
    distance_weight = models.FloatField(
        default=0.4,
        help_text=_('Weight for distance factor in scoring')
    )
    battery_weight = models.FloatField(
        default=0.2,
        help_text=_('Weight for battery level in scoring')
    )
    efficiency_weight = models.FloatField(
        default=0.2,
        help_text=_('Weight for vehicle efficiency in scoring')
    )
    availability_weight = models.FloatField(
        default=0.2,
        help_text=_('Weight for availability time in scoring')
    )
    
    # Time constraints
    max_processing_time_seconds = models.IntegerField(
        default=30,
        help_text=_('Maximum time allowed for processing')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dispatch_algorithconfig'
        verbose_name = _('Dispatch Algorithm Config')
        verbose_name_plural = _('Dispatch Algorithm Configs')
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class DispatchMetrics(models.Model):
    """Metrics and analytics for dispatch performance."""
    
    date = models.DateField(
        help_text=_('Date for these metrics')
    )
    algorithm_name = models.CharField(
        max_length=50,
        help_text=_('Algorithm name')
    )
    
    # Volume metrics
    total_requests = models.IntegerField(
        default=0,
        help_text=_('Total dispatch requests')
    )
    successful_assignments = models.IntegerField(
        default=0,
        help_text=_('Successful vehicle assignments')
    )
    failed_assignments = models.IntegerField(
        default=0,
        help_text=_('Failed assignments')
    )
    expired_requests = models.IntegerField(
        default=0,
        help_text=_('Expired requests')
    )
    
    # Performance metrics
    average_processing_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Average processing time in seconds')
    )
    average_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Average distance to assigned vehicle')
    )
    average_eta_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Average ETA in minutes')
    )
    
    # Success rates
    success_rate = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Success rate percentage')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dispatch_metrics'
        verbose_name = _('Dispatch Metrics')
        verbose_name_plural = _('Dispatch Metrics')
        unique_together = ['date', 'algorithm_name']
        indexes = [
            models.Index(fields=['date', 'algorithm_name']),
            models.Index(fields=['-date']),
        ]
        ordering = ['-date', 'algorithm_name']
    
    def __str__(self):
        return f"{self.algorithm_name} - {self.date}"
    
    @property
    def failure_rate(self):
        """Calculate failure rate."""
        if self.total_requests > 0:
            return (self.failed_assignments / self.total_requests) * 100
        return 0
    
    @property
    def expiration_rate(self):
        """Calculate expiration rate."""
        if self.total_requests > 0:
            return (self.expired_requests / self.total_requests) * 100
        return 0