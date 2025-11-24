"""
Cache Manager
Handles caching for SERP responses, embeddings, and other expensive operations
"""

import json
import hashlib
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Simple in-memory cache manager
    For production, consider using Redis or Memcached
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = 10000  # Maximum cache entries
        
    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Check expiration
        if entry.get("expires_at"):
            if datetime.utcnow() > entry["expires_at"]:
                del self.cache[key]
                return None
        
        return entry.get("value")
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """
        Set cached value
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        # Evict old entries if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        self.cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        }
        
        logger.debug(f"Cached value for key: {key[:50]}... (TTL: {ttl_seconds}s)")
    
    def _evict_oldest(self):
        """Evict oldest cache entries (FIFO)"""
        if not self.cache:
            return
        
        # Remove 10% of oldest entries
        num_to_remove = max(1, len(self.cache) // 10)
        
        # Sort by creation time
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].get("created_at", datetime.utcnow())
        )
        
        for key, _ in sorted_entries[:num_to_remove]:
            del self.cache[key]
        
        logger.debug(f"Evicted {num_to_remove} oldest cache entries")
    
    async def delete(self, key: str):
        """Delete cached value"""
        if key in self.cache:
            del self.cache[key]
    
    async def clear(self):
        """Clear all cache"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "usage_percent": (len(self.cache) / self.max_size) * 100
        }

