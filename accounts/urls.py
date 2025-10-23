"""
URL patterns for accounts app.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication (simplified for now)
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    # path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    # path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    
    # Email verification
    path('auth/verify-email/<str:token>/', views.EmailVerificationView.as_view(), name='verify-email'),
    path('auth/resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    
    # Phone verification
    path('auth/send-phone-verification/', views.send_phone_verification, name='send-phone-verification'),
    path('auth/verify-phone/', views.verify_phone, name='verify-phone'),
    
    # Password management
    path('auth/change-password/', views.PasswordChangeView.as_view(), name='change-password'),
    
    # User profile
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('me/', views.current_user, name='current-user'),
    
    # User management (admin only)
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
]