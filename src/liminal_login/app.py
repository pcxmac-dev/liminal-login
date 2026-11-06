"""The login app's page and API (the user, 2026-11-04: "the simpler ones like the login app, and just
have a port for that so that I can see just that one icon, that basically lets me log in, lets me
log out, gives me basic user information. When I click on the icon, when I'm logged in, gives me an
idea about the key value, database that's associated with my user, and the encrypted hash that is
used to mask the values"): an App of the library's frame (liminal_libs.apps) with the one master
icon, the user. Sessions live in memory: a token in the page's cookie and in a client's
X-Liminal-Session header, the user's vault open for the session's life and closed at sign-out or
once idle too long. The routes are the page's and the library's LoginClient's."""
from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote

from liminal_libs.apps import SESSION_HEADER, App, Refused
from liminal_libs.layout import data_dir
from liminal_libs.web import cookie

from .users import User, UserStore
from .vault import KeyPairStore, store_file

DIR_VAR = "LIMINAL_LOGIN_DIR"  # where the users' file and the stores live (store/data/login by default)
SESSION_MINUTES_VAR = "LIMINAL_LOGIN_SESSION_MINUTES"
SESSION_MINUTES = 480.0  # a session ends after this long without a request
COOKIE = "liminal_login"
FAILURE_DELAY_S = 0.5  # after a wrong name or password: no guessing at speed


def login_dir() -> Path:
    """The login's folder: LIMINAL_LOGIN_DIR, else `login/` in the data folder (store/data), never
    in a repository."""
    raw = (os.environ.get(DIR_VAR) or "").strip()
    return Path(raw) if raw else data_dir() / "login"


@dataclass
class Session:
    """A signed-in user's session: its token, the user (with the keys that open their store), their
    store open, and when it was last used."""

    token: str
    user: User
    vault: KeyPairStore
    last: float

    def close(self) -> None:
        self.vault.close()


