"""
Views for accounts app.
"""

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.urls import reverse
import uuid
import random

from .models import User, UserProfile
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    UserProfileUpdateSerializer,
)
from .permissions import IsOwner, CanManageUsers


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view with additional user data."""
    
    def post(self, request, *args, **kwargs):
        """Override to include user data in response."""
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Get user data
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data['user']
                user_serializer = UserSerializer(user)
                
                # Add user data to response
                response.data['user'] = user_serializer.data
                
                # Update last login IP
                user.last_login_ip = self.get_client_ip(request)
                user.save(update_fields=['last_login_ip'])
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class UserRegistrationView(generics.CreateAPIView):
    """User registration view."""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Create new user and send verification email."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Generate email verification token
        user.email_verification_token = str(uuid.uuid4())
        user.save()
        
        # Send verification email
        self.send_verification_email(user, request)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Registration successful. Please check your email for verification.',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
    
    def send_verification_email(self, user, request):
        """Send email verification email."""
        try:
            verification_url = request.build_absolute_uri(
                reverse('accounts:verify-email', kwargs={
                    'token': user.email_verification_token
                })
            )
            
            subject = 'Verify your NeuroRides account'
            message = render_to_string('accounts/verification_email.html', {
                'user': user,
                'verification_url': verification_url,
            })
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
                fail_silently=True,
            )
        except Exception as e:
            # Log error but don't fail registration
            print(f"Failed to send verification email: {e}")


class EmailVerificationView(APIView):
    """Email verification view."""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        """Verify email with token."""
        try:
            user = User.objects.get(email_verification_token=token)
            user.is_verified = True
            user.email_verification_token = None
            user.save()
            
            return Response({
                'message': 'Email verified successfully.'
            }, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid verification token.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    """Resend email verification view."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Resend verification email."""
        user = request.user
        
        if user.is_verified:
            return Response({
                'message': 'Email is already verified.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate new token
        user.email_verification_token = str(uuid.uuid4())
        user.save()
        
        # Send verification email
        try:
            verification_url = request.build_absolute_uri(
                reverse('accounts:verify-email', kwargs={
                    'token': user.email_verification_token
                })
            )
            
            subject = 'Verify your NeuroRides account'
            message = render_to_string('accounts/verification_email.html', {
                'user': user,
                'verification_url': verification_url,
            })
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
                fail_silently=False,
            )
            
            return Response({
                'message': 'Verification email sent successfully.'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': 'Failed to send verification email.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile view."""
    
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_object(self):
        """Get user profile."""
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class PasswordChangeView(APIView):
    """Password change view."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Change user password."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class LogoutView(APIView):
    """Logout view."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Logout user by blacklisting refresh token."""
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'message': 'Logged out successfully.'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': 'Invalid token.'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """User list view for admins."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]
    
    def get_queryset(self):
        """Filter users based on role."""
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset.order_by('-created_at')


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """User detail view for admins."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    """Get current user data."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_phone_verification(request):
    """Send phone verification OTP."""
    phone_number = request.data.get('phone_number')
    
    if not phone_number:
        return Response({
            'error': 'Phone number is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        user.phone_verification_token = otp
        user.save()
        
        # In production, send SMS via SMS gateway
        # For development, just return success
        print(f"Phone verification OTP for {phone_number}: {otp}")
        
        return Response({
            'message': 'Verification code sent to your phone.'
        }, status=status.HTTP_200_OK)
    
    except User.DoesNotExist:
        return Response({
            'error': 'User with this phone number not found.'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_phone(request):
    """Verify phone with OTP."""
    phone_number = request.data.get('phone_number')
    otp = request.data.get('otp')
    
    if not phone_number or not otp:
        return Response({
            'error': 'Phone number and OTP are required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(
            phone_number=phone_number,
            phone_verification_token=otp
        )
        
        user.is_verified = True
        user.phone_verification_token = None
        user.save()
        
        return Response({
            'message': 'Phone verified successfully.'
        }, status=status.HTTP_200_OK)
    
    except User.DoesNotExist:
        return Response({
            'error': 'Invalid phone number or OTP.'
        }, status=status.HTTP_400_BAD_REQUEST)