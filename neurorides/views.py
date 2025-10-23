"""
System monitoring and health check views.
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings

from .monitoring import health_checker, metrics_collector
from .logging import get_logger

logger = get_logger('neurorides.monitoring')


@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': health_checker._get_timestamp(),
        'service': 'NeuroRides API',
        'version': '1.0.0',
    })


@require_http_methods(["GET"])
def health_detailed(request):
    """
    Detailed health check endpoint.
    Runs comprehensive system checks.
    """
    try:
        health_results = health_checker.run_all_checks()
        
        # Log health check results
        logger.info(
            f"Health check completed: {health_results['overall_status']} "
            f"({health_results['summary']['passed']}/{health_results['summary']['total_checks']} passed)"
        )
        
        # Return appropriate HTTP status code
        status_code = 200
        if health_results['overall_status'] == 'warning':
            status_code = 200  # Still operational
        elif health_results['overall_status'] == 'unhealthy':
            status_code = 503  # Service unavailable
        
        return JsonResponse(health_results, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed with exception: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Health check failed',
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
def readiness_check(request):
    """
    Kubernetes readiness probe endpoint.
    Checks if the service is ready to receive traffic.
    """
    try:
        # Check critical dependencies
        critical_checks = ['database', 'redis']
        
        for check_name in critical_checks:
            check_func = health_checker.checks.get(check_name)
            if check_func:
                result = check_func()
                if result['status'] == 'error':
                    return JsonResponse({
                        'status': 'not_ready',
                        'message': f'Critical dependency {check_name} is not available',
                        'details': result,
                    }, status=503)
        
        return JsonResponse({
            'status': 'ready',
            'timestamp': health_checker._get_timestamp(),
        })
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'not_ready',
            'message': 'Readiness check failed',
            'error': str(e),
        }, status=503)


@require_http_methods(["GET"])
def liveness_check(request):
    """
    Kubernetes liveness probe endpoint.
    Checks if the service is alive and should not be restarted.
    """
    try:
        # Simple check to ensure the application is responsive
        return JsonResponse({
            'status': 'alive',
            'timestamp': health_checker._get_timestamp(),
        })
        
    except Exception as e:
        logger.error(f"Liveness check failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'dead',
            'message': 'Liveness check failed',
            'error': str(e),
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def metrics(request):
    """
    System and application metrics endpoint.
    Requires admin privileges.
    """
    try:
        metrics_data = metrics_collector.collect_all_metrics()
        
        logger.info("Metrics collected successfully")
        
        return JsonResponse(metrics_data)
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}", exc_info=True)
        return JsonResponse({
            'error': 'Metrics collection failed',
            'message': str(e),
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def system_info(request):
    """
    System information endpoint.
    Requires admin privileges.
    """
    try:
        import platform
        import sys
        import django
        
        system_info = {
            'timestamp': health_checker._get_timestamp(),
            'system': {
                'platform': platform.platform(),
                'architecture': platform.architecture(),
                'processor': platform.processor(),
                'python_version': sys.version,
                'django_version': django.get_version(),
            },
            'application': {
                'name': 'NeuroRides',
                'version': '1.0.0',
                'debug_mode': settings.DEBUG,
                'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
            },
            'database': {
                'engine': settings.DATABASES['default']['ENGINE'],
                'name': settings.DATABASES['default']['NAME'],
            },
            'cache': {
                'backend': settings.CACHES['default']['BACKEND'],
            },
        }
        
        return JsonResponse(system_info)
        
    except Exception as e:
        logger.error(f"System info collection failed: {e}", exc_info=True)
        return JsonResponse({
            'error': 'System info collection failed',
            'message': str(e),
        }, status=500)


class MonitoringDashboardView(View):
    """
    Simple monitoring dashboard view.
    """
    
    @method_decorator(staff_member_required)
    def get(self, request):
        """Render monitoring dashboard."""
        try:
            # Get health status
            health_results = health_checker.run_all_checks()
            
            # Get metrics
            metrics_data = metrics_collector.collect_all_metrics()
            
            # Simple HTML dashboard
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>NeuroRides Monitoring Dashboard</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .status-healthy {{ color: green; }}
                    .status-warning {{ color: orange; }}
                    .status-error {{ color: red; }}
                    .metric-box {{ 
                        border: 1px solid #ddd; 
                        padding: 15px; 
                        margin: 10px 0; 
                        border-radius: 5px; 
                    }}
                    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                    pre {{ background: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <h1>NeuroRides Monitoring Dashboard</h1>
                
                <div class="metric-box">
                    <h2>Overall System Status: 
                        <span class="status-{health_results['overall_status']}">
                            {health_results['overall_status'].upper()}
                        </span>
                    </h2>
                    <p>Last updated: {health_results['timestamp']}</p>
                    <p>Checks: {health_results['summary']['passed']}/{health_results['summary']['total_checks']} passed</p>
                </div>
                
                <div class="grid">
                    <div class="metric-box">
                        <h3>Health Checks</h3>
                        <pre>{json.dumps(health_results['checks'], indent=2)}</pre>
                    </div>
                    
                    <div class="metric-box">
                        <h3>System Metrics</h3>
                        <pre>{json.dumps(metrics_data.get('system', {}), indent=2)}</pre>
                    </div>
                    
                    <div class="metric-box">
                        <h3>Application Metrics</h3>
                        <pre>{json.dumps(metrics_data.get('application', {}), indent=2)}</pre>
                    </div>
                </div>
                
                <div class="metric-box">
                    <h3>API Endpoints</h3>
                    <ul>
                        <li><a href="/health/">Basic Health Check</a></li>
                        <li><a href="/health/detailed/">Detailed Health Check</a></li>
                        <li><a href="/health/ready/">Readiness Check</a></li>
                        <li><a href="/health/live/">Liveness Check</a></li>
                        <li><a href="/monitoring/metrics/">Metrics (JSON)</a></li>
                        <li><a href="/monitoring/system-info/">System Info</a></li>
                    </ul>
                </div>
                
                <script>
                    // Auto-refresh every 30 seconds
                    setTimeout(function() {{
                        window.location.reload();
                    }}, 30000);
                </script>
            </body>
            </html>
            """
            
            from django.http import HttpResponse
            return HttpResponse(html_content)
            
        except Exception as e:
            logger.error(f"Dashboard rendering failed: {e}", exc_info=True)
            from django.http import HttpResponse
            return HttpResponse(f"Dashboard error: {str(e)}", status=500)


# Add helper method to health_checker
def _get_timestamp():
    """Get current timestamp in ISO format."""
    from django.utils import timezone
    return timezone.now().isoformat()

# Monkey patch the method
health_checker._get_timestamp = _get_timestamp