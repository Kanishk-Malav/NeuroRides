"""
Celery tasks for fleet management.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Vehicle, VehicleTelemetry, MaintenanceSchedule, MaintenanceRecord
from .services import FleetManagementService, MaintenanceService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_vehicle_telemetry(self, vehicle_id, telemetry_data):
    """
    Process incoming vehicle telemetry data.
    
    Args:
        vehicle_id: ID of the vehicle
        telemetry_data: Dictionary containing telemetry information
    
    Returns:
        dict: Processing result
    """
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
        
        # Create telemetry record
        telemetry = VehicleTelemetry.objects.create(
            vehicle=vehicle,
            latitude=telemetry_data.get('latitude'),
            longitude=telemetry_data.get('longitude'),
            speed=telemetry_data.get('speed', 0),
            battery_level=telemetry_data.get('battery_level'),
            fuel_level=telemetry_data.get('fuel_level'),
            engine_temperature=telemetry_data.get('engine_temperature'),
            odometer_reading=telemetry_data.get('odometer_reading'),
            diagnostic_codes=telemetry_data.get('diagnostic_codes', []),
            timestamp=timezone.now()
        )
        
        # Update vehicle's current location and status
        vehicle.current_latitude = telemetry_data.get('latitude')
        vehicle.current_longitude = telemetry_data.get('longitude')
        vehicle.battery_level = telemetry_data.get('battery_level')
        vehicle.last_seen = timezone.now()
        
        # Check for critical issues
        alerts = []
        if telemetry_data.get('battery_level', 100) < 15:
            alerts.append('low_battery')
        
        if telemetry_data.get('engine_temperature', 0) > 100:
            alerts.append('high_temperature')
        
        if telemetry_data.get('diagnostic_codes'):
            alerts.append('diagnostic_error')
        
        # Update vehicle status based on alerts
        if alerts:
            if 'diagnostic_error' in alerts:
                vehicle.status = 'maintenance'
            elif vehicle.status == 'idle':
                vehicle.status = 'idle'  # Keep current status but log alert
        
        vehicle.save(update_fields=[
            'current_latitude', 'current_longitude', 'battery_level', 
            'last_seen', 'status'
        ])
        
        logger.info(f"Processed telemetry for vehicle {vehicle.license_plate}")
        
        return {
            'success': True,
            'vehicle_id': vehicle_id,
            'telemetry_id': str(telemetry.id),
            'alerts': alerts,
        }
        
    except Vehicle.DoesNotExist:
        logger.error(f"Vehicle not found: {vehicle_id}")
        return {
            'success': False,
            'error': 'Vehicle not found',
            'vehicle_id': vehicle_id,
        }
    except Exception as exc:
        logger.error(f"Error processing telemetry for vehicle {vehicle_id}: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying telemetry processing (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Task failed after retries: {str(exc)}',
            'vehicle_id': vehicle_id,
        }


@shared_task
def schedule_maintenance_checks():
    """
    Schedule maintenance checks for vehicles based on usage and time.
    
    Returns:
        dict: Scheduling results
    """
    try:
        logger.info("Starting maintenance scheduling")
        
        maintenance_service = MaintenanceService()
        results = maintenance_service.schedule_routine_maintenance()
        
        logger.info(f"Maintenance scheduling completed: {results['scheduled']} vehicles scheduled")
        
        return results
        
    except Exception as exc:
        logger.error(f"Maintenance scheduling failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def update_vehicle_locations():
    """
    Update vehicle locations and check for location-based alerts.
    
    Returns:
        dict: Update results
    """
    try:
        logger.info("Starting vehicle location updates")
        
        # Get vehicles that haven't reported in the last 10 minutes
        stale_threshold = timezone.now() - timedelta(minutes=10)
        stale_vehicles = Vehicle.objects.filter(
            is_active=True,
            last_seen__lt=stale_threshold
        )
        
        alerts = []
        for vehicle in stale_vehicles:
            if vehicle.status in ['assigned', 'in_ride']:
                alerts.append({
                    'vehicle_id': str(vehicle.id),
                    'license_plate': vehicle.license_plate,
                    'alert_type': 'communication_lost',
                    'last_seen': vehicle.last_seen.isoformat(),
                })
        
        # Check for vehicles outside service area (placeholder logic)
        # In a real system, this would check against defined service boundaries
        
        logger.info(f"Vehicle location updates completed: {len(alerts)} alerts generated")
        
        return {
            'success': True,
            'stale_vehicles': stale_vehicles.count(),
            'alerts': alerts,
        }
        
    except Exception as exc:
        logger.error(f"Vehicle location updates failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def check_vehicle_health():
    """
    Check vehicle health status and generate alerts.
    
    Returns:
        dict: Health check results
    """
    try:
        logger.info("Starting vehicle health checks")
        
        fleet_service = FleetManagementService()
        health_results = fleet_service.check_fleet_health()
        
        # Generate alerts for unhealthy vehicles
        alerts = []
        for vehicle_health in health_results['vehicle_health']:
            if vehicle_health['health_score'] < 70:
                alerts.append({
                    'vehicle_id': vehicle_health['vehicle_id'],
                    'license_plate': vehicle_health['license_plate'],
                    'health_score': vehicle_health['health_score'],
                    'issues': vehicle_health['issues'],
                    'severity': 'high' if vehicle_health['health_score'] < 50 else 'medium',
                })
        
        logger.info(f"Vehicle health checks completed: {len(alerts)} alerts generated")
        
        return {
            'success': True,
            'vehicles_checked': health_results['total_vehicles'],
            'healthy_vehicles': health_results['healthy_vehicles'],
            'alerts': alerts,
        }
        
    except Exception as exc:
        logger.error(f"Vehicle health checks failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def generate_maintenance_alerts():
    """
    Generate maintenance alerts for vehicles that need attention.
    
    Returns:
        dict: Alert generation results
    """
    try:
        logger.info("Generating maintenance alerts")
        
        maintenance_service = MaintenanceService()
        alerts = maintenance_service.generate_maintenance_alerts()
        
        # Log critical alerts
        critical_alerts = [alert for alert in alerts if alert.get('priority') == 'critical']
        if critical_alerts:
            logger.warning(f"Generated {len(critical_alerts)} critical maintenance alerts")
        
        logger.info(f"Maintenance alert generation completed: {len(alerts)} alerts generated")
        
        return {
            'success': True,
            'total_alerts': len(alerts),
            'critical_alerts': len(critical_alerts),
            'alerts': alerts[:10],  # Return first 10 for logging
        }
        
    except Exception as exc:
        logger.error(f"Maintenance alert generation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def cleanup_old_telemetry_data():
    """
    Clean up old telemetry data to manage database size.
    
    Returns:
        dict: Cleanup results
    """
    try:
        logger.info("Starting telemetry data cleanup")
        
        # Keep telemetry data for the last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_telemetry = VehicleTelemetry.objects.filter(timestamp__lt=cutoff_date)
        count = old_telemetry.count()
        old_telemetry.delete()
        
        logger.info(f"Cleaned up {count} old telemetry records")
        
        return {
            'success': True,
            'deleted_records': count,
            'cutoff_date': cutoff_date.isoformat(),
        }
        
    except Exception as exc:
        logger.error(f"Telemetry cleanup failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def calculate_vehicle_utilization():
    """
    Calculate vehicle utilization metrics.
    
    Returns:
        dict: Utilization calculation results
    """
    try:
        logger.info("Calculating vehicle utilization")
        
        fleet_service = FleetManagementService()
        utilization_data = fleet_service.calculate_utilization_metrics()
        
        # Log vehicles with low utilization
        low_utilization = [
            v for v in utilization_data['vehicle_utilization'] 
            if v['utilization_rate'] < 0.3
        ]
        
        if low_utilization:
            logger.info(f"Found {len(low_utilization)} vehicles with low utilization")
        
        logger.info("Vehicle utilization calculation completed")
        
        return {
            'success': True,
            'fleet_utilization_rate': utilization_data['fleet_utilization_rate'],
            'vehicles_analyzed': len(utilization_data['vehicle_utilization']),
            'low_utilization_vehicles': len(low_utilization),
        }
        
    except Exception as exc:
        logger.error(f"Vehicle utilization calculation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def optimize_fleet_distribution():
    """
    Optimize fleet distribution based on demand patterns.
    
    Returns:
        dict: Optimization results
    """
    try:
        logger.info("Starting fleet distribution optimization")
        
        fleet_service = FleetManagementService()
        optimization_result = fleet_service.optimize_fleet_distribution()
        
        # Log optimization recommendations
        if optimization_result['recommendations']:
            logger.info(f"Generated {len(optimization_result['recommendations'])} optimization recommendations")
        
        logger.info("Fleet distribution optimization completed")
        
        return {
            'success': True,
            'recommendations': len(optimization_result['recommendations']),
            'potential_improvement': optimization_result.get('potential_improvement', 0),
            'current_efficiency': optimization_result.get('current_efficiency', 0),
        }
        
    except Exception as exc:
        logger.error(f"Fleet distribution optimization failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }