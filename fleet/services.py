"""
Business logic services for fleet management.
"""

from django.db import models
from django.db.models import Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta
from typing import List, Dict, Optional
import math
from .models import Vehicle, MaintenanceRecord, VehicleTelemetry


class MaintenanceScheduler:
    """Service for scheduling and managing vehicle maintenance."""
    
    @staticmethod
    def check_maintenance_requirements(vehicle: Vehicle) -> Dict:
        """Check if vehicle needs maintenance and return details."""
        requirements = {
            'needs_maintenance': False,
            'reasons': [],
            'priority': 'low',
            'recommended_date': None
        }
        
        now = timezone.now()
        
        # Check mileage-based maintenance
        if vehicle.mileage >= vehicle.maintenance_mileage_threshold:
            requirements['needs_maintenance'] = True
            requirements['reasons'].append(
                f'Mileage threshold reached: {vehicle.mileage}km >= {vehicle.maintenance_mileage_threshold}km'
            )
            requirements['priority'] = 'high'
        
        # Check time-based maintenance
        if vehicle.next_maintenance_due and vehicle.next_maintenance_due <= now:
            requirements['needs_maintenance'] = True
            requirements['reasons'].append(
                f'Scheduled maintenance overdue: {vehicle.next_maintenance_due.date()}'
            )
            requirements['priority'] = 'high'
        elif vehicle.next_maintenance_due and vehicle.next_maintenance_due <= now + timedelta(days=7):
            requirements['needs_maintenance'] = True
            requirements['reasons'].append(
                f'Scheduled maintenance due soon: {vehicle.next_maintenance_due.date()}'
            )
            requirements['priority'] = 'medium'
        
        # Check for diagnostic codes
        latest_telemetry = vehicle.telemetry_data.first()
        if latest_telemetry and latest_telemetry.diagnostic_codes:
            requirements['needs_maintenance'] = True
            requirements['reasons'].append(
                f'Diagnostic codes detected: {", ".join(latest_telemetry.diagnostic_codes)}'
            )
            requirements['priority'] = 'high'
        
        # Check battery health (if consistently low)
        recent_telemetry = vehicle.telemetry_data.filter(
            timestamp__gte=now - timedelta(hours=24)
        )
        if recent_telemetry.exists():
            avg_battery = recent_telemetry.aggregate(
                avg=Avg('battery_level')
            )['avg']
            if avg_battery and avg_battery < 30:
                requirements['needs_maintenance'] = True
                requirements['reasons'].append(
                    f'Consistently low battery levels: {avg_battery:.1f}% average'
                )
                requirements['priority'] = 'medium'
        
        # Recommend maintenance date
        if requirements['needs_maintenance']:
            if requirements['priority'] == 'high':
                requirements['recommended_date'] = now + timedelta(days=1)
            elif requirements['priority'] == 'medium':
                requirements['recommended_date'] = now + timedelta(days=3)
            else:
                requirements['recommended_date'] = now + timedelta(days=7)
        
        return requirements
    
    @staticmethod
    def schedule_maintenance(
        vehicle: Vehicle,
        maintenance_type: str,
        scheduled_date: timezone.datetime,
        description: str,
        estimated_cost: Optional[float] = None,
        technician=None
    ) -> MaintenanceRecord:
        """Schedule maintenance for a vehicle."""
        
        # Check if there's already scheduled maintenance
        existing_maintenance = MaintenanceRecord.objects.filter(
            vehicle=vehicle,
            status__in=[
                MaintenanceRecord.Status.SCHEDULED,
                MaintenanceRecord.Status.IN_PROGRESS
            ]
        ).first()
        
        if existing_maintenance:
            raise ValueError(
                f'Vehicle already has scheduled maintenance: {existing_maintenance.id}'
            )
        
        # Create maintenance record
        maintenance_record = MaintenanceRecord.objects.create(
            vehicle=vehicle,
            maintenance_type=maintenance_type,
            scheduled_date=scheduled_date,
            description=description,
            estimated_cost=estimated_cost,
            technician=technician
        )
        
        return maintenance_record
    
    @staticmethod
    def get_maintenance_schedule(days_ahead: int = 30) -> List[MaintenanceRecord]:
        """Get maintenance schedule for the next N days."""
        end_date = timezone.now() + timedelta(days=days_ahead)
        
        return MaintenanceRecord.objects.filter(
            scheduled_date__lte=end_date,
            status__in=[
                MaintenanceRecord.Status.SCHEDULED,
                MaintenanceRecord.Status.IN_PROGRESS
            ]
        ).order_by('scheduled_date')
    
    @staticmethod
    def get_overdue_maintenance() -> List[MaintenanceRecord]:
        """Get overdue maintenance records."""
        return MaintenanceRecord.objects.filter(
            scheduled_date__lt=timezone.now(),
            status=MaintenanceRecord.Status.SCHEDULED
        ).order_by('scheduled_date')
    
    @staticmethod
    def auto_schedule_maintenance():
        """Automatically schedule maintenance for vehicles that need it."""
        scheduled_count = 0
        
        # Get vehicles that need maintenance but don't have scheduled maintenance
        vehicles_needing_maintenance = []
        
        for vehicle in Vehicle.objects.filter(
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE]
        ):
            # Skip if already has scheduled maintenance
            if MaintenanceRecord.objects.filter(
                vehicle=vehicle,
                status__in=[
                    MaintenanceRecord.Status.SCHEDULED,
                    MaintenanceRecord.Status.IN_PROGRESS
                ]
            ).exists():
                continue
            
            requirements = MaintenanceScheduler.check_maintenance_requirements(vehicle)
            if requirements['needs_maintenance']:
                vehicles_needing_maintenance.append((vehicle, requirements))
        
        # Schedule maintenance for vehicles that need it
        for vehicle, requirements in vehicles_needing_maintenance:
            try:
                maintenance_type = MaintenanceRecord.MaintenanceType.ROUTINE
                if 'diagnostic' in ' '.join(requirements['reasons']).lower():
                    maintenance_type = MaintenanceRecord.MaintenanceType.REPAIR
                
                description = f"Auto-scheduled maintenance. Reasons: {'; '.join(requirements['reasons'])}"
                
                MaintenanceScheduler.schedule_maintenance(
                    vehicle=vehicle,
                    maintenance_type=maintenance_type,
                    scheduled_date=requirements['recommended_date'],
                    description=description,
                    estimated_cost=200.00 if maintenance_type == MaintenanceRecord.MaintenanceType.ROUTINE else 500.00
                )
                
                scheduled_count += 1
                
            except ValueError:
                # Already has scheduled maintenance
                continue
        
        return scheduled_count


