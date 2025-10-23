"""
API views for dispatch app.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
import logging

from accounts.permissions import IsOperatorOrAdmin, IsAdmin
from .models import DispatchRequest, DispatchAlgorithmConfig, DispatchMetrics
from .serializers import (
    DispatchRequestSerializer,
    DispatchRequestCreateSerializer,
    DispatchAlgorithmConfigSerializer,
    DispatchMetricsSerializer,
    DispatchQueueStatusSerializer,
    DispatchStatisticsSerializer,
    DispatchProcessingResultSerializer,
)
from .queue import DispatchQueue
from .services import DispatchService

logger = logging.getLogger(__name__)


class DispatchRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing dispatch requests."""
    
    queryset = DispatchRequest.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'create':
            return DispatchRequestCreateSerializer
        return DispatchRequestSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters."""
        queryset = DispatchRequest.objects.select_related(
            'ride__rider',
            'assigned_vehicle'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by priority
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        # Filter by algorithm
        algorithm_filter = self.request.query_params.get('algorithm')
        if algorithm_filter:
            queryset = queryset.filter(algorithm_used=algorithm_filter)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=date_to)
            except ValueError:
                pass
        
        # Filter active requests only
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(
                status__in=[
                    DispatchRequest.Status.PENDING,
                    DispatchRequest.Status.PROCESSING,
                ]
            )
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new dispatch request."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create dispatch request
        dispatch_request = serializer.save()
        
        # Add to dispatch queue
        dispatch_queue = DispatchQueue()
        dispatch_queue.add_ride_to_queue(dispatch_request.ride, dispatch_request.priority)
        
        logger.info(
            f"Created dispatch request {dispatch_request.id} for ride {dispatch_request.ride.id}"
        )
        
        # Return full serialized data
        response_serializer = DispatchRequestSerializer(dispatch_request)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed dispatch request."""
        dispatch_request = self.get_object()
        
        if dispatch_request.status != DispatchRequest.Status.FAILED:
            return Response(
                {'error': 'Only failed dispatch requests can be retried.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if dispatch_request.retry_count >= 3:
            return Response(
                {'error': 'Maximum retry attempts reached.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset status and add back to queue
        dispatch_request.status = DispatchRequest.Status.PENDING
        dispatch_request.failure_reason = ''
        dispatch_request.save(update_fields=['status', 'failure_reason'])
        
        # Add to dispatch queue
        dispatch_queue = DispatchQueue()
        dispatch_queue.add_ride_to_queue(dispatch_request.ride, dispatch_request.priority)
        
        logger.info(f"Retrying dispatch request {dispatch_request.id}")
        
        serializer = self.get_serializer(dispatch_request)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def expire(self, request, pk=None):
        """Manually expire a dispatch request."""
        dispatch_request = self.get_object()
        
        if dispatch_request.status not in [
            DispatchRequest.Status.PENDING,
            DispatchRequest.Status.PROCESSING
        ]:
            return Response(
                {'error': 'Only pending or processing requests can be expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dispatch_request.expire_request()
        
        logger.info(f"Manually expired dispatch request {dispatch_request.id}")
        
        serializer = self.get_serializer(dispatch_request)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def queue_status(self, request):
        """Get current dispatch queue status."""
        dispatch_queue = DispatchQueue()
        queue_status = dispatch_queue.get_queue_status()
        
        serializer = DispatchQueueStatusSerializer(queue_status)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def process_queue(self, request):
        """Process dispatch queue."""
        max_requests = int(request.data.get('max_requests', 10))
        
        if max_requests > 100:
            return Response(
                {'error': 'Maximum 100 requests can be processed at once.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dispatch_queue = DispatchQueue()
        result = dispatch_queue.process_queue(max_requests=max_requests)
        
        logger.info(
            f"Processed {result['processed']} dispatch requests: "
            f"{result['successful']} successful, {result['failed']} failed"
        )
        
        serializer = DispatchProcessingResultSerializer(result)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get dispatch statistics."""
        days = int(request.query_params.get('days', 7))
        algorithm = request.query_params.get('algorithm')
        
        dispatch_service = DispatchService()
        stats = dispatch_service.get_dispatch_statistics(days=days, algorithm=algorithm)
        
        serializer = DispatchStatisticsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired dispatch requests."""
        dispatch_service = DispatchService()
        count = dispatch_service.cleanup_expired_requests()
        
        logger.info(f"Cleaned up {count} expired dispatch requests")
        
        return Response({
            'message': f'Cleaned up {count} expired dispatch requests.',
            'count': count
        })


class DispatchAlgorithmConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing dispatch algorithm configurations."""
    
    queryset = DispatchAlgorithmConfig.objects.all()
    serializer_class = DispatchAlgorithmConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = DispatchAlgorithmConfig.objects.order_by('-priority', 'name')
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an algorithm configuration."""
        config = self.get_object()
        config.is_active = True
        config.save(update_fields=['is_active'])
        
        logger.info(f"Activated dispatch algorithm: {config.name}")
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an algorithm configuration."""
        config = self.get_object()
        config.is_active = False
        config.save(update_fields=['is_active'])
        
        logger.info(f"Deactivated dispatch algorithm: {config.name}")
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active algorithm configurations."""
        active_configs = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(active_configs, many=True)
        return Response(serializer.data)


class DispatchMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing dispatch metrics."""
    
    queryset = DispatchMetrics.objects.all()
    serializer_class = DispatchMetricsSerializer
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = DispatchMetrics.objects.order_by('-date', 'algorithm_name')
        
        # Filter by algorithm
        algorithm = self.request.query_params.get('algorithm')
        if algorithm:
            queryset = queryset.filter(algorithm_name=algorithm)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.fromisoformat(date_from).date()
                queryset = queryset.filter(date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.fromisoformat(date_to).date()
                queryset = queryset.filter(date__lte=date_to)
            except ValueError:
                pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get metrics summary."""
        days = int(request.query_params.get('days', 30))
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        metrics = self.get_queryset().filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        # Aggregate metrics
        total_requests = sum(m.total_requests for m in metrics)
        total_successful = sum(m.successful_assignments for m in metrics)
        total_failed = sum(m.failed_assignments for m in metrics)
        total_expired = sum(m.expired_requests for m in metrics)
        
        success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        
        # Average processing time (weighted by request count)
        weighted_processing_times = [
            m.average_processing_time_seconds * m.total_requests
            for m in metrics
            if m.average_processing_time_seconds
        ]
        avg_processing_time = (
            sum(weighted_processing_times) / total_requests
            if total_requests > 0 and weighted_processing_times
            else None
        )
        
        # Algorithm distribution
        algorithm_stats = {}
        for metric in metrics:
            if metric.algorithm_name not in algorithm_stats:
                algorithm_stats[metric.algorithm_name] = {
                    'requests': 0,
                    'successful': 0,
                    'success_rate': 0
                }
            
            algorithm_stats[metric.algorithm_name]['requests'] += metric.total_requests
            algorithm_stats[metric.algorithm_name]['successful'] += metric.successful_assignments
        
        # Calculate success rates for each algorithm
        for algo_name, stats in algorithm_stats.items():
            if stats['requests'] > 0:
                stats['success_rate'] = (stats['successful'] / stats['requests']) * 100
        
        summary = {
            'period_days': days,
            'start_date': start_date,
            'end_date': end_date,
            'total_requests': total_requests,
            'successful_assignments': total_successful,
            'failed_assignments': total_failed,
            'expired_requests': total_expired,
            'success_rate': round(success_rate, 2),
            'average_processing_time_seconds': round(avg_processing_time, 2) if avg_processing_time else None,
            'algorithm_performance': algorithm_stats,
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def generate_daily_metrics(self, request):
        """Generate daily metrics for a specific date."""
        date_str = request.data.get('date')
        if not date_str:
            return Response(
                {'error': 'Date is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dispatch_service = DispatchService()
        metrics = dispatch_service.generate_daily_metrics(target_date)
        
        serializer = self.get_serializer(metrics, many=True)
        return Response(serializer.data)