"""
User models for NeuroRides platform.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Custom user model with role-based access control."""
    
    class Role(models.TextChoices):
        RIDER = 'rider', _('Rider')
        OPERATOR = 'operator', _('Operator')
        ADMIN = 'admin', _('Admin')
    
    # Role field for access control
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RIDER,
        help_text=_('User role determines access permissions')
    )
    
    # Phone number with validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message=_("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        unique=True,
        help_text=_('Phone number for SMS notifications and verification')
    )
    
    # Verification status
    is_verified = models.BooleanField(
        default=False,
        help_text=_('Designates whether this user has verified their email/phone.')
    )
    
    # Email verification token
    email_verification_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_('Token for email verification')
    )
    
    # Phone verification token
    phone_verification_token = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        help_text=_('OTP for phone verification')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Last login tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'accounts_user'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_rider(self):
        """Check if user is a rider."""
        return self.role == self.Role.RIDER
    
    @property
    def is_operator(self):
        """Check if user is an operator."""
        return self.role == self.Role.OPERATOR
    
    @property
    def is_admin_user(self):
        """Check if user is an admin."""
        return self.role == self.Role.ADMIN
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name


class UserProfile(models.Model):
    """Extended user profile information."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Profile image
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        help_text=_('User profile picture')
    )
    
    # Address information
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default='India')
    
    # Preferences
    preferred_payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=_('User preferred payment method')
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text=_('Receive email notifications')
    )
    sms_notifications = models.BooleanField(
        default=True,
        help_text=_('Receive SMS notifications')
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text=_('Receive push notifications')
    )
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=17, blank=True)
    
    # Rider-specific fields
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_userprofile'
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def full_address(self):
        """Return formatted full address."""
        address_parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join([part for part in address_parts if part])
