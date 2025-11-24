"""
Rate Limiting Middleware
Implements rate limiting for API endpoints
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from fastapi import Request, HTTPException, status
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter
    For production, consider using Redis-based rate limiting
    """
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 3600  # Clean up old entries every hour
        self.last_cleanup = time.time()
    
    def is_allowed(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> bool:
        """
        Check if request is allowed
        
        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if allowed, False otherwise
        """
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup(now)
            self.last_cleanup = now
        
        # Get requests in current window
        window_start = now - window_seconds
        request_times = self.requests[identifier]
        
        # Remove old requests outside window
        request_times[:] = [t for t in request_times if t > window_start]
        
        # Check if limit exceeded
        if len(request_times) >= max_requests:
            return False
        
        # Add current request
        request_times.append(now)
        return True
    
    def _cleanup(self, now: float):
        """Clean up old request entries"""
        cutoff = now - 3600  # Remove entries older than 1 hour
        
        identifiers_to_remove = []
        for identifier, request_times in self.requests.items():
            request_times[:] = [t for t in request_times if t > cutoff]
            if not request_times:
                identifiers_to_remove.append(identifier)
        
        for identifier in identifiers_to_remove:
            del self.requests[identifier]
        
        if identifiers_to_remove:
            logger.debug(f"Cleaned up {len(identifiers_to_remove)} rate limit entries")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware
    
    Limits:
    - Auth endpoints: 10 requests/minute
    - Chat endpoints: 30 requests/minute
    - Other endpoints: 100 requests/minute
    """
    try:
        # Get identifier (user_id from token if available, otherwise IP)
        identifier = request.client.host if request.client else "unknown"
        
        # Get user_id from request state if available (set by auth middleware)
        if hasattr(request.state, "user_id"):
            identifier = f"user:{request.state.user_id}"
        
        # Determine rate limit based on endpoint
        path = request.url.path
        
        if "/api/auth" in path:
            # Higher limit for auth endpoints - login/profile might be called frequently
            # Separate limits for login vs profile
            if "/api/auth/login" in path or "/api/auth/register" in path:
                max_requests = 20  # 20 login attempts per minute
            elif "/api/auth/profile" in path:
                max_requests = 120  # 120 profile requests per minute (2 per second) - increased for development
            else:
                max_requests = 30  # Other auth endpoints
            window_seconds = 60
        elif "/api/chats" in path:
            # Higher limit for chats endpoint (used for polling chat list)
            max_requests = 120  # 2 requests per second
            window_seconds = 60
        elif "/api/chat" in path:
            max_requests = 30
            window_seconds = 60
        else:
            max_requests = 100
            window_seconds = 60
        
        # Check rate limit
        if not _rate_limiter.is_allowed(identifier, max_requests, window_seconds):
            logger.warning(f"Rate limit exceeded for {identifier} on {path} (limit: {max_requests}/{window_seconds}s)")
            # Return 429 error - don't raise to avoid EndOfStream issues
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds. Please wait a moment and try again."
                }
            )
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Handle client disconnection gracefully
            from anyio import EndOfStream
            if isinstance(e, EndOfStream):
                logger.debug(f"Client disconnected during request: {path}")
                # Return empty response instead of raising
                from fastapi.responses import Response
                return Response(status_code=204)  # No Content
            raise
    except HTTPException:
        # Re-raise HTTPException - let FastAPI handle it
        # If client disconnected, EndOfStream will be caught by global handler
        raise
    except Exception as e:
        # Handle client disconnection gracefully
        from anyio import EndOfStream
        if isinstance(e, EndOfStream):
            # Client disconnected, don't try to send response
            # Let it propagate to global handler
            logger.debug(f"Client disconnected during rate limit check: {identifier if 'identifier' in locals() else 'unknown'}")
            raise
        # Re-raise other exceptions
        raise

