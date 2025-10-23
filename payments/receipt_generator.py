"""
Receipt generation service for NeuroRides platform.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from io import BytesIO
import base64

from .models import Payment, PaymentRefund
from rides.models import Ride

logger = logging.getLogger(__name__)


class ReceiptGenerator:
    """Service for generating payment receipts."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_payment_receipt(self, payment: Payment) -> Dict[str, Any]:
        """Generate receipt for a payment."""
        try:
            receipt_data = self._prepare_payment_receipt_data(payment)
            
            # Generate HTML receipt
            html_receipt = self._generate_html_receipt(receipt_data)
            
            # Generate receipt number
            receipt_number = self._generate_receipt_number(payment)
            
            return {
                'success': True,
                'receipt_number': receipt_number,
                'receipt_data': receipt_data,
                'html_receipt': html_receipt,
                'pdf_available': False,  # PDF generation would require additional libraries
            }
            
        except Exception as e:
            self.logger.error(f"Receipt generation failed for payment {payment.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def generate_refund_receipt(self, refund: PaymentRefund) -> Dict[str, Any]:
        """Generate receipt for a refund."""
        try:
            receipt_data = self._prepare_refund_receipt_data(refund)
            
            # Generate HTML receipt
            html_receipt = self._generate_html_refund_receipt(receipt_data)
            
            # Generate receipt number
            receipt_number = self._generate_refund_receipt_number(refund)
            
            return {
                'success': True,
                'receipt_number': receipt_number,
                'receipt_data': receipt_data,
                'html_receipt': html_receipt,
                'pdf_available': False,
            }
            
        except Exception as e:
            self.logger.error(f"Refund receipt generation failed for refund {refund.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def _prepare_payment_receipt_data(self, payment: Payment) -> Dict[str, Any]:
        """Prepare data for payment receipt."""
        ride = payment.ride
        user = payment.user
        
        # Calculate fare breakdown if available
        fare_breakdown = None
        if ride and hasattr(ride, 'fare_breakdown'):
            fare_breakdown = ride.fare_breakdown
        
        receipt_data = {
            'receipt_type': 'payment',
            'payment_id': str(payment.id),
            'receipt_number': self._generate_receipt_number(payment),
            'date': payment.processed_at or payment.created_at,
            'company_info': {
                'name': 'NeuroRides',
                'address': '123 Tech Street, San Francisco, CA 94105',
                'phone': '+1 (555) 123-4567',
                'email': 'support@neurorides.com',
                'website': 'www.neurorides.com',
            },
            'customer_info': {
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'phone': user.phone_number,
            },
            'payment_info': {
                'amount': float(payment.amount),
                'currency': payment.currency,
                'status': payment.get_status_display(),
                'gateway': payment.gateway.name,
                'transaction_id': payment.gateway_transaction_id,
                'payment_method': str(payment.payment_method) if payment.payment_method else 'N/A',
            },
            'ride_info': None,
            'fare_breakdown': fare_breakdown,
        }
        
        # Add ride information if available
        if ride:
            receipt_data['ride_info'] = {
                'ride_id': str(ride.id),
                'pickup_address': ride.pickup_address,
                'destination_address': ride.destination_address,
                'pickup_time': ride.picked_up_at,
                'dropoff_time': ride.completed_at,
                'distance': f"{ride.actual_distance_km or ride.estimated_distance_km or 0} km",
                'duration': f"{ride.actual_duration_minutes or ride.estimated_duration_minutes or 0} minutes",
                'vehicle_info': self._get_vehicle_info(ride),
            }
        
        return receipt_data
    
    def _prepare_refund_receipt_data(self, refund: PaymentRefund) -> Dict[str, Any]:
        """Prepare data for refund receipt."""
        payment = refund.payment
        user = payment.user
        
        receipt_data = {
            'receipt_type': 'refund',
            'refund_id': str(refund.id),
            'original_payment_id': str(payment.id),
            'receipt_number': self._generate_refund_receipt_number(refund),
            'date': refund.processed_at or refund.created_at,
            'company_info': {
                'name': 'NeuroRides',
                'address': '123 Tech Street, San Francisco, CA 94105',
                'phone': '+1 (555) 123-4567',
                'email': 'support@neurorides.com',
                'website': 'www.neurorides.com',
            },
            'customer_info': {
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'phone': user.phone_number,
            },
            'refund_info': {
                'amount': float(refund.amount),
                'currency': payment.currency,
                'reason': refund.get_reason_display(),
                'status': refund.get_status_display(),
                'gateway_refund_id': refund.gateway_refund_id,
                'notes': refund.notes,
            },
            'original_payment_info': {
                'amount': float(payment.amount),
                'currency': payment.currency,
                'transaction_id': payment.gateway_transaction_id,
                'date': payment.processed_at or payment.created_at,
            },
        }
        
        return receipt_data
    
    def _get_vehicle_info(self, ride: Ride) -> Optional[Dict[str, Any]]:
        """Get vehicle information for the ride."""
        # Get vehicle from dispatch request
        from dispatch.models import DispatchRequest
        
        dispatch_request = DispatchRequest.objects.filter(
            ride=ride,
            status=DispatchRequest.Status.ASSIGNED
        ).first()
        
        if dispatch_request and dispatch_request.assigned_vehicle:
            vehicle = dispatch_request.assigned_vehicle
            return {
                'license_plate': vehicle.license_plate,
                'model': vehicle.model,
                'type': vehicle.get_vehicle_type_display(),
            }
        
        return None
    
    def _generate_receipt_number(self, payment: Payment) -> str:
        """Generate unique receipt number for payment."""
        date_str = (payment.processed_at or payment.created_at).strftime('%Y%m%d')
        payment_short_id = str(payment.id)[:8]
        return f"NR-PAY-{date_str}-{payment_short_id}"
    
    def _generate_refund_receipt_number(self, refund: PaymentRefund) -> str:
        """Generate unique receipt number for refund."""
        date_str = (refund.processed_at or refund.created_at).strftime('%Y%m%d')
        refund_short_id = str(refund.id)[:8]
        return f"NR-REF-{date_str}-{refund_short_id}"
    
    def _generate_html_receipt(self, receipt_data: Dict[str, Any]) -> str:
        """Generate HTML receipt from template."""
        template_name = 'payments/receipt_payment.html'
        
        try:
            return render_to_string(template_name, receipt_data)
        except Exception as e:
            self.logger.error(f"HTML receipt generation failed: {str(e)}")
            return self._generate_simple_html_receipt(receipt_data)
    
    def _generate_html_refund_receipt(self, receipt_data: Dict[str, Any]) -> str:
        """Generate HTML refund receipt from template."""
        template_name = 'payments/receipt_refund.html'
        
        try:
            return render_to_string(template_name, receipt_data)
        except Exception as e:
            self.logger.error(f"HTML refund receipt generation failed: {str(e)}")
            return self._generate_simple_html_refund_receipt(receipt_data)
    
    def _generate_simple_html_receipt(self, receipt_data: Dict[str, Any]) -> str:
        """Generate simple HTML receipt as fallback."""
        payment_info = receipt_data['payment_info']
        customer_info = receipt_data['customer_info']
        company_info = receipt_data['company_info']
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Payment Receipt - {receipt_data['receipt_number']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                .section {{ margin: 20px 0; }}
                .amount {{ font-size: 24px; font-weight: bold; color: #2e7d32; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{company_info['name']}</h1>
                <p>Payment Receipt</p>
                <p>Receipt #: {receipt_data['receipt_number']}</p>
            </div>
            
            <div class="section">
                <h3>Payment Details</h3>
                <p><strong>Amount:</strong> <span class="amount">{payment_info['amount']} {payment_info['currency']}</span></p>
                <p><strong>Status:</strong> {payment_info['status']}</p>
                <p><strong>Transaction ID:</strong> {payment_info['transaction_id']}</p>
                <p><strong>Payment Gateway:</strong> {payment_info['gateway']}</p>
                <p><strong>Date:</strong> {receipt_data['date']}</p>
            </div>
            
            <div class="section">
                <h3>Customer Information</h3>
                <p><strong>Name:</strong> {customer_info['name']}</p>
                <p><strong>Email:</strong> {customer_info['email']}</p>
            </div>
            
            <div class="section">
                <p><em>Thank you for using {company_info['name']}!</em></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_simple_html_refund_receipt(self, receipt_data: Dict[str, Any]) -> str:
        """Generate simple HTML refund receipt as fallback."""
        refund_info = receipt_data['refund_info']
        customer_info = receipt_data['customer_info']
        company_info = receipt_data['company_info']
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Refund Receipt - {receipt_data['receipt_number']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                .section {{ margin: 20px 0; }}
                .amount {{ font-size: 24px; font-weight: bold; color: #d32f2f; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{company_info['name']}</h1>
                <p>Refund Receipt</p>
                <p>Receipt #: {receipt_data['receipt_number']}</p>
            </div>
            
            <div class="section">
                <h3>Refund Details</h3>
                <p><strong>Refund Amount:</strong> <span class="amount">{refund_info['amount']} {refund_info['currency']}</span></p>
                <p><strong>Reason:</strong> {refund_info['reason']}</p>
                <p><strong>Status:</strong> {refund_info['status']}</p>
                <p><strong>Refund ID:</strong> {refund_info['gateway_refund_id']}</p>
                <p><strong>Date:</strong> {receipt_data['date']}</p>
            </div>
            
            <div class="section">
                <h3>Customer Information</h3>
                <p><strong>Name:</strong> {customer_info['name']}</p>
                <p><strong>Email:</strong> {customer_info['email']}</p>
            </div>
            
            <div class="section">
                <p><em>Your refund has been processed. Please allow 3-5 business days for the amount to appear in your account.</em></p>
            </div>
        </body>
        </html>
        """
        
        return html