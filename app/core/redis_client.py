"""Redis client for Upstash-based rate limiting using HTTP driver."""

import logging
import os
from typing import Optional

from upstash_redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Global Redis client instance (lazy initialization)
_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """
    Get or create the async Redis client for Upstash (HTTP-based).

    Returns:
        Redis client instance, or None if Upstash credentials are not configured.

    Note:
        The client is created lazily on first call and reused thereafter.
        Uses Upstash REST API which is ideal for serverless environments.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not redis_url or not redis_token:
        logger.warning(
            "UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN not configured - "
            "rate limiting disabled"
        )
        return None

    try:
        _redis_client = Redis(url=redis_url, token=redis_token)
        logger.info("Upstash Redis HTTP client initialized successfully")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to create Redis client: {e}")
        return None


async def check_rate_limit(device_id: str, ttl_seconds: int = 60) -> bool:
    """
    Check if a device is rate-limited using Upstash Redis.

    Args:
        device_id: Anonymous device identifier
        ttl_seconds: Time-to-live for the rate limit key (default: 60s)

    Returns:
        True if the request should be BLOCKED (rate limited)
        False if the request should be ALLOWED

    Note:
        Fails open - if Redis is unavailable, requests are allowed.
    """
    client = get_redis_client()

    if client is None:
        # No Redis configured - allow request
        return False

    key = f"rate_limit:{device_id}"

    try:
        # Check if key exists (device is rate-limited)
        existing = await client.get(key)
        if existing is not None:
            return True  # BLOCKED

        # Not rate-limited - set the key with expiration BEFORE processing
        # This prevents spam attacks during slow calculations
        # Upstash uses: set(key, value, ex=seconds) syntax
        await client.set(key, "1", ex=ttl_seconds)
        return False  # ALLOWED

    except Exception as e:
        # Fail open - log error but allow request
        logger.error(f"Redis error during rate limit check: {e}")
        return False  # ALLOWED
