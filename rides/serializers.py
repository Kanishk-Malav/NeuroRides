"""
Serializers for rides app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from .models import Ride, RideRequest, ServiceArea, RideFareCalculator
from fleet.models import Vehicle

User = get_user_model()


class ServiceAreaSerializer(serializers.ModelSerializer):
    """Serializer for ServiceArea model."""
    
    class Meta:
        model = ServiceArea
        fields = [
            'id',
            'name',
            'description',
            'north_lat',
            'south_lat',
            'east_lng',
            'west_lng',
            'is_active',
            'surge_multiplier',
        ]
        read_only_fields = ['id']


class RideRequestSerializer(serializers.ModelSerializer):
    """Serializer for creating ride requests."""
    
    class Meta:
        model = RideRequest
        fields = [
            'pickup_latitude',
            'pickup_longitude',
            'destination_latitude',
            'destination_longitude',
            'passenger_count',
            'requires_wheelchair_access',
            'requires_child_seat',
        ]
    
    def validate(self, attrs):
        """Validate ride request data."""
        pickup_lat = attrs['pickup_latitude']
        pickup_lng = attrs['pickup_longitude']
        dest_lat = attrs['destination_latitude']
        dest_lng = attrs['destination_longitude']
        
        # Check if pickup and destination are in service area
        pickup_area = ServiceArea.get_service_area_for_location(pickup_lat, pickup_lng)
        dest_area = ServiceArea.get_service_area_for_location(dest_lat, dest_lng)
        
        if not pickup_area:
            raise serializers.ValidationError({
                'pickup_location': 'Pickup location is outside service area'
            })
        
        if not dest_area:
            raise serializers.ValidationError({
                'destination_location': 'Destination is outside service area'
            })
        
        # Check if pickup and destination are different
        if (abs(pickup_lat - dest_lat) < 0.001 and 
            abs(pickup_lng - dest_lng) < 0.001):
            raise serializers.ValidationError(
                'Pickup and destination must be different locations'
            )
        
        return attrs


class FareEstimateSerializer(serializers.Serializer):
    """Serializer for fare estimation requests."""
    
    pickup_latitude = serializers.FloatField(min_value=-90, max_value=90)
    pickup_longitude = serializers.FloatField(min_value=-180, max_value=180)
    destination_latitude = serializers.FloatField(min_value=-90, max_value=90)
    destination_longitude = serializers.FloatField(min_value=-180, max_value=180)
    passenger_count = serializers.IntegerField(min_value=1, max_value=8, default=1)
    requires_wheelchair_access = serializers.BooleanField(default=False)
    requires_child_seat = serializers.BooleanField(default=False)
    vehicle_type = serializers.ChoiceField(
        choices=['sedan', 'suv', 'luxury', 'compact'],
        default='sedan'
    )


class FareEstimateResponseSerializer(serializers.Serializer):
    """Serializer for fare estimation responses."""
    
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    distance_km = serializers.FloatField()
    estimated_duration_minutes = serializers.IntegerField()
    surge_multiplier = serializers.DecimalField(max_digits=3, decimal_places=2)
    breakdown = serializers.DictField()


class RideSerializer(serializers.ModelSerializer):
    """Serializer for Ride model."""
    
    rider_name = serializers.CharField(source='rider.get_full_name', read_only=True)
    vehicle_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pickup_location = serializers.SerializerMethodField()
    destination_location = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    total_duration_minutes = serializers.SerializerMethodField()
    can_be_cancelled = serializers.ReadOnlyField()
    
    class Meta:
        model = Ride
        fields = [
            'id',
            'rider',
            'rider_name',
            'vehicle',
            'vehicle_info',
            'status',
            'status_display',
            'pickup_latitude',
            'pickup_longitude',
            'pickup_location',
            'pickup_address',
            'destination_latitude',
            'destination_longitude',
            'destination_location',
            'destination_address',
            'passenger_count',
            'requires_wheelchair_access',
            'requires_child_seat',
            'pickup_notes',
            'ride_notes',
            'fare_estimate',
            'final_fare',
            'estimated_distance_km',
            'actual_distance_km',
            'estimated_duration_minutes',
            'actual_duration_minutes',
            'duration_minutes',
            'total_duration_minutes',
            'rider_rating',
            'rider_feedback',
            'cancellation_reason',
            'cancellation_notes',
            'requested_at',
            'assigned_at',
            'pickup_started_at',
            'picked_up_at',
            'completed_at',
            'cancelled_at',
            'can_be_cancelled',
        ]
        read_only_fields = [
            'id',
            'rider',
            'vehicle',
            'status',
            'fare_estimate',
            'final_fare',
            'estimated_distance_km',
            'actual_distance_km',
            'estimated_duration_minutes',
            'actual_duration_minutes',
            'requested_at',
            'assigned_at',
            'pickup_started_at',
            'picked_up_at',
            'completed_at',
            'cancelled_at',
        ]
    
    def get_vehicle_info(self, obj):
        """Get vehicle information."""
        if obj.vehicle:
            return {
                'id': obj.vehicle.id,
                'license_plate': obj.vehicle.license_plate,
                'model': obj.vehicle.model,
                'vehicle_type': obj.vehicle.vehicle_type,
                'current_location': {
                    'latitude': obj.vehicle.current_latitude,
                    'longitude': obj.vehicle.current_longitude,
                }
            }
        return None
    
    def get_pickup_location(self, obj):
        """Get pickup location as dict."""
        return {
            'latitude': obj.pickup_latitude,
            'longitude': obj.pickup_longitude,
        }
    
    def get_destination_location(self, obj):
        """Get destination location as dict."""
        return {
            'latitude': obj.destination_latitude,
            'longitude': obj.destination_longitude,
        }
    
    def get_duration_minutes(self, obj):
        """Get ride duration in minutes."""
        duration = obj.duration
        if duration:
            return int(duration.total_seconds() / 60)
        return None
    
    def get_total_duration_minutes(self, obj):
        """Get total duration in minutes."""
        duration = obj.total_duration
        if duration:
            return int(duration.total_seconds() / 60)
        return None


class RideCreateSerializer(serializers.Serializer):
    """Serializer for creating rides."""
    
    pickup_latitude = serializers.FloatField(min_value=-90, max_value=90)
    pickup_longitude = serializers.FloatField(min_value=-180, max_value=180)
    pickup_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    destination_latitude = serializers.FloatField(min_value=-90, max_value=90)
    destination_longitude = serializers.FloatField(min_value=-180, max_value=180)
    destination_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    passenger_count = serializers.IntegerField(min_value=1, max_value=8, default=1)
    requires_wheelchair_access = serializers.BooleanField(default=False)
    requires_child_seat = serializers.BooleanField(default=False)
    pickup_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    ride_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate ride creation data."""
        pickup_lat = attrs['pickup_latitude']
        pickup_lng = attrs['pickup_longitude']
        dest_lat = attrs['destination_latitude']
        dest_lng = attrs['destination_longitude']
        
        # Check service areas
        pickup_area = ServiceArea.get_service_area_for_location(pickup_lat, pickup_lng)
        dest_area = ServiceArea.get_service_area_for_location(dest_lat, dest_lng)
        
        if not pickup_area:
            raise serializers.ValidationError({
                'pickup_location': 'Pickup location is outside service area'
            })
        
        if not dest_area:
            raise serializers.ValidationError({
                'destination_location': 'Destination is outside service area'
            })
        
        # Check if locations are different
        if (abs(pickup_lat - dest_lat) < 0.001 and 
            abs(pickup_lng - dest_lng) < 0.001):
            raise serializers.ValidationError(
                'Pickup and destination must be different locations'
            )
        
        return attrs
    
    def create(self, validated_data):
        """Create a new ride."""
        rider = self.context['request'].user
        
        # Create the ride
        ride = Ride.objects.create(
            rider=rider,
            **validated_data
        )
        
        return ride


