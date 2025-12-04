"""
Custom exception handlers for Django REST Framework.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.db import IntegrityError

from .exceptions import (
    NeuroRidesException,
    RideBookingError,
    PaymentProcessingError,
    DispatchError,
    VehicleUnavailableError,
    InvalidStateTransitionError,
)

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    
    Args:
        exc: The exception instance
        context: The context dict containing view, request, etc.
    
    Returns:
        Response object with error details
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Get the view and request from context
    view = context.get('view', None)
    request = context.get('request', None)
    
    # Log the exception with context
    log_exception(exc, context)
    
    # If DRF handled it, return the response
    if response is not None:
        # Add custom error code to response
        if hasattr(exc, 'default_code'):
            response.data['error_code'] = exc.default_code
        return response
    
    # Handle custom NeuroRides exceptions
    if isinstance(exc, RideBookingError):
        return Response({
            'error': 'Ride booking failed',
            'detail': str(exc),
            'error_code': 'ride_booking_error'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if isinstance(exc, PaymentProcessingError):
        return Response({
            'error': 'Payment processing failed',
            'detail': str(exc),
            'error_code': 'payment_error'
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    if isinstance(exc, DispatchError):
        return Response({
            'error': 'Dispatch failed',
            'detail': str(exc),
            'error_code': 'dispatch_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    if isinstance(exc, VehicleUnavailableError):
        return Response({
            'error': 'No vehicles available',
            'detail': str(exc),
            'error_code': 'vehicle_unavailable'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    if isinstance(exc, InvalidStateTransitionError):
        return Response({
            'error': 'Invalid state transition',
            'detail': str(exc),
            'error_code': 'invalid_state'
        }, status=status.HTTP_409_CONFLICT)
    
    # Handle Django validation errors
    if isinstance(exc, DjangoValidationError):
        return Response({
            'error': 'Validation error',
            'detail': exc.message_dict if hasattr(exc, 'message_dict') else str(exc),
            'error_code': 'validation_error'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle 404 errors
    if isinstance(exc, Http404):
        return Response({
            'error': 'Not found',
            'detail': 'The requested resource was not found.',
            'error_code': 'not_found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Handle database integrity errors
    if isinstance(exc, IntegrityError):
        return Response({
            'error': 'Database integrity error',
            'detail': 'A database constraint was violated.',
            'error_code': 'integrity_error'
        }, status=status.HTTP_409_CONFLICT)
    
    # Handle all other exceptions
    return Response({
        'error': 'Internal server error',
        'detail': 'An unexpected error occurred. Please try again later.',
        'error_code': 'internal_error'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def log_exception(exc, context):
    """
    Log exception with full context.
    
    Args:
        exc: The exception instance
        context: The context dict containing view, request, etc.
    """
    view = context.get('view', None)
    request = context.get('request', None)
    
    # Build log context
    log_context = {
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
    }
    
    if request:
        log_context.update({
            'method': request.method,
            'path': request.path,
            'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
            'ip_address': get_client_ip(request),
        })
    
    if view:
        log_context['view'] = view.__class__.__name__
    
    # Log based on exception type
    if isinstance(exc, (RideBookingError, PaymentProcessingError, VehicleUnavailableError)):
        logger.warning(f"Business logic error: {exc}", extra=log_context)
    elif isinstance(exc, (Http404, DjangoValidationError)):
        logger.info(f"Client error: {exc}", extra=log_context)
    else:
        logger.error(f"Unexpected error: {exc}", extra=log_context, exc_info=True)


def get_client_ip(request):
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
    
    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
