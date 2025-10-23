"""
Management command to automatically schedule maintenance for vehicles.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from fleet.services import MaintenanceScheduler
from fleet.models import Vehicle, MaintenanceRecord


class Command(BaseCommand):
    """Automatically schedule maintenance for vehicles that need it."""
    
    help = 'Automatically schedule maintenance for vehicles'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be scheduled without actually creating records',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force scheduling even if maintenance already exists',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write('Checking vehicles for maintenance requirements...\n')
        
        vehicles_checked = 0
        vehicles_needing_maintenance = 0
        maintenance_scheduled = 0
        
        for vehicle in Vehicle.objects.all():
            vehicles_checked += 1
            
            # Check if vehicle already has scheduled maintenance
            existing_maintenance = MaintenanceRecord.objects.filter(
                vehicle=vehicle,
                status__in=[
                    MaintenanceRecord.Status.SCHEDULED,
                    MaintenanceRecord.Status.IN_PROGRESS
                ]
            ).first()
            
            if existing_maintenance and not force:
                self.stdout.write(
                    f"  {vehicle.license_plate}: Already has scheduled maintenance ({existing_maintenance.id})"
                )
                continue
            
            # Check maintenance requirements
            requirements = MaintenanceScheduler.check_maintenance_requirements(vehicle)
            
            if requirements['needs_maintenance']:
                vehicles_needing_maintenance += 1
                
                self.stdout.write(
                    self.style.WARNING(
                        f"  {vehicle.license_plate}: Needs maintenance ({requirements['priority']} priority)"
                    )
                )
                
                for reason in requirements['reasons']:
                    self.stdout.write(f"    - {reason}")
                
                # Determine maintenance type based on reasons
                maintenance_type = MaintenanceRecord.MaintenanceType.ROUTINE
                estimated_cost = 200.00
                
                if any('diagnostic' in reason.lower() for reason in requirements['reasons']):
                    maintenance_type = MaintenanceRecord.MaintenanceType.REPAIR
                    estimated_cost = 500.00
                elif any('overdue' in reason.lower() for reason in requirements['reasons']):
                    maintenance_type = MaintenanceRecord.MaintenanceType.INSPECTION
                    estimated_cost = 150.00
                
                if not dry_run:
                    try:
                        description = f"Auto-scheduled {maintenance_type} maintenance. " + \
                                    f"Reasons: {'; '.join(requirements['reasons'])}"
                        
                        # Cancel existing maintenance if force is used
                        if existing_maintenance and force:
                            existing_maintenance.status = MaintenanceRecord.Status.CANCELLED
                            existing_maintenance.save()
                            self.stdout.write(
                                f"    Cancelled existing maintenance: {existing_maintenance.id}"
                            )
                        
                        maintenance_record = MaintenanceScheduler.schedule_maintenance(
                            vehicle=vehicle,
                            maintenance_type=maintenance_type,
                            scheduled_date=requirements['recommended_date'],
                            description=description,
                            estimated_cost=estimated_cost
                        )
                        
                        maintenance_scheduled += 1
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    Scheduled maintenance: {maintenance_record.id} "
                                f"for {requirements['recommended_date'].date()}"
                            )
                        )
                        
                    except ValueError as e:
                        self.stdout.write(
                            self.style.ERROR(f"    Failed to schedule: {e}")
                        )
                else:
                    self.stdout.write(
                        f"    Would schedule {maintenance_type} maintenance "
                        f"for {requirements['recommended_date'].date()}"
                    )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  {vehicle.license_plate}: No maintenance needed")
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('MAINTENANCE SCHEDULING SUMMARY:'))
        self.stdout.write('='*60)
        
        self.stdout.write(f"Vehicles checked: {vehicles_checked}")
        self.stdout.write(f"Vehicles needing maintenance: {vehicles_needing_maintenance}")
        
        if dry_run:
            self.stdout.write(f"Would schedule maintenance for: {vehicles_needing_maintenance} vehicles")
            self.stdout.write(self.style.WARNING("This was a dry run - no maintenance was actually scheduled"))
        else:
            self.stdout.write(f"Maintenance scheduled: {maintenance_scheduled}")
        
        # Show upcoming maintenance
        upcoming_maintenance = MaintenanceRecord.objects.filter(
            status=MaintenanceRecord.Status.SCHEDULED,
            scheduled_date__gte=timezone.now(),
            scheduled_date__lte=timezone.now() + timezone.timedelta(days=7)
        ).order_by('scheduled_date')
        
        if upcoming_maintenance.exists():
            self.stdout.write('\nUpcoming maintenance (next 7 days):')
            for record in upcoming_maintenance:
                self.stdout.write(
                    f"  {record.scheduled_date.date()} - {record.vehicle.license_plate} "
                    f"({record.get_maintenance_type_display()})"
                )
        
        # Show overdue maintenance
        overdue_maintenance = MaintenanceRecord.objects.filter(
            status=MaintenanceRecord.Status.SCHEDULED,
            scheduled_date__lt=timezone.now()
        ).order_by('scheduled_date')
        
        if overdue_maintenance.exists():
            self.stdout.write('\n' + self.style.ERROR('OVERDUE MAINTENANCE:'))
            for record in overdue_maintenance:
                days_overdue = (timezone.now().date() - record.scheduled_date.date()).days
                self.stdout.write(
                    self.style.ERROR(
                        f"  {record.scheduled_date.date()} - {record.vehicle.license_plate} "
                        f"({record.get_maintenance_type_display()}) - {days_overdue} days overdue"
                    )
                )