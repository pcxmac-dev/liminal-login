"""A user's store of key-vector pairs (the user, 2026-11-03: keys and accounts "stored according to
key-vector pair which interrogates the current logged in user, for a particular account, like
claude-account-name or claude-account-api-key (key name) it's return vector would be the api key or
account name or account password, that only the liminal-login instance would be able to furnish"):
one SQLite file per user, every value sealed under the user's vault key (crypto.py) with the pair's
name bound in, so the file gives nothing without the key, and a value cannot be moved under another
name. The names are listed freely; the values only through `get`, by whoever holds the key."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from pathlib import Path

from . import crypto
from .users import CONTROL, now_iso

PAIR_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")  # massive-account-api-key, claude-account-name
KINDS = ("key", "account", "password", "detail")
VALUE_MAX = 4096

SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    nonce BLOB NOT NULL,
    sealed BLOB NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def clean_pair_name(name) -> str:
    name = str(name or "").strip().lower()
    if not PAIR_NAME.match(name):
        raise ValueError("a pair's name is lowercase letters, digits, dots, dashes and underscores "
                         "(massive-account-api-key), 1 to 64 characters")
    return name


def clean_value(value) -> str:
    value = str(value if value is not None else "").strip()
    if not value or len(value) > VALUE_MAX or CONTROL.search(value):
        raise ValueError(f"a value is 1 to {VALUE_MAX} characters, no control characters")
    return value


def clean_kind(kind) -> str:
    kind = str(kind or "key").strip().lower()
    if kind not in KINDS:
        raise ValueError(f"a pair's kind is one of {', '.join(KINDS)}")
    return kind


def store_file(users_dir: Path, name: str) -> Path:
    """A user's store file: their name made safe for a file name, with a hash so two names that
    differ only in what was dropped get two files."""
    slug = re.sub(r"[^a-z0-9._-]+", "_", name.lower()).strip("._") or "user"
    return Path(users_dir) / f"{slug[:32]}-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]}.db"


class KeyPairStore:
    """One user's pairs, opened with their vault key. One connection, used from the server's threads
    under a lock."""

    def __init__(self, path: Path, vault_key: bytes):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = vault_key
        self._lock = threading.Lock()
        self._con = sqlite3.connect(str(self.path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._con.close()
        self._key = b""

    @property
    def fingerprint(self) -> str:
        return crypto.fingerprint(self._key)

    def count(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]

    def names(self) -> list[dict]:
        """Every pair by name: its kind, label and dates, never its value."""
        with self._lock:
            rows = self._con.execute("SELECT name, kind, label, created_at, updated_at FROM pairs ORDER BY name").fetchall()
        return [{"name": r["name"], "kind": r["kind"], "label": r["label"], "createdAt": r["created_at"],
                 "updatedAt": r["updated_at"]} for r in rows]

    def info(self, name: str) -> dict | None:
        with self._lock:
            r = self._con.execute("SELECT name, kind, label, created_at, updated_at FROM pairs WHERE name = ?",
                                  (clean_pair_name(name),)).fetchone()
        return None if r is None else {"name": r["name"], "kind": r["kind"], "label": r["label"],
                                       "createdAt": r["created_at"], "updatedAt": r["updated_at"]}

    def get(self, name: str) -> str:
        """The pair's value (the vector); KeyError when there is no such pair."""
        name = clean_pair_name(name)
        with self._lock:
            r = self._con.execute("SELECT nonce, sealed FROM pairs WHERE name = ?", (name,)).fetchone()
        if r is None:
            raise KeyError(name)
        return crypto.unseal(self._key, r["nonce"], r["sealed"], name.encode("utf-8")).decode("utf-8")

    def put(self, name: str, value: str, kind: str = "key", label: str = "") -> dict:
        """Keep a pair (a new one, or the value of one there already); the row's dates and kind."""
        name, value, kind = clean_pair_name(name), clean_value(value), clean_kind(kind)
        label = str(label or "").strip()[:80]
        nonce, sealed = crypto.seal(self._key, value.encode("utf-8"), name.encode("utf-8"))
        now = now_iso()
        with self._lock:
            self._con.execute("INSERT INTO pairs (name, kind, label, nonce, sealed, created_at, updated_at) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET kind = excluded.kind, "
                              "label = excluded.label, nonce = excluded.nonce, sealed = excluded.sealed, "
                              "updated_at = excluded.updated_at", (name, kind, label, nonce, sealed, now, now))
            self._con.commit()
        return self.info(name)

    def remove(self, name: str) -> bool:
        with self._lock:
            n = self._con.execute("DELETE FROM pairs WHERE name = ?", (clean_pair_name(name),)).rowcount
            self._con.commit()
        return n > 0
