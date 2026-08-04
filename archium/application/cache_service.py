"""Application-level caching service for frequently accessed data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.infrastructure.cache import get_cache


class CacheService:
    """Service for managing application-level caching."""
    
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
    
    def get_design_system(self, project_id: UUID) -> dict[str, Any] | None:
        """Get cached design system for a project."""
        cache_key = f"design_system:{project_id}"
        return get_cache().get(cache_key)
    
    def set_design_system(self, project_id: UUID, design_system: dict[str, Any]) -> None:
        """Cache design system for a project."""
        cache_key = f"design_system:{project_id}"
        # Design systems change rarely, cache for 1 hour
        get_cache().set(cache_key, design_system, ttl=timedelta(hours=1))
    
    def invalidate_design_system(self, project_id: UUID) -> None:
        """Invalidate cached design system for a project."""
        cache_key = f"design_system:{project_id}"
        get_cache().invalidate(cache_key)
    
    def get_layout_family(self, layout_id: str) -> dict[str, Any] | None:
        """Get cached layout family definition."""
        cache_key = f"layout_family:{layout_id}"
        return get_cache().get(cache_key)
    
    def set_layout_family(self, layout_id: str, layout_def: dict[str, Any]) -> None:
        """Cache layout family definition."""
        cache_key = f"layout_family:{layout_id}"
        # Layout definitions are stable, cache for 2 hours
        get_cache().set(cache_key, layout_def, ttl=timedelta(hours=2))
    
    def get_project_config(self, project_id: UUID) -> dict[str, Any] | None:
        """Get cached project configuration."""
        cache_key = f"project_config:{project_id}"
        return get_cache().get(cache_key)
    
    def set_project_config(self, project_id: UUID, config: dict[str, Any]) -> None:
        """Cache project configuration."""
        cache_key = f"project_config:{project_id}"
        # Project config changes moderately, cache for 30 minutes
        get_cache().set(cache_key, config, ttl=timedelta(minutes=30))
    
    def invalidate_project_config(self, project_id: UUID) -> None:
        """Invalidate cached project configuration."""
        cache_key = f"project_config:{project_id}"
        get_cache().invalidate(cache_key)
    
    def get_template_metadata(self, template_id: str) -> dict[str, Any] | None:
        """Get cached template metadata."""
        cache_key = f"template_metadata:{template_id}"
        return get_cache().get(cache_key)
    
    def set_template_metadata(self, template_id: str, metadata: dict[str, Any]) -> None:
        """Cache template metadata."""
        cache_key = f"template_metadata:{template_id}"
        # Template metadata is stable, cache for 2 hours
        get_cache().set(cache_key, metadata, ttl=timedelta(hours=2))
    
    def get_style_preset(self, preset_id: str) -> dict[str, Any] | None:
        """Get cached style preset."""
        cache_key = f"style_preset:{preset_id}"
        return get_cache().get(cache_key)
    
    def set_style_preset(self, preset_id: str, preset: dict[str, Any]) -> None:
        """Cache style preset."""
        cache_key = f"style_preset:{preset_id}"
        # Style presets are stable, cache for 2 hours
        get_cache().set(cache_key, preset, ttl=timedelta(hours=2))
    
    def get_user_preferences(self, user_id: str) -> dict[str, Any] | None:
        """Get cached user preferences."""
        cache_key = f"user_preferences:{user_id}"
        return get_cache().get(cache_key)
    
    def set_user_preferences(self, user_id: str, preferences: dict[str, Any]) -> None:
        """Cache user preferences."""
        cache_key = f"user_preferences:{user_id}"
        # User preferences change occasionally, cache for 15 minutes
        get_cache().set(cache_key, preferences, ttl=timedelta(minutes=15))
    
    def invalidate_user_preferences(self, user_id: str) -> None:
        """Invalidate cached user preferences."""
        cache_key = f"user_preferences:{user_id}"
        get_cache().invalidate(cache_key)
    
    def invalidate_project(self, project_id: UUID) -> None:
        """Invalidate all cache entries for a specific project."""
        self.invalidate_design_system(project_id)
        self.invalidate_project_config(project_id)
        # Additional project-specific invalidations can be added here
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        return get_cache().cleanup_expired()
    
    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        cache = get_cache()
        return {
            "total_entries": len(cache._cache),
            "expired_entries": cache.cleanup_expired(),
        }


# Global cache service instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
