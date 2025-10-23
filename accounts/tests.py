"""
Tests for accounts app.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import json

from .models import UserProfile

User = get_user_model()


class UserModelTest(TestCase):
    """Test User model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'phone_number': '+1234567890',
            'first_name': 'Test',
            'last_name': 'User',
            'role': User.Role.RIDER,
        }
    
    def test_create_user(self):
        """Test user creation."""
        user = User.objects.create_user(
            password='testpass123',
            **self.user_data
        )
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, User.Role.RIDER)
        self.assertFalse(user.is_verified)
        self.assertTrue(user.check_password('testpass123'))
    
    def test_user_profile_creation(self):
        """Test that UserProfile is created automatically."""
        user = User.objects.create_user(
            password='testpass123',
            **self.user_data
        )
        
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)
    
    def test_user_role_properties(self):
        """Test user role property methods."""
        # Test rider
        rider = User.objects.create_user(
            username='rider',
            email='rider@example.com',
            phone_number='+1234567891',
            role=User.Role.RIDER,
            password='testpass123'
        )
        self.assertTrue(rider.is_rider)
        self.assertFalse(rider.is_operator)
        self.assertFalse(rider.is_admin_user)
        
        # Test operator
        operator = User.objects.create_user(
            username='operator',
            email='operator@example.com',
            phone_number='+1234567892',
            role=User.Role.OPERATOR,
            password='testpass123'
        )
        self.assertFalse(operator.is_rider)
        self.assertTrue(operator.is_operator)
        self.assertFalse(operator.is_admin_user)
        
        # Test admin
        admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            phone_number='+1234567893',
            role=User.Role.ADMIN,
            password='testpass123'
        )
        self.assertFalse(admin.is_rider)
        self.assertFalse(admin.is_operator)
        self.assertTrue(admin.is_admin_user)
    
    def test_user_string_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            password='testpass123',
            **self.user_data
        )
        
        expected = f"{user.username} ({user.get_role_display()})"
        self.assertEqual(str(user), expected)
    
    def test_get_full_name(self):
        """Test get_full_name method."""
        user = User.objects.create_user(
            password='testpass123',
            **self.user_data
        )
        
        self.assertEqual(user.get_full_name(), 'Test User')
    
    def test_phone_number_validation(self):
        """Test phone number validation."""
        # Valid phone numbers should work
        valid_phones = ['+1234567890', '1234567890', '+919876543210']
        
        for i, phone in enumerate(valid_phones):
            user_data = self.user_data.copy()
            user_data['username'] = f'user{i}'
            user_data['email'] = f'user{i}@example.com'
            user_data['phone_number'] = phone
            
            user = User.objects.create_user(
                password='testpass123',
                **user_data
            )
            self.assertEqual(user.phone_number, phone)


class UserProfileModelTest(TestCase):
    """Test UserProfile model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='testpass123'
        )
    
    def test_profile_creation(self):
        """Test profile is created with user."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)
    
    def test_profile_string_representation(self):
        """Test profile string representation."""
        expected = f"{self.user.username}'s Profile"
        self.assertEqual(str(self.user.profile), expected)
    
    def test_full_address_property(self):
        """Test full_address property."""
        profile = self.user.profile
        profile.address_line_1 = '123 Main St'
        profile.address_line_2 = 'Apt 4B'
        profile.city = 'New York'
        profile.state = 'NY'
        profile.postal_code = '10001'
        profile.country = 'USA'
        profile.save()
        
        expected = '123 Main St, Apt 4B, New York, NY, 10001, USA'
        self.assertEqual(profile.full_address, expected)


