"""
Health check views for monitoring.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import sys


@csrf_exempt
@require_GET
def health_check(request):
    """
    Basic health check endpoint.
    Returns 200 if service is healthy.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'neurorides',
        'version': '1.0.0'
    })


@csrf_exempt
@require_GET
def health_check_detailed(request):
    """
    Detailed health check with database connectivity.
    """
    health_status = {
        'status': 'healthy',
        'service': 'neurorides',
        'version': '1.0.0',
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'checks': {}
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['checks']['database'] = 'ok'
    except Exception as e:
        health_status['checks']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check cache (if configured)
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['checks']['cache'] = 'ok'
        else:
            health_status['checks']['cache'] = 'error'
    except Exception as e:
        health_status['checks']['cache'] = f'error: {str(e)}'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return JsonResponse(health_status, status=status_code)


@csrf_exempt
@require_GET
def readiness_check(request):
    """
    Readiness check for load balancers.
    Returns 200 when ready to accept traffic.
    """
    try:
        # Check if database is accessible
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'ready',
            'service': 'neurorides'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e)
        }, status=503)


@csrf_exempt
@require_GET
def liveness_check(request):
    """
    Liveness check for container orchestration.
    Returns 200 if process is alive.
    """
    return JsonResponse({
        'status': 'alive',
        'service': 'neurorides'
    })
