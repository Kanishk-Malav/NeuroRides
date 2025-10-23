"""
URL patterns for payments app.
"""

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Methods
    path('methods/', views.PaymentMethodListCreateView.as_view(), name='payment-methods'),
    path('methods/<uuid:pk>/', views.PaymentMethodDetailView.as_view(), name='payment-method-detail'),
    
    # Payment Gateways
    path('gateways/', views.PaymentGatewayListView.as_view(), name='payment-gateways'),
    
    # Fare Estimation
    path('fare-estimate/', views.FareEstimateView.as_view(), name='fare-estimate'),
    
    # Payments
    path('create/', views.PaymentCreateView.as_view(), name='payment-create'),
    path('<uuid:payment_id>/confirm/', views.PaymentConfirmView.as_view(), name='payment-confirm'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('', views.PaymentListView.as_view(), name='payment-list'),
    
    # Refunds
    path('<uuid:payment_id>/refund/', views.PaymentRefundCreateView.as_view(), name='payment-refund-create'),
    path('refunds/', views.PaymentRefundListView.as_view(), name='payment-refunds'),
    
    # Receipts
    path('<uuid:payment_id>/receipt/', views.PaymentReceiptView.as_view(), name='payment-receipt'),
    
    # Promo Codes
    path('promo-codes/validate/', views.PromoCodeValidateView.as_view(), name='promo-code-validate'),
    
    # Webhooks
    path('webhooks/<str:gateway_name>/', views.PaymentWebhookView.as_view(), name='payment-webhook'),
    
    # Statistics
    path('statistics/', views.payment_statistics, name='payment-statistics'),
]