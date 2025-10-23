"""
Tests for analytics app.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, Mock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from .models import (
    RideAnalytics, RevenueAnalytics, FleetAnalytics, UserAnalytics,
    PerformanceMetric, ReportTemplate, GeneratedReport, AnalyticsMetric
)
from .services import DataAggregationService, PerformanceMetricsService
from .tasks import aggregate_daily_analytics, calculate_performance_metrics
from rides.models import Ride
from payments.models import Payment, PaymentGateway
from fleet.models import Vehicle

User = get_user_model()


class AnalyticsModelsTestCase(TestCase):
    """Test analytics models functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.today = timezone.now().date()
    
    def test_ride_analytics_creation(self):
        """Test RideAnalytics model creation."""
        analytics = RideAnalytics.objects.create(
            date=self.today,
            total_rides=100,
            completed_rides=85,
            cancelled_rides=10,
            failed_rides=5,
            total_distance_km=Decimal('500.50'),
            avg_distance_km=Decimal('5.89'),
            avg_duration_minutes=Decimal('15.5')
        )
        
        self.assertEqual(analytics.total_rides, 100)
        self.assertEqual(analytics.completed_rides, 85)
        self.assertEqual(float(analytics.completion_rate), 85.0)
        self.assertEqual(float(analytics.cancellation_rate), 10.0)
    
    def test_revenue_analytics_creation(self):
        """Test RevenueAnalytics model creation."""
        analytics = RevenueAnalytics.objects.create(
            date=self.today,
            total_revenue=Decimal('1500.00'),
            gross_revenue=Decimal('1500.00'),
            net_revenue=Decimal('1400.00'),
            total_transactions=50,
            successful_transactions=48,
            failed_transactions=2
        )
        
        self.assertEqual(analytics.total_revenue, Decimal('1500.00'))
        self.assertEqual(float(analytics.transaction_success_rate), 96.0)
    
    def test_fleet_analytics_creation(self):
        """Test FleetAnalytics model creation."""
        analytics = FleetAnalytics.objects.create(
            date=self.today,
            total_vehicles=20,
            active_vehicles=18,
            idle_vehicles=5,
            maintenance_vehicles=2,
            utilization_rate=Decimal('75.50')
        )
        
        self.assertEqual(analytics.total_vehicles, 20)
        self.assertEqual(analytics.utilization_rate, Decimal('75.50'))
    
    def test_performance_metric_creation(self):
        """Test PerformanceMetric model creation."""
        metric = PerformanceMetric.objects.create(
            category=PerformanceMetric.MetricCategory.RESPONSE_TIME,
            metric_name='api_response_time',
            service_name='rides',
            timestamp=timezone.now(),
            value=Decimal('250.5'),
            unit='ms',
            warning_threshold=Decimal('1000'),
            critical_threshold=Decimal('5000'),
            is_healthy=True
        )
        
        self.assertEqual(metric.service_name, 'rides')
        self.assertTrue(metric.is_healthy)
        self.assertEqual(metric.value, Decimal('250.5'))
    
    def test_report_template_creation(self):
        """Test ReportTemplate model creation."""
        template = ReportTemplate.objects.create(
            name='Daily Summary',
            description='Daily analytics summary report',
            report_type=ReportTemplate.ReportType.SUMMARY,
            created_by=self.user,
            metrics_included=['rides', 'revenue'],
            output_formats=['pdf', 'csv']
        )
        
        self.assertEqual(template.name, 'Daily Summary')
        self.assertEqual(template.created_by, self.user)
        self.assertIn('rides', template.metrics_included)


