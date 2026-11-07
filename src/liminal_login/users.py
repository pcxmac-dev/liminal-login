"""The users (the user, 2026-11-04: "username and password are the first things that identify" a
user; "the login app is going to need a database for storing user/passwords/account info"; "i need a
way to create a user and send an email out ... in order to obtain a passkey to create the account"):
a SQLite file of users, each with the salt and parameters of their unlock key, the verifier of their
password, their vault key wrapped under the unlock key (crypto.py), their email and when it was
verified; and the sign-ups waiting for their passkey (the same material, made when the account was
asked for, so the password is typed once; the passkey kept as a salted hash, with its expiry and the
tries made). Nothing in the file opens a vault without the password. The pairs themselves are each
user's own store (vault.py)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import crypto

NAME_MAX = 40
PASSWORD_MIN = 8
PASSWORD_MAX = 512
EMAIL_MAX = 254
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_MINUTES = 15.0  # a passkey's life
CODE_TRIES = 5  # wrong passkeys before the sign-up is dropped
RESEND_SECONDS = 60.0  # no new passkey sooner than this

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    name TEXT PRIMARY KEY COLLATE NOCASE,
    salt BLOB NOT NULL,
    kdf TEXT NOT NULL,              -- the unlock key's derivation (json: name, n, r, p, length)
    verifier BLOB NOT NULL,         -- a hash of the unlock key, never the password
    vault_nonce BLOB NOT NULL,
    vault_wrapped BLOB NOT NULL,    -- the vault key, sealed under the unlock key
    created_at TEXT NOT NULL,
    seen_at TEXT,                   -- the last sign-in
    email TEXT COLLATE NOCASE,      -- the address the account was made with (1.0: none)
    verified_at TEXT                -- when its passkey came back
);
CREATE TABLE IF NOT EXISTS signups (
    email TEXT PRIMARY KEY COLLATE NOCASE,
    name TEXT NOT NULL,
    salt BLOB NOT NULL, kdf TEXT NOT NULL, verifier BLOB NOT NULL, vault_nonce BLOB NOT NULL, vault_wrapped BLOB NOT NULL,
    code_salt BLOB NOT NULL,
    code_hash BLOB NOT NULL,        -- the passkey mailed, as a salted hash
    tries INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
ADDED_COLUMNS = (("email", "TEXT COLLATE NOCASE"), ("verified_at", "TEXT"))  # 0.2.0, on a 0.1.0 file


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _at(minutes: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def clean_name(name) -> str:
    """A user's name: 1 to 40 characters, no control characters, spaces trimmed."""
    name = str(name or "").strip()
    if not name or len(name) > NAME_MAX or CONTROL.search(name):
        raise ValueError(f"a user's name is 1 to {NAME_MAX} characters")
    return name


def clean_email(email) -> str:
    email = str(email or "").strip().lower()
    if not email or len(email) > EMAIL_MAX or not EMAIL.match(email):
        raise ValueError("an email address is needed, like you@example.com")
    return email


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
    email: str | None = None
    verified_at: str | None = None

    @property
    def unlock_fingerprint(self) -> str:
        return crypto.fingerprint(self.unlock_key)

    @property
    def vault_fingerprint(self) -> str:
        return crypto.fingerprint(self.vault_key)

    def as_dict(self) -> dict:
        """What the page and the clients see: never a key."""
        return {"name": self.name, "createdAt": self.created_at, "seenAt": self.seen_at, "email": self.email,
                "verified": self.verified_at is not None}


