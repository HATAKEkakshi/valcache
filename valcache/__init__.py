from valcache.cache import ValCache
from valcache.encrypted_cache import EncryptedValCache

# ValCache — Async Redis Cache with Optional Encryption.
# A lightweight, async-first Redis caching library with two modes:
#   - ValCache: Normal plaintext caching with JSON support.
#   - EncryptedValCache: Transparent AES-128 encryption via mores-encryption.

__version__ = "0.1.0"
__all__ = ["ValCache", "EncryptedValCache"]