class DataAggregationServiceTestCase(TestCase):
    """Test data aggregation service functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Gateway',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True
        )
        
        self.vehicle = Vehicle.objects.create(
            license_plate='TEST123',
            model='Test Model',
            status=Vehicle.Status.IDLE,
            is_active=True
        )
        
        self.service = DataAggregationService()
        self.target_date = timezone.now().date()
    
    def test_aggregate_ride_data_empty(self):
        """Test ride data aggregation with no data."""
        result = self.service.aggregate_ride_data(self.target_date)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['date'], self.target_date)
        self.assertIn('daily', result['results'])
    
    def test_aggregate_ride_data_with_rides(self):
        """Test ride data aggregation with actual rides."""
        # Create test rides
        for i in range(5):
            Ride.objects.create(
                rider=self.user,
                pickup_latitude=37.7749,
                pickup_longitude=-122.4194,
                destination_latitude=37.7849,
                destination_longitude=-122.4094,
                status=Ride.Status.COMPLETED,
                requested_at=timezone.now(),
                actual_distance_km=Decimal('5.0'),
                actual_duration_minutes=15
            )
        
        # Create cancelled ride
        Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.CANCELLED,
            requested_at=timezone.now()
        )
        
        result = self.service.aggregate_ride_data(self.target_date)
        
        self.assertTrue(result['success'])
        
        # Check that analytics were created
        analytics = RideAnalytics.objects.filter(date=self.target_date, hour__isnull=True).first()
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.total_rides, 6)
        self.assertEqual(analytics.completed_rides, 5)
        self.assertEqual(analytics.cancelled_rides, 1)
    
    def test_aggregate_revenue_data_with_payments(self):
        """Test revenue data aggregation with payments."""
        # Create test payments
        for i in range(3):
            Payment.objects.create(
                user=self.user,
                amount=Decimal('25.50'),
                currency='USD',
                status=Payment.PaymentStatus.COMPLETED,
                gateway=self.gateway,
                base_fare=Decimal('5.00'),
                distance_fare=Decimal('15.00'),
                time_fare=Decimal('3.50'),
                tax_amount=Decimal('2.00')
            )
        
        result = self.service.aggregate_revenue_data(self.target_date)
        
        self.assertTrue(result['success'])
        
        # Check that analytics were created
        analytics = RevenueAnalytics.objects.filter(date=self.target_date, hour__isnull=True).first()
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.total_transactions, 3)
        self.assertEqual(analytics.total_revenue, Decimal('76.50'))  # 3 * 25.50
    
    def test_aggregate_fleet_data(self):
        """Test fleet data aggregation."""
        # Create additional vehicles
        for i in range(4):
            Vehicle.objects.create(
                license_plate=f'TEST{i}',
                model='Test Model',
                status=Vehicle.Status.IDLE,
                is_active=True
            )
        
        result = self.service.aggregate_fleet_data(self.target_date)
        
        self.assertTrue(result['success'])
        
        # Check that analytics were created
        analytics = FleetAnalytics.objects.filter(date=self.target_date, hour__isnull=True).first()
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.total_vehicles, 5)  # Including the one from setUp
    
    def test_aggregate_all_data(self):
        """Test aggregating all data types."""
        result = self.service.aggregate_all_data(self.target_date)
        
        self.assertTrue(result['success'])
        self.assertIn('rides', result['aggregations'])
        self.assertIn('revenue', result['aggregations'])
        self.assertIn('fleet', result['aggregations'])
        self.assertIn('users', result['aggregations'])
        self.assertEqual(len(result['errors']), 0)


class PerformanceMetricsServiceTestCase(TestCase):
    """Test performance metrics service functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.service = PerformanceMetricsService()
    
    def test_record_response_time(self):
        """Test recording response time metric."""
        metric = self.service.record_response_time('rides', 'list', 250.5)
        
        self.assertEqual(metric.service_name, 'rides')
        self.assertEqual(metric.category, PerformanceMetric.MetricCategory.RESPONSE_TIME)
        self.assertEqual(metric.value, Decimal('250.5'))
        self.assertTrue(metric.is_healthy)  # 250ms < 1000ms threshold
    
    def test_record_throughput(self):
        """Test recording throughput metric."""
        metric = self.service.record_throughput('payments', 15.5)
        
        self.assertEqual(metric.service_name, 'payments')
        self.assertEqual(metric.category, PerformanceMetric.MetricCategory.THROUGHPUT)
        self.assertEqual(metric.value, Decimal('15.5'))
        self.assertTrue(metric.is_healthy)  # 15.5 req/s >= 10 req/s threshold
    
    def test_record_error_rate(self):
        """Test recording error rate metric."""
        metric = self.service.record_error_rate('fleet', 2.5)
        
        self.assertEqual(metric.service_name, 'fleet')
        self.assertEqual(metric.category, PerformanceMetric.MetricCategory.ERROR_RATE)
        self.assertEqual(metric.value, Decimal('2.5'))
        self.assertTrue(metric.is_healthy)  # 2.5% < 5% threshold
    
    def test_get_service_health_summary(self):
        """Test getting service health summary."""
        # Create test metrics
        service_name = 'test_service'
        
        self.service.record_response_time(service_name, 'api', 300)
        self.service.record_response_time(service_name, 'api', 400)
        self.service.record_throughput(service_name, 20)
        self.service.record_error_rate(service_name, 1.5)
        
        summary = self.service.get_service_health_summary(service_name, 1)
        
        self.assertEqual(summary['service_name'], service_name)
        self.assertIn('response_time', summary['summary'])
        self.assertIn('throughput', summary['summary'])
        self.assertIn('error_rate', summary['summary'])
        self.assertGreater(summary['overall_health'], 0)


