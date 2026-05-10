"""
Tests for ValCache — Normal (Plaintext) Mode

Uses fakeredis to simulate a Redis server in-memory, so no actual
Redis instance is needed to run these tests.
"""

import pytest
import pytest_asyncio
import json
import fakeredis.aioredis

from valcache.cache import ValCache


class FakeValCache(ValCache):
    """
    Test-only subclass that injects a fakeredis connection pool
    instead of connecting to a real Redis server.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._fake_redis = None

    async def _get_client(self):
        if self._fake_redis is None:
            self._fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        return self._fake_redis

    async def close(self):
        if self._fake_redis:
            await self._fake_redis.flushall()
            await self._fake_redis.aclose()
            self._fake_redis = None


@pytest_asyncio.fixture
async def cache():
    """Provide a fresh FakeValCache instance for each test."""
    c = FakeValCache(default_ttl=60)
    yield c
    await c.close()


# ------------------------------------------------------------------ #
#  Basic set / get / delete                                            #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_set_and_get(cache):
    """Test basic set and get operations."""
    await cache.set("name", "Alice")
    result = await cache.get("name")
    assert result == "Alice"


@pytest.mark.asyncio
async def test_get_missing_key(cache):
    """Test that getting a non-existent key returns None."""
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete(cache):
    """Test that delete removes the key."""
    await cache.set("key", "value")
    await cache.delete("key")
    result = await cache.get("key")
    assert result is None


@pytest.mark.asyncio
async def test_exists(cache):
    """Test exists returns True for existing keys, False otherwise."""
    await cache.set("key", "value")
    assert await cache.exists("key") is True
    assert await cache.exists("missing") is False


# ------------------------------------------------------------------ #
#  JSON helpers                                                        #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_set_json_and_get_json(cache):
    """Test JSON serialization round-trip."""
    data = {"name": "Bob", "age": 30, "active": True}
    await cache.set_json("user:1", data)
    result = await cache.get_json("user:1")
    assert result == data


@pytest.mark.asyncio
async def test_get_json_missing_key(cache):
    """Test that get_json returns None for missing keys."""
    result = await cache.get_json("missing")
    assert result is None


@pytest.mark.asyncio
async def test_set_json_nested(cache):
    """Test JSON with nested structures."""
    data = {
        "user": {"name": "Carol"},
        "scores": [95, 87, 92],
        "metadata": {"enrolled": True},
    }
    await cache.set_json("complex", data)
    result = await cache.get_json("complex")
    assert result == data


# ------------------------------------------------------------------ #
#  Utility operations                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_health_check(cache):
    """Test that health_check returns True for a live connection."""
    result = await cache.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_keys_pattern(cache):
    """Test key listing with glob patterns."""
    await cache.set("user:1", "Alice")
    await cache.set("user:2", "Bob")
    await cache.set("session:1", "token")

    user_keys = await cache.keys("user:*")
    assert len(user_keys) == 2
    assert "session:1" not in user_keys


@pytest.mark.asyncio
async def test_flush_db(cache):
    """Test that flush_db removes all keys."""
    await cache.set("a", "1")
    await cache.set("b", "2")
    await cache.flush_db()
    assert await cache.get("a") is None
    assert await cache.get("b") is None


@pytest.mark.asyncio
async def test_overwrite_value(cache):
    """Test that setting the same key overwrites the previous value."""
    await cache.set("key", "old")
    await cache.set("key", "new")
    result = await cache.get("key")
    assert result == "new"


@pytest.mark.asyncio
async def test_numeric_value_stored_as_string(cache):
    """Test that numeric values are stored and retrieved as strings."""
    await cache.set("count", 42)
    result = await cache.get("count")
    assert result == "42"
