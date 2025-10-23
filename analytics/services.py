"""
Analytics data aggregation services.
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.db import models, transaction
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Max, Min, Q, F
from django.contrib.auth import get_user_model

from .models import (
    AnalyticsMetric, RideAnalytics, RevenueAnalytics, 
    FleetAnalytics, UserAnalytics, PerformanceMetric
)
from rides.models import Ride
from payments.models import Payment, PaymentRefund
from fleet.models import Vehicle, VehicleTelemetry
from accounts.models import User

logger = logging.getLogger(__name__)


class DataAggregationService:
    """Service for aggregating data into analytics models."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def aggregate_ride_data(self, target_date: date, hourly: bool = False) -> Dict[str, Any]:
        """Aggregate ride data for a specific date."""
        try:
            results = {}
            
            if hourly:
                # Aggregate hourly data
                for hour in range(24):
                    hour_start = timezone.make_aware(
                        datetime.combine(target_date, datetime.min.time().replace(hour=hour))
                    )
                    hour_end = hour_start + timedelta(hours=1)
                    
                    analytics = self._aggregate_rides_for_period(hour_start, hour_end, target_date, hour)
                    results[f"hour_{hour}"] = analytics
            else:
                # Aggregate daily data
                day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                analytics = self._aggregate_rides_for_period(day_start, day_end, target_date)
                results["daily"] = analytics
            
            return {
                'success': True,
                'date': target_date,
                'results': results,
            }
            
        except Exception as e:
            self.logger.error(f"Ride data aggregation failed for {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date,
            }
    
    def _aggregate_rides_for_period(self, start_time: datetime, end_time: datetime, 
                                  target_date: date, hour: Optional[int] = None) -> RideAnalytics:
        """Aggregate ride data for a specific time period."""
        
        # Get rides in the time period
        rides = Ride.objects.filter(
            requested_at__gte=start_time,
            requested_at__lt=end_time
        )
        
        # Calculate metrics
        total_rides = rides.count()
        completed_rides = rides.filter(status=Ride.Status.COMPLETED).count()
        cancelled_rides = rides.filter(status=Ride.Status.CANCELLED).count()
        failed_rides = rides.filter(status=Ride.Status.PAYMENT_FAILED).count()
        
        # Distance and duration metrics
        completed_ride_stats = rides.filter(status=Ride.Status.COMPLETED).aggregate(
            total_distance=Sum('actual_distance_km'),
            total_duration=Sum('actual_duration_minutes'),
            avg_distance=Avg('actual_distance_km'),
            avg_duration=Avg('actual_duration_minutes'),
        )
        
        # Wait time metrics
        wait_time_stats = rides.filter(
            status__in=[Ride.Status.COMPLETED, Ride.Status.IN_PROGRESS]
        ).aggregate(
            avg_wait_time=Avg(
                models.F('picked_up_at') - models.F('requested_at'),
                output_field=models.DurationField()
            ),
            max_wait_time=Max(
                models.F('picked_up_at') - models.F('requested_at'),
                output_field=models.DurationField()
            ),
        )
        
        # Convert wait times to minutes
        avg_wait_minutes = Decimal('0.00')
        max_wait_minutes = 0
        
        if wait_time_stats['avg_wait_time']:
            avg_wait_minutes = Decimal(wait_time_stats['avg_wait_time'].total_seconds() / 60)
        
        if wait_time_stats['max_wait_time']:
            max_wait_minutes = int(wait_time_stats['max_wait_time'].total_seconds() / 60)
        
        # Check if this is a peak hour (7-9 AM or 5-7 PM)
        is_peak_hour = hour is not None and (7 <= hour <= 9 or 17 <= hour <= 19)
        
        # Calculate average surge multiplier (if available in ride data)
        surge_multiplier_avg = Decimal('1.00')  # Default, would need surge data from rides
        
        # Create or update analytics record
        analytics, created = RideAnalytics.objects.update_or_create(
            date=target_date,
            hour=hour,
            defaults={
                'total_rides': total_rides,
                'completed_rides': completed_rides,
                'cancelled_rides': cancelled_rides,
                'failed_rides': failed_rides,
                'total_distance_km': completed_ride_stats['total_distance'] or Decimal('0.00'),
                'total_duration_minutes': completed_ride_stats['total_duration'] or 0,
                'avg_distance_km': completed_ride_stats['avg_distance'] or Decimal('0.00'),
                'avg_duration_minutes': completed_ride_stats['avg_duration'] or Decimal('0.00'),
                'avg_wait_time_minutes': avg_wait_minutes,
                'max_wait_time_minutes': max_wait_minutes,
                'is_peak_hour': is_peak_hour,
                'surge_multiplier_avg': surge_multiplier_avg,
            }
        )
        
        return analytics
    
    def aggregate_revenue_data(self, target_date: date, hourly: bool = False) -> Dict[str, Any]:
        """Aggregate revenue data for a specific date."""
        try:
            results = {}
            
            if hourly:
                # Aggregate hourly data
                for hour in range(24):
                    hour_start = timezone.make_aware(
                        datetime.combine(target_date, datetime.min.time().replace(hour=hour))
                    )
                    hour_end = hour_start + timedelta(hours=1)
                    
                    analytics = self._aggregate_revenue_for_period(hour_start, hour_end, target_date, hour)
                    results[f"hour_{hour}"] = analytics
            else:
                # Aggregate daily data
                day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                analytics = self._aggregate_revenue_for_period(day_start, day_end, target_date)
                results["daily"] = analytics
            
            return {
                'success': True,
                'date': target_date,
                'results': results,
            }
            
        except Exception as e:
            self.logger.error(f"Revenue data aggregation failed for {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date,
            }
    
    def _aggregate_revenue_for_period(self, start_time: datetime, end_time: datetime,
                                    target_date: date, hour: Optional[int] = None) -> RevenueAnalytics:
        """Aggregate revenue data for a specific time period."""
        
        # Get payments in the time period
        payments = Payment.objects.filter(
            created_at__gte=start_time,
            created_at__lt=end_time,
            status=Payment.PaymentStatus.COMPLETED
        )
        
        # Calculate revenue metrics
        revenue_stats = payments.aggregate(
            total_revenue=Sum('amount'),
            base_fare_revenue=Sum('base_fare'),
            distance_fare_revenue=Sum('distance_fare'),
            time_fare_revenue=Sum('time_fare'),
            surge_revenue=Sum('surge_amount'),
            tip_revenue=Sum('tip_amount'),
            booking_fees=Sum('booking_fee'),
            tax_amount=Sum('tax_amount'),
            discount_amount=Sum('discount_amount'),
            avg_transaction_value=Avg('amount'),
        )
        
        # Get refund data
        refunds = PaymentRefund.objects.filter(
            created_at__gte=start_time,
            created_at__lt=end_time,
            status=PaymentRefund.Status.COMPLETED
        )
        
        refund_amount = refunds.aggregate(
            total_refunds=Sum('amount')
        )['total_refunds'] or Decimal('0.00')
        
        # Transaction counts
        total_transactions = payments.count()
        failed_payments = Payment.objects.filter(
            created_at__gte=start_time,
            created_at__lt=end_time,
            status=Payment.PaymentStatus.FAILED
        ).count()
        
        # Calculate net revenue
        gross_revenue = revenue_stats['total_revenue'] or Decimal('0.00')
        net_revenue = gross_revenue - refund_amount
        
        # Create or update analytics record
        analytics, created = RevenueAnalytics.objects.update_or_create(
            date=target_date,
            hour=hour,
            defaults={
                'total_revenue': gross_revenue,
                'gross_revenue': gross_revenue,
                'net_revenue': net_revenue,
                'base_fare_revenue': revenue_stats['base_fare_revenue'] or Decimal('0.00'),
                'distance_fare_revenue': revenue_stats['distance_fare_revenue'] or Decimal('0.00'),
                'time_fare_revenue': revenue_stats['time_fare_revenue'] or Decimal('0.00'),
                'surge_revenue': revenue_stats['surge_revenue'] or Decimal('0.00'),
                'tip_revenue': revenue_stats['tip_revenue'] or Decimal('0.00'),
                'booking_fees': revenue_stats['booking_fees'] or Decimal('0.00'),
                'tax_amount': revenue_stats['tax_amount'] or Decimal('0.00'),
                'discount_amount': revenue_stats['discount_amount'] or Decimal('0.00'),
                'refund_amount': refund_amount,
                'total_transactions': total_transactions,
                'successful_transactions': total_transactions,
                'failed_transactions': failed_payments,
                'avg_transaction_value': revenue_stats['avg_transaction_value'] or Decimal('0.00'),
                'avg_ride_fare': revenue_stats['avg_transaction_value'] or Decimal('0.00'),
            }
        )
        
        return analytics
    
    def aggregate_fleet_data(self, target_date: date, hourly: bool = False) -> Dict[str, Any]:
        """Aggregate fleet data for a specific date."""
        try:
            results = {}
            
            if hourly:
                # Aggregate hourly data
                for hour in range(24):
                    hour_start = timezone.make_aware(
                        datetime.combine(target_date, datetime.min.time().replace(hour=hour))
                    )
                    hour_end = hour_start + timedelta(hours=1)
                    
                    analytics = self._aggregate_fleet_for_period(hour_start, hour_end, target_date, hour)
                    results[f"hour_{hour}"] = analytics
            else:
                # Aggregate daily data
                day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                analytics = self._aggregate_fleet_for_period(day_start, day_end, target_date)
                results["daily"] = analytics
            
            return {
                'success': True,
                'date': target_date,
                'results': results,
            }
            
        except Exception as e:
            self.logger.error(f"Fleet data aggregation failed for {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date,
            }
    
    def _aggregate_fleet_for_period(self, start_time: datetime, end_time: datetime,
                                  target_date: date, hour: Optional[int] = None) -> FleetAnalytics:
        """Aggregate fleet data for a specific time period."""
        
        # Get vehicle counts by status
        total_vehicles = Vehicle.objects.filter(is_active=True).count()
        
        # For simplicity, we'll use current status. In a real system, you'd track historical status
        vehicle_stats = Vehicle.objects.filter(is_active=True).aggregate(
            active_count=Count('id', filter=Q(status__in=[
                Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE
            ])),
            idle_count=Count('id', filter=Q(status=Vehicle.Status.IDLE)),
            maintenance_count=Count('id', filter=Q(status=Vehicle.Status.MAINTENANCE)),
        )
        
        active_vehicles = vehicle_stats['active_count'] or 0
        idle_vehicles = vehicle_stats['idle_count'] or 0
        maintenance_vehicles = vehicle_stats['maintenance_count'] or 0
        
        # Calculate utilization rate
        utilization_rate = Decimal('0.00')
        if total_vehicles > 0:
            utilization_rate = (Decimal(active_vehicles - idle_vehicles) / Decimal(total_vehicles)) * 100
        
        # Get ride data for fleet metrics
        rides_in_period = Ride.objects.filter(
            requested_at__gte=start_time,
            requested_at__lt=end_time,
            status=Ride.Status.COMPLETED
        )
        
        total_rides = rides_in_period.count()
        avg_rides_per_vehicle = Decimal('0.00')
        if active_vehicles > 0:
            avg_rides_per_vehicle = Decimal(total_rides) / Decimal(active_vehicles)
        
        # Get revenue per vehicle
        revenue_in_period = Payment.objects.filter(
            created_at__gte=start_time,
            created_at__lt=end_time,
            status=Payment.PaymentStatus.COMPLETED
        ).aggregate(total_revenue=Sum('amount'))['total_revenue'] or Decimal('0.00')
        
        avg_revenue_per_vehicle = Decimal('0.00')
        if active_vehicles > 0:
            avg_revenue_per_vehicle = revenue_in_period / Decimal(active_vehicles)
        
        # Distance metrics
        distance_stats = rides_in_period.aggregate(
            total_distance=Sum('actual_distance_km'),
            avg_distance=Avg('actual_distance_km'),
        )
        
        total_distance_driven = distance_stats['total_distance'] or Decimal('0.00')
        avg_distance_per_vehicle = Decimal('0.00')
        if active_vehicles > 0:
            avg_distance_per_vehicle = total_distance_driven / Decimal(active_vehicles)
        
        # Performance metrics (simplified)
        avg_response_time = rides_in_period.aggregate(
            avg_response=Avg(
                models.F('picked_up_at') - models.F('requested_at'),
                output_field=models.DurationField()
            )
        )['avg_response']
        
        avg_response_time_minutes = Decimal('0.00')
        if avg_response_time:
            avg_response_time_minutes = Decimal(avg_response_time.total_seconds() / 60)
        
        # Create or update analytics record
        analytics, created = FleetAnalytics.objects.update_or_create(
            date=target_date,
            hour=hour,
            defaults={
                'total_vehicles': total_vehicles,
                'active_vehicles': active_vehicles,
                'idle_vehicles': idle_vehicles,
                'maintenance_vehicles': maintenance_vehicles,
                'utilization_rate': utilization_rate,
                'avg_rides_per_vehicle': avg_rides_per_vehicle,
                'avg_revenue_per_vehicle': avg_revenue_per_vehicle,
                'total_distance_driven': total_distance_driven,
                'avg_distance_per_vehicle': avg_distance_per_vehicle,
                'avg_response_time_minutes': avg_response_time_minutes,
                'customer_rating_avg': Decimal('4.5'),  # Placeholder
                'fuel_efficiency_avg': Decimal('25.0'),  # Placeholder
                'vehicles_due_maintenance': 0,  # Would need maintenance scheduling data
                'maintenance_cost': Decimal('0.00'),  # Would need cost tracking
                'downtime_hours': Decimal('0.00'),  # Would need downtime tracking
            }
        )
        
        return analytics
    
    def aggregate_user_data(self, target_date: date, hourly: bool = False) -> Dict[str, Any]:
        """Aggregate user data for a specific date."""
        try:
            results = {}
            
            if hourly:
                # Aggregate hourly data
                for hour in range(24):
                    hour_start = timezone.make_aware(
                        datetime.combine(target_date, datetime.min.time().replace(hour=hour))
                    )
                    hour_end = hour_start + timedelta(hours=1)
                    
                    analytics = self._aggregate_users_for_period(hour_start, hour_end, target_date, hour)
                    results[f"hour_{hour}"] = analytics
            else:
                # Aggregate daily data
                day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                analytics = self._aggregate_users_for_period(day_start, day_end, target_date)
                results["daily"] = analytics
            
            return {
                'success': True,
                'date': target_date,
                'results': results,
            }
            
        except Exception as e:
            self.logger.error(f"User data aggregation failed for {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date,
            }
    
    def _aggregate_users_for_period(self, start_time: datetime, end_time: datetime,
                                  target_date: date, hour: Optional[int] = None) -> UserAnalytics:
        """Aggregate user data for a specific time period."""
        
        # Get user metrics
        total_users = User.objects.filter(date_joined__lte=end_time).count()
        new_users = User.objects.filter(
            date_joined__gte=start_time,
            date_joined__lt=end_time
        ).count()
        
        # Active users (users who made a ride in this period)
        active_users = User.objects.filter(
            rides__requested_at__gte=start_time,
            rides__requested_at__lt=end_time
        ).distinct().count()
        
        # Returning users (users who made rides before and also in this period)
        returning_users = User.objects.filter(
            rides__requested_at__gte=start_time,
            rides__requested_at__lt=end_time
        ).filter(
            rides__requested_at__lt=start_time
        ).distinct().count()
        
        # Engagement metrics
        user_ride_stats = Ride.objects.filter(
            requested_at__gte=start_time,
            requested_at__lt=end_time
        ).values('rider').annotate(
            ride_count=Count('id'),
            total_spend=Sum('final_fare')
        )
        
        avg_rides_per_user = Decimal('0.00')
        avg_spend_per_user = Decimal('0.00')
        
        if user_ride_stats:
            total_rides = sum(stat['ride_count'] for stat in user_ride_stats)
            total_spend = sum(stat['total_spend'] or Decimal('0.00') for stat in user_ride_stats)
            
            if active_users > 0:
                avg_rides_per_user = Decimal(total_rides) / Decimal(active_users)
                avg_spend_per_user = total_spend / Decimal(active_users)
        
        # Retention rate (simplified - users who used service in last 30 days)
        thirty_days_ago = start_time - timedelta(days=30)
        retention_users = User.objects.filter(
            rides__requested_at__gte=thirty_days_ago,
            rides__requested_at__lt=start_time
        ).filter(
            rides__requested_at__gte=start_time,
            rides__requested_at__lt=end_time
        ).distinct().count()
        
        user_retention_rate = Decimal('0.00')
        if active_users > 0:
            user_retention_rate = (Decimal(retention_users) / Decimal(active_users)) * 100
        
        # Create or update analytics record
        analytics, created = UserAnalytics.objects.update_or_create(
            date=target_date,
            hour=hour,
            defaults={
                'total_users': total_users,
                'new_users': new_users,
                'active_users': active_users,
                'returning_users': returning_users,
                'avg_rides_per_user': avg_rides_per_user,
                'avg_spend_per_user': avg_spend_per_user,
                'user_retention_rate': user_retention_rate,
                'avg_rating_given': Decimal('4.3'),  # Placeholder
                'complaint_rate': Decimal('2.5'),  # Placeholder
            }
        )
        
        return analytics
    
    def aggregate_all_data(self, target_date: date, hourly: bool = False) -> Dict[str, Any]:
        """Aggregate all analytics data for a specific date."""
        results = {
            'date': target_date,
            'hourly': hourly,
            'success': True,
            'aggregations': {},
            'errors': []
        }
        
        # Aggregate each data type
        aggregation_methods = [
            ('rides', self.aggregate_ride_data),
            ('revenue', self.aggregate_revenue_data),
            ('fleet', self.aggregate_fleet_data),
            ('users', self.aggregate_user_data),
        ]
        
        for data_type, method in aggregation_methods:
            try:
                result = method(target_date, hourly)
                results['aggregations'][data_type] = result
                
                if not result['success']:
                    results['errors'].append(f"{data_type}: {result['error']}")
                    
            except Exception as e:
                error_msg = f"Failed to aggregate {data_type} data: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        # Overall success if no errors
        results['success'] = len(results['errors']) == 0
        
        return results