class RideActionSerializer(serializers.Serializer):
    """Serializer for ride actions (cancel, rate, etc.)."""
    
    action = serializers.ChoiceField(choices=['cancel', 'rate'])
    
    # Cancel action fields
    cancellation_reason = serializers.ChoiceField(
        choices=Ride.CancellationReason.choices,
        required=False
    )
    cancellation_notes = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    # Rate action fields
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    feedback = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True
    )
    
    def validate(self, attrs):
        """Validate action-specific requirements."""
        action = attrs.get('action')
        
        if action == 'cancel':
            if not attrs.get('cancellation_reason'):
                raise serializers.ValidationError({
                    'cancellation_reason': 'Cancellation reason is required for cancel action'
                })
        
        elif action == 'rate':
            if not attrs.get('rating'):
                raise serializers.ValidationError({
                    'rating': 'Rating is required for rate action'
                })
        
        return attrs


class RideHistorySerializer(serializers.ModelSerializer):
    """Serializer for ride history (simplified)."""
    
    vehicle_license_plate = serializers.CharField(
        source='vehicle.license_plate',
        read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = Ride
        fields = [
            'id',
            'status',
            'status_display',
            'pickup_address',
            'destination_address',
            'vehicle_license_plate',
            'fare_estimate',
            'final_fare',
            'actual_distance_km',
            'duration_minutes',
            'rider_rating',
            'requested_at',
            'completed_at',
        ]
    
    def get_duration_minutes(self, obj):
        """Get ride duration in minutes."""
        duration = obj.duration
        if duration:
            return int(duration.total_seconds() / 60)
        return None


class RideStatsSerializer(serializers.Serializer):
    """Serializer for ride statistics."""
    
    total_rides = serializers.IntegerField()
    completed_rides = serializers.IntegerField()
    cancelled_rides = serializers.IntegerField()
    active_rides = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_rating = serializers.FloatField()
    completion_rate = serializers.FloatField()


class NearbyVehicleSerializer(serializers.Serializer):
    """Serializer for nearby vehicle information."""
    
    vehicle_id = serializers.UUIDField()
    license_plate = serializers.CharField()
    model = serializers.CharField()
    vehicle_type = serializers.CharField()
    battery_level = serializers.IntegerField()
    distance_km = serializers.FloatField()
    estimated_arrival_minutes = serializers.IntegerField()
    location = serializers.DictField()


class RideTrackingSerializer(serializers.Serializer):
    """Serializer for real-time ride tracking data."""
    
    ride_id = serializers.UUIDField()
    status = serializers.CharField()
    vehicle_location = serializers.DictField(required=False)
    estimated_arrival_minutes = serializers.IntegerField(required=False)
    distance_to_pickup_km = serializers.FloatField(required=False)
    distance_to_destination_km = serializers.FloatField(required=False)
    last_updated = serializers.DateTimeField()