"""
Analytics models for NeuroRides platform.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import JSONField

User = get_user_model()


class AnalyticsMetric(models.Model):
    """Base model for analytics metrics."""
    
    class MetricType(models.TextChoices):
        RIDES = 'rides', 'Rides'
        REVENUE = 'revenue', 'Revenue'
        FLEET = 'fleet', 'Fleet'
        USERS = 'users', 'Users'
        PERFORMANCE = 'performance', 'Performance'
        UTILIZATION = 'utilization', 'Utilization'
    
    class TimeGranularity(models.TextChoices):
        HOURLY = 'hourly', 'Hourly'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_type = models.CharField(max_length=20, choices=MetricType.choices)
    metric_name = models.CharField(max_length=100)
    time_granularity = models.CharField(max_length=10, choices=TimeGranularity.choices)
    
    # Time period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Metric values
    value = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    count = models.PositiveIntegerField(default=0)
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_metric'
        ordering = ['-period_start']
        unique_together = [
            ['metric_type', 'metric_name', 'time_granularity', 'period_start']
        ]
        indexes = [
            models.Index(fields=['metric_type', 'period_start']),
            models.Index(fields=['metric_name', 'period_start']),
            models.Index(fields=['time_granularity', 'period_start']),
        ]
    
    def __str__(self):
        return f"{self.metric_name} ({self.period_start.date()}): {self.value}"


class RideAnalytics(models.Model):
    """Analytics data for rides."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Time period
    date = models.DateField()
    hour = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True, blank=True
    )
    
    # Ride metrics
    total_rides = models.PositiveIntegerField(default=0)
    completed_rides = models.PositiveIntegerField(default=0)
    cancelled_rides = models.PositiveIntegerField(default=0)
    failed_rides = models.PositiveIntegerField(default=0)
    
    # Distance and duration
    total_distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_duration_minutes = models.PositiveIntegerField(default=0)
    avg_distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    avg_duration_minutes = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Wait times
    avg_wait_time_minutes = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    max_wait_time_minutes = models.PositiveIntegerField(default=0)
    
    # Geographic data
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Peak hour indicators
    is_peak_hour = models.BooleanField(default=False)
    surge_multiplier_avg = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_ride_analytics'
        ordering = ['-date', '-hour']
        unique_together = [['date', 'hour', 'city']]
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['city', 'date']),
            models.Index(fields=['is_peak_hour', 'date']),
        ]
    
    def __str__(self):
        time_str = f"{self.date}"
        if self.hour is not None:
            time_str += f" {self.hour:02d}:00"
        return f"Ride Analytics - {time_str}: {self.total_rides} rides"
    
    @property
    def completion_rate(self):
        """Calculate ride completion rate."""
        if self.total_rides == 0:
            return Decimal('0.00')
        return (Decimal(self.completed_rides) / Decimal(self.total_rides)) * 100
    
    @property
    def cancellation_rate(self):
        """Calculate ride cancellation rate."""
        if self.total_rides == 0:
            return Decimal('0.00')
        return (Decimal(self.cancelled_rides) / Decimal(self.total_rides)) * 100


class RevenueAnalytics(models.Model):
    """Analytics data for revenue."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Time period
    date = models.DateField()
    hour = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True, blank=True
    )
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Revenue breakdown
    base_fare_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    distance_fare_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    time_fare_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    surge_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tip_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Fees and adjustments
    booking_fees = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Transaction metrics
    total_transactions = models.PositiveIntegerField(default=0)
    successful_transactions = models.PositiveIntegerField(default=0)
    failed_transactions = models.PositiveIntegerField(default=0)
    
    # Average values
    avg_transaction_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    avg_ride_fare = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Geographic data
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_revenue_analytics'
        ordering = ['-date', '-hour']
        unique_together = [['date', 'hour', 'city']]
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['city', 'date']),
            models.Index(fields=['total_revenue', 'date']),
        ]
    
    def __str__(self):
        time_str = f"{self.date}"
        if self.hour is not None:
            time_str += f" {self.hour:02d}:00"
        return f"Revenue Analytics - {time_str}: ${self.total_revenue}"
    
    @property
    def transaction_success_rate(self):
        """Calculate transaction success rate."""
        if self.total_transactions == 0:
            return Decimal('0.00')
        return (Decimal(self.successful_transactions) / Decimal(self.total_transactions)) * 100


class FleetAnalytics(models.Model):
    """Analytics data for fleet performance."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Time period
    date = models.DateField()
    hour = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True, blank=True
    )
    
    # Fleet size metrics
    total_vehicles = models.PositiveIntegerField(default=0)
    active_vehicles = models.PositiveIntegerField(default=0)
    idle_vehicles = models.PositiveIntegerField(default=0)
    maintenance_vehicles = models.PositiveIntegerField(default=0)
    
    # Utilization metrics
    utilization_rate = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=Decimal('0.00')
    )
    avg_rides_per_vehicle = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    avg_revenue_per_vehicle = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Distance and efficiency
    total_distance_driven = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    avg_distance_per_vehicle = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fuel_efficiency_avg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Maintenance metrics
    vehicles_due_maintenance = models.PositiveIntegerField(default=0)
    maintenance_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    downtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Performance metrics
    avg_response_time_minutes = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    customer_rating_avg = models.DecimalField(
        max_digits=3, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        default=Decimal('0.00')
    )
    
    # Geographic data
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_fleet_analytics'
        ordering = ['-date', '-hour']
        unique_together = [['date', 'hour', 'city']]
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['city', 'date']),
            models.Index(fields=['utilization_rate', 'date']),
        ]
    
    def __str__(self):
        time_str = f"{self.date}"
        if self.hour is not None:
            time_str += f" {self.hour:02d}:00"
        return f"Fleet Analytics - {time_str}: {self.active_vehicles}/{self.total_vehicles} active"


