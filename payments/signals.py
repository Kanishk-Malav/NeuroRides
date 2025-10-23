"""
Signal handlers for payments app with PCI compliance logging.
"""

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_login_failed

from .models import Payment, PaymentRefund, PaymentMethod, PaymentGateway, PaymentAuditLog
from .encryption import payment_audit_logger
from .pci_compliance import pci_checker, pci_sanitizer

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def log_payment_activity(sender, instance, created, **kwargs):
    """Log payment activity for audit purposes."""
    
    if created:
        # Log payment creation
        PaymentAuditLog.objects.create(
            payment=instance,
            user=instance.user,
            action=PaymentAuditLog.Action.PAYMENT_CREATED,
            description=f"Payment created for amount {instance.amount} {instance.currency}",
        )
        
        payment_audit_logger.log_payment_action(
            user_id=str(instance.user.id),
            action='payment_created',
            payment_id=str(instance.id),
            amount=str(instance.amount),
            gateway=instance.gateway.name if instance.gateway else None,
        )
        
        logger.info(f"Payment {instance.id} created for user {instance.user.id}")
    
    else:
        # Log status changes
        if hasattr(instance, '_original_status'):
            old_status = instance._original_status
            new_status = instance.status
            
            if old_status != new_status:
                action_mapping = {
                    Payment.PaymentStatus.COMPLETED: PaymentAuditLog.Action.PAYMENT_PROCESSED,
                    Payment.PaymentStatus.FAILED: PaymentAuditLog.Action.PAYMENT_FAILED,
                    Payment.PaymentStatus.CANCELLED: PaymentAuditLog.Action.PAYMENT_CANCELLED,
                }
                
                action = action_mapping.get(new_status, PaymentAuditLog.Action.PAYMENT_PROCESSED)
                
                PaymentAuditLog.objects.create(
                    payment=instance,
                    user=instance.user,
                    action=action,
                    description=f"Payment status changed from {old_status} to {new_status}",
                )
                
                payment_audit_logger.log_payment_action(
                    user_id=str(instance.user.id),
                    action=f'payment_status_changed',
                    payment_id=str(instance.id),
                    additional_data={
                        'old_status': old_status,
                        'new_status': new_status,
                    }
                )
                
                logger.info(f"Payment {instance.id} status changed: {old_status} -> {new_status}")


@receiver(pre_save, sender=Payment)
def track_payment_changes(sender, instance, **kwargs):
    """Track payment changes for audit logging."""
    
    if instance.pk:
        try:
            original = Payment.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Payment.DoesNotExist:
            instance._original_status = None


@receiver(post_save, sender=PaymentRefund)
def log_refund_activity(sender, instance, created, **kwargs):
    """Log refund activity for audit purposes."""
    
    if created:
        PaymentAuditLog.objects.create(
            payment=instance.payment,
            user=instance.payment.user,
            action=PaymentAuditLog.Action.REFUND_INITIATED,
            description=f"Refund initiated for amount {instance.amount} - Reason: {instance.get_reason_display()}",
        )
        
        payment_audit_logger.log_payment_action(
            user_id=str(instance.payment.user.id),
            action='refund_initiated',
            payment_id=str(instance.payment.id),
            amount=str(instance.amount),
            additional_data={
                'refund_id': str(instance.id),
                'reason': instance.reason,
            }
        )
        
        logger.info(f"Refund {instance.id} initiated for payment {instance.payment.id}")
    
    else:
        # Log status changes
        if hasattr(instance, '_original_status'):
            old_status = instance._original_status
            new_status = instance.status
            
            if old_status != new_status and new_status == PaymentRefund.Status.COMPLETED:
                PaymentAuditLog.objects.create(
                    payment=instance.payment,
                    user=instance.payment.user,
                    action=PaymentAuditLog.Action.REFUND_PROCESSED,
                    description=f"Refund processed for amount {instance.amount}",
                )
                
                payment_audit_logger.log_payment_action(
                    user_id=str(instance.payment.user.id),
                    action='refund_processed',
                    payment_id=str(instance.payment.id),
                    amount=str(instance.amount),
                    additional_data={
                        'refund_id': str(instance.id),
                    }
                )
                
                logger.info(f"Refund {instance.id} processed for payment {instance.payment.id}")


@receiver(pre_save, sender=PaymentRefund)
def track_refund_changes(sender, instance, **kwargs):
    """Track refund changes for audit logging."""
    
    if instance.pk:
        try:
            original = PaymentRefund.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except PaymentRefund.DoesNotExist:
            instance._original_status = None


