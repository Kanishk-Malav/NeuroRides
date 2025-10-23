"""
URL configuration for dispatch app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DispatchRequestViewSet,
    DispatchAlgorithmConfigViewSet,
    DispatchMetricsViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'requests', DispatchRequestViewSet, basename='dispatch-request')
router.register(r'algorithms', DispatchAlgorithmConfigViewSet, basename='dispatch-algorithm')
router.register(r'metrics', DispatchMetricsViewSet, basename='dispatch-metrics')

app_name = 'dispatch'

urlpatterns = [
    path('api/dispatch/', include(router.urls)),
]