"""
Admin configuration for analytics app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Sum, Avg, Count

from .models import (
    AnalyticsMetric, RideAnalytics, RevenueAnalytics, 
    FleetAnalytics, UserAnalytics, PerformanceMetric,
    ReportTemplate, GeneratedReport
)


@admin.register(RideAnalytics)
class RideAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for RideAnalytics model."""
    
    list_display = [
        'date', 'hour_display', 'total_rides', 'completed_rides',
        'completion_rate_display', 'avg_distance_km', 'avg_duration_minutes',
        'city', 'is_peak_hour'
    ]
    list_filter = [
        'date', 'is_peak_hour', 'city', 'region'
    ]
    search_fields = ['city', 'region']
    readonly_fields = [
        'completion_rate', 'cancellation_rate', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    
    fieldsets = [
        (_('Time Period'), {
            'fields': ['date', 'hour', 'city', 'region', 'is_peak_hour']
        }),
        (_('Ride Metrics'), {
            'fields': [
                'total_rides', 'completed_rides', 'cancelled_rides', 'failed_rides',
                'completion_rate', 'cancellation_rate'
            ]
        }),
        (_('Distance & Duration'), {
            'fields': [
                'total_distance_km', 'avg_distance_km',
                'total_duration_minutes', 'avg_duration_minutes'
            ]
        }),
        (_('Wait Times'), {
            'fields': ['avg_wait_time_minutes', 'max_wait_time_minutes']
        }),
        (_('Surge Pricing'), {
            'fields': ['surge_multiplier_avg']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def hour_display(self, obj):
        """Display hour in readable format."""
        if obj.hour is not None:
            return f"{obj.hour:02d}:00"
        return "Daily"
    hour_display.short_description = _('Hour')
    
    def completion_rate_display(self, obj):
        """Display completion rate with color coding."""
        rate = float(obj.completion_rate)
        if rate >= 90:
            color = 'green'
        elif rate >= 80:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    completion_rate_display.short_description = _('Completion Rate')


@admin.register(RevenueAnalytics)
class RevenueAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for RevenueAnalytics model."""
    
    list_display = [
        'date', 'hour_display', 'total_revenue_display', 'net_revenue_display',
        'total_transactions', 'success_rate_display', 'avg_transaction_value',
        'city'
    ]
    list_filter = [
        'date', 'city', 'region'
    ]
    search_fields = ['city', 'region']
    readonly_fields = [
        'transaction_success_rate', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    
    fieldsets = [
        (_('Time Period'), {
            'fields': ['date', 'hour', 'city', 'region']
        }),
        (_('Revenue Metrics'), {
            'fields': [
                'total_revenue', 'gross_revenue', 'net_revenue',
                'avg_transaction_value', 'avg_ride_fare'
            ]
        }),
        (_('Revenue Breakdown'), {
            'fields': [
                'base_fare_revenue', 'distance_fare_revenue', 'time_fare_revenue',
                'surge_revenue', 'tip_revenue', 'booking_fees'
            ]
        }),
        (_('Adjustments'), {
            'fields': ['tax_amount', 'discount_amount', 'refund_amount']
        }),
        (_('Transactions'), {
            'fields': [
                'total_transactions', 'successful_transactions', 'failed_transactions',
                'transaction_success_rate'
            ]
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def hour_display(self, obj):
        """Display hour in readable format."""
        if obj.hour is not None:
            return f"{obj.hour:02d}:00"
        return "Daily"
    hour_display.short_description = _('Hour')
    
    def total_revenue_display(self, obj):
        """Display total revenue formatted."""
        return format_html(
            '<span style="color: green; font-weight: bold;">${:,.2f}</span>',
            obj.total_revenue
        )
    total_revenue_display.short_description = _('Total Revenue')
    
    def net_revenue_display(self, obj):
        """Display net revenue formatted."""
        return format_html('${:,.2f}', obj.net_revenue)
    net_revenue_display.short_description = _('Net Revenue')
    
    def success_rate_display(self, obj):
        """Display transaction success rate with color coding."""
        rate = float(obj.transaction_success_rate)
        if rate >= 95:
            color = 'green'
        elif rate >= 90:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    success_rate_display.short_description = _('Success Rate')


@admin.register(FleetAnalytics)
class FleetAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for FleetAnalytics model."""
    
    list_display = [
        'date', 'hour_display', 'total_vehicles', 'active_vehicles',
        'utilization_rate_display', 'avg_rides_per_vehicle',
        'avg_response_time_minutes', 'city'
    ]
    list_filter = [
        'date', 'city', 'region'
    ]
    search_fields = ['city', 'region']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = [
        (_('Time Period'), {
            'fields': ['date', 'hour', 'city', 'region']
        }),
        (_('Fleet Size'), {
            'fields': [
                'total_vehicles', 'active_vehicles', 'idle_vehicles',
                'maintenance_vehicles'
            ]
        }),
        (_('Utilization'), {
            'fields': [
                'utilization_rate', 'avg_rides_per_vehicle', 'avg_revenue_per_vehicle'
            ]
        }),
        (_('Distance & Efficiency'), {
            'fields': [
                'total_distance_driven', 'avg_distance_per_vehicle', 'fuel_efficiency_avg'
            ]
        }),
        (_('Maintenance'), {
            'fields': [
                'vehicles_due_maintenance', 'maintenance_cost', 'downtime_hours'
            ]
        }),
        (_('Performance'), {
            'fields': ['avg_response_time_minutes', 'customer_rating_avg']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def hour_display(self, obj):
        """Display hour in readable format."""
        if obj.hour is not None:
            return f"{obj.hour:02d}:00"
        return "Daily"
    hour_display.short_description = _('Hour')
    
    def utilization_rate_display(self, obj):
        """Display utilization rate with color coding."""
        rate = float(obj.utilization_rate)
        if rate >= 80:
            color = 'green'
        elif rate >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    utilization_rate_display.short_description = _('Utilization Rate')


@admin.register(UserAnalytics)
class UserAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for UserAnalytics model."""
    
    list_display = [
        'date', 'hour_display', 'total_users', 'active_users',
        'new_users', 'retention_rate_display', 'avg_rides_per_user',
        'avg_spend_per_user', 'city'
    ]
    list_filter = [
        'date', 'city', 'region'
    ]
    search_fields = ['city', 'region']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = [
        (_('Time Period'), {
            'fields': ['date', 'hour', 'city', 'region']
        }),
        (_('User Counts'), {
            'fields': [
                'total_users', 'new_users', 'active_users', 'returning_users'
            ]
        }),
        (_('Engagement'), {
            'fields': [
                'avg_rides_per_user', 'avg_spend_per_user', 'user_retention_rate'
            ]
        }),
        (_('Satisfaction'), {
            'fields': ['avg_rating_given', 'complaint_rate']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def hour_display(self, obj):
        """Display hour in readable format."""
        if obj.hour is not None:
            return f"{obj.hour:02d}:00"
        return "Daily"
    hour_display.short_description = _('Hour')
    
    def retention_rate_display(self, obj):
        """Display retention rate with color coding."""
        rate = float(obj.user_retention_rate)
        if rate >= 70:
            color = 'green'
        elif rate >= 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    retention_rate_display.short_description = _('Retention Rate')


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceMetric model."""
    
    list_display = [
        'timestamp', 'service_name', 'metric_name', 'value_display',
        'unit', 'health_status', 'category'
    ]
    list_filter = [
        'category', 'service_name', 'is_healthy', 'timestamp'
    ]
    search_fields = ['service_name', 'metric_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'
    
    fieldsets = [
        (_('Metric Information'), {
            'fields': [
                'category', 'metric_name', 'service_name', 'timestamp'
            ]
        }),
        (_('Values'), {
            'fields': [
                'value', 'unit', 'warning_threshold', 'critical_threshold'
            ]
        }),
        (_('Status'), {
            'fields': ['is_healthy', 'alert_sent']
        }),
        (_('Metadata'), {
            'fields': ['metadata'],
            'classes': ['collapse']
        }),
        (_('Timestamps'), {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]
    
    def value_display(self, obj):
        """Display value with color coding based on health."""
        color = 'green' if obj.is_healthy else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.value
        )
    value_display.short_description = _('Value')
    
    def health_status(self, obj):
        """Display health status with icon."""
        if obj.is_healthy:
            return format_html(
                '<span style="color: green;">✓ Healthy</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Unhealthy</span>'
            )
    health_status.short_description = _('Health Status')


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """Admin interface for ReportTemplate model."""
    
    list_display = [
        'name', 'report_type', 'created_by', 'is_public',
        'is_scheduled', 'metrics_count', 'created_at'
    ]
    list_filter = [
        'report_type', 'is_public', 'is_scheduled', 'created_at'
    ]
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': ['name', 'description', 'report_type']
        }),
        (_('Configuration'), {
            'fields': ['metrics_included', 'filters', 'grouping', 'output_formats']
        }),
        (_('Access Control'), {
            'fields': ['created_by', 'is_public', 'allowed_roles']
        }),
        (_('Scheduling'), {
            'fields': ['is_scheduled', 'schedule_cron']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def metrics_count(self, obj):
        """Display number of metrics included."""
        return len(obj.metrics_included) if obj.metrics_included else 0
    metrics_count.short_description = _('Metrics Count')


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    """Admin interface for GeneratedReport model."""
    
    list_display = [
        'name', 'template_name', 'requested_by', 'status_display',
        'output_format', 'file_size_display', 'created_at'
    ]
    list_filter = [
        'status', 'output_format', 'created_at', 'completed_at'
    ]
    search_fields = ['name', 'template__name', 'requested_by__username']
    readonly_fields = [
        'created_at', 'completed_at', 'expires_at', 'generation_time_seconds'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = [
        (_('Report Information'), {
            'fields': [
                'template', 'name', 'requested_by', 'status'
            ]
        }),
        (_('Period'), {
            'fields': ['period_start', 'period_end']
        }),
        (_('Configuration'), {
            'fields': ['filters_applied', 'output_format']
        }),
        (_('Output'), {
            'fields': [
                'file_path', 'file_size_bytes', 'generation_time_seconds'
            ]
        }),
        (_('Error Information'), {
            'fields': ['error_message'],
            'classes': ['collapse']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'completed_at', 'expires_at'],
            'classes': ['collapse']
        }),
    ]
    
    def template_name(self, obj):
        """Display template name."""
        return obj.template.name
    template_name.short_description = _('Template')
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'orange',
            'generating': 'blue',
            'completed': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_display.short_description = _('Status')
    
    def file_size_display(self, obj):
        """Display file size in human readable format."""
        if obj.file_size_bytes:
            if obj.file_size_bytes < 1024:
                return f"{obj.file_size_bytes} B"
            elif obj.file_size_bytes < 1024 * 1024:
                return f"{obj.file_size_bytes / 1024:.1f} KB"
            else:
                return f"{obj.file_size_bytes / (1024 * 1024):.1f} MB"
        return "-"
    file_size_display.short_description = _('File Size')


@admin.register(AnalyticsMetric)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    """Admin interface for AnalyticsMetric model."""
    
    list_display = [
        'metric_name', 'metric_type', 'time_granularity',
        'period_start', 'value', 'count', 'created_at'
    ]
    list_filter = [
        'metric_type', 'time_granularity', 'created_at'
    ]
    search_fields = ['metric_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'period_start'
    
    fieldsets = [
        (_('Metric Information'), {
            'fields': ['metric_type', 'metric_name', 'time_granularity']
        }),
        (_('Time Period'), {
            'fields': ['period_start', 'period_end']
        }),
        (_('Values'), {
            'fields': ['value', 'count']
        }),
        (_('Metadata'), {
            'fields': ['metadata'],
            'classes': ['collapse']
        }),
        (_('Timestamps'), {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
