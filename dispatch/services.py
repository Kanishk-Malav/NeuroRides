"""
Dispatch services for intelligent vehicle assignment.
"""

import math
import logging
from typing import List, Dict, Optional, Tuple
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from abc import ABC, abstractmethod

from fleet.models import Vehicle
from fleet.services import VehicleLocationService
from rides.models import Ride
from .models import DispatchRequest, DispatchAlgorithmConfig, DispatchMetrics

logger = logging.getLogger(__name__)


class VehicleScore:
    """Container for vehicle scoring information."""
    
    def __init__(self, vehicle: Vehicle, distance_km: float, score: float, factors: Dict):
        self.vehicle = vehicle
        self.distance_km = distance_km
        self.score = score
        self.factors = factors
        self.eta_minutes = max(1, int(distance_km / 0.5))  # Assume 30 km/h average speed
    
    def __repr__(self):
        return f"VehicleScore({self.vehicle.license_plate}, distance={self.distance_km:.2f}km, score={self.score:.3f})"


class BaseDispatchAlgorithm(ABC):
    """Base class for dispatch algorithms."""
    
    def __init__(self, config: DispatchAlgorithmConfig):
        self.config = config
        self.name = config.name
    
    @abstractmethod
    def find_best_vehicle(
        self, 
        pickup_lat: float, 
        pickup_lng: float, 
        ride: Ride
    ) -> Optional[VehicleScore]:
        """Find the best vehicle for the given pickup location and ride."""
        pass
    
    def get_available_vehicles(
        self, 
        pickup_lat: float, 
        pickup_lng: float, 
        ride: Ride
    ) -> List[Vehicle]:
        """Get available vehicles within search radius."""
        
        # Calculate bounding box for search
        lat_delta = self.config.max_search_radius_km / 111.0
        lng_delta = self.config.max_search_radius_km / (111.0 * math.cos(math.radians(pickup_lat)))
        
        # Base query for available vehicles
        vehicles = Vehicle.objects.filter(
            status=Vehicle.Status.IDLE,
            battery_level__gte=self.config.min_battery_level,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
            current_latitude__range=[pickup_lat - lat_delta, pickup_lat + lat_delta],
            current_longitude__range=[pickup_lng - lng_delta, pickup_lng + lng_delta]
        )
        
        # Filter by special requirements
        if ride.requires_wheelchair_access:
            vehicles = vehicles.filter(has_wheelchair_access=True)
        
        if ride.requires_child_seat:
            vehicles = vehicles.filter(has_child_seat=True)
        
        # Filter by passenger capacity
        vehicles = vehicles.filter(passenger_capacity__gte=ride.passenger_count)
        
        # Calculate actual distances and filter by radius
        available_vehicles = []
        for vehicle in vehicles[:self.config.max_vehicles_to_consider]:
            if vehicle.current_location:
                v_lat, v_lng = vehicle.current_location
                distance = VehicleLocationService.calculate_distance(
                    pickup_lat, pickup_lng, v_lat, v_lng
                )
                
                if distance <= self.config.max_search_radius_km:
                    available_vehicles.append(vehicle)
        
        return available_vehicles
    
    def calculate_base_factors(self, vehicle: Vehicle, distance_km: float) -> Dict:
        """Calculate base scoring factors for a vehicle."""
        return {
            'distance_km': distance_km,
            'battery_level': vehicle.battery_level,
            'efficiency_score': self._calculate_efficiency_score(vehicle),
            'availability_score': self._calculate_availability_score(vehicle),
        }
    
    def _calculate_efficiency_score(self, vehicle: Vehicle) -> float:
        """Calculate vehicle efficiency score (0-1)."""
        # Base efficiency on total rides and revenue
        if vehicle.total_rides == 0:
            return 0.5  # Neutral score for new vehicles
        
        # Calculate rides per day (assuming vehicle has been active for at least 1 day)
        days_active = max(1, (timezone.now() - vehicle.created_at).days)
        rides_per_day = vehicle.total_rides / days_active
        
        # Normalize to 0-1 scale (assuming 10 rides/day is excellent)
        efficiency = min(1.0, rides_per_day / 10.0)
        return efficiency
    
    def _calculate_availability_score(self, vehicle: Vehicle) -> float:
        """Calculate availability score based on how long vehicle has been idle."""
        if not vehicle.last_seen:
            return 0.5  # Neutral score if no data
        
        # Time since last activity
        idle_time = timezone.now() - vehicle.last_seen
        idle_hours = idle_time.total_seconds() / 3600
        
        # Score increases with idle time up to 2 hours, then plateaus
        availability = min(1.0, idle_hours / 2.0)
        return availability