class AnalyticsAPITestCase(APITestCase):
    """Test analytics API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            role='admin'
        )
        
        self.operator_user = User.objects.create_user(
            username='operator',
            email='operator@example.com',
            password='testpass123',
            role='operator'
        )
        
        self.rider_user = User.objects.create_user(
            username='rider',
            email='rider@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.today = timezone.now().date()
        
        # Create test analytics data
        self.ride_analytics = RideAnalytics.objects.create(
            date=self.today,
            total_rides=50,
            completed_rides=45,
            cancelled_rides=3,
            failed_rides=2,
            avg_distance_km=Decimal('6.5'),
            avg_duration_minutes=Decimal('18.2')
        )
        
        self.revenue_analytics = RevenueAnalytics.objects.create(
            date=self.today,
            total_revenue=Decimal('1250.00'),
            net_revenue=Decimal('1150.00'),
            total_transactions=45,
            successful_transactions=45,
            avg_transaction_value=Decimal('27.78')
        )
        
        self.fleet_analytics = FleetAnalytics.objects.create(
            date=self.today,
            total_vehicles=15,
            active_vehicles=12,
            utilization_rate=Decimal('80.0'),
            avg_response_time_minutes=Decimal('4.5')
        )
    
    def test_dashboard_data_admin(self):
        """Test dashboard data endpoint for admin user."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_rides_today', response.data)
        self.assertIn('total_revenue_today', response.data)
        self.assertIn('active_vehicles', response.data)
        self.assertEqual(response.data['total_rides_today'], 50)
    
    def test_dashboard_data_rider(self):
        """Test dashboard data endpoint for rider user (limited data)."""
        self.client.force_authenticate(user=self.rider_user)
        
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_rides_today', response.data)
        self.assertIn('active_vehicles', response.data)
        # Riders shouldn't see revenue data
        self.assertNotIn('total_revenue_today', response.data)
    
    def test_ride_analytics_list(self):
        """Test ride analytics list endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:ride-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['total_rides'], 50)
    
    def test_revenue_analytics_list_admin(self):
        """Test revenue analytics list endpoint for admin."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:revenue-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(float(response.data['results'][0]['total_revenue']), 1250.00)
    
    def test_revenue_analytics_list_rider_forbidden(self):
        """Test revenue analytics list endpoint forbidden for rider."""
        self.client.force_authenticate(user=self.rider_user)
        
        url = reverse('analytics:revenue-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)  # No data for riders
    
    def test_kpis_endpoint(self):
        """Test KPIs endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:kpis')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        
        # Check for expected KPIs
        kpi_names = [kpi['name'] for kpi in response.data]
        self.assertIn('Total Rides', kpi_names)
        self.assertIn('Fleet Utilization', kpi_names)
    
    def test_chart_data_endpoint(self):
        """Test chart data endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:chart-data')
        data = {
            'start_date': self.today,
            'end_date': self.today,
            'metric_name': 'total_rides',
            'chart_type': 'line'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['chart_type'], 'line')
        self.assertIn('data_points', response.data)
    
    def test_performance_metrics_admin_only(self):
        """Test performance metrics endpoint (admin only)."""
        # Test with admin user
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:performance-metrics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with rider user (should have no access)
        self.client.force_authenticate(user=self.rider_user)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)  # No data for riders
    
    def test_export_csv_endpoint(self):
        """Test CSV export endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:export-csv')
        params = {
            'start_date': self.today,
            'end_date': self.today,
            'metric_type': 'rides'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_trigger_aggregation_admin_only(self):
        """Test trigger aggregation endpoint (admin only)."""
        # Test with admin user
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:trigger-aggregation')
        data = {'date': str(self.today)}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Test with rider user (should be forbidden)
        self.client.force_authenticate(user=self.rider_user)
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AnalyticsTasksTestCase(TransactionTestCase):
    """Test analytics Celery tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.target_date = timezone.now().date()
    
    def test_aggregate_daily_analytics_task(self):
        """Test daily analytics aggregation task."""
        # Create some test data
        Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED,
            requested_at=timezone.now()
        )
        
        result = aggregate_daily_analytics(str(self.target_date))
        
        self.assertTrue(result['success'])
        self.assertEqual(result['date'], str(self.target_date))
        
        # Check that analytics were created
        self.assertTrue(
            RideAnalytics.objects.filter(date=self.target_date).exists()
        )
    
    def test_calculate_performance_metrics_task(self):
        """Test performance metrics calculation task."""
        result = calculate_performance_metrics()
        
        self.assertTrue(result['success'])
        self.assertGreater(result['metrics_recorded'], 0)
        
        # Check that metrics were created
        self.assertTrue(PerformanceMetric.objects.exists())


