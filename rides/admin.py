"""
Admin configuration for rides app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone
from .models import Ride, RideRequest, ServiceArea


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    """Admin interface for Ride model."""
    
    list_display = [
        'id',
        'rider',
        'vehicle_display',
        'status_badge',
        'fare_display',
        'distance_display',
        'duration_display',
        'requested_at',
    ]
    
    list_filter = [
        'status',
        'requires_wheelchair_access',
        'requires_child_seat',
        'requested_at',
        'completed_at',
    ]
    
    search_fields = [
        'id',
        'rider__username',
        'rider__email',
        'vehicle__license_plate',
        'pickup_address',
        'destination_address',
    ]
    
    readonly_fields = [
        'id',
        'requested_at',
        'assigned_at',
        'pickup_started_at',
        'picked_up_at',
        'completed_at',
        'cancelled_at',
        'duration_display',
        'total_duration_display',
        'distance_calculated',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'id',
                'rider',
                'vehicle',
                'status',
            ]
        }),
        (_('Pickup Location'), {
            'fields': [
                'pickup_latitude',
                'pickup_longitude',
                'pickup_address',
                'pickup_notes',
            ]
        }),
        (_('Destination'), {
            'fields': [
                'destination_latitude',
                'destination_longitude',
                'destination_address',
            ]
        }),
        (_('Ride Details'), {
            'fields': [
                'passenger_count',
                'requires_wheelchair_access',
                'requires_child_seat',
                'ride_notes',
            ]
        }),
        (_('Fare Information'), {
            'fields': [
                'fare_estimate',
                'final_fare',
            ]
        }),
        (_('Distance & Duration'), {
            'fields': [
                'estimated_distance_km',
                'actual_distance_km',
                'distance_calculated',
                'estimated_duration_minutes',
                'actual_duration_minutes',
                'duration_display',
                'total_duration_display',
            ]
        }),
        (_('Timestamps'), {
            'fields': [
                'requested_at',
                'assigned_at',
                'pickup_started_at',
                'picked_up_at',
                'completed_at',
                'cancelled_at',
            ],
            'classes': ['collapse'],
        }),
        (_('Cancellation'), {
            'fields': [
                'cancellation_reason',
                'cancellation_notes',
            ],
            'classes': ['collapse'],
        }),
        (_('Rating & Feedback'), {
            'fields': [
                'rider_rating',
                'rider_feedback',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    actions = [
        'cancel_selected_rides',
        'complete_selected_rides',
    ]
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'requested': 'blue',
            'assigned': 'orange',
            'pickup': 'purple',
            'in_progress': 'green',
            'completed': 'darkgreen',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def vehicle_display(self, obj):
        """Display vehicle information."""
        if obj.vehicle:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:fleet_vehicle_change', args=[obj.vehicle.id]),
                obj.vehicle.license_plate
            )
        return _('Not assigned')
    vehicle_display.short_description = _('Vehicle')
    
    def fare_display(self, obj):
        """Display fare information."""
        if obj.final_fare:
            return f"₹{obj.final_fare} (Final)"
        return f"₹{obj.fare_estimate} (Estimate)"
    fare_display.short_description = _('Fare')
    
    def distance_display(self, obj):
        """Display distance information."""
        if obj.actual_distance_km:
            return f"{obj.actual_distance_km:.2f} km (Actual)"
        elif obj.estimated_distance_km:
            return f"{obj.estimated_distance_km:.2f} km (Estimate)"
        return _('Unknown')
    distance_display.short_description = _('Distance')
    
    def duration_display(self, obj):
        """Display ride duration."""
        duration = obj.duration
        if duration:
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f} hours"
        return _('Not completed')
    duration_display.short_description = _('Duration')
    
    def total_duration_display(self, obj):
        """Display total duration from request to completion."""
        duration = obj.total_duration
        if duration:
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f} hours"
        return _('Not completed')
    total_duration_display.short_description = _('Total Duration')
    
    def distance_calculated(self, obj):
        """Display calculated straight-line distance."""
        distance = obj.calculate_distance()
        return f"{distance:.2f} km"
    distance_calculated.short_description = _('Calculated Distance')
    
    def cancel_selected_rides(self, request, queryset):
        """Cancel selected rides."""
        count = 0
        for ride in queryset:
            if ride.can_be_cancelled:
                ride.cancel_ride(
                    reason=Ride.CancellationReason.SYSTEM_ERROR,
                    notes='Cancelled by admin',
                    cancelled_by=request.user
                )
                count += 1
        
        self.message_user(
            request,
            f'{count} ride(s) cancelled successfully.'
        )
    cancel_selected_rides.short_description = _('Cancel selected rides')
    
    def complete_selected_rides(self, request, queryset):
        """Complete selected rides (for testing purposes)."""
        count = 0
        for ride in queryset:
            if ride.status == Ride.Status.IN_PROGRESS:
                ride.complete_ride()
                count += 1
        
        self.message_user(
            request,
            f'{count} ride(s) completed successfully.'
        )
    complete_selected_rides.short_description = _('Complete selected rides')


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    """Admin interface for RideRequest model."""
    
    list_display = [
        'id',
        'rider',
        'status_badge',
        'passenger_count',
        'requirements_display',
        'created_at',
        'expires_at',
        'is_expired_badge',
    ]
    
    list_filter = [
        'status',
        'requires_wheelchair_access',
        'requires_child_seat',
        'created_at',
    ]
    
    search_fields = [
        'id',
        'rider__username',
        'rider__email',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'is_expired_badge',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'id',
                'rider',
                'status',
                'matched_ride',
            ]
        }),
        (_('Location'), {
            'fields': [
                'pickup_latitude',
                'pickup_longitude',
                'destination_latitude',
                'destination_longitude',
            ]
        }),
        (_('Requirements'), {
            'fields': [
                'passenger_count',
                'requires_wheelchair_access',
                'requires_child_seat',
            ]
        }),
        (_('Timing'), {
            'fields': [
                'created_at',
                'expires_at',
                'is_expired_badge',
            ]
        }),
    ]
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'pending': 'orange',
            'matched': 'green',
            'expired': 'red',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def requirements_display(self, obj):
        """Display special requirements."""
        requirements = []
        if obj.requires_wheelchair_access:
            requirements.append('♿ Wheelchair')
        if obj.requires_child_seat:
            requirements.append('👶 Child Seat')
        return ', '.join(requirements) if requirements else _('None')
    requirements_display.short_description = _('Requirements')
    
    def is_expired_badge(self, obj):
        """Display expiration status."""
        if obj.is_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Expired</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
    is_expired_badge.short_description = _('Expiration Status')


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    """Admin interface for ServiceArea model."""
    
    list_display = [
        'name',
        'is_active_badge',
        'surge_multiplier',
        'bounds_display',
        'created_at',
    ]
    
    list_filter = [
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'description',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'name',
                'description',
                'is_active',
            ]
        }),
        (_('Geographic Bounds'), {
            'fields': [
                'north_lat',
                'south_lat',
                'east_lng',
                'west_lng',
            ]
        }),
        (_('Service Configuration'), {
            'fields': [
                'surge_multiplier',
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
    
    def is_active_badge(self, obj):
        """Display active status badge."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Inactive</span>'
            )
    is_active_badge.short_description = _('Status')
    
    def bounds_display(self, obj):
        """Display geographic bounds."""
        return f"N:{obj.north_lat:.4f} S:{obj.south_lat:.4f} E:{obj.east_lng:.4f} W:{obj.west_lng:.4f}"
    bounds_display.short_description = _('Bounds')