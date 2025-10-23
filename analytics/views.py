"""
API views for analytics app.
"""

import csv
import io
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.pagination import PageNumberPagination

from .models import (
    RideAnalytics, RevenueAnalytics, FleetAnalytics, UserAnalytics,
    PerformanceMetric, ReportTemplate, GeneratedReport
)
from .serializers import (
    RideAnalyticsSerializer, RevenueAnalyticsSerializer, FleetAnalyticsSerializer,
    UserAnalyticsSerializer, PerformanceMetricSerializer, DashboardDataSerializer,
    ChartDataSerializer, KPISerializer, ReportTemplateSerializer,
    GeneratedReportSerializer, ReportGenerationRequestSerializer,
    AnalyticsFilterSerializer, ServiceHealthSerializer, DateRangeSerializer
)
from .services import data_aggregation_service, performance_metrics_service
from .tasks import generate_scheduled_report
from accounts.permissions import IsOwnerOrReadOnly


class AnalyticsPagination(PageNumberPagination):
    """Custom pagination for analytics lists."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class DashboardDataView(APIView):
    """Get dashboard data for different user roles."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get dashboard data based on user role."""
        user = request.user
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get today's analytics data
        rides_today = RideAnalytics.objects.filter(date=today, hour__isnull=True).first()
        revenue_today = RevenueAnalytics.objects.filter(date=today, hour__isnull=True).first()
        fleet_today = FleetAnalytics.objects.filter(date=today, hour__isnull=True).first()
        users_today = UserAnalytics.objects.filter(date=today, hour__isnull=True).first()
        
        # Get yesterday's data for trend calculation
        rides_yesterday = RideAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        revenue_yesterday = RevenueAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        fleet_yesterday = FleetAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        users_yesterday = UserAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        
        # Calculate trends
        def calculate_trend(today_value, yesterday_value):
            if not yesterday_value or yesterday_value == 0:
                return Decimal('0.00')
            return ((today_value - yesterday_value) / yesterday_value) * 100
        
        rides_trend = Decimal('0.00')
        revenue_trend = Decimal('0.00')
        fleet_utilization_trend = Decimal('0.00')
        user_growth_trend = Decimal('0.00')
        
        if rides_today and rides_yesterday:
            rides_trend = calculate_trend(rides_today.total_rides, rides_yesterday.total_rides)
        
        if revenue_today and revenue_yesterday:
            revenue_trend = calculate_trend(revenue_today.total_revenue, revenue_yesterday.total_revenue)
        
        if fleet_today and fleet_yesterday:
            fleet_utilization_trend = calculate_trend(fleet_today.utilization_rate, fleet_yesterday.utilization_rate)
        
        if users_today and users_yesterday:
            user_growth_trend = calculate_trend(users_today.active_users, users_yesterday.active_users)
        
        # Prepare dashboard data
        dashboard_data = {
            'period': f"{today}",
            'rides': RideAnalyticsSerializer(rides_today).data if rides_today else None,
            'revenue': RevenueAnalyticsSerializer(revenue_today).data if revenue_today else None,
            'fleet': FleetAnalyticsSerializer(fleet_today).data if fleet_today else None,
            'users': UserAnalyticsSerializer(users_today).data if users_today else None,
            
            # KPI summaries
            'total_rides_today': rides_today.total_rides if rides_today else 0,
            'total_revenue_today': revenue_today.total_revenue if revenue_today else Decimal('0.00'),
            'active_vehicles': fleet_today.active_vehicles if fleet_today else 0,
            'active_users_today': users_today.active_users if users_today else 0,
            
            # Trends
            'rides_trend': rides_trend,
            'revenue_trend': revenue_trend,
            'fleet_utilization_trend': fleet_utilization_trend,
            'user_growth_trend': user_growth_trend,
        }
        
        # Filter data based on user role
        if user.role == 'rider':
            # Riders see limited data
            dashboard_data = {
                'total_rides_today': dashboard_data['total_rides_today'],
                'active_vehicles': dashboard_data['active_vehicles'],
                'rides_trend': dashboard_data['rides_trend'],
            }
        elif user.role == 'operator':
            # Operators see operational data
            dashboard_data.pop('revenue', None)
            dashboard_data.pop('total_revenue_today', None)
            dashboard_data.pop('revenue_trend', None)
        
        # Admins see all data (no filtering)
        
        serializer = DashboardDataSerializer(dashboard_data)
        return Response(serializer.data)


class RideAnalyticsListView(ListAPIView):
    """List ride analytics data with filtering."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RideAnalyticsSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get filtered ride analytics."""
        queryset = RideAnalytics.objects.all().order_by('-date', '-hour')
        
        # Apply filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        granularity = self.request.query_params.get('granularity', 'daily')
        if granularity == 'daily':
            queryset = queryset.filter(hour__isnull=True)
        elif granularity == 'hourly':
            queryset = queryset.filter(hour__isnull=False)
        
        return queryset


