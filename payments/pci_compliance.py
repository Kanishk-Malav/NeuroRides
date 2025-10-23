"""
PCI DSS compliance utilities for payment processing.
"""

import re
import logging
from typing import Dict, List, Any, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import Payment, PaymentMethod, PaymentGateway, PaymentAuditLog
from .encryption import payment_encryption, mask_sensitive_data

logger = logging.getLogger(__name__)


class PCIComplianceChecker:
    """PCI DSS compliance checker for payment data."""
    
    # PCI DSS requirements mapping
    PCI_REQUIREMENTS = {
        'requirement_1': 'Install and maintain a firewall configuration',
        'requirement_2': 'Do not use vendor-supplied defaults for system passwords',
        'requirement_3': 'Protect stored cardholder data',
        'requirement_4': 'Encrypt transmission of cardholder data across open networks',
        'requirement_5': 'Protect all systems against malware',
        'requirement_6': 'Develop and maintain secure systems and applications',
        'requirement_7': 'Restrict access to cardholder data by business need-to-know',
        'requirement_8': 'Identify and authenticate access to system components',
        'requirement_9': 'Restrict physical access to cardholder data',
        'requirement_10': 'Track and monitor all access to network resources',
        'requirement_11': 'Regularly test security systems and processes',
        'requirement_12': 'Maintain a policy that addresses information security',
    }
    
    # Sensitive data patterns
    SENSITIVE_PATTERNS = {
        'card_number': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'cvv': r'\b\d{3,4}\b',
        'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
        'account_number': r'\b\d{8,17}\b',
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_data_encryption(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if sensitive data is properly encrypted."""
        issues = []
        recommendations = []
        
        # Check for unencrypted sensitive data
        for field_name, value in data.items():
            if self._is_sensitive_field(field_name):
                if value and not self._is_encrypted_data(str(value)):
                    issues.append(f"Unencrypted sensitive data in field: {field_name}")
        
        # Check for proper masking
        for field_name, value in data.items():
            if field_name.lower() in ['card_number', 'account_number']:
                if value and not self._is_properly_masked(str(value)):
                    issues.append(f"Improperly masked data in field: {field_name}")
        
        if issues:
            recommendations.extend([
                "Encrypt all sensitive payment data using strong encryption (AES-256)",
                "Mask sensitive data for display and logging purposes",
                "Implement proper key management practices",
            ])
        
        return {
            'requirement': 'PCI DSS Requirement 3 - Protect stored cardholder data',
            'compliant': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def check_access_controls(self, user_id: str, requested_data: List[str]) -> Dict[str, Any]:
        """Check access controls for cardholder data."""
        issues = []
        recommendations = []
        
        # Check if user has appropriate permissions
        sensitive_fields = ['card_number', 'cvv', 'account_number', 'routing_number']
        
        for field in requested_data:
            if field in sensitive_fields:
                # In a real implementation, check user roles and permissions
                if not self._user_has_permission(user_id, field):
                    issues.append(f"User {user_id} lacks permission to access {field}")
        
        if issues:
            recommendations.extend([
                "Implement role-based access control (RBAC)",
                "Restrict access to cardholder data on need-to-know basis",
                "Regular review of user access permissions",
            ])
        
        return {
            'requirement': 'PCI DSS Requirement 7 - Restrict access to cardholder data',
            'compliant': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def check_audit_logging(self, payment_id: str = None) -> Dict[str, Any]:
        """Check audit logging compliance."""
        issues = []
        recommendations = []
        
        # Check if audit logs exist
        if payment_id:
            audit_logs = PaymentAuditLog.objects.filter(payment_id=payment_id)
            if not audit_logs.exists():
                issues.append(f"No audit logs found for payment {payment_id}")
        
        # Check audit log completeness
        required_actions = [
            PaymentAuditLog.Action.PAYMENT_CREATED,
            PaymentAuditLog.Action.PAYMENT_PROCESSED,
        ]
        
        if payment_id:
            logged_actions = audit_logs.values_list('action', flat=True)
            for action in required_actions:
                if action not in logged_actions:
                    issues.append(f"Missing audit log for action: {action}")
        
        if issues:
            recommendations.extend([
                "Implement comprehensive audit logging for all payment operations",
                "Ensure audit logs are tamper-evident and secure",
                "Regular review of audit logs for suspicious activities",
            ])
        
        return {
            'requirement': 'PCI DSS Requirement 10 - Track and monitor access',
            'compliant': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def check_network_security(self) -> Dict[str, Any]:
        """Check network security compliance."""
        issues = []
        recommendations = []
        
        # Check SSL/TLS configuration
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            issues.append("SSL redirect not enabled")
        
        if not getattr(settings, 'SECURE_HSTS_SECONDS', 0):
            issues.append("HSTS not configured")
        
        # Check for secure cookies
        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            issues.append("Session cookies not marked as secure")
        
        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            issues.append("CSRF cookies not marked as secure")
        
        if issues:
            recommendations.extend([
                "Enable SSL/TLS for all payment-related communications",
                "Implement HTTP Strict Transport Security (HSTS)",
                "Use secure cookies for session management",
                "Regularly update SSL/TLS certificates",
            ])
        
        return {
            'requirement': 'PCI DSS Requirement 4 - Encrypt transmission of data',
            'compliant': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def check_password_security(self) -> Dict[str, Any]:
        """Check password and authentication security."""
        issues = []
        recommendations = []
        
        # Check password configuration
        auth_password_validators = getattr(settings, 'AUTH_PASSWORD_VALIDATORS', [])
        
        if not auth_password_validators:
            issues.append("No password validators configured")
        
        # Check for strong password requirements
        has_length_validator = any(
            'MinimumLengthValidator' in validator.get('NAME', '')
            for validator in auth_password_validators
        )
        
        if not has_length_validator:
            issues.append("Minimum password length not enforced")
        
        if issues:
            recommendations.extend([
                "Implement strong password policies",
                "Require minimum password length of 8 characters",
                "Enforce password complexity requirements",
                "Implement account lockout after failed attempts",
            ])
        
        return {
            'requirement': 'PCI DSS Requirement 8 - Identify and authenticate access',
            'compliant': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def run_comprehensive_check(self, payment_id: str = None, 
                              user_id: str = None, 
                              data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run comprehensive PCI compliance check."""
        
        results = {
            'overall_compliant': True,
            'checks': {},
            'summary': {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 0,
                'total_issues': 0,
            },
            'recommendations': [],
        }
        
        # Run individual checks
        checks = [
            ('data_encryption', self.check_data_encryption(data or {})),
            ('network_security', self.check_network_security()),
            ('password_security', self.check_password_security()),
            ('audit_logging', self.check_audit_logging(payment_id)),
        ]
        
        if user_id and data:
            checks.append((
                'access_controls',
                self.check_access_controls(user_id, list(data.keys()))
            ))
        
        # Process results
        for check_name, check_result in checks:
            results['checks'][check_name] = check_result
            results['summary']['total_checks'] += 1
            
            if check_result['compliant']:
                results['summary']['passed_checks'] += 1
            else:
                results['summary']['failed_checks'] += 1
                results['overall_compliant'] = False
                results['summary']['total_issues'] += len(check_result['issues'])
                results['recommendations'].extend(check_result['recommendations'])
        
        # Remove duplicate recommendations
        results['recommendations'] = list(set(results['recommendations']))
        
        return results
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field contains sensitive data."""
        sensitive_fields = [
            'card_number', 'cvv', 'cvv2', 'cvc', 'cid',
            'account_number', 'routing_number', 'ssn',
            'api_key', 'api_secret', 'webhook_secret',
            'password', 'token', 'private_key'
        ]
        
        return field_name.lower() in sensitive_fields
    
    def _is_encrypted_data(self, data: str) -> bool:
        """Check if data appears to be encrypted."""
        try:
            # Check if it's base64 encoded (encrypted data should be)
            import base64
            base64.urlsafe_b64decode(data.encode())
            
            # Check if it contains only base64 characters
            base64_pattern = r'^[A-Za-z0-9+/]*={0,2}$'
            return bool(re.match(base64_pattern, data))
        except Exception:
            return False
    
    def _is_properly_masked(self, data: str) -> bool:
        """Check if sensitive data is properly masked."""
        # Data should contain masking characters
        masking_chars = ['*', 'X', '#']
        return any(char in data for char in masking_chars)
    
    def _user_has_permission(self, user_id: str, field: str) -> bool:
        """Check if user has permission to access sensitive field."""
        # In a real implementation, check user roles and permissions
        # For now, return True for demonstration
        return True


class PCIDataSanitizer:
    """Sanitize data for PCI compliance."""
    
    def __init__(self):
        self.checker = PCIComplianceChecker()
    
    def sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for safe logging."""
        sanitized = {}
        
        for key, value in data.items():
            if self.checker._is_sensitive_field(key):
                if key.lower() in ['card_number', 'account_number']:
                    sanitized[key] = mask_sensitive_data(str(value), '*', 4)
                elif key.lower() in ['cvv', 'cvv2', 'cvc']:
                    sanitized[key] = '***'
                elif key.lower() in ['api_key', 'api_secret', 'password']:
                    sanitized[key] = '[REDACTED]'
                else:
                    sanitized[key] = mask_sensitive_data(str(value), '*', 2)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def sanitize_for_display(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for user display."""
        sanitized = {}
        
        for key, value in data.items():
            if key.lower() == 'card_number':
                sanitized[key] = mask_sensitive_data(str(value), '*', 4)
            elif key.lower() in ['cvv', 'cvv2', 'cvc']:
                sanitized[key] = '***'
            elif key.lower() in ['account_number']:
                sanitized[key] = mask_sensitive_data(str(value), '*', 4)
            elif key.lower() in ['api_key', 'api_secret']:
                sanitized[key] = '[HIDDEN]'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def validate_card_number(self, card_number: str) -> Tuple[bool, str]:
        """Validate credit card number using Luhn algorithm."""
        # Remove spaces and hyphens
        card_number = re.sub(r'[\s-]', '', card_number)
        
        # Check if it's all digits
        if not card_number.isdigit():
            return False, "Card number must contain only digits"
        
        # Check length
        if len(card_number) < 13 or len(card_number) > 19:
            return False, "Card number must be between 13 and 19 digits"
        
        # Luhn algorithm
        def luhn_check(card_num):
            digits = [int(d) for d in card_num]
            for i in range(len(digits) - 2, -1, -2):
                digits[i] *= 2
                if digits[i] > 9:
                    digits[i] -= 9
            return sum(digits) % 10 == 0
        
        if not luhn_check(card_number):
            return False, "Invalid card number (failed Luhn check)"
        
        return True, "Valid card number"
    
    def detect_card_type(self, card_number: str) -> str:
        """Detect credit card type from number."""
        card_number = re.sub(r'[\s-]', '', card_number)
        
        patterns = {
            'Visa': r'^4[0-9]{12}(?:[0-9]{3})?$',
            'Mastercard': r'^5[1-5][0-9]{14}$',
            'American Express': r'^3[47][0-9]{13}$',
            'Discover': r'^6(?:011|5[0-9]{2})[0-9]{12}$',
            'Diners Club': r'^3[0689][0-9]{11}$',
            'JCB': r'^(?:2131|1800|35\d{3})\d{11}$',
        }
        
        for card_type, pattern in patterns.items():
            if re.match(pattern, card_number):
                return card_type
        
        return 'Unknown'


# Global instances
pci_checker = PCIComplianceChecker()
pci_sanitizer = PCIDataSanitizer()