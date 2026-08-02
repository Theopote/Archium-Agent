"""Caching infrastructure for frequently accessed data."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, ParamSpec
from functools import wraps
from datetime import timedelta
import hashlib
import json

T = TypeVar('T')
P = ParamSpec('P')


class CacheKey:
    """Generate consistent cache keys from function arguments."""
    
    @staticmethod
    def from_args(*args: Any, **kwargs: Any) -> str:
        """Generate a cache key from function arguments."""
        # Convert args and kwargs to a stable string representation
        key_parts = []
        
        for arg in args:
            if hasattr(arg, 'id'):
                # Use ID for domain objects
                key_parts.append(str(arg.id))
            elif hasattr(arg, '__dict__'):
                # Use dict representation for objects
                key_parts.append(str(sorted(arg.__dict__.items())))
            else:
                key_parts.append(str(arg))
        
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()


class SimpleCache:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: timedelta = timedelta(minutes=30)) -> None:
        self._cache: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
    
    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        import time
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: timedelta | None = None) -> None:
        """Set value in cache with TTL."""
        import time
        ttl = ttl or self._default_ttl
        expiry = time.time() + ttl.total_seconds()
        self._cache[key] = (value, expiry)
    
    def invalidate(self, key: str) -> None:
        """Remove specific key from cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items."""
        import time
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if expiry < current_time
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache instance
_global_cache = SimpleCache()


def cached(ttl: timedelta | None = None, key_prefix: str = ""):
    """Decorator to cache function results.
    
    Args:
        ttl: Time to live for cached values. Defaults to 30 minutes.
        key_prefix: Prefix for cache keys to avoid collisions.
    
    Example:
        @cached(ttl=timedelta(hours=1), key_prefix="design_system")
        def get_design_system(project_id: UUID) -> DesignSystem:
            # Expensive operation
            return load_from_database(project_id)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            cache_key = CacheKey.from_args(*args, **kwargs)
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"
            
            # Try to get from cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _global_cache.set(cache_key, result, ttl)
            return result
        
        # Add cache management methods to the wrapped function
        wrapper.cache_key = lambda *args, **kwargs: f"{key_prefix}:{CacheKey.from_args(*args, **kwargs)}"  # type: ignore
        wrapper.invalidate = lambda *args, **kwargs: _global_cache.invalidate(wrapper.cache_key(*args, **kwargs))  # type: ignore
        wrapper.cache_clear = lambda: _global_cache.clear()  # type: ignore
        
        return wrapper
    return decorator


def get_cache() -> SimpleCache:
    """Get the global cache instance."""
    return _global_cache


def clear_cache() -> None:
    """Clear the global cache."""
    _global_cache.clear()
