"""
Admin configuration for payments app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone

from .models import PaymentGateway, PaymentMethod, Payment, PaymentRefund, PaymentAuditLog


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    """Admin interface for PaymentGateway model."""
    
    list_display = [
        'name',
        'gateway_type',
        'is_active_badge',
        'is_sandbox_badge',
        'supported_currencies_display',
        'updated_at',
    ]
    
    list_filter = [
        'gateway_type',
        'is_active',
        'is_sandbox',
        'created_at',
    ]
    
    search_fields = [
        'name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': [
                'name',
                'gateway_type',
                'is_active',
                'is_sandbox',
            ]
        }),
        (_('Configuration'), {
            'fields': [
                'supported_currencies',
                'configuration',
            ]
        }),
        (_('API Credentials'), {
            'fields': [
                'api_key',
                'api_secret',
                'webhook_secret',
            ],
            'classes': ['collapse'],
            'description': 'API credentials are encrypted when stored.',
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
    
    def is_sandbox_badge(self, obj):
        """Display sandbox status badge."""
        if obj.is_sandbox:
            return format_html(
                '<span style="color: orange; font-weight: bold;">🧪 Sandbox</span>'
            )
        else:
            return format_html(
                '<span style="color: blue; font-weight: bold;">🏭 Production</span>'
            )
    is_sandbox_badge.short_description = _('Environment')
    
    def supported_currencies_display(self, obj):
        """Display supported currencies."""
        if obj.supported_currencies:
            return ', '.join(obj.supported_currencies[:5])  # Show first 5
        return _('None configured')
    supported_currencies_display.short_description = _('Currencies')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Admin interface for PaymentMethod model."""
    
    list_display = [
        'user_link',
        'method_display',
        'gateway',
        'is_default_badge',
        'is_active_badge',
        'created_at',
    ]
    
    list_filter = [
        'method_type',
        'gateway',
        'is_default',
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'card_last_four',
        'gateway_method_id',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        (_('User Information'), {
            'fields': [
                'user',
            ]
        }),
        (_('Payment Method Details'), {
            'fields': [
                'method_type',
                'gateway',
                'gateway_method_id',
            ]
        }),
        (_('Card Information'), {
            'fields': [
                'card_last_four',
                'card_brand',
                'card_exp_month',
                'card_exp_year',
            ],
            'classes': ['collapse'],
        }),
        (_('Status'), {
            'fields': [
                'is_default',
                'is_active',
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
    
    def user_link(self, obj):
        """Display user as link."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:accounts_user_change', args=[obj.user.id]),
            obj.user.username
        )
    user_link.short_description = _('User')
    
    def method_display(self, obj):
        """Display payment method information."""
        if obj.method_type == PaymentMethod.MethodType.CARD:
            return f"{obj.card_brand} ****{obj.card_last_four}"
        return obj.get_method_type_display()
    method_display.short_description = _('Method')
    
    def is_default_badge(self, obj):
        """Display default status badge."""
        if obj.is_default:
            return format_html(
                '<span style="color: blue; font-weight: bold;">⭐ Default</span>'
            )
        return ''
    is_default_badge.short_description = _('Default')
    
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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment model."""
    
    list_display = [
        'id',
        'user_link',
        'ride_link',
        'amount_display',
        'status_badge',
        'gateway',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'payment_type',
        'gateway',
        'currency',
        'created_at',
    ]
    
    search_fields = [
        'id',
        'user__username',
        'user__email',
        'ride__id',
        'gateway_transaction_id',
        'gateway_payment_intent_id',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'processed_at',
    ]
    
    fieldsets = [
        (_('Payment Information'), {
            'fields': [
                'id',
                'user',
                'ride',
                'payment_method',
            ]
        }),
        (_('Payment Details'), {
            'fields': [
                'payment_type',
                'status',
                'amount',
                'currency',
            ]
        }),
        (_('Gateway Information'), {
            'fields': [
                'gateway',
                'gateway_transaction_id',
                'gateway_payment_intent_id',
            ]
        }),
        (_('Timestamps'), {
            'fields': [
                'created_at',
                'updated_at',
                'processed_at',
            ]
        }),
        (_('Additional Information'), {
            'fields': [
                'metadata',
                'failure_reason',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    def user_link(self, obj):
        """Display user as link."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:accounts_user_change', args=[obj.user.id]),
            obj.user.username
        )
    user_link.short_description = _('User')
    
    def ride_link(self, obj):
        """Display ride as link."""
        if obj.ride:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:rides_ride_change', args=[obj.ride.id]),
                f"Ride {obj.ride.id}"
            )
        return _('No ride')
    ride_link.short_description = _('Ride')
    
    def amount_display(self, obj):
        """Display amount with currency."""
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = _('Amount')
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple',
            'partially_refunded': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')


@admin.register(PaymentRefund)
class PaymentRefundAdmin(admin.ModelAdmin):
    """Admin interface for PaymentRefund model."""
    
    list_display = [
        'id',
        'payment_link',
        'amount_display',
        'reason_display',
        'status_badge',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'reason',
        'created_at',
    ]
    
    search_fields = [
        'id',
        'payment__id',
        'payment__user__username',
        'gateway_refund_id',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'processed_at',
    ]
    
    fieldsets = [
        (_('Refund Information'), {
            'fields': [
                'id',
                'payment',
                'amount',
                'reason',
                'status',
            ]
        }),
        (_('Gateway Information'), {
            'fields': [
                'gateway_refund_id',
            ]
        }),
        (_('Timestamps'), {
            'fields': [
                'created_at',
                'updated_at',
                'processed_at',
            ]
        }),
        (_('Additional Information'), {
            'fields': [
                'notes',
                'metadata',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    def payment_link(self, obj):
        """Display payment as link."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:payments_payment_change', args=[obj.payment.id]),
            f"Payment {obj.payment.id}"
        )
    payment_link.short_description = _('Payment')
    
    def amount_display(self, obj):
        """Display amount with currency."""
        return f"{obj.amount} {obj.payment.currency}"
    amount_display.short_description = _('Amount')
    
    def reason_display(self, obj):
        """Display refund reason."""
        return obj.get_reason_display()
    reason_display.short_description = _('Reason')
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')


@admin.register(PaymentAuditLog)
class PaymentAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for PaymentAuditLog model."""
    
    list_display = [
        'id',
        'payment_link',
        'user_link',
        'action_display',
        'created_at',
    ]
    
    list_filter = [
        'action',
        'created_at',
    ]
    
    search_fields = [
        'payment__id',
        'user__username',
        'description',
    ]
    
    readonly_fields = [
        'id',
        'payment',
        'user',
        'action',
        'description',
        'request_data',
        'response_data',
        'ip_address',
        'user_agent',
        'created_at',
    ]
    
    fieldsets = [
        (_('Audit Information'), {
            'fields': [
                'id',
                'payment',
                'user',
                'action',
                'description',
            ]
        }),
        (_('Request/Response Data'), {
            'fields': [
                'request_data',
                'response_data',
            ],
            'classes': ['collapse'],
        }),
        (_('Client Information'), {
            'fields': [
                'ip_address',
                'user_agent',
            ],
            'classes': ['collapse'],
        }),
        (_('Timestamp'), {
            'fields': [
                'created_at',
            ]
        }),
    ]
    
    def payment_link(self, obj):
        """Display payment as link."""
        if obj.payment:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:payments_payment_change', args=[obj.payment.id]),
                f"Payment {obj.payment.id}"
            )
        return _('No payment')
    payment_link.short_description = _('Payment')
    
    def user_link(self, obj):
        """Display user as link."""
        if obj.user:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:accounts_user_change', args=[obj.user.id]),
                obj.user.username
            )
        return _('System')
    user_link.short_description = _('User')
    
    def action_display(self, obj):
        """Display action with color coding."""
        colors = {
            'payment_created': 'blue',
            'payment_processed': 'green',
            'payment_failed': 'red',
            'payment_cancelled': 'orange',
            'refund_initiated': 'purple',
            'refund_processed': 'purple',
            'webhook_received': 'gray',
            'error_occurred': 'red',
        }
        color = colors.get(obj.action, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_display.short_description = _('Action')
    
    def has_add_permission(self, request):
        """Disable adding audit logs through admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing audit logs through admin."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deleting audit logs through admin."""
        return False