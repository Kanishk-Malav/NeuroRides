"""
Custom permissions for role-based access control.
"""

from rest_framework import permissions


class IsRider(permissions.BasePermission):
    """Permission class for riders."""
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is a rider."""
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_rider
        )


class IsOperator(permissions.BasePermission):
    """Permission class for operators."""
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is an operator."""
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_operator
        )


class IsAdmin(permissions.BasePermission):
    """Permission class for admins."""
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is an admin."""
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_admin_user
        )


class IsOperatorOrAdmin(permissions.BasePermission):
    """Permission class for operators or admins."""
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is an operator or admin."""
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_operator or request.user.is_admin_user)
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission class for object owners."""
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the object or has read-only access."""
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to the owner
        return obj.user == request.user


class IsOwner(permissions.BasePermission):
    """Permission class for object owners only."""
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the object."""
        return obj.user == request.user


class CanManageUsers(permissions.BasePermission):
    """Permission class for user management."""
    
    def has_permission(self, request, view):
        """Check if user can manage other users."""
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_admin_user or request.user.is_staff)
        )


class RoleBasedPermission(permissions.BasePermission):
    """
    Custom permission class that checks user roles.
    
    Usage in views:
    permission_classes = [RoleBasedPermission]
    required_roles = ['admin', 'operator']  # Define in view
    """
    
    def has_permission(self, request, view):
        """Check if user has required role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get required roles from view
        required_roles = getattr(view, 'required_roles', [])
        
        if not required_roles:
            # If no specific roles required, just check authentication
            return True
        
        # Check if user role is in required roles
        user_role = request.user.role
        return user_role in required_roles