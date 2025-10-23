"""
URL patterns for analytics app.
"""

from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard and KPIs
    path('dashboard/', views.DashboardDataView.as_view(), name='dashboard'),
    path('kpis/', views.KPIView.as_view(), name='kpis'),
    
    # Analytics Data
    path('rides/', views.RideAnalyticsListView.as_view(), name='ride-analytics'),
    path('revenue/', views.RevenueAnalyticsListView.as_view(), name='revenue-analytics'),
    path('fleet/', views.FleetAnalyticsListView.as_view(), name='fleet-analytics'),
    path('users/', views.UserAnalyticsListView.as_view(), name='user-analytics'),
    
    # Charts and Visualization
    path('charts/', views.ChartDataView.as_view(), name='chart-data'),
    
    # Performance Monitoring
    path('performance/', views.PerformanceMetricsView.as_view(), name='performance-metrics'),
    path('health/', views.ServiceHealthView.as_view(), name='service-health-all'),
    path('health/<str:service_name>/', views.ServiceHealthView.as_view(), name='service-health'),
    
    # Reports
    path('reports/templates/', views.ReportTemplateListCreateView.as_view(), name='report-templates'),
    path('reports/generate/', views.GenerateReportView.as_view(), name='generate-report'),
    path('reports/', views.GeneratedReportListView.as_view(), name='generated-reports'),
    
    # Data Export
    path('export/csv/', views.export_analytics_csv, name='export-csv'),
    
    # Admin Functions
    path('admin/aggregate/', views.trigger_data_aggregation, name='trigger-aggregation'),
]