class NearestVehicleAlgorithm(BaseDispatchAlgorithm):
    """Simple nearest vehicle algorithm."""
    
    def find_best_vehicle(
        self, 
        pickup_lat: float, 
        pickup_lng: float, 
        ride: Ride
    ) -> Optional[VehicleScore]:
        """Find the nearest available vehicle."""
        
        available_vehicles = self.get_available_vehicles(pickup_lat, pickup_lng, ride)
        
        if not available_vehicles:
            return None
        
        best_vehicle = None
        best_distance = float('inf')
        
        for vehicle in available_vehicles:
            v_lat, v_lng = vehicle.current_location
            distance = VehicleLocationService.calculate_distance(
                pickup_lat, pickup_lng, v_lat, v_lng
            )
            
            if distance < best_distance:
                best_distance = distance
                best_vehicle = vehicle
        
        if best_vehicle:
            factors = self.calculate_base_factors(best_vehicle, best_distance)
            # Score is inverse of distance (closer = higher score)
            score = 1.0 / (1.0 + best_distance)
            
            return VehicleScore(best_vehicle, best_distance, score, factors)
        
        return None


class WeightedScoringAlgorithm(BaseDispatchAlgorithm):
    """Advanced algorithm using weighted scoring of multiple factors."""
    
    def find_best_vehicle(
        self, 
        pickup_lat: float, 
        pickup_lng: float, 
        ride: Ride
    ) -> Optional[VehicleScore]:
        """Find the best vehicle using weighted scoring."""
        
        available_vehicles = self.get_available_vehicles(pickup_lat, pickup_lng, ride)
        
        if not available_vehicles:
            return None
        
        scored_vehicles = []
        
        for vehicle in available_vehicles:
            v_lat, v_lng = vehicle.current_location
            distance = VehicleLocationService.calculate_distance(
                pickup_lat, pickup_lng, v_lat, v_lng
            )
            
            factors = self.calculate_base_factors(vehicle, distance)
            score = self._calculate_weighted_score(factors)
            
            scored_vehicles.append(VehicleScore(vehicle, distance, score, factors))
        
        # Sort by score (highest first)
        scored_vehicles.sort(key=lambda x: x.score, reverse=True)
        
        return scored_vehicles[0] if scored_vehicles else None
    
    def _calculate_weighted_score(self, factors: Dict) -> float:
        """Calculate weighted score from factors."""
        
        # Normalize distance (closer = higher score)
        distance_score = 1.0 / (1.0 + factors['distance_km'])
        
        # Normalize battery level (0-100 -> 0-1)
        battery_score = factors['battery_level'] / 100.0
        
        # Efficiency and availability are already 0-1
        efficiency_score = factors['efficiency_score']
        availability_score = factors['availability_score']
        
        # Calculate weighted sum
        total_score = (
            distance_score * self.config.distance_weight +
            battery_score * self.config.battery_weight +
            efficiency_score * self.config.efficiency_weight +
            availability_score * self.config.availability_weight
        )
        
        return total_score


