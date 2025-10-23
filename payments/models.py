"""
Payment models for NeuroRides platform.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import json
from .encryption import payment_encryption, payment_audit_logger

from rides.models import Ride

User = get_user_model()


class PaymentGateway(models.Model):
    """Payment gateway configuration."""
    
    class GatewayType(models.TextChoices):
        STRIPE = 'stripe', _('Stripe')
        RAZORPAY = 'razorpay', _('Razorpay')
        PAYPAL = 'paypal', _('PayPal')
    
    name = models.CharField(max_length=50, unique=True)
    gateway_type = models.CharField(
        max_length=20,
        choices=GatewayType.choices,
        help_text=_('Type of payment gateway')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this gateway is currently active')
    )
    is_sandbox = models.BooleanField(
        default=True,
        help_text=_('Whether this gateway is in sandbox/test mode')
    )
    
    # Configuration (encrypted)
    api_key = models.TextField(
        help_text=_('Encrypted API key for the gateway')
    )
    api_secret = models.TextField(
        help_text=_('Encrypted API secret for the gateway')
    )
    webhook_secret = models.TextField(
        blank=True,
        help_text=_('Encrypted webhook secret for the gateway')
    )
    
    # Additional configuration
    supported_currencies = models.JSONField(
        default=list,
        help_text=_('List of supported currency codes')
    )
    configuration = models.JSONField(
        default=dict,
        help_text=_('Additional gateway-specific configuration')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Payment Gateway')
        verbose_name_plural = _('Payment Gateways')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_gateway_type_display()})"
    
    def set_api_key(self, value):
        """Set encrypted API key."""
        if value:
            self.api_key = payment_encryption.encrypt(value)
            payment_audit_logger.log_encryption_event(
                'encrypt', 'api_key', True
            )
        else:
            self.api_key = ''
    
    def get_api_key(self):
        """Get decrypted API key."""
        if self.api_key:
            try:
                decrypted = payment_encryption.decrypt(self.api_key)
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'api_key', True
                )
                return decrypted
            except ValueError as e:
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'api_key', False, str(e)
                )
                return ''
        return ''
    
    def set_api_secret(self, value):
        """Set encrypted API secret."""
        if value:
            self.api_secret = payment_encryption.encrypt(value)
            payment_audit_logger.log_encryption_event(
                'encrypt', 'api_secret', True
            )
        else:
            self.api_secret = ''
    
    def get_api_secret(self):
        """Get decrypted API secret."""
        if self.api_secret:
            try:
                decrypted = payment_encryption.decrypt(self.api_secret)
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'api_secret', True
                )
                return decrypted
            except ValueError as e:
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'api_secret', False, str(e)
                )
                return ''
        return ''
    
    def set_webhook_secret(self, value):
        """Set encrypted webhook secret."""
        if value:
            self.webhook_secret = payment_encryption.encrypt(value)
            payment_audit_logger.log_encryption_event(
                'encrypt', 'webhook_secret', True
            )
        else:
            self.webhook_secret = ''
    
    def get_webhook_secret(self):
        """Get decrypted webhook secret."""
        if self.webhook_secret:
            try:
                decrypted = payment_encryption.decrypt(self.webhook_secret)
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'webhook_secret', True
                )
                return decrypted
            except ValueError as e:
                payment_audit_logger.log_encryption_event(
                    'decrypt', 'webhook_secret', False, str(e)
                )
                return ''
        return ''
    
    def get_webhook_secret(self):
        """Get decrypted webhook secret."""
        return self.decrypt_field(self.webhook_secret)


class PaymentMethod(models.Model):
    """User payment methods."""
    
    class MethodType(models.TextChoices):
        CARD = 'card', _('Credit/Debit Card')
        WALLET = 'wallet', _('Digital Wallet')
        UPI = 'upi', _('UPI')
        NET_BANKING = 'net_banking', _('Net Banking')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    
    method_type = models.CharField(
        max_length=20,
        choices=MethodType.choices
    )
    
    # Card details (encrypted)
    card_last_four = models.CharField(
        max_length=4,
        blank=True,
        help_text=_('Last four digits of card (for display)')
    )
    card_brand = models.CharField(
        max_length=20,
        blank=True,
        help_text=_('Card brand (Visa, Mastercard, etc.)')
    )
    card_exp_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    card_exp_year = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(2024), MaxValueValidator(2050)]
    )
    
    # Gateway-specific data
    gateway = models.ForeignKey(
        PaymentGateway,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    gateway_method_id = models.CharField(
        max_length=255,
        help_text=_('Payment method ID from the gateway')
    )
    
    # Status and metadata
    is_default = models.BooleanField(
        default=False,
        help_text=_('Whether this is the default payment method')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this payment method is active')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        ordering = ['-is_default', '-created_at']
        unique_together = ['user', 'gateway_method_id']
    
    def __str__(self):
        if self.method_type == self.MethodType.CARD:
            return f"{self.card_brand} ****{self.card_last_four}"
        return f"{self.get_method_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Payment records."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED = 'refunded', _('Refunded')
        PARTIALLY_REFUNDED = 'partially_refunded', _('Partially Refunded')
    
    class PaymentType(models.TextChoices):
        RIDE_PAYMENT = 'ride_payment', _('Ride Payment')
        REFUND = 'refund', _('Refund')
        ADJUSTMENT = 'adjustment', _('Adjustment')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Related objects
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Payment details
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.RIDE_PAYMENT
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Amount details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text=_('ISO 4217 currency code')
    )
    
    # Gateway information
    gateway = models.ForeignKey(
        PaymentGateway,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    gateway_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Transaction ID from the payment gateway')
    )
    gateway_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Payment intent ID from the gateway')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the payment was processed')
    )
    
    # Additional data
    metadata = models.JSONField(
        default=dict,
        help_text=_('Additional payment metadata')
    )
    failure_reason = models.TextField(
        blank=True,
        help_text=_('Reason for payment failure')
    )
    
    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['gateway_transaction_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and not self.processed_at:
            self.processed_at = timezone.now()
        
        super().save(*args, **kwargs)


class PaymentRefund(models.Model):
    """Payment refund records."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    class RefundReason(models.TextChoices):
        RIDE_CANCELLED = 'ride_cancelled', _('Ride Cancelled')
        SERVICE_ISSUE = 'service_issue', _('Service Issue')
        CUSTOMER_REQUEST = 'customer_request', _('Customer Request')
        SYSTEM_ERROR = 'system_error', _('System Error')
        OTHER = 'other', _('Other')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Related payment
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    
    # Refund details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.CharField(
        max_length=20,
        choices=RefundReason.choices
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Gateway information
    gateway_refund_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Refund ID from the payment gateway')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the refund was processed')
    )
    
    # Additional data
    notes = models.TextField(
        blank=True,
        help_text=_('Additional notes about the refund')
    )
    metadata = models.JSONField(
        default=dict,
        help_text=_('Additional refund metadata')
    )
    
    class Meta:
        verbose_name = _('Payment Refund')
        verbose_name_plural = _('Payment Refunds')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund {self.id} - {self.amount} ({self.status})"
    
    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and not self.processed_at:
            self.processed_at = timezone.now()
        
        super().save(*args, **kwargs)