class LoginApp(App):
    NAME, TITLE, ICON = "login", "Login", "user"
    PORT, PORT_VAR = 8795, "LIMINAL_LOGIN_PORT"
    STATIC = Path(__file__).parent / "static"
    API = "1.0"

    def __init__(self, directory: Path | None = None, log=print, failure_delay: float = FAILURE_DELAY_S):
        super().__init__(log)
        self.dir = Path(directory) if directory else login_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.users = UserStore(self.dir / "users.db")
        self.failure_delay = failure_delay
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    @property
    def session_seconds(self) -> float:
        raw = (os.environ.get(SESSION_MINUTES_VAR) or "").strip()
        try:
            minutes = float(raw) if raw else SESSION_MINUTES
        except ValueError:
            minutes = SESSION_MINUTES
        return max(minutes, 0.1) * 60

    # -- sessions --------------------------------------------------------------------------------
    @staticmethod
    def _token(handler) -> str | None:
        return handler.headers.get(SESSION_HEADER) or cookie(handler, COOKIE)

    def session(self, handler) -> Session | None:
        """The request's session, its idle clock reset; None when there is none, or it idled out
        (closed then)."""
        token = self._token(handler)
        if not token:
            return None
        now = time.monotonic()
        with self._lock:
            s = self._sessions.get(token)
            if s is None:
                return None
            if now - s.last > self.session_seconds:
                del self._sessions[token]
                s.close()
                self.log(f"login: {s.user.name}'s session ended (idle)")
                return None
            s.last = now
            return s

    def _require(self, handler) -> Session:
        s = self.session(handler)
        if s is None:
            raise Refused(HTTPStatus.UNAUTHORIZED, "not signed in")
        return s

    def _open(self, user: User) -> Session:
        vault = KeyPairStore(store_file(self.dir / "users", user.name), user.vault_key)
        s = Session(secrets.token_urlsafe(32), user, vault, time.monotonic())
        with self._lock:
            self._sessions[s.token] = s
        return s

    def _end(self, token: str | None) -> Session | None:
        with self._lock:
            s = self._sessions.pop(token, None) if token else None
        if s is not None:
            s.close()
        return s

    def end_sessions(self) -> None:
        with self._lock:
            sessions, self._sessions = list(self._sessions.values()), {}
        for s in sessions:
            s.close()

    def sessions(self) -> list[str]:
        """Who is signed in now (the names), for the command line."""
        with self._lock:
            return sorted({s.user.name for s in self._sessions.values()})

    def stop(self) -> None:
        super().stop()
        self.end_sessions()

    def close(self) -> None:
        self.stop()
        self.users.close()

    @staticmethod
    def _cookie(token: str | None) -> list[tuple[str, str]]:
        value = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict" if token \
            else f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return [("Set-Cookie", value)]

    # -- the routes ------------------------------------------------------------------------------
    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if path == "/api/status" and method == "GET":
            s = self.session(handler)
            return 200, {"users": self.users.count(), "signedIn": s is not None, "name": s.user.name if s else None,
                         "app": self.describe()}
        if path == "/api/users" and method == "GET":
            self._require(handler)
            return 200, {"users": self.users.names()}
        if path == "/api/users" and method == "POST":
            if self.users.count() and self.session(handler) is None:
                raise Refused(HTTPStatus.UNAUTHORIZED, "sign in to add a user")
            try:
                user = self.users.create(body.get("name"), body.get("password"))
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
            self.log(f"login: user {user.name} created")
            return 201, user.as_dict()
        if path == "/api/sign-in" and method == "POST":
            user = self.users.verify(body.get("name"), body.get("password"))
            if user is None:
                if self.failure_delay:
                    time.sleep(self.failure_delay)
                self.log("login: a sign-in failed (wrong name or password)")
                raise Refused(HTTPStatus.UNAUTHORIZED, "wrong name or password")
            s = self._open(user)
            self.log(f"login: {user.name} signed in")
            return 200, {"token": s.token, "user": user.as_dict()}, self._cookie(s.token)
        if path == "/api/sign-out" and method == "POST":
            s = self._end(self._token(handler))
            if s is not None:
                self.log(f"login: {s.user.name} signed out")
            return 200, {"signedOut": True}, self._cookie(None)
        if path == "/api/me" and method == "GET":
            return 200, self._me(self._require(handler))
        if path == "/api/me/password" and method == "PUT":
            s = self._require(handler)
            try:
                s.user = self.users.change_password(s.user.name, body.get("old"), body.get("new"))
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
            self.log(f"login: {s.user.name} changed their password")
            return 200, {"changed": True, "unlockFingerprint": s.user.unlock_fingerprint}
        if path == "/api/pairs" and method == "GET":
            return 200, {"pairs": self._require(handler).vault.names()}
        if path.startswith("/api/pairs/"):
            s = self._require(handler)
            name = unquote(path[len("/api/pairs/"):])
            try:
                if method == "GET":
                    try:
                        value = s.vault.get(name)
                    except KeyError:
                        raise Refused(HTTPStatus.NOT_FOUND, "no such pair") from None
                    return 200, {**s.vault.info(name), "value": value}
                if method == "PUT":
                    info = s.vault.put(name, body.get("value"), body.get("kind") or "key", body.get("label") or "")
                    self.log(f"login: {s.user.name} kept the pair {info['name']} ({info['kind']})")
                    return 200, info
                if method == "DELETE":
                    if not s.vault.remove(name):
                        raise Refused(HTTPStatus.NOT_FOUND, "no such pair")
                    self.log(f"login: {s.user.name} removed the pair {name}")
                    return 200, {"removed": True, "name": name}
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        return super().api(handler, method, path, query, body)

    def _me(self, s: Session) -> dict:
        """The signed-in user for the page: who, since when, their store and the fingerprints of the
        keys that mask it (the unlock key from the password, the vault key it wraps); never a key."""
        u = s.user
        return {"name": u.name, "createdAt": u.created_at, "seenAt": u.seen_at,
                "store": {"file": str(s.vault.path), "pairs": s.vault.count(), "vaultFingerprint": s.vault.fingerprint,
                          "unlockFingerprint": u.unlock_fingerprint, "kdf": u.kdf, "salt": u.salt.hex(),
                          "usersFile": str(self.users.path)},
                "session": {"minutes": self.session_seconds / 60}}
