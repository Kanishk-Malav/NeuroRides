"""
Views for ride booking and management API.
"""

from django.db.models import Q, Avg, Count, Sum
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsRider, IsOperatorOrAdmin
from fleet.services import VehicleLocationService

from .models import Ride, RideRequest, ServiceArea, RideFareCalculator
from .serializers import (
    RideSerializer,
    RideCreateSerializer,
    RideActionSerializer,
    RideHistorySerializer,
    FareEstimateSerializer,
    FareEstimateResponseSerializer,
    ServiceAreaSerializer,
    RideStatsSerializer,
    NearbyVehicleSerializer,
    RideTrackingSerializer,
)


class FareEstimateView(APIView):
    """Get fare estimate for a ride."""
    
    permission_classes = [permissions.IsAuthenticated, IsRider]
    
    def post(self, request):
        """Calculate fare estimate."""
        serializer = FareEstimateSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Calculate distance
            pickup_lat = data['pickup_latitude']
            pickup_lng = data['pickup_longitude']
            dest_lat = data['destination_latitude']
            dest_lng = data['destination_longitude']
            
            distance_km = VehicleLocationService.calculate_distance(
                pickup_lat, pickup_lng, dest_lat, dest_lng
            )
            
            # Estimate duration (assuming 25 km/h average speed + 10 min buffer)
            estimated_duration = int((distance_km / 25) * 60) + 10
            
            # Get surge multiplier from service area
            service_area = ServiceArea.get_service_area_for_location(pickup_lat, pickup_lng)
            surge_multiplier = service_area.surge_multiplier if service_area else 1.0
            
            # Calculate fare
            fare = RideFareCalculator.calculate_fare_estimate(
                distance_km=distance_km,
                estimated_duration_minutes=estimated_duration,
                vehicle_type=data.get('vehicle_type', 'sedan'),
                requires_wheelchair_access=data.get('requires_wheelchair_access', False),
                requires_child_seat=data.get('requires_child_seat', False),
                surge_multiplier=surge_multiplier
            )
            
            # Create breakdown
            breakdown = {
                'base_fare': float(RideFareCalculator.BASE_FARE),
                'distance_fare': float(distance_km * RideFareCalculator.RATE_PER_KM),
                'time_fare': float(estimated_duration * RideFareCalculator.RATE_PER_MINUTE),
                'surge_multiplier': float(surge_multiplier),
                'special_requirements': 0.0
            }
            
            if data.get('requires_wheelchair_access'):
                breakdown['special_requirements'] += float(RideFareCalculator.WHEELCHAIR_SURCHARGE)
            
            if data.get('requires_child_seat'):
                breakdown['special_requirements'] += float(RideFareCalculator.CHILD_SEAT_SURCHARGE)
            
            response_data = {
                'estimated_fare': fare,
                'distance_km': round(distance_km, 2),
                'estimated_duration_minutes': estimated_duration,
                'surge_multiplier': surge_multiplier,
                'breakdown': breakdown
            }
            
            return Response(response_data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideCreateView(generics.CreateAPIView):
    """Create a new ride booking."""
    
    serializer_class = RideCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsRider]
    
    def create(self, request, *args, **kwargs):
        """Create a new ride."""
        # Check if user has any active rides
        active_ride = Ride.objects.filter(
            rider=request.user,
            status__in=[
                Ride.Status.REQUESTED,
                Ride.Status.ASSIGNED,
                Ride.Status.PICKUP,
                Ride.Status.IN_PROGRESS
            ]
        ).first()
        
        if active_ride:
            return Response({
                'error': 'You already have an active ride',
                'active_ride_id': active_ride.id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            ride = serializer.save()
            
            # Return ride data with fare estimate
            ride_serializer = RideSerializer(ride)
            
            return Response({
                'message': 'Ride booked successfully',
                'ride': ride_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideDetailView(generics.RetrieveAPIView):
    """Get ride details."""
    
    serializer_class = RideSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter rides based on user role."""
        user = self.request.user
        
        if user.is_rider:
            # Riders can only see their own rides
            return Ride.objects.filter(rider=user)
        elif user.is_operator or user.is_admin_user:
            # Operators and admins can see all rides
            return Ride.objects.all()
        
        return Ride.objects.none()


class RideActionView(APIView):
    """Perform actions on rides (cancel, rate, etc.)."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, ride_id):
        """Perform ride action."""
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            return Response(
                {'error': 'Ride not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if request.user.is_rider and ride.rider != request.user:
            return Response(
                {'error': 'You can only perform actions on your own rides'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RideActionSerializer(data=request.data)
        if serializer.is_valid():
            action = serializer.validated_data['action']
            
            if action == 'cancel':
                if not ride.can_be_cancelled:
                    return Response(
                        {'error': f'Cannot cancel ride with status {ride.status}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                ride.cancel_ride(
                    reason=serializer.validated_data['cancellation_reason'],
                    notes=serializer.validated_data.get('cancellation_notes', ''),
                    cancelled_by=request.user
                )
                
                return Response({
                    'message': 'Ride cancelled successfully',
                    'status': ride.status
                })
            
            elif action == 'rate':
                if ride.status != Ride.Status.COMPLETED:
                    return Response(
                        {'error': 'Can only rate completed rides'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if ride.rider != request.user:
                    return Response(
                        {'error': 'Only the rider can rate the ride'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                ride.rider_rating = serializer.validated_data['rating']
                ride.rider_feedback = serializer.validated_data.get('feedback', '')
                ride.save(update_fields=['rider_rating', 'rider_feedback'])
                
                return Response({
                    'message': 'Rating submitted successfully',
                    'rating': ride.rider_rating
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideHistoryView(generics.ListAPIView):
    """Get ride history for the current user."""
    
    serializer_class = RideHistorySerializer
    permission_classes = [permissions.IsAuthenticated, IsRider]
    
    def get_queryset(self):
        """Get rides for the current user."""
        return Ride.objects.filter(
            rider=self.request.user
        ).order_by('-requested_at')


class ActiveRideView(APIView):
    """Get current active ride for the user."""
    
    permission_classes = [permissions.IsAuthenticated, IsRider]
    
    def get(self, request):
        """Get active ride."""
        active_ride = Ride.objects.filter(
            rider=request.user,
            status__in=[
                Ride.Status.REQUESTED,
                Ride.Status.ASSIGNED,
                Ride.Status.PICKUP,
                Ride.Status.IN_PROGRESS
            ]
        ).first()
        
        if active_ride:
            serializer = RideSerializer(active_ride)
            return Response({
                'has_active_ride': True,
                'ride': serializer.data
            })
        
        return Response({
            'has_active_ride': False,
            'ride': None
        })


class RideTrackingView(APIView):
    """Get real-time ride tracking information."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, ride_id):
        """Get ride tracking data."""
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            return Response(
                {'error': 'Ride not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if request.user.is_rider and ride.rider != request.user:
            return Response(
                {'error': 'You can only track your own rides'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tracking_data = {
            'ride_id': ride.id,
            'status': ride.status,
            'last_updated': timezone.now()
        }
        
        # Add vehicle location if available
        if ride.vehicle and ride.vehicle.current_location:
            vehicle_lat, vehicle_lng = ride.vehicle.current_location
            tracking_data['vehicle_location'] = {
                'latitude': vehicle_lat,
                'longitude': vehicle_lng
            }
            
            # Calculate distances and ETA based on status
            if ride.status == Ride.Status.PICKUP:
                # Vehicle is en route to pickup
                distance_to_pickup = VehicleLocationService.calculate_distance(
                    vehicle_lat, vehicle_lng,
                    ride.pickup_latitude, ride.pickup_longitude
                )
                tracking_data['distance_to_pickup_km'] = round(distance_to_pickup, 2)
                tracking_data['estimated_arrival_minutes'] = max(1, int(distance_to_pickup / 0.5))  # 30 km/h
            
            elif ride.status == Ride.Status.IN_PROGRESS:
                # Vehicle is en route to destination
                distance_to_destination = VehicleLocationService.calculate_distance(
                    vehicle_lat, vehicle_lng,
                    ride.destination_latitude, ride.destination_longitude
                )
                tracking_data['distance_to_destination_km'] = round(distance_to_destination, 2)
                tracking_data['estimated_arrival_minutes'] = max(1, int(distance_to_destination / 0.5))
        
        return Response(tracking_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def nearby_vehicles(request):
    """Get nearby available vehicles."""
    latitude = request.query_params.get('lat')
    longitude = request.query_params.get('lng')
    radius = float(request.query_params.get('radius', 10))  # Default 10km
    
    if not latitude or not longitude:
        return Response(
            {'error': 'Latitude and longitude are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        lat = float(latitude)
        lng = float(longitude)
    except ValueError:
        return Response(
            {'error': 'Invalid latitude or longitude'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find nearby vehicles
    nearby_vehicles_data = VehicleLocationService.find_nearest_vehicles(
        latitude=lat,
        longitude=lng,
        radius_km=radius,
        available_only=True
    )
    
    # Format response
    vehicles = []
    for vehicle_data in nearby_vehicles_data:
        vehicle = vehicle_data['vehicle']
        vehicles.append({
            'vehicle_id': vehicle.id,
            'license_plate': vehicle.license_plate,
            'model': vehicle.model,
            'vehicle_type': vehicle.vehicle_type,
            'battery_level': vehicle.battery_level,
            'distance_km': vehicle_data['distance_km'],
            'estimated_arrival_minutes': vehicle_data['estimated_arrival_minutes'],
            'location': {
                'latitude': vehicle.current_latitude,
                'longitude': vehicle.current_longitude
            }
        })
    
    return Response({
        'center': {'latitude': lat, 'longitude': lng},
        'radius_km': radius,
        'count': len(vehicles),
        'vehicles': vehicles
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def ride_stats(request):
    """Get ride statistics."""
    # Time filter
    days = int(request.query_params.get('days', 30))
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    # Base queryset
    rides = Ride.objects.filter(requested_at__gte=start_date)
    
    # Calculate statistics
    total_rides = rides.count()
    completed_rides = rides.filter(status=Ride.Status.COMPLETED).count()
    cancelled_rides = rides.filter(status=Ride.Status.CANCELLED).count()
    active_rides = rides.filter(
        status__in=[
            Ride.Status.REQUESTED,
            Ride.Status.ASSIGNED,
            Ride.Status.PICKUP,
            Ride.Status.IN_PROGRESS
        ]
    ).count()
    
    # Revenue and fare statistics
    completed_rides_qs = rides.filter(status=Ride.Status.COMPLETED)
    total_revenue = completed_rides_qs.aggregate(
        total=Sum('final_fare')
    )['total'] or 0
    
    average_fare = completed_rides_qs.aggregate(
        avg=Avg('final_fare')
    )['avg'] or 0
    
    # Rating statistics
    average_rating = completed_rides_qs.filter(
        rider_rating__isnull=False
    ).aggregate(
        avg=Avg('rider_rating')
    )['avg'] or 0
    
    # Completion rate
    completion_rate = (completed_rides / total_rides * 100) if total_rides > 0 else 0
    
    stats = {
        'total_rides': total_rides,
        'completed_rides': completed_rides,
        'cancelled_rides': cancelled_rides,
        'active_rides': active_rides,
        'total_revenue': total_revenue,
        'average_fare': average_fare,
        'average_rating': round(average_rating, 2),
        'completion_rate': round(completion_rate, 2)
    }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def service_areas(request):
    """Get available service areas."""
    areas = ServiceArea.objects.filter(is_active=True)
    serializer = ServiceAreaSerializer(areas, many=True)
    
    return Response({
        'service_areas': serializer.data
    })


class RideListView(generics.ListAPIView):
    """List rides (for operators/admins)."""
    
    serializer_class = RideSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_queryset(self):
        """Get rides with filtering."""
        queryset = Ride.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by rider
        rider_id = self.request.query_params.get('rider_id')
        if rider_id:
            queryset = queryset.filter(rider_id=rider_id)
        
        # Filter by vehicle
        vehicle_id = self.request.query_params.get('vehicle_id')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(requested_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(requested_at__lte=end_date)
        
        return queryset.order_by('-requested_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def cleanup_expired_requests(request):
    """Clean up expired ride requests."""
    from .signals import cleanup_expired_requests
    
    count = cleanup_expired_requests()
    
    return Response({
        'message': f'Cleaned up {count} expired ride requests',
        'expired_count': count
    })