"""
Views for fleet management API.
"""

import math
from django.db import models
from django.db.models import Q, Avg, Count, Sum
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsOperatorOrAdmin, IsOperator, IsAdmin
from accounts.decorators import secure_api_view

from .models import Vehicle, VehicleTelemetry, MaintenanceRecord
from .serializers import (
    VehicleSerializer,
    VehicleCreateSerializer,
    VehicleLocationSerializer,
    VehicleStatusSerializer,
    VehicleTelemetrySerializer,
    VehicleTelemetryCreateSerializer,
    MaintenanceRecordSerializer,
    MaintenanceRecordCreateSerializer,
    MaintenanceActionSerializer,
    VehicleStatsSerializer,
    FleetOverviewSerializer,
    VehicleSearchSerializer,
)


class VehicleListCreateView(generics.ListCreateAPIView):
    """List all vehicles or create a new vehicle."""
    
    queryset = Vehicle.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == 'POST':
            return VehicleCreateSerializer
        return VehicleSerializer
    
    def get_queryset(self):
        """Filter vehicles based on query parameters."""
        queryset = super().get_queryset()
        
        # Apply search filters
        search_serializer = VehicleSearchSerializer(data=self.request.query_params)
        if search_serializer.is_valid():
            filters = search_serializer.validated_data
            
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'vehicle_type' in filters:
                queryset = queryset.filter(vehicle_type=filters['vehicle_type'])
            
            if 'min_battery' in filters:
                queryset = queryset.filter(battery_level__gte=filters['min_battery'])
            
            if 'has_wheelchair_access' in filters:
                queryset = queryset.filter(has_wheelchair_access=filters['has_wheelchair_access'])
            
            if 'has_child_seat' in filters:
                queryset = queryset.filter(has_child_seat=filters['has_child_seat'])
            
            if filters.get('available_only'):
                # Filter for available vehicles
                queryset = queryset.filter(
                    status=Vehicle.Status.IDLE,
                    battery_level__gte=20,
                    current_latitude__isnull=False,
                    current_longitude__isnull=False
                )
            
            if 'near_location' in filters:
                location_data = filters['near_location']
                if isinstance(location_data, dict):
                    # Simple distance filtering (not using PostGIS for now)
                    lat = location_data['latitude']
                    lng = location_data['longitude']
                    radius = location_data['radius']
                    
                    # Calculate approximate bounding box
                    lat_delta = radius / 111.0  # Approximate km per degree latitude
                    lng_delta = radius / (111.0 * math.cos(math.radians(lat)))
                    
                    queryset = queryset.filter(
                        current_latitude__range=[lat - lat_delta, lat + lat_delta],
                        current_longitude__range=[lng - lng_delta, lng + lng_delta]
                    )
        
        return queryset.order_by('-created_at')


