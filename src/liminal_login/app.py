"""The login app's page and API (the user, 2026-11-04: "the simpler ones like the login app, and just
have a port for that so that I can see just that one icon, that basically lets me log in, lets me
log out, gives me basic user information. When I click on the icon, when I'm logged in, gives me an
idea about the key value, database that's associated with my user, and the encrypted hash that is
used to mask the values"; 2026-11-06: "sign up lets you put in an email and sends an email to an
email account, which you then enter the 4-6 digit code back in to the signup prompt to generate a
new user, password, etcc"; "each login-app instance is either tied to the chart app or the
integrator app ... the context/name space under which the user exists is either for the integrator
or the chart app"): an App of the library's frame (liminal_libs.apps) with the one master icon, the
user, serving one app, its namespace (`for`: "charts" or "integrator"; LIMINAL_LOGIN_FOR), whose
users live in their own folder, with their own cookie and default port. A sign-up begins with an
email; a six-digit code goes to it through the user's own mail account (liminal_libs.mail); typed
back, the name and the password are chosen and the account is made and signed in. Sessions live in
memory: a token in the page's cookie and in a client's X-Liminal-Session header, the user's vault
open for the session's life and closed at sign-out or once idle too long. The routes are the page's
and the library's LoginClient's."""
from __future__ import annotations

import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote

from liminal_libs.apps import SESSION_HEADER, App, Refused
from liminal_libs.layout import data_dir
from liminal_libs.mail import MailError, Mailer, mask
from liminal_libs.web import cookie

from .users import CODE_MINUTES, User, UserStore
from .vault import KeyPairStore, store_file

DIR_VAR = "LIMINAL_LOGIN_DIR"  # where the namespaces' folders live (store/data/login by default)
FOR_VAR = "LIMINAL_LOGIN_FOR"  # the app this instance serves: its users' namespace
NAMESPACES = {"charts": ("Liminal Charts", 8795), "integrator": ("Liminal Integrator", 8796)}  # title, default port
NAMESPACE = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
SESSION_MINUTES_VAR = "LIMINAL_LOGIN_SESSION_MINUTES"
SESSION_MINUTES = 480.0  # a session ends after this long without a request
FAILURE_DELAY_S = 0.5  # after a wrong name or password: no guessing at speed
CODE_SUBJECT = "Your {title} code"
CODE_TEXT = ("Your code to create a {title} account is\n\n    {code}\n\n"
             "Type it on the page that asked for it within {minutes:g} minutes. If you did not ask for an "
             "account, nothing happens: ignore this message.\n")


def login_dir() -> Path:
    """The login's folder: LIMINAL_LOGIN_DIR, else `login/` in the data folder (store/data), never
    in a repository; each namespace has a folder of its own inside it."""
    raw = (os.environ.get(DIR_VAR) or "").strip()
    return Path(raw) if raw else data_dir() / "login"


