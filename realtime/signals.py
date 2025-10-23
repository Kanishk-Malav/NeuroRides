"""
Signal handlers for real-time WebSocket notifications.
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from rides.models import Ride
from fleet.models import Vehicle, VehicleTelemetry, MaintenanceRecord
from dispatch.models import DispatchRequest
from .utils import (
    notify_ride_status_change,
    notify_vehicle_assignment,
    notify_vehicle_location_update,
    notify_vehicle_status_change,
    notify_vehicle_telemetry_update,
    notify_maintenance_alert,
    notify_user,
    notify_system_alert
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ride)
def handle_ride_status_change(sender, instance, created, **kwargs):
    """Handle ride status changes."""
    
    if created:
        # New ride created
        notify_user(
            instance.rider.id,
            'ride_created',
            'Ride Requested',
            f'Your ride from {instance.pickup_address} has been requested.',
            {'ride_id': str(instance.id)}
        )
        logger.info(f"Notified user {instance.rider.id} about new ride {instance.id}")
    
    else:
        # Ride status updated
        notify_ride_status_change(
            str(instance.id),
            instance.status,
            {
                'pickup_address': instance.pickup_address,
                'destination_address': instance.destination_address,
                'estimated_fare': float(instance.estimated_fare) if instance.estimated_fare else None
            }
        )
        
        # Send user-specific notifications based on status
        if instance.status == Ride.Status.ASSIGNED:
            notify_user(
                instance.rider.id,
                'ride_assigned',
                'Driver Assigned',
                'A driver has been assigned to your ride.',
                {'ride_id': str(instance.id)}
            )
        
        elif instance.status == Ride.Status.IN_PROGRESS:
            notify_user(
                instance.rider.id,
                'ride_started',
                'Ride Started',
                'Your ride has started.',
                {'ride_id': str(instance.id)}
            )
        
        elif instance.status == Ride.Status.COMPLETED:
            notify_user(
                instance.rider.id,
                'ride_completed',
                'Ride Completed',
                'Your ride has been completed. Thank you for using NeuroRides!',
                {'ride_id': str(instance.id)}
            )
        
        elif instance.status == Ride.Status.CANCELLED:
            notify_user(
                instance.rider.id,
                'ride_cancelled',
                'Ride Cancelled',
                'Your ride has been cancelled.',
                {'ride_id': str(instance.id)}
            )
        
        logger.info(f"Notified about ride {instance.id} status change to {instance.status}")


@receiver(post_save, sender=DispatchRequest)
def handle_dispatch_assignment(sender, instance, **kwargs):
    """Handle dispatch request assignments."""
    
    if instance.status == DispatchRequest.Status.ASSIGNED and instance.assigned_vehicle:
        # Vehicle assigned to ride
        vehicle_data = {
            'id': str(instance.assigned_vehicle.id),
            'license_plate': instance.assigned_vehicle.license_plate,
            'model': instance.assigned_vehicle.model,
            'current_latitude': instance.assigned_vehicle.current_latitude,
            'current_longitude': instance.assigned_vehicle.current_longitude,
            'battery_level': instance.assigned_vehicle.battery_level,
        }
        
        notify_vehicle_assignment(str(instance.ride.id), vehicle_data)
        logger.info(f"Notified about vehicle assignment for ride {instance.ride.id}")


@receiver(post_save, sender=Vehicle)
def handle_vehicle_status_change(sender, instance, created, **kwargs):
    """Handle vehicle status changes."""
    
    if not created:  # Only for updates, not new vehicles
        notify_vehicle_status_change(
            str(instance.id),
            instance.status,
            {
                'license_plate': instance.license_plate,
                'model': instance.model,
                'battery_level': instance.battery_level,
                'current_latitude': instance.current_latitude,
                'current_longitude': instance.current_longitude,
                'last_seen': instance.last_seen.isoformat() if instance.last_seen else None
            }
        )
        
        # Check for low battery alerts
        if instance.battery_level <= 20:
            notify_maintenance_alert(
                str(instance.id),
                'low_battery',
                f'Vehicle {instance.license_plate} has low battery ({instance.battery_level}%)',
                {'severity': 'high' if instance.battery_level <= 10 else 'medium'}
            )
        
        # Check for maintenance alerts
        if instance.needs_maintenance:
            notify_maintenance_alert(
                str(instance.id),
                'maintenance_due',
                f'Vehicle {instance.license_plate} requires maintenance',
                {'severity': 'medium'}
            )
        
        logger.debug(f"Notified about vehicle {instance.license_plate} status change")


@receiver(post_save, sender=VehicleTelemetry)
def handle_vehicle_telemetry_update(sender, instance, created, **kwargs):
    """Handle vehicle telemetry updates."""
    
    if created:  # Only for new telemetry data
        vehicle_data = {
            'id': str(instance.vehicle.id),
            'license_plate': instance.vehicle.license_plate,
            'latitude': instance.latitude,
            'longitude': instance.longitude,
            'speed': instance.speed,
            'heading': instance.heading,
            'battery_level': instance.battery_level,
            'timestamp': instance.timestamp.isoformat()
        }
        
        notify_vehicle_telemetry_update(vehicle_data)
        
        # If vehicle is assigned to a ride, notify the ride tracking
        # Check if vehicle is assigned to any active rides
        from dispatch.models import DispatchRequest
        active_dispatch = DispatchRequest.objects.filter(
            assigned_vehicle=instance.vehicle,
            status=DispatchRequest.Status.ASSIGNED
        ).first()
        
        if active_dispatch:
            notify_vehicle_location_update(
                str(active_dispatch.ride.id),
                vehicle_data
            )
        
        logger.debug(f"Notified about telemetry update for vehicle {instance.vehicle.license_plate}")


@receiver(post_save, sender=MaintenanceRecord)
def handle_maintenance_record_update(sender, instance, created, **kwargs):
    """Handle maintenance record updates."""
    
    if created:
        # New maintenance scheduled
        notify_maintenance_alert(
            str(instance.vehicle.id),
            'maintenance_scheduled',
            f'Maintenance scheduled for vehicle {instance.vehicle.license_plate} on {instance.scheduled_date.date()}',
            {
                'maintenance_type': instance.maintenance_type,
                'scheduled_date': instance.scheduled_date.isoformat(),
                'severity': 'low'
            }
        )
    
    elif instance.status == MaintenanceRecord.Status.COMPLETED:
        # Maintenance completed
        notify_maintenance_alert(
            str(instance.vehicle.id),
            'maintenance_completed',
            f'Maintenance completed for vehicle {instance.vehicle.license_plate}',
            {
                'maintenance_type': instance.maintenance_type,
                'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
                'severity': 'low'
            }
        )
    
    logger.info(f"Notified about maintenance record update for vehicle {instance.vehicle.license_plate}")


# System-wide alerts for critical events
@receiver(post_save, sender=Vehicle)
def handle_critical_vehicle_alerts(sender, instance, **kwargs):
    """Handle critical vehicle alerts."""
    
    # Critical battery level
    if instance.battery_level <= 5:
        notify_system_alert(
            f'CRITICAL: Vehicle {instance.license_plate} has critically low battery ({instance.battery_level}%)',
            severity='critical',
            target_roles=['operator', 'admin']
        )
    
    # Vehicle offline for too long
    if instance.last_seen and (timezone.now() - instance.last_seen).total_seconds() > 3600:  # 1 hour
        notify_system_alert(
            f'WARNING: Vehicle {instance.license_plate} has been offline for over 1 hour',
            severity='warning',
            target_roles=['operator', 'admin']
        )