class RevenueAnalyticsListView(ListAPIView):
    """List revenue analytics data with filtering."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RevenueAnalyticsSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get filtered revenue analytics."""
        # Only admins and operators can see revenue data
        if self.request.user.role == 'rider':
            return RevenueAnalytics.objects.none()
        
        queryset = RevenueAnalytics.objects.all().order_by('-date', '-hour')
        
        # Apply filters (same as ride analytics)
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        granularity = self.request.query_params.get('granularity', 'daily')
        if granularity == 'daily':
            queryset = queryset.filter(hour__isnull=True)
        elif granularity == 'hourly':
            queryset = queryset.filter(hour__isnull=False)
        
        return queryset


class FleetAnalyticsListView(ListAPIView):
    """List fleet analytics data with filtering."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FleetAnalyticsSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get filtered fleet analytics."""
        queryset = FleetAnalytics.objects.all().order_by('-date', '-hour')
        
        # Apply filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        granularity = self.request.query_params.get('granularity', 'daily')
        if granularity == 'daily':
            queryset = queryset.filter(hour__isnull=True)
        elif granularity == 'hourly':
            queryset = queryset.filter(hour__isnull=False)
        
        return queryset


class UserAnalyticsListView(ListAPIView):
    """List user analytics data with filtering."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserAnalyticsSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get filtered user analytics."""
        # Only admins can see detailed user analytics
        if self.request.user.role not in ['admin', 'operator']:
            return UserAnalytics.objects.none()
        
        queryset = UserAnalytics.objects.all().order_by('-date', '-hour')
        
        # Apply filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        granularity = self.request.query_params.get('granularity', 'daily')
        if granularity == 'daily':
            queryset = queryset.filter(hour__isnull=True)
        elif granularity == 'hourly':
            queryset = queryset.filter(hour__isnull=False)
        
        return queryset


