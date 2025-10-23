"""
URL patterns for rides app.
"""

from django.urls import path
from . import views

app_name = 'rides'

urlpatterns = [
    # Fare estimation
    path('fare-estimate/', views.FareEstimateView.as_view(), name='fare-estimate'),
    
    # Ride booking and management
    path('book/', views.RideCreateView.as_view(), name='ride-create'),
    path('<uuid:id>/', views.RideDetailView.as_view(), name='ride-detail'),
    path('<uuid:ride_id>/action/', views.RideActionView.as_view(), name='ride-action'),
    path('<uuid:ride_id>/tracking/', views.RideTrackingView.as_view(), name='ride-tracking'),
    
    # Rider-specific endpoints
    path('history/', views.RideHistoryView.as_view(), name='ride-history'),
    path('active/', views.ActiveRideView.as_view(), name='active-ride'),
    
    # Utility endpoints
    path('nearby-vehicles/', views.nearby_vehicles, name='nearby-vehicles'),
    path('service-areas/', views.service_areas, name='service-areas'),
    
    # Operator/Admin endpoints
    path('', views.RideListView.as_view(), name='ride-list'),
    path('stats/', views.ride_stats, name='ride-stats'),
    path('cleanup-expired/', views.cleanup_expired_requests, name='cleanup-expired'),
]