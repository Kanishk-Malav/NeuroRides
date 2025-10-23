"""
API views for real-time WebSocket management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from accounts.permissions import IsOperatorOrAdmin, IsRider
from rides.models import Ride
from .services import RideTrackingService, FleetMonitoringService, NotificationService
from .utils import (
    notify_ride_status_change,
    notify_vehicle_location_update,
    notify_user,
    notify_system_alert
)

User = get_user_model()


class RideTrackingViewSet(viewsets.ViewSet):
    """ViewSet for ride tracking WebSocket management."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def tracking_data(self, request, pk=None):
        """Get comprehensive ride tracking data."""
        ride = get_object_or_404(Ride, id=pk)
        
        # Check permissions
        if not (request.user == ride.rider or 
                request.user.is_operator or 
                request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tracking_data = RideTrackingService.get_ride_tracking_data(str(ride.id))
        
        if tracking_data:
            return Response(tracking_data)
        else:
            return Response(
                {'error': 'Unable to get tracking data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def notify_progress(self, request, pk=None):
        """Notify about ride progress (for operators/drivers)."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ride = get_object_or_404(Ride, id=pk)
        progress_data = request.data
        
        RideTrackingService.notify_ride_progress_update(str(ride.id), progress_data)
        
        return Response({'message': 'Progress notification sent'})
    
    @action(detail=True, methods=['post'])
    def notify_driver_arrival(self, request, pk=None):
        """Notify that driver has arrived at pickup location."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ride = get_object_or_404(Ride, id=pk)
        vehicle_data = request.data.get('vehicle', {})
        
        RideTrackingService.notify_driver_arrival(str(ride.id), vehicle_data)
        
        return Response({'message': 'Driver arrival notification sent'})
    
    @action(detail=True, methods=['post'])
    def notify_ride_started(self, request, pk=None):
        """Notify that ride has started."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ride = get_object_or_404(Ride, id=pk)
        
        RideTrackingService.notify_ride_started(str(ride.id))
        
        return Response({'message': 'Ride started notification sent'})
    
    @action(detail=True, methods=['post'])
    def notify_ride_completed(self, request, pk=None):
        """Notify that ride has been completed."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ride = get_object_or_404(Ride, id=pk)
        completion_data = request.data
        
        RideTrackingService.notify_ride_completed(str(ride.id), completion_data)
        
        return Response({'message': 'Ride completion notification sent'})


class FleetMonitoringViewSet(viewsets.ViewSet):
    """ViewSet for fleet monitoring WebSocket management."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    @action(detail=False, methods=['get'])
    def fleet_summary(self, request):
        """Get fleet summary statistics."""
        summary = FleetMonitoringService.get_fleet_summary()
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def vehicle_list(self, request):
        """Get list of vehicles with optional filtering."""
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 100))
        
        vehicles = FleetMonitoringService.get_vehicle_list(status_filter, limit)
        
        return Response({
            'vehicles': vehicles,
            'count': len(vehicles),
            'filter': status_filter
        })
    
    @action(detail=False, methods=['get'])
    def maintenance_alerts(self, request):
        """Get current maintenance alerts."""
        alerts = FleetMonitoringService.get_maintenance_alerts()
        
        return Response({
            'alerts': alerts,
            'count': len(alerts)
        })
    
    @action(detail=False, methods=['post'])
    def broadcast_fleet_update(self, request):
        """Broadcast fleet update to all monitoring clients."""
        change_type = request.data.get('change_type', 'general_update')
        data = request.data.get('data', {})
        
        FleetMonitoringService.notify_fleet_status_change(change_type, data)
        
        return Response({'message': 'Fleet update broadcasted'})


class NotificationViewSet(viewsets.ViewSet):
    """ViewSet for notification management."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send_user_notification(self, request):
        """Send notification to specific user."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_id = request.data.get('user_id')
        notification_type = request.data.get('type', 'general')
        title = request.data.get('title', '')
        message = request.data.get('message', '')
        additional_data = request.data.get('additional_data', {})
        
        if not user_id or not title or not message:
            return Response(
                {'error': 'user_id, title, and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user exists
        try:
            User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        NotificationService.send_user_notification(
            user_id, notification_type, title, message, additional_data
        )
        
        return Response({'message': 'Notification sent'})
    
    @action(detail=False, methods=['post'])
    def send_role_notification(self, request):
        """Send notification to all users with specific role."""
        if not (request.user.is_operator or request.user.is_admin_user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role = request.data.get('role')
        notification_type = request.data.get('type', 'general')
        title = request.data.get('title', '')
        message = request.data.get('message', '')
        additional_data = request.data.get('additional_data', {})
        
        if not role or not title or not message:
            return Response(
                {'error': 'role, title, and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if role not in ['rider', 'operator', 'admin']:
            return Response(
                {'error': 'Invalid role. Must be rider, operator, or admin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        NotificationService.send_role_based_notification(
            role, notification_type, title, message, additional_data
        )
        
        return Response({'message': f'Notification sent to all {role}s'})
    
    @action(detail=False, methods=['post'])
    def send_system_alert(self, request):
        """Send system-wide alert."""
        if not request.user.is_admin_user:
            return Response(
                {'error': 'Admin permission required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        title = request.data.get('title', '')
        message = request.data.get('message', '')
        severity = request.data.get('severity', 'info')
        additional_data = request.data.get('additional_data', {})
        
        if not title or not message:
            return Response(
                {'error': 'title and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if severity not in ['info', 'warning', 'error', 'critical']:
            return Response(
                {'error': 'Invalid severity. Must be info, warning, error, or critical'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        NotificationService.send_system_wide_notification(
            'system_alert', title, message, severity, additional_data
        )
        
        return Response({'message': 'System alert sent'})
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsRider])
    def test_notification(self, request):
        """Test notification for current user (riders only)."""
        NotificationService.send_user_notification(
            request.user.id,
            'test',
            'Test Notification',
            'This is a test notification to verify WebSocket connectivity.',
            {'test': True}
        )
        
        return Response({'message': 'Test notification sent'})