class PredictiveDispatchAlgorithm(BaseDispatchAlgorithm):
    """Advanced algorithm with predictive elements."""
    
    def find_best_vehicle(
        self, 
        pickup_lat: float, 
        pickup_lng: float, 
        ride: Ride
    ) -> Optional[VehicleScore]:
        """Find the best vehicle using predictive scoring."""
        
        available_vehicles = self.get_available_vehicles(pickup_lat, pickup_lng, ride)
        
        if not available_vehicles:
            return None
        
        scored_vehicles = []
        
        for vehicle in available_vehicles:
            v_lat, v_lng = vehicle.current_location
            distance = VehicleLocationService.calculate_distance(
                pickup_lat, pickup_lng, v_lat, v_lng
            )
            
            factors = self.calculate_base_factors(vehicle, distance)
            
            # Add predictive factors
            factors.update({
                'demand_prediction': self._predict_demand_score(pickup_lat, pickup_lng),
                'traffic_prediction': self._predict_traffic_score(v_lat, v_lng, pickup_lat, pickup_lng),
                'vehicle_reliability': self._calculate_reliability_score(vehicle),
            })
            
            score = self._calculate_predictive_score(factors)
            scored_vehicles.append(VehicleScore(vehicle, distance, score, factors))
        
        # Sort by score (highest first)
        scored_vehicles.sort(key=lambda x: x.score, reverse=True)
        
        return scored_vehicles[0] if scored_vehicles else None
    
    def _predict_demand_score(self, lat: float, lng: float) -> float:
        """Predict demand score for the area (simplified)."""
        # In a real implementation, this would use historical data and ML models
        # For now, return a base score with some variation based on location
        
        # Higher demand in central areas (simplified)
        mumbai_center_lat, mumbai_center_lng = 19.0760, 72.8777
        distance_from_center = VehicleLocationService.calculate_distance(
            lat, lng, mumbai_center_lat, mumbai_center_lng
        )
        
        # Closer to center = higher demand
        demand_score = max(0.1, 1.0 - (distance_from_center / 20.0))
        return min(1.0, demand_score)
    
    def _predict_traffic_score(self, v_lat: float, v_lng: float, p_lat: float, p_lng: float) -> float:
        """Predict traffic conditions (simplified)."""
        # In a real implementation, this would use traffic APIs
        # For now, return a base score with time-of-day variation
        
        current_hour = timezone.now().hour
        
        # Rush hours have lower scores (more traffic)
        if 8 <= current_hour <= 10 or 17 <= current_hour <= 20:
            traffic_score = 0.3
        elif 11 <= current_hour <= 16:
            traffic_score = 0.7
        else:
            traffic_score = 0.9
        
        return traffic_score
    
    def _calculate_reliability_score(self, vehicle: Vehicle) -> float:
        """Calculate vehicle reliability score."""
        # Base reliability on maintenance history and age
        if vehicle.total_rides == 0:
            return 0.8  # Good default for new vehicles
        
        # Check if vehicle needs maintenance
        if vehicle.needs_maintenance:
            return 0.3  # Lower reliability if maintenance is due
        
        # Calculate based on maintenance frequency
        if vehicle.last_maintenance:
            days_since_maintenance = (timezone.now() - vehicle.last_maintenance).days
            # Reliability decreases as time since maintenance increases
            reliability = max(0.2, 1.0 - (days_since_maintenance / 90.0))  # 90 days = full cycle
        else:
            reliability = 0.5  # Neutral if no maintenance history
        
        return reliability
    
    def _calculate_predictive_score(self, factors: Dict) -> float:
        """Calculate predictive score from all factors."""
        
        # Base weighted score
        base_score = (
            (1.0 / (1.0 + factors['distance_km'])) * self.config.distance_weight +
            (factors['battery_level'] / 100.0) * self.config.battery_weight +
            factors['efficiency_score'] * self.config.efficiency_weight +
            factors['availability_score'] * self.config.availability_weight
        )
        
        # Predictive adjustments
        predictive_multiplier = (
            factors['demand_prediction'] * 0.3 +
            factors['traffic_prediction'] * 0.4 +
            factors['vehicle_reliability'] * 0.3
        )
        
        # Combine base score with predictive factors
        final_score = base_score * (0.7 + 0.3 * predictive_multiplier)
        
        return final_score


class DispatchService:
    """Main dispatch service for vehicle assignment."""
    
    def __init__(self):
        self.algorithms = {
            'nearest': NearestVehicleAlgorithm,
            'weighted': WeightedScoringAlgorithm,
            'predictive': PredictiveDispatchAlgorithm,
        }
    
    def dispatch_ride(self, ride: Ride) -> Optional[DispatchRequest]:
        """Dispatch a vehicle for the given ride."""
        
        # Create dispatch request
        dispatch_request = DispatchRequest.objects.create(
            ride=ride,
            priority=self._determine_priority(ride)
        )
        
        try:
            dispatch_request.start_processing()
            
            # Get active algorithm configuration
            algorithm_config = self._get_active_algorithm()
            if not algorithm_config:
                dispatch_request.mark_failed("No active dispatch algorithm configured")
                return dispatch_request
            
            # Initialize algorithm
            algorithm_class = self.algorithms.get(algorithm_config.name)
            if not algorithm_class:
                dispatch_request.mark_failed(f"Unknown algorithm: {algorithm_config.name}")
                return dispatch_request
            
            algorithm = algorithm_class(algorithm_config)
            
            # Find best vehicle
            best_vehicle_score = algorithm.find_best_vehicle(
                ride.pickup_latitude,
                ride.pickup_longitude,
                ride
            )
            
            if best_vehicle_score:
                # Assign vehicle
                dispatch_request.assign_vehicle(
                    vehicle=best_vehicle_score.vehicle,
                    algorithm_used=algorithm_config.name,
                    search_radius=algorithm_config.max_search_radius_km,
                    vehicles_considered=len(algorithm.get_available_vehicles(
                        ride.pickup_latitude, ride.pickup_longitude, ride
                    ))
                )
                
                logger.info(
                    f"Dispatched vehicle {best_vehicle_score.vehicle.license_plate} "
                    f"to ride {ride.id} using {algorithm_config.name} algorithm. "
                    f"Distance: {best_vehicle_score.distance_km:.2f}km, "
                    f"Score: {best_vehicle_score.score:.3f}"
                )
                
            else:
                dispatch_request.mark_failed("No available vehicles found")
                logger.warning(f"No vehicles available for ride {ride.id}")
            
        except Exception as e:
            dispatch_request.mark_failed(f"Dispatch error: {str(e)}")
            logger.error(f"Dispatch error for ride {ride.id}: {str(e)}")
        
        return dispatch_request
    
    def _determine_priority(self, ride: Ride) -> str:
        """Determine dispatch priority for a ride."""
        
        # High priority for special requirements
        if ride.requires_wheelchair_access:
            return DispatchRequest.Priority.HIGH
        
        # Normal priority by default
        return DispatchRequest.Priority.NORMAL
    
    def _get_active_algorithm(self) -> Optional[DispatchAlgorithmConfig]:
        """Get the active dispatch algorithm configuration."""
        return DispatchAlgorithmConfig.objects.filter(
            is_active=True
        ).order_by('-priority').first()
    
    def retry_failed_dispatches(self) -> int:
        """Retry failed dispatch requests."""
        
        # Get failed requests that haven't exceeded retry limit
        failed_requests = DispatchRequest.objects.filter(
            status=DispatchRequest.Status.FAILED,
            retry_count__lt=3,  # Max 3 retries
            created_at__gte=timezone.now() - timedelta(hours=1)  # Only recent failures
        )
        
        retry_count = 0
        
        for dispatch_request in failed_requests:
            # Reset status and retry
            dispatch_request.status = DispatchRequest.Status.PENDING
            dispatch_request.failure_reason = ''
            dispatch_request.save(update_fields=['status', 'failure_reason'])
            
            # Attempt dispatch again
            new_request = self.dispatch_ride(dispatch_request.ride)
            if new_request and new_request.status == DispatchRequest.Status.ASSIGNED:
                retry_count += 1
        
        return retry_count
    
    def cleanup_expired_requests(self) -> int:
        """Clean up expired dispatch requests."""
        
        expired_requests = DispatchRequest.objects.filter(
            status__in=[
                DispatchRequest.Status.PENDING,
                DispatchRequest.Status.PROCESSING
            ],
            expires_at__lt=timezone.now()
        )
        
        count = 0
        for request in expired_requests:
            request.expire_request()
            count += 1
            
            # Cancel the associated ride if it's still in requested status
            if request.ride.status == Ride.Status.REQUESTED:
                request.ride.cancel_ride(
                    reason=Ride.CancellationReason.NO_DRIVER,
                    notes='Dispatch request expired - no vehicles available'
                )
        
        return count
    
    def get_dispatch_statistics(self, days: int = 7) -> Dict:
        """Get dispatch performance statistics."""
        
        start_date = timezone.now() - timedelta(days=days)
        
        requests = DispatchRequest.objects.filter(created_at__gte=start_date)
        
        total_requests = requests.count()
        successful = requests.filter(status=DispatchRequest.Status.ASSIGNED).count()
        failed = requests.filter(status=DispatchRequest.Status.FAILED).count()
        expired = requests.filter(status=DispatchRequest.Status.EXPIRED).count()
        
        # Calculate average processing time
        completed_requests = requests.filter(
            status=DispatchRequest.Status.ASSIGNED,
            processing_started_at__isnull=False,
            assigned_at__isnull=False
        )
        
        avg_processing_time = None
        if completed_requests.exists():
            total_time = sum(
                (req.assigned_at - req.processing_started_at).total_seconds()
                for req in completed_requests
            )
            avg_processing_time = total_time / completed_requests.count()
        
        return {
            'total_requests': total_requests,
            'successful_assignments': successful,
            'failed_assignments': failed,
            'expired_requests': expired,
            'success_rate': (successful / total_requests * 100) if total_requests > 0 else 0,
            'average_processing_time_seconds': avg_processing_time,
        }