class ReportTemplateTestCase(TestCase):
    """Test report template functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_report_template_creation(self):
        """Test creating a report template."""
        template = ReportTemplate.objects.create(
            name='Test Report',
            description='Test report description',
            report_type=ReportTemplate.ReportType.SUMMARY,
            created_by=self.user,
            metrics_included=['rides', 'revenue'],
            output_formats=['pdf', 'csv'],
            is_public=True
        )
        
        self.assertEqual(template.name, 'Test Report')
        self.assertEqual(template.created_by, self.user)
        self.assertTrue(template.is_public)
        self.assertIn('rides', template.metrics_included)
    
    def test_generated_report_creation(self):
        """Test creating a generated report."""
        template = ReportTemplate.objects.create(
            name='Test Report',
            report_type=ReportTemplate.ReportType.SUMMARY,
            created_by=self.user,
            metrics_included=['rides']
        )
        
        report = GeneratedReport.objects.create(
            template=template,
            name='Test Generated Report',
            requested_by=self.user,
            period_start=timezone.now() - timedelta(days=1),
            period_end=timezone.now(),
            output_format='pdf',
            status=GeneratedReport.Status.PENDING
        )
        
        self.assertEqual(report.template, template)
        self.assertEqual(report.requested_by, self.user)
        self.assertEqual(report.status, GeneratedReport.Status.PENDING)


class AnalyticsIntegrationTestCase(TestCase):
    """Integration tests for analytics system."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Gateway',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True
        )
        
        self.today = timezone.now().date()
    
    def test_end_to_end_analytics_flow(self):
        """Test complete analytics flow from data creation to aggregation."""
        # Create rides
        rides = []
        for i in range(10):
            ride = Ride.objects.create(
                rider=self.user,
                pickup_latitude=37.7749,
                pickup_longitude=-122.4194,
                destination_latitude=37.7849,
                destination_longitude=-122.4094,
                status=Ride.Status.COMPLETED,
                requested_at=timezone.now(),
                actual_distance_km=Decimal('5.0'),
                actual_duration_minutes=15
            )
            rides.append(ride)
        
        # Create payments for rides
        for ride in rides[:8]:  # 8 successful payments
            Payment.objects.create(
                user=self.user,
                ride=ride,
                amount=Decimal('25.00'),
                currency='USD',
                status=Payment.PaymentStatus.COMPLETED,
                gateway=self.gateway
            )
        
        # Aggregate data
        service = DataAggregationService()
        result = service.aggregate_all_data(self.today)
        
        self.assertTrue(result['success'])
        
        # Verify ride analytics
        ride_analytics = RideAnalytics.objects.filter(date=self.today, hour__isnull=True).first()
        self.assertIsNotNone(ride_analytics)
        self.assertEqual(ride_analytics.total_rides, 10)
        self.assertEqual(ride_analytics.completed_rides, 10)
        
        # Verify revenue analytics
        revenue_analytics = RevenueAnalytics.objects.filter(date=self.today, hour__isnull=True).first()
        self.assertIsNotNone(revenue_analytics)
        self.assertEqual(revenue_analytics.total_transactions, 8)
        self.assertEqual(revenue_analytics.total_revenue, Decimal('200.00'))  # 8 * 25.00
        
        # Verify analytics can be retrieved via API
        from rest_framework.test import APIClient
        client = APIClient()
        
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            role='admin'
        )
        client.force_authenticate(user=admin_user)
        
        # Test dashboard endpoint
        response = client.get('/api/analytics/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_rides_today'], 10)
