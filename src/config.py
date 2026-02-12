"""Configuration management for the Bluesky bot."""

import os
from decouple import config


class Config:
    """Bot configuration loaded from environment variables."""

    # Required settings
    BLUESKY_HANDLE: str = config("BLUESKY_HANDLE")
    BLUESKY_APP_PASSWORD: str = config("BLUESKY_APP_PASSWORD")

    # Optional settings with defaults
    POLL_INTERVAL: int = config("POLL_INTERVAL", default=30, cast=int)
    RECENT_DAYS: int = config("RECENT_DAYS", default=30, cast=int)
    MAX_POSTS: int = config("MAX_POSTS", default=1000, cast=int)
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")

    # Health check server
    HEALTH_CHECK_PORT: int = config("HEALTH_CHECK_PORT", default=8080, cast=int)

    # Rate limiting
    MIN_ENGAGEMENT_FOR_RATIO: int = config("MIN_ENGAGEMENT_FOR_RATIO", default=5, cast=int)

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration is present."""
        if not cls.BLUESKY_HANDLE:
            raise ValueError("BLUESKY_HANDLE is required")
        if not cls.BLUESKY_APP_PASSWORD:
            raise ValueError("BLUESKY_APP_PASSWORD is required")
        if cls.POLL_INTERVAL < 10:
            raise ValueError("POLL_INTERVAL must be at least 10 seconds")

        print(f"✓ Configuration loaded successfully")
        print(f"  Bot handle: {cls.BLUESKY_HANDLE}")
        print(f"  Poll interval: {cls.POLL_INTERVAL}s")
        print(f"  Recent days: {cls.RECENT_DAYS}")