class AuthenticationAPITest(APITestCase):
    """Test authentication API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.register_url = reverse('accounts:register')
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')
        
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'phone_number': '+1234567890',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'rider',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!'
        }
    
    def test_user_registration(self):
        """Test user registration."""
        response = self.client.post(self.register_url, self.user_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertIn('message', response.data)
        
        # Check user was created
        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.is_verified)  # Should not be verified initially
        
        # Check verification email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify your NeuroRides account', mail.outbox[0].subject)
    
    def test_registration_password_mismatch(self):
        """Test registration with password mismatch."""
        data = self.user_data.copy()
        data['password_confirm'] = 'DifferentPassword'
        
        response = self.client.post(self.register_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)
    
    def test_registration_duplicate_email(self):
        """Test registration with duplicate email."""
        # Create first user
        User.objects.create_user(
            username='existing',
            email='test@example.com',
            phone_number='+1234567891',
            password='testpass123'
        )
        
        response = self.client.post(self.register_url, self.user_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_registration_duplicate_phone(self):
        """Test registration with duplicate phone number."""
        # Create first user
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            phone_number='+1234567890',
            password='testpass123'
        )
        
        response = self.client.post(self.register_url, self.user_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)
    
    def test_registration_invalid_role(self):
        """Test registration with invalid role."""
        data = self.user_data.copy()
        data['role'] = 'admin'  # Should not be allowed for public registration
        
        response = self.client.post(self.register_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)
    
    def test_user_login(self):
        """Test user login."""
        # Create user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='TestPass123!'
        )
        
        login_data = {
            'username': 'testuser',
            'password': 'TestPass123!'
        }
        
        response = self.client.post(self.login_url, login_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
    
    def test_login_with_email(self):
        """Test login with email instead of username."""
        # Create user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='TestPass123!'
        )
        
        login_data = {
            'username': 'test@example.com',  # Using email
            'password': 'TestPass123!'
        }
        
        response = self.client.post(self.login_url, login_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        login_data = {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.login_url, login_data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_inactive_user(self):
        """Test login with inactive user."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='TestPass123!',
            is_active=False
        )
        
        login_data = {
            'username': 'testuser',
            'password': 'TestPass123!'
        }
        
        response = self.client.post(self.login_url, login_data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout(self):
        """Test user logout."""
        # Create user and get tokens
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='TestPass123!'
        )
        
        refresh = RefreshToken.for_user(user)
        
        logout_data = {
            'refresh_token': str(refresh)
        }
        
        # Authenticate client
        self.client.force_authenticate(user=user)
        
        response = self.client.post(self.logout_url, logout_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)


class EmailVerificationTest(APITestCase):
    """Test email verification functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='testpass123',
            email_verification_token='test-token-123'
        )
    
    def test_email_verification_success(self):
        """Test successful email verification."""
        url = reverse('accounts:verify-email', kwargs={'token': 'test-token-123'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertIsNone(self.user.email_verification_token)
    
    def test_email_verification_invalid_token(self):
        """Test email verification with invalid token."""
        url = reverse('accounts:verify-email', kwargs={'token': 'invalid-token'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check user is still not verified
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)


class RateLimitingTest(APITestCase):
    """Test rate limiting functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.login_url = reverse('accounts:login')
        cache.clear()  # Clear cache before each test
    
    def test_login_rate_limiting(self):
        """Test rate limiting on login endpoint."""
        login_data = {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        }
        
        # Make requests up to the limit (5 for login)
        for i in range(5):
            response = self.client.post(self.login_url, login_data)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Next request should be rate limited
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Rate limit exceeded', response.data['error'])


class PasswordChangeTest(APITestCase):
    """Test password change functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='OldPass123!'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:change-password')
    
    def test_password_change_success(self):
        """Test successful password change."""
        data = {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'NewPass123!'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))
        self.assertFalse(self.user.check_password('OldPass123!'))
    
    def test_password_change_wrong_old_password(self):
        """Test password change with wrong old password."""
        data = {
            'old_password': 'WrongOldPass',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'NewPass123!'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)
    
    def test_password_change_mismatch(self):
        """Test password change with mismatched new passwords."""
        data = {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'DifferentPass123!'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)


class UserProfileTest(APITestCase):
    """Test user profile functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            phone_number='+1234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:profile')
    
    def test_get_profile(self):
        """Test getting user profile."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('first_name', response.data)
        self.assertIn('last_name', response.data)
        self.assertIn('email', response.data)
    
    def test_update_profile(self):
        """Test updating user profile."""
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'city': 'New York',
            'country': 'USA'
        }
        
        response = self.client.patch(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check user was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        
        # Check profile was updated
        self.assertEqual(self.user.profile.city, 'New York')
        self.assertEqual(self.user.profile.country, 'USA')