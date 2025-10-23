"""
Serializers for dispatch app.
"""

from rest_framework import serializers
from django.utils import timezone
from .models import DispatchRequest, DispatchAlgorithmConfig, DispatchMetrics


class DispatchRequestSerializer(serializers.ModelSerializer):
    """Serializer for DispatchRequest model."""
    
    ride_info = serializers.SerializerMethodField()
    vehicle_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    processing_duration_seconds = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = DispatchRequest
        fields = [
            'id',
            'ride',
            'ride_info',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'assigned_vehicle',
            'vehicle_info',
            'algorithm_used',
            'search_radius_km',
            'vehicles_considered',
            'failure_reason',
            'retry_count',
            'created_at',
            'processing_started_at',
            'assigned_at',
            'expires_at',
            'processing_duration_seconds',
            'is_expired',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'processing_started_at',
            'assigned_at',
            'processing_duration_seconds',
            'is_expired',
        ]
    
    def get_ride_info(self, obj):
        """Get ride information."""
        if obj.ride:
            return {
                'id': obj.ride.id,
                'rider_name': obj.ride.rider.get_full_name() or obj.ride.rider.username,
                'pickup_address': obj.ride.pickup_address,
                'destination_address': obj.ride.destination_address,
                'status': obj.ride.status,
                'created_at': obj.ride.created_at,
            }
        return None
    
    def get_vehicle_info(self, obj):
        """Get assigned vehicle information."""
        if obj.assigned_vehicle:
            return {
                'id': obj.assigned_vehicle.id,
                'license_plate': obj.assigned_vehicle.license_plate,
                'model': obj.assigned_vehicle.model,
                'battery_level': obj.assigned_vehicle.battery_level,
                'status': obj.assigned_vehicle.status,
            }
        return None
    
    def get_processing_duration_seconds(self, obj):
        """Get processing duration in seconds."""
        duration = obj.processing_duration
        if duration:
            return round(duration.total_seconds(), 2)
        return None


class DispatchRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dispatch requests."""
    
    class Meta:
        model = DispatchRequest
        fields = [
            'ride',
            'priority',
        ]
    
    def validate_ride(self, value):
        """Validate ride for dispatch."""
        if value.status != value.Status.REQUESTED:
            raise serializers.ValidationError(
                "Only rides with 'requested' status can be dispatched."
            )
        
        # Check if there's already an active dispatch request
        existing_request = DispatchRequest.objects.filter(
            ride=value,
            status__in=[
                DispatchRequest.Status.PENDING,
                DispatchRequest.Status.PROCESSING,
                DispatchRequest.Status.ASSIGNED,
            ]
        ).first()
        
        if existing_request:
            raise serializers.ValidationError(
                f"Active dispatch request already exists for this ride (ID: {existing_request.id})."
            )
        
        return value


class DispatchAlgorithmConfigSerializer(serializers.ModelSerializer):
    """Serializer for DispatchAlgorithmConfig model."""
    
    class Meta:
        model = DispatchAlgorithmConfig
        fields = [
            'id',
            'name',
            'is_active',
            'priority',
            'max_search_radius_km',
            'max_vehicles_to_consider',
            'min_battery_level',
            'distance_weight',
            'battery_weight',
            'efficiency_weight',
            'availability_weight',
            'max_processing_time_seconds',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]
    
    def validate_name(self, value):
        """Validate algorithm name."""
        if self.instance:
            # Update case - exclude current instance
            existing = DispatchAlgorithmConfig.objects.filter(
                name=value
            ).exclude(id=self.instance.id)
        else:
            # Create case
            existing = DispatchAlgorithmConfig.objects.filter(name=value)
        
        if existing.exists():
            raise serializers.ValidationError(
                "Algorithm configuration with this name already exists."
            )
        
        return value
    
    def validate(self, attrs):
        """Validate algorithm configuration."""
        # Validate weights sum to 1.0 for weighted algorithms
        if attrs.get('name') in ['weighted', 'predictive']:
            weights = [
                attrs.get('distance_weight', 0),
                attrs.get('battery_weight', 0),
                attrs.get('efficiency_weight', 0),
                attrs.get('availability_weight', 0),
            ]
            total_weight = sum(weights)
            
            if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
                raise serializers.ValidationError(
                    "For weighted algorithms, all weights must sum to 1.0. "
                    f"Current sum: {total_weight}"
                )
        
        return attrs


class DispatchMetricsSerializer(serializers.ModelSerializer):
    """Serializer for DispatchMetrics model."""
    
    success_rate_percentage = serializers.SerializerMethodField()
    failure_rate_percentage = serializers.SerializerMethodField()
    expiration_rate_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = DispatchMetrics
        fields = [
            'id',
            'date',
            'algorithm_name',
            'total_requests',
            'successful_assignments',
            'failed_assignments',
            'expired_requests',
            'average_processing_time_seconds',
            'average_distance_km',
            'average_eta_minutes',
            'success_rate',
            'success_rate_percentage',
            'failure_rate_percentage',
            'expiration_rate_percentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'success_rate',
            'created_at',
            'updated_at',
        ]
    
    def get_success_rate_percentage(self, obj):
        """Get success rate as percentage."""
        return f"{obj.success_rate:.1f}%" if obj.success_rate else "0.0%"
    
    def get_failure_rate_percentage(self, obj):
        """Get failure rate as percentage."""
        return f"{obj.failure_rate:.1f}%"
    
    def get_expiration_rate_percentage(self, obj):
        """Get expiration rate as percentage."""
        return f"{obj.expiration_rate:.1f}%"


class DispatchQueueStatusSerializer(serializers.Serializer):
    """Serializer for dispatch queue status."""
    
    pending_requests = serializers.IntegerField()
    processing_requests = serializers.IntegerField()
    total_active = serializers.IntegerField()
    priority_distribution = serializers.DictField()
    oldest_pending_request = serializers.DateTimeField(allow_null=True)
    average_wait_time_seconds = serializers.FloatField(allow_null=True)


class DispatchStatisticsSerializer(serializers.Serializer):
    """Serializer for dispatch statistics."""
    
    total_requests = serializers.IntegerField()
    successful_assignments = serializers.IntegerField()
    failed_assignments = serializers.IntegerField()
    expired_requests = serializers.IntegerField()
    success_rate = serializers.FloatField()
    failure_rate = serializers.FloatField()
    expiration_rate = serializers.FloatField()
    average_processing_time_seconds = serializers.FloatField(allow_null=True)
    average_distance_km = serializers.FloatField(allow_null=True)
    average_eta_minutes = serializers.FloatField(allow_null=True)
    algorithms_used = serializers.DictField()


class DispatchProcessingResultSerializer(serializers.Serializer):
    """Serializer for dispatch processing results."""
    
    processed = serializers.IntegerField()
    successful = serializers.IntegerField()
    failed = serializers.IntegerField()
    queue_size = serializers.IntegerField()
    processing_time_seconds = serializers.FloatField()
    details = serializers.ListField(child=serializers.DictField(), required=False)