class FleetAnalytics:
    """Service for fleet analytics and reporting."""
    
    @staticmethod
    def get_fleet_utilization(days: int = 7) -> Dict:
        """Calculate fleet utilization metrics."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        total_vehicles = Vehicle.objects.count()
        
        # Calculate average vehicles in each status
        utilization = {}
        
        for status_choice in Vehicle.Status.choices:
            status = status_choice[0]
            # This is a simplified calculation - in production, you'd want
            # to track status changes over time
            current_count = Vehicle.objects.filter(status=status).count()
            utilization[status] = {
                'count': current_count,
                'percentage': (current_count / total_vehicles * 100) if total_vehicles > 0 else 0
            }
        
        return {
            'period_days': days,
            'total_vehicles': total_vehicles,
            'utilization': utilization,
            'calculated_at': timezone.now()
        }
    
    @staticmethod
    def get_maintenance_metrics(days: int = 30) -> Dict:
        """Get maintenance-related metrics."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Maintenance records in period
        maintenance_records = MaintenanceRecord.objects.filter(
            created_at__gte=start_date
        )
        
        total_maintenance = maintenance_records.count()
        completed_maintenance = maintenance_records.filter(
            status=MaintenanceRecord.Status.COMPLETED
        ).count()
        
        # Calculate average maintenance time
        completed_records = maintenance_records.filter(
            status=MaintenanceRecord.Status.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        avg_maintenance_hours = 0
        if completed_records.exists():
            total_hours = sum(
                (record.completed_at - record.started_at).total_seconds() / 3600
                for record in completed_records
            )
            avg_maintenance_hours = total_hours / completed_records.count()
        
        # Calculate costs
        total_estimated_cost = maintenance_records.aggregate(
            total=Sum('estimated_cost')
        )['total'] or 0
        
        total_actual_cost = maintenance_records.filter(
            actual_cost__isnull=False
        ).aggregate(
            total=Sum('actual_cost')
        )['total'] or 0
        
        return {
            'period_days': days,
            'total_maintenance': total_maintenance,
            'completed_maintenance': completed_maintenance,
            'completion_rate': (completed_maintenance / total_maintenance * 100) if total_maintenance > 0 else 0,
            'avg_maintenance_hours': round(avg_maintenance_hours, 2),
            'total_estimated_cost': total_estimated_cost,
            'total_actual_cost': total_actual_cost,
            'cost_variance': total_actual_cost - total_estimated_cost if total_actual_cost > 0 else 0
        }
    
    @staticmethod
    def get_vehicle_performance(vehicle: Vehicle, days: int = 30) -> Dict:
        """Get performance metrics for a specific vehicle."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Telemetry data in period
        telemetry_data = vehicle.telemetry_data.filter(
            timestamp__gte=start_date
        )
        
        if not telemetry_data.exists():
            return {
                'vehicle_id': vehicle.id,
                'license_plate': vehicle.license_plate,
                'period_days': days,
                'no_data': True
            }
        
        # Calculate metrics
        avg_battery = telemetry_data.aggregate(
            avg=Avg('battery_level')
        )['avg']
        
        avg_speed = telemetry_data.filter(
            speed__gt=0
        ).aggregate(
            avg=Avg('speed')
        )['avg']
        
        total_distance = 0  # Would need to calculate from GPS coordinates
        
        # Maintenance in period
        maintenance_count = vehicle.maintenance_records.filter(
            created_at__gte=start_date
        ).count()
        
        return {
            'vehicle_id': vehicle.id,
            'license_plate': vehicle.license_plate,
            'period_days': days,
            'avg_battery_level': round(avg_battery, 1) if avg_battery else 0,
            'avg_speed': round(avg_speed, 1) if avg_speed else 0,
            'total_distance_km': total_distance,
            'maintenance_events': maintenance_count,
            'telemetry_records': telemetry_data.count(),
            'uptime_percentage': 100  # Simplified - would calculate from online/offline periods
        }


class VehicleLocationService:
    """Service for vehicle location and routing operations."""
    
    @staticmethod
    def find_nearest_vehicles(
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        limit: int = 10,
        available_only: bool = True
    ) -> List[Dict]:
        """Find nearest vehicles to a location."""
        
        # Simple bounding box calculation
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(latitude)))
        
        queryset = Vehicle.objects.filter(
            current_latitude__range=[latitude - lat_delta, latitude + lat_delta],
            current_longitude__range=[longitude - lng_delta, longitude + lng_delta],
            current_latitude__isnull=False,
            current_longitude__isnull=False
        )
        
        if available_only:
            queryset = queryset.filter(
                status=Vehicle.Status.IDLE,
                battery_level__gte=20
            )
        
        # Calculate actual distances
        vehicles_with_distance = []
        for vehicle in queryset:
            if vehicle.current_location:
                v_lat, v_lng = vehicle.current_location
                distance = VehicleLocationService.calculate_distance(
                    latitude, longitude, v_lat, v_lng
                )
                
                if distance <= radius_km:
                    vehicles_with_distance.append({
                        'vehicle': vehicle,
                        'distance_km': distance,
                        'estimated_arrival_minutes': max(1, int(distance / 0.5))  # Assume 30km/h avg speed
                    })
        
        # Sort by distance and limit results
        vehicles_with_distance.sort(key=lambda x: x['distance_km'])
        return vehicles_with_distance[:limit]
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        import math
        
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
    
    @staticmethod
    def update_vehicle_location_batch(location_updates: List[Dict]):
        """Update multiple vehicle locations efficiently."""
        updated_count = 0
        
        for update in location_updates:
            try:
                vehicle = Vehicle.objects.get(id=update['vehicle_id'])
                vehicle.update_location(
                    update['latitude'],
                    update['longitude']
                )
                updated_count += 1
            except Vehicle.DoesNotExist:
                continue
        
        return updated_count