"""
Dispatch queue management for handling ride requests.
"""

import logging
from typing import List, Optional, Dict
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from rides.models import Ride
from .models import DispatchRequest
from .services import DispatchService

logger = logging.getLogger(__name__)


class DispatchQueue:
    """Manages the queue of rides waiting for vehicle assignment."""
    
    def __init__(self):
        self.dispatch_service = DispatchService()
    
    def add_ride_to_queue(self, ride: Ride) -> DispatchRequest:
        """Add a ride to the dispatch queue."""
        
        # Check if ride already has a dispatch request
        existing_request = DispatchRequest.objects.filter(
            ride=ride,
            status__in=[
                DispatchRequest.Status.PENDING,
                DispatchRequest.Status.PROCESSING
            ]
        ).first()
        
        if existing_request:
            return existing_request
        
        # Create new dispatch request
        return self.dispatch_service.dispatch_ride(ride)
    
    def process_queue(self, max_requests: int = 10) -> Dict:
        """Process pending dispatch requests."""
        
        # Get pending requests ordered by priority and creation time
        pending_requests = DispatchRequest.objects.filter(
            status=DispatchRequest.Status.PENDING
        ).order_by(
            '-priority',  # Higher priority first
            'created_at'  # Older requests first within same priority
        )[:max_requests]
        
        processed = 0
        successful = 0
        failed = 0
        
        for request in pending_requests:
            # Check if request has expired
            if request.is_expired:
                request.expire_request()
                continue
            
            # Process the request
            try:
                new_request = self.dispatch_service.dispatch_ride(request.ride)
                processed += 1
                
                if new_request.status == DispatchRequest.Status.ASSIGNED:
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error processing dispatch request {request.id}: {e}")
                request.mark_failed(f"Processing error: {str(e)}")
                failed += 1
        
        return {
            'processed': processed,
            'successful': successful,
            'failed': failed,
            'queue_size': DispatchRequest.objects.filter(
                status=DispatchRequest.Status.PENDING
            ).count()
        }
    
    def get_queue_status(self) -> Dict:
        """Get current queue status."""
        
        pending = DispatchRequest.objects.filter(
            status=DispatchRequest.Status.PENDING
        ).count()
        
        processing = DispatchRequest.objects.filter(
            status=DispatchRequest.Status.PROCESSING
        ).count()
        
        # Get priority distribution
        priority_counts = {}
        for priority_choice in DispatchRequest.Priority.choices:
            priority = priority_choice[0]
            count = DispatchRequest.objects.filter(
                status__in=[
                    DispatchRequest.Status.PENDING,
                    DispatchRequest.Status.PROCESSING
                ],
                priority=priority
            ).count()
            priority_counts[priority] = count
        
        return {
            'pending_requests': pending,
            'processing_requests': processing,
            'total_active': pending + processing,
            'priority_distribution': priority_counts,
            'timestamp': timezone.now()
        }