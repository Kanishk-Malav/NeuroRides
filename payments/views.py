"""
API views for payments app.
"""

import logging
from decimal import Decimal
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import models

from .models import Payment, PaymentMethod, PaymentRefund, PaymentGateway
from .serializers import (
    PaymentMethodSerializer, FareEstimateSerializer, PaymentCreateSerializer,
    PaymentConfirmSerializer, PaymentSerializer, PaymentRefundSerializer,
    RefundCreateSerializer,
    ReceiptSerializer, WebhookEventSerializer, PaymentHistorySerializer,
    PaymentGatewaySerializer
)
from .services import PaymentService
from .workflow import PaymentWorkflow
from .fare_calculator import FareCalculator
from .receipt_generator import ReceiptGenerator
from rides.models import Ride
from accounts.permissions import IsOwnerOrReadOnly

logger = logging.getLogger(__name__)


class PaymentPagination(PageNumberPagination):
    """Custom pagination for payment lists."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class PaymentMethodListCreateView(APIView):
    """List and create payment methods."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """List user's payment methods."""
        payment_methods = PaymentMethod.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-is_default', '-last_used_at')
        
        serializer = PaymentMethodSerializer(payment_methods, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new payment method."""
        serializer = PaymentMethodSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentMethodDetailView(APIView):
    """Retrieve, update, and delete payment methods."""
    
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_object(self, pk, user):
        """Get payment method by ID for the current user."""
        return get_object_or_404(PaymentMethod, pk=pk, user=user)
    
    def get(self, request, pk):
        """Retrieve a payment method."""
        payment_method = self.get_object(pk, request.user)
        serializer = PaymentMethodSerializer(payment_method)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """Update a payment method."""
        payment_method = self.get_object(pk, request.user)
        serializer = PaymentMethodSerializer(payment_method, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete a payment method."""
        payment_method = self.get_object(pk, request.user)
        payment_method.is_active = False
        payment_method.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentGatewayListView(ListAPIView):
    """List available payment gateways."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentGatewaySerializer
    
    def get_queryset(self):
        """Get active payment gateways."""
        return PaymentGateway.objects.filter(is_active=True)


class FareEstimateView(APIView):
    """Estimate fare for a potential ride."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Calculate fare estimate."""
        serializer = FareEstimateSerializer(data=request.data)
        if serializer.is_valid():
            calculator = FareCalculator()
            
            result = calculator.estimate_fare(
                pickup_lat=serializer.validated_data['pickup_latitude'],
                pickup_lng=serializer.validated_data['pickup_longitude'],
                destination_lat=serializer.validated_data['destination_latitude'],
                destination_lng=serializer.validated_data['destination_longitude'],
                vehicle_type=serializer.validated_data.get('vehicle_type')
            )
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentCreateView(APIView):
    """Create a new payment for a ride."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create payment for a ride."""
        serializer = PaymentCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    ride = Ride.objects.get(id=serializer.validated_data['ride_id'])
                    gateway = None
                    
                    if serializer.validated_data.get('gateway_id'):
                        gateway = PaymentGateway.objects.get(
                            id=serializer.validated_data['gateway_id']
                        )
                    
                    # Process promo code if provided
                    promo_code = serializer.validated_data.get('promo_code')
                    if promo_code:
                        # Validate and apply promo code logic here
                        pass
                    
                    workflow = PaymentWorkflow()
                    result = workflow.process_ride_payment(
                        ride=ride,
                        user=request.user,
                        payment_method_id=serializer.validated_data.get('payment_method_id')
                    )
                    
                    if result['success']:
                        return Response(result, status=status.HTTP_201_CREATED)
                    else:
                        return Response(
                            {'error': result['error']},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            except Exception as e:
                logger.error(f"Payment creation failed: {str(e)}")
                return Response(
                    {'error': 'Payment creation failed'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentConfirmView(APIView):
    """Confirm a payment."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, payment_id):
        """Confirm payment with payment method."""
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PaymentConfirmSerializer(data=request.data)
        if serializer.is_valid():
            workflow = PaymentWorkflow()
            
            # Handle different gateway confirmation methods
            if payment.gateway.gateway_type == PaymentGateway.GatewayType.RAZORPAY:
                # Razorpay requires signature verification
                razorpay_data = {
                    'payment_id': serializer.validated_data.get('razorpay_payment_id'),
                    'order_id': serializer.validated_data.get('razorpay_order_id'),
                    'signature': serializer.validated_data.get('razorpay_signature'),
                }
                
                # Verify signature and confirm payment
                from .services import PaymentGatewayFactory
                gateway_service = PaymentGatewayFactory.create_gateway(payment.gateway)
                
                if gateway_service.verify_payment_signature(
                    razorpay_data['order_id'],
                    razorpay_data['payment_id'],
                    razorpay_data['signature']
                ):
                    result = workflow.confirm_payment(
                        str(payment.id),
                        razorpay_data['payment_id']
                    )
                else:
                    return Response(
                        {'error': 'Invalid payment signature'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Stripe and other gateways
                result = workflow.confirm_payment(
                    str(payment.id),
                    serializer.validated_data['payment_method_id']
                )
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentDetailView(RetrieveAPIView):
    """Retrieve payment details."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer
    
    def get_object(self):
        """Get payment by ID for the current user."""
        return get_object_or_404(
            Payment,
            pk=self.kwargs['pk'],
            user=self.request.user
        )


class PaymentListView(ListAPIView):
    """List user's payments with filtering."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer
    pagination_class = PaymentPagination
    
    def get_queryset(self):
        """Get filtered payments for the current user."""
        queryset = Payment.objects.filter(user=self.request.user).select_related(
            'user', 'ride', 'gateway', 'payment_method'
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        payment_type = self.request.query_params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)
        
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset


class PaymentRefundCreateView(APIView):
    """Create a refund for a payment."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, payment_id):
        """Create refund for a payment."""
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RefundCreateSerializer(data=request.data)
        if serializer.is_valid():
            workflow = PaymentWorkflow()
            
            result = workflow.process_refund(
                payment_id=str(payment.id),
                refund_amount=serializer.validated_data.get('amount'),
                reason=serializer.validated_data['reason'],
                notes=serializer.validated_data.get('notes', '')
            )
            
            if result['success']:
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentRefundListView(ListAPIView):
    """List refunds for user's payments."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentRefundSerializer
    pagination_class = PaymentPagination
    
    def get_queryset(self):
        """Get refunds for the current user's payments."""
        return PaymentRefund.objects.filter(
            payment__user=self.request.user
        ).select_related('payment', 'payment__gateway').order_by('-created_at')


class PaymentReceiptView(APIView):
    """Generate and retrieve payment receipts."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, payment_id):
        """Get payment receipt."""
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if payment.status != Payment.PaymentStatus.COMPLETED:
            return Response(
                {'error': 'Receipt only available for completed payments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        receipt_generator = ReceiptGenerator()
        result = receipt_generator.generate_payment_receipt(payment)
        
        if result['success']:
            # Return HTML receipt by default
            format_type = request.query_params.get('format', 'json')
            
            if format_type == 'html':
                return HttpResponse(
                    result['html_receipt'],
                    content_type='text/html'
                )
            else:
                serializer = ReceiptSerializer(result)
                return Response(serializer.data)
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PromoCodeValidateView(APIView):
    """Validate promo codes."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Validate a promo code."""
        serializer = PromoCodeValidationSerializer(data=request.data)
        if serializer.is_valid():
            promo_code = serializer.validated_data['code']
            ride_amount = serializer.validated_data.get('ride_amount')
            
            is_valid, message = promo_code.is_valid(
                user=request.user,
                ride_amount=ride_amount
            )
            
            if is_valid:
                discount_amount = promo_code.calculate_discount(ride_amount) if ride_amount else None
                
                return Response({
                    'valid': True,
                    'promo_code': PromoCodeSerializer(promo_code, context={'request': request}).data,
                    'discount_amount': float(discount_amount) if discount_amount else None,
                    'message': 'Promo code is valid'
                })
            else:
                return Response({
                    'valid': False,
                    'message': message
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(APIView):
    """Handle payment gateway webhooks."""
    
    permission_classes = []  # Webhooks don't require authentication
    
    def post(self, request, gateway_name):
        """Process webhook from payment gateway."""
        try:
            # Get raw payload and signature
            payload = request.body.decode('utf-8')
            signature = request.META.get('HTTP_STRIPE_SIGNATURE') or request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
            
            if not signature:
                return Response(
                    {'error': 'Missing signature'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process webhook
            payment_service = PaymentService()
            result = payment_service.process_payment_webhook(
                gateway_name=gateway_name,
                payload=payload,
                signature=signature,
                event_data=request.data
            )
            
            if result['success']:
                return Response({'status': 'processed'})
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return Response(
                {'error': 'Webhook processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def payment_statistics(request):
    """Get payment statistics for the current user."""
    user = request.user
    
    # Get payment statistics
    payments = Payment.objects.filter(user=user)
    
    total_payments = payments.count()
    completed_payments = payments.filter(status=Payment.PaymentStatus.COMPLETED).count()
    total_spent = payments.filter(
        status=Payment.PaymentStatus.COMPLETED
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    # Get refund statistics
    refunds = PaymentRefund.objects.filter(payment__user=user)
    total_refunds = refunds.count()
    total_refunded = refunds.filter(
        status=PaymentRefund.Status.COMPLETED
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    return Response({
        'total_payments': total_payments,
        'completed_payments': completed_payments,
        'success_rate': (completed_payments / total_payments * 100) if total_payments > 0 else 0,
        'total_spent': float(total_spent),
        'total_refunds': total_refunds,
        'total_refunded': float(total_refunded),
        'net_spent': float(total_spent - total_refunded),
    })
