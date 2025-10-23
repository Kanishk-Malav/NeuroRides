"""
Serializers for fleet app.
"""

from rest_framework import serializers
from django.utils import timezone
from .models import Vehicle, VehicleTelemetry, MaintenanceRecord


class VehicleLocationSerializer(serializers.Serializer):
    """Serializer for vehicle location updates."""
    
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class VehicleStatusSerializer(serializers.Serializer):
    """Serializer for vehicle status updates."""
    
    status = serializers.ChoiceField(choices=Vehicle.Status.choices)
    battery_level = serializers.IntegerField(min_value=0, max_value=100, required=False)


class VehicleSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle model."""
    
    current_location_lat = serializers.SerializerMethodField()
    current_location_lng = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()
    is_online = serializers.ReadOnlyField()
    needs_maintenance = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    vehicle_type_display = serializers.CharField(source='get_vehicle_type_display', read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id',
            'license_plate',
            'model',
            'manufacturer',
            'year',
            'vehicle_type',
            'vehicle_type_display',
            'status',
            'status_display',
            'current_location_lat',
            'current_location_lng',
            'battery_level',
            'mileage',
            'passenger_capacity',
            'has_wheelchair_access',
            'has_child_seat',
            'total_rides',
            'total_revenue',
            'last_maintenance',
            'next_maintenance_due',
            'is_available',
            'is_online',
            'needs_maintenance',
            'last_seen',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'total_rides',
            'total_revenue',
            'last_seen',
            'created_at',
        ]
    
    def get_current_location_lat(self, obj):
        """Get current latitude."""
        return obj.current_latitude
    
    def get_current_location_lng(self, obj):
        """Get current longitude."""
        return obj.current_longitude


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating vehicles."""
    
    class Meta:
        model = Vehicle
        fields = [
            'license_plate',
            'model',
            'manufacturer',
            'year',
            'vehicle_type',
            'passenger_capacity',
            'has_wheelchair_access',
            'has_child_seat',
            'current_latitude',
            'current_longitude',
        ]
    
    def validate_license_plate(self, value):
        """Validate license plate uniqueness."""
        if Vehicle.objects.filter(license_plate=value).exists():
            raise serializers.ValidationError(
                'A vehicle with this license plate already exists.'
            )
        return value


class VehicleTelemetrySerializer(serializers.ModelSerializer):
    """Serializer for VehicleTelemetry model."""
    
    location_lat = serializers.SerializerMethodField()
    location_lng = serializers.SerializerMethodField()
    vehicle_license_plate = serializers.CharField(source='vehicle.license_plate', read_only=True)
    
    class Meta:
        model = VehicleTelemetry
        fields = [
            'id',
            'vehicle',
            'vehicle_license_plate',
            'location_lat',
            'location_lng',
            'speed',
            'heading',
            'battery_level',
            'temperature',
            'engine_status',
            'passenger_count',
            'diagnostic_codes',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']
    
    def get_location_lat(self, obj):
        """Get latitude."""
        return obj.latitude
    
    def get_location_lng(self, obj):
        """Get longitude."""
        return obj.longitude


class VehicleTelemetryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating telemetry data."""
    
    vehicle_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = VehicleTelemetry
        fields = [
            'vehicle_id',
            'latitude',
            'longitude',
            'speed',
            'heading',
            'battery_level',
            'temperature',
            'engine_status',
            'passenger_count',
            'diagnostic_codes',
        ]
    
    def validate_vehicle_id(self, value):
        """Validate vehicle exists."""
        try:
            Vehicle.objects.get(id=value)
        except Vehicle.DoesNotExist:
            raise serializers.ValidationError('Vehicle not found.')
        return value
    
    def create(self, validated_data):
        """Create telemetry record."""
        vehicle_id = validated_data.pop('vehicle_id')
        vehicle = Vehicle.objects.get(id=vehicle_id)
        
        return VehicleTelemetry.objects.create(
            vehicle=vehicle,
            **validated_data
        )


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    """Serializer for MaintenanceRecord model."""
    
    vehicle_license_plate = serializers.CharField(source='vehicle.license_plate', read_only=True)
    maintenance_type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    duration = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'id',
            'vehicle',
            'vehicle_license_plate',
            'maintenance_type',
            'maintenance_type_display',
            'status',
            'status_display',
            'scheduled_date',
            'started_at',
            'completed_at',
            'duration',
            'description',
            'notes',
            'estimated_cost',
            'actual_cost',
            'technician',
            'technician_name',
            'mileage_at_maintenance',
            'is_overdue',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'started_at',
            'completed_at',
            'mileage_at_maintenance',
            'created_at',
            'updated_at',
        ]
    
    def get_duration(self, obj):
        """Get maintenance duration in hours."""
        duration = obj.duration
        if duration:
            return round(duration.total_seconds() / 3600, 2)
        return None


class MaintenanceRecordCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating maintenance records."""
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'vehicle',
            'maintenance_type',
            'scheduled_date',
            'description',
            'estimated_cost',
            'technician',
        ]
    
    def validate_vehicle(self, value):
        """Validate vehicle exists and can be scheduled for maintenance."""
        if not value:
            raise serializers.ValidationError('Vehicle is required.')
        return value
    
    def validate_scheduled_date(self, value):
        """Validate scheduled date is in the future."""
        if value <= timezone.now():
            raise serializers.ValidationError(
                'Scheduled date must be in the future.'
            )
        return value


