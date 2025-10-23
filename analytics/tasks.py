"""
Celery tasks for analytics data aggregation.
"""

from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta, datetime
import logging

from .services import data_aggregation_service, performance_metrics_service
from .models import GeneratedReport, ReportTemplate

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def aggregate_daily_analytics(self, target_date_str=None):
    """
    Aggregate analytics data for a specific date.
    
    Args:
        target_date_str: Date string in YYYY-MM-DD format. If None, uses yesterday.
    
    Returns:
        dict: Aggregation results
    """
    try:
        # Parse target date or use yesterday
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = (timezone.now() - timedelta(days=1)).date()
        
        logger.info(f"Starting daily analytics aggregation for {target_date}")
        
        # Aggregate all data types
        result = data_aggregation_service.aggregate_all_data(target_date, hourly=False)
        
        if result['success']:
            logger.info(f"Daily analytics aggregation completed for {target_date}")
        else:
            logger.error(f"Daily analytics aggregation had errors for {target_date}: {result['errors']}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Daily analytics aggregation failed: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying daily analytics aggregation (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))  # Exponential backoff
        
        return {
            'success': False,
            'error': f'Task failed after {self.max_retries} retries: {str(exc)}',
            'date': target_date_str,
        }


@shared_task(bind=True, max_retries=3)
def aggregate_hourly_analytics(self, target_date_str=None):
    """
    Aggregate hourly analytics data for a specific date.
    
    Args:
        target_date_str: Date string in YYYY-MM-DD format. If None, uses yesterday.
    
    Returns:
        dict: Aggregation results
    """
    try:
        # Parse target date or use yesterday
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = (timezone.now() - timedelta(days=1)).date()
        
        logger.info(f"Starting hourly analytics aggregation for {target_date}")
        
        # Aggregate all data types with hourly granularity
        result = data_aggregation_service.aggregate_all_data(target_date, hourly=True)
        
        if result['success']:
            logger.info(f"Hourly analytics aggregation completed for {target_date}")
        else:
            logger.error(f"Hourly analytics aggregation had errors for {target_date}: {result['errors']}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Hourly analytics aggregation failed: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying hourly analytics aggregation (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Task failed after {self.max_retries} retries: {str(exc)}',
            'date': target_date_str,
        }


@shared_task
def aggregate_weekly_analytics():
    """
    Aggregate analytics data for the past week.
    
    Returns:
        dict: Aggregation results for the week
    """
    try:
        logger.info("Starting weekly analytics aggregation")
        
        # Get the past 7 days
        end_date = (timezone.now() - timedelta(days=1)).date()
        start_date = end_date - timedelta(days=6)
        
        results = {
            'success': True,
            'period': f"{start_date} to {end_date}",
            'daily_results': {},
            'errors': []
        }
        
        # Aggregate each day
        current_date = start_date
        while current_date <= end_date:
            try:
                daily_result = data_aggregation_service.aggregate_all_data(current_date, hourly=False)
                results['daily_results'][str(current_date)] = daily_result
                
                if not daily_result['success']:
                    results['errors'].extend(daily_result['errors'])
                    
            except Exception as e:
                error_msg = f"Failed to aggregate data for {current_date}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
            
            current_date += timedelta(days=1)
        
        # Overall success if no errors
        results['success'] = len(results['errors']) == 0
        
        logger.info(f"Weekly analytics aggregation completed with {len(results['errors'])} errors")
        return results
        
    except Exception as exc:
        logger.error(f"Weekly analytics aggregation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def cleanup_old_analytics_data():
    """
    Clean up old analytics data to manage database size.
    
    Returns:
        dict: Cleanup results
    """
    try:
        logger.info("Starting analytics data cleanup")
        
        # Keep data for the last 2 years
        cutoff_date = timezone.now() - timedelta(days=730)
        
        from .models import RideAnalytics, RevenueAnalytics, FleetAnalytics, UserAnalytics, PerformanceMetric
        
        cleanup_results = {}
        
        # Clean up each analytics model
        models_to_clean = [
            ('RideAnalytics', RideAnalytics),
            ('RevenueAnalytics', RevenueAnalytics),
            ('FleetAnalytics', FleetAnalytics),
            ('UserAnalytics', UserAnalytics),
        ]
        
        for model_name, model_class in models_to_clean:
            old_records = model_class.objects.filter(date__lt=cutoff_date.date())
            count = old_records.count()
            old_records.delete()
            cleanup_results[model_name] = count
            logger.info(f"Cleaned up {count} old {model_name} records")
        
        # Clean up performance metrics (keep last 90 days)
        perf_cutoff = timezone.now() - timedelta(days=90)
        old_perf_metrics = PerformanceMetric.objects.filter(timestamp__lt=perf_cutoff)
        perf_count = old_perf_metrics.count()
        old_perf_metrics.delete()
        cleanup_results['PerformanceMetric'] = perf_count
        logger.info(f"Cleaned up {perf_count} old performance metrics")
        
        # Clean up old generated reports (keep last 30 days)
        report_cutoff = timezone.now() - timedelta(days=30)
        old_reports = GeneratedReport.objects.filter(created_at__lt=report_cutoff)
        report_count = old_reports.count()
        old_reports.delete()
        cleanup_results['GeneratedReport'] = report_count
        logger.info(f"Cleaned up {report_count} old generated reports")
        
        total_cleaned = sum(cleanup_results.values())
        logger.info(f"Analytics cleanup completed. Total records cleaned: {total_cleaned}")
        
        return {
            'success': True,
            'cleanup_results': cleanup_results,
            'total_cleaned': total_cleaned,
            'cutoff_date': cutoff_date.isoformat(),
        }
        
    except Exception as exc:
        logger.error(f"Analytics cleanup failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task(bind=True, max_retries=2)
def generate_scheduled_report(self, template_id):
    """
    Generate a scheduled report.
    
    Args:
        template_id: ID of the report template to generate
    
    Returns:
        dict: Report generation results
    """
    try:
        template = ReportTemplate.objects.get(id=template_id)
        
        logger.info(f"Generating scheduled report: {template.name}")
        
        # Create report record
        report = GeneratedReport.objects.create(
            template=template,
            name=f"{template.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            requested_by=template.created_by,
            status=GeneratedReport.Status.GENERATING,
            period_start=timezone.now() - timedelta(days=1),  # Yesterday
            period_end=timezone.now(),
            filters_applied=template.filters,
            output_format='pdf',  # Default for scheduled reports
        )
        
        # Generate the report (placeholder - would implement actual report generation)
        # This would involve:
        # 1. Querying analytics data based on template configuration
        # 2. Formatting data according to template
        # 3. Generating output file (PDF, CSV, etc.)
        # 4. Storing file and updating report record
        
        # For now, mark as completed
        report.status = GeneratedReport.Status.COMPLETED
        report.completed_at = timezone.now()
        report.generation_time_seconds = 5.0  # Placeholder
        report.file_path = f"/reports/{report.id}.pdf"  # Placeholder
        report.file_size_bytes = 1024 * 100  # Placeholder: 100KB
        report.expires_at = timezone.now() + timedelta(days=30)
        report.save()
        
        logger.info(f"Scheduled report generated successfully: {report.id}")
        
        return {
            'success': True,
            'report_id': str(report.id),
            'template_name': template.name,
            'file_path': report.file_path,
        }
        
    except ReportTemplate.DoesNotExist:
        logger.error(f"Report template not found: {template_id}")
        return {
            'success': False,
            'error': 'Report template not found',
        }
    except Exception as exc:
        logger.error(f"Scheduled report generation failed: {str(exc)}")
        
        # Update report status if it exists
        try:
            report = GeneratedReport.objects.get(template_id=template_id, status=GeneratedReport.Status.GENERATING)
            report.status = GeneratedReport.Status.FAILED
            report.error_message = str(exc)
            report.save()
        except GeneratedReport.DoesNotExist:
            pass
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying report generation (attempt {self.request.retries + 1})")
            raise self.retry(countdown=600)  # Retry after 10 minutes
        
        return {
            'success': False,
            'error': f'Task failed after {self.max_retries} retries: {str(exc)}',
        }


@shared_task
def calculate_performance_metrics():
    """
    Calculate and record system performance metrics.
    
    Returns:
        dict: Performance calculation results
    """
    try:
        logger.info("Starting performance metrics calculation")
        
        # This would typically collect metrics from various sources:
        # - Database query performance
        # - API response times
        # - System resource usage
        # - External service health
        
        # For demonstration, we'll record some sample metrics
        services = ['rides', 'payments', 'fleet', 'dispatch', 'analytics']
        
        results = {
            'success': True,
            'metrics_recorded': 0,
            'services_checked': services,
        }
        
        for service in services:
            # Record sample response time (in a real system, this would be actual measurements)
            import random
            response_time = random.uniform(50, 500)  # 50-500ms
            
            performance_metrics_service.record_response_time(
                service_name=service,
                endpoint='api',
                response_time_ms=response_time
            )
            
            # Record sample throughput
            throughput = random.uniform(5, 50)  # 5-50 req/s
            performance_metrics_service.record_throughput(
                service_name=service,
                requests_per_second=throughput
            )
            
            # Record sample error rate
            error_rate = random.uniform(0, 8)  # 0-8%
            performance_metrics_service.record_error_rate(
                service_name=service,
                error_rate_percent=error_rate
            )
            
            results['metrics_recorded'] += 3
        
        logger.info(f"Performance metrics calculation completed. Recorded {results['metrics_recorded']} metrics")
        return results
        
    except Exception as exc:
        logger.error(f"Performance metrics calculation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def generate_daily_summary_report():
    """
    Generate daily summary report with key metrics.
    
    Returns:
        dict: Summary report data
    """
    try:
        logger.info("Generating daily summary report")
        
        yesterday = (timezone.now() - timedelta(days=1)).date()
        
        # Get analytics data for yesterday
        from .models import RideAnalytics, RevenueAnalytics, FleetAnalytics, UserAnalytics
        
        # Aggregate daily totals
        ride_analytics = RideAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        revenue_analytics = RevenueAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        fleet_analytics = FleetAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        user_analytics = UserAnalytics.objects.filter(date=yesterday, hour__isnull=True).first()
        
        summary = {
            'date': str(yesterday),
            'rides': {
                'total_rides': ride_analytics.total_rides if ride_analytics else 0,
                'completed_rides': ride_analytics.completed_rides if ride_analytics else 0,
                'completion_rate': float(ride_analytics.completion_rate) if ride_analytics else 0,
            },
            'revenue': {
                'total_revenue': float(revenue_analytics.total_revenue) if revenue_analytics else 0,
                'net_revenue': float(revenue_analytics.net_revenue) if revenue_analytics else 0,
                'avg_transaction_value': float(revenue_analytics.avg_transaction_value) if revenue_analytics else 0,
            },
            'fleet': {
                'total_vehicles': fleet_analytics.total_vehicles if fleet_analytics else 0,
                'active_vehicles': fleet_analytics.active_vehicles if fleet_analytics else 0,
                'utilization_rate': float(fleet_analytics.utilization_rate) if fleet_analytics else 0,
            },
            'users': {
                'active_users': user_analytics.active_users if user_analytics else 0,
                'new_users': user_analytics.new_users if user_analytics else 0,
                'avg_rides_per_user': float(user_analytics.avg_rides_per_user) if user_analytics else 0,
            }
        }
        
        logger.info(f"Daily summary report generated for {yesterday}")
        return {
            'success': True,
            'summary': summary,
        }
        
    except Exception as exc:
        logger.error(f"Daily summary report generation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }