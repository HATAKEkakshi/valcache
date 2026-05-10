import os
from typing import Optional, Any
from valcache.cache import ValCache
from mores_encryption.encryption import encryption_service

# ValCache — Async Redis Cache (Encrypted Mode).
# Extends ValCache with transparent AES-128 encryption/decryption
# powered by mores-encryption. Supports hashed keys for full anonymization.


class EncryptedValCache(ValCache):
    """
    Async Redis cache — encrypted mode via mores-encryption.

    Inherits all ValCache functionality but transparently encrypts
    values before writing and decrypts on retrieval using AES-128 (Fernet).

    Configuration is resolved in priority order:
        1. Constructor parameters
        2. Environment variables / .env file
        3. Built-in defaults

    Args:
        host: Redis hostname. Overrides ``REDIS_HOST`` env var.
        port: Redis port. Overrides ``REDIS_PORT`` env var.
        db: Database number. Overrides ``REDIS_DB`` env var.
        max_connections: Pool size. Overrides ``REDIS_MAX_CONNECTIONS``.
        default_ttl: Default TTL in seconds (default: 3600).
        encryption_key: Fernet key. Sets ``ENCRYPTION_KEY`` env var if provided.
        password: Auth password. Overrides ``REDIS_PASSWORD`` env var.
        **kwargs: Extra arguments forwarded to ``RedisPoolManager``.

    Example::

        cache = EncryptedValCache(encryption_key="your-fernet-key")
        await cache.connect()
        await cache.set("secret", "classified")
        result = await cache.get("secret")  # "classified"
        await cache.close()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        max_connections: Optional[int] = None,
        default_ttl: int = 3600,
        encryption_key: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            host=host,
            port=port,
            db=db,
            max_connections=max_connections,
            default_ttl=default_ttl,
            password=password,
            **kwargs,
        )

        # Set encryption key in environment if provided directly
        if encryption_key is not None:
            os.environ["ENCRYPTION_KEY"] = encryption_key

        self._enc = encryption_service

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Encrypt and store a value.

        Args:
            key: Cache key (stored as plaintext).
            value: Value to encrypt and store.
            ttl: Time-to-live in seconds.
        """
        encrypted_value = self._enc.encrypt(str(value))
        await super().set(key, encrypted_value, ttl=ttl)

    async def get(self, key: str) -> Optional[str]:
        """
        Retrieve and decrypt a value.

        Args:
            key: Cache key to look up.

        Returns:
            Decrypted value, or None if key doesn't exist.
        """
        encrypted_value = await super().get(key)
        if encrypted_value is None:
            return None
        return self._enc.decrypt(encrypted_value)

    async def set_json(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """
        Encrypt a dict and store it as an encrypted JSON blob.

        Args:
            key: Cache key.
            data: Dictionary to encrypt and store.
            ttl: Time-to-live in seconds.
        """
        encrypted_json = self._enc.encrypt_json(data)
        await super().set(key, encrypted_json, ttl=ttl)

    async def get_json(self, key: str) -> Optional[dict]:
        """
        Retrieve and decrypt a JSON value.

        Args:
            key: Cache key to look up.

        Returns:
            Decrypted dict, or None if key doesn't exist.
        """
        encrypted_value = await super().get(key)
        if encrypted_value is None:
            return None
        return self._enc.decrypt_json(encrypted_value)

    def _hash_key(self, key: str, salt: str) -> str:
        """
        Deterministically hash a key using PBKDF2-SHA256.

        Same (key, salt) pair always produces the same hash,
        enabling lookups without exposing the original key in Redis.

        Args:
            key: Original plaintext key.
            salt: Static salt for deterministic hashing.

        Returns:
            URL-safe Base64 hashed key.
        """
        return self._enc.hash(key, salt)

    async def set_hashed(self, key: str, value: Any, salt: str, ttl: Optional[int] = None) -> None:
        """
        Hash the key and encrypt the value before storing.

        Args:
            key: Plaintext key (will be hashed).
            value: Value to encrypt and store.
            salt: Static salt for key hashing.
            ttl: Time-to-live in seconds.
        """
        hashed_key = self._hash_key(key, salt)
        await self.set(hashed_key, value, ttl=ttl)

    async def get_hashed(self, key: str, salt: str) -> Optional[str]:
        """
        Hash the key, look up in Redis, and decrypt the value.

        Args:
            key: Original plaintext key.
            salt: Same salt used during set_hashed().

        Returns:
            Decrypted value, or None if not found.
        """
        hashed_key = self._hash_key(key, salt)
        return await self.get(hashed_key)

    async def delete_hashed(self, key: str, salt: str) -> None:
        """
        Hash the key and delete the corresponding entry.

        Args:
            key: Original plaintext key.
            salt: Same salt used during set_hashed().
        """
        hashed_key = self._hash_key(key, salt)
        await self.delete(hashed_key)

    async def exists_hashed(self, key: str, salt: str) -> bool:
        """
        Hash the key and check if it exists in Redis.

        Args:
            key: Original plaintext key.
            salt: Same salt used during set_hashed().

        Returns:
            True if the hashed key exists.
        """
        hashed_key = self._hash_key(key, salt)
        return await self.exists(hashed_key)

    async def set_json_hashed(self, key: str, data: dict, salt: str, ttl: Optional[int] = None) -> None:
        """
        Hash the key, encrypt the JSON data, and store both.

        Args:
            key: Plaintext key (will be hashed).
            data: Dictionary to encrypt and store.
            salt: Static salt for key hashing.
            ttl: Time-to-live in seconds.
        """
        hashed_key = self._hash_key(key, salt)
        await self.set_json(hashed_key, data, ttl=ttl)

    async def get_json_hashed(self, key: str, salt: str) -> Optional[dict]:
        """
        Hash the key and decrypt the stored JSON value.

        Args:
            key: Original plaintext key.
            salt: Same salt used during set_json_hashed().

        Returns:
            Decrypted dict, or None if not found.
        """
        hashed_key = self._hash_key(key, salt)
        return await self.get_json(hashed_key)
