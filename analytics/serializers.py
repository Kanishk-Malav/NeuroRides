"""
Serializers for analytics app.
"""

from rest_framework import serializers
from datetime import date, datetime, timedelta
from django.utils import timezone
from .models import (
    AnalyticsMetric, RideAnalytics, RevenueAnalytics, 
    FleetAnalytics, UserAnalytics, PerformanceMetric,
    ReportTemplate, GeneratedReport
)


class DateRangeSerializer(serializers.Serializer):
    """Serializer for date range queries."""
    
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    granularity = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )
    
    def validate(self, data):
        """Validate date range."""
        start_date = data['start_date']
        end_date = data['end_date']
        
        if start_date > end_date:
            raise serializers.ValidationError("Start date must be before end date")
        
        # Limit range to prevent excessive data queries
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise serializers.ValidationError(f"Date range cannot exceed {max_days} days")
        
        return data


class RideAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for RideAnalytics model."""
    
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    cancellation_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = RideAnalytics
        fields = [
            'id', 'date', 'hour', 'total_rides', 'completed_rides', 
            'cancelled_rides', 'failed_rides', 'total_distance_km',
            'total_duration_minutes', 'avg_distance_km', 'avg_duration_minutes',
            'avg_wait_time_minutes', 'max_wait_time_minutes', 'city', 'region',
            'is_peak_hour', 'surge_multiplier_avg', 'completion_rate', 
            'cancellation_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RevenueAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for RevenueAnalytics model."""
    
    transaction_success_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = RevenueAnalytics
        fields = [
            'id', 'date', 'hour', 'total_revenue', 'gross_revenue', 'net_revenue',
            'base_fare_revenue', 'distance_fare_revenue', 'time_fare_revenue',
            'surge_revenue', 'tip_revenue', 'booking_fees', 'tax_amount',
            'discount_amount', 'refund_amount', 'total_transactions',
            'successful_transactions', 'failed_transactions', 'avg_transaction_value',
            'avg_ride_fare', 'city', 'region', 'transaction_success_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FleetAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for FleetAnalytics model."""
    
    class Meta:
        model = FleetAnalytics
        fields = [
            'id', 'date', 'hour', 'total_vehicles', 'active_vehicles',
            'idle_vehicles', 'maintenance_vehicles', 'utilization_rate',
            'avg_rides_per_vehicle', 'avg_revenue_per_vehicle', 'total_distance_driven',
            'avg_distance_per_vehicle', 'fuel_efficiency_avg', 'vehicles_due_maintenance',
            'maintenance_cost', 'downtime_hours', 'avg_response_time_minutes',
            'customer_rating_avg', 'city', 'region', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for UserAnalytics model."""
    
    class Meta:
        model = UserAnalytics
        fields = [
            'id', 'date', 'hour', 'total_users', 'new_users', 'active_users',
            'returning_users', 'avg_rides_per_user', 'avg_spend_per_user',
            'user_retention_rate', 'avg_rating_given', 'complaint_rate',
            'city', 'region', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceMetric model."""
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'category', 'metric_name', 'service_name', 'timestamp',
            'value', 'unit', 'warning_threshold', 'critical_threshold',
            'is_healthy', 'alert_sent', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for dashboard data."""
    
    period = serializers.CharField(read_only=True)
    rides = RideAnalyticsSerializer(read_only=True)
    revenue = RevenueAnalyticsSerializer(read_only=True)
    fleet = FleetAnalyticsSerializer(read_only=True)
    users = UserAnalyticsSerializer(read_only=True)
    
    # KPI summaries
    total_rides_today = serializers.IntegerField(read_only=True)
    total_revenue_today = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    active_vehicles = serializers.IntegerField(read_only=True)
    active_users_today = serializers.IntegerField(read_only=True)
    
    # Trends (percentage change from previous period)
    rides_trend = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    revenue_trend = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    fleet_utilization_trend = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    user_growth_trend = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)


class ChartDataPointSerializer(serializers.Serializer):
    """Serializer for chart data points."""
    
    timestamp = serializers.DateTimeField()
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    label = serializers.CharField(required=False)


class ChartDataSerializer(serializers.Serializer):
    """Serializer for chart data."""
    
    chart_type = serializers.ChoiceField(
        choices=['line', 'bar', 'pie', 'area', 'scatter']
    )
    title = serializers.CharField()
    x_axis_label = serializers.CharField()
    y_axis_label = serializers.CharField()
    data_points = ChartDataPointSerializer(many=True)
    
    # Optional metadata
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    average_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    trend_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class KPISerializer(serializers.Serializer):
    """Serializer for Key Performance Indicators."""
    
    name = serializers.CharField()
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    unit = serializers.CharField()
    trend_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    trend_direction = serializers.ChoiceField(
        choices=['up', 'down', 'stable'],
        required=False
    )
    target_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    status = serializers.ChoiceField(
        choices=['good', 'warning', 'critical'],
        default='good'
    )


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ReportTemplate model."""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'description', 'report_type', 'metrics_included',
            'filters', 'grouping', 'output_formats', 'created_by', 'created_by_name',
            'is_public', 'allowed_roles', 'is_scheduled', 'schedule_cron',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def validate_metrics_included(self, value):
        """Validate metrics_included field."""
        valid_metrics = [
            'rides', 'revenue', 'fleet', 'users', 'performance'
        ]
        
        if not isinstance(value, list):
            raise serializers.ValidationError("metrics_included must be a list")
        
        for metric in value:
            if metric not in valid_metrics:
                raise serializers.ValidationError(f"Invalid metric: {metric}")
        
        return value
    
    def validate_output_formats(self, value):
        """Validate output_formats field."""
        valid_formats = ['json', 'csv', 'pdf', 'excel']
        
        if not isinstance(value, list):
            raise serializers.ValidationError("output_formats must be a list")
        
        for format_type in value:
            if format_type not in valid_formats:
                raise serializers.ValidationError(f"Invalid format: {format_type}")
        
        return value


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for GeneratedReport model."""
    
    template_name = serializers.CharField(source='template.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'template', 'template_name', 'name', 'requested_by',
            'requested_by_name', 'status', 'period_start', 'period_end',
            'filters_applied', 'output_format', 'file_path', 'file_size_bytes',
            'generation_time_seconds', 'error_message', 'created_at',
            'completed_at', 'expires_at'
        ]
        read_only_fields = [
            'id', 'status', 'file_path', 'file_size_bytes',
            'generation_time_seconds', 'error_message', 'created_at',
            'completed_at', 'expires_at'
        ]


class ReportGenerationRequestSerializer(serializers.Serializer):
    """Serializer for report generation requests."""
    
    template_id = serializers.UUIDField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    output_format = serializers.ChoiceField(
        choices=['json', 'csv', 'pdf', 'excel'],
        default='pdf'
    )
    filters = serializers.JSONField(required=False, default=dict)
    
    def validate(self, data):
        """Validate report generation request."""
        period_start = data['period_start']
        period_end = data['period_end']
        
        if period_start >= period_end:
            raise serializers.ValidationError("period_start must be before period_end")
        
        # Limit report period to prevent excessive data processing
        max_days = 365
        if (period_end - period_start).days > max_days:
            raise serializers.ValidationError(f"Report period cannot exceed {max_days} days")
        
        return data


class AnalyticsFilterSerializer(serializers.Serializer):
    """Serializer for analytics filters."""
    
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    city = serializers.CharField(required=False, allow_blank=True)
    region = serializers.CharField(required=False, allow_blank=True)
    granularity = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly', 'monthly'],
        default='daily'
    )
    metric_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    
    def validate(self, data):
        """Validate analytics filters."""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("start_date must be before end_date")
        
        # Set default dates if not provided
        if not start_date:
            data['start_date'] = (timezone.now() - timedelta(days=30)).date()
        
        if not end_date:
            data['end_date'] = timezone.now().date()
        
        return data


class ServiceHealthSerializer(serializers.Serializer):
    """Serializer for service health data."""
    
    service_name = serializers.CharField()
    period_hours = serializers.IntegerField()
    overall_health = serializers.DecimalField(max_digits=5, decimal_places=2)
    summary = serializers.DictField()
    
    # Individual metric summaries
    response_time_avg = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    throughput_avg = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    error_rate_avg = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    availability_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class TrendAnalysisSerializer(serializers.Serializer):
    """Serializer for trend analysis data."""
    
    metric_name = serializers.CharField()
    period = serializers.CharField()
    trend_direction = serializers.ChoiceField(choices=['increasing', 'decreasing', 'stable'])
    trend_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    confidence_level = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Statistical data
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    previous_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Forecast (optional)
    forecasted_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    forecast_confidence = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)