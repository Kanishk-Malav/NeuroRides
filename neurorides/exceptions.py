"""
Custom exception classes for NeuroRides platform.
"""

from rest_framework.exceptions import APIException
from rest_framework import status


class NeuroRidesException(Exception):
    """Base exception for NeuroRides platform."""
    pass


class RideBookingError(NeuroRidesException):
    """Raised when ride booking fails."""
    pass


class PaymentProcessingError(NeuroRidesException):
    """Raised when payment processing fails."""
    pass


class DispatchError(NeuroRidesException):
    """Raised when dispatch fails."""
    pass


class VehicleUnavailableError(NeuroRidesException):
    """Raised when no vehicles are available."""
    pass


class InvalidStateTransitionError(NeuroRidesException):
    """Raised when an invalid state transition is attempted."""
    pass


class InsufficientBalanceError(NeuroRidesException):
    """Raised when user has insufficient balance."""
    pass


class GatewayError(NeuroRidesException):
    """Raised when payment gateway returns an error."""
    pass


# DRF API Exceptions

class RideBookingAPIError(APIException):
    """API exception for ride booking errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Ride booking failed.'
    default_code = 'ride_booking_error'


class PaymentAPIError(APIException):
    """API exception for payment errors."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment processing failed.'
    default_code = 'payment_error'


class VehicleUnavailableAPIError(APIException):
    """API exception when no vehicles are available."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'No vehicles available at this time.'
    default_code = 'vehicle_unavailable'


class InvalidStateAPIError(APIException):
    """API exception for invalid state transitions."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Invalid state transition.'
    default_code = 'invalid_state'


class RateLimitExceededError(APIException):
    """API exception for rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded. Please try again later.'
    default_code = 'rate_limit_exceeded'
