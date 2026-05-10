"""
Tests for EncryptedValCache — Encrypted Mode

Uses fakeredis + real mores-encryption to verify that:
1. Values are actually encrypted in Redis (not plaintext).
2. Round-trip set → get returns the original data.
3. Hashed-key operations work correctly.
4. JSON encryption/decryption works end-to-end.
"""

import os
import pytest
import pytest_asyncio
import json
import fakeredis.aioredis

from valcache.encrypted_cache import EncryptedValCache


class FakeEncryptedValCache(EncryptedValCache):
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
    """Provide a fresh FakeEncryptedValCache instance for each test."""
    # Generate a deterministic key for tests
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode()

    c = FakeEncryptedValCache(default_ttl=60, encryption_key=test_key)
    yield c
    await c.close()


# ------------------------------------------------------------------ #
#  Encrypted set / get round-trip                                      #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_encrypted_set_and_get(cache):
    """Test that encrypted set/get returns the original value."""
    await cache.set("secret", "My Secret Data")
    result = await cache.get("secret")
    assert result == "My Secret Data"


@pytest.mark.asyncio
async def test_value_is_actually_encrypted_in_redis(cache):
    """Verify the raw Redis value is NOT the plaintext."""
    await cache.set("secret", "plaintext_value")

    # Access the raw Redis value (bypass decryption)
    client = await cache._get_client()
    raw_value = await client.get("secret")

    # The raw value should NOT be the plaintext
    assert raw_value != "plaintext_value"
    # It should be a Fernet token (starts with gAAAAA)
    assert raw_value.startswith("gAAAAA")


@pytest.mark.asyncio
async def test_encrypted_get_missing_key(cache):
    """Test that getting a non-existent key returns None."""
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_encrypted_delete(cache):
    """Test that delete works in encrypted mode."""
    await cache.set("key", "value")
    await cache.delete("key")
    result = await cache.get("key")
    assert result is None


# ------------------------------------------------------------------ #
#  Encrypted JSON helpers                                              #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_encrypted_set_json_and_get_json(cache):
    """Test encrypted JSON round-trip."""
    data = {"name": "Alice", "ssn": "123-45-6789", "active": True}
    await cache.set_json("profile:1", data)
    result = await cache.get_json("profile:1")
    assert result == data


@pytest.mark.asyncio
async def test_encrypted_json_is_not_plaintext_in_redis(cache):
    """Verify the raw Redis value for JSON is encrypted."""
    data = {"card": "4111-1111-1111-1111"}
    await cache.set_json("payment", data)

    client = await cache._get_client()
    raw_value = await client.get("payment")

    # Should not contain plaintext card number
    assert "4111" not in raw_value


@pytest.mark.asyncio
async def test_encrypted_get_json_missing_key(cache):
    """Test that get_json returns None for missing keys."""
    result = await cache.get_json("missing")
    assert result is None


# ------------------------------------------------------------------ #
#  Hashed-key operations                                               #
# ------------------------------------------------------------------ #

SALT = "test_salt_for_hashing"


@pytest.mark.asyncio
async def test_set_hashed_and_get_hashed(cache):
    """Test hashed-key set/get round-trip."""
    await cache.set_hashed("user@example.com", "sensitive data", salt=SALT)
    result = await cache.get_hashed("user@example.com", salt=SALT)
    assert result == "sensitive data"


@pytest.mark.asyncio
async def test_hashed_key_is_not_plaintext_in_redis(cache):
    """Verify the Redis key itself is hashed, not plaintext."""
    await cache.set_hashed("patient@hospital.com", "diagnosis", salt=SALT)

    client = await cache._get_client()
    all_keys = await client.keys("*")

    # The plaintext key should NOT appear in Redis
    assert "patient@hospital.com" not in all_keys
    # But there should be exactly one key (the hashed version)
    assert len(all_keys) == 1


@pytest.mark.asyncio
async def test_hashed_key_deterministic(cache):
    """Test that the same key+salt always produces the same hash."""
    await cache.set_hashed("test@test.com", "data1", salt=SALT)
    result = await cache.get_hashed("test@test.com", salt=SALT)
    assert result == "data1"

    # Overwrite with same key+salt — should hit same Redis key
    await cache.set_hashed("test@test.com", "data2", salt=SALT)
    result = await cache.get_hashed("test@test.com", salt=SALT)
    assert result == "data2"


@pytest.mark.asyncio
async def test_delete_hashed(cache):
    """Test delete with hashed keys."""
    await cache.set_hashed("key", "value", salt=SALT)
    await cache.delete_hashed("key", salt=SALT)
    result = await cache.get_hashed("key", salt=SALT)
    assert result is None


@pytest.mark.asyncio
async def test_exists_hashed(cache):
    """Test exists with hashed keys."""
    await cache.set_hashed("key", "value", salt=SALT)
    assert await cache.exists_hashed("key", salt=SALT) is True
    assert await cache.exists_hashed("missing", salt=SALT) is False


@pytest.mark.asyncio
async def test_set_json_hashed_and_get_json_hashed(cache):
    """Test hashed-key JSON encryption round-trip."""
    data = {"diagnosis": "healthy", "blood_type": "O+"}
    await cache.set_json_hashed("patient:001", data, salt=SALT)
    result = await cache.get_json_hashed("patient:001", salt=SALT)
    assert result == data


@pytest.mark.asyncio
async def test_different_salts_produce_different_keys(cache):
    """Test that different salts produce different hashed keys."""
    await cache.set_hashed("same_key", "salt1_data", salt="salt_one")
    await cache.set_hashed("same_key", "salt2_data", salt="salt_two")

    result1 = await cache.get_hashed("same_key", salt="salt_one")
    result2 = await cache.get_hashed("same_key", salt="salt_two")

    assert result1 == "salt1_data"
    assert result2 == "salt2_data"
    # Both should exist (different hashed keys)
    assert result1 != result2
