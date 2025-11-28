"""
Encryption utilities for sensitive payment data.
"""

import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings


logger = logging.getLogger(__name__)


class PaymentDataEncryption:
    """Handles encryption and decryption of sensitive payment data."""

    def __init__(self):
        self._fernet = None
        self._initialize_encryption()

    def _initialize_encryption(self):
        """
        Initialize encryption key.

        Simplified approach:
        - If PAYMENT_ENCRYPTION_KEY exists, use it.
        - Otherwise ALWAYS derive a stable encryption key from SECRET_KEY.
        This avoids deployment crashes and ensures consistency.
        """

        base_key = getattr(settings, "PAYMENT_ENCRYPTION_KEY", None)

        # Always fallback to SECRET_KEY (always present)
        if not base_key:
            base_key = settings.SECRET_KEY

        if isinstance(base_key, str):
            base_key = base_key.encode()

        # Derive proper Fernet key
        encryption_key = self._derive_key_from_password(base_key)
        self._fernet = Fernet(encryption_key)

    def _derive_key_from_password(self, password: bytes) -> bytes:
        """Derive a Fernet-compatible key from any bytes."""
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
                    pass

        return decrypted_dict


# Global encryption instance
payment_encryption = PaymentDataEncryption()


class EncryptedTextField:
    """Custom descriptor for encrypted model fields."""

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
    """Decrypt sensitive payment data."""
    sensitive_fields = [
        'card_number', 'cvv', 'account_number', 'routing_number',
        'wallet_token', 'bank_account_token'
    ]

    return payment_encryption.decrypt_dict(encrypted_data, sensitive_fields)


def mask_sensitive_data(data: str, mask_char='*', visible_chars=4) -> str:
    """Mask sensitive data for logs / UI."""
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ''

    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]


def validate_pci_compliance(payment_data: dict) -> dict:
    """PCI compliance helper."""

    issues = []

    sensitive_fields = ['card_number', 'cvv', 'account_number', 'routing_number']

    for field in sensitive_fields:
        if field in payment_data:
            val = payment_data[field]
            if val and not _is_encrypted(val):
                issues.append(f"Unencrypted {field} detected")

    if 'card_number' in payment_data:
        card = payment_data['card_number']
        if card and len(card) > 6 and not _is_masked(card):
            issues.append("Card number not properly masked")

    return {
        'compliant': len(issues) == 0,
        'issues': issues,
        'recommendations': [
            "Encrypt all sensitive payment data",
            "Mask sensitive fields in logs",
            "Use TLS for transmission",
            "Rotate encryption keys periodically"
        ]
    }


def _is_encrypted(data: str) -> bool:
    try:
        base64.urlsafe_b64decode(data.encode())
        return True
    except Exception:
        return False


def _is_masked(data: str) -> bool:
    return '*' in data or 'X' in data


class PaymentAuditLogger:
    """Simple audit logger for payment events."""
    def log(self, message):
        print(f"[PAYMENT AUDIT] {message}")

# Global audit logger instance (THIS WAS MISSING)
payment_audit_logger = PaymentAuditLogger()
