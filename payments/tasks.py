"""
Celery tasks for payment processing.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction, models
from datetime import timedelta
from decimal import Decimal
import logging

from .models import Payment, PaymentRefund
from .workflow import PaymentWorkflow, PaymentRetryService
from .services import PaymentService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_payment_confirmation(self, payment_id, payment_method_id):
    """
    Process payment confirmation asynchronously.
    
    Args:
        payment_id: ID of the payment to confirm
        payment_method_id: Payment method ID from the gateway
    
    Returns:
        dict: Processing result
    """
    try:
        workflow = PaymentWorkflow()
        result = workflow.confirm_payment(payment_id, payment_method_id)
        
        if result['success']:
            logger.info(f"Payment {payment_id} confirmed successfully")
        else:
            logger.error(f"Payment {payment_id} confirmation failed: {result.get('error')}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Error confirming payment {payment_id}: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying payment confirmation {payment_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        # Mark payment as failed after max retries
        try:
            payment = Payment.objects.get(id=payment_id)
            payment.status = Payment.Status.FAILED
            payment.failure_reason = f"Task failed after {self.max_retries} retries: {str(exc)}"
            payment.save()
        except Payment.DoesNotExist:
            pass
        
        return {
            'success': False,
            'error': f'Task failed after retries: {str(exc)}',
            'payment_id': payment_id
        }


@shared_task(bind=True, max_retries=2)
def process_refund_request(self, payment_id, refund_amount, reason, notes=''):
    """
    Process refund request asynchronously.
    
    Args:
        payment_id: ID of the payment to refund
        refund_amount: Amount to refund
        reason: Reason for refund
        notes: Additional notes
    
    Returns:
        dict: Processing result
    """
    try:
        workflow = PaymentWorkflow()
        result = workflow.process_refund(
            payment_id, 
            Decimal(str(refund_amount)), 
            reason, 
            notes
        )
        
        if result['success']:
            logger.info(f"Refund processed for payment {payment_id}: {refund_amount}")
        else:
            logger.error(f"Refund failed for payment {payment_id}: {result.get('error')}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Error processing refund for payment {payment_id}: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying refund for payment {payment_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=120 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Refund task failed after retries: {str(exc)}',
            'payment_id': payment_id
        }


@shared_task
def retry_failed_payments():
    """
    Retry failed payments that haven't exceeded retry limit.
    
    Returns:
        dict: Retry results
    """
    logger.info("Starting retry of failed payments")
    
    try:
        retry_service = PaymentRetryService()
        result = retry_service.retry_failed_payments()
        
        logger.info(f"Payment retry completed: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Payment retry task failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cleanup_old_payment_data():
    """
    Clean up old payment-related data.
    
    Returns:
        dict: Cleanup results
    """
    logger.info("Starting cleanup of old payment data")
    
    try:
        # Clean up old failed payments (older than 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_failed_payments = Payment.objects.filter(
            status=Payment.Status.FAILED,
            created_at__lt=cutoff_date
        )
        
        failed_count = old_failed_payments.count()
        old_failed_payments.delete()
        
        # Clean up old audit logs (older than 90 days)
        audit_cutoff_date = timezone.now() - timedelta(days=90)
        
        from .models import PaymentAuditLog
        old_audit_logs = PaymentAuditLog.objects.filter(
            created_at__lt=audit_cutoff_date
        )
        
        audit_count = old_audit_logs.count()
        old_audit_logs.delete()
        
        logger.info(f"Cleaned up {failed_count} old failed payments and {audit_count} old audit logs")
        
        return {
            'success': True,
            'failed_payments_cleaned': failed_count,
            'audit_logs_cleaned': audit_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Payment cleanup task failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def generate_payment_reports():
    """
    Generate daily payment reports and statistics.
    
    Returns:
        dict: Report generation results
    """
    logger.info("Starting payment report generation")
    
    try:
        # Get today's payment statistics
        today = timezone.now().date()
        start_of_day = timezone.datetime.combine(today, timezone.datetime.min.time())
        end_of_day = timezone.datetime.combine(today, timezone.datetime.max.time())
        
        # Make timezone aware
        start_of_day = timezone.make_aware(start_of_day)
        end_of_day = timezone.make_aware(end_of_day)
        
        payments_today = Payment.objects.filter(
            created_at__range=(start_of_day, end_of_day)
        )
        
        # Calculate statistics
        total_payments = payments_today.count()
        completed_payments = payments_today.filter(status=Payment.Status.COMPLETED).count()
        failed_payments = payments_today.filter(status=Payment.Status.FAILED).count()
        
        total_revenue = payments_today.filter(
            status=Payment.Status.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        success_rate = (completed_payments / total_payments * 100) if total_payments > 0 else 0
        
        # Get refund statistics
        refunds_today = PaymentRefund.objects.filter(
            created_at__range=(start_of_day, end_of_day)
        )
        
        total_refunds = refunds_today.count()
        total_refund_amount = refunds_today.filter(
            status=PaymentRefund.Status.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        report_data = {
            'date': today.isoformat(),
            'payment_statistics': {
                'total_payments': total_payments,
                'completed_payments': completed_payments,
                'failed_payments': failed_payments,
                'success_rate': round(success_rate, 2),
                'total_revenue': float(total_revenue),
            },
            'refund_statistics': {
                'total_refunds': total_refunds,
                'total_refund_amount': float(total_refund_amount),
            },
            'net_revenue': float(total_revenue - total_refund_amount),
        }
        
        logger.info(f"Payment report generated for {today}: {report_data}")
        
        return {
            'success': True,
            'report_data': report_data,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Payment report generation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def send_payment_notifications(payment_id):
    """
    Send payment-related notifications to users.
    
    Args:
        payment_id: ID of the payment
    
    Returns:
        dict: Notification results
    """
    try:
        payment = Payment.objects.select_related('user', 'ride').get(id=payment_id)
        
        # Send notification based on payment status
        if payment.status == Payment.Status.COMPLETED:
            # Send payment success notification
            from realtime.utils import notify_user
            
            notify_user(
                payment.user.id,
                'payment_completed',
                'Payment Successful',
                f'Your payment of ${payment.amount} has been processed successfully.',
                {
                    'payment_id': str(payment.id),
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'ride_id': str(payment.ride.id) if payment.ride else None,
                }
            )
            
        elif payment.status == Payment.Status.FAILED:
            # Send payment failure notification
            from realtime.utils import notify_user
            
            notify_user(
                payment.user.id,
                'payment_failed',
                'Payment Failed',
                f'Your payment of ${payment.amount} could not be processed. Please try again.',
                {
                    'payment_id': str(payment.id),
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'failure_reason': payment.failure_reason,
                }
            )
        
        logger.info(f"Payment notification sent for payment {payment_id}")
        
        return {
            'success': True,
            'payment_id': payment_id,
            'notification_sent': True,
        }
        
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found for notification")
        return {
            'success': False,
            'error': 'Payment not found',
            'payment_id': payment_id,
        }
    except Exception as exc:
        logger.error(f"Payment notification failed for {payment_id}: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
            'payment_id': payment_id,
        }

@share
d_task(bind=True, max_retries=3)
def process_payment_async(self, payment_data):
    """
    Process payment asynchronously.
    
    Args:
        payment_data: Dictionary containing payment information
    
    Returns:
        dict: Processing result
    """
    try:
        payment_service = PaymentService()
        result = payment_service.process_payment(payment_data)
        
        if result['success']:
            logger.info(f"Async payment processed successfully: {result.get('payment_id')}")
        else:
            logger.error(f"Async payment processing failed: {result.get('error')}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Error in async payment processing: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying async payment processing (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Task failed after retries: {str(exc)}',
        }


@shared_task(bind=True, max_retries=2)
def process_refund_async(self, refund_data):
    """
    Process refund asynchronously.
    
    Args:
        refund_data: Dictionary containing refund information
    
    Returns:
        dict: Processing result
    """
    try:
        payment_service = PaymentService()
        result = payment_service.process_refund(refund_data)
        
        if result['success']:
            logger.info(f"Async refund processed successfully: {result.get('refund_id')}")
        else:
            logger.error(f"Async refund processing failed: {result.get('error')}")
        
        return result
        
    except Exception as exc:
        logger.error(f"Error in async refund processing: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying async refund processing (attempt {self.request.retries + 1})")
            raise self.retry(countdown=120 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Task failed after retries: {str(exc)}',
        }


@shared_task
def generate_payment_receipts():
    """
    Generate receipts for completed payments that don't have receipts yet.
    
    Returns:
        dict: Receipt generation results
    """
    try:
        logger.info("Starting payment receipt generation")
        
        # Find completed payments without receipts
        payments_without_receipts = Payment.objects.filter(
            status=Payment.Status.COMPLETED,
            receipt_generated=False
        ).select_related('user', 'ride')
        
        generated_count = 0
        errors = []
        
        for payment in payments_without_receipts[:50]:  # Process max 50 at a time
            try:
                from .receipt_generator import generate_payment_receipt
                
                receipt_path = generate_payment_receipt(payment)
                payment.receipt_path = receipt_path
                payment.receipt_generated = True
                payment.save(update_fields=['receipt_path', 'receipt_generated'])
                
                generated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to generate receipt for payment {payment.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Receipt generation completed: {generated_count} generated, {len(errors)} errors")
        
        return {
            'success': True,
            'receipts_generated': generated_count,
            'errors': len(errors),
            'error_details': errors[:5],  # Return first 5 errors
        }
        
    except Exception as exc:
        logger.error(f"Receipt generation task failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def reconcile_payment_records():
    """
    Reconcile payment records with payment gateway data.
    
    Returns:
        dict: Reconciliation results
    """
    try:
        logger.info("Starting payment reconciliation")
        
        # Get payments from the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        recent_payments = Payment.objects.filter(
            created_at__gte=yesterday,
            status__in=[Payment.Status.COMPLETED, Payment.Status.FAILED]
        )
        
        reconciled_count = 0
        discrepancies = []
        
        payment_service = PaymentService()
        
        for payment in recent_payments:
            try:
                # Check payment status with gateway
                gateway_status = payment_service.check_payment_status(payment.gateway_transaction_id)
                
                if gateway_status['status'] != payment.status:
                    discrepancies.append({
                        'payment_id': str(payment.id),
                        'local_status': payment.status,
                        'gateway_status': gateway_status['status'],
                        'transaction_id': payment.gateway_transaction_id,
                    })
                    
                    # Update local status to match gateway
                    payment.status = gateway_status['status']
                    payment.save(update_fields=['status'])
                
                reconciled_count += 1
                
            except Exception as e:
                logger.error(f"Failed to reconcile payment {payment.id}: {str(e)}")
        
        logger.info(f"Payment reconciliation completed: {reconciled_count} checked, {len(discrepancies)} discrepancies")
        
        return {
            'success': True,
            'payments_reconciled': reconciled_count,
            'discrepancies_found': len(discrepancies),
            'discrepancies': discrepancies,
        }
        
    except Exception as exc:
        logger.error(f"Payment reconciliation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def cleanup_expired_payment_intents():
    """
    Clean up expired payment intents and pending payments.
    
    Returns:
        dict: Cleanup results
    """
    try:
        logger.info("Starting cleanup of expired payment intents")
        
        # Clean up payments that have been pending for more than 1 hour
        expiry_threshold = timezone.now() - timedelta(hours=1)
        
        expired_payments = Payment.objects.filter(
            status=Payment.Status.PENDING,
            created_at__lt=expiry_threshold
        )
        
        expired_count = expired_payments.count()
        
        # Mark as expired instead of deleting
        expired_payments.update(
            status=Payment.Status.FAILED,
            failure_reason='Payment intent expired',
            updated_at=timezone.now()
        )
        
        logger.info(f"Marked {expired_count} expired payment intents as failed")
        
        return {
            'success': True,
            'expired_payments': expired_count,
        }
        
    except Exception as exc:
        logger.error(f"Payment intent cleanup failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def check_pci_compliance():
    """
    Check PCI compliance status and generate alerts if needed.
    
    Returns:
        dict: Compliance check results
    """
    try:
        logger.info("Starting PCI compliance check")
        
        from .pci_compliance import PCIComplianceChecker
        
        checker = PCIComplianceChecker()
        compliance_result = checker.run_compliance_check()
        
        # Log any compliance issues
        if not compliance_result['compliant']:
            logger.warning(f"PCI compliance issues found: {compliance_result['issues']}")
            
            # Send alert to administrators
            from realtime.utils import notify_admins
            notify_admins(
                'pci_compliance_issue',
                'PCI Compliance Alert',
                f"PCI compliance check found {len(compliance_result['issues'])} issues",
                compliance_result
            )
        
        logger.info(f"PCI compliance check completed: {'COMPLIANT' if compliance_result['compliant'] else 'NON-COMPLIANT'}")
        
        return {
            'success': True,
            'compliant': compliance_result['compliant'],
            'issues_found': len(compliance_result['issues']),
            'issues': compliance_result['issues'][:5],  # Return first 5 issues
        }
        
    except Exception as exc:
        logger.error(f"PCI compliance check failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }


@shared_task
def generate_financial_reports():
    """
    Generate daily financial reports.
    
    Returns:
        dict: Report generation results
    """
    try:
        logger.info("Starting financial report generation")
        
        yesterday = (timezone.now() - timedelta(days=1)).date()
        
        # Generate comprehensive financial report
        from .services import FinancialReportService
        
        report_service = FinancialReportService()
        report_data = report_service.generate_daily_financial_report(yesterday)
        
        # Save report to database or file system
        # This would typically involve creating a report record and storing the file
        
        logger.info(f"Financial report generated for {yesterday}")
        
        return {
            'success': True,
            'report_date': str(yesterday),
            'total_revenue': report_data.get('total_revenue', 0),
            'total_refunds': report_data.get('total_refunds', 0),
            'net_revenue': report_data.get('net_revenue', 0),
            'transaction_count': report_data.get('transaction_count', 0),
        }
        
    except Exception as exc:
        logger.error(f"Financial report generation failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc),
        }