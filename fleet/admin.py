"""
Admin configuration for fleet app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone
from .models import Vehicle, VehicleTelemetry, MaintenanceRecord


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    """Admin interface for Vehicle model."""
    
    list_display = [
        'license_plate',
        'model',
        'status_badge',
        'battery_level_bar',
        'location_display',
        'is_online_badge',
        'total_rides',
        'mileage',
        'last_seen',
    ]
    
    list_filter = [
        'status',
        'vehicle_type',
        'manufacturer',
        'year',
        'has_wheelchair_access',
        'has_child_seat',
        'created_at',
    ]
    
    search_fields = [
        'license_plate',
        'model',
        'manufacturer',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'last_seen',
        'total_rides',
        'total_revenue',
        'is_online_badge',
        'needs_maintenance_badge',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'id',
                'license_plate',
                'model',
                'manufacturer',
                'year',
                'vehicle_type',
                'passenger_capacity',
            ]
        }),
        (_('Features'), {
            'fields': [
                'has_wheelchair_access',
                'has_child_seat',
            ]
        }),
        (_('Status & Location'), {
            'fields': [
                'status',
                'current_latitude',
                'current_longitude',
                'battery_level',
                'last_seen',
                'is_online_badge',
            ]
        }),
        (_('Maintenance'), {
            'fields': [
                'last_maintenance',
                'next_maintenance_due',
                'maintenance_mileage_threshold',
                'needs_maintenance_badge',
            ]
        }),
        (_('Metrics'), {
            'fields': [
                'mileage',
                'total_rides',
                'total_revenue',
            ]
        }),
        # (_('Current Assignment'), {
        #     'fields': [
        #         'current_ride',
        #     ]
        # }),
        (_('Timestamps'), {
            'fields': [
                'created_at',
                'updated_at',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    actions = [
        'set_maintenance_mode',
        'set_idle_mode',
        'set_offline_mode',
    ]
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'idle': 'green',
            'assigned': 'blue',
            'in_ride': 'orange',
            'maintenance': 'red',
            'offline': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def battery_level_bar(self, obj):
        """Display battery level as progress bar."""
        color = 'green' if obj.battery_level > 50 else 'orange' if obj.battery_level > 20 else 'red'
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; '
            'text-align: center; color: white; font-size: 12px; line-height: 20px;">'
            '{}%</div></div>',
            obj.battery_level,
            color,
            obj.battery_level
        )
    battery_level_bar.short_description = _('Battery')
    
    def location_display(self, obj):
        """Display current location."""
        if obj.current_location:
            lat, lng = obj.current_location
            return f"{lat:.4f}, {lng:.4f}"
        return _('Unknown')
    location_display.short_description = _('Location')
    
    def is_online_badge(self, obj):
        """Display online status badge."""
        if obj.is_online:
            return format_html(
                '<span style="color: green; font-weight: bold;">● Online</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">● Offline</span>'
            )
    is_online_badge.short_description = _('Connection')
    
    def needs_maintenance_badge(self, obj):
        """Display maintenance status badge."""
        if obj.needs_maintenance:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Maintenance Required</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ OK</span>'
            )
    needs_maintenance_badge.short_description = _('Maintenance Status')
    
    def set_maintenance_mode(self, request, queryset):
        """Set selected vehicles to maintenance mode."""
        count = 0
        for vehicle in queryset:
            if vehicle.status != Vehicle.Status.MAINTENANCE:
                vehicle.set_maintenance_mode()
                count += 1
        
        self.message_user(
            request,
            f'{count} vehicle(s) set to maintenance mode.'
        )
    set_maintenance_mode.short_description = _('Set to maintenance mode')
    
    def set_idle_mode(self, request, queryset):
        """Set selected vehicles to idle mode."""
        count = 0
        for vehicle in queryset:
            if vehicle.status in [Vehicle.Status.OFFLINE, Vehicle.Status.MAINTENANCE]:
                vehicle.status = Vehicle.Status.IDLE
                vehicle.save(update_fields=['status'])
                count += 1
        
        self.message_user(
            request,
            f'{count} vehicle(s) set to idle mode.'
        )
    set_idle_mode.short_description = _('Set to idle mode')
    
    def set_offline_mode(self, request, queryset):
        """Set selected vehicles to offline mode."""
        count = 0
        for vehicle in queryset:
            vehicle.status = Vehicle.Status.OFFLINE
            # vehicle.current_ride = None  # Will be enabled when rides app is implemented
            vehicle.save(update_fields=['status'])
            count += 1
        
        self.message_user(
            request,
            f'{count} vehicle(s) set to offline mode.'
        )
    set_offline_mode.short_description = _('Set to offline mode')


@admin.register(VehicleTelemetry)
class VehicleTelemetryAdmin(admin.ModelAdmin):
    """Admin interface for VehicleTelemetry model."""
    
    list_display = [
        'vehicle',
        'timestamp',
        'location_display',
        'speed',
        'battery_level',
        'engine_status',
        'passenger_count',
    ]
    
    list_filter = [
        'engine_status',
        'timestamp',
        'battery_level',
        'speed',
    ]
    
    search_fields = [
        'vehicle__license_plate',
        'vehicle__model',
    ]
    
    readonly_fields = [
        'timestamp',
    ]
    
    fieldsets = [
        (_('Vehicle'), {
            'fields': ['vehicle']
        }),
        (_('Location'), {
            'fields': [
                'latitude',
                'longitude',
                'speed',
                'heading',
            ]
        }),
        (_('Status'), {
            'fields': [
                'battery_level',
                'engine_status',
                'temperature',
                'passenger_count',
            ]
        }),
        (_('Diagnostics'), {
            'fields': [
                'diagnostic_codes',
            ],
            'classes': ['collapse'],
        }),
        (_('Timestamp'), {
            'fields': ['timestamp']
        }),
    ]
    
    def location_display(self, obj):
        """Display location coordinates."""
        return f"{obj.latitude:.4f}, {obj.longitude:.4f}"
    location_display.short_description = _('Location')
    
    def has_add_permission(self, request):
        """Disable manual addition of telemetry data."""
        return False


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    """Admin interface for MaintenanceRecord model."""
    
    list_display = [
        'vehicle',
        'maintenance_type',
        'status_badge',
        'scheduled_date',
        'technician',
        'estimated_cost',
        'actual_cost',
        'is_overdue_badge',
    ]
    
    list_filter = [
        'maintenance_type',
        'status',
        'scheduled_date',
        'created_at',
    ]
    
    search_fields = [
        'vehicle__license_plate',
        'vehicle__model',
        'description',
        'technician__username',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'duration_display',
        'is_overdue_badge',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'vehicle',
                'maintenance_type',
                'status',
                'technician',
            ]
        }),
        (_('Scheduling'), {
            'fields': [
                'scheduled_date',
                'started_at',
                'completed_at',
                'duration_display',
                'is_overdue_badge',
            ]
        }),
        (_('Details'), {
            'fields': [
                'description',
                'notes',
                'mileage_at_maintenance',
            ]
        }),
        (_('Costs'), {
            'fields': [
                'estimated_cost',
                'actual_cost',
            ]
        }),
        (_('Timestamps'), {
            'fields': [
                'created_at',
                'updated_at',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    actions = [
        'start_maintenance',
        'complete_maintenance',
    ]
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'scheduled': 'blue',
            'in_progress': 'orange',
            'completed': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def is_overdue_badge(self, obj):
        """Display overdue status badge."""
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Overdue</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ On Time</span>'
            )
    is_overdue_badge.short_description = _('Schedule Status')
    
    def duration_display(self, obj):
        """Display maintenance duration."""
        duration = obj.duration
        if duration:
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f} hours"
        return _('Not completed')
    duration_display.short_description = _('Duration')
    
    def start_maintenance(self, request, queryset):
        """Start maintenance for selected records."""
        count = 0
        for record in queryset:
            if record.status == MaintenanceRecord.Status.SCHEDULED:
                record.start_maintenance()
                count += 1
        
        self.message_user(
            request,
            f'{count} maintenance record(s) started.'
        )
    start_maintenance.short_description = _('Start maintenance')
    
    def complete_maintenance(self, request, queryset):
        """Complete maintenance for selected records."""
        count = 0
        for record in queryset:
            if record.status == MaintenanceRecord.Status.IN_PROGRESS:
                record.complete_maintenance()
                count += 1
        
        self.message_user(
            request,
            f'{count} maintenance record(s) completed.'
        )
    complete_maintenance.short_description = _('Complete maintenance')