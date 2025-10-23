"""
Tests for payment processing Celery tasks.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .tasks import (
    process_payment_confirmation,
    process_refund_request,
    retry_failed_payments,
    cleanup_old_payment_data,
    generate_payment_reports,
    send_payment_notifications,
    process_payment_async,
    process_refund_async,
    generate_payment_receipts,
    reconcile_payment_records,
    cleanup_expired_payment_intents,
    check_pci_compliance,
    generate_financial_reports
)
from .models import Payment, PaymentRefund, PaymentAuditLog
from accounts.models import User
from rides.models import Ride


class PaymentTasksTestCase(TestCase):
    """Test case for payment processing tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St, San Francisco, CA',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave, San Francisco, CA',
            status='completed',
            fare_estimate=15.50
        )
        
        self.payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            currency='USD',
            status=Payment.Status.PENDING,
            payment_method='credit_card',
            gateway_transaction_id='txn_123456'
        )
    
    @patch('payments.tasks.PaymentWorkflow')
    def test_process_payment_confirmation_success(self, mock_workflow):
        """Test successful payment confirmation processing."""
        # Mock workflow response
        mock_workflow_instance = mock_workflow.return_value
        mock_workflow_instance.confirm_payment.return_value = {
            'success': True,
            'payment_id': str(self.payment.id),
            'transaction_id': 'txn_confirmed_123456'
        }
        
        # Execute task
        result = process_payment_confirmation(str(self.payment.id), 'pm_123456')
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['payment_id'], str(self.payment.id))
        
        # Verify workflow was called
        mock_workflow_instance.confirm_payment.assert_called_once_with(
            str(self.payment.id), 'pm_123456'
        )
    
    @patch('payments.tasks.PaymentWorkflow')
    def test_process_payment_confirmation_failure(self, mock_workflow):
        """Test payment confirmation processing failure."""
        # Mock workflow response
        mock_workflow_instance = mock_workflow.return_value
        mock_workflow_instance.confirm_payment.return_value = {
            'success': False,
            'error': 'Payment method declined',
            'payment_id': str(self.payment.id)
        }
        
        # Execute task
        result = process_payment_confirmation(str(self.payment.id), 'pm_123456')
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Payment method declined')
    
    @patch('payments.tasks.PaymentWorkflow')
    def test_process_refund_request_success(self, mock_workflow):
        """Test successful refund request processing."""
        # Mock workflow response
        mock_workflow_instance = mock_workflow.return_value
        mock_workflow_instance.process_refund.return_value = {
            'success': True,
            'refund_id': 'refund_123456',
            'amount': Decimal('15.50')
        }
        
        # Execute task
        result = process_refund_request(
            str(self.payment.id), 15.50, 'customer_request', 'Customer requested refund'
        )
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['refund_id'], 'refund_123456')
        
        # Verify workflow was called
        mock_workflow_instance.process_refund.assert_called_once_with(
            str(self.payment.id), Decimal('15.50'), 'customer_request', 'Customer requested refund'
        )
    
    @patch('payments.tasks.PaymentRetryService')
    def test_retry_failed_payments(self, mock_retry_service):
        """Test retry of failed payments."""
        # Mock service response
        mock_service_instance = mock_retry_service.return_value
        mock_service_instance.retry_failed_payments.return_value = {
            'success': True,
            'retried_count': 3,
            'successful_retries': 2,
            'failed_retries': 1
        }
        
        # Execute task
        result = retry_failed_payments()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['retried_count'], 3)
        
        # Verify service was called
        mock_service_instance.retry_failed_payments.assert_called_once()
    
    def test_cleanup_old_payment_data(self):
        """Test cleanup of old payment data."""
        # Create old failed payment
        old_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('10.00'),
            currency='USD',
            status=Payment.Status.FAILED,
            payment_method='credit_card',
            created_at=timezone.now() - timedelta(days=35)
        )
        
        # Create old audit log
        old_audit_log = PaymentAuditLog.objects.create(
            payment=self.payment,
            action='payment_created',
            details={'amount': '15.50'},
            created_at=timezone.now() - timedelta(days=95)
        )
        
        # Execute task
        result = cleanup_old_payment_data()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['failed_payments_cleaned'], 1)
        self.assertEqual(result['audit_logs_cleaned'], 1)
        
        # Verify old data was deleted
        self.assertFalse(Payment.objects.filter(id=old_payment.id).exists())
        self.assertFalse(PaymentAuditLog.objects.filter(id=old_audit_log.id).exists())
        
        # Verify recent payment was not deleted
        self.assertTrue(Payment.objects.filter(id=self.payment.id).exists())
    
    def test_generate_payment_reports(self):
        """Test payment report generation."""
        # Create completed payment for today
        completed_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('20.00'),
            currency='USD',
            status=Payment.Status.COMPLETED,
            payment_method='credit_card',
            created_at=timezone.now()
        )
        
        # Create failed payment for today
        failed_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('25.00'),
            currency='USD',
            status=Payment.Status.FAILED,
            payment_method='credit_card',
            created_at=timezone.now()
        )
        
        # Create refund for today
        refund = PaymentRefund.objects.create(
            payment=completed_payment,
            amount=Decimal('5.00'),
            reason='partial_refund',
            status=PaymentRefund.Status.COMPLETED,
            created_at=timezone.now()
        )
        
        # Execute task
        result = generate_payment_reports()
        
        # Verify result
        self.assertTrue(result['success'])
        
        # Verify report data
        report_data = result['report_data']
        self.assertEqual(report_data['payment_statistics']['total_payments'], 3)  # Including setup payment
        self.assertEqual(report_data['payment_statistics']['completed_payments'], 1)
        self.assertEqual(report_data['payment_statistics']['failed_payments'], 1)
        self.assertEqual(report_data['payment_statistics']['total_revenue'], 20.0)
        self.assertEqual(report_data['refund_statistics']['total_refunds'], 1)
        self.assertEqual(report_data['refund_statistics']['total_refund_amount'], 5.0)
        self.assertEqual(report_data['net_revenue'], 15.0)
    
    @patch('payments.tasks.notify_user')
    def test_send_payment_notifications_success(self, mock_notify_user):
        """Test sending payment success notifications."""
        # Set payment to completed
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save()
        
        # Execute task
        result = send_payment_notifications(str(self.payment.id))
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertTrue(result['notification_sent'])
        
        # Verify notification was sent
        mock_notify_user.assert_called_once()
        call_args = mock_notify_user.call_args
        self.assertEqual(call_args[0][0], self.user.id)
        self.assertEqual(call_args[0][1], 'payment_completed')
    
    @patch('payments.tasks.notify_user')
    def test_send_payment_notifications_failure(self, mock_notify_user):
        """Test sending payment failure notifications."""
        # Set payment to failed
        self.payment.status = Payment.Status.FAILED
        self.payment.failure_reason = 'Card declined'
        self.payment.save()
        
        # Execute task
        result = send_payment_notifications(str(self.payment.id))
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertTrue(result['notification_sent'])
        
        # Verify notification was sent
        mock_notify_user.assert_called_once()
        call_args = mock_notify_user.call_args
        self.assertEqual(call_args[0][0], self.user.id)
        self.assertEqual(call_args[0][1], 'payment_failed')
    
    def test_send_payment_notifications_not_found(self):
        """Test sending notifications for non-existent payment."""
        # Execute task with non-existent payment ID
        result = send_payment_notifications('non-existent-id')
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Payment not found')
    
    @patch('payments.tasks.PaymentService')
    def test_process_payment_async(self, mock_payment_service):
        """Test asynchronous payment processing."""
        # Mock service response
        mock_service_instance = mock_payment_service.return_value
        mock_service_instance.process_payment.return_value = {
            'success': True,
            'payment_id': str(self.payment.id),
            'transaction_id': 'txn_async_123456'
        }
        
        payment_data = {
            'amount': 15.50,
            'currency': 'USD',
            'payment_method': 'credit_card',
            'user_id': str(self.user.id)
        }
        
        # Execute task
        result = process_payment_async(payment_data)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['payment_id'], str(self.payment.id))
        
        # Verify service was called
        mock_service_instance.process_payment.assert_called_once_with(payment_data)
    
    @patch('payments.tasks.generate_payment_receipt')
    def test_generate_payment_receipts(self, mock_generate_receipt):
        """Test payment receipt generation."""
        # Set payment to completed without receipt
        self.payment.status = Payment.Status.COMPLETED
        self.payment.receipt_generated = False
        self.payment.save()
        
        # Mock receipt generation
        mock_generate_receipt.return_value = '/receipts/payment_123.pdf'
        
        # Execute task
        result = generate_payment_receipts()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['receipts_generated'], 1)
        self.assertEqual(result['errors'], 0)
        
        # Verify payment was updated
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.receipt_generated)
        self.assertEqual(self.payment.receipt_path, '/receipts/payment_123.pdf')
    
    @patch('payments.tasks.PaymentService')
    def test_reconcile_payment_records(self, mock_payment_service):
        """Test payment record reconciliation."""
        # Set payment to completed
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save()
        
        # Mock service to return different status
        mock_service_instance = mock_payment_service.return_value
        mock_service_instance.check_payment_status.return_value = {
            'status': Payment.Status.FAILED
        }
        
        # Execute task
        result = reconcile_payment_records()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['payments_reconciled'], 1)
        self.assertEqual(result['discrepancies_found'], 1)
        
        # Verify payment status was updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
    
    def test_cleanup_expired_payment_intents(self):
        """Test cleanup of expired payment intents."""
        # Create expired pending payment
        expired_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('30.00'),
            currency='USD',
            status=Payment.Status.PENDING,
            payment_method='credit_card',
            created_at=timezone.now() - timedelta(hours=2)
        )
        
        # Execute task
        result = cleanup_expired_payment_intents()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['expired_payments'], 1)
        
        # Verify payment was marked as failed
        expired_payment.refresh_from_db()
        self.assertEqual(expired_payment.status, Payment.Status.FAILED)
        self.assertEqual(expired_payment.failure_reason, 'Payment intent expired')
    
    @patch('payments.tasks.PCIComplianceChecker')
    def test_check_pci_compliance_compliant(self, mock_checker):
        """Test PCI compliance check when compliant."""
        # Mock compliance checker
        mock_checker_instance = mock_checker.return_value
        mock_checker_instance.run_compliance_check.return_value = {
            'compliant': True,
            'issues': []
        }
        
        # Execute task
        result = check_pci_compliance()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertTrue(result['compliant'])
        self.assertEqual(result['issues_found'], 0)
    
    @patch('payments.tasks.PCIComplianceChecker')
    @patch('payments.tasks.notify_admins')
    def test_check_pci_compliance_non_compliant(self, mock_notify_admins, mock_checker):
        """Test PCI compliance check when non-compliant."""
        # Mock compliance checker
        mock_checker_instance = mock_checker.return_value
        mock_checker_instance.run_compliance_check.return_value = {
            'compliant': False,
            'issues': ['Weak encryption', 'Missing access controls']
        }
        
        # Execute task
        result = check_pci_compliance()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertFalse(result['compliant'])
        self.assertEqual(result['issues_found'], 2)
        
        # Verify admin notification was sent
        mock_notify_admins.assert_called_once()
    
    @patch('payments.tasks.FinancialReportService')
    def test_generate_financial_reports(self, mock_report_service):
        """Test financial report generation."""
        # Mock service response
        mock_service_instance = mock_report_service.return_value
        mock_service_instance.generate_daily_financial_report.return_value = {
            'total_revenue': 1500.00,
            'total_refunds': 150.00,
            'net_revenue': 1350.00,
            'transaction_count': 85
        }
        
        # Execute task
        result = generate_financial_reports()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['total_revenue'], 1500.00)
        self.assertEqual(result['net_revenue'], 1350.00)
        self.assertEqual(result['transaction_count'], 85)
        
        # Verify service was called
        yesterday = (timezone.now() - timedelta(days=1)).date()
        mock_service_instance.generate_daily_financial_report.assert_called_once_with(yesterday)