class PaymentAuditLog(models.Model):
    """Audit log for payment operations."""
    
    class Action(models.TextChoices):
        PAYMENT_CREATED = 'payment_created', _('Payment Created')
        PAYMENT_PROCESSED = 'payment_processed', _('Payment Processed')
        PAYMENT_FAILED = 'payment_failed', _('Payment Failed')
        PAYMENT_CANCELLED = 'payment_cancelled', _('Payment Cancelled')
        REFUND_INITIATED = 'refund_initiated', _('Refund Initiated')
        REFUND_PROCESSED = 'refund_processed', _('Refund Processed')
        WEBHOOK_RECEIVED = 'webhook_received', _('Webhook Received')
        ERROR_OCCURRED = 'error_occurred', _('Error Occurred')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Related objects
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Audit details
    action = models.CharField(
        max_length=30,
        choices=Action.choices
    )
    description = models.TextField(
        help_text=_('Description of the action')
    )
    
    # Request/Response data (encrypted)
    request_data = models.TextField(
        blank=True,
        help_text=_('Encrypted request data')
    )
    response_data = models.TextField(
        blank=True,
        help_text=_('Encrypted response data')
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    user_agent = models.TextField(
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Payment Audit Log')
        verbose_name_plural = _('Payment Audit Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.created_at}"
    
    def set_request_data(self, data):
        """Set encrypted request data."""
        if data:
            json_data = json.dumps(data) if isinstance(data, dict) else str(data)
            self.request_data = payment_encryption.encrypt(json_data)
        else:
            self.request_data = ''
    
    def get_request_data(self):
        """Get decrypted request data."""
        if self.request_data:
            try:
                decrypted = payment_encryption.decrypt(self.request_data)
                return json.loads(decrypted)
            except (ValueError, json.JSONDecodeError):
                return {}
        return {}
    
    def set_response_data(self, data):
        """Set encrypted response data."""
        if data:
            json_data = json.dumps(data) if isinstance(data, dict) else str(data)
            self.response_data = payment_encryption.encrypt(json_data)
        else:
            self.response_data = ''
    
    def get_response_data(self):
        """Get decrypted response data."""
        if self.response_data:
            try:
                decrypted = payment_encryption.decrypt(self.response_data)
                return json.loads(decrypted)
            except (ValueError, json.JSONDecodeError):
                return {}
        return {}