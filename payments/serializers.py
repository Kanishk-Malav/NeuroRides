"""
Serializers for payments app.
"""

from rest_framework import serializers
from decimal import Decimal
from django.contrib.auth import get_user_model
from .models import Payment, PaymentMethod, PaymentRefund, PaymentGateway
from rides.models import Ride

User = get_user_model()


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod model."""
    
    display_name = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'payment_type', 'card_brand', 'last_four_digits',
            'expiry_month', 'expiry_year', 'cardholder_name',
            'wallet_email', 'wallet_phone', 'is_default', 'is_active',
            'is_verified', 'display_name', 'is_expired', 'created_at',
            'last_used_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_used_at', 'is_verified']
    
    def validate(self, data):
        """Validate payment method data."""
        payment_type = data.get('payment_type')
        
        if payment_type in ['credit_card', 'debit_card']:
            required_fields = ['card_brand', 'last_four_digits', 'expiry_month', 'expiry_year']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field} is required for card payments")
        
        elif payment_type == 'digital_wallet':
            if not data.get('wallet_email') and not data.get('wallet_phone'):
                raise serializers.ValidationError("Email or phone is required for digital wallet")
        
        return data


class PaymentGatewaySerializer(serializers.ModelSerializer):
    """Serializer for PaymentGateway model."""
    
    class Meta:
        model = PaymentGateway
        fields = [
            'id', 'name', 'gateway_type', 'is_active', 'is_sandbox',
            'supported_currencies', 'configuration'
        ]
        read_only_fields = ['id']


class FareEstimateSerializer(serializers.Serializer):
    """Serializer for fare estimation requests."""
    
    pickup_latitude = serializers.FloatField()
    pickup_longitude = serializers.FloatField()
    destination_latitude = serializers.FloatField()
    destination_longitude = serializers.FloatField()
    vehicle_type = serializers.CharField(required=False, allow_blank=True)
    
    def validate_pickup_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_pickup_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value
    
    def validate_destination_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_destination_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating payments."""
    
    ride_id = serializers.UUIDField()
    payment_method_id = serializers.UUIDField(required=False, allow_null=True)
    gateway_id = serializers.UUIDField(required=False, allow_null=True)
    promo_code = serializers.CharField(required=False, allow_blank=True)
    
    def validate_ride_id(self, value):
        """Validate ride exists and belongs to user."""
        try:
            ride = Ride.objects.get(id=value)
            user = self.context['request'].user
            if ride.rider != user:
                raise serializers.ValidationError("Ride does not belong to current user")
            if ride.status != Ride.Status.COMPLETED:
                raise serializers.ValidationError("Ride must be completed before payment")
            return value
        except Ride.DoesNotExist:
            raise serializers.ValidationError("Ride not found")
    
    def validate_payment_method_id(self, value):
        """Validate payment method exists and belongs to user."""
        if value:
            try:
                payment_method = PaymentMethod.objects.get(id=value)
                user = self.context['request'].user
                if payment_method.user != user:
                    raise serializers.ValidationError("Payment method does not belong to current user")
                if not payment_method.is_active:
                    raise serializers.ValidationError("Payment method is not active")
                return value
            except PaymentMethod.DoesNotExist:
                raise serializers.ValidationError("Payment method not found")
        return value
    
    def validate_gateway_id(self, value):
        """Validate gateway exists and is active."""
        if value:
            try:
                gateway = PaymentGateway.objects.get(id=value)
                if not gateway.is_active:
                    raise serializers.ValidationError("Payment gateway is not active")
                return value
            except PaymentGateway.objects.DoesNotExist:
                raise serializers.ValidationError("Payment gateway not found")
        return value


