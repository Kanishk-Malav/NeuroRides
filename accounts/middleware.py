"""
Custom middleware for security and logging.
"""

import json
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('neurorides')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses."""
    
    def process_response(self, request, response):
        """Add security headers."""
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Remove server information
        if 'Server' in response:
            del response['Server']
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Enhanced request/response logging middleware."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_logger = logging.getLogger('neurorides.api')
        self.performance_logger = logging.getLogger('neurorides.performance')
        super().__init__(get_response)
    
    def process_request(self, request):
        """Log incoming request with detailed information."""
        request.start_time = time.time()
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        request.client_ip = ip
        
        # Prepare request data for logging
        request_data = {
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'client_ip': ip,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'content_type': request.META.get('CONTENT_TYPE', ''),
            'content_length': request.META.get('CONTENT_LENGTH', 0),
            'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
            'username': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous',
            'session_key': request.session.session_key if hasattr(request, 'session') else None,
        }
        
        # Log request body for POST/PUT/PATCH (excluding sensitive data)
        if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
            try:
                body = json.loads(request.body.decode('utf-8'))
                # Remove sensitive fields
                sensitive_fields = ['password', 'token', 'secret', 'key', 'cvv', 'card_number']
                filtered_body = self._filter_sensitive_data(body, sensitive_fields)
                request_data['body'] = filtered_body
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data['body'] = '[Non-JSON body]'
        
        # Log the request
        self.api_logger.info(
            f"Incoming request: {request.method} {request.path}",
            extra=request_data
        )
    
    def process_response(self, request, response):
        """Log response with performance metrics."""
        if hasattr(request, 'start_time'):
            duration_ms = (time.time() - request.start_time) * 1000
            
            # Prepare response data for logging
            response_data = {
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2),
                'content_type': response.get('Content-Type', ''),
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
            }
            
            # Add request context
            if hasattr(request, 'client_ip'):
                response_data.update({
                    'method': request.method,
                    'path': request.path,
                    'client_ip': request.client_ip,
                    'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                })
            
            # Log response
            if response.status_code >= 500:
                self.api_logger.error(
                    f"Server error: {request.method} {request.path} - {response.status_code}",
                    extra=response_data
                )
            elif response.status_code >= 400:
                self.api_logger.warning(
                    f"Client error: {request.method} {request.path} - {response.status_code}",
                    extra=response_data
                )
            else:
                self.api_logger.info(
                    f"Response: {request.method} {request.path} - {response.status_code} ({duration_ms:.2f}ms)",
                    extra=response_data
                )
            
            # Log performance metrics for slow requests
            if duration_ms > 1000:  # Log requests taking more than 1 second
                self.performance_logger.warning(
                    f"Slow request detected: {request.method} {request.path} took {duration_ms:.2f}ms",
                    extra=response_data
                )
        
        return response
    
    def process_exception(self, request, exception):
        """Log unhandled exceptions."""
        if hasattr(request, 'start_time'):
            duration_ms = (time.time() - request.start_time) * 1000
            
            exception_data = {
                'method': request.method,
                'path': request.path,
                'client_ip': getattr(request, 'client_ip', 'unknown'),
                'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                'duration_ms': round(duration_ms, 2),
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
            }
            
            self.api_logger.error(
                f"Unhandled exception in {request.method} {request.path}: {type(exception).__name__}",
                exc_info=True,
                extra=exception_data
            )
    
    def _filter_sensitive_data(self, data, sensitive_fields):
        """Recursively filter sensitive data from request body."""
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                    filtered[key] = '[FILTERED]'
                elif isinstance(value, (dict, list)):
                    filtered[key] = self._filter_sensitive_data(value, sensitive_fields)
                else:
                    filtered[key] = value
            return filtered
        elif isinstance(data, list):
            return [self._filter_sensitive_data(item, sensitive_fields) for item in data]
        else:
            return data


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware."""
    
    def process_request(self, request):
        """Check rate limits."""
        # Skip rate limiting for certain paths
        skip_paths = ['/admin/', '/api/schema/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Get client IP
        client_ip = getattr(request, 'client_ip', self.get_client_ip(request))
        
        # Different rate limits for different endpoints
        rate_limits = {
            '/api/accounts/auth/login/': (5, 300),  # 5 attempts per 5 minutes
            '/api/accounts/auth/register/': (3, 3600),  # 3 attempts per hour
            '/api/accounts/auth/send-phone-verification/': (3, 300),  # 3 per 5 minutes
            'default': (100, 3600),  # 100 requests per hour for other endpoints
        }
        
        # Get rate limit for current path
        limit, window = rate_limits.get(request.path, rate_limits['default'])
        
        # Create cache key
        cache_key = f"rate_limit:{client_ip}:{request.path}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': window
            }, status=429)
        
        # Increment counter
        cache.set(cache_key, current_count + 1, window)
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class APIVersionMiddleware(MiddlewareMixin):
    """Add API version to responses."""
    
    def process_response(self, request, response):
        """Add API version header."""
        if request.path.startswith('/api/'):
            response['API-Version'] = '1.0'
        return response


class CORSMiddleware(MiddlewareMixin):
    """Custom CORS middleware for WebSocket support."""
    
    def process_response(self, request, response):
        """Add CORS headers."""
        if request.path.startswith('/ws/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response