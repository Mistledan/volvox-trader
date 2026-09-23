"""Password hashing (stdlib PBKDF2) and opaque bearer-token management."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

_ITERATIONS = 600_000
_SALT_BYTES = 16

TOKEN_TTL_SECONDS = float(os.getenv("TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_hex(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_expiry() -> float:
    """Unix timestamp at which a freshly-issued token expires."""
    return time.time() + TOKEN_TTL_SECONDS