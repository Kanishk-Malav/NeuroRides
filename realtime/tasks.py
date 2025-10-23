"""
Celery tasks for real-time WebSocket communication.
"""

from celery import shared_task
from django.utils import timezone
import logging

from .fleet_monitoring import FleetAlertManager, FleetAnalytics, run_fleet_health_check
from .utils import notify_system_alert

logger = logging.getLogger(__name__)


@shared_task
def periodic_fleet_health_check():
    """Periodic task to check fleet health and send alerts."""
    try:
        result = run_fleet_health_check()
        logger.info(f"Fleet health check completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in fleet health check: {str(e)}")
        return {'error': str(e)}


@shared_task
def broadcast_fleet_status():
    """Broadcast current fleet status to all monitoring clients."""
    try:
        result = FleetAlertManager.send_fleet_status_broadcast()
        logger.info("Fleet status broadcast sent")
        return {'success': True, 'timestamp': result['timestamp']}
    except Exception as e:
        logger.error(f"Error broadcasting fleet status: {str(e)}")
        return {'error': str(e)}


@shared_task
def check_fleet_alerts():
    """Check for fleet alerts and send notifications."""
    try:
        alerts = FleetAlertManager.check_and_send_alerts()
        logger.info(f"Fleet alerts check completed: {len(alerts)} alerts sent")
        return {'alerts_sent': len(alerts), 'alerts': alerts}
    except Exception as e:
        logger.error(f"Error checking fleet alerts: {str(e)}")
        return {'error': str(e)}


@shared_task
def calculate_fleet_metrics():
    """Calculate and cache fleet performance metrics."""
    try:
        metrics = FleetAnalytics.get_real_time_metrics()
        health_score = FleetAnalytics.get_fleet_health_score()
        
        # Log critical metrics
        if health_score['health_score'] < 70:
            notify_system_alert(
                f"Fleet health score is low: {health_score['health_score']:.1f}%",
                severity='warning',
                target_roles=['operator', 'admin']
            )
        
        logger.info(f"Fleet metrics calculated: Health score {health_score['health_score']:.1f}%")
        
        return {
            'metrics': metrics,
            'health_score': health_score,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error calculating fleet metrics: {str(e)}")
        return {'error': str(e)}


@shared_task
def process_vehicle_telemetry_batch(telemetry_batch):
    """Process a batch of vehicle telemetry data."""
    from .fleet_monitoring import VehicleTelemetryProcessor
    
    processed_count = 0
    errors = []
    
    try:
        for telemetry_data in telemetry_batch:
            try:
                VehicleTelemetryProcessor.process_telemetry_update(telemetry_data)
                processed_count += 1
            except Exception as e:
                errors.append({
                    'vehicle_id': telemetry_data.get('vehicle_id'),
                    'error': str(e)
                })
        
        logger.info(f"Processed {processed_count} telemetry updates with {len(errors)} errors")
        
        return {
            'processed': processed_count,
            'errors': len(errors),
            'error_details': errors[:10]  # Limit error details
        }
    except Exception as e:
        logger.error(f"Error processing telemetry batch: {str(e)}")
        return {'error': str(e)}


@shared_task
def cleanup_old_websocket_data():
    """Clean up old WebSocket-related data."""
    from fleet.models import VehicleTelemetry
    from datetime import timedelta
    
    try:
        # Remove telemetry data older than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count = VehicleTelemetry.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old telemetry records")
        
        return {
            'deleted_telemetry_records': deleted_count,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error cleaning up old WebSocket data: {str(e)}")
        return {'error': str(e)}