class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a vehicle."""
    
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    lookup_field = 'id'


class VehicleLocationUpdateView(APIView):
    """Update vehicle location."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def patch(self, request, vehicle_id):
        """Update vehicle location."""
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response(
                {'error': 'Vehicle not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = VehicleLocationSerializer(data=request.data)
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            
            vehicle.update_location(latitude, longitude)
            
            return Response({
                'message': 'Location updated successfully',
                'latitude': latitude,
                'longitude': longitude,
                'last_seen': vehicle.last_seen
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VehicleStatusUpdateView(APIView):
    """Update vehicle status."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def patch(self, request, vehicle_id):
        """Update vehicle status."""
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response(
                {'error': 'Vehicle not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = VehicleStatusSerializer(data=request.data)
        if serializer.is_valid():
            vehicle.status = serializer.validated_data['status']
            
            if 'battery_level' in serializer.validated_data:
                vehicle.battery_level = serializer.validated_data['battery_level']
            
            vehicle.save(update_fields=['status', 'battery_level'])
            
            return Response({
                'message': 'Status updated successfully',
                'status': vehicle.status,
                'battery_level': vehicle.battery_level
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VehicleTelemetryListCreateView(generics.ListCreateAPIView):
    """List telemetry data or create new telemetry record."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == 'POST':
            return VehicleTelemetryCreateSerializer
        return VehicleTelemetrySerializer
    
    def get_queryset(self):
        """Filter telemetry data."""
        queryset = VehicleTelemetry.objects.all()
        
        vehicle_id = self.request.query_params.get('vehicle_id')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        # Limit to recent data by default
        hours = int(self.request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        queryset = queryset.filter(timestamp__gte=since)
        
        return queryset.order_by('-timestamp')


class VehicleTelemetryDetailView(generics.RetrieveAPIView):
    """Retrieve specific telemetry record."""
    
    queryset = VehicleTelemetry.objects.all()
    serializer_class = VehicleTelemetrySerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]


class MaintenanceRecordListCreateView(generics.ListCreateAPIView):
    """List maintenance records or create new record."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == 'POST':
            return MaintenanceRecordCreateSerializer
        return MaintenanceRecordSerializer
    
    def get_queryset(self):
        """Filter maintenance records."""
        queryset = MaintenanceRecord.objects.all()
        
        vehicle_id = self.request.query_params.get('vehicle_id')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        maintenance_type = self.request.query_params.get('type')
        if maintenance_type:
            queryset = queryset.filter(maintenance_type=maintenance_type)
        
        return queryset.order_by('-scheduled_date')


class MaintenanceRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete maintenance record."""
    
    queryset = MaintenanceRecord.objects.all()
    serializer_class = MaintenanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]


class MaintenanceActionView(APIView):
    """Start or complete maintenance."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperator]
    
    def post(self, request, record_id):
        """Perform maintenance action."""
        try:
            record = MaintenanceRecord.objects.get(id=record_id)
        except MaintenanceRecord.DoesNotExist:
            return Response(
                {'error': 'Maintenance record not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MaintenanceActionSerializer(data=request.data)
        if serializer.is_valid():
            action = serializer.validated_data['action']
            notes = serializer.validated_data.get('notes', '')
            actual_cost = serializer.validated_data.get('actual_cost')
            
            if action == 'start':
                if record.status != MaintenanceRecord.Status.SCHEDULED:
                    return Response(
                        {'error': 'Can only start scheduled maintenance'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                record.start_maintenance()
                message = 'Maintenance started successfully'
            
            elif action == 'complete':
                if record.status != MaintenanceRecord.Status.IN_PROGRESS:
                    return Response(
                        {'error': 'Can only complete in-progress maintenance'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                record.complete_maintenance(actual_cost=actual_cost, notes=notes)
                message = 'Maintenance completed successfully'
            
            return Response({
                'message': message,
                'status': record.status,
                'started_at': record.started_at,
                'completed_at': record.completed_at
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def fleet_overview(request):
    """Get fleet overview statistics."""
    # Calculate statistics
    total_vehicles = Vehicle.objects.count()
    available_vehicles = sum(1 for v in Vehicle.objects.all() if v.is_available)
    online_vehicles = sum(1 for v in Vehicle.objects.all() if v.is_online)
    
    vehicles_in_ride = Vehicle.objects.filter(status=Vehicle.Status.IN_RIDE).count()
    vehicles_in_maintenance = Vehicle.objects.filter(status=Vehicle.Status.MAINTENANCE).count()
    
    avg_battery = Vehicle.objects.aggregate(
        avg=Avg('battery_level')
    )['avg'] or 0
    
    # Today's statistics
    today = timezone.now().date()
    total_rides_today = Vehicle.objects.aggregate(
        total=Count('telemetry_data', filter=Q(telemetry_data__timestamp__date=today))
    )['total'] or 0
    
    total_revenue_today = Vehicle.objects.filter(
        updated_at__date=today
    ).aggregate(
        total=Sum('total_revenue')
    )['total'] or 0
    
    # Status distribution
    status_distribution = {}
    for status_choice in Vehicle.Status.choices:
        status = status_choice[0]
        count = Vehicle.objects.filter(status=status).count()
        status_distribution[status] = count
    
    # Battery distribution
    battery_ranges = [
        ('0-20', 0, 20),
        ('21-50', 21, 50),
        ('51-80', 51, 80),
        ('81-100', 81, 100),
    ]
    
    battery_distribution = {}
    for range_name, min_val, max_val in battery_ranges:
        count = Vehicle.objects.filter(
            battery_level__gte=min_val,
            battery_level__lte=max_val
        ).count()
        battery_distribution[range_name] = count
    
    # Recent alerts (vehicles needing attention)
    recent_alerts = []
    
    # Low battery vehicles
    low_battery_vehicles = Vehicle.objects.filter(battery_level__lt=20)
    for vehicle in low_battery_vehicles:
        recent_alerts.append({
            'type': 'low_battery',
            'vehicle': vehicle.license_plate,
            'message': f'Low battery: {vehicle.battery_level}%',
            'severity': 'high' if vehicle.battery_level < 10 else 'medium'
        })
    
    # Vehicles needing maintenance
    maintenance_vehicles = Vehicle.objects.filter(
        next_maintenance_due__lte=timezone.now() + timezone.timedelta(days=7)
    )
    for vehicle in maintenance_vehicles:
        recent_alerts.append({
            'type': 'maintenance_due',
            'vehicle': vehicle.license_plate,
            'message': f'Maintenance due: {vehicle.next_maintenance_due.date()}',
            'severity': 'medium'
        })
    
    # Offline vehicles
    offline_vehicles = Vehicle.objects.filter(status=Vehicle.Status.OFFLINE)
    for vehicle in offline_vehicles:
        recent_alerts.append({
            'type': 'offline',
            'vehicle': vehicle.license_plate,
            'message': 'Vehicle offline',
            'severity': 'high'
        })
    
    stats = {
        'total_vehicles': total_vehicles,
        'available_vehicles': available_vehicles,
        'online_vehicles': online_vehicles,
        'vehicles_in_ride': vehicles_in_ride,
        'vehicles_in_maintenance': vehicles_in_maintenance,
        'average_battery_level': round(avg_battery, 1),
        'total_rides_today': total_rides_today,
        'total_revenue_today': total_revenue_today,
    }
    
    overview_data = {
        'stats': stats,
        'status_distribution': status_distribution,
        'battery_distribution': battery_distribution,
        'recent_alerts': recent_alerts[:10]  # Limit to 10 most recent
    }
    
    return Response(overview_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def vehicle_nearby(request):
    """Find vehicles near a location."""
    latitude = request.query_params.get('lat')
    longitude = request.query_params.get('lng')
    radius = float(request.query_params.get('radius', 5))  # Default 5km
    
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
    
    # Simple distance calculation (not using PostGIS for now)
    lat_delta = radius / 111.0  # Approximate km per degree latitude
    lng_delta = radius / (111.0 * math.cos(math.radians(lat)))
    
    nearby_vehicles = Vehicle.objects.filter(
        current_latitude__range=[lat - lat_delta, lat + lat_delta],
        current_longitude__range=[lng - lng_delta, lng + lng_delta],
        current_latitude__isnull=False,
        current_longitude__isnull=False
    )
    
    # Calculate actual distances and sort
    vehicles_with_distance = []
    for vehicle in nearby_vehicles:
        if vehicle.current_location:
            v_lat, v_lng = vehicle.current_location
            # Haversine formula for distance calculation
            distance = calculate_distance(lat, lng, v_lat, v_lng)
            if distance <= radius:
                vehicles_with_distance.append({
                    'vehicle': VehicleSerializer(vehicle).data,
                    'distance_km': round(distance, 2)
                })
    
    # Sort by distance
    vehicles_with_distance.sort(key=lambda x: x['distance_km'])
    
    return Response({
        'center': {'latitude': lat, 'longitude': lng},
        'radius_km': radius,
        'count': len(vehicles_with_distance),
        'vehicles': vehicles_with_distance
    })


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def bulk_vehicle_action(request):
    """Perform bulk actions on vehicles."""
    vehicle_ids = request.data.get('vehicle_ids', [])
    action = request.data.get('action')
    
    if not vehicle_ids or not action:
        return Response(
            {'error': 'vehicle_ids and action are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    vehicles = Vehicle.objects.filter(id__in=vehicle_ids)
    if not vehicles.exists():
        return Response(
            {'error': 'No vehicles found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    updated_count = 0
    
    if action == 'set_maintenance':
        for vehicle in vehicles:
            if vehicle.status != Vehicle.Status.MAINTENANCE:
                vehicle.set_maintenance_mode()
                updated_count += 1
    
    elif action == 'set_idle':
        for vehicle in vehicles:
            if vehicle.status in [Vehicle.Status.OFFLINE, Vehicle.Status.MAINTENANCE]:
                vehicle.status = Vehicle.Status.IDLE
                vehicle.save(update_fields=['status'])
                updated_count += 1
    
    elif action == 'set_offline':
        for vehicle in vehicles:
            vehicle.status = Vehicle.Status.OFFLINE
            vehicle.save(update_fields=['status'])
            updated_count += 1
    
    else:
        return Response(
            {'error': 'Invalid action'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response({
        'message': f'{updated_count} vehicles updated successfully',
        'action': action,
        'updated_count': updated_count
    })