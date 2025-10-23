"""
Celery tasks for dispatch app.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from .models import DispatchRequest
from .queue import DispatchQueue
from .services import DispatchService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_dispatch_request(self, dispatch_request_id):
    """
    Process a single dispatch request.
    
    Args:
        dispatch_request_id: ID of the dispatch request to process
    
    Returns:
        dict: Processing result with success status and details
    """
    try:
        dispatch_request = DispatchRequest.objects.select_related(
            'ride__rider',
            'assigned_vehicle'
        ).get(id=dispatch_request_id)
        
        logger.info(f"Processing dispatch request {dispatch_request_id}")
        
        # Check if request is still valid
        if dispatch_request.status != DispatchRequest.Status.PENDING:
            logger.warning(
                f"Dispatch request {dispatch_request_id} is not in pending status: {dispatch_request.status}"
            )
            return {
                'success': False,
                'error': f'Request not in pending status: {dispatch_request.status}',
                'dispatch_request_id': dispatch_request_id
            }
        
        # Check if request has expired
        if dispatch_request.is_expired:
            dispatch_request.expire_request()
            logger.warning(f"Dispatch request {dispatch_request_id} has expired")
            return {
                'success': False,
                'error': 'Request has expired',
                'dispatch_request_id': dispatch_request_id
            }
        
        # Process the dispatch
        dispatch_service = DispatchService()
        result = dispatch_service.process_single_dispatch(dispatch_request)
        
        if result['success']:
            logger.info(
                f"Successfully processed dispatch request {dispatch_request_id}: "
                f"assigned vehicle {result.get('vehicle_id')}"
            )
        else:
            logger.error(
                f"Failed to process dispatch request {dispatch_request_id}: {result.get('error')}"
            )
        
        return result
        
    except DispatchRequest.DoesNotExist:
        error_msg = f"Dispatch request {dispatch_request_id} not found"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'dispatch_request_id': dispatch_request_id
        }
    
    except Exception as exc:
        logger.error(
            f"Error processing dispatch request {dispatch_request_id}: {str(exc)}",
            exc_info=True
        )
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying dispatch request {dispatch_request_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        # Mark as failed after max retries
        try:
            dispatch_request = DispatchRequest.objects.get(id=dispatch_request_id)
            dispatch_request.status = DispatchRequest.Status.FAILED
            dispatch_request.failure_reason = f"Task failed after {self.max_retries} retries: {str(exc)}"
            dispatch_request.save(update_fields=['status', 'failure_reason'])
        except DispatchRequest.DoesNotExist:
            pass
        
        return {
            'success': False,
            'error': f'Task failed after retries: {str(exc)}',
            'dispatch_request_id': dispatch_request_id
        }


@shared_task
def process_dispatch_queue(max_requests=50):
    """
    Process pending dispatch requests in the queue.
    
    Args:
        max_requests: Maximum number of requests to process
    
    Returns:
        dict: Processing results
    """
    logger.info(f"Starting dispatch queue processing (max_requests: {max_requests})")
    
    dispatch_queue = DispatchQueue()
    result = dispatch_queue.process_queue(max_requests=max_requests)
    
    logger.info(
        f"Dispatch queue processing completed: {result['processed']} processed, "
        f"{result['successful']} successful, {result['failed']} failed"
    )
    
    return result


@shared_task
def cleanup_expired_dispatch_requests():
    """
    Clean up expired dispatch requests.
    
    Returns:
        dict: Cleanup results
    """
    logger.info("Starting cleanup of expired dispatch requests")
    
    dispatch_service = DispatchService()
    count = dispatch_service.cleanup_expired_requests()
    
    logger.info(f"Cleaned up {count} expired dispatch requests")
    
    return {
        'cleaned_up': count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def retry_failed_dispatch_requests():
    """
    Retry failed dispatch requests that haven't exceeded retry limit.
    
    Returns:
        dict: Retry results
    """
    logger.info("Starting retry of failed dispatch requests")
    
    dispatch_service = DispatchService()
    count = dispatch_service.retry_failed_dispatches()
    
    logger.info(f"Retried {count} failed dispatch requests")
    
    return {
        'retried': count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def generate_daily_dispatch_metrics(date_str=None):
    """
    Generate daily dispatch metrics for a specific date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to yesterday)
    
    Returns:
        dict: Generated metrics
    """
    if date_str:
        try:
            from datetime import datetime
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            logger.error(f"Invalid date format: {date_str}")
            return {'error': f'Invalid date format: {date_str}'}
    else:
        # Default to yesterday
        target_date = (timezone.now() - timedelta(days=1)).date()
    
    logger.info(f"Generating daily dispatch metrics for {target_date}")
    
    dispatch_service = DispatchService()
    metrics = dispatch_service.generate_daily_metrics(target_date)
    
    logger.info(f"Generated {len(metrics)} metric records for {target_date}")
    
    return {
        'date': target_date.isoformat(),
        'metrics_generated': len(metrics),
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def monitor_dispatch_performance():
    """
    Monitor dispatch performance and send alerts if needed.
    
    Returns:
        dict: Monitoring results
    """
    logger.info("Starting dispatch performance monitoring")
    
    dispatch_service = DispatchService()
    
    # Get recent statistics
    stats = dispatch_service.get_dispatch_statistics(days=1)
    
    alerts = []
    
    # Check success rate
    if stats['success_rate'] < 80:
        alerts.append({
            'type': 'low_success_rate',
            'message': f"Dispatch success rate is {stats['success_rate']:.1f}% (below 80%)",
            'severity': 'high' if stats['success_rate'] < 60 else 'medium'
        })
    
    # Check average processing time
    if stats['average_processing_time_seconds'] and stats['average_processing_time_seconds'] > 30:
        alerts.append({
            'type': 'slow_processing',
            'message': f"Average processing time is {stats['average_processing_time_seconds']:.1f}s (above 30s)",
            'severity': 'medium'
        })
    
    # Check queue status
    dispatch_queue = DispatchQueue()
    queue_status = dispatch_queue.get_queue_status()
    
    if queue_status['pending_requests'] > 100:
        alerts.append({
            'type': 'large_queue',
            'message': f"Dispatch queue has {queue_status['pending_requests']} pending requests",
            'severity': 'high' if queue_status['pending_requests'] > 200 else 'medium'
        })
    
    # Check for old pending requests
    if queue_status['average_wait_time_seconds'] and queue_status['average_wait_time_seconds'] > 300:
        alerts.append({
            'type': 'long_wait_time',
            'message': f"Average wait time is {queue_status['average_wait_time_seconds']:.0f}s (above 5 minutes)",
            'severity': 'high'
        })
    
    # Log alerts
    for alert in alerts:
        if alert['severity'] == 'high':
            logger.error(f"DISPATCH ALERT: {alert['message']}")
        else:
            logger.warning(f"DISPATCH WARNING: {alert['message']}")
    
    logger.info(f"Dispatch performance monitoring completed: {len(alerts)} alerts generated")
    
    return {
        'alerts': alerts,
        'statistics': stats,
        'queue_status': queue_status,
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def update_vehicle_assignments():
    """
    Update vehicle assignments and handle assignment changes.
    
    Returns:
        dict: Update results
    """
    logger.info("Starting vehicle assignment updates")
    
    # Get all assigned dispatch requests
    assigned_requests = DispatchRequest.objects.filter(
        status=DispatchRequest.Status.ASSIGNED,
        assigned_vehicle__isnull=False
    ).select_related('assigned_vehicle', 'ride')
    
    updated_count = 0
    errors = []
    
    for dispatch_request in assigned_requests:
        try:
            vehicle = dispatch_request.assigned_vehicle
            
            # Check if vehicle is still available and in good condition
            if vehicle.status not in ['idle', 'assigned']:
                logger.warning(
                    f"Vehicle {vehicle.license_plate} is no longer available "
                    f"for dispatch request {dispatch_request.id} (status: {vehicle.status})"
                )
                continue
            
            # Check battery level
            if vehicle.battery_level < 20:
                logger.warning(
                    f"Vehicle {vehicle.license_plate} has low battery "
                    f"({vehicle.battery_level}%) for dispatch request {dispatch_request.id}"
                )
                continue
            
            # Update vehicle status if needed
            if vehicle.status == 'idle':
                vehicle.status = 'assigned'
                vehicle.save(update_fields=['status'])
                updated_count += 1
                
        except Exception as exc:
            error_msg = f"Error updating assignment for dispatch request {dispatch_request.id}: {str(exc)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    logger.info(f"Vehicle assignment updates completed: {updated_count} updated, {len(errors)} errors")
    
    return {
        'updated': updated_count,
        'errors': errors,
        'timestamp': timezone.now().isoformat()
    }