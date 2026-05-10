import os
from redis.asyncio import Redis, ConnectionPool
from typing import Optional
from dotenv import load_dotenv

# Redis Connection Pool Manager for ValCache.
# Manages a shared async Redis connection pool with configuration
# resolved from constructor params, environment variables, or defaults.

# Auto-load .env file
load_dotenv()


def _env_str(key: str, default: str) -> str:
    """Read a string from environment, with fallback."""
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    """Read an integer from environment, with fallback."""
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


class RedisPoolManager:
    """
    Async Redis connection pool manager.

    Resolves configuration in priority order:
        1. Constructor parameters (if provided)
        2. Environment variables / .env file
        3. Built-in defaults

    Supported environment variables::

        REDIS_HOST            - Server hostname       (default: localhost)
        REDIS_PORT            - Server port           (default: 6379)
        REDIS_DB              - Database number       (default: 0)
        REDIS_PASSWORD        - Authentication secret (default: None)
        REDIS_MAX_CONNECTIONS - Pool size             (default: 20)

    Args:
        host: Redis hostname. Overrides ``REDIS_HOST``.
        port: Redis port. Overrides ``REDIS_PORT``.
        db: Database number. Overrides ``REDIS_DB``.
        max_connections: Pool size. Overrides ``REDIS_MAX_CONNECTIONS``.
        decode_responses: Auto-decode Redis responses to strings.
        retry_on_timeout: Retry failed operations on timeout.
        password: Auth password. Overrides ``REDIS_PASSWORD``.
        **kwargs: Extra arguments forwarded to ``ConnectionPool``.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        max_connections: Optional[int] = None,
        decode_responses: bool = True,
        retry_on_timeout: bool = True,
        password: Optional[str] = None,
        **kwargs,
    ):
        self._host = host if host is not None else _env_str("REDIS_HOST", "localhost")
        self._port = port if port is not None else _env_int("REDIS_PORT", 6379)
        self._db = db if db is not None else _env_int("REDIS_DB", 0)
        self._max_connections = (
            max_connections if max_connections is not None
            else _env_int("REDIS_MAX_CONNECTIONS", 20)
        )
        self._decode_responses = decode_responses
        self._retry_on_timeout = retry_on_timeout
        self._password = password if password is not None else os.getenv("REDIS_PASSWORD")
        self._extra_kwargs = kwargs
        self._pool: Optional[ConnectionPool] = None

    async def get_pool(self) -> ConnectionPool:
        """Create and return the shared connection pool."""
        if self._pool is None:
            pool_kwargs = dict(
                host=self._host,
                port=self._port,
                db=self._db,
                max_connections=self._max_connections,
                decode_responses=self._decode_responses,
                retry_on_timeout=self._retry_on_timeout,
                **self._extra_kwargs,
            )
            if self._password is not None:
                pool_kwargs["password"] = self._password

            self._pool = ConnectionPool(**pool_kwargs)
        return self._pool

    async def get_client(self) -> Redis:
        """Return an async Redis client backed by the shared pool."""
        pool = await self.get_pool()
        return Redis(connection_pool=pool)

    async def close(self) -> None:
        """Close the pool and release all connections."""
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
