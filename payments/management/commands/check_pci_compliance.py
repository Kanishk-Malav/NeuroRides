"""
Management command to check PCI DSS compliance.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from payments.pci_compliance import pci_checker
from payments.models import Payment, PaymentGateway, PaymentAuditLog
import json


class Command(BaseCommand):
    """Check PCI DSS compliance for payment system."""
    
    help = 'Check PCI DSS compliance for the payment system'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--payment-id',
            type=str,
            help='Check compliance for specific payment ID',
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed compliance report',
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Attempt to fix common compliance issues',
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to JSON file',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        payment_id = options.get('payment_id')
        detailed = options.get('detailed', False)
        fix_issues = options.get('fix_issues', False)
        export_file = options.get('export')
        
        self.stdout.write(
            self.style.SUCCESS('Starting PCI DSS Compliance Check')
        )
        self.stdout.write('=' * 50)
        
        # Run comprehensive compliance check
        results = pci_checker.run_comprehensive_check(payment_id=payment_id)
        
        # Display results
        self._display_results(results, detailed)
        
        # Fix issues if requested
        if fix_issues:
            self._fix_common_issues(results)
        
        # Export results if requested
        if export_file:
            self._export_results(results, export_file)
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        if results['overall_compliant']:
            self.stdout.write(
                self.style.SUCCESS('✓ OVERALL COMPLIANCE: PASSED')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ OVERALL COMPLIANCE: FAILED')
            )
        
        self.stdout.write(f"Total Checks: {results['summary']['total_checks']}")
        self.stdout.write(f"Passed: {results['summary']['passed_checks']}")
        self.stdout.write(f"Failed: {results['summary']['failed_checks']}")
        self.stdout.write(f"Total Issues: {results['summary']['total_issues']}")
    
    def _display_results(self, results, detailed=False):
        """Display compliance check results."""
        
        for check_name, check_result in results['checks'].items():
            status = "✓ PASS" if check_result['compliant'] else "✗ FAIL"
            status_style = self.style.SUCCESS if check_result['compliant'] else self.style.ERROR
            
            self.stdout.write(f"\n{check_name.upper().replace('_', ' ')}")
            self.stdout.write(f"Requirement: {check_result['requirement']}")
            self.stdout.write(status_style(f"Status: {status}"))
            
            if check_result['issues']:
                self.stdout.write(self.style.WARNING("Issues:"))
                for issue in check_result['issues']:
                    self.stdout.write(f"  - {issue}")
            
            if detailed and check_result['recommendations']:
                self.stdout.write("Recommendations:")
                for rec in check_result['recommendations']:
                    self.stdout.write(f"  • {rec}")
        
        if results['recommendations']:
            self.stdout.write(f"\n{self.style.WARNING('OVERALL RECOMMENDATIONS:')}")
            for i, rec in enumerate(results['recommendations'], 1):
                self.stdout.write(f"{i}. {rec}")
    
    def _fix_common_issues(self, results):
        """Attempt to fix common compliance issues."""
        self.stdout.write(f"\n{self.style.WARNING('Attempting to fix common issues...')}")
        
        fixed_count = 0
        
        # Check for unencrypted payment gateway credentials
        for gateway in PaymentGateway.objects.all():
            if gateway.api_key and not self._is_encrypted(gateway.api_key):
                self.stdout.write(f"Encrypting API key for gateway: {gateway.name}")
                # Re-encrypt using proper encryption
                decrypted_key = gateway.api_key
                gateway.set_api_key(decrypted_key)
                gateway.save()
                fixed_count += 1
            
            if gateway.api_secret and not self._is_encrypted(gateway.api_secret):
                self.stdout.write(f"Encrypting API secret for gateway: {gateway.name}")
                decrypted_secret = gateway.api_secret
                gateway.set_api_secret(decrypted_secret)
                gateway.save()
                fixed_count += 1
        
        # Create missing audit logs
        payments_without_logs = Payment.objects.filter(
            audit_logs__isnull=True
        )
        
        for payment in payments_without_logs:
            PaymentAuditLog.objects.create(
                payment=payment,
                user=payment.user,
                action=PaymentAuditLog.Action.PAYMENT_CREATED,
                description=f"Retroactive audit log for payment {payment.id}",
            )
            fixed_count += 1
        
        if fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Fixed {fixed_count} compliance issues")
            )
        else:
            self.stdout.write("No fixable issues found")
    
    def _export_results(self, results, filename):
        """Export results to JSON file."""
        try:
            # Convert datetime objects to strings for JSON serialization
            export_data = {
                'timestamp': timezone.now().isoformat(),
                'compliance_check': results,
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f"Results exported to: {filename}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to export results: {str(e)}")
            )
    
    def _is_encrypted(self, data):
        """Check if data appears to be encrypted."""
        try:
            import base64
            base64.urlsafe_b64decode(data.encode())
            return True
        except Exception:
            return False