@receiver(post_save, sender=PaymentMethod)
def log_payment_method_activity(sender, instance, created, **kwargs):
    """Log payment method activity with PCI compliance checks."""
    
    if created:
        # Run PCI compliance check on payment method data
        payment_method_data = {
            'payment_type': instance.payment_type,
            'card_brand': instance.card_brand,
            'last_four_digits': instance.last_four_digits,
        }
        
        compliance_result = pci_checker.check_data_encryption(payment_method_data)
        
        if not compliance_result['compliant']:
            logger.warning(f"PCI compliance issues detected for payment method {instance.id}")
            payment_audit_logger.log_pci_compliance_check(
                'payment_method_creation',
                False,
                compliance_result['issues']
            )
        
        payment_audit_logger.log_payment_action(
            user_id=str(instance.user.id),
            action='payment_method_created',
            additional_data={
                'payment_method_id': str(instance.id),
                'payment_type': instance.payment_type,
            }
        )
        
        logger.info(f"Payment method {instance.id} created for user {instance.user.id}")


@receiver(post_delete, sender=PaymentMethod)
def log_payment_method_deletion(sender, instance, **kwargs):
    """Log payment method deletion."""
    
    payment_audit_logger.log_payment_action(
        user_id=str(instance.user.id),
        action='payment_method_deleted',
        additional_data={
            'payment_method_id': str(instance.id),
            'payment_type': instance.payment_type,
        }
    )
    
    logger.info(f"Payment method {instance.id} deleted for user {instance.user.id}")


@receiver(post_save, sender=PaymentGateway)
def log_gateway_configuration(sender, instance, created, **kwargs):
    """Log payment gateway configuration changes."""
    
    action = 'gateway_created' if created else 'gateway_updated'
    
    # Check for security issues
    security_issues = []
    
    if instance.is_sandbox and not instance.name.lower().endswith('_test'):
        security_issues.append("Sandbox gateway without test suffix")
    
    if not instance.is_active and instance.gateway_type == PaymentGateway.GatewayType.STRIPE:
        security_issues.append("Primary payment gateway disabled")
    
    if security_issues:
        logger.warning(f"Security issues detected for gateway {instance.name}: {security_issues}")
    
    payment_audit_logger.log_payment_action(
        user_id='system',
        action=action,
        additional_data={
            'gateway_id': str(instance.id),
            'gateway_name': instance.name,
            'gateway_type': instance.gateway_type,
            'is_active': instance.is_active,
            'is_sandbox': instance.is_sandbox,
            'security_issues': security_issues,
        }
    )
    
    logger.info(f"Payment gateway {instance.name} {action}")


@receiver(user_logged_in)
def log_user_payment_access(sender, request, user, **kwargs):
    """Log user login for payment access tracking."""
    
    # Get IP address and user agent
    ip_address = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    payment_audit_logger.log_payment_action(
        user_id=str(user.id),
        action='user_login',
        ip_address=ip_address,
        user_agent=user_agent,
    )


@receiver(user_login_failed)
def log_failed_payment_access(sender, credentials, request, **kwargs):
    """Log failed login attempts for security monitoring."""
    
    ip_address = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    username = credentials.get('username', 'unknown')
    
    payment_audit_logger.log_payment_action(
        user_id=username,
        action='login_failed',
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    logger.warning(f"Failed login attempt for username: {username} from IP: {ip_address}")


# Custom signal for webhook events
def log_webhook_event(sender, gateway_name, event_type, event_data, **kwargs):
    """Log webhook events for audit purposes."""
    
    # Sanitize event data for logging
    sanitized_data = pci_sanitizer.sanitize_for_logging(event_data)
    
    PaymentAuditLog.objects.create(
        action=PaymentAuditLog.Action.WEBHOOK_RECEIVED,
        description=f"Webhook received from {gateway_name}: {event_type}",
    )
    
    payment_audit_logger.log_payment_action(
        user_id='system',
        action='webhook_received',
        gateway=gateway_name,
        additional_data={
            'event_type': event_type,
            'event_data': sanitized_data,
        }
    )
    
    logger.info(f"Webhook received from {gateway_name}: {event_type}")


# Custom signal for PCI compliance violations
def log_pci_violation(sender, violation_type, details, **kwargs):
    """Log PCI compliance violations."""
    
    PaymentAuditLog.objects.create(
        action=PaymentAuditLog.Action.ERROR_OCCURRED,
        description=f"PCI compliance violation: {violation_type}",
    )
    
    payment_audit_logger.log_pci_compliance_check(
        violation_type,
        False,
        [details]
    )
    
    logger.error(f"PCI compliance violation: {violation_type} - {details}")