class PaymentTaskRetryTestCase(TestCase):
    """Test case for payment task retry logic."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St, San Francisco, CA',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave, San Francisco, CA',
            status='completed',
            fare_estimate=15.50
        )
        
        self.payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            currency='USD',
            status=Payment.Status.PENDING,
            payment_method='credit_card'
        )
    
    @patch('payments.tasks.PaymentWorkflow')
    def test_process_payment_confirmation_retry_logic(self, mock_workflow):
        """Test payment confirmation retry logic on failure."""
        # Mock workflow to raise exception
        mock_workflow_instance = mock_workflow.return_value
        mock_workflow_instance.confirm_payment.side_effect = Exception("Gateway error")
        
        # Create a mock task with retry capability
        task_mock = MagicMock()
        task_mock.request.retries = 0
        task_mock.max_retries = 3
        task_mock.retry.side_effect = Exception("Retry called")
        
        # Execute task and expect retry to be called
        with self.assertRaises(Exception) as context:
            process_payment_confirmation.__wrapped__(
                task_mock, str(self.payment.id), 'pm_123456'
            )
        
        self.assertEqual(str(context.exception), "Retry called")
        task_mock.retry.assert_called_once()
    
    @patch('payments.tasks.PaymentWorkflow')
    def test_process_payment_confirmation_max_retries_exceeded(self, mock_workflow):
        """Test payment confirmation when max retries are exceeded."""
        # Mock workflow to raise exception
        mock_workflow_instance = mock_workflow.return_value
        mock_workflow_instance.confirm_payment.side_effect = Exception("Gateway error")
        
        # Create a mock task that has exceeded max retries
        task_mock = MagicMock()
        task_mock.request.retries = 3
        task_mock.max_retries = 3
        
        # Execute task
        result = process_payment_confirmation.__wrapped__(
            task_mock, str(self.payment.id), 'pm_123456'
        )
        
        # Verify result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('Task failed after retries', result['error'])
        
        # Verify payment was marked as failed
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertIn('Task failed after 3 retries', self.payment.failure_reason)


class PaymentTaskIntegrationTestCase(TestCase):
    """Integration tests for payment tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.ride = Ride.objects.create(
            rider=self.user,
            pickup_latitude=37.7749,
            pickup_longitude=-122.4194,
            pickup_address='123 Test St, San Francisco, CA',
            destination_latitude=37.7849,
            destination_longitude=-122.4094,
            destination_address='456 Test Ave, San Francisco, CA',
            status='completed',
            fare_estimate=15.50
        )
    
    @patch('payments.tasks.generate_payment_receipt')
    @patch('payments.tasks.notify_user')
    def test_payment_processing_workflow_integration(self, mock_notify_user, mock_generate_receipt):
        """Test integration of payment processing workflow."""
        # Create payment
        payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('15.50'),
            currency='USD',
            status=Payment.Status.COMPLETED,
            payment_method='credit_card',
            receipt_generated=False
        )
        
        # Mock receipt generation
        mock_generate_receipt.return_value = '/receipts/payment_123.pdf'
        
        # Send notification
        notification_result = send_payment_notifications(str(payment.id))
        self.assertTrue(notification_result['success'])
        
        # Generate receipt
        receipt_result = generate_payment_receipts()
        self.assertTrue(receipt_result['success'])
        self.assertEqual(receipt_result['receipts_generated'], 1)
        
        # Verify payment was updated
        payment.refresh_from_db()
        self.assertTrue(payment.receipt_generated)
        self.assertEqual(payment.receipt_path, '/receipts/payment_123.pdf')
        
        # Verify notification was sent
        mock_notify_user.assert_called_once()
    
    def test_payment_cleanup_and_reporting_integration(self):
        """Test integration between payment cleanup and reporting."""
        # Create payments for today
        today_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('20.00'),
            currency='USD',
            status=Payment.Status.COMPLETED,
            payment_method='credit_card',
            created_at=timezone.now()
        )
        
        # Create old failed payment
        old_payment = Payment.objects.create(
            user=self.user,
            ride=self.ride,
            amount=Decimal('10.00'),
            currency='USD',
            status=Payment.Status.FAILED,
            payment_method='credit_card',
            created_at=timezone.now() - timedelta(days=35)
        )
        
        # Generate report before cleanup
        report_result_before = generate_payment_reports()
        self.assertTrue(report_result_before['success'])
        total_before = report_result_before['report_data']['payment_statistics']['total_payments']
        
        # Run cleanup
        cleanup_result = cleanup_old_payment_data()
        self.assertTrue(cleanup_result['success'])
        self.assertEqual(cleanup_result['failed_payments_cleaned'], 1)
        
        # Generate report after cleanup
        report_result_after = generate_payment_reports()
        self.assertTrue(report_result_after['success'])
        total_after = report_result_after['report_data']['payment_statistics']['total_payments']
        
        # Verify old payment was excluded from report
        self.assertEqual(total_after, total_before - 1)
        
        # Verify today's payment is still included
        self.assertTrue(Payment.objects.filter(id=today_payment.id).exists())
        self.assertFalse(Payment.objects.filter(id=old_payment.id).exists())