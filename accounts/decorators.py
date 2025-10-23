"""
Custom decorators for security and rate limiting.
"""

import functools
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from rest_framework import status


def rate_limit(requests_per_minute=60, per_ip=True, per_user=False):
    """
    Rate limiting decorator.
    
    Args:
        requests_per_minute: Number of requests allowed per minute
        per_ip: Apply rate limit per IP address
        per_user: Apply rate limit per authenticated user
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            key_parts = ['rate_limit']
            
            if per_ip:
                # Get client IP
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                else:
                    ip = request.META.get('REMOTE_ADDR')
                key_parts.append(f"ip:{ip}")
            
            if per_user and request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")
            
            key_parts.append(request.path)
            cache_key = ':'.join(key_parts)
            
            # Check current count
            current_count = cache.get(cache_key, 0)
            
            if current_count >= requests_per_minute:
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.',
                    'retry_after': 60
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Increment counter
            cache.set(cache_key, current_count + 1, 60)  # 60 seconds window
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_verification(view_func):
    """Decorator to require email/phone verification."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_verified:
            return JsonResponse({
                'error': 'Account verification required.',
                'code': 'VERIFICATION_REQUIRED'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def role_required(*roles):
    """Decorator to require specific user roles."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required.'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role not in roles:
                return JsonResponse({
                    'error': 'Insufficient permissions.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitMixin:
    """Mixin for class-based views to add rate limiting."""
    
    rate_limit_requests = 60  # requests per minute
    rate_limit_per_ip = True
    rate_limit_per_user = False
    
    @method_decorator(rate_limit)
    def dispatch(self, request, *args, **kwargs):
        """Apply rate limiting to dispatch method."""
        return super().dispatch(request, *args, **kwargs)


class VerificationRequiredMixin:
    """Mixin to require account verification."""
    
    @method_decorator(require_verification)
    def dispatch(self, request, *args, **kwargs):
        """Apply verification requirement to dispatch method."""
        return super().dispatch(request, *args, **kwargs)


def log_security_event(event_type, user=None, ip_address=None, details=None):
    """Log security-related events."""
    import logging
    
    logger = logging.getLogger('neurorides.security')
    
    log_data = {
        'event_type': event_type,
        'user': str(user) if user else 'Anonymous',
        'ip_address': ip_address,
        'details': details or {}
    }
    
    logger.warning(f"Security Event: {log_data}")


def secure_api_view(rate_limit_rpm=60, require_auth=True, require_verified=False, allowed_roles=None):
    """
    Comprehensive security decorator for API views.
    
    Args:
        rate_limit_rpm: Rate limit requests per minute
        require_auth: Require authentication
        require_verified: Require account verification
        allowed_roles: List of allowed user roles
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Rate limiting
            if rate_limit_rpm:
                rate_limit_decorator = rate_limit(rate_limit_rpm)
                rate_limited_view = rate_limit_decorator(view_func)
                
                # Check rate limit
                cache_key = f"rate_limit:ip:{request.META.get('REMOTE_ADDR')}:{request.path}"
                current_count = cache.get(cache_key, 0)
                
                if current_count >= rate_limit_rpm:
                    log_security_event(
                        'RATE_LIMIT_EXCEEDED',
                        user=request.user if request.user.is_authenticated else None,
                        ip_address=request.META.get('REMOTE_ADDR'),
                        details={'path': request.path, 'count': current_count}
                    )
                    return JsonResponse({
                        'error': 'Rate limit exceeded.'
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Authentication check
            if require_auth and not request.user.is_authenticated:
                log_security_event(
                    'UNAUTHORIZED_ACCESS_ATTEMPT',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details={'path': request.path}
                )
                return JsonResponse({
                    'error': 'Authentication required.'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Verification check
            if require_verified and request.user.is_authenticated and not request.user.is_verified:
                return JsonResponse({
                    'error': 'Account verification required.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Role check
            if allowed_roles and request.user.is_authenticated:
                if request.user.role not in allowed_roles:
                    log_security_event(
                        'INSUFFICIENT_PERMISSIONS',
                        user=request.user,
                        ip_address=request.META.get('REMOTE_ADDR'),
                        details={'path': request.path, 'required_roles': allowed_roles}
                    )
                    return JsonResponse({
                        'error': 'Insufficient permissions.'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator