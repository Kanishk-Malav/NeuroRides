"""
Management command to set up payment gateways.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from payments.models import PaymentGateway


class Command(BaseCommand):
    """Set up payment gateway configurations."""
    
    help = 'Set up payment gateway configurations'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing gateway configurations',
        )
        parser.add_argument(
            '--sandbox',
            action='store_true',
            help='Set up gateways in sandbox mode',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        reset = options['reset']
        sandbox = options.get('sandbox', True)  # Default to sandbox
        
        if reset:
            PaymentGateway.objects.all().delete()
            self.stdout.write(
                self.style.WARNING('Deleted existing payment gateway configurations')
            )
        
        # Default gateway configurations
        gateways = [
            {
                'name': 'Stripe',
                'gateway_type': PaymentGateway.GatewayType.STRIPE,
                'is_active': True,
                'is_sandbox': sandbox,
                'supported_currencies': ['USD', 'EUR', 'GBP', 'CAD'],
                'configuration': {
                    'webhook_endpoint': '/api/payments/webhooks/stripe/',
                    'supported_payment_methods': ['card', 'apple_pay', 'google_pay'],
                },
                # These would be set from environment variables in production
                'api_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', 'pk_test_dummy'),
                'api_secret': getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_dummy'),
                'webhook_secret': getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_dummy'),
            },
            {
                'name': 'Razorpay',
                'gateway_type': PaymentGateway.GatewayType.RAZORPAY,
                'is_active': True,
                'is_sandbox': sandbox,
                'supported_currencies': ['INR'],
                'configuration': {
                    'webhook_endpoint': '/api/payments/webhooks/razorpay/',
                    'supported_payment_methods': ['card', 'upi', 'netbanking', 'wallet'],
                },
                # These would be set from environment variables in production
                'api_key': getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_dummy'),
                'api_secret': getattr(settings, 'RAZORPAY_KEY_SECRET', 'dummy_secret'),
                'webhook_secret': getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'webhook_dummy'),
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for gateway_config in gateways:
            # Extract credentials
            api_key = gateway_config.pop('api_key')
            api_secret = gateway_config.pop('api_secret')
            webhook_secret = gateway_config.pop('webhook_secret')
            
            gateway, created = PaymentGateway.objects.get_or_create(
                name=gateway_config['name'],
                defaults=gateway_config
            )
            
            # Set encrypted credentials
            gateway.set_api_key(api_key)
            gateway.set_api_secret(api_secret)
            gateway.set_webhook_secret(webhook_secret)
            
            if created:
                gateway.save()
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created payment gateway: {gateway.name}")
                )
            else:
                # Update existing configuration
                for key, value in gateway_config.items():
                    if key not in ['name']:
                        setattr(gateway, key, value)
                gateway.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"Updated payment gateway: {gateway.name}")
                )
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('PAYMENT GATEWAY SETUP COMPLETE'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Created: {created_count} gateways")
        self.stdout.write(f"Updated: {updated_count} gateways")
        
        mode = "SANDBOX" if sandbox else "PRODUCTION"
        self.stdout.write(f"Mode: {mode}")
        
        # Display all configurations
        self.stdout.write("\nConfigured Payment Gateways:")
        for gateway in PaymentGateway.objects.all().order_by('name'):
            status = "ACTIVE" if gateway.is_active else "INACTIVE"
            mode = "SANDBOX" if gateway.is_sandbox else "PRODUCTION"
            currencies = ', '.join(gateway.supported_currencies) if gateway.supported_currencies else 'None'
            
            self.stdout.write(
                f"  {gateway.name} ({gateway.get_gateway_type_display()}): "
                f"{status} - {mode} - Currencies: {currencies}"
            )
        
        if sandbox:
            self.stdout.write(
                self.style.WARNING(
                    "\nNote: Gateways are configured in SANDBOX mode. "
                    "Use --no-sandbox flag for production setup."
                )
            )