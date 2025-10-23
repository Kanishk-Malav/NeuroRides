"""
Tests for payments app.
"""

import json
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone

from .models import (
    PaymentGateway, PaymentMethod, Payment, PaymentRefund, 
    PaymentAuditLog, PromoCode
)
from .services import PaymentService, StripePaymentGateway, RazorpayPaymentGateway
from .fare_calculator import FareCalculator
from .workflow import PaymentWorkflow
from .encryption import PaymentDataEncryption, payment_encryption
from .pci_compliance import PCIComplianceChecker, PCIDataSanitizer
from rides.models import Ride
from fleet.models import Vehicle

User = get_user_model()


class PaymentEncryptionTestCase(TestCase):
    """Test payment data encryption functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.encryption = PaymentDataEncryption()
        self.test_data = "sensitive_payment_data_123"
    
    def test_encrypt_decrypt_data(self):
        """Test basic encryption and decryption."""
        encrypted = self.encryption.encrypt(self.test_data)
        self.assertNotEqual(encrypted, self.test_data)
        
        decrypted = self.encryption.decrypt(encrypted)
        self.assertEqual(decrypted, self.test_data)
    
    def test_encrypt_empty_data(self):
        """Test encryption of empty data."""
        encrypted = self.encryption.encrypt("")
        self.assertEqual(encrypted, "")
        
        encrypted_none = self.encryption.encrypt(None)
        self.assertEqual(encrypted_none, None)
    
    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data."""
        with self.assertRaises(ValueError):
            self.encryption.decrypt("invalid_encrypted_data")
    
    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        test_dict = {
            'card_number': '4111111111111111',
            'cvv': '123',
            'name': 'John Doe',
            'amount': '100.00'
        }
        
        fields_to_encrypt = ['card_number', 'cvv']
        
        encrypted_dict = self.encryption.encrypt_dict(test_dict, fields_to_encrypt)
        
        # Check that sensitive fields are encrypted
        self.assertNotEqual(encrypted_dict['card_number'], test_dict['card_number'])
        self.assertNotEqual(encrypted_dict['cvv'], test_dict['cvv'])
        
        # Check that non-sensitive fields are unchanged
        self.assertEqual(encrypted_dict['name'], test_dict['name'])
        self.assertEqual(encrypted_dict['amount'], test_dict['amount'])
        
        # Decrypt and verify
        decrypted_dict = self.encryption.decrypt_dict(encrypted_dict, fields_to_encrypt)
        self.assertEqual(decrypted_dict['card_number'], test_dict['card_number'])
        self.assertEqual(decrypted_dict['cvv'], test_dict['cvv'])


