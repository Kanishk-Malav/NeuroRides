"""
Signal handlers for rides app.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Ride, RideRequest, RideFareCalculator


@receiver(pre_save, sender=Ride)
def calculate_ride_estimates(sender, instance, **kwargs):
    """Calculate fare and distance estimates before saving ride."""
    
    # Calculate distance if not provided
    if not instance.estimated_distance_km:
        instance.estimated_distance_km = instance.calculate_distance()
    
    # Estimate duration based on distance (assuming 30 km/h average speed)
    if not instance.estimated_duration_minutes and instance.estimated_distance_km:
        # Add 10 minutes for pickup and traffic
        estimated_minutes = (instance.estimated_distance_km / 30) * 60 + 10
        instance.estimated_duration_minutes = int(estimated_minutes)
    
    # Calculate fare estimate if not provided
    if not instance.fare_estimate and instance.estimated_distance_km:
        vehicle_type = 'sedan'  # Default
        if instance.vehicle and hasattr(instance.vehicle, 'vehicle_type'):
            vehicle_type = instance.vehicle.vehicle_type
        
        instance.fare_estimate = RideFareCalculator.calculate_fare_estimate(
            distance_km=instance.estimated_distance_km,
            estimated_duration_minutes=instance.estimated_duration_minutes,
            vehicle_type=vehicle_type,
            requires_wheelchair_access=instance.requires_wheelchair_access,
            requires_child_seat=instance.requires_child_seat
        )


@receiver(post_save, sender=Ride)
def handle_ride_status_changes(sender, instance, created, **kwargs):
    """Handle ride status changes and update related models."""
    
    if created:
        # New ride created - could trigger notifications here
        pass
    
    # Handle vehicle assignment
    if instance.vehicle and instance.status == Ride.Status.ASSIGNED:
        # Ensure vehicle is marked as assigned
        if instance.vehicle.status != 'assigned':
            instance.vehicle.status = 'assigned'
            instance.vehicle.save(update_fields=['status'])
    
    # Handle ride completion
    if instance.status == Ride.Status.COMPLETED:
        # Calculate final fare if not set
        if not instance.final_fare:
            instance.final_fare = RideFareCalculator.calculate_final_fare(
                ride=instance,
                actual_distance_km=instance.actual_distance_km,
                actual_duration_minutes=instance.actual_duration_minutes
            )
            instance.save(update_fields=['final_fare'])
    
    # Handle ride cancellation
    if instance.status == Ride.Status.CANCELLED:
        # Free up the vehicle
        if instance.vehicle and instance.vehicle.status in ['assigned', 'in_ride']:
            instance.vehicle.status = 'idle'
            instance.vehicle.save(update_fields=['status'])


@receiver(post_save, sender=RideRequest)
def handle_ride_request_creation(sender, instance, created, **kwargs):
    """Handle ride request creation."""
    
    if created:
        # New ride request created
        # Could trigger dispatch algorithm here
        pass


# Periodic cleanup of expired ride requests
from django.core.management.base import BaseCommand
from django.utils import timezone


def cleanup_expired_requests():
    """Clean up expired ride requests."""
    expired_requests = RideRequest.objects.filter(
        status=RideRequest.Status.PENDING,
        expires_at__lt=timezone.now()
    )
    
    count = expired_requests.count()
    expired_requests.update(status=RideRequest.Status.EXPIRED)
    
    return count