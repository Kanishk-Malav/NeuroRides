"""
Encryption utilities for sensitive payment data.
"""

import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import os

logger = logging.getLogger(__name__)


class PaymentDataEncryption:
    """Handles encryption and decryption of sensitive payment data."""
    
    def __init__(self):
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption with key from settings."""
        encryption_key = getattr(settings, 'PAYMENT_ENCRYPTION_KEY', None)
        
        if not encryption_key:
            # Generate a key if not provided (for development only)
            if settings.DEBUG:
                logger.warning("No PAYMENT_ENCRYPTION_KEY found, generating temporary key for development")
                encryption_key = Fernet.generate_key().decode()
            else:
                raise ImproperlyConfigured(
                    "PAYMENT_ENCRYPTION_KEY must be set in production settings"
                )
        
        # If key is a string, encode it
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        
        # If key looks like a password, derive a proper key
        if len(encryption_key) != 44:  # Fernet keys are 44 characters when base64 encoded
            encryption_key = self._derive_key_from_password(encryption_key)
        
        try:
            self._fernet = Fernet(encryption_key)
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid PAYMENT_ENCRYPTION_KEY: {str(e)}")
    
    def _derive_key_from_password(self, password: bytes) -> bytes:
        """Derive a Fernet key from a password."""
        # Use a fixed salt for consistency (in production, use a proper salt management system)
        salt = b'neurorides_payment_salt_2024'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not data:
            return data
        
        try:
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not encrypted_data:
            return encrypted_data
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data_dict: dict, fields_to_encrypt: list) -> dict:
        """Encrypt specific fields in a dictionary."""
        encrypted_dict = data_dict.copy()
        
        for field in fields_to_encrypt:
            if field in encrypted_dict and encrypted_dict[field]:
                encrypted_dict[field] = self.encrypt(str(encrypted_dict[field]))
        
        return encrypted_dict
    
    def decrypt_dict(self, encrypted_dict: dict, fields_to_decrypt: list) -> dict:
        """Decrypt specific fields in a dictionary."""
        decrypted_dict = encrypted_dict.copy()
        
        for field in fields_to_decrypt:
            if field in decrypted_dict and decrypted_dict[field]:
                try:
                    decrypted_dict[field] = self.decrypt(decrypted_dict[field])
                except ValueError:
                    # Field might not be encrypted, leave as is
                    pass
        
        return decrypted_dict


# Global encryption instance
payment_encryption = PaymentDataEncryption()


class EncryptedTextField:
    """Custom field descriptor for encrypted text fields."""
    
    def __init__(self, field_name):
        self.field_name = field_name
        self.encrypted_field_name = f"_{field_name}_encrypted"
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        encrypted_value = getattr(instance, self.encrypted_field_name, None)
        if encrypted_value:
            try:
                return payment_encryption.decrypt(encrypted_value)
            except ValueError:
                logger.warning(f"Failed to decrypt {self.field_name} for {instance}")
                return None
        return None
    
    def __set__(self, instance, value):
        if value:
            encrypted_value = payment_encryption.encrypt(str(value))
            setattr(instance, self.encrypted_field_name, encrypted_value)
        else:
            setattr(instance, self.encrypted_field_name, None)


def encrypt_payment_method_data(payment_method_data: dict) -> dict:
    """Encrypt sensitive payment method data."""
    sensitive_fields = [
        'card_number', 'cvv', 'account_number', 'routing_number',
        'wallet_token', 'bank_account_token'
    ]
    
    return payment_encryption.encrypt_dict(payment_method_data, sensitive_fields)


def decrypt_payment_method_data(encrypted_data: dict) -> dict:
    """Decrypt sensitive payment method data."""
    sensitive_fields = [
        'card_number', 'cvv', 'account_number', 'routing_number',
        'wallet_token', 'bank_account_token'
    ]
    
    return payment_encryption.decrypt_dict(encrypted_data, sensitive_fields)


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mask sensitive data for display purposes."""
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ''
    
    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]


