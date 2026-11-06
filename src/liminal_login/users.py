"""The users (the user, 2026-11-04: "username and password are the first things that identify" a
user; "the login app is going to need a database for storing user/passwords/account info"): a
SQLite file of users, each with the salt and parameters of their unlock key, the verifier of their
password and their vault key wrapped under the unlock key (crypto.py). Nothing in the file opens a
vault without the password. The pairs themselves are each user's own store (vault.py)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import crypto

NAME_MAX = 40
PASSWORD_MIN = 8
PASSWORD_MAX = 512
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    name TEXT PRIMARY KEY COLLATE NOCASE,
    salt BLOB NOT NULL,
    kdf TEXT NOT NULL,              -- the unlock key's derivation (json: name, n, r, p, length)
    verifier BLOB NOT NULL,         -- a hash of the unlock key, never the password
    vault_nonce BLOB NOT NULL,
    vault_wrapped BLOB NOT NULL,    -- the vault key, sealed under the unlock key
    created_at TEXT NOT NULL,
    seen_at TEXT                    -- the last sign-in
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_name(name) -> str:
    """A user's name: 1 to 40 characters, no control characters, spaces trimmed."""
    name = str(name or "").strip()
    if not name or len(name) > NAME_MAX or CONTROL.search(name):
        raise ValueError(f"a user's name is 1 to {NAME_MAX} characters")
    return name


def check_password(password) -> str:
    password = str(password or "")
    if len(password) < PASSWORD_MIN:
        raise ValueError(f"a password is at least {PASSWORD_MIN} characters")
    if len(password) > PASSWORD_MAX:
        raise ValueError(f"a password is at most {PASSWORD_MAX} characters")
    return password


@dataclass
class User:
    """A signed-in user: who, since when, and the keys that open their store (in memory only)."""

    name: str
    created_at: str
    seen_at: str | None
    kdf: dict
    salt: bytes = field(repr=False)
    unlock_key: bytes = field(repr=False)
    vault_key: bytes = field(repr=False)

    @property
    def unlock_fingerprint(self) -> str:
        return crypto.fingerprint(self.unlock_key)

    @property
    def vault_fingerprint(self) -> str:
        return crypto.fingerprint(self.vault_key)

    def as_dict(self) -> dict:
        """What the page and the clients see: never a key."""
        return {"name": self.name, "createdAt": self.created_at, "seenAt": self.seen_at}


class UserStore:
    """The users' file. One connection, used from the server's threads under a lock."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(str(self.path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def count(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def names(self) -> list[dict]:
        """Every user, the last signed in first: name, createdAt, seenAt; nothing of their keys."""
        with self._lock:
            rows = self._con.execute("SELECT name, created_at, seen_at FROM users "
                                     "ORDER BY seen_at IS NULL, seen_at DESC, created_at").fetchall()
        return [{"name": r["name"], "createdAt": r["created_at"], "seenAt": r["seen_at"]} for r in rows]

    def exists(self, name: str) -> bool:
        with self._lock:
            return self._con.execute("SELECT 1 FROM users WHERE name = ?", (str(name or "").strip(),)).fetchone() is not None

    def create(self, name, password) -> User:
        """A new user: a salt, the unlock key from the password, a vault key wrapped under it."""
        name, password = clean_name(name), check_password(password)
        salt = crypto.new_salt()
        kdf = dict(crypto.KDF)
        unlock = crypto.derive(password, salt, kdf)
        vault_key = crypto.new_key()
        nonce, wrapped = crypto.seal(unlock, vault_key, name.encode("utf-8"))
        created = now_iso()
        with self._lock:
            if self._con.execute("SELECT 1 FROM users WHERE name = ?", (name,)).fetchone():
                raise ValueError(f"there is a user named {name!r} already")
            self._con.execute("INSERT INTO users (name, salt, kdf, verifier, vault_nonce, vault_wrapped, created_at) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (name, salt, json.dumps(kdf), crypto.verifier(unlock), nonce, wrapped, created))
            self._con.commit()
        return User(name, created, None, kdf, salt, unlock, vault_key)

    def verify(self, name, password) -> User | None:
        """The user when the name and password are theirs (their sign-in noted), else None. A wrong
        name and a wrong password cost the same (the key is derived either way)."""
        name = str(name or "").strip()
        with self._lock:
            row = self._con.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
        salt = row["salt"] if row else crypto.new_salt()
        kdf = json.loads(row["kdf"]) if row else dict(crypto.KDF)
        unlock = crypto.derive(str(password or ""), salt, kdf)
        if row is None or not crypto.same(crypto.verifier(unlock), row["verifier"]):
            return None
        try:
            vault_key = crypto.unseal(unlock, row["vault_nonce"], row["vault_wrapped"], row["name"].encode("utf-8"))
        except crypto.Locked:
            return None
        seen = now_iso()
        with self._lock:
            self._con.execute("UPDATE users SET seen_at = ? WHERE name = ?", (seen, row["name"]))
            self._con.commit()
        return User(row["name"], row["created_at"], seen, kdf, salt, unlock, vault_key)

    def change_password(self, name, old, new) -> User:
        """A new password: a new salt and unlock key, the same vault key wrapped again under it; the
        pairs stay as they are. ValueError when the old one is wrong or the new one too short."""
        user = self.verify(name, old)
        if user is None:
            raise ValueError("the current password is wrong")
        new = check_password(new)
        salt = crypto.new_salt()
        kdf = dict(crypto.KDF)
        unlock = crypto.derive(new, salt, kdf)
        nonce, wrapped = crypto.seal(unlock, user.vault_key, user.name.encode("utf-8"))
        with self._lock:
            self._con.execute("UPDATE users SET salt = ?, kdf = ?, verifier = ?, vault_nonce = ?, vault_wrapped = ? "
                              "WHERE name = ?", (salt, json.dumps(kdf), crypto.verifier(unlock), nonce, wrapped, user.name))
            self._con.commit()
        return User(user.name, user.created_at, user.seen_at, kdf, salt, unlock, user.vault_key)

    def rename(self, name, new_name, password) -> User:
        """A new name (the vault key's wrap binds the name, so it is wrapped again)."""
        user = self.verify(name, password)
        if user is None:
            raise ValueError("the password is wrong")
        new_name = clean_name(new_name)
        nonce, wrapped = crypto.seal(user.unlock_key, user.vault_key, new_name.encode("utf-8"))
        with self._lock:
            if new_name.lower() != user.name.lower() and \
                    self._con.execute("SELECT 1 FROM users WHERE name = ?", (new_name,)).fetchone():
                raise ValueError(f"there is a user named {new_name!r} already")
            self._con.execute("UPDATE users SET name = ?, vault_nonce = ?, vault_wrapped = ? WHERE name = ?",
                              (new_name, nonce, wrapped, user.name))
            self._con.commit()
        return User(new_name, user.created_at, user.seen_at, user.kdf, user.salt, user.unlock_key, user.vault_key)
