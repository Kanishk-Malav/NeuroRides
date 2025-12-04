"""
Custom validators for NeuroRides platform.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import re


def validate_latitude(value):
    """Validate latitude is between -90 and 90."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Latitude must be a number.'))
    if value < -90 or value > 90:
        raise ValidationError(_('Latitude must be between -90 and 90.'))


def validate_longitude(value):
    """Validate longitude is between -180 and 180."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Longitude must be a number.'))
    if value < -180 or value > 180:
        raise ValidationError(_('Longitude must be between -180 and 180.'))


def validate_positive_decimal(value):
    """Validate value is a positive decimal."""
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except:
            raise ValidationError(_('Value must be a valid decimal number.'))
    if value <= 0:
        raise ValidationError(_('Value must be positive.'))


def validate_phone_number(value):
    """Validate phone number format."""
    pattern = r'^\+?1?\d{9,15}$'
    if not re.match(pattern, value):
        raise ValidationError(
            _("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
        )


def validate_license_plate(value):
    """Validate license plate format."""
    if not value or len(value) < 2 or len(value) > 20:
        raise ValidationError(_('License plate must be between 2 and 20 characters.'))
    # Allow alphanumeric and hyphens
    if not re.match(r'^[A-Z0-9\-]+$', value.upper()):
        raise ValidationError(_('License plate can only contain letters, numbers, and hyphens.'))


def validate_fare_amount(value):
    """Validate fare amount is reasonable."""
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except:
            raise ValidationError(_('Fare must be a valid decimal number.'))
    
    if value < Decimal('0.01'):
        raise ValidationError(_('Fare must be at least 0.01.'))
    
    if value > Decimal('100000.00'):
        raise ValidationError(_('Fare cannot exceed 100,000.'))


def validate_distance(value):
    """Validate distance is reasonable."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Distance must be a number.'))
    
    if value < 0:
        raise ValidationError(_('Distance cannot be negative.'))
    
    if value > 10000:  # 10,000 km
        raise ValidationError(_('Distance cannot exceed 10,000 km.'))


def validate_duration(value):
    """Validate duration is reasonable."""
    if not isinstance(value, int):
        raise ValidationError(_('Duration must be an integer (minutes).'))
    
    if value < 0:
        raise ValidationError(_('Duration cannot be negative.'))
    
    if value > 1440:  # 24 hours
        raise ValidationError(_('Duration cannot exceed 24 hours (1440 minutes).'))


def validate_battery_level(value):
    """Validate battery level is between 0 and 100."""
    if not isinstance(value, int):
        raise ValidationError(_('Battery level must be an integer.'))
    
    if value < 0 or value > 100:
        raise ValidationError(_('Battery level must be between 0 and 100.'))


def validate_rating(value):
    """Validate rating is between 1 and 5."""
    if not isinstance(value, int):
        raise ValidationError(_('Rating must be an integer.'))
    
    if value < 1 or value > 5:
        raise ValidationError(_('Rating must be between 1 and 5.'))


def validate_passenger_count(value):
    """Validate passenger count is reasonable."""
    if not isinstance(value, int):
        raise ValidationError(_('Passenger count must be an integer.'))
    
    if value < 1:
        raise ValidationError(_('Passenger count must be at least 1.'))
    
    if value > 8:
        raise ValidationError(_('Passenger count cannot exceed 8.'))


def validate_card_last_four(value):
    """Validate card last four digits."""
    if not value or len(value) != 4:
        raise ValidationError(_('Card last four must be exactly 4 digits.'))
    
    if not value.isdigit():
        raise ValidationError(_('Card last four must contain only digits.'))


def validate_card_exp_month(value):
    """Validate card expiration month."""
    if not isinstance(value, int):
        raise ValidationError(_('Expiration month must be an integer.'))
    
    if value < 1 or value > 12:
        raise ValidationError(_('Expiration month must be between 1 and 12.'))


def validate_card_exp_year(value):
    """Validate card expiration year."""
    if not isinstance(value, int):
        raise ValidationError(_('Expiration year must be an integer.'))
    
    from datetime import datetime
    current_year = datetime.now().year
    
    if value < current_year:
        raise ValidationError(_('Card has expired.'))
    
    if value > current_year + 20:
        raise ValidationError(_('Expiration year is too far in the future.'))


def validate_currency_code(value):
    """Validate currency code is ISO 4217 format."""
    if not value or len(value) != 3:
        raise ValidationError(_('Currency code must be exactly 3 characters.'))
    
    if not value.isupper():
        raise ValidationError(_('Currency code must be uppercase.'))
    
    # Common currency codes
    valid_codes = ['USD', 'EUR', 'GBP', 'INR', 'JPY', 'CNY', 'AUD', 'CAD']
    if value not in valid_codes:
        raise ValidationError(_(f'Currency code must be one of: {", ".join(valid_codes)}'))


def validate_speed(value):
    """Validate speed is reasonable."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Speed must be a number.'))
    
    if value < 0:
        raise ValidationError(_('Speed cannot be negative.'))
    
    if value > 200:  # 200 km/h
        raise ValidationError(_('Speed cannot exceed 200 km/h.'))


def validate_heading(value):
    """Validate heading is between 0 and 360 degrees."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Heading must be a number.'))
    
    if value < 0 or value > 360:
        raise ValidationError(_('Heading must be between 0 and 360 degrees.'))
