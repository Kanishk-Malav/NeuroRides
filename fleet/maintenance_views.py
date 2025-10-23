"""
Additional views for maintenance scheduling and management.
"""

from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsOperatorOrAdmin, IsOperator

from .models import Vehicle, MaintenanceRecord
from .services import MaintenanceScheduler, FleetAnalytics
from .serializers import MaintenanceRecordSerializer


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsOperator])
def auto_schedule_maintenance(request):
    """Automatically schedule maintenance for vehicles that need it."""
    
    force = request.data.get('force', False)
    
    try:
        scheduled_count = MaintenanceScheduler.auto_schedule_maintenance()
        
        return Response({
            'message': f'Successfully scheduled maintenance for {scheduled_count} vehicles',
            'scheduled_count': scheduled_count,
            'timestamp': timezone.now()
        })
    
    except Exception as e:
        return Response({
            'error': f'Failed to schedule maintenance: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def maintenance_schedule(request):
    """Get maintenance schedule for the next N days."""
    
    days_ahead = int(request.query_params.get('days', 30))
    
    schedule = MaintenanceScheduler.get_maintenance_schedule(days_ahead)
    serializer = MaintenanceRecordSerializer(schedule, many=True)
    
    return Response({
        'days_ahead': days_ahead,
        'total_scheduled': len(schedule),
        'schedule': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def overdue_maintenance(request):
    """Get overdue maintenance records."""
    
    overdue_records = MaintenanceScheduler.get_overdue_maintenance()
    serializer = MaintenanceRecordSerializer(overdue_records, many=True)
    
    return Response({
        'total_overdue': len(overdue_records),
        'overdue_maintenance': serializer.data
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsOperator])
def check_vehicle_maintenance(request, vehicle_id):
    """Check maintenance requirements for a specific vehicle."""
    
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response(
            {'error': 'Vehicle not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    requirements = MaintenanceScheduler.check_maintenance_requirements(vehicle)
    
    # Get existing maintenance records
    existing_maintenance = MaintenanceRecord.objects.filter(
        vehicle=vehicle,
        status__in=[
            MaintenanceRecord.Status.SCHEDULED,
            MaintenanceRecord.Status.IN_PROGRESS
        ]
    ).first()
    
    response_data = {
        'vehicle_id': vehicle.id,
        'license_plate': vehicle.license_plate,
        'requirements': requirements,
        'existing_maintenance': None
    }
    
    if existing_maintenance:
        response_data['existing_maintenance'] = MaintenanceRecordSerializer(
            existing_maintenance
        ).data
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def fleet_analytics(request):
    """Get fleet analytics and metrics."""
    
    days = int(request.query_params.get('days', 7))
    
    utilization = FleetAnalytics.get_fleet_utilization(days)
    maintenance_metrics = FleetAnalytics.get_maintenance_metrics(days)
    
    return Response({
        'utilization': utilization,
        'maintenance_metrics': maintenance_metrics,
        'generated_at': timezone.now()
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOperatorOrAdmin])
def vehicle_performance(request, vehicle_id):
    """Get performance metrics for a specific vehicle."""
    
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response(
            {'error': 'Vehicle not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    days = int(request.query_params.get('days', 30))
    performance = FleetAnalytics.get_vehicle_performance(vehicle, days)
    
    return Response(performance)


class MaintenanceAlertView(APIView):
    """Get maintenance alerts and notifications."""
    
    permission_classes = [permissions.IsAuthenticated, IsOperatorOrAdmin]
    
    def get(self, request):
        """Get current maintenance alerts."""
        
        alerts = []
        
        # Overdue maintenance
        overdue_maintenance = MaintenanceScheduler.get_overdue_maintenance()
        for record in overdue_maintenance:
            days_overdue = (timezone.now().date() - record.scheduled_date.date()).days
            alerts.append({
                'type': 'overdue_maintenance',
                'severity': 'high',
                'vehicle_id': record.vehicle.id,
                'vehicle_license': record.vehicle.license_plate,
                'message': f'Maintenance overdue by {days_overdue} days',
                'maintenance_id': record.id,
                'scheduled_date': record.scheduled_date,
                'days_overdue': days_overdue
            })
        
        # Vehicles needing maintenance
        vehicles_needing_maintenance = []
        for vehicle in Vehicle.objects.filter(
            status__in=[Vehicle.Status.IDLE, Vehicle.Status.ASSIGNED, Vehicle.Status.IN_RIDE]
        ):
            # Skip if already has scheduled maintenance
            if MaintenanceRecord.objects.filter(
                vehicle=vehicle,
                status__in=[
                    MaintenanceRecord.Status.SCHEDULED,
                    MaintenanceRecord.Status.IN_PROGRESS
                ]
            ).exists():
                continue
            
            requirements = MaintenanceScheduler.check_maintenance_requirements(vehicle)
            if requirements['needs_maintenance']:
                alerts.append({
                    'type': 'maintenance_required',
                    'severity': requirements['priority'],
                    'vehicle_id': vehicle.id,
                    'vehicle_license': vehicle.license_plate,
                    'message': f'Vehicle needs {requirements["priority"]} priority maintenance',
                    'reasons': requirements['reasons'],
                    'recommended_date': requirements['recommended_date']
                })
        
        # Maintenance due soon (within 3 days)
        upcoming_maintenance = MaintenanceRecord.objects.filter(
            status=MaintenanceRecord.Status.SCHEDULED,
            scheduled_date__gte=timezone.now(),
            scheduled_date__lte=timezone.now() + timezone.timedelta(days=3)
        )
        
        for record in upcoming_maintenance:
            days_until = (record.scheduled_date.date() - timezone.now().date()).days
            alerts.append({
                'type': 'maintenance_due_soon',
                'severity': 'medium',
                'vehicle_id': record.vehicle.id,
                'vehicle_license': record.vehicle.license_plate,
                'message': f'Maintenance due in {days_until} days',
                'maintenance_id': record.id,
                'scheduled_date': record.scheduled_date,
                'days_until': days_until
            })
        
        # Sort alerts by severity
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))
        
        return Response({
            'total_alerts': len(alerts),
            'alerts': alerts,
            'generated_at': timezone.now()
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsOperator])
def bulk_maintenance_action(request):
    """Perform bulk actions on maintenance records."""
    
    maintenance_ids = request.data.get('maintenance_ids', [])
    action = request.data.get('action')
    
    if not maintenance_ids or not action:
        return Response(
            {'error': 'maintenance_ids and action are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    maintenance_records = MaintenanceRecord.objects.filter(id__in=maintenance_ids)
    if not maintenance_records.exists():
        return Response(
            {'error': 'No maintenance records found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    updated_count = 0
    errors = []
    
    for record in maintenance_records:
        try:
            if action == 'start':
                if record.status == MaintenanceRecord.Status.SCHEDULED:
                    record.start_maintenance()
                    updated_count += 1
                else:
                    errors.append(f'Record {record.id}: Can only start scheduled maintenance')
            
            elif action == 'complete':
                if record.status == MaintenanceRecord.Status.IN_PROGRESS:
                    record.complete_maintenance()
                    updated_count += 1
                else:
                    errors.append(f'Record {record.id}: Can only complete in-progress maintenance')
            
            elif action == 'cancel':
                if record.status in [MaintenanceRecord.Status.SCHEDULED, MaintenanceRecord.Status.IN_PROGRESS]:
                    record.status = MaintenanceRecord.Status.CANCELLED
                    record.save(update_fields=['status'])
                    updated_count += 1
                else:
                    errors.append(f'Record {record.id}: Cannot cancel completed maintenance')
            
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            errors.append(f'Record {record.id}: {str(e)}')
    
    response_data = {
        'message': f'{updated_count} maintenance records updated successfully',
        'action': action,
        'updated_count': updated_count
    }
    
    if errors:
        response_data['errors'] = errors
    
    return Response(response_data)