class PaymentConfirmSerializer(serializers.Serializer):
    """Serializer for confirming payments."""
    
    payment_method_id = serializers.CharField()
    
    # Stripe-specific fields
    payment_intent_id = serializers.CharField(required=False, allow_blank=True)
    
    # Razorpay-specific fields
    razorpay_payment_id = serializers.CharField(required=False, allow_blank=True)
    razorpay_order_id = serializers.CharField(required=False, allow_blank=True)
    razorpay_signature = serializers.CharField(required=False, allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    ride_info = serializers.SerializerMethodField()
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    payment_method_display = serializers.CharField(source='payment_method.display_name', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_before_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    final_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user_name', 'ride_info', 'payment_type', 'status',
            'amount', 'currency', 'base_fare', 'distance_fare', 'time_fare',
            'surge_amount', 'booking_fee', 'tax_amount', 'tip_amount',
            'discount_amount', 'subtotal', 'total_before_discount', 'final_amount',
            'gateway_name', 'payment_method_display', 'gateway_payment_intent_id',
            'gateway_transaction_id', 'failure_reason', 'receipt_url',
            'created_at', 'updated_at', 'processed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processed_at']
    
    def get_ride_info(self, obj):
        """Get ride information."""
        if obj.ride:
            return {
                'id': str(obj.ride.id),
                'pickup_address': obj.ride.pickup_address,
                'destination_address': obj.ride.destination_address,
                'status': obj.ride.get_status_display(),
                'distance_km': obj.ride.actual_distance_km or obj.ride.estimated_distance_km,
                'duration_minutes': obj.ride.actual_duration_minutes or obj.ride.estimated_duration_minutes,
            }
        return None


class PaymentRefundSerializer(serializers.ModelSerializer):
    """Serializer for PaymentRefund model."""
    
    payment_info = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentRefund
        fields = [
            'id', 'payment_info', 'amount', 'reason', 'status',
            'gateway_refund_id', 'notes', 'processed_by',
            'created_at', 'updated_at', 'processed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processed_at']
    
    def get_payment_info(self, obj):
        """Get payment information."""
        return {
            'id': str(obj.payment.id),
            'amount': obj.payment.amount,
            'currency': obj.payment.currency,
            'gateway': obj.payment.gateway.name,
        }


class RefundCreateSerializer(serializers.Serializer):
    """Serializer for creating refunds."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.ChoiceField(choices=PaymentRefund.RefundReason.choices)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate refund amount."""
        if value and value <= 0:
            raise serializers.ValidationError("Refund amount must be positive")
        return value


# class PromoCodeSerializer(serializers.ModelSerializer):
#     """Serializer for PromoCode model."""
#     
#     is_valid_now = serializers.SerializerMethodField()
#     usage_stats = serializers.SerializerMethodField()
#     
#     class Meta:
#         model = PromoCode
#         fields = [
#             'id', 'code', 'name', 'description', 'discount_type',
#             'discount_value', 'max_discount_amount', 'min_ride_amount',
#             'usage_type', 'max_uses_total', 'max_uses_per_user',
#             'current_uses', 'is_active', 'valid_from', 'valid_until',
#             'first_ride_only', 'new_users_only', 'is_valid_now', 'usage_stats'
#         ]
#         read_only_fields = ['id', 'current_uses', 'is_valid_now', 'usage_stats']
#     
#     def get_is_valid_now(self, obj):
#         """Check if promo code is currently valid."""
#         user = self.context.get('request').user if self.context.get('request') else None
#         is_valid, message = obj.is_valid(user=user)
#         return is_valid
#     
#     def get_usage_stats(self, obj):
#         """Get usage statistics."""
#         return {
#             'current_uses': obj.current_uses,
#             'max_uses_total': obj.max_uses_total,
#             'max_uses_per_user': obj.max_uses_per_user,
#             'usage_percentage': (obj.current_uses / obj.max_uses_total * 100) if obj.max_uses_total else 0,
#         }


# class PromoCodeValidationSerializer(serializers.Serializer):
#     """Serializer for validating promo codes."""
#     
#     code = serializers.CharField()
#     ride_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
#     
#     def validate_code(self, value):
#         """Validate promo code exists."""
#         try:
#             promo_code = PromoCode.objects.get(code=value.upper())
#             return promo_code
#         except PromoCode.DoesNotExist:
#             raise serializers.ValidationError("Invalid promo code")


class ReceiptSerializer(serializers.Serializer):
    """Serializer for receipt data."""
    
    receipt_number = serializers.CharField()
    receipt_data = serializers.DictField()
    html_receipt = serializers.CharField()
    pdf_available = serializers.BooleanField()


class WebhookEventSerializer(serializers.Serializer):
    """Serializer for webhook events."""
    
    gateway = serializers.CharField()
    event_type = serializers.CharField()
    event_data = serializers.DictField()
    signature = serializers.CharField()
    
    def validate_gateway(self, value):
        """Validate gateway exists."""
        try:
            gateway = PaymentGateway.objects.get(name=value, is_active=True)
            return gateway
        except PaymentGateway.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive gateway")


class PaymentHistorySerializer(serializers.Serializer):
    """Serializer for payment history requests."""
    
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=Payment.Status.choices, required=False)
    payment_type = serializers.ChoiceField(choices=Payment.PaymentType.choices, required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    
    def validate(self, data):
        """Validate date range."""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date must be before end date")
        
        return data