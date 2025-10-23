"""
Payment gateway services for NeuroRides platform.
"""

import logging
import stripe
import razorpay
from decimal import Decimal
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import PaymentGateway, Payment, PaymentMethod, PaymentRefund, PaymentAuditLog
from rides.models import Ride

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Custom exception for payment gateway errors."""
    pass


class BasePaymentGateway:
    """Base class for payment gateway implementations."""
    
    def __init__(self, gateway_config: PaymentGateway):
        self.gateway_config = gateway_config
        self.is_sandbox = gateway_config.is_sandbox
    
    def create_payment_intent(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent."""
        raise NotImplementedError
    
    def confirm_payment(self, payment_intent_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Confirm a payment."""
        raise NotImplementedError
    
    def create_refund(self, payment_id: str, amount: Decimal, reason: str) -> Dict[str, Any]:
        """Create a refund."""
        raise NotImplementedError
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status."""
        raise NotImplementedError
    
    def validate_webhook(self, payload: str, signature: str) -> bool:
        """Validate webhook signature."""
        raise NotImplementedError
    
    def process_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook event."""
        raise NotImplementedError


class StripePaymentGateway(BasePaymentGateway):
    """Stripe payment gateway implementation."""
    
    def __init__(self, gateway_config: PaymentGateway):
        super().__init__(gateway_config)
        stripe.api_key = gateway_config.get_api_secret()
        self.webhook_secret = gateway_config.get_webhook_secret()
    
    def create_payment_intent(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={'enabled': True},
            )
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status,
                'amount': amount,
                'currency': currency,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment intent creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code if hasattr(e, 'code') else 'unknown',
            }
    
    def confirm_payment(self, payment_intent_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Confirm a Stripe payment."""
        try:
            intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method_id,
            )
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'status': intent.status,
                'charges': [charge.id for charge in intent.charges.data] if intent.charges else [],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment confirmation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code if hasattr(e, 'code') else 'unknown',
            }
    
    def create_refund(self, payment_id: str, amount: Decimal, reason: str) -> Dict[str, Any]:
        """Create a Stripe refund."""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            refund = stripe.Refund.create(
                charge=payment_id,
                amount=amount_cents,
                reason=reason,
            )
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': Decimal(refund.amount) / 100,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code if hasattr(e, 'code') else 'unknown',
            }
    
    def get_payment_status(self, payment_intent_id: str) -> Dict[str, Any]:
        """Get Stripe payment status."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'status': intent.status,
                'amount': Decimal(intent.amount) / 100,
                'currency': intent.currency.upper(),
                'charges': [charge.id for charge in intent.charges.data] if intent.charges else [],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment status retrieval failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code if hasattr(e, 'code') else 'unknown',
            }
    
    def validate_webhook(self, payload: str, signature: str) -> bool:
        """Validate Stripe webhook signature."""
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except (ValueError, stripe.error.SignatureVerificationError):
            return False
    
    def process_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook event."""
        event_type = event_data.get('type')
        
        if event_type == 'payment_intent.succeeded':
            return self._handle_payment_success(event_data['data']['object'])
        elif event_type == 'payment_intent.payment_failed':
            return self._handle_payment_failure(event_data['data']['object'])
        elif event_type == 'charge.dispute.created':
            return self._handle_dispute_created(event_data['data']['object'])
        
        return {'success': True, 'processed': False}
    
    def _handle_payment_success(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook."""
        try:
            payment = Payment.objects.get(
                gateway_payment_intent_id=payment_intent['id']
            )
            payment.status = Payment.Status.COMPLETED
            payment.gateway_transaction_id = payment_intent.get('latest_charge', '')
            payment.save()
            
            return {'success': True, 'processed': True, 'payment_id': str(payment.id)}
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent['id']}")
            return {'success': False, 'error': 'Payment not found'}
    
    def _handle_payment_failure(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment webhook."""
        try:
            payment = Payment.objects.get(
                gateway_payment_intent_id=payment_intent['id']
            )
            payment.status = Payment.Status.FAILED
            payment.failure_reason = payment_intent.get('last_payment_error', {}).get('message', 'Unknown error')
            payment.save()
            
            return {'success': True, 'processed': True, 'payment_id': str(payment.id)}
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent['id']}")
            return {'success': False, 'error': 'Payment not found'}
    
    def _handle_dispute_created(self, charge: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dispute created webhook."""
        # Log dispute for manual review
        logger.warning(f"Dispute created for charge: {charge['id']}")
        return {'success': True, 'processed': True}


class RazorpayPaymentGateway(BasePaymentGateway):
    """Razorpay payment gateway implementation."""
    
    def __init__(self, gateway_config: PaymentGateway):
        super().__init__(gateway_config)
        self.client = razorpay.Client(
            auth=(gateway_config.get_api_key(), gateway_config.get_api_secret())
        )
        self.webhook_secret = gateway_config.get_webhook_secret()
    
    def create_payment_intent(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Razorpay order."""
        try:
            # Convert amount to paise for Razorpay
            amount_paise = int(amount * 100)
            
            order_data = {
                'amount': amount_paise,
                'currency': currency.upper(),
                'notes': metadata,
            }
            
            order = self.client.order.create(data=order_data)
            
            return {
                'success': True,
                'payment_intent_id': order['id'],
                'status': order['status'],
                'amount': amount,
                'currency': currency,
            }
            
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'razorpay_error',
            }
    
    def confirm_payment(self, payment_intent_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Confirm a Razorpay payment."""
        try:
            # In Razorpay, payment confirmation happens on the client side
            # This method would be used to verify the payment signature
            return {
                'success': True,
                'payment_intent_id': payment_intent_id,
                'status': 'requires_verification',
            }
            
        except Exception as e:
            logger.error(f"Razorpay payment confirmation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'razorpay_error',
            }
    
    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify Razorpay payment signature."""
        try:
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            self.client.utility.verify_payment_signature(params_dict)
            return True
        except Exception:
            return False
    
    def create_refund(self, payment_id: str, amount: Decimal, reason: str) -> Dict[str, Any]:
        """Create a Razorpay refund."""
        try:
            # Convert amount to paise for Razorpay
            amount_paise = int(amount * 100)
            
            refund = self.client.payment.refund(
                payment_id,
                amount_paise
            )
            
            return {
                'success': True,
                'refund_id': refund['id'],
                'status': refund['status'],
                'amount': Decimal(refund['amount']) / 100,
            }
            
        except Exception as e:
            logger.error(f"Razorpay refund creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'razorpay_error',
            }
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get Razorpay payment status."""
        try:
            payment = self.client.payment.fetch(payment_id)
            
            return {
                'success': True,
                'payment_id': payment['id'],
                'status': payment['status'],
                'amount': Decimal(payment['amount']) / 100,
                'currency': payment['currency'],
            }
            
        except Exception as e:
            logger.error(f"Razorpay payment status retrieval failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'razorpay_error',
            }
    
    def validate_webhook(self, payload: str, signature: str) -> bool:
        """Validate Razorpay webhook signature."""
        try:
            return self.client.utility.verify_webhook_signature(
                payload, signature, self.webhook_secret
            )
        except Exception:
            return False
    
    def process_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Razorpay webhook event."""
        event_type = event_data.get('event')
        
        if event_type == 'payment.captured':
            return self._handle_payment_success(event_data['payload']['payment']['entity'])
        elif event_type == 'payment.failed':
            return self._handle_payment_failure(event_data['payload']['payment']['entity'])
        
        return {'success': True, 'processed': False}
    
    def _handle_payment_success(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook."""
        try:
            payment = Payment.objects.get(
                gateway_payment_intent_id=payment_data['order_id']
            )
            payment.status = Payment.Status.COMPLETED
            payment.gateway_transaction_id = payment_data['id']
            payment.save()
            
            return {'success': True, 'processed': True, 'payment_id': str(payment.id)}
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for order: {payment_data['order_id']}")
            return {'success': False, 'error': 'Payment not found'}
    
    def _handle_payment_failure(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment webhook."""
        try:
            payment = Payment.objects.get(
                gateway_payment_intent_id=payment_data['order_id']
            )
            payment.status = Payment.Status.FAILED
            payment.failure_reason = payment_data.get('error_description', 'Unknown error')
            payment.save()
            
            return {'success': True, 'processed': True, 'payment_id': str(payment.id)}
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for order: {payment_data['order_id']}")
            return {'success': False, 'error': 'Payment not found'}


class PaymentGatewayFactory:
    """Factory for creating payment gateway instances."""
    
    @staticmethod
    def create_gateway(gateway_config: PaymentGateway) -> BasePaymentGateway:
        """Create a payment gateway instance based on configuration."""
        if gateway_config.gateway_type == PaymentGateway.GatewayType.STRIPE:
            return StripePaymentGateway(gateway_config)
        elif gateway_config.gateway_type == PaymentGateway.GatewayType.RAZORPAY:
            return RazorpayPaymentGateway(gateway_config)
        else:
            raise ValueError(f"Unsupported gateway type: {gateway_config.gateway_type}")


class PaymentService:
    """Main payment service for handling payment operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_active_gateways(self) -> List[PaymentGateway]:
        """Get all active payment gateways."""
        return PaymentGateway.objects.filter(is_active=True)
    
    def get_default_gateway(self) -> Optional[PaymentGateway]:
        """Get the default payment gateway."""
        return PaymentGateway.objects.filter(is_active=True).first()
    
    def create_payment(self, user, ride: Ride, amount: Decimal, 
                      currency: str = 'USD', 
                      gateway: Optional[PaymentGateway] = None) -> Dict[str, Any]:
        """Create a new payment."""
        try:
            if not gateway:
                gateway = self.get_default_gateway()
                if not gateway:
                    raise PaymentGatewayError("No active payment gateway found")
            
            # Create payment record
            payment = Payment.objects.create(
                user=user,
                ride=ride,
                amount=amount,
                currency=currency,
                gateway=gateway,
                status=Payment.Status.PENDING,
            )
            
            # Create payment intent with gateway
            gateway_service = PaymentGatewayFactory.create_gateway(gateway)
            
            metadata = {
                'payment_id': str(payment.id),
                'ride_id': str(ride.id),
                'user_id': str(user.id),
            }
            
            result = gateway_service.create_payment_intent(amount, currency, metadata)
            
            if result['success']:
                payment.gateway_payment_intent_id = result['payment_intent_id']
                payment.status = Payment.Status.PROCESSING
                payment.save()
                
                # Log the action
                self._log_payment_action(
                    payment, 
                    PaymentAuditLog.Action.PAYMENT_CREATED,
                    f"Payment created with intent {result['payment_intent_id']}"
                )
                
                return {
                    'success': True,
                    'payment_id': str(payment.id),
                    'client_secret': result.get('client_secret'),
                    'payment_intent_id': result['payment_intent_id'],
                }
            else:
                payment.status = Payment.Status.FAILED
                payment.failure_reason = result.get('error', 'Unknown error')
                payment.save()
                
                self._log_payment_action(
                    payment,
                    PaymentAuditLog.Action.PAYMENT_FAILED,
                    f"Payment creation failed: {result.get('error')}"
                )
                
                return {
                    'success': False,
                    'error': result.get('error'),
                    'payment_id': str(payment.id),
                }
                
        except Exception as e:
            self.logger.error(f"Payment creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def process_payment_webhook(self, gateway_name: str, payload: str, 
                              signature: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook."""
        try:
            gateway = PaymentGateway.objects.get(name=gateway_name, is_active=True)
            gateway_service = PaymentGatewayFactory.create_gateway(gateway)
            
            # Validate webhook signature
            if not gateway_service.validate_webhook(payload, signature):
                return {'success': False, 'error': 'Invalid webhook signature'}
            
            # Process webhook event
            result = gateway_service.process_webhook(event_data)
            
            # Log webhook processing
            self._log_webhook_action(gateway, event_data, result)
            
            return result
            
        except PaymentGateway.DoesNotExist:
            return {'success': False, 'error': 'Gateway not found'}
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_refund(self, payment: Payment, amount: Decimal, 
                     reason: str, notes: str = '') -> Dict[str, Any]:
        """Create a refund for a payment."""
        try:
            if payment.status != Payment.Status.COMPLETED:
                return {'success': False, 'error': 'Payment not completed'}
            
            if amount > payment.amount:
                return {'success': False, 'error': 'Refund amount exceeds payment amount'}
            
            # Create refund record
            refund = PaymentRefund.objects.create(
                payment=payment,
                amount=amount,
                reason=reason,
                notes=notes,
                status=PaymentRefund.Status.PENDING,
            )
            
            # Process refund with gateway
            gateway_service = PaymentGatewayFactory.create_gateway(payment.gateway)
            result = gateway_service.create_refund(
                payment.gateway_transaction_id, amount, reason
            )
            
            if result['success']:
                refund.gateway_refund_id = result['refund_id']
                refund.status = PaymentRefund.Status.COMPLETED
                refund.save()
                
                # Update payment status if fully refunded
                total_refunded = payment.refunds.filter(
                    status=PaymentRefund.Status.COMPLETED
                ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
                
                if total_refunded >= payment.amount:
                    payment.status = Payment.Status.REFUNDED
                else:
                    payment.status = Payment.Status.PARTIALLY_REFUNDED
                payment.save()
                
                self._log_payment_action(
                    payment,
                    PaymentAuditLog.Action.REFUND_PROCESSED,
                    f"Refund processed: {amount} {payment.currency}"
                )
                
                return {
                    'success': True,
                    'refund_id': str(refund.id),
                    'gateway_refund_id': result['refund_id'],
                }
            else:
                refund.status = PaymentRefund.Status.FAILED
                refund.save()
                
                return {
                    'success': False,
                    'error': result.get('error'),
                    'refund_id': str(refund.id),
                }
                
        except Exception as e:
            self.logger.error(f"Refund creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _log_payment_action(self, payment: Payment, action: str, description: str):
        """Log payment action for audit."""
        PaymentAuditLog.objects.create(
            payment=payment,
            user=payment.user,
            action=action,
            description=description,
        )
    
    def _log_webhook_action(self, gateway: PaymentGateway, event_data: Dict[str, Any], result: Dict[str, Any]):
        """Log webhook action for audit."""
        PaymentAuditLog.objects.create(
            action=PaymentAuditLog.Action.WEBHOOK_RECEIVED,
            description=f"Webhook received from {gateway.name}: {event_data.get('type', 'unknown')}",
        )