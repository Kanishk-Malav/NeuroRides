"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = (
        'avatar',
        ('address_line_1', 'address_line_2'),
        ('city', 'state', 'postal_code', 'country'),
        'preferred_payment_method',
        ('email_notifications', 'sms_notifications', 'push_notifications'),
        ('emergency_contact_name', 'emergency_contact_phone'),
        'date_of_birth',
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""
    
    inlines = (UserProfileInline,)
    
    # Fields to display in the user list
    list_display = (
        'username',
        'email',
        'phone_number',
        'role',
        'is_verified',
        'is_active',
        'is_staff',
        'created_at',
    )
    
    # Fields to filter by
    list_filter = (
        'role',
        'is_verified',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
    )
    
    # Fields to search
    search_fields = (
        'username',
        'email',
        'phone_number',
        'first_name',
        'last_name',
    )
    
    # Ordering
    ordering = ('-created_at',)
    
    # Fields for add user form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'phone_number',
                'role',
                'password1',
                'password2',
            ),
        }),
    )
    
    # Fields for change user form
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        (_('Personal info'), {
            'fields': (
                'first_name',
                'last_name',
                'email',
                'phone_number',
            )
        }),
        (_('Role & Permissions'), {
            'fields': (
                'role',
                'is_verified',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),
        (_('Verification'), {
            'fields': (
                'email_verification_token',
                'phone_verification_token',
            ),
            'classes': ('collapse',),
        }),
        (_('Important dates'), {
            'fields': (
                'last_login',
                'date_joined',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    # Read-only fields
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_login',
        'date_joined',
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only for non-superusers."""
        readonly_fields = list(self.readonly_fields)
        
        if not request.user.is_superuser:
            readonly_fields.extend([
                'is_superuser',
                'user_permissions',
                'groups',
            ])
        
        return readonly_fields


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for UserProfile model."""
    
    list_display = (
        'user',
        'city',
        'country',
        'preferred_payment_method',
        'email_notifications',
        'created_at',
    )
    
    list_filter = (
        'country',
        'email_notifications',
        'sms_notifications',
        'push_notifications',
        'created_at',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'city',
        'state',
        'country',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Profile Picture'), {
            'fields': ('avatar',)
        }),
        (_('Address'), {
            'fields': (
                ('address_line_1', 'address_line_2'),
                ('city', 'state'),
                ('postal_code', 'country'),
            )
        }),
        (_('Preferences'), {
            'fields': (
                'preferred_payment_method',
                ('email_notifications', 'sms_notifications', 'push_notifications'),
            )
        }),
        (_('Emergency Contact'), {
            'fields': (
                'emergency_contact_name',
                'emergency_contact_phone',
            )
        }),
        (_('Personal Information'), {
            'fields': ('date_of_birth',)
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )