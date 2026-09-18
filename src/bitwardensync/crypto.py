"""Bitwarden's client-side vault crypto: KDF, key stretching, and EncString decryption.

Implements the same scheme the official clients use, so the server never sees
the plaintext master password: https://bitwarden.com/help/bitwarden-security-white-paper/
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


class DecryptionError(RuntimeError):
    """Raised when an EncString fails MAC verification or is malformed."""


@dataclass(frozen=True)
class KdfConfig:
    kdf_type: int  # 0 = PBKDF2-SHA256, 1 = Argon2id
    iterations: int
    memory_mb: int | None = None
    parallelism: int | None = None


def derive_master_key(password: str, email: str, kdf: KdfConfig) -> bytes:
    password_bytes = password.encode("utf-8")
    email_normalized = email.strip().lower().encode("utf-8")

    if kdf.kdf_type == 0:
        return hashlib.pbkdf2_hmac(
            "sha256", password_bytes, email_normalized, kdf.iterations, dklen=32
        )
    if kdf.kdf_type == 1:
        if kdf.memory_mb is None or kdf.parallelism is None:
            raise ValueError("Argon2id KDF requires memory and parallelism")
        salt = hashlib.sha256(email_normalized).digest()
        return hash_secret_raw(
            secret=password_bytes,
            salt=salt,
            time_cost=kdf.iterations,
            memory_cost=kdf.memory_mb * 1024,
            parallelism=kdf.parallelism,
            hash_len=32,
            type=Type.ID,
        )
    raise ValueError(f"Unsupported KDF type: {kdf.kdf_type}")


def hash_master_password(master_key: bytes, password: str) -> str:
    """The value sent to the server to authenticate a password-grant login."""
    hashed = hashlib.pbkdf2_hmac("sha256", master_key, password.encode("utf-8"), 1, dklen=32)
    return base64.b64encode(hashed).decode("ascii")


def stretch_key(master_key: bytes) -> bytes:
    """HKDF-Expand the master key into a 64-byte enc+mac key pair."""
    return _hkdf_expand(master_key, b"enc", 32) + _hkdf_expand(master_key, b"mac", 32)


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def decrypt(enc_string: str, enc_key: bytes, mac_key: bytes) -> bytes:
    """Decrypt a Bitwarden "EncString" of the form `2.<iv>|<ciphertext>|<mac>` (base64 parts)."""
    _enc_type, _, rest = enc_string.partition(".")
    parts = rest.split("|")
    if len(parts) != 3:
        raise DecryptionError(f"Unexpected EncString format: {enc_string[:16]}...")

    iv = base64.b64decode(parts[0])
    ciphertext = base64.b64decode(parts[1])
    mac = base64.b64decode(parts[2])

    calculated_mac = hmac.new(mac_key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(calculated_mac, mac):
        raise DecryptionError("MAC verification failed; wrong key or corrupted data")

    decryptor = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def decrypt_str(enc_string: str | None, enc_key: bytes, mac_key: bytes) -> str | None:
    if enc_string is None:
        return None
    return decrypt(enc_string, enc_key, mac_key).decode("utf-8")