def namespace_of(value=None) -> str:
    """The app this instance serves (`value`, else LIMINAL_LOGIN_FOR, else charts): charts or
    integrator, or another short name for an app to come."""
    raw = (value or os.environ.get(FOR_VAR) or "charts").strip().lower()
    if not NAMESPACE.match(raw):
        raise ValueError(f"the app a login serves is a short name like charts or integrator, not {raw!r}")
    return raw


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
    NAME, ICON = "login", "user"
    PORT_VAR = "LIMINAL_LOGIN_PORT"
    STATIC = Path(__file__).parent / "static"
    API = "1.2"

    def __init__(self, directory: Path | None = None, log=print, failure_delay: float = FAILURE_DELAY_S, mailer=None,
                 namespace: str | None = None):
        super().__init__(log)
        self.namespace = namespace_of(namespace)
        self.title_for, self.PORT = NAMESPACES.get(self.namespace, (f"Liminal {self.namespace.capitalize()}", 8795))
        self.TITLE = f"Login: {self.title_for}"
        self.cookie_name = f"liminal_login_{self.namespace.replace('-', '_')}"  # cookies ignore ports: one a namespace
        self.root = Path(directory) if directory else login_dir()
        self.dir = self.root / self.namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.users = UserStore(self.dir / "users.db")
        self.mailer = mailer or Mailer(log=self.log)
        self.failure_delay = failure_delay
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def describe(self) -> dict:
        return {**super().describe(), "for": self.namespace, "forTitle": self.title_for}

    @property
    def session_seconds(self) -> float:
        raw = (os.environ.get(SESSION_MINUTES_VAR) or "").strip()
        try:
            minutes = float(raw) if raw else SESSION_MINUTES
        except ValueError:
            minutes = SESSION_MINUTES
        return max(minutes, 0.1) * 60

    # -- sessions --------------------------------------------------------------------------------
    def _token(self, handler) -> str | None:
        return handler.headers.get(SESSION_HEADER) or cookie(handler, self.cookie_name)

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

    def _cookie(self, token: str | None) -> list[tuple[str, str]]:
        value = f"{self.cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict" if token \
            else f"{self.cookie_name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return [("Set-Cookie", value)]

    def _signed_in(self, user: User, status: int = 200):
        s = self._open(user)
        self.log(f"login: {user.name} signed in")
        return status, {"token": s.token, "user": user.as_dict()}, self._cookie(s.token)

    # -- the routes ------------------------------------------------------------------------------
    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if path == "/api/status" and method == "GET":
            s = self.session(handler)
            return 200, {"users": self.users.count(), "signedIn": s is not None, "name": s.user.name if s else None,
                         "for": self.namespace, "forTitle": self.title_for,
                         "signup": {"email": self.mailer.configured, **self.mailer.settings.describe()},
                         "app": self.describe()}
        if path == "/api/users" and method == "GET":
            self._require(handler)
            return 200, {"users": self.users.names()}
        if path == "/api/users" and method == "POST":
            if self.users.count() and self.session(handler) is None:
                raise Refused(HTTPStatus.UNAUTHORIZED, "sign in to add a user")
            if not self.users.count() and self.mailer.configured:
                raise Refused(HTTPStatus.CONFLICT, "the first account is made with a code sent to your email (sign up)")
            try:
                user = self.users.create(body.get("name"), body.get("password"), body.get("email") or None)
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
            self.log(f"login: user {user.name} created")
            return 201, user.as_dict()
        if path == "/api/signup" and method == "POST":
            return self._signup(body)
        if path == "/api/signup/resend" and method == "POST":
            return self._resend(body)
        if path == "/api/signup/verify" and method == "POST":
            return self._verify(body)
        if path == "/api/signup/complete" and method == "POST":
            return self._complete(body)
        if path == "/api/sign-in" and method == "POST":
            user = self.users.verify(body.get("name"), body.get("password"))
            if user is None:
                if self.failure_delay:
                    time.sleep(self.failure_delay)
                self.log("login: a sign-in failed (wrong name or password)")
                raise Refused(HTTPStatus.UNAUTHORIZED, "wrong name or password")
            return self._signed_in(user)
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

    # -- a sign-up: the email, its code, then the name and the password ----------------------------
    def _send_code(self, email: str, code: str) -> None:
        try:
            self.mailer.send(email, CODE_SUBJECT.format(title=self.title_for),
                             CODE_TEXT.format(title=self.title_for, code=code, minutes=CODE_MINUTES))
        except MailError as e:
            self.log(f"login: the code for {mask(email)} could not be sent: {e}")
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, f"the code could not be sent: {e}") from None

    def _signup(self, body: dict):
        """An email: its code goes out; the sign-up waits for it."""
        if not self.mailer.configured:
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, "email sending is not set up on this machine: "
                          + "; ".join(self.mailer.settings.problems()) + " (or `liminal-login user add NAME` here)")
        try:
            code = self.users.start_signup(body.get("email"))
        except ValueError as e:
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        waiting = self.users.signup(body.get("email"))
        self._send_code(waiting["email"], code)
        self.log(f"login: a sign-up began for {mask(waiting['email'])}; its code went out")
        return 202, {"email": mask(waiting["email"]), "expiresAt": waiting["expiresAt"], "minutes": CODE_MINUTES}

    def _resend(self, body: dict):
        try:
            code = self.users.resend_signup(body.get("email"))
        except ValueError as e:
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        waiting = self.users.signup(body.get("email"))
        self._send_code(waiting["email"], code)
        return 202, {"email": mask(waiting["email"]), "expiresAt": waiting["expiresAt"], "minutes": CODE_MINUTES}

    def _verify(self, body: dict):
        """The code typed: right, the proof for the last step; wrong, a try spent."""
        try:
            token = self.users.verify_signup(body.get("email"), body.get("code"))
        except ValueError as e:
            self.log(f"login: a code was refused for {mask(str(body.get('email') or ''))}: {e}")
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        self.log(f"login: {mask(str(body.get('email') or ''))} verified its address")
        return 200, {"token": token, "email": mask(str(body.get("email") or "")), "minutes": 30}

    def _complete(self, body: dict):
        """The name and the password chosen: the account is made (its email verified) and signed in."""
        try:
            user = self.users.complete_signup(body.get("email"), body.get("token"), body.get("name"), body.get("password"))
        except ValueError as e:
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        self.log(f"login: the account {user.name} was made ({mask(user.email or '')} verified)")
        return self._signed_in(user, 201)

    def _me(self, s: Session) -> dict:
        """The signed-in user for the page: who, since when, their store and the fingerprints of the
        keys that mask it (the unlock key from the password, the vault key it wraps); never a key."""
        u = s.user
        return {"name": u.name, "createdAt": u.created_at, "seenAt": u.seen_at, "email": u.email,
                "verified": u.verified_at is not None, "for": self.namespace, "forTitle": self.title_for,
                "store": {"file": str(s.vault.path), "pairs": s.vault.count(), "vaultFingerprint": s.vault.fingerprint,
                          "unlockFingerprint": u.unlock_fingerprint, "kdf": u.kdf, "salt": u.salt.hex(),
                          "usersFile": str(self.users.path)},
                "session": {"minutes": self.session_seconds / 60}}
