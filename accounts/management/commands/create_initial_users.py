"""
Management command to create initial users for development.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    """Create initial users for development and testing."""
    
    help = 'Create initial users for development'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip creation if users already exist',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@neurorides.com',
                'phone_number': '+1234567890',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'password': 'admin123456'
            },
            {
                'username': 'operator1',
                'email': 'operator@neurorides.com',
                'phone_number': '+1234567891',
                'first_name': 'Fleet',
                'last_name': 'Operator',
                'role': User.Role.OPERATOR,
                'is_staff': True,
                'is_verified': True,
                'password': 'operator123456'
            },
            {
                'username': 'rider1',
                'email': 'rider@neurorides.com',
                'phone_number': '+1234567892',
                'first_name': 'John',
                'last_name': 'Rider',
                'role': User.Role.RIDER,
                'is_verified': True,
                'password': 'rider123456'
            }
        ]
        
        created_count = 0
        
        for user_data in users_data:
            username = user_data['username']
            
            if User.objects.filter(username=username).exists():
                if options['skip_existing']:
                    self.stdout.write(
                        self.style.WARNING(f'User {username} already exists, skipping...')
                    )
                    continue
                else:
                    self.stdout.write(
                        self.style.WARNING(f'User {username} already exists, updating...')
                    )
                    user = User.objects.get(username=username)
                    for key, value in user_data.items():
                        if key != 'password':
                            setattr(user, key, value)
                    user.set_password(user_data['password'])
                    user.save()
            else:
                password = user_data.pop('password')
                user = User.objects.create_user(password=password, **user_data)
                created_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created user: {username} ({user.role})')
                )
        
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} users')
            )
        else:
            self.stdout.write(
                self.style.WARNING('No new users created')
            )
        
        # Display login information
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('LOGIN INFORMATION:'))
        self.stdout.write('='*50)
        
        for user_data in users_data:
            self.stdout.write(
                f"Role: {user_data['role'].title()}\n"
                f"Username: {user_data['username']}\n"
                f"Email: {user_data['email']}\n"
                f"Password: {user_data.get('password', 'Not shown')}\n"
                f"{'-'*30}"
            )