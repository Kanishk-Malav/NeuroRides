"""
Tests for analytics Celery tasks.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta

from .tasks import (
    aggregate_daily_analytics,
    aggregate_hourly_analytics,
    aggregate_weekly_analytics,
    cleanup_old_analytics_data,
    generate_scheduled_report,
    calculate_performance_metrics,
    generate_daily_summary_report
)
from .models import (
    RideAnalytics, RevenueAnalytics, FleetAnalytics, UserAnalytics,
    PerformanceMetric, GeneratedReport, ReportTemplate
)
from accounts.models import User


class AnalyticsTasksTestCase(TestCase):
    """Test case for analytics tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='admin'
        )
        
        # Create test analytics data
        self.test_date = date.today() - timedelta(days=1)
        
        self.ride_analytics = RideAnalytics.objects.create(
            date=self.test_date,
            total_rides=100,
            completed_rides=85,
            cancelled_rides=15,
            completion_rate=85.0,
            avg_distance_km=5.5,
            avg_duration_minutes=15.0,
            avg_wait_time_minutes=3.5
        )
        
        self.revenue_analytics = RevenueAnalytics.objects.create(
            date=self.test_date,
            total_revenue=1500.00,
            net_revenue=1350.00,
            total_transactions=85,
            successful_transactions=85,
            transaction_success_rate=100.0,
            avg_transaction_value=17.65
        )
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_daily_analytics_success(self, mock_service):
        """Test successful daily analytics aggregation."""
        # Mock service response
        mock_service.aggregate_all_data.return_value = {
            'success': True,
            'aggregated_records': 4,
            'errors': []
        }
        
        # Execute task
        result = aggregate_daily_analytics('2023-12-01')
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['aggregated_records'], 4)
        
        # Verify service was called with correct parameters
        mock_service.aggregate_all_data.assert_called_once_with(
            date(2023, 12, 1), hourly=False
        )
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_daily_analytics_with_errors(self, mock_service):
        """Test daily analytics aggregation with errors."""
        # Mock service response with errors
        mock_service.aggregate_all_data.return_value = {
            'success': False,
            'aggregated_records': 2,
            'errors': ['Failed to aggregate ride data', 'Database connection error']
        }
        
        # Execute task
        result = aggregate_daily_analytics('2023-12-01')
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(len(result['errors']), 2)
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_daily_analytics_default_date(self, mock_service):
        """Test daily analytics aggregation with default date (yesterday)."""
        # Mock service response
        mock_service.aggregate_all_data.return_value = {
            'success': True,
            'aggregated_records': 4,
            'errors': []
        }
        
        # Execute task without date parameter
        result = aggregate_daily_analytics()
        
        # Verify result
        self.assertTrue(result['success'])
        
        # Verify service was called with yesterday's date
        expected_date = (timezone.now() - timedelta(days=1)).date()
        mock_service.aggregate_all_data.assert_called_once_with(
            expected_date, hourly=False
        )
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_hourly_analytics(self, mock_service):
        """Test hourly analytics aggregation."""
        # Mock service response
        mock_service.aggregate_all_data.return_value = {
            'success': True,
            'aggregated_records': 24,  # 24 hours
            'errors': []
        }
        
        # Execute task
        result = aggregate_hourly_analytics('2023-12-01')
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['aggregated_records'], 24)
        
        # Verify service was called with hourly=True
        mock_service.aggregate_all_data.assert_called_once_with(
            date(2023, 12, 1), hourly=True
        )
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_weekly_analytics(self, mock_service):
        """Test weekly analytics aggregation."""
        # Mock service response for each day
        mock_service.aggregate_all_data.return_value = {
            'success': True,
            'aggregated_records': 4,
            'errors': []
        }
        
        # Execute task
        result = aggregate_weekly_analytics()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(len(result['daily_results']), 7)  # 7 days
        
        # Verify service was called 7 times (once for each day)
        self.assertEqual(mock_service.aggregate_all_data.call_count, 7)
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_weekly_analytics_with_errors(self, mock_service):
        """Test weekly analytics aggregation with some daily failures."""
        # Mock service to fail on some days
        def side_effect(target_date, hourly):
            if target_date.day % 2 == 0:  # Fail on even days
                raise Exception("Database error")
            return {
                'success': True,
                'aggregated_records': 4,
                'errors': []
            }
        
        mock_service.aggregate_all_data.side_effect = side_effect
        
        # Execute task
        result = aggregate_weekly_analytics()
        
        # Verify result
        self.assertFalse(result['success'])  # Overall failure due to errors
        self.assertTrue(len(result['errors']) > 0)
        self.assertEqual(len(result['daily_results']), 7)
    
    def test_cleanup_old_analytics_data(self):
        """Test cleanup of old analytics data."""
        # Create old analytics data (older than 2 years)
        old_date = timezone.now() - timedelta(days=800)
        
        old_ride_analytics = RideAnalytics.objects.create(
            date=old_date.date(),
            total_rides=50,
            completed_rides=40,
            cancelled_rides=10,
            completion_rate=80.0,
            avg_distance_km=4.0,
            avg_duration_minutes=12.0,
            avg_wait_time_minutes=2.0
        )
        
        old_performance_metric = PerformanceMetric.objects.create(
            service_name='test_service',
            metric_type='response_time',
            metric_value=100.0,
            timestamp=timezone.now() - timedelta(days=100)
        )
        
        # Execute task
        result = cleanup_old_analytics_data()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['cleanup_results']['RideAnalytics'], 1)
        self.assertEqual(result['cleanup_results']['PerformanceMetric'], 1)
        
        # Verify old data was deleted
        self.assertFalse(RideAnalytics.objects.filter(id=old_ride_analytics.id).exists())
        self.assertFalse(PerformanceMetric.objects.filter(id=old_performance_metric.id).exists())
        
        # Verify recent data was not deleted
        self.assertTrue(RideAnalytics.objects.filter(id=self.ride_analytics.id).exists())
    
    def test_generate_scheduled_report(self):
        """Test scheduled report generation."""
        # Create report template
        template = ReportTemplate.objects.create(
            name='Daily Revenue Report',
            description='Daily revenue and transaction summary',
            created_by=self.user,
            report_type='revenue',
            filters={'period': 'daily'},
            schedule_enabled=True,
            schedule_frequency='daily'
        )
        
        # Execute task
        result = generate_scheduled_report(str(template.id))
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['template_name'], 'Daily Revenue Report')
        self.assertIn('report_id', result)
        
        # Verify report was created
        report = GeneratedReport.objects.get(id=result['report_id'])
        self.assertEqual(report.template, template)
        self.assertEqual(report.status, GeneratedReport.Status.COMPLETED)
    
    def test_generate_scheduled_report_template_not_found(self):
        """Test scheduled report generation with non-existent template."""
        # Execute task with non-existent template ID
        result = generate_scheduled_report('non-existent-id')
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Report template not found')
    
    @patch('analytics.tasks.performance_metrics_service')
    def test_calculate_performance_metrics(self, mock_service):
        """Test performance metrics calculation."""
        # Execute task
        result = calculate_performance_metrics()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['metrics_recorded'], 15)  # 5 services * 3 metrics each
        self.assertEqual(len(result['services_checked']), 5)
        
        # Verify service methods were called
        self.assertEqual(mock_service.record_response_time.call_count, 5)
        self.assertEqual(mock_service.record_throughput.call_count, 5)
        self.assertEqual(mock_service.record_error_rate.call_count, 5)
    
    def test_generate_daily_summary_report(self):
        """Test daily summary report generation."""
        # Execute task
        result = generate_daily_summary_report()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('summary', result)
        
        # Verify summary contains expected data
        summary = result['summary']
        self.assertEqual(summary['rides']['total_rides'], 100)
        self.assertEqual(summary['rides']['completed_rides'], 85)
        self.assertEqual(summary['revenue']['total_revenue'], 1500.0)
        self.assertEqual(summary['revenue']['net_revenue'], 1350.0)
    
    def test_generate_daily_summary_report_no_data(self):
        """Test daily summary report generation with no data."""
        # Delete test data
        RideAnalytics.objects.all().delete()
        RevenueAnalytics.objects.all().delete()
        
        # Execute task
        result = generate_daily_summary_report()
        
        # Verify result
        self.assertTrue(result['success'])
        
        # Verify summary contains zeros for missing data
        summary = result['summary']
        self.assertEqual(summary['rides']['total_rides'], 0)
        self.assertEqual(summary['revenue']['total_revenue'], 0)