def _material(name: str, password: str) -> tuple:
    """What a user's row keeps of a password (the salt, the KDF, the verifier, the vault key
    wrapped), and the two keys themselves for the caller that signs the user in at once."""
    salt = crypto.new_salt()
    kdf = dict(crypto.KDF)
    unlock = crypto.derive(password, salt, kdf)
    vault_key = crypto.new_key()
    nonce, wrapped = crypto.seal(unlock, vault_key, name.encode("utf-8"))
    return salt, kdf, crypto.verifier(unlock), nonce, wrapped, unlock, vault_key


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
            have = {r["name"] for r in self._con.execute("PRAGMA table_info(users)")}
            for column, kind in ADDED_COLUMNS:
                if column not in have:
                    self._con.execute(f"ALTER TABLE users ADD COLUMN {column} {kind}")
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # -- the users ---------------------------------------------------------------------------------
    def count(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def names(self) -> list[dict]:
        """Every user, the last signed in first: name, createdAt, seenAt, email, verified; nothing of
        their keys."""
        with self._lock:
            rows = self._con.execute("SELECT name, created_at, seen_at, email, verified_at FROM users "
                                     "ORDER BY seen_at IS NULL, seen_at DESC, created_at").fetchall()
        return [{"name": r["name"], "createdAt": r["created_at"], "seenAt": r["seen_at"], "email": r["email"],
                 "verified": r["verified_at"] is not None} for r in rows]

    def exists(self, name: str) -> bool:
        with self._lock:
            return self._con.execute("SELECT 1 FROM users WHERE name = ?", (str(name or "").strip(),)).fetchone() is not None

    def _row(self, who: str):
        """A user's row by name, or by email when `who` holds an @."""
        who = str(who or "").strip()
        column = "email" if "@" in who else "name"
        with self._lock:
            return self._con.execute(f"SELECT * FROM users WHERE {column} = ?", (who,)).fetchone()

    def create(self, name, password, email=None) -> User:
        """A new user without a passkey (the command line, a signed-in user adding one): a salt, the
        unlock key from the password, a vault key wrapped under it; the email, if given, unverified."""
        name, password = clean_name(name), check_password(password)
        email = clean_email(email) if email else None
        salt, kdf, verifier, nonce, wrapped, unlock, vault_key = _material(name, password)
        created = now_iso()
        with self._lock:
            self._refuse_taken(name, email)
            self._con.execute("INSERT INTO users (name, salt, kdf, verifier, vault_nonce, vault_wrapped, created_at, email) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (name, salt, json.dumps(kdf), verifier, nonce, wrapped, created, email))
            self._con.commit()
        return User(name, created, None, kdf, salt, unlock, vault_key, email)

    def _refuse_taken(self, name: str, email: str | None, pending_ok: str | None = None) -> None:
        """Under the lock: ValueError when the name or the email is a user's already."""
        if self._con.execute("SELECT 1 FROM users WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"there is a user named {name!r} already")
        if email and self._con.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("there is a user with that email address already: sign in instead")

    def verify(self, who, password) -> User | None:
        """The user when the name (or email) and password are theirs (their sign-in noted), else None.
        A wrong name and a wrong password cost the same (the key is derived either way)."""
        row = self._row(who)
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
        return User(row["name"], row["created_at"], seen, kdf, salt, unlock, vault_key, row["email"], row["verified_at"])

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
        return User(user.name, user.created_at, user.seen_at, kdf, salt, unlock, user.vault_key, user.email, user.verified_at)

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
        return User(new_name, user.created_at, user.seen_at, user.kdf, user.salt, user.unlock_key, user.vault_key,
                    user.email, user.verified_at)

    # -- the sign-ups: an account asked for, waiting for its passkey ---------------------------------
    def start_signup(self, name, email, password, minutes: float = CODE_MINUTES) -> str:
        """An account asked for: the row that will be the user's, kept aside until the passkey
        returned here is typed on the page; returns the passkey to mail (never kept in the clear).
        A sign-up for the same email asked again replaces the one waiting."""
        name, email, password = clean_name(name), clean_email(email), check_password(password)
        salt, kdf, verifier, nonce, wrapped, _, _ = _material(name, password)
        code = crypto.new_code()
        code_salt = crypto.new_salt()
        now = now_iso()
        with self._lock:
            self._refuse_taken(name, email)
            self._con.execute("INSERT OR REPLACE INTO signups (email, name, salt, kdf, verifier, vault_nonce, vault_wrapped, "
                              "code_salt, code_hash, tries, sent_at, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                              (email, name, salt, json.dumps(kdf), verifier, nonce, wrapped, code_salt,
                               crypto.code_hash(code, code_salt), now, _at(minutes), now))
            self._con.commit()
        return code

    def signup(self, email) -> dict | None:
        """The sign-up waiting for `email`: its name, when the passkey was sent and expires, the
        tries made; None when there is none."""
        try:
            email = clean_email(email)
        except ValueError:
            return None
        with self._lock:
            r = self._con.execute("SELECT name, tries, sent_at, expires_at FROM signups WHERE email = ?", (email,)).fetchone()
        return None if r is None else {"email": email, "name": r["name"], "tries": r["tries"], "sentAt": r["sent_at"],
                                       "expiresAt": r["expires_at"]}

    def resend_signup(self, email, minutes: float = CODE_MINUTES, sooner_than: float = RESEND_SECONDS) -> str:
        """A new passkey for the sign-up waiting (the old one no longer counts); ValueError when none
        waits or the last went out less than `sooner_than` seconds ago."""
        email = clean_email(email)
        with self._lock:
            r = self._con.execute("SELECT sent_at FROM signups WHERE email = ?", (email,)).fetchone()
            if r is None:
                raise ValueError("no account is waiting for a passkey at that address: ask for one first")
            sent = datetime.fromisoformat(r["sent_at"])
            if (datetime.now(timezone.utc) - sent).total_seconds() < sooner_than:
                raise ValueError(f"a passkey went out less than {int(sooner_than)} seconds ago: look for it, then ask again")
            code = crypto.new_code()
            code_salt = crypto.new_salt()
            self._con.execute("UPDATE signups SET code_salt = ?, code_hash = ?, tries = 0, sent_at = ?, expires_at = ? WHERE email = ?",
                              (code_salt, crypto.code_hash(code, code_salt), now_iso(), _at(minutes), email))
            self._con.commit()
        return code

    def confirm_signup(self, email, code) -> dict:
        """The passkey typed: right, the user is made (their email verified) and returned as the page
        sees them (the keys open with the password at sign-in: `verify`); wrong, a try is spent
        (ValueError), and after CODE_TRIES or past the expiry the sign-up is dropped (ValueError says
        to ask again)."""
        email = clean_email(email)
        with self._lock:
            r = self._con.execute("SELECT * FROM signups WHERE email = ?", (email,)).fetchone()
            if r is None:
                raise ValueError("no account is waiting for a passkey at that address: ask for one first")
            if datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc):
                self._con.execute("DELETE FROM signups WHERE email = ?", (email,))
                self._con.commit()
                raise ValueError("that passkey has expired: ask for a new one")
            if not crypto.same(crypto.code_hash(code, r["code_salt"]), r["code_hash"]):
                tries = r["tries"] + 1
                if tries >= CODE_TRIES:
                    self._con.execute("DELETE FROM signups WHERE email = ?", (email,))
                    self._con.commit()
                    raise ValueError("that was the last try for that passkey: ask for a new one")
                self._con.execute("UPDATE signups SET tries = ? WHERE email = ?", (tries, email))
                self._con.commit()
                raise ValueError(f"wrong passkey ({CODE_TRIES - tries} tries left)")
            self._refuse_taken(r["name"], email)
            now = now_iso()
            self._con.execute("INSERT INTO users (name, salt, kdf, verifier, vault_nonce, vault_wrapped, created_at, seen_at, email, verified_at) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (r["name"], r["salt"], r["kdf"], r["verifier"], r["vault_nonce"], r["vault_wrapped"], now, now, email, now))
            self._con.execute("DELETE FROM signups WHERE email = ?", (email,))
            self._con.commit()
        return {"name": r["name"], "createdAt": now, "seenAt": now, "email": email, "verified": True}