def validate_pci_compliance(payment_data: dict) -> dict:
    """Validate payment data for PCI compliance."""
    compliance_issues = []
    
    # Check for unencrypted sensitive data
    sensitive_fields = ['card_number', 'cvv', 'account_number', 'routing_number']
    
    for field in sensitive_fields:
        if field in payment_data:
            value = payment_data[field]
            if value and not _is_encrypted(value):
                compliance_issues.append(f"Unencrypted {field} detected")
    
    # Check for proper data masking in logs
    if 'card_number' in payment_data:
        card_number = payment_data['card_number']
        if card_number and len(card_number) > 6 and not _is_masked(card_number):
            compliance_issues.append("Card number not properly masked")
    
    return {
        'compliant': len(compliance_issues) == 0,
        'issues': compliance_issues,
        'recommendations': _get_pci_recommendations(compliance_issues)
    }


def _is_encrypted(data: str) -> bool:
    """Check if data appears to be encrypted."""
    try:
        # Try to decode as base64 - encrypted data should be base64 encoded
        base64.urlsafe_b64decode(data.encode())
        return True
    except Exception:
        return False


def _is_masked(data: str) -> bool:
    """Check if data is properly masked."""
    return '*' in data or 'X' in data


def _get_pci_recommendations(issues: list) -> list:
    """Get PCI compliance recommendations based on issues."""
    recommendations = []
    
    if any('Unencrypted' in issue for issue in issues):
        recommendations.append("Encrypt all sensitive payment data before storage")
    
    if any('not properly masked' in issue for issue in issues):
        recommendations.append("Mask sensitive data in logs and displays")
    
    recommendations.extend([
        "Use strong encryption algorithms (AES-256 or equivalent)",
        "Implement proper key management practices",
        "Regularly rotate encryption keys",
        "Audit access to encrypted payment data",
        "Implement secure data transmission (TLS 1.2+)",
        "Maintain PCI DSS compliance documentation"
    ])
    
    return recommendations


class PaymentAuditLogger:
    """Specialized logger for payment audit trails."""
    
    def __init__(self):
        self.logger = logging.getLogger('payment_audit')
    
    def log_payment_action(self, user_id: str, action: str, payment_id: str = None,
                          amount: str = None, gateway: str = None, 
                          ip_address: str = None, user_agent: str = None,
                          additional_data: dict = None):
        """Log payment-related actions for audit purposes."""
        
        audit_data = {
            'user_id': user_id,
            'action': action,
            'timestamp': logger.handlers[0].formatter.formatTime(
                logging.LogRecord('', 0, '', 0, '', (), None)
            ) if logger.handlers else None,
            'ip_address': ip_address,
            'user_agent': user_agent,
        }
        
        if payment_id:
            audit_data['payment_id'] = payment_id
        
        if amount:
            # Mask amount for certain actions
            if action in ['payment_failed', 'refund_requested']:
                audit_data['amount'] = mask_sensitive_data(str(amount), '*', 2)
            else:
                audit_data['amount'] = amount
        
        if gateway:
            audit_data['gateway'] = gateway
        
        if additional_data:
            # Ensure no sensitive data in additional_data
            safe_additional_data = {}
            for key, value in additional_data.items():
                if key.lower() in ['card_number', 'cvv', 'ssn', 'account_number']:
                    safe_additional_data[key] = mask_sensitive_data(str(value))
                else:
                    safe_additional_data[key] = value
            audit_data['additional_data'] = safe_additional_data
        
        self.logger.info(f"PAYMENT_AUDIT: {audit_data}")
    
    def log_encryption_event(self, event_type: str, field_name: str, 
                           success: bool, error_message: str = None):
        """Log encryption/decryption events."""
        
        audit_data = {
            'event_type': event_type,
            'field_name': field_name,
            'success': success,
            'timestamp': logger.handlers[0].formatter.formatTime(
                logging.LogRecord('', 0, '', 0, '', (), None)
            ) if logger.handlers else None,
        }
        
        if error_message:
            audit_data['error_message'] = error_message
        
        self.logger.info(f"ENCRYPTION_AUDIT: {audit_data}")
    
    def log_pci_compliance_check(self, check_type: str, compliant: bool, 
                               issues: list = None):
        """Log PCI compliance checks."""
        
        audit_data = {
            'check_type': check_type,
            'compliant': compliant,
            'timestamp': logger.handlers[0].formatter.formatTime(
                logging.LogRecord('', 0, '', 0, '', (), None)
            ) if logger.handlers else None,
        }
        
        if issues:
            audit_data['issues_count'] = len(issues)
            # Don't log actual issues to avoid exposing sensitive data
        
        self.logger.warning(f"PCI_COMPLIANCE_AUDIT: {audit_data}")


# Global audit logger instance
payment_audit_logger = PaymentAuditLogger()