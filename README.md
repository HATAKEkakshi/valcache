# 🚀 ValCache

[![PyPI](https://img.shields.io/pypi/v/valcache?color=blue)](https://pypi.org/project/valcache/)
[![Python](https://img.shields.io/pypi/pyversions/valcache)](https://pypi.org/project/valcache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/HATAKEkakshi/valcache/actions/workflows/publish.yml/badge.svg)](https://github.com/HATAKEkakshi/valcache/actions)

**Async Redis Cache with Optional AES-128 Encryption**

ValCache is a lightweight, async-first Redis caching library for Python with two modes:

- 🔓 **Normal Mode** (`ValCache`) — Fast plaintext caching with JSON support
- 🔐 **Encrypted Mode** (`EncryptedValCache`) — Transparent AES-128 encryption via [mores-encryption](https://pypi.org/project/mores-encryption/)

Perfect for securing PII, medical data, API keys, session tokens, or any sensitive information in your Redis cache.

---

## 📦 Installation

```bash
pip install valcache
```

---

## ⚙️ Setup (Encrypted Mode)

Generate a secure encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Save it in your `.env` file:

```
ENCRYPTION_KEY=your_generated_key_here
```

Or pass it directly to the constructor (see usage below).

---

## 🚀 Usage

### 1. Normal Cache

```python
from valcache import ValCache

cache = ValCache(host="localhost", port=6379, default_ttl=600)
await cache.connect()

# String operations
await cache.set("user:1", "John Doe")
name = await cache.get("user:1")  # "John Doe"

# JSON operations
await cache.set_json("profile:1", {"name": "John", "age": 30})
profile = await cache.get_json("profile:1")  # {"name": "John", "age": 30}

# Check existence
exists = await cache.exists("user:1")  # True

# Delete
await cache.delete("user:1")

# Health check
healthy = await cache.health_check()  # True

await cache.close()
```

### 2. Encrypted Cache

```python
from valcache import EncryptedValCache

cache = EncryptedValCache(
    host="localhost",
    port=6379,
    encryption_key="your-fernet-key-here",  # or set ENCRYPTION_KEY env var
)
await cache.connect()

# Values are automatically encrypted in Redis
await cache.set("secret", "My Secret Data")
result = await cache.get("secret")  # "My Secret Data" (decrypted)

# JSON encryption — entire dict encrypted as one blob
await cache.set_json("patient:1", {"ssn": "123-45-6789", "diagnosis": "healthy"})
data = await cache.get_json("patient:1")  # decrypted dict

await cache.close()
```

### 3. Hashed Keys (Full Anonymization)

When even the Redis **key** should not reveal sensitive information:

```python
from valcache import EncryptedValCache

cache = EncryptedValCache(encryption_key="your-fernet-key")
await cache.connect()

# Key is hashed, value is encrypted
await cache.set_hashed("patient@hospital.com", "diagnosis data", salt="my_salt")
# Redis key: "a3F9x...Kz8=" (hashed)  |  Redis value: "gAAAAABk..." (encrypted)

# Retrieve using the same key + salt
data = await cache.get_hashed("patient@hospital.com", salt="my_salt")
# "diagnosis data" (decrypted)

# JSON with hashed keys
await cache.set_json_hashed("user@example.com", {"role": "admin"}, salt="my_salt")
profile = await cache.get_json_hashed("user@example.com", salt="my_salt")

# Delete & exists with hashed keys
await cache.delete_hashed("patient@hospital.com", salt="my_salt")
exists = await cache.exists_hashed("patient@hospital.com", salt="my_salt")  # False

await cache.close()
```

---

## 📚 API Reference

### `ValCache` (Normal Mode)

| Method | Description |
|--------|-------------|
| `connect()` | Initialize the Redis connection pool |
| `close()` | Gracefully close the connection pool |
| `set(key, value, ttl=None)` | Store a value with optional TTL |
| `get(key)` | Retrieve a value by key |
| `delete(key)` | Delete a key |
| `exists(key)` | Check if a key exists |
| `set_json(key, data, ttl=None)` | Store a dict as JSON |
| `get_json(key)` | Retrieve and parse a JSON value |
| `health_check()` | Ping the Redis server |
| `get_ttl(key)` | Get remaining TTL for a key |
| `keys(pattern="*")` | List keys matching a pattern |
| `flush_db()` | Delete all keys in the database |

### `EncryptedValCache` (Encrypted Mode)

Inherits all methods from `ValCache`. The following are automatically encrypted:

| Method | Key | Value |
|--------|-----|-------|
| `set(key, value)` | Plaintext | 🔐 Encrypted |
| `get(key)` | Plaintext | 🔓 Decrypted |
| `set_json(key, data)` | Plaintext | 🔐 Encrypted |
| `get_json(key)` | Plaintext | 🔓 Decrypted |

**Hashed-key methods** (key is also anonymized):

| Method | Key | Value |
|--------|-----|-------|
| `set_hashed(key, value, salt)` | 🔒 Hashed | 🔐 Encrypted |
| `get_hashed(key, salt)` | 🔒 Hashed | 🔓 Decrypted |
| `delete_hashed(key, salt)` | 🔒 Hashed | — |
| `exists_hashed(key, salt)` | 🔒 Hashed | — |
| `set_json_hashed(key, data, salt)` | 🔒 Hashed | 🔐 Encrypted |
| `get_json_hashed(key, salt)` | 🔒 Hashed | 🔓 Decrypted |

---

## 🔒 Security Details

| Component | Implementation |
|-----------|---------------|
| **Encryption** | AES-128 CBC via `cryptography.fernet.Fernet` (PKCS7 padding, HMAC-SHA256 integrity) |
| **Key Hashing** | PBKDF2HMAC-SHA256 with 200,000 iterations, 32-byte output |
| **Encoding** | URL-safe Base64 for all encrypted outputs |
| **Key Management** | Via `ENCRYPTION_KEY` env var or constructor parameter |

---

## 🧪 Running Tests

```bash
pip install -e ".[encrypted,dev]"
pytest tests/ -v
```

---

## 🔧 Configuration

ValCache resolves configuration in this priority order:

1. **Constructor params** — `ValCache(host="myhost")` wins
2. **`.env` file / environment variables** — auto-loaded via `python-dotenv`
3. **Defaults** — `localhost`, `6379`, `0`

### `.env` File (Recommended)

Create a `.env` file in your project root:

```env
# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
REDIS_MAX_CONNECTIONS=20

# Encryption (EncryptedValCache only)
ENCRYPTION_KEY=your_fernet_key_here
```

ValCache auto-loads this file — no extra setup needed.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis server hostname | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |
| `REDIS_DB` | Redis database number | `0` |
| `REDIS_PASSWORD` | Redis auth password | `None` |
| `REDIS_MAX_CONNECTIONS` | Connection pool size | `20` |
| `ENCRYPTION_KEY` | Fernet encryption key | Auto-generated |

### Constructor Parameters

All env vars can be overridden via constructor:

| Parameter | Type | Overrides Env Var |
|-----------|------|-------------------|
| `host` | `str` | `REDIS_HOST` |
| `port` | `int` | `REDIS_PORT` |
| `db` | `int` | `REDIS_DB` |
| `password` | `str` | `REDIS_PASSWORD` |
| `max_connections` | `int` | `REDIS_MAX_CONNECTIONS` |
| `default_ttl` | `int` | — (no env var, default `3600`) |
| `encryption_key` | `str` | `ENCRYPTION_KEY` *(EncryptedValCache only)* |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🔗 Related

- [mores-encryption](https://github.com/HATAKEkakshi/mores-encryption) — The encryption library powering ValCache's encrypted mode