class PerformanceMetricsService:
    """Service for collecting and analyzing performance metrics."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def record_response_time(self, service_name: str, endpoint: str, 
                           response_time_ms: float) -> PerformanceMetric:
        """Record API response time metric."""
        
        metric = PerformanceMetric.objects.create(
            category=PerformanceMetric.MetricCategory.RESPONSE_TIME,
            metric_name=f"{service_name}_{endpoint}_response_time",
            service_name=service_name,
            timestamp=timezone.now(),
            value=Decimal(str(response_time_ms)),
            unit='ms',
            warning_threshold=Decimal('1000'),  # 1 second
            critical_threshold=Decimal('5000'),  # 5 seconds
            is_healthy=response_time_ms < 1000,
            metadata={
                'endpoint': endpoint,
                'service': service_name,
            }
        )
        
        return metric
    
    def record_throughput(self, service_name: str, requests_per_second: float) -> PerformanceMetric:
        """Record throughput metric."""
        
        metric = PerformanceMetric.objects.create(
            category=PerformanceMetric.MetricCategory.THROUGHPUT,
            metric_name=f"{service_name}_throughput",
            service_name=service_name,
            timestamp=timezone.now(),
            value=Decimal(str(requests_per_second)),
            unit='req/s',
            warning_threshold=Decimal('10'),  # Below 10 req/s
            critical_threshold=Decimal('5'),   # Below 5 req/s
            is_healthy=requests_per_second >= 10,
            metadata={
                'service': service_name,
            }
        )
        
        return metric
    
    def record_error_rate(self, service_name: str, error_rate_percent: float) -> PerformanceMetric:
        """Record error rate metric."""
        
        metric = PerformanceMetric.objects.create(
            category=PerformanceMetric.MetricCategory.ERROR_RATE,
            metric_name=f"{service_name}_error_rate",
            service_name=service_name,
            timestamp=timezone.now(),
            value=Decimal(str(error_rate_percent)),
            unit='%',
            warning_threshold=Decimal('5'),   # 5% error rate
            critical_threshold=Decimal('10'), # 10% error rate
            is_healthy=error_rate_percent < 5,
            metadata={
                'service': service_name,
            }
        )
        
        return metric
    
    def get_service_health_summary(self, service_name: str, 
                                 hours_back: int = 24) -> Dict[str, Any]:
        """Get health summary for a service."""
        
        since = timezone.now() - timedelta(hours=hours_back)
        
        metrics = PerformanceMetric.objects.filter(
            service_name=service_name,
            timestamp__gte=since
        )
        
        # Calculate averages by category
        summary = {}
        
        for category in PerformanceMetric.MetricCategory.values:
            category_metrics = metrics.filter(category=category)
            
            if category_metrics.exists():
                stats = category_metrics.aggregate(
                    avg_value=Avg('value'),
                    min_value=Min('value'),
                    max_value=Max('value'),
                    healthy_count=Count('id', filter=Q(is_healthy=True)),
                    total_count=Count('id')
                )
                
                health_percentage = 0
                if stats['total_count'] > 0:
                    health_percentage = (stats['healthy_count'] / stats['total_count']) * 100
                
                summary[category] = {
                    'average': float(stats['avg_value'] or 0),
                    'minimum': float(stats['min_value'] or 0),
                    'maximum': float(stats['max_value'] or 0),
                    'health_percentage': health_percentage,
                    'total_measurements': stats['total_count'],
                }
        
        return {
            'service_name': service_name,
            'period_hours': hours_back,
            'summary': summary,
            'overall_health': self._calculate_overall_health(summary),
        }
    
    def _calculate_overall_health(self, summary: Dict[str, Any]) -> float:
        """Calculate overall health score from category summaries."""
        if not summary:
            return 0.0
        
        health_scores = [
            category_data['health_percentage'] 
            for category_data in summary.values()
        ]
        
        return sum(health_scores) / len(health_scores) if health_scores else 0.0


# Global service instances
data_aggregation_service = DataAggregationService()
performance_metrics_service = PerformanceMetricsService()