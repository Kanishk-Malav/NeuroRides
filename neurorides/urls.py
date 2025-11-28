"""
URL configuration for neurorides project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [

    path('sentry-debug/', trigger_error),
    # Admin
    path('admin/', admin.site.urls),
    
    # Monitoring and health checks
    path('', include('neurorides.monitoring_urls')),
    
    # API endpoints
    path('api/accounts/', include('accounts.urls')),
    path('api/rides/', include('rides.urls')),
    path('api/fleet/', include('fleet.urls')),
    path('api/dispatch/', include('dispatch.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('', include('realtime.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