class PaymentGatewayTestCase(TestCase):
    """Test payment gateway functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.gateway = PaymentGateway.objects.create(
            name='Test Stripe',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True,
            is_sandbox=True,
            supported_currencies=['USD', 'EUR']
        )
    
    def test_gateway_creation(self):
        """Test payment gateway creation."""
        self.assertEqual(self.gateway.name, 'Test Stripe')
        self.assertEqual(self.gateway.gateway_type, PaymentGateway.GatewayType.STRIPE)
        self.assertTrue(self.gateway.is_active)
        self.assertTrue(self.gateway.is_sandbox)
    
    def test_encrypt_decrypt_credentials(self):
        """Test encryption and decryption of gateway credentials."""
        api_key = 'pk_test_123456789'
        api_secret = 'sk_test_987654321'
        webhook_secret = 'whsec_test_abcdef'
        
        # Set encrypted credentials
        self.gateway.set_api_key(api_key)
        self.gateway.set_api_secret(api_secret)
        self.gateway.set_webhook_secret(webhook_secret)
        self.gateway.save()
        
        # Verify credentials are encrypted in database
        self.assertNotEqual(self.gateway.api_key, api_key)
        self.assertNotEqual(self.gateway.api_secret, api_secret)
        self.assertNotEqual(self.gateway.webhook_secret, webhook_secret)
        
        # Verify credentials can be decrypted
        self.assertEqual(self.gateway.get_api_key(), api_key)
        self.assertEqual(self.gateway.get_api_secret(), api_secret)
        self.assertEqual(self.gateway.get_webhook_secret(), webhook_secret)


class FareCalculatorTestCase(TestCase):
    """Test fare calculation functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.calculator = FareCalculator()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED,
            estimated_distance_km=5.0,
            estimated_duration_minutes=15
        )
    
    def test_fare_estimation(self):
        """Test fare estimation for coordinates."""
        result = self.calculator.estimate_fare(
            pickup_lat=37.7749,
            pickup_lng=-122.4194,
            destination_lat=37.7849,
            destination_lng=-122.4094
        )
        
        self.assertTrue(result['success'])
        self.assertIn('estimated_fare', result)
        self.assertIn('fare_breakdown', result)
        self.assertGreater(result['estimated_fare'], 0)
    
    def test_ride_fare_calculation(self):
        """Test fare calculation for completed ride."""
        result = self.calculator.calculate_fare(self.ride)
        
        self.assertTrue(result['success'])
        self.assertIn('fare_breakdown', result)
        
        breakdown = result['fare_breakdown']
        self.assertIn('base_fare', breakdown)
        self.assertIn('distance_fare', breakdown)
        self.assertIn('time_fare', breakdown)
        self.assertIn('total_fare', breakdown)
        
        # Verify fare components are positive
        self.assertGreater(breakdown['base_fare'], 0)
        self.assertGreater(breakdown['distance_fare'], 0)
        self.assertGreater(breakdown['time_fare'], 0)
        self.assertGreater(breakdown['total_fare'], 0)
    
    def test_surge_pricing(self):
        """Test surge pricing calculation."""
        # Create ride during peak hours
        peak_time = timezone.now().replace(hour=8, minute=0)  # 8 AM
        
        with patch('django.utils.timezone.now', return_value=peak_time):
            result = self.calculator.calculate_fare(self.ride)
            
            self.assertTrue(result['success'])
            self.assertTrue(result['surge_active'])
            self.assertGreater(result['fare_breakdown']['surge_multiplier'], 1.0)
    
    def test_minimum_fare_enforcement(self):
        """Test minimum fare enforcement."""
        # Create very short ride
        short_ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7750,  # Very close
            destination_longitude=-122.4195,
            status=Ride.Status.COMPLETED,
            estimated_distance_km=0.1,
            estimated_duration_minutes=1
        )
        
        result = self.calculator.calculate_fare(short_ride)
        
        self.assertTrue(result['success'])
        self.assertGreaterEqual(
            result['fare_breakdown']['total_fare'],
            float(self.calculator.MIN_FARE)
        )


class PaymentServiceTestCase(TestCase):
    """Test payment service functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Stripe',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True,
            is_sandbox=True
        )
        self.gateway.set_api_key('pk_test_123')
        self.gateway.set_api_secret('sk_test_456')
        self.gateway.save()
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED,
            estimated_distance_km=5.0,
            final_fare=Decimal('15.50')
        )
        
        self.service = PaymentService()
    
    @patch('stripe.PaymentIntent.create')
    def test_create_payment_success(self, mock_stripe_create):
        """Test successful payment creation."""
        mock_stripe_create.return_value = Mock(
            id='pi_test_123',
            client_secret='pi_test_123_secret',
            status='requires_payment_method'
        )
        
        result = self.service.create_payment(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            gateway=self.gateway
        )
        
        self.assertTrue(result['success'])
        self.assertIn('payment_id', result)
        self.assertIn('client_secret', result)
        
        # Verify payment was created in database
        payment = Payment.objects.get(id=result['payment_id'])
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.ride, self.ride)
        self.assertEqual(payment.amount, Decimal('15.50'))
    
    @patch('stripe.PaymentIntent.create')
    def test_create_payment_failure(self, mock_stripe_create):
        """Test payment creation failure."""
        mock_stripe_create.side_effect = Exception('Payment failed')
        
        result = self.service.create_payment(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            gateway=self.gateway
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)


class PaymentWorkflowTestCase(TransactionTestCase):
    """Test payment workflow functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Stripe',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True,
            is_sandbox=True
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED,
            estimated_distance_km=5.0
        )
        
        self.workflow = PaymentWorkflow()
    
    @patch('payments.services.PaymentService.create_payment')
    def test_process_ride_payment(self, mock_create_payment):
        """Test ride payment processing."""
        mock_create_payment.return_value = {
            'success': True,
            'payment_id': 'test_payment_id',
            'client_secret': 'test_secret'
        }
        
        result = self.workflow.process_ride_payment(
            ride=self.ride,
            user=self.user
        )
        
        self.assertTrue(result['success'])
        self.assertIn('payment_id', result)
        self.assertIn('fare_breakdown', result)
    
    def test_process_ride_payment_invalid_status(self):
        """Test payment processing for invalid ride status."""
        self.ride.status = Ride.Status.REQUESTED
        self.ride.save()
        
        result = self.workflow.process_ride_payment(
            ride=self.ride,
            user=self.user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)


