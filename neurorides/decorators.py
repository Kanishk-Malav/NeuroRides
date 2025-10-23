"""
Logging and monitoring decorators.
"""

import time
import functools
import logging
from django.http import JsonResponse
from django.utils import timezone

from .logging import performance_logger, security_logger, business_logger


def log_api_call(logger_name=None):
    """
    Decorator to log API calls with performance metrics.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            logger = logging.getLogger(logger_name or 'neurorides.api')
            start_time = time.time()
            
            # Log request
            logger.info(
                f"API call started: {request.method} {request.path}",
                extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'method': request.method,
                    'path': request.path,
                    'query_params': dict(request.GET),
                }
            )
            
            try:
                response = view_func(request, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log successful response
                performance_logger.log_api_performance(
                    endpoint=request.path,
                    method=request.method,
                    duration=duration_ms,
                    status_code=response.status_code,
                    user=request.user if request.user.is_authenticated else None
                )
                
                return response
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log error
                logger.error(
                    f"API call failed: {request.method} {request.path} - {str(e)}",
                    exc_info=True,
                    extra={
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'method': request.method,
                        'path': request.path,
                        'duration_ms': duration_ms,
                        'error': str(e),
                    }
                )
                
                raise
        
        return wrapper
    return decorator


def log_business_event(event_type, extract_data=None):
    """
    Decorator to log business events.
    
    Args:
        event_type: Type of business event (e.g., 'ride_created', 'payment_processed')
        extract_data: Function to extract relevant data from request/response
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                response = view_func(request, *args, **kwargs)
                
                # Extract business event data
                event_data = {}
                if extract_data and callable(extract_data):
                    event_data = extract_data(request, response, *args, **kwargs)
                
                # Log business event
                business_logger.logger.info(
                    f"Business event: {event_type}",
                    extra={
                        'event_type': 'business_event',
                        'business_event': event_type,
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'timestamp': timezone.now().isoformat(),
                        'data': event_data,
                    }
                )
                
                return response
                
            except Exception as e:
                # Log failed business event
                business_logger.logger.error(
                    f"Business event failed: {event_type} - {str(e)}",
                    extra={
                        'event_type': 'business_event_failed',
                        'business_event': event_type,
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'error': str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator


def log_security_event(event_type, extract_data=None):
    """
    Decorator to log security-related events.
    
    Args:
        event_type: Type of security event (e.g., 'login_attempt', 'permission_check')
        extract_data: Function to extract relevant security data
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                response = view_func(request, *args, **kwargs)
                
                # Extract security event data
                event_data = {}
                if extract_data and callable(extract_data):
                    event_data = extract_data(request, response, *args, **kwargs)
                
                # Log security event
                security_logger.logger.info(
                    f"Security event: {event_type}",
                    extra={
                        'event_type': 'security_event',
                        'security_event': event_type,
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'ip_address': security_logger._get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'timestamp': timezone.now().isoformat(),
                        'data': event_data,
                    }
                )
                
                return response
                
            except Exception as e:
                # Log security event failure
                security_logger.logger.warning(
                    f"Security event failed: {event_type} - {str(e)}",
                    extra={
                        'event_type': 'security_event_failed',
                        'security_event': event_type,
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'ip_address': security_logger._get_client_ip(request),
                        'error': str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator


def monitor_performance(threshold_ms=1000):
    """
    Decorator to monitor function performance and log slow operations.
    
    Args:
        threshold_ms: Threshold in milliseconds to consider operation as slow
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > threshold_ms:
                    performance_logger.logger.warning(
                        f"Slow operation detected: {func.__name__} took {duration_ms:.2f}ms",
                        extra={
                            'event_type': 'slow_operation',
                            'function_name': func.__name__,
                            'module': func.__module__,
                            'duration_ms': duration_ms,
                            'threshold_ms': threshold_ms,
                        }
                    )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                performance_logger.logger.error(
                    f"Operation failed: {func.__name__} failed after {duration_ms:.2f}ms - {str(e)}",
                    extra={
                        'event_type': 'operation_failed',
                        'function_name': func.__name__,
                        'module': func.__module__,
                        'duration_ms': duration_ms,
                        'error': str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator


def require_permission(permission, log_access=True):
    """
    Decorator to check permissions and log access attempts.
    
    Args:
        permission: Required permission string
        log_access: Whether to log access attempts
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if log_access:
                    security_logger.log_permission_denied(
                        user=None,
                        resource=view_func.__name__,
                        action=permission,
                        request=request
                    )
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            if not request.user.has_perm(permission):
                if log_access:
                    security_logger.log_permission_denied(
                        user=request.user,
                        resource=view_func.__name__,
                        action=permission,
                        request=request
                    )
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            if log_access:
                security_logger.log_data_access(
                    user=request.user,
                    resource_type=view_func.__name__,
                    resource_id=kwargs.get('pk', 'unknown'),
                    action=permission,
                    request=request
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def log_database_queries(threshold_ms=100):
    """
    Decorator to log slow database queries.
    
    Args:
        threshold_ms: Threshold in milliseconds to consider query as slow
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.db import connection
            from django.conf import settings
            
            # Only log in debug mode or if explicitly enabled
            if not (settings.DEBUG or getattr(settings, 'LOG_DB_QUERIES', False)):
                return func(*args, **kwargs)
            
            initial_queries = len(connection.queries)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Get queries executed during function call
                queries = connection.queries[initial_queries:]
                
                for query in queries:
                    query_time = float(query['time']) * 1000
                    if query_time > threshold_ms:
                        performance_logger.log_slow_query(
                            query=query['sql'],
                            duration=query_time
                        )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logging.getLogger('neurorides.database').error(
                    f"Database operation failed in {func.__name__} after {duration_ms:.2f}ms: {str(e)}",
                    extra={
                        'function_name': func.__name__,
                        'module': func.__module__,
                        'duration_ms': duration_ms,
                        'error': str(e),
                    }
                )
                raise
        
        return wrapper
    return decorator