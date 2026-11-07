"""The cryptography of the stores (the user, 2026-11-03: "each user has a key pair db which is
encrypted by the user password"; "for now lets just use an encrypted hash of the password as the
decryption key for the keypair db"; "per user"), and the passkeys mailed to create an account.

The unlock key is the salted hash of the password (scrypt, a salt per user, the parameters kept
with the user so they can be raised later); it is the decryption key of the user's vault key (a
random key, wrapped under the unlock key with AES-256-GCM), and the vault key seals every pair's
value, the pair's name bound in as associated data so a value cannot be moved under another name.
The password itself is never kept: its verifier is a hash of the unlock key, compared in constant
time. Changing the password re-wraps the vault key alone; the pairs stay as they are.

A passkey (`new_code`: eight letters and digits that are never mistaken for one another, in two
groups) goes out by mail and is kept only as a salted hash, like a password."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KDF = {"name": "scrypt", "n": 2 ** 15, "r": 8, "p": 1, "length": 32}  # 32 MB, ~0.1 s: a sign-in, not a loop
SALT_BYTES = 16
KEY_BYTES = 32
NONCE_BYTES = 12
VERIFIER_TAG = b"liminal-login verifier:"
CODE_DIGITS = 6  # the code mailed at sign-up (the user: "the 4-6 digit code"); five tries, fifteen minutes


class Locked(Exception):
    """The key given does not open it (a wrong password, another user's store, a tampered row)."""


def new_salt() -> bytes:
    return os.urandom(SALT_BYTES)


def new_key() -> bytes:
    return os.urandom(KEY_BYTES)


def derive(password: str, salt: bytes, kdf: dict | None = None) -> bytes:
    """The unlock key: scrypt of the password with the user's salt and parameters."""
    kdf = kdf or KDF
    if kdf.get("name", "scrypt") != "scrypt":
        raise ValueError(f"unknown key derivation: {kdf.get('name')}")
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(kdf["n"]), r=int(kdf["r"]), p=int(kdf["p"]),
                          dklen=int(kdf["length"]), maxmem=256 * 1024 * 1024)


def verifier(unlock: bytes) -> bytes:
    """What is kept to check a password: a hash of the unlock key, never the key or the password."""
    return hashlib.sha256(VERIFIER_TAG + unlock).digest()


def same(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def fingerprint(key: bytes) -> str:
    """A key's name for the page (12 hex characters of its hash): says which key, gives nothing of it."""
    return hashlib.sha256(key).hexdigest()[:12]


def seal(key: bytes, plain: bytes, aad: bytes) -> tuple[bytes, bytes]:
    """`plain` sealed under `key` with a fresh nonce, `aad` bound in: (nonce, sealed)."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce, AESGCM(key).encrypt(nonce, plain, aad)


def unseal(key: bytes, nonce: bytes, sealed: bytes, aad: bytes) -> bytes:
    """The plain bytes, or Locked when the key, the nonce, the aad or the bytes are not the ones."""
    try:
        return AESGCM(key).decrypt(nonce, sealed, aad)
    except InvalidTag:
        raise Locked("the key does not open it") from None


# -- the codes mailed at sign-up -------------------------------------------------------------------

def new_code() -> str:
    """The code to mail: six digits (a million; five tries, fifteen minutes)."""
    return "".join(secrets.choice("0123456789") for _ in range(CODE_DIGITS))


def normal_code(code) -> str:
    """A typed code as compared: its digits alone (spaces and dashes dropped)."""
    return "".join(ch for ch in str(code or "") if ch.isdigit())[:CODE_DIGITS]


def code_hash(code: str, salt: bytes) -> bytes:
    """A code as kept: a salted hash (never the code)."""
    return hashlib.sha256(salt + b"liminal-login code:" + normal_code(code).encode("ascii")).digest()


def new_token() -> str:
    """What proves a code was typed right, for the step that makes the account (never kept in the clear)."""
    return secrets.token_urlsafe(24)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(b"liminal-login signup token:" + str(token or "").encode("utf-8")).digest()
