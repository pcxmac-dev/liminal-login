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

from liminal_libs import layout
from liminal_libs.apps import SESSION_HEADER, App, Refused, Scope
from liminal_libs.layout import data_dir
from liminal_libs.mail import MailError, Mailer, mask, mx_records
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


MX_SECONDS = 600.0  # a domain's mail record is looked up again after this long


def folder_for(root: Path, scope: Scope, namespace: str) -> Path:
    """The namespace's folder under `root`: a domain's login keeps a folder per domain first."""
    return root / scope.domain / namespace if scope.kind == "domain" else root / namespace


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
                 namespace: str | None = None, scope: Scope | None = None):
        super().__init__(log)
        self.namespace = namespace_of(namespace)
        self.title_for, self.PORT = NAMESPACES.get(self.namespace, (f"Liminal {self.namespace.capitalize()}", 8795))
        self.TITLE = f"Login: {self.title_for}"
        self.cookie_name = f"liminal_login_{self.namespace.replace('-', '_')}"  # cookies ignore ports: one a namespace
        # What this login is tied to (liminal_libs.apps.scope; the user, 2026-11-06: "login apps tied to domains
        # (with email server) or local (file://project/folder)"): the scope given, else the file found (not
        # when the users' folder is given outright: a test's), else local to the folder, else to the workspace
        self.scope = scope or (Scope.find() if directory is None else None) \
            or Scope.local(Path(directory) if directory else (layout.home() or login_dir()))
        self.root = Path(directory) if directory else (login_dir() if (os.environ.get(DIR_VAR) or "").strip()
                                                       else self.scope.data_dir(login_dir()))
        self.dir = folder_for(self.root, self.scope, self.namespace)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.users = UserStore(self.dir / "users.db")
        self.mailer = mailer or Mailer(log=self.log, cfg=self.scope.mail_variables())
        self._exchangers: tuple[float, list[str]] | None = None  # the domain's mail record, looked up now and then
        self.last_sent: dict | None = None  # the mail server's word on the last code sent (the status, the page)
        self.failure_delay = failure_delay
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def describe(self) -> dict:
        return {**super().describe(), "for": self.namespace, "forTitle": self.title_for, "scope": self.scope.describe()}

    def port(self) -> int:
        """LIMINAL_LOGIN_PORT, else the scope's file's port, else the namespace's."""
        raw = (os.environ.get(self.PORT_VAR) or "").strip()
        return int(raw) if raw.isdecimal() else (self.scope.port or self.PORT)

    # -- whether an account can be made with a code (the user, 2026-11-06: "only allow signup if the login app
    # is tied to an smtp server"; "domain w/ email server in mail record (lookup) or specified if none") -----
    def signup_closed_why(self) -> str:
        """Why no sign-up by email here, or "" when there is one: a local login takes none; a domain's needs
        an email server, the one its mail record names or the one its file's [mail] names."""
        if self.scope.kind != "domain":
            return (f"this login is local ({self.scope.label}): no sign-up by email; the first user is made here, "
                    "the next by a signed-in user or `liminal-login user add NAME`")
        s = self.mailer.settings
        if not s.configured:
            return "email sending is not set up: " + "; ".join(s.problems()) + " (or `liminal-login user add NAME` here)"
        if s.direct and not self._domain_mail_record():
            return (f"no email server for {self.scope.domain}: none in its mail record (MX) and none named in "
                    "liminal-login.cfg's [mail] (or `liminal-login user add NAME` here)")
        return ""

    def signup_open(self) -> bool:
        return self.signup_closed_why() == ""

    def signup_status(self) -> dict:
        """The status's word on signing up: whether a code can make an account here, and why not. A local login sends no
        email, so it names no mail account (0.12.1: it named this machine's, the sender's address among them, though it
        never sends a message); a domain's says how its codes go out and the mail server's word on the last one."""
        why = self.signup_closed_why()
        if self.scope.kind != "domain":
            return {"email": False, "local": True, "configured": False, "lastSent": None, "why": why}
        return {"email": why == "", "local": False, **self.mailer.settings.describe(), "lastSent": self.last_sent, "why": why}

    def mail_words(self) -> str:
        """How the codes go out, in words for the start-up line (0.12.1: a local login said "passkeys through direct",
        this machine's mail account, though it sends none)."""
        if self.scope.kind != "domain":
            return "a local login: no email"
        s = self.mailer.settings
        return f"passkeys through {s.host}" if s.configured else "no mail account set (LIMINAL_SMTP_*): no passkeys"

    def _domain_mail_record(self) -> list[str]:
        now = time.monotonic()
        if self._exchangers is None or now - self._exchangers[0] > MX_SECONDS:
            self._exchangers = (now, mx_records(self.scope.domain) or [])
        return self._exchangers[1]

    @property
    def session_seconds(self) -> float:
        raw = (os.environ.get(SESSION_MINUTES_VAR) or "").strip()
        try:
            minutes = float(raw) if raw else SESSION_MINUTES
        except ValueError:
            minutes = SESSION_MINUTES
        return max(minutes, 0.1) * 60

    # -- sessions --------------------------------------------------------------------------------
    def _tokens(self, handler) -> list[str]:
        """The session tokens a request carries: the header's, then every cookie of this app's name
        (a browser may hold more than one, from another path or an earlier sign-in: the live one counts)."""
        out = [handler.headers.get(SESSION_HEADER) or ""]
        for part in (handler.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == self.cookie_name:
                out.append(value)
        return [t for t in out if t]

    def _token(self, handler) -> str | None:
        tokens = self._tokens(handler)
        with self._lock:
            live = [t for t in tokens if t in self._sessions]
        return live[0] if live else (tokens[0] if tokens else None)

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
                         "for": self.namespace, "forTitle": self.title_for, "scope": self.scope.describe(),
                         "signup": self.signup_status(), "app": self.describe()}
        if path == "/api/users" and method == "GET":
            self._require(handler)
            return 200, {"users": self.users.names()}
        if path == "/api/users" and method == "POST":
            if self.users.count() and self.session(handler) is None:
                raise Refused(HTTPStatus.UNAUTHORIZED, "sign in to add a user")
            if not self.users.count() and self.signup_open():
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
            for token in self._tokens(handler):  # every session this browser carries
                s = self._end(token)
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
        if path == "/api/pairs/known" and method == "GET":
            return 200, {"known": self.known_pairs(self.session(handler))}
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
    def _send_code(self, email: str, code: str) -> dict:
        """The code mailed, and the mail server's word that it took the message (the user, 2026-11-06:
        "only if it did, does it wait for the response, if no valid response than don't have me wait to
        enter a code"): a refusal drops the sign-up, so nothing waits for a code that never went out."""
        try:
            sent = self.mailer.send(email, CODE_SUBJECT.format(title=self.title_for),
                                    CODE_TEXT.format(title=self.title_for, code=code, minutes=CODE_MINUTES))
        except MailError as e:
            self.users.forget_signup(email)
            self.log(f"login: the code for {mask(email)} could not be sent, the sign-up dropped: {e}")
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, f"the code could not be sent, so nothing waits for one: {e}") from None
        receipt = sent.as_dict()
        self.last_sent = receipt
        return receipt

    def _signup(self, body: dict):
        """An email: its code goes out; the sign-up waits for it. Only a domain's login with an email server
        takes sign-ups, for addresses at the domain unless its file says `members = any`."""
        why = self.signup_closed_why()
        if why:
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, why)
        email = (body.get("email") or "").strip().lower()
        if self.scope.members == "domain" and not email.endswith("@" + self.scope.domain):
            raise Refused(HTTPStatus.BAD_REQUEST, f"this login is for {self.scope.domain}: an address at it")
        try:
            code = self.users.start_signup(body.get("email"))
        except ValueError as e:
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        waiting = self.users.signup(body.get("email"))
        sent = self._send_code(waiting["email"], code)
        self.log(f"login: a sign-up began for {mask(waiting['email'])}; its code went out "
                 f"({sent['host']} answered {sent['code']} {sent['reply']})")
        return 202, {"email": mask(waiting["email"]), "expiresAt": waiting["expiresAt"], "minutes": CODE_MINUTES, "sent": sent}

    def _resend(self, body: dict):
        try:
            code = self.users.resend_signup(body.get("email"))
        except ValueError as e:
            raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
        waiting = self.users.signup(body.get("email"))
        sent = self._send_code(waiting["email"], code)
        return 202, {"email": mask(waiting["email"]), "expiresAt": waiting["expiresAt"], "minutes": CODE_MINUTES, "sent": sent}

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

    def known_pairs(self, s: Session | None = None) -> list[dict]:
        """The pairs the plugins of this login's app ask for (the user, 2026-11-06: "By the
        variables"): every plugin's key variables as pairs (`massive-api-key` for MASSIVE_API_KEY),
        with the plugin, its label, whether it is a secret, and whether the signed-in user has it.
        Read from the plugin registry when asked (the plugins installed beside this app)."""
        try:
            from liminal_libs.sources.registry import assistants, providers, publishers
        except Exception:  # noqa: BLE001 - no registry here: nothing known
            return []
        have = {p["name"] for p in s.vault.names()} if s is not None else set()
        plugins = [*providers().values(), *publishers().values(), *assistants().values()]
        rows: dict[str, dict] = {}  # by pair: a plugin's parts share their keys (one row, the plugin's own)
        for p in sorted(plugins, key=lambda p: (getattr(p, "part_of", None) or p.name, p.name)):
            for k in getattr(p, "keys", ()) or ():
                rows.setdefault(k.pair, {"name": k.pair, "variable": k.name, "plugin": getattr(p, "part_of", None) or p.name,
                                         "title": p.title, "label": k.label, "secret": k.secret,
                                         "kind": "key" if k.secret else "detail", "system": getattr(p, "SYSTEM", ""),
                                         "set": k.pair in have})
        return sorted(rows.values(), key=lambda r: (r["plugin"], r["name"]))

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
