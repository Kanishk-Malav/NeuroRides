"""
Management command to process the dispatch queue.
"""

from django.core.management.base import BaseCommand
from dispatch.queue import DispatchQueue
from dispatch.services import DispatchService


class Command(BaseCommand):
    """Process pending dispatch requests in the queue."""
    
    help = 'Process pending dispatch requests'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-requests',
            type=int,
            default=50,
            help='Maximum number of requests to process (default: 50)',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up expired requests before processing',
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry failed dispatch requests',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        max_requests = options['max_requests']
        cleanup = options['cleanup']
        retry_failed = options['retry_failed']
        
        dispatch_queue = DispatchQueue()
        dispatch_service = DispatchService()
        
        self.stdout.write('Starting dispatch queue processing...')
        
        # Get initial queue status
        initial_status = dispatch_queue.get_queue_status()
        self.stdout.write(
            f"Initial queue status: {initial_status['pending_requests']} pending, "
            f"{initial_status['processing_requests']} processing"
        )
        
        # Clean up expired requests if requested
        if cleanup:
            expired_count = dispatch_service.cleanup_expired_requests()
            self.stdout.write(
                self.style.WARNING(f"Cleaned up {expired_count} expired requests")
            )
        
        # Retry failed requests if requested
        if retry_failed:
            retry_count = dispatch_service.retry_failed_dispatches()
            self.stdout.write(
                self.style.WARNING(f"Retried {retry_count} failed requests")
            )
        
        # Process the queue
        result = dispatch_queue.process_queue(max_requests=max_requests)
        
        # Display results
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('DISPATCH PROCESSING RESULTS'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Processed: {result['processed']} requests")
        self.stdout.write(
            self.style.SUCCESS(f"Successful: {result['successful']} assignments")
        )
        self.stdout.write(
            self.style.ERROR(f"Failed: {result['failed']} assignments")
        )
        self.stdout.write(f"Remaining in queue: {result['queue_size']}")
        
        # Calculate success rate
        if result['processed'] > 0:
            success_rate = (result['successful'] / result['processed']) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")
        
        # Get final queue status
        final_status = dispatch_queue.get_queue_status()
        
        self.stdout.write("\nFinal queue status:")
        self.stdout.write(
            f"  Pending: {final_status['pending_requests']}")
        self.stdout.write(
            f"  Processing: {final_status['processing_requests']}")
        self.stdout.write(
            f"  Total active: {final_status['total_active']}")
        
        # Display priority distribution
        if final_status['priority_distribution']:
            self.stdout.write("\nPriority distribution:")
            for priority, count in final_status['priority_distribution'].items():
                if count > 0:
                    self.stdout.write(f"  {priority.title()}: {count}")
        
        # Get dispatch statistics
        stats = dispatch_service.get_dispatch_statistics(days=1)
        
        self.stdout.write("\nToday's dispatch statistics:")
        self.stdout.write(f"  Total requests: {stats['total_requests']}")
        self.stdout.write(f"  Success rate: {stats['success_rate']:.1f}%")
        if stats['average_processing_time_seconds']:
            self.stdout.write(
                f"  Avg processing time: {stats['average_processing_time_seconds']:.2f}s"
            )
        
        if result['processed'] > 0:
            self.stdout.write(
                self.style.SUCCESS('\nDispatch queue processing completed successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('\nNo requests were processed.')
            )