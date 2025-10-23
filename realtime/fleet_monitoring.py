"""
Advanced fleet monitoring utilities for WebSocket communication.
"""

import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta

from fleet.models import Vehicle, VehicleTelemetry, MaintenanceRecord
from dispatch.models import DispatchRequest
from rides.models import Ride
from .utils import notify_system_alert, notifier

logger = logging.getLogger(__name__)


class FleetAnalytics:
    """Advanced fleet analytics for real-time monitoring."""
    
    @staticmethod
    def get_real_time_metrics() -> Dict[str, Any]:
        """Get real-time fleet performance metrics."""
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Vehicle status distribution
        vehicles = Vehicle.objects.all()
        status_distribution = {
            'idle': vehicles.filter(status=Vehicle.Status.IDLE).count(),
            'assigned': vehicles.filter(status=Vehicle.Status.ASSIGNED).count(),
            'in_ride': vehicles.filter(status=Vehicle.Status.IN_RIDE).count(),
            'maintenance': vehicles.filter(status=Vehicle.Status.MAINTENANCE).count(),
            'offline': vehicles.filter(status=Vehicle.Status.OFFLINE).count(),
        }
        
        # Active rides
        active_rides = Ride.objects.filter(
            status__in=[Ride.Status.ASSIGNED, Ride.Status.IN_PROGRESS]
        ).count()
        
        # Recent dispatch performance
        recent_dispatches = DispatchRequest.objects.filter(created_at__gte=hour_ago)
        dispatch_success_rate = 0
        if recent_dispatches.count() > 0:
            successful_dispatches = recent_dispatches.filter(
                status=DispatchRequest.Status.ASSIGNED
            ).count()
            dispatch_success_rate = (successful_dispatches / recent_dispatches.count()) * 100
        
        # Battery levels
        low_battery_vehicles = vehicles.filter(battery_level__lte=20).count()
        critical_battery_vehicles = vehicles.filter(battery_level__lte=10).count()
        
        # Maintenance alerts
        from django.db import models
        maintenance_due = vehicles.filter(
            Q(next_maintenance_due__lte=now) |
            Q(mileage__gte=models.F('maintenance_mileage_threshold'))
        ).count()
        
        # Fleet utilization
        total_vehicles = vehicles.count()
        active_vehicles = status_distribution['assigned'] + status_distribution['in_ride']
        utilization_rate = (active_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0
        
        return {
            'timestamp': now.isoformat(),
            'fleet_size': total_vehicles,
            'status_distribution': status_distribution,
            'active_rides': active_rides,
            'utilization_rate': round(utilization_rate, 1),
            'dispatch_success_rate': round(dispatch_success_rate, 1),
            'battery_alerts': {
                'low_battery': low_battery_vehicles,
                'critical_battery': critical_battery_vehicles,
            },
            'maintenance_due': maintenance_due,
        }
    
    @staticmethod
    def get_vehicle_performance_metrics(vehicle_id: str) -> Dict[str, Any]:
        """Get performance metrics for a specific vehicle."""
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            
            # Recent telemetry
            recent_telemetry = VehicleTelemetry.objects.filter(
                vehicle=vehicle,
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-timestamp')
            
            # Calculate averages
            avg_speed = recent_telemetry.aggregate(Avg('speed'))['speed__avg'] or 0
            avg_battery = recent_telemetry.aggregate(Avg('battery_level'))['battery_level__avg'] or 0
            
            # Recent rides
            recent_rides = Ride.objects.filter(
                # This would need to be updated when vehicle-ride relationship is established
                requested_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Maintenance history
            recent_maintenance = MaintenanceRecord.objects.filter(
                vehicle=vehicle,
                completed_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            return {
                'vehicle_id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'performance': {
                    'avg_speed_24h': round(avg_speed, 1),
                    'avg_battery_24h': round(avg_battery, 1),
                    'rides_last_7_days': recent_rides,
                    'maintenance_last_30_days': recent_maintenance,
                    'total_mileage': vehicle.mileage,
                    'total_rides': vehicle.total_rides,
                },
                'current_status': {
                    'status': vehicle.status,
                    'battery_level': vehicle.battery_level,
                    'last_seen': vehicle.last_seen.isoformat() if vehicle.last_seen else None,
                    'needs_maintenance': vehicle.needs_maintenance,
                    'is_online': vehicle.is_online,
                }
            }
            
        except Vehicle.DoesNotExist:
            return None
    
    @staticmethod
    def get_fleet_health_score() -> Dict[str, Any]:
        """Calculate overall fleet health score."""
        vehicles = Vehicle.objects.all()
        total_vehicles = vehicles.count()
        
        if total_vehicles == 0:
            return {'health_score': 0, 'factors': {}}
        
        # Factor 1: Vehicle availability (40% weight)
        available_vehicles = vehicles.filter(
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE]
        ).count()
        availability_score = (available_vehicles / total_vehicles) * 40
        
        # Factor 2: Battery health (25% weight)
        good_battery_vehicles = vehicles.filter(battery_level__gte=50).count()
        battery_score = (good_battery_vehicles / total_vehicles) * 25
        
        # Factor 3: Maintenance status (20% weight)
        from django.db import models
        well_maintained_vehicles = vehicles.exclude(
            Q(next_maintenance_due__lte=timezone.now()) |
            Q(mileage__gte=models.F('maintenance_mileage_threshold'))
        ).count()
        maintenance_score = (well_maintained_vehicles / total_vehicles) * 20
        
        # Factor 4: Connectivity (15% weight)
        online_vehicles = vehicles.filter(
            last_seen__gte=timezone.now() - timedelta(minutes=10)
        ).count()
        connectivity_score = (online_vehicles / total_vehicles) * 15
        
        total_score = availability_score + battery_score + maintenance_score + connectivity_score
        
        return {
            'health_score': round(total_score, 1),
            'factors': {
                'availability': round(availability_score, 1),
                'battery_health': round(battery_score, 1),
                'maintenance_status': round(maintenance_score, 1),
                'connectivity': round(connectivity_score, 1),
            },
            'vehicle_counts': {
                'total': total_vehicles,
                'available': available_vehicles,
                'good_battery': good_battery_vehicles,
                'well_maintained': well_maintained_vehicles,
                'online': online_vehicles,
            }
        }


class FleetAlertManager:
    """Manages fleet-wide alerts and notifications."""
    
    @staticmethod
    def check_and_send_alerts():
        """Check for various fleet conditions and send alerts."""
        alerts_sent = []
        
        # Check for critical battery levels
        critical_battery_vehicles = Vehicle.objects.filter(
            battery_level__lte=10,
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE]
        )
        
        for vehicle in critical_battery_vehicles:
            alert_data = {
                'vehicle_id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'battery_level': vehicle.battery_level,
                'alert_type': 'critical_battery',
                'severity': 'critical',
                'message': f'Vehicle {vehicle.license_plate} has critically low battery ({vehicle.battery_level}%)',
                'action_required': 'Immediate charging required'
            }
            
            notifier.send_fleet_update('maintenance_alert', alert_data)
            alerts_sent.append(alert_data)
        
        # Check for overdue maintenance
        overdue_maintenance_vehicles = Vehicle.objects.filter(
            next_maintenance_due__lte=timezone.now(),
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED]
        )
        
        for vehicle in overdue_maintenance_vehicles:
            alert_data = {
                'vehicle_id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'alert_type': 'maintenance_overdue',
                'severity': 'high',
                'message': f'Vehicle {vehicle.license_plate} has overdue maintenance',
                'due_date': vehicle.next_maintenance_due.isoformat() if vehicle.next_maintenance_due else None,
                'action_required': 'Schedule maintenance immediately'
            }
            
            notifier.send_fleet_update('maintenance_alert', alert_data)
            alerts_sent.append(alert_data)
        
        # Check for offline vehicles
        offline_threshold = timezone.now() - timedelta(hours=2)
        offline_vehicles = Vehicle.objects.filter(
            last_seen__lt=offline_threshold
        ).exclude(status=Vehicle.Status.MAINTENANCE)
        
        for vehicle in offline_vehicles:
            offline_duration = timezone.now() - vehicle.last_seen if vehicle.last_seen else None
            
            alert_data = {
                'vehicle_id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'alert_type': 'vehicle_offline',
                'severity': 'medium',
                'message': f'Vehicle {vehicle.license_plate} has been offline for over 2 hours',
                'offline_duration_hours': offline_duration.total_seconds() / 3600 if offline_duration else None,
                'action_required': 'Check vehicle connectivity'
            }
            
            notifier.send_fleet_update('maintenance_alert', alert_data)
            alerts_sent.append(alert_data)
        
        # Check fleet utilization
        fleet_metrics = FleetAnalytics.get_real_time_metrics()
        if fleet_metrics['utilization_rate'] > 90:
            notify_system_alert(
                f"High fleet utilization: {fleet_metrics['utilization_rate']:.1f}% of vehicles are active",
                severity='warning',
                target_roles=['operator', 'admin']
            )
            alerts_sent.append({
                'alert_type': 'high_utilization',
                'utilization_rate': fleet_metrics['utilization_rate'],
                'severity': 'warning'
            })
        
        return alerts_sent
    
    @staticmethod
    def send_fleet_status_broadcast():
        """Send comprehensive fleet status to all monitoring clients."""
        metrics = FleetAnalytics.get_real_time_metrics()
        health_score = FleetAnalytics.get_fleet_health_score()
        
        broadcast_data = {
            'type': 'fleet_status_broadcast',
            'metrics': metrics,
            'health_score': health_score,
            'timestamp': timezone.now().isoformat()
        }
        
        notifier.send_fleet_update('fleet_status_update', broadcast_data)
        
        return broadcast_data


