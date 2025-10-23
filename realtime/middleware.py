"""
WebSocket middleware for logging and error handling.
"""

import json
import logging
import time
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


class WebSocketLoggingMiddleware(BaseMiddleware):
    """Middleware for logging WebSocket connections and messages."""
    
    async def __call__(self, scope, receive, send):
        """Process WebSocket connection."""
        
        # Log connection attempt
        client_ip = self.get_client_ip(scope)
        path = scope.get('path', 'unknown')
        
        logger.info(f"WebSocket connection attempt from {client_ip} to {path}")
        
        # Add timing
        start_time = time.time()
        
        try:
            # Call the next middleware/consumer
            await super().__call__(scope, receive, send)
            
        except Exception as e:
            logger.error(f"WebSocket error on {path} from {client_ip}: {str(e)}")
            raise
        
        finally:
            # Log connection duration
            duration = time.time() - start_time
            logger.info(f"WebSocket connection to {path} lasted {duration:.2f} seconds")
    
    def get_client_ip(self, scope):
        """Extract client IP from scope."""
        headers = dict(scope.get('headers', []))
        
        # Check for forwarded IP first
        forwarded_for = headers.get(b'x-forwarded-for')
        if forwarded_for:
            return forwarded_for.decode().split(',')[0].strip()
        
        # Check for real IP
        real_ip = headers.get(b'x-real-ip')
        if real_ip:
            return real_ip.decode()
        
        # Fall back to client address
        client = scope.get('client')
        if client:
            return client[0]
        
        return 'unknown'


class WebSocketAuthMiddleware(BaseMiddleware):
    """Middleware for WebSocket authentication."""
    
    async def __call__(self, scope, receive, send):
        """Authenticate WebSocket connection."""
        
        # Get user from session (if available)
        user = scope.get('user')
        
        if isinstance(user, AnonymousUser):
            # Try to authenticate using query parameters or headers
            user = await self.authenticate_from_params(scope)
            scope['user'] = user
        
        # Log authentication result
        if isinstance(user, AnonymousUser):
            logger.warning(f"Anonymous WebSocket connection to {scope.get('path')}")
        else:
            logger.info(f"Authenticated WebSocket connection: {user.username}")
        
        await super().__call__(scope, receive, send)
    
    async def authenticate_from_params(self, scope):
        """Try to authenticate from query parameters."""
        # This is a simplified example - in production, you'd want more secure authentication
        query_string = scope.get('query_string', b'').decode()
        
        if 'token=' in query_string:
            # Extract token from query string
            token = None
            for param in query_string.split('&'):
                if param.startswith('token='):
                    token = param.split('=', 1)[1]
                    break
            
            if token:
                # Validate token and get user
                user = await self.get_user_from_token(token)
                if user:
                    return user
        
        return AnonymousUser()
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Get user from authentication token."""
        # This is a placeholder - implement your token validation logic
        # For example, JWT token validation or session token lookup
        try:
            # Simple example - in production use proper JWT validation
            if token.startswith('user_'):
                user_id = int(token.replace('user_', ''))
                return User.objects.get(id=user_id)
        except (ValueError, User.DoesNotExist):
            pass
        
        return None


class WebSocketErrorHandlingMiddleware(BaseMiddleware):
    """Middleware for handling WebSocket errors gracefully."""
    
    async def __call__(self, scope, receive, send):
        """Handle WebSocket errors."""
        
        try:
            await super().__call__(scope, receive, send)
            
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}", exc_info=True)
            
            # Try to send error message to client
            try:
                await send({
                    'type': 'websocket.send',
                    'text': json.dumps({
                        'type': 'error',
                        'message': 'Internal server error',
                        'timestamp': time.time()
                    })
                })
            except:
                pass  # Connection might be closed
            
            # Close connection gracefully
            try:
                await send({
                    'type': 'websocket.close',
                    'code': 1011  # Internal error
                })
            except:
                pass


def WebSocketMiddlewareStack(inner):
    """Stack of WebSocket middlewares."""
    return WebSocketErrorHandlingMiddleware(
        WebSocketLoggingMiddleware(
            WebSocketAuthMiddleware(inner)
        )
    )