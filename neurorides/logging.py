"""
Custom logging formatters and utilities for NeuroRides.
"""

import json
import logging
import traceback
from datetime import datetime
from django.conf import settings
from django.utils import timezone


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    """
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'process_id': record.process,
            'thread_id': record.thread,
        }
        
        # Add request information if available
        if hasattr(record, 'request'):
            request = record.request
            log_entry['request'] = {
                'method': getattr(request, 'method', None),
                'path': getattr(request, 'path', None),
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'user_agent': request.META.get('HTTP_USER_AGENT', None) if hasattr(request, 'META') else None,
                'remote_addr': self._get_client_ip(request) if hasattr(request, 'META') else None,
            }
        
        # Add exception information if available
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info),
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info', 'request']:
                log_entry['extra'] = log_entry.get('extra', {})
                log_entry['extra'][key] = value
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityLogger:
    """
    Utility class for security-related logging.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('django.security')
    
    def log_authentication_attempt(self, username, success, request=None, reason=None):
        """Log authentication attempts."""
        extra = {
            'event_type': 'authentication_attempt',
            'username': username,
            'success': success,
            'reason': reason,
        }
        
        if request:
            extra.update({
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            })
        
        if success:
            self.logger.info(f"Successful authentication for user: {username}", extra=extra)
        else:
            self.logger.warning(f"Failed authentication for user: {username} - {reason}", extra=extra)
    
    def log_permission_denied(self, user, resource, action, request=None):
        """Log permission denied events."""
        extra = {
            'event_type': 'permission_denied',
            'user_id': user.id if user and user.is_authenticated else None,
            'username': user.username if user and user.is_authenticated else 'anonymous',
            'resource': resource,
            'action': action,
        }
        
        if request:
            extra.update({
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'method': request.method,
            })
        
        self.logger.warning(f"Permission denied for user {extra['username']} on {resource}:{action}", extra=extra)
    
    def log_suspicious_activity(self, description, user=None, request=None, severity='medium'):
        """Log suspicious activities."""
        extra = {
            'event_type': 'suspicious_activity',
            'description': description,
            'severity': severity,
            'user_id': user.id if user and user.is_authenticated else None,
        }
        
        if request:
            extra.update({
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            })
        
        if severity == 'high':
            self.logger.error(f"High severity suspicious activity: {description}", extra=extra)
        else:
            self.logger.warning(f"Suspicious activity detected: {description}", extra=extra)
    
    def log_data_access(self, user, resource_type, resource_id, action, request=None):
        """Log sensitive data access."""
        extra = {
            'event_type': 'data_access',
            'user_id': user.id if user and user.is_authenticated else None,
            'username': user.username if user and user.is_authenticated else 'anonymous',
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
        }
        
        if request:
            extra.update({
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'method': request.method,
            })
        
        self.logger.info(f"Data access: {action} on {resource_type}:{resource_id} by {extra['username']}", extra=extra)
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PerformanceLogger:
    """
    Utility class for performance-related logging.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('neurorides.performance')
    
    def log_slow_query(self, query, duration, params=None):
        """Log slow database queries."""
        extra = {
            'event_type': 'slow_query',
            'query': query,
            'duration_ms': duration,
            'params': params,
        }
        
        self.logger.warning(f"Slow query detected: {duration}ms", extra=extra)
    
    def log_api_performance(self, endpoint, method, duration, status_code, user=None):
        """Log API endpoint performance."""
        extra = {
            'event_type': 'api_performance',
            'endpoint': endpoint,
            'method': method,
            'duration_ms': duration,
            'status_code': status_code,
            'user_id': user.id if user and user.is_authenticated else None,
        }
        
        if duration > 5000:  # Log slow API calls (>5 seconds)
            self.logger.warning(f"Slow API call: {method} {endpoint} took {duration}ms", extra=extra)
        else:
            self.logger.info(f"API call: {method} {endpoint} - {status_code} ({duration}ms)", extra=extra)
    
    def log_task_performance(self, task_name, duration, success, error=None):
        """Log Celery task performance."""
        extra = {
            'event_type': 'task_performance',
            'task_name': task_name,
            'duration_ms': duration,
            'success': success,
            'error': error,
        }
        
        if success:
            if duration > 30000:  # Log slow tasks (>30 seconds)
                self.logger.warning(f"Slow task: {task_name} took {duration}ms", extra=extra)
            else:
                self.logger.info(f"Task completed: {task_name} ({duration}ms)", extra=extra)
        else:
            self.logger.error(f"Task failed: {task_name} - {error}", extra=extra)
    
    def log_memory_usage(self, component, memory_mb, threshold_mb=500):
        """Log memory usage."""
        extra = {
            'event_type': 'memory_usage',
            'component': component,
            'memory_mb': memory_mb,
            'threshold_mb': threshold_mb,
        }
        
        if memory_mb > threshold_mb:
            self.logger.warning(f"High memory usage in {component}: {memory_mb}MB", extra=extra)
        else:
            self.logger.info(f"Memory usage in {component}: {memory_mb}MB", extra=extra)


class BusinessLogger:
    """
    Utility class for business event logging.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('neurorides.business')
    
    def log_ride_event(self, ride_id, event_type, user_id=None, details=None):
        """Log ride-related business events."""
        extra = {
            'event_type': 'ride_event',
            'ride_id': ride_id,
            'business_event': event_type,
            'user_id': user_id,
            'details': details or {},
        }
        
        self.logger.info(f"Ride event: {event_type} for ride {ride_id}", extra=extra)
    
    def log_payment_event(self, payment_id, event_type, amount=None, user_id=None, details=None):
        """Log payment-related business events."""
        extra = {
            'event_type': 'payment_event',
            'payment_id': payment_id,
            'business_event': event_type,
            'amount': amount,
            'user_id': user_id,
            'details': details or {},
        }
        
        self.logger.info(f"Payment event: {event_type} for payment {payment_id}", extra=extra)
    
    def log_fleet_event(self, vehicle_id, event_type, details=None):
        """Log fleet-related business events."""
        extra = {
            'event_type': 'fleet_event',
            'vehicle_id': vehicle_id,
            'business_event': event_type,
            'details': details or {},
        }
        
        self.logger.info(f"Fleet event: {event_type} for vehicle {vehicle_id}", extra=extra)
    
    def log_user_event(self, user_id, event_type, details=None):
        """Log user-related business events."""
        extra = {
            'event_type': 'user_event',
            'user_id': user_id,
            'business_event': event_type,
            'details': details or {},
        }
        
        self.logger.info(f"User event: {event_type} for user {user_id}", extra=extra)


# Global logger instances
security_logger = SecurityLogger()
performance_logger = PerformanceLogger()
business_logger = BusinessLogger()


def get_logger(name):
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def log_exception(logger, exception, context=None):
    """Log an exception with context."""
    extra = {
        'event_type': 'exception',
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'context': context or {},
    }
    
    logger.error(f"Exception occurred: {type(exception).__name__}: {exception}", 
                exc_info=True, extra=extra)