class VehicleTelemetryProcessor:
    """Processes vehicle telemetry data for real-time monitoring."""
    
    @staticmethod
    def process_telemetry_update(telemetry_data: Dict[str, Any]):
        """Process incoming telemetry data and trigger appropriate notifications."""
        vehicle_id = telemetry_data.get('vehicle_id')
        
        if not vehicle_id:
            logger.error("Telemetry data missing vehicle_id")
            return
        
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            
            # Update vehicle location and status
            if 'latitude' in telemetry_data and 'longitude' in telemetry_data:
                vehicle.current_latitude = telemetry_data['latitude']
                vehicle.current_longitude = telemetry_data['longitude']
            
            if 'battery_level' in telemetry_data:
                vehicle.battery_level = telemetry_data['battery_level']
            
            vehicle.last_seen = timezone.now()
            vehicle.save()
            
            # Create telemetry record
            VehicleTelemetry.objects.create(
                vehicle=vehicle,
                latitude=telemetry_data.get('latitude', vehicle.current_latitude),
                longitude=telemetry_data.get('longitude', vehicle.current_longitude),
                speed=telemetry_data.get('speed', 0),
                heading=telemetry_data.get('heading', 0),
                battery_level=telemetry_data.get('battery_level', vehicle.battery_level),
                temperature=telemetry_data.get('temperature'),
                engine_status=telemetry_data.get('engine_status', 'idle'),
                passenger_count=telemetry_data.get('passenger_count', 0),
            )
            
            # Send real-time update to fleet monitoring
            fleet_telemetry_data = {
                'vehicle_id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'latitude': telemetry_data.get('latitude', vehicle.current_latitude),
                'longitude': telemetry_data.get('longitude', vehicle.current_longitude),
                'speed': telemetry_data.get('speed', 0),
                'battery_level': telemetry_data.get('battery_level', vehicle.battery_level),
                'timestamp': timezone.now().isoformat()
            }
            
            notifier.send_fleet_update('vehicle_telemetry_update', fleet_telemetry_data)
            
            # Check for alerts
            if telemetry_data.get('battery_level', 100) <= 15:
                FleetAlertManager.check_and_send_alerts()
            
        except Vehicle.DoesNotExist:
            logger.error(f"Vehicle {vehicle_id} not found for telemetry update")
        except Exception as e:
            logger.error(f"Error processing telemetry for vehicle {vehicle_id}: {str(e)}")


# Periodic tasks for fleet monitoring
def run_fleet_health_check():
    """Run periodic fleet health check and send alerts."""
    logger.info("Running fleet health check")
    
    # Send alerts
    alerts = FleetAlertManager.check_and_send_alerts()
    
    # Broadcast fleet status
    FleetAlertManager.send_fleet_status_broadcast()
    
    logger.info(f"Fleet health check completed. {len(alerts)} alerts sent.")
    
    return {
        'alerts_sent': len(alerts),
        'timestamp': timezone.now().isoformat()
    }