class PCIComplianceTestCase(TestCase):
    """Test PCI compliance functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.checker = PCIComplianceChecker()
        self.sanitizer = PCIDataSanitizer()
    
    def test_data_encryption_check(self):
        """Test data encryption compliance check."""
        # Test with unencrypted sensitive data
        unencrypted_data = {
            'card_number': '4111111111111111',
            'cvv': '123',
            'name': 'John Doe'
        }
        
        result = self.checker.check_data_encryption(unencrypted_data)
        
        self.assertFalse(result['compliant'])
        self.assertGreater(len(result['issues']), 0)
        self.assertIn('Unencrypted sensitive data', result['issues'][0])
    
    def test_data_encryption_check_encrypted(self):
        """Test data encryption check with encrypted data."""
        encrypted_data = {
            'card_number': payment_encryption.encrypt('4111111111111111'),
            'cvv': payment_encryption.encrypt('123'),
            'name': 'John Doe'
        }
        
        result = self.checker.check_data_encryption(encrypted_data)
        
        # Should pass since sensitive data is encrypted
        self.assertTrue(result['compliant'])
        self.assertEqual(len(result['issues']), 0)
    
    def test_data_sanitization_for_logging(self):
        """Test data sanitization for logging."""
        sensitive_data = {
            'card_number': '4111111111111111',
            'cvv': '123',
            'name': 'John Doe',
            'amount': '100.00'
        }
        
        sanitized = self.sanitizer.sanitize_for_logging(sensitive_data)
        
        # Sensitive fields should be masked
        self.assertIn('*', sanitized['card_number'])
        self.assertEqual(sanitized['cvv'], '***')
        
        # Non-sensitive fields should be unchanged
        self.assertEqual(sanitized['name'], 'John Doe')
        self.assertEqual(sanitized['amount'], '100.00')
    
    def test_card_number_validation(self):
        """Test credit card number validation."""
        # Valid card numbers
        valid_cards = [
            '4111111111111111',  # Visa
            '5555555555554444',  # Mastercard
            '378282246310005',   # American Express
        ]
        
        for card in valid_cards:
            is_valid, message = self.sanitizer.validate_card_number(card)
            self.assertTrue(is_valid, f"Card {card} should be valid: {message}")
        
        # Invalid card numbers
        invalid_cards = [
            '1234567890123456',  # Invalid Luhn
            '411111111111111',   # Too short
            '41111111111111111', # Too long
            'abcd1234efgh5678',  # Contains letters
        ]
        
        for card in invalid_cards:
            is_valid, message = self.sanitizer.validate_card_number(card)
            self.assertFalse(is_valid, f"Card {card} should be invalid")
    
    def test_card_type_detection(self):
        """Test credit card type detection."""
        test_cards = {
            '4111111111111111': 'Visa',
            '5555555555554444': 'Mastercard',
            '378282246310005': 'American Express',
            '6011111111111117': 'Discover',
        }
        
        for card_number, expected_type in test_cards.items():
            detected_type = self.sanitizer.detect_card_type(card_number)
            self.assertEqual(detected_type, expected_type)


class PaymentAPITestCase(APITestCase):
    """Test payment API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Stripe',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True,
            is_sandbox=True
        )
        
        self.payment_method = PaymentMethod.objects.create(
            user=self.user,
            payment_type=PaymentMethod.PaymentType.CREDIT_CARD,
            card_brand=PaymentMethod.CardBrand.VISA,
            last_four_digits='1111',
            expiry_month=12,
            expiry_year=2025,
            is_default=True
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED,
            estimated_distance_km=5.0
        )
    
    def test_payment_method_list(self):
        """Test payment method list endpoint."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('payments:payment-methods')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.payment_method.id))
    
    def test_payment_method_create(self):
        """Test payment method creation endpoint."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('payments:payment-methods')
        data = {
            'payment_type': PaymentMethod.PaymentType.CREDIT_CARD,
            'card_brand': PaymentMethod.CardBrand.MASTERCARD,
            'last_four_digits': '4444',
            'expiry_month': 6,
            'expiry_year': 2026,
            'cardholder_name': 'Test User'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PaymentMethod.objects.count(), 2)
    
    def test_fare_estimate(self):
        """Test fare estimation endpoint."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('payments:fare-estimate')
        data = {
            'pickup_latitude': 37.7749,
            'pickup_longitude': -122.4194,
            'destination_latitude': 37.7849,
            'destination_longitude': -122.4094
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('estimated_fare', response.data)
        self.assertIn('fare_breakdown', response.data)
    
    @patch('payments.workflow.PaymentWorkflow.process_ride_payment')
    def test_payment_create(self, mock_process_payment):
        """Test payment creation endpoint."""
        mock_process_payment.return_value = {
            'success': True,
            'payment_id': 'test_payment_id',
            'client_secret': 'test_secret',
            'fare_breakdown': {'total_fare': 15.50}
        }
        
        self.client.force_authenticate(user=self.user)
        
        url = reverse('payments:payment-create')
        data = {
            'ride_id': str(self.ride.id),
            'payment_method_id': str(self.payment_method.id)
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment_id', response.data)
    
    def test_payment_statistics(self):
        """Test payment statistics endpoint."""
        # Create a completed payment
        payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            status=Payment.PaymentStatus.COMPLETED,
            gateway=self.gateway
        )
        
        self.client.force_authenticate(user=self.user)
        
        url = reverse('payments:payment-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_payments'], 1)
        self.assertEqual(response.data['completed_payments'], 1)
        self.assertEqual(float(response.data['total_spent']), 15.50)


class PaymentAuditTestCase(TestCase):
    """Test payment audit logging functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.gateway = PaymentGateway.objects.create(
            name='Test Stripe',
            gateway_type=PaymentGateway.GatewayType.STRIPE,
            is_active=True,
            is_sandbox=True
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            status=Ride.Status.COMPLETED
        )
    
    def test_payment_creation_audit_log(self):
        """Test audit log creation for payment."""
        payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            gateway=self.gateway
        )
        
        # Check that audit log was created
        audit_logs = PaymentAuditLog.objects.filter(payment=payment)
        self.assertTrue(audit_logs.exists())
        
        audit_log = audit_logs.first()
        self.assertEqual(audit_log.action, PaymentAuditLog.Action.PAYMENT_CREATED)
        self.assertEqual(audit_log.user, self.user)
    
    def test_audit_log_data_encryption(self):
        """Test audit log data encryption."""
        audit_log = PaymentAuditLog.objects.create(
            user=self.user,
            action=PaymentAuditLog.Action.PAYMENT_CREATED,
            description='Test audit log'
        )
        
        # Set request data
        request_data = {
            'card_number': '4111111111111111',
            'amount': '15.50'
        }
        
        audit_log.set_request_data(request_data)
        audit_log.save()
        
        # Verify data is encrypted in database
        self.assertNotEqual(audit_log.request_data, json.dumps(request_data))
        
        # Verify data can be decrypted
        decrypted_data = audit_log.get_request_data()
        self.assertEqual(decrypted_data['card_number'], '4111111111111111')
        self.assertEqual(decrypted_data['amount'], '15.50')