class MaintenanceActionSerializer(serializers.Serializer):
    """Serializer for maintenance actions (start/complete)."""
    
    action = serializers.ChoiceField(choices=['start', 'complete'])
    notes = serializers.CharField(required=False, allow_blank=True)
    actual_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    
    def validate(self, attrs):
        """Validate action-specific requirements."""
        action = attrs.get('action')
        
        if action == 'complete':
            # For completion, we might want to require actual cost
            pass
        
        return attrs


class VehicleStatsSerializer(serializers.Serializer):
    """Serializer for vehicle statistics."""
    
    total_vehicles = serializers.IntegerField()
    available_vehicles = serializers.IntegerField()
    online_vehicles = serializers.IntegerField()
    vehicles_in_ride = serializers.IntegerField()
    vehicles_in_maintenance = serializers.IntegerField()
    average_battery_level = serializers.FloatField()
    total_rides_today = serializers.IntegerField()
    total_revenue_today = serializers.DecimalField(max_digits=10, decimal_places=2)


class FleetOverviewSerializer(serializers.Serializer):
    """Serializer for fleet overview data."""
    
    stats = VehicleStatsSerializer()
    status_distribution = serializers.DictField()
    battery_distribution = serializers.DictField()
    recent_alerts = serializers.ListField()


class VehicleSearchSerializer(serializers.Serializer):
    """Serializer for vehicle search parameters."""
    
    status = serializers.ChoiceField(
        choices=Vehicle.Status.choices,
        required=False
    )
    vehicle_type = serializers.ChoiceField(
        choices=Vehicle.VehicleType.choices,
        required=False
    )
    min_battery = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False
    )
    has_wheelchair_access = serializers.BooleanField(required=False)
    has_child_seat = serializers.BooleanField(required=False)
    available_only = serializers.BooleanField(required=False)
    near_location = serializers.CharField(required=False)  # "lat,lng,radius_km"
    
    def validate_near_location(self, value):
        """Validate location search format."""
        if value:
            try:
                parts = value.split(',')
                if len(parts) != 3:
                    raise ValueError()
                
                lat = float(parts[0])
                lng = float(parts[1])
                radius = float(parts[2])
                
                if not (-90 <= lat <= 90):
                    raise ValueError('Invalid latitude')
                if not (-180 <= lng <= 180):
                    raise ValueError('Invalid longitude')
                if radius <= 0:
                    raise ValueError('Invalid radius')
                
                return {
                    'latitude': lat,
                    'longitude': lng,
                    'radius': radius
                }
            except (ValueError, IndexError):
                raise serializers.ValidationError(
                    'Location must be in format: "latitude,longitude,radius_km"'
                )
        return value