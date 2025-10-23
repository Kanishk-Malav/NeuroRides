"""
Celery configuration for payment processing tasks.
"""

from celery.schedules import crontab

# Payment-specific task routing
PAYMENTS_TASK_ROUTES = {
    'payments.tasks.process_payment_async': {'queue': 'payments_high'},
    'payments.tasks.retry_failed_payments': {'queue': 'payments_medium'},
    'payments.tasks.process_refund_async': {'queue': 'payments_medium'},
    'payments.tasks.generate_payment_receipts': {'queue': 'payments_low'},
    'payments.tasks.reconcile_payment_records': {'queue': 'payments_low'},
    'payments.tasks.cleanup_expired_payment_intents': {'queue': 'payments_low'},
    'payments.tasks.check_pci_compliance': {'queue': 'payments_low'},
    'payments.tasks.generate_financial_reports': {'queue': 'payments_low'},
}

# Periodic task schedule for payment processing
PAYMENTS_BEAT_SCHEDULE = {
    # Retry failed payments every 30 minutes
    'retry-failed-payments': {
        'task': 'payments.tasks.retry_failed_payments',
        'schedule': crontab(minute='*/30'),
    },
    
    # Generate receipts every 15 minutes
    'generate-payment-receipts': {
        'task': 'payments.tasks.generate_payment_receipts',
        'schedule': crontab(minute='*/15'),
    },
    
    # Reconcile payment records daily at 2 AM
    'reconcile-payment-records': {
        'task': 'payments.tasks.reconcile_payment_records',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Clean up expired payment intents every 4 hours
    'cleanup-expired-payment-intents': {
        'task': 'payments.tasks.cleanup_expired_payment_intents',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    
    # Check PCI compliance daily at 3 AM
    'check-pci-compliance': {
        'task': 'payments.tasks.check_pci_compliance',
        'schedule': crontab(hour=3, minute=0),
    },
    
    # Generate financial reports daily at 5 AM
    'generate-financial-reports': {
        'task': 'payments.tasks.generate_financial_reports',
        'schedule': crontab(hour=5, minute=0),
    },
}