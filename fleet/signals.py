"""
Signal handlers for fleet app.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Vehicle, VehicleTelemetry, MaintenanceRecord


@receiver(post_save, sender=VehicleTelemetry)
def update_vehicle_from_telemetry(sender, instance, created, **kwargs):
    """Update vehicle status based on telemetry data."""
    if created:
        vehicle = instance.vehicle
        
        # Update vehicle's last seen timestamp
        vehicle.last_seen = instance.timestamp
        
        # Update location if different
        if (vehicle.current_latitude != instance.latitude or 
            vehicle.current_longitude != instance.longitude):
            vehicle.current_latitude = instance.latitude
            vehicle.current_longitude = instance.longitude
        
        # Update battery level if different
        if vehicle.battery_level != instance.battery_level:
            vehicle.battery_level = instance.battery_level
        
        # Check if vehicle needs to go offline due to low battery
        if instance.battery_level < 10 and vehicle.status != Vehicle.Status.MAINTENANCE:
            vehicle.status = Vehicle.Status.OFFLINE
        
        # Save vehicle with updated fields
        vehicle.save(update_fields=[
            'last_seen', 'current_latitude', 'current_longitude', 
            'battery_level', 'status'
        ])


@receiver(pre_save, sender=Vehicle)
def vehicle_status_change_handler(sender, instance, **kwargs):
    """Handle vehicle status changes."""
    if instance.pk:  # Only for existing vehicles
        try:
            old_vehicle = Vehicle.objects.get(pk=instance.pk)
            
            # If vehicle is going to maintenance, clear current ride
            if (old_vehicle.status != Vehicle.Status.MAINTENANCE and 
                instance.status == Vehicle.Status.MAINTENANCE):
                pass  # instance.current_ride = None  # Will be enabled when rides app is implemented
            
            # If vehicle is coming back from maintenance, set to idle
            if (old_vehicle.status == Vehicle.Status.MAINTENANCE and 
                instance.status != Vehicle.Status.MAINTENANCE):
                if instance.status not in [Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE]:
                    instance.status = Vehicle.Status.IDLE
        
        except Vehicle.DoesNotExist:
            pass


@receiver(post_save, sender=MaintenanceRecord)
def maintenance_record_created(sender, instance, created, **kwargs):
    """Handle maintenance record creation and updates."""
    if created and instance.status == MaintenanceRecord.Status.SCHEDULED:
        # Check if maintenance is due soon (within 24 hours)
        time_until_maintenance = instance.scheduled_date - timezone.now()
        if time_until_maintenance.total_seconds() < 86400:  # 24 hours
            # Could send notification here
            pass
    
    # If maintenance is started, update vehicle status
    if (instance.status == MaintenanceRecord.Status.IN_PROGRESS and 
        instance.vehicle.status != Vehicle.Status.MAINTENANCE):
        instance.vehicle.set_maintenance_mode()
    
    # If maintenance is completed, return vehicle to service
    if (instance.status == MaintenanceRecord.Status.COMPLETED and 
        instance.vehicle.status == Vehicle.Status.MAINTENANCE):
        instance.vehicle.complete_maintenance()


@receiver(post_save, sender=Vehicle)
def check_maintenance_alerts(sender, instance, **kwargs):
    """Check if vehicle needs maintenance and create alerts."""
    if instance.needs_maintenance and instance.status != Vehicle.Status.MAINTENANCE:
        # Check if there's already a scheduled maintenance
        existing_maintenance = MaintenanceRecord.objects.filter(
            vehicle=instance,
            status__in=[
                MaintenanceRecord.Status.SCHEDULED,
                MaintenanceRecord.Status.IN_PROGRESS
            ]
        ).exists()
        
        if not existing_maintenance:
            # Create automatic maintenance record
            MaintenanceRecord.objects.create(
                vehicle=instance,
                maintenance_type=MaintenanceRecord.MaintenanceType.ROUTINE,
                scheduled_date=timezone.now() + timezone.timedelta(days=1),
                description=f"Automatic maintenance scheduled for {instance.license_plate}. "
                           f"Mileage: {instance.mileage}km",
                estimated_cost=200.00  # Default estimated cost
            )