class ChartDataView(APIView):
    """Get chart data for analytics visualization."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Get chart data based on request parameters."""
        serializer = AnalyticsFilterSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            
            chart_type = request.data.get('chart_type', 'line')
            metric_name = request.data.get('metric_name', 'total_rides')
            
            # Get data based on metric type
            if metric_name in ['total_rides', 'completed_rides', 'cancelled_rides']:
                data = self._get_ride_chart_data(filters, metric_name)
            elif metric_name in ['total_revenue', 'net_revenue', 'avg_transaction_value']:
                if request.user.role == 'rider':
                    return Response(
                        {'error': 'Permission denied for revenue data'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                data = self._get_revenue_chart_data(filters, metric_name)
            elif metric_name in ['utilization_rate', 'active_vehicles', 'avg_response_time_minutes']:
                data = self._get_fleet_chart_data(filters, metric_name)
            elif metric_name in ['active_users', 'new_users', 'user_retention_rate']:
                if request.user.role == 'rider':
                    return Response(
                        {'error': 'Permission denied for user data'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                data = self._get_user_chart_data(filters, metric_name)
            else:
                return Response(
                    {'error': f'Unknown metric: {metric_name}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            chart_data = {
                'chart_type': chart_type,
                'title': f'{metric_name.replace("_", " ").title()} Over Time',
                'x_axis_label': 'Date',
                'y_axis_label': metric_name.replace('_', ' ').title(),
                'data_points': data,
            }
            
            serializer = ChartDataSerializer(chart_data)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _get_ride_chart_data(self, filters, metric_name):
        """Get ride chart data."""
        queryset = RideAnalytics.objects.filter(
            date__gte=filters['start_date'],
            date__lte=filters['end_date'],
            hour__isnull=True  # Daily data
        ).order_by('date')
        
        data_points = []
        for analytics in queryset:
            value = getattr(analytics, metric_name, 0)
            data_points.append({
                'timestamp': timezone.make_aware(
                    datetime.combine(analytics.date, datetime.min.time())
                ),
                'value': Decimal(str(value)),
                'label': str(analytics.date)
            })
        
        return data_points
    
    def _get_revenue_chart_data(self, filters, metric_name):
        """Get revenue chart data."""
        queryset = RevenueAnalytics.objects.filter(
            date__gte=filters['start_date'],
            date__lte=filters['end_date'],
            hour__isnull=True
        ).order_by('date')
        
        data_points = []
        for analytics in queryset:
            value = getattr(analytics, metric_name, Decimal('0.00'))
            data_points.append({
                'timestamp': timezone.make_aware(
                    datetime.combine(analytics.date, datetime.min.time())
                ),
                'value': value,
                'label': str(analytics.date)
            })
        
        return data_points
    
    def _get_fleet_chart_data(self, filters, metric_name):
        """Get fleet chart data."""
        queryset = FleetAnalytics.objects.filter(
            date__gte=filters['start_date'],
            date__lte=filters['end_date'],
            hour__isnull=True
        ).order_by('date')
        
        data_points = []
        for analytics in queryset:
            value = getattr(analytics, metric_name, 0)
            data_points.append({
                'timestamp': timezone.make_aware(
                    datetime.combine(analytics.date, datetime.min.time())
                ),
                'value': Decimal(str(value)),
                'label': str(analytics.date)
            })
        
        return data_points
    
    def _get_user_chart_data(self, filters, metric_name):
        """Get user chart data."""
        queryset = UserAnalytics.objects.filter(
            date__gte=filters['start_date'],
            date__lte=filters['end_date'],
            hour__isnull=True
        ).order_by('date')
        
        data_points = []
        for analytics in queryset:
            value = getattr(analytics, metric_name, 0)
            data_points.append({
                'timestamp': timezone.make_aware(
                    datetime.combine(analytics.date, datetime.min.time())
                ),
                'value': Decimal(str(value)),
                'label': str(analytics.date)
            })
        
        return data_points


class KPIView(APIView):
    """Get Key Performance Indicators."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current KPIs."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get today's data
        rides_today = RideAnalytics.objects.filter(date=today, hour__isnull=True).first()
        revenue_today = RevenueAnalytics.objects.filter(date=today, hour__isnull=True).first()
        fleet_today = FleetAnalytics.objects.filter(date=today, hour__isnull=True).first()
        users_today = UserAnalytics.objects.filter(date=today, hour__isnull=True).first()
        
        # Get yesterday's data for trends
        rides_yesterday = RideAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        revenue_yesterday = RevenueAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        fleet_yesterday = FleetAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        
        def calculate_trend(today_val, yesterday_val):
            if not yesterday_val or yesterday_val == 0:
                return Decimal('0.00'), 'stable'
            
            change = ((today_val - yesterday_val) / yesterday_val) * 100
            direction = 'up' if change > 1 else 'down' if change < -1 else 'stable'
            return change, direction
        
        kpis = []
        
        # Rides KPI
        if rides_today:
            trend_pct, trend_dir = calculate_trend(
                rides_today.total_rides,
                rides_yesterday.total_rides if rides_yesterday else 0
            )
            
            kpis.append({
                'name': 'Total Rides',
                'value': Decimal(str(rides_today.total_rides)),
                'unit': 'rides',
                'trend_percentage': trend_pct,
                'trend_direction': trend_dir,
                'target_value': Decimal('100'),  # Example target
                'status': 'good' if rides_today.total_rides >= 50 else 'warning'
            })
        
        # Revenue KPI (only for admins/operators)
        if revenue_today and request.user.role != 'rider':
            trend_pct, trend_dir = calculate_trend(
                revenue_today.total_revenue,
                revenue_yesterday.total_revenue if revenue_yesterday else Decimal('0.00')
            )
            
            kpis.append({
                'name': 'Total Revenue',
                'value': revenue_today.total_revenue,
                'unit': 'USD',
                'trend_percentage': trend_pct,
                'trend_direction': trend_dir,
                'target_value': Decimal('5000'),  # Example target
                'status': 'good' if revenue_today.total_revenue >= 1000 else 'warning'
            })
        
        # Fleet Utilization KPI
        if fleet_today:
            trend_pct, trend_dir = calculate_trend(
                fleet_today.utilization_rate,
                fleet_yesterday.utilization_rate if fleet_yesterday else Decimal('0.00')
            )
            
            kpis.append({
                'name': 'Fleet Utilization',
                'value': fleet_today.utilization_rate,
                'unit': '%',
                'trend_percentage': trend_pct,
                'trend_direction': trend_dir,
                'target_value': Decimal('80'),  # Example target
                'status': 'good' if fleet_today.utilization_rate >= 60 else 'warning'
            })
        
        # Active Users KPI (only for admins/operators)
        if users_today and request.user.role != 'rider':
            kpis.append({
                'name': 'Active Users',
                'value': Decimal(str(users_today.active_users)),
                'unit': 'users',
                'trend_percentage': Decimal('0.00'),  # Simplified
                'trend_direction': 'stable',
                'target_value': Decimal('200'),  # Example target
                'status': 'good' if users_today.active_users >= 50 else 'warning'
            })
        
        serializer = KPISerializer(kpis, many=True)
        return Response(serializer.data)


class PerformanceMetricsView(ListAPIView):
    """List performance metrics."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PerformanceMetricSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get filtered performance metrics."""
        # Only admins can see performance metrics
        if self.request.user.role != 'admin':
            return PerformanceMetric.objects.none()
        
        queryset = PerformanceMetric.objects.all().order_by('-timestamp')
        
        # Apply filters
        service_name = self.request.query_params.get('service_name')
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        hours_back = int(self.request.query_params.get('hours_back', 24))
        since = timezone.now() - timedelta(hours=hours_back)
        queryset = queryset.filter(timestamp__gte=since)
        
        return queryset


class ServiceHealthView(APIView):
    """Get service health summary."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, service_name=None):
        """Get health summary for service(s)."""
        # Only admins can see service health
        if request.user.role != 'admin':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        hours_back = int(request.query_params.get('hours_back', 24))
        
        if service_name:
            # Get health for specific service
            health_data = performance_metrics_service.get_service_health_summary(
                service_name, hours_back
            )
            serializer = ServiceHealthSerializer(health_data)
            return Response(serializer.data)
        else:
            # Get health for all services
            services = ['rides', 'payments', 'fleet', 'dispatch', 'analytics']
            health_data = []
            
            for service in services:
                service_health = performance_metrics_service.get_service_health_summary(
                    service, hours_back
                )
                health_data.append(service_health)
            
            serializer = ServiceHealthSerializer(health_data, many=True)
            return Response(serializer.data)


class ReportTemplateListCreateView(APIView):
    """List and create report templates."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """List report templates."""
        # Get templates user can access
        templates = ReportTemplate.objects.filter(
            Q(created_by=request.user) | 
            Q(is_public=True) |
            Q(allowed_roles__contains=[request.user.role])
        ).order_by('-created_at')
        
        serializer = ReportTemplateSerializer(templates, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create new report template."""
        serializer = ReportTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GenerateReportView(APIView):
    """Generate a report from template."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate report."""
        serializer = ReportGenerationRequestSerializer(data=request.data)
        if serializer.is_valid():
            # Create report generation task
            task_result = generate_scheduled_report.delay(
                serializer.validated_data['template_id']
            )
            
            return Response({
                'success': True,
                'task_id': task_result.id,
                'message': 'Report generation started'
            }, status=status.HTTP_202_ACCEPTED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GeneratedReportListView(ListAPIView):
    """List generated reports."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GeneratedReportSerializer
    pagination_class = AnalyticsPagination
    
    def get_queryset(self):
        """Get user's generated reports."""
        return GeneratedReport.objects.filter(
            requested_by=self.request.user
        ).order_by('-created_at')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_analytics_csv(request):
    """Export analytics data as CSV."""
    
    # Parse query parameters
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    metric_type = request.query_params.get('metric_type', 'rides')
    
    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get data based on metric type
    if metric_type == 'rides':
        queryset = RideAnalytics.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            hour__isnull=True
        ).order_by('date')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="ride_analytics_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Total Rides', 'Completed Rides', 'Cancelled Rides',
            'Total Distance (km)', 'Avg Distance (km)', 'Avg Duration (min)',
            'Completion Rate (%)'
        ])
        
        for analytics in queryset:
            writer.writerow([
                analytics.date,
                analytics.total_rides,
                analytics.completed_rides,
                analytics.cancelled_rides,
                analytics.total_distance_km,
                analytics.avg_distance_km,
                analytics.avg_duration_minutes,
                float(analytics.completion_rate)
            ])
    
    elif metric_type == 'revenue' and request.user.role != 'rider':
        queryset = RevenueAnalytics.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            hour__isnull=True
        ).order_by('date')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="revenue_analytics_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Total Revenue', 'Net Revenue', 'Total Transactions',
            'Avg Transaction Value', 'Success Rate (%)'
        ])
        
        for analytics in queryset:
            writer.writerow([
                analytics.date,
                analytics.total_revenue,
                analytics.net_revenue,
                analytics.total_transactions,
                analytics.avg_transaction_value,
                float(analytics.transaction_success_rate)
            ])
    
    else:
        return Response(
            {'error': 'Invalid metric_type or insufficient permissions'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def trigger_data_aggregation(request):
    """Manually trigger data aggregation for a specific date."""
    
    # Only admins can trigger aggregation
    if request.user.role != 'admin':
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    target_date_str = request.data.get('date')
    if not target_date_str:
        target_date_str = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Trigger aggregation task
    from .tasks import aggregate_daily_analytics
    task_result = aggregate_daily_analytics.delay(target_date_str)
    
    return Response({
        'success': True,
        'task_id': task_result.id,
        'message': f'Data aggregation started for {target_date_str}'
    })