class UserAnalytics(models.Model):
    """Analytics data for user behavior."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Time period
    date = models.DateField()
    hour = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True, blank=True
    )
    
    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    returning_users = models.PositiveIntegerField(default=0)
    
    # Engagement metrics
    avg_rides_per_user = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    avg_spend_per_user = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    user_retention_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=Decimal('0.00')
    )
    
    # Satisfaction metrics
    avg_rating_given = models.DecimalField(
        max_digits=3, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        default=Decimal('0.00')
    )
    complaint_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=Decimal('0.00')
    )
    
    # Geographic data
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_user_analytics'
        ordering = ['-date', '-hour']
        unique_together = [['date', 'hour', 'city']]
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['city', 'date']),
            models.Index(fields=['active_users', 'date']),
        ]
    
    def __str__(self):
        time_str = f"{self.date}"
        if self.hour is not None:
            time_str += f" {self.hour:02d}:00"
        return f"User Analytics - {time_str}: {self.active_users} active users"


class PerformanceMetric(models.Model):
    """System performance metrics."""
    
    class MetricCategory(models.TextChoices):
        RESPONSE_TIME = 'response_time', 'Response Time'
        THROUGHPUT = 'throughput', 'Throughput'
        ERROR_RATE = 'error_rate', 'Error Rate'
        AVAILABILITY = 'availability', 'Availability'
        RESOURCE_USAGE = 'resource_usage', 'Resource Usage'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metric identification
    category = models.CharField(max_length=20, choices=MetricCategory.choices)
    metric_name = models.CharField(max_length=100)
    service_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Time period
    timestamp = models.DateTimeField()
    
    # Metric values
    value = models.DecimalField(max_digits=15, decimal_places=4)
    unit = models.CharField(max_length=20)  # ms, req/s, %, MB, etc.
    
    # Thresholds
    warning_threshold = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Status
    is_healthy = models.BooleanField(default=True)
    alert_sent = models.BooleanField(default=False)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_performance_metric'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['category', 'timestamp']),
            models.Index(fields=['metric_name', 'timestamp']),
            models.Index(fields=['service_name', 'timestamp']),
            models.Index(fields=['is_healthy', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.metric_name}: {self.value} {self.unit} ({self.timestamp})"


class ReportTemplate(models.Model):
    """Templates for generating reports."""
    
    class ReportType(models.TextChoices):
        DASHBOARD = 'dashboard', 'Dashboard'
        SUMMARY = 'summary', 'Summary'
        DETAILED = 'detailed', 'Detailed'
        CUSTOM = 'custom', 'Custom'
    
    class OutputFormat(models.TextChoices):
        JSON = 'json', 'JSON'
        CSV = 'csv', 'CSV'
        PDF = 'pdf', 'PDF'
        EXCEL = 'excel', 'Excel'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Template details
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=ReportType.choices)
    
    # Configuration
    metrics_included = models.JSONField(default=list)  # List of metric types to include
    filters = models.JSONField(default=dict)  # Default filters
    grouping = models.JSONField(default=dict)  # Grouping configuration
    
    # Output settings
    output_formats = models.JSONField(default=list)  # Supported output formats
    
    # Access control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_templates')
    is_public = models.BooleanField(default=False)
    allowed_roles = models.JSONField(default=list)  # List of roles that can use this template
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_cron = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_report_template'
        ordering = ['name']
        indexes = [
            models.Index(fields=['created_by', 'is_public']),
            models.Index(fields=['report_type']),
            models.Index(fields=['is_scheduled']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class GeneratedReport(models.Model):
    """Generated reports and their metadata."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        GENERATING = 'generating', 'Generating'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Report details
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='generated_reports')
    name = models.CharField(max_length=200)
    
    # Generation details
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_reports')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Time range
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Filters applied
    filters_applied = models.JSONField(default=dict)
    
    # Output
    output_format = models.CharField(max_length=20)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)
    
    # Processing details
    generation_time_seconds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'analytics_generated_report'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['requested_by', 'status']),
            models.Index(fields=['template', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
