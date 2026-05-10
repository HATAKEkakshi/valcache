import json
from typing import Optional, Any, List
from valcache.pool import RedisPoolManager

# ValCache — Async Redis Cache (Normal Mode).
# Provides a clean async Redis caching interface with JSON support,
# TTL management, and health checking. Data is stored as-is (plaintext).


class ValCache:
    """
    Async Redis cache — plaintext (normal) mode.

    Stores data in Redis without any encryption or transformation.
    Use ``EncryptedValCache`` for transparent encryption.

    Configuration is resolved in priority order:
        1. Constructor parameters
        2. Environment variables / .env file
        3. Built-in defaults (localhost:6379)

    Args:
        host: Redis hostname. Overrides ``REDIS_HOST`` env var.
        port: Redis port. Overrides ``REDIS_PORT`` env var.
        db: Database number. Overrides ``REDIS_DB`` env var.
        max_connections: Pool size. Overrides ``REDIS_MAX_CONNECTIONS``.
        default_ttl: Default TTL in seconds (default: 3600).
        password: Auth password. Overrides ``REDIS_PASSWORD`` env var.
        **kwargs: Extra arguments forwarded to ``RedisPoolManager``.

    Example::

        cache = ValCache()
        await cache.connect()
        await cache.set("key", "value")
        result = await cache.get("key")
        await cache.close()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        max_connections: Optional[int] = None,
        default_ttl: int = 3600,
        password: Optional[str] = None,
        **kwargs,
    ):
        self._default_ttl = default_ttl
        self._pool_manager = RedisPoolManager(
            host=host,
            port=port,
            db=db,
            max_connections=max_connections,
            password=password,
            **kwargs,
        )
        self._connected = False

    async def connect(self) -> None:
        """Initialize the Redis connection pool. Safe to call multiple times."""
        if not self._connected:
            await self._pool_manager.get_pool()
            self._connected = True

    async def close(self) -> None:
        """Close the connection pool and release all connections."""
        await self._pool_manager.close()
        self._connected = False

    async def _get_client(self):
        """Return a Redis client, auto-connecting if needed."""
        if not self._connected:
            await self.connect()
        return await self._pool_manager.get_client()

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in cache with optional TTL.

        Args:
            key: Cache key.
            value: Value to store (converted to string).
            ttl: Time-to-live in seconds. Uses default_ttl if not set.
        """
        client = await self._get_client()
        ttl = ttl if ttl is not None else self._default_ttl
        await client.setex(key, ttl, str(value))

    async def get(self, key: str) -> Optional[str]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key to look up.

        Returns:
            Cached value as string, or None if key doesn't exist.
        """
        client = await self._get_client()
        return await client.get(key)

    async def delete(self, key: str) -> None:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete.
        """
        client = await self._get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key to check.

        Returns:
            True if the key exists.
        """
        client = await self._get_client()
        return bool(await client.exists(key))

    async def set_json(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """
        Serialize a dict to JSON and store in cache.

        Args:
            key: Cache key.
            data: Dictionary to serialize and store.
            ttl: Time-to-live in seconds.
        """
        json_str = json.dumps(data, default=str)
        await self.set(key, json_str, ttl=ttl)

    async def get_json(self, key: str) -> Optional[dict]:
        """
        Retrieve and deserialize a JSON value from cache.

        Args:
            key: Cache key to look up.

        Returns:
            Deserialized dict, or None if key doesn't exist.
        """
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    async def health_check(self) -> bool:
        """
        Check if the Redis server is reachable.

        Returns:
            True if server responds to PING.
        """
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False

    async def get_ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key.

        Returns:
            TTL in seconds. -2 if key doesn't exist, -1 if no expiry.
        """
        client = await self._get_client()
        return await client.ttl(key)

    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Return all keys matching a glob pattern.

        Warning:
            Avoid in production on large datasets. Prefer SCAN.

        Args:
            pattern: Glob-style pattern (default: "*").

        Returns:
            List of matching keys.
        """
        client = await self._get_client()
        return await client.keys(pattern)

    async def flush_db(self) -> None:
        """
        Delete all keys in the current database.

        Warning:
            Destructive operation. Use with caution.
        """
        client = await self._get_client()
        await client.flushdb()
