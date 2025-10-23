"""
URL patterns for fleet app.
"""

from django.urls import path
from . import views, maintenance_views

app_name = 'fleet'

urlpatterns = [
    # Vehicle management
    path('vehicles/', views.VehicleListCreateView.as_view(), name='vehicle-list'),
    path('vehicles/<uuid:id>/', views.VehicleDetailView.as_view(), name='vehicle-detail'),
    path('vehicles/<uuid:vehicle_id>/location/', views.VehicleLocationUpdateView.as_view(), name='vehicle-location'),
    path('vehicles/<uuid:vehicle_id>/status/', views.VehicleStatusUpdateView.as_view(), name='vehicle-status'),
    path('vehicles/<uuid:vehicle_id>/maintenance-check/', maintenance_views.check_vehicle_maintenance, name='vehicle-maintenance-check'),
    path('vehicles/<uuid:vehicle_id>/performance/', maintenance_views.vehicle_performance, name='vehicle-performance'),
    
    # Vehicle search and utilities
    path('vehicles/nearby/', views.vehicle_nearby, name='vehicle-nearby'),
    path('vehicles/bulk-action/', views.bulk_vehicle_action, name='vehicle-bulk-action'),
    
    # Telemetry
    path('telemetry/', views.VehicleTelemetryListCreateView.as_view(), name='telemetry-list'),
    path('telemetry/<int:pk>/', views.VehicleTelemetryDetailView.as_view(), name='telemetry-detail'),
    
    # Maintenance
    path('maintenance/', views.MaintenanceRecordListCreateView.as_view(), name='maintenance-list'),
    path('maintenance/<int:pk>/', views.MaintenanceRecordDetailView.as_view(), name='maintenance-detail'),
    path('maintenance/<int:record_id>/action/', views.MaintenanceActionView.as_view(), name='maintenance-action'),
    path('maintenance/schedule/', maintenance_views.maintenance_schedule, name='maintenance-schedule'),
    path('maintenance/overdue/', maintenance_views.overdue_maintenance, name='maintenance-overdue'),
    path('maintenance/auto-schedule/', maintenance_views.auto_schedule_maintenance, name='maintenance-auto-schedule'),
    path('maintenance/alerts/', maintenance_views.MaintenanceAlertView.as_view(), name='maintenance-alerts'),
    path('maintenance/bulk-action/', maintenance_views.bulk_maintenance_action, name='maintenance-bulk-action'),
    
    # Fleet overview and analytics
    path('overview/', views.fleet_overview, name='fleet-overview'),
    path('analytics/', maintenance_views.fleet_analytics, name='fleet-analytics'),
]