class AnalyticsTaskRetryTestCase(TestCase):
    """Test case for analytics task retry logic."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='admin'
        )
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_daily_analytics_retry_logic(self, mock_service):
        """Test daily analytics aggregation retry logic on failure."""
        # Mock service to raise exception
        mock_service.aggregate_all_data.side_effect = Exception("Database error")
        
        # Create a mock task with retry capability
        task_mock = MagicMock()
        task_mock.request.retries = 0
        task_mock.max_retries = 3
        task_mock.retry.side_effect = Exception("Retry called")
        
        # Execute task and expect retry to be called
        with self.assertRaises(Exception) as context:
            aggregate_daily_analytics.__wrapped__(task_mock, '2023-12-01')
        
        self.assertEqual(str(context.exception), "Retry called")
        task_mock.retry.assert_called_once()
    
    @patch('analytics.tasks.data_aggregation_service')
    def test_aggregate_daily_analytics_max_retries_exceeded(self, mock_service):
        """Test daily analytics aggregation when max retries are exceeded."""
        # Mock service to raise exception
        mock_service.aggregate_all_data.side_effect = Exception("Database error")
        
        # Create a mock task that has exceeded max retries
        task_mock = MagicMock()
        task_mock.request.retries = 3
        task_mock.max_retries = 3
        
        # Execute task
        result = aggregate_daily_analytics.__wrapped__(task_mock, '2023-12-01')
        
        # Verify result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('Task failed after 3 retries', result['error'])
    
    def test_generate_scheduled_report_retry_logic(self):
        """Test scheduled report generation retry logic."""
        # Create report template
        template = ReportTemplate.objects.create(
            name='Test Report',
            description='Test report template',
            created_by=self.user,
            report_type='revenue',
            filters={'period': 'daily'},
            schedule_enabled=True,
            schedule_frequency='daily'
        )
        
        # Create a mock task with retry capability
        task_mock = MagicMock()
        task_mock.request.retries = 0
        task_mock.max_retries = 2
        task_mock.retry.side_effect = Exception("Retry called")
        
        # Mock report generation to fail
        with patch('analytics.tasks.GeneratedReport.objects.create') as mock_create:
            mock_create.side_effect = Exception("Report generation error")
            
            # Execute task and expect retry to be called
            with self.assertRaises(Exception) as context:
                generate_scheduled_report.__wrapped__(task_mock, str(template.id))
            
            self.assertEqual(str(context.exception), "Retry called")
            task_mock.retry.assert_called_once()


class AnalyticsTaskIntegrationTestCase(TestCase):
    """Integration tests for analytics tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='admin'
        )
    
    def test_cleanup_and_aggregation_integration(self):
        """Test integration between cleanup and aggregation tasks."""
        # Create old and new analytics data
        old_date = timezone.now() - timedelta(days=800)
        recent_date = timezone.now() - timedelta(days=1)
        
        old_analytics = RideAnalytics.objects.create(
            date=old_date.date(),
            total_rides=50,
            completed_rides=40,
            cancelled_rides=10,
            completion_rate=80.0,
            avg_distance_km=4.0,
            avg_duration_minutes=12.0,
            avg_wait_time_minutes=2.0
        )
        
        recent_analytics = RideAnalytics.objects.create(
            date=recent_date.date(),
            total_rides=100,
            completed_rides=85,
            cancelled_rides=15,
            completion_rate=85.0,
            avg_distance_km=5.5,
            avg_duration_minutes=15.0,
            avg_wait_time_minutes=3.5
        )
        
        # Run cleanup task
        cleanup_result = cleanup_old_analytics_data()
        
        # Verify cleanup worked
        self.assertTrue(cleanup_result['success'])
        self.assertEqual(cleanup_result['cleanup_results']['RideAnalytics'], 1)
        
        # Verify old data was deleted but recent data remains
        self.assertFalse(RideAnalytics.objects.filter(id=old_analytics.id).exists())
        self.assertTrue(RideAnalytics.objects.filter(id=recent_analytics.id).exists())
        
        # Run summary report generation
        summary_result = generate_daily_summary_report()
        
        # Verify summary uses remaining data
        self.assertTrue(summary_result['success'])
        summary = summary_result['summary']
        self.assertEqual(summary['rides']['total_rides'], 100)  # From recent data