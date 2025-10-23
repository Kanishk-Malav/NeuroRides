"""
Services for real-time WebSocket communication.
"""

import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.contrib.auth import get_user_model

from rides.models import Ride
from fleet.models import Vehicle, VehicleTelemetry
from dispatch.models import DispatchRequest
from .utils import (
    notify_ride_status_change,
    notify_vehicle_assignment,
    notify_vehicle_location_update,
    notify_vehicle_status_change,
    notify_user
)

logger = logging.getLogger(__name__)

User = get_user_model()


class RideTrackingService:
    """Service for managing ride tracking WebSocket communications."""
    
    @staticmethod
    def get_ride_tracking_data(ride_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive ride tracking data."""
        try:
            ride = Ride.objects.select_related('rider').get(id=ride_id)
            
            data = {
                'ride': {
                    'id': str(ride.id),
                    'status': ride.status,
                    'pickup_address': ride.pickup_address,
                    'destination_address': ride.destination_address,
                    'pickup_latitude': ride.pickup_latitude,
                    'pickup_longitude': ride.pickup_longitude,
                    'destination_latitude': ride.destination_latitude,
                    'destination_longitude': ride.destination_longitude,
                    'estimated_fare': float(ride.estimated_fare) if ride.estimated_fare else None,
                    'actual_fare': float(ride.actual_fare) if ride.actual_fare else None,
                    'created_at': ride.created_at.isoformat(),
                    'assigned_at': ride.assigned_at.isoformat() if ride.assigned_at else None,
                    'started_at': ride.started_at.isoformat() if ride.started_at else None,
                    'completed_at': ride.completed_at.isoformat() if ride.completed_at else None,
                },
                'rider': {
                    'id': ride.rider.id,
                    'name': ride.rider.get_full_name() or ride.rider.username,
                    'phone_number': ride.rider.phone_number,
                },
                'vehicle': None,
                'dispatch_info': None,
                'estimated_arrival': None,
            }
            
            # Get dispatch information
            dispatch_request = DispatchRequest.objects.filter(
                ride=ride,
                status=DispatchRequest.Status.ASSIGNED
            ).select_related('assigned_vehicle').first()
            
            if dispatch_request and dispatch_request.assigned_vehicle:
                vehicle = dispatch_request.assigned_vehicle
                
                data['vehicle'] = {
                    'id': str(vehicle.id),
                    'license_plate': vehicle.license_plate,
                    'model': vehicle.model,
                    'manufacturer': vehicle.manufacturer,
                    'vehicle_type': vehicle.vehicle_type,
                    'status': vehicle.status,
                    'battery_level': vehicle.battery_level,
                    'current_latitude': vehicle.current_latitude,
                    'current_longitude': vehicle.current_longitude,
                    'last_seen': vehicle.last_seen.isoformat() if vehicle.last_seen else None,
                }
                
                data['dispatch_info'] = {
                    'assigned_at': dispatch_request.assigned_at.isoformat() if dispatch_request.assigned_at else None,
                    'algorithm_used': dispatch_request.algorithm_used,
                    'search_radius_km': dispatch_request.search_radius_km,
                }
                
                # Calculate estimated arrival time
                if vehicle.current_latitude and vehicle.current_longitude:
                    eta = RideTrackingService.calculate_eta(
                        vehicle.current_latitude,
                        vehicle.current_longitude,
                        ride.pickup_latitude,
                        ride.pickup_longitude
                    )
                    data['estimated_arrival'] = eta
            
            return data
            
        except Ride.DoesNotExist:
            logger.error(f"Ride {ride_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting ride tracking data for {ride_id}: {str(e)}")
            return None
    
    @staticmethod
    def calculate_eta(vehicle_lat: float, vehicle_lng: float, 
                     pickup_lat: float, pickup_lng: float) -> Dict[str, Any]:
        """Calculate estimated time of arrival."""
        from fleet.services import VehicleLocationService
        
        # Calculate distance
        distance_km = VehicleLocationService.calculate_distance(
            vehicle_lat, vehicle_lng, pickup_lat, pickup_lng
        )
        
        # Estimate time based on average speed (30 km/h in city)
        average_speed_kmh = 30
        eta_minutes = max(1, int((distance_km / average_speed_kmh) * 60))
        
        # Add current time to get arrival time
        arrival_time = timezone.now() + timezone.timedelta(minutes=eta_minutes)
        
        return {
            'distance_km': round(distance_km, 2),
            'eta_minutes': eta_minutes,
            'arrival_time': arrival_time.isoformat(),
        }
    
    @staticmethod
    def notify_ride_progress_update(ride_id: str, progress_data: Dict[str, Any]):
        """Notify about ride progress updates."""
        notify_ride_status_change(ride_id, 'progress_update', progress_data)
    
    @staticmethod
    def notify_driver_arrival(ride_id: str, vehicle_data: Dict[str, Any]):
        """Notify when driver arrives at pickup location."""
        data = {
            'message': 'Your driver has arrived!',
            'vehicle': vehicle_data,
            'action_required': 'Please come to the pickup location',
        }
        
        notify_ride_status_change(ride_id, 'driver_arrived', data)
        
        # Also send user notification
        try:
            ride = Ride.objects.get(id=ride_id)
            notify_user(
                ride.rider.id,
                'driver_arrived',
                'Driver Arrived',
                f'Your driver in {vehicle_data.get("model", "vehicle")} {vehicle_data.get("license_plate", "")} has arrived.',
                {'ride_id': ride_id}
            )
        except Ride.DoesNotExist:
            pass
    
    @staticmethod
    def notify_ride_started(ride_id: str):
        """Notify when ride has started."""
        data = {
            'message': 'Your ride has started. Enjoy your trip!',
            'status': 'in_progress',
        }
        
        notify_ride_status_change(ride_id, 'ride_started', data)
    
    @staticmethod
    def notify_ride_completed(ride_id: str, completion_data: Dict[str, Any]):
        """Notify when ride is completed."""
        data = {
            'message': 'Your ride has been completed. Thank you for using NeuroRides!',
            'status': 'completed',
            **completion_data
        }
        
        notify_ride_status_change(ride_id, 'ride_completed', data)


class FleetMonitoringService:
    """Service for managing fleet monitoring WebSocket communications."""
    
    @staticmethod
    def get_fleet_summary() -> Dict[str, Any]:
        """Get fleet summary statistics."""
        vehicles = Vehicle.objects.all()
        
        summary = {
            'total_vehicles': vehicles.count(),
            'idle_vehicles': vehicles.filter(status=Vehicle.Status.IDLE).count(),
            'assigned_vehicles': vehicles.filter(status=Vehicle.Status.ASSIGNED).count(),
            'in_ride_vehicles': vehicles.filter(status=Vehicle.Status.IN_RIDE).count(),
            'maintenance_vehicles': vehicles.filter(status=Vehicle.Status.MAINTENANCE).count(),
            'offline_vehicles': vehicles.filter(status=Vehicle.Status.OFFLINE).count(),
        }
        
        # Calculate percentages
        total = summary['total_vehicles']
        if total > 0:
            summary['utilization_rate'] = round(
                (summary['assigned_vehicles'] + summary['in_ride_vehicles']) / total * 100, 1
            )
            summary['availability_rate'] = round(summary['idle_vehicles'] / total * 100, 1)
            summary['maintenance_rate'] = round(summary['maintenance_vehicles'] / total * 100, 1)
        else:
            summary['utilization_rate'] = 0
            summary['availability_rate'] = 0
            summary['maintenance_rate'] = 0
        
        return summary
    
    @staticmethod
    def get_vehicle_list(status_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of vehicles with optional status filter."""
        vehicles = Vehicle.objects.all()
        
        if status_filter:
            vehicles = vehicles.filter(status=status_filter)
        
        vehicle_list = []
        for vehicle in vehicles[:limit]:
            # Get latest telemetry
            latest_telemetry = VehicleTelemetry.objects.filter(
                vehicle=vehicle
            ).order_by('-timestamp').first()
            
            vehicle_data = {
                'id': str(vehicle.id),
                'license_plate': vehicle.license_plate,
                'model': vehicle.model,
                'manufacturer': vehicle.manufacturer,
                'vehicle_type': vehicle.vehicle_type,
                'status': vehicle.status,
                'battery_level': vehicle.battery_level,
                'current_latitude': vehicle.current_latitude,
                'current_longitude': vehicle.current_longitude,
                'last_seen': vehicle.last_seen.isoformat() if vehicle.last_seen else None,
                'total_rides': vehicle.total_rides,
                'mileage': vehicle.mileage,
                'needs_maintenance': vehicle.needs_maintenance,
                'is_online': vehicle.is_online,
            }
            
            # Add telemetry data if available
            if latest_telemetry:
                vehicle_data['telemetry'] = {
                    'speed': latest_telemetry.speed,
                    'heading': latest_telemetry.heading,
                    'temperature': latest_telemetry.temperature,
                    'engine_status': latest_telemetry.engine_status,
                    'passenger_count': latest_telemetry.passenger_count,
                    'timestamp': latest_telemetry.timestamp.isoformat(),
                }
            
            vehicle_list.append(vehicle_data)
        
        return vehicle_list
    
    @staticmethod
    def get_maintenance_alerts() -> List[Dict[str, Any]]:
        """Get current maintenance alerts."""
        vehicles_needing_maintenance = Vehicle.objects.filter(
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED]
        )
        
        alerts = []
        for vehicle in vehicles_needing_maintenance:
            if vehicle.needs_maintenance:
                alert = {
                    'vehicle_id': str(vehicle.id),
                    'license_plate': vehicle.license_plate,
                    'alert_type': 'maintenance_due',
                    'message': f'Vehicle {vehicle.license_plate} requires maintenance',
                    'severity': 'medium',
                    'mileage': vehicle.mileage,
                    'last_maintenance': vehicle.last_maintenance.isoformat() if vehicle.last_maintenance else None,
                }
                alerts.append(alert)
            
            if vehicle.battery_level <= 20:
                alert = {
                    'vehicle_id': str(vehicle.id),
                    'license_plate': vehicle.license_plate,
                    'alert_type': 'low_battery',
                    'message': f'Vehicle {vehicle.license_plate} has low battery ({vehicle.battery_level}%)',
                    'severity': 'high' if vehicle.battery_level <= 10 else 'medium',
                    'battery_level': vehicle.battery_level,
                }
                alerts.append(alert)
        
        return alerts
    
    @staticmethod
    def notify_fleet_status_change(change_type: str, data: Dict[str, Any]):
        """Notify about fleet status changes."""
        from .utils import notifier
        
        message_data = {
            'change_type': change_type,
            'timestamp': timezone.now().isoformat(),
            **data
        }
        
        notifier.send_fleet_update('fleet_status_change', message_data)


class NotificationService:
    """Service for managing general notifications."""
    
    @staticmethod
    def send_user_notification(user_id: int, notification_type: str, 
                             title: str, message: str, 
                             additional_data: Optional[Dict] = None):
        """Send notification to specific user."""
        notify_user(user_id, notification_type, title, message, additional_data)
    
    @staticmethod
    def send_role_based_notification(role: str, notification_type: str,
                                   title: str, message: str,
                                   additional_data: Optional[Dict] = None):
        """Send notification to all users with specific role."""
        from .utils import notifier
        
        data = {
            'title': title,
            'message': message,
            'type': notification_type,
            **(additional_data or {})
        }
        
        if role == 'rider':
            notifier.send_notification_to_riders('notification', data)
        elif role == 'operator':
            notifier.send_notification_to_operators('notification', data)
        elif role == 'admin':
            notifier.send_notification_to_admins('notification', data)
    
    @staticmethod
    def send_system_wide_notification(notification_type: str, title: str, 
                                    message: str, severity: str = 'info',
                                    additional_data: Optional[Dict] = None):
        """Send system-wide notification to all users."""
        from .utils import notify_system_alert
        
        notify_system_alert(
            f"{title}: {message}",
            severity=severity,
            target_roles=None  # Send to all roles
        )