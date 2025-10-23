"""
Payment workflow service for NeuroRides platform.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Payment, PaymentRefund, PaymentAuditLog
from .services import PaymentService, PaymentGatewayError
from .fare_calculator import FareCalculator
from .receipt_generator import ReceiptGenerator
from rides.models import Ride
from accounts.models import User

logger = logging.getLogger(__name__)


class PaymentWorkflow:
    """Service for managing payment workflows."""
    
    def __init__(self):
        self.payment_service = PaymentService()
        self.fare_calculator = FareCalculator()
        self.receipt_generator = ReceiptGenerator()
        self.logger = logging.getLogger(__name__)
    
    def process_ride_payment(self, ride: Ride, user: User, 
                           payment_method_id: Optional[str] = None) -> Dict[str, Any]:
        """Process payment for a completed ride."""
        try:
            with transaction.atomic():
                # Validate ride status
                if ride.status != Ride.Status.COMPLETED:
                    return {
                        'success': False,
                        'error': 'Ride must be completed before payment processing',
                    }
                
                # Check if payment already exists
                existing_payment = Payment.objects.filter(
                    ride=ride,
                    status__in=[Payment.Status.COMPLETED, Payment.Status.PROCESSING]
                ).first()
                
                if existing_payment:
                    return {
                        'success': False,
                        'error': 'Payment already exists for this ride',
                        'payment_id': str(existing_payment.id),
                    }
                
                # Calculate fare
                fare_result = self.fare_calculator.calculate_fare(ride)
                if not fare_result['success']:
                    return {
                        'success': False,
                        'error': f"Fare calculation failed: {fare_result['error']}",
                    }
                
                total_fare = Decimal(str(fare_result['fare_breakdown']['total_fare']))
                
                # Update ride with fare information
                ride.final_fare = total_fare
                ride.fare_breakdown = fare_result['fare_breakdown']
                ride.save(update_fields=['final_fare', 'fare_breakdown'])
                
                # Create payment
                payment_result = self.payment_service.create_payment(
                    user=user,
                    ride=ride,
                    amount=total_fare,
                    currency='USD'  # Default currency
                )
                
                if not payment_result['success']:
                    return payment_result
                
                # Log the workflow step
                self._log_workflow_step(
                    ride, user, 'payment_initiated',
                    f"Payment initiated for ride {ride.id}, amount: {total_fare} USD"
                )
                
                return {
                    'success': True,
                    'payment_id': payment_result['payment_id'],
                    'client_secret': payment_result.get('client_secret'),
                    'payment_intent_id': payment_result.get('payment_intent_id'),
                    'fare_breakdown': fare_result['fare_breakdown'],
                    'total_amount': float(total_fare),
                }
                
        except Exception as e:
            self.logger.error(f"Ride payment processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def confirm_payment(self, payment_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Confirm a payment using payment method."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment_id)
                
                if payment.status != Payment.Status.PROCESSING:
                    return {
                        'success': False,
                        'error': f'Payment is not in processing status: {payment.status}',
                    }
                
                # Get gateway service
                from .services import PaymentGatewayFactory
                gateway_service = PaymentGatewayFactory.create_gateway(payment.gateway)
                
                # Confirm payment with gateway
                result = gateway_service.confirm_payment(
                    payment.gateway_payment_intent_id,
                    payment_method_id
                )
                
                if result['success']:
                    payment.status = Payment.Status.COMPLETED
                    payment.processed_at = timezone.now()
                    if result.get('charges'):
                        payment.gateway_transaction_id = result['charges'][0]
                    payment.save()
                    
                    # Generate receipt
                    receipt_result = self.receipt_generator.generate_payment_receipt(payment)
                    
                    # Update ride status
                    if payment.ride:
                        payment.ride.status = Ride.Status.PAYMENT_COMPLETED
                        payment.ride.save(update_fields=['status'])
                    
                    # Log successful payment
                    self._log_workflow_step(
                        payment.ride, payment.user, 'payment_completed',
                        f"Payment {payment.id} completed successfully"
                    )
                    
                    return {
                        'success': True,
                        'payment_id': str(payment.id),
                        'status': payment.status,
                        'receipt': receipt_result if receipt_result['success'] else None,
                    }
                else:
                    payment.status = Payment.Status.FAILED
                    payment.failure_reason = result.get('error', 'Unknown error')
                    payment.save()
                    
                    # Log failed payment
                    self._log_workflow_step(
                        payment.ride, payment.user, 'payment_failed',
                        f"Payment {payment.id} failed: {result.get('error')}"
                    )
                    
                    return {
                        'success': False,
                        'error': result.get('error'),
                        'payment_id': str(payment.id),
                    }
                    
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            self.logger.error(f"Payment confirmation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def process_refund(self, payment_id: str, refund_amount: Optional[Decimal] = None,
                      reason: str = 'customer_request', notes: str = '') -> Dict[str, Any]:
        """Process a refund for a payment."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment_id)
                
                if payment.status != Payment.Status.COMPLETED:
                    return {
                        'success': False,
                        'error': 'Can only refund completed payments',
                    }
                
                # Default to full refund if amount not specified
                if refund_amount is None:
                    refund_amount = payment.amount
                
                # Validate refund amount
                from django.db import models
                total_refunded = payment.refunds.filter(
                    status=PaymentRefund.Status.COMPLETED
                ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
                
                available_for_refund = payment.amount - total_refunded
                
                if refund_amount > available_for_refund:
                    return {
                        'success': False,
                        'error': f'Refund amount exceeds available amount: {available_for_refund}',
                    }
                
                # Process refund
                refund_result = self.payment_service.create_refund(
                    payment=payment,
                    amount=refund_amount,
                    reason=reason,
                    notes=notes
                )
                
                if refund_result['success']:
                    # Generate refund receipt
                    refund = PaymentRefund.objects.get(id=refund_result['refund_id'])
                    receipt_result = self.receipt_generator.generate_refund_receipt(refund)
                    
                    # Update ride status if fully refunded
                    if payment.status == Payment.Status.REFUNDED and payment.ride:
                        payment.ride.status = Ride.Status.REFUNDED
                        payment.ride.save(update_fields=['status'])
                    
                    # Log successful refund
                    self._log_workflow_step(
                        payment.ride, payment.user, 'refund_processed',
                        f"Refund processed for payment {payment.id}, amount: {refund_amount}"
                    )
                    
                    return {
                        'success': True,
                        'refund_id': refund_result['refund_id'],
                        'gateway_refund_id': refund_result['gateway_refund_id'],
                        'amount': float(refund_amount),
                        'receipt': receipt_result if receipt_result['success'] else None,
                    }
                else:
                    return refund_result
                    
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            self.logger.error(f"Refund processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def handle_payment_failure(self, payment_id: str, failure_reason: str,
                             retry_count: int = 0) -> Dict[str, Any]:
        """Handle payment failure and implement retry logic."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment_id)
                
                payment.status = Payment.Status.FAILED
                payment.failure_reason = failure_reason
                payment.save()
                
                # Log payment failure
                self._log_workflow_step(
                    payment.ride, payment.user, 'payment_failed',
                    f"Payment {payment.id} failed: {failure_reason}"
                )
                
                # Implement retry logic
                max_retries = 3
                if retry_count < max_retries:
                    # Create new payment attempt
                    retry_result = self.payment_service.create_payment(
                        user=payment.user,
                        ride=payment.ride,
                        amount=payment.amount,
                        currency=payment.currency,
                        gateway=payment.gateway
                    )
                    
                    if retry_result['success']:
                        self._log_workflow_step(
                            payment.ride, payment.user, 'payment_retry',
                            f"Payment retry {retry_count + 1} initiated for failed payment {payment.id}"
                        )
                        
                        return {
                            'success': True,
                            'retry_initiated': True,
                            'new_payment_id': retry_result['payment_id'],
                            'client_secret': retry_result.get('client_secret'),
                        }
                
                # No more retries or retry failed
                if payment.ride:
                    payment.ride.status = Ride.Status.PAYMENT_FAILED
                    payment.ride.save(update_fields=['status'])
                
                return {
                    'success': True,
                    'retry_initiated': False,
                    'max_retries_reached': retry_count >= max_retries,
                }
                
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            self.logger.error(f"Payment failure handling failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get comprehensive payment status."""
        try:
            payment = Payment.objects.select_related(
                'user', 'ride', 'gateway', 'payment_method'
            ).get(id=payment_id)
            
            # Get receipt if payment is completed
            receipt = None
            if payment.status == Payment.Status.COMPLETED:
                receipt_result = self.receipt_generator.generate_payment_receipt(payment)
                if receipt_result['success']:
                    receipt = receipt_result
            
            # Get refunds
            refunds = []
            for refund in payment.refunds.all():
                refund_data = {
                    'id': str(refund.id),
                    'amount': float(refund.amount),
                    'reason': refund.get_reason_display(),
                    'status': refund.get_status_display(),
                    'created_at': refund.created_at,
                    'processed_at': refund.processed_at,
                }
                refunds.append(refund_data)
            
            return {
                'success': True,
                'payment': {
                    'id': str(payment.id),
                    'status': payment.get_status_display(),
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'gateway': payment.gateway.name,
                    'created_at': payment.created_at,
                    'processed_at': payment.processed_at,
                    'failure_reason': payment.failure_reason,
                },
                'ride': {
                    'id': str(payment.ride.id),
                    'status': payment.ride.get_status_display(),
                } if payment.ride else None,
                'refunds': refunds,
                'receipt': receipt,
            }
            
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            self.logger.error(f"Payment status retrieval failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def _log_workflow_step(self, ride: Optional[Ride], user: User, 
                          action: str, description: str):
        """Log workflow step for audit."""
        try:
            # Map workflow actions to audit log actions
            action_mapping = {
                'payment_initiated': PaymentAuditLog.Action.PAYMENT_CREATED,
                'payment_completed': PaymentAuditLog.Action.PAYMENT_PROCESSED,
                'payment_failed': PaymentAuditLog.Action.PAYMENT_FAILED,
                'payment_retry': PaymentAuditLog.Action.PAYMENT_CREATED,
                'refund_processed': PaymentAuditLog.Action.REFUND_PROCESSED,
            }
            
            audit_action = action_mapping.get(action, PaymentAuditLog.Action.PAYMENT_CREATED)
            
            PaymentAuditLog.objects.create(
                user=user,
                action=audit_action,
                description=description,
            )
            
        except Exception as e:
            self.logger.error(f"Workflow logging failed: {str(e)}")


class PaymentRetryService:
    """Service for handling payment retries and failure recovery."""
    
    def __init__(self):
        self.workflow = PaymentWorkflow()
        self.logger = logging.getLogger(__name__)
    
    def retry_failed_payments(self, max_retries: int = 3) -> Dict[str, Any]:
        """Retry failed payments that haven't exceeded retry limit."""
        try:
            # Get failed payments from the last 24 hours
            from datetime import timedelta
            cutoff_time = timezone.now() - timedelta(hours=24)
            
            failed_payments = Payment.objects.filter(
                status=Payment.Status.FAILED,
                created_at__gte=cutoff_time
            ).select_related('user', 'ride', 'gateway')
            
            retry_results = []
            
            for payment in failed_payments:
                # Count existing retry attempts
                retry_count = Payment.objects.filter(
                    ride=payment.ride,
                    user=payment.user,
                    status=Payment.Status.FAILED
                ).count()
                
                if retry_count <= max_retries:
                    result = self.workflow.handle_payment_failure(
                        str(payment.id),
                        payment.failure_reason,
                        retry_count
                    )
                    
                    retry_results.append({
                        'payment_id': str(payment.id),
                        'retry_result': result,
                    })
            
            return {
                'success': True,
                'retried_payments': len(retry_results),
                'results': retry_results,
            }
            
        except Exception as e:
            self.logger.error(f"Payment retry service failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }