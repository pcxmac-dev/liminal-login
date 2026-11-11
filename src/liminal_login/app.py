"""The login app's page and API (the user, 2026-11-04: "the simpler ones like the login app, and just
have a port for that so that I can see just that one icon, that basically lets me log in, lets me
log out, gives me basic user information. When I click on the icon, when I'm logged in, gives me an
idea about the key value, database that's associated with my user, and the encrypted hash that is
used to mask the values"; 2026-11-06: "sign up lets you put in an email and sends an email to an
email account, which you then enter the 4-6 digit code back in to the signup prompt to generate a
new user, password, etcc"; 2026-11-10: "the log-in app should not point to platform, integrator or
charts, it should be standalone"; "when its inherited it can point to it's superclass, charts, platform,
or integrator"): an App of the library's frame (liminal_libs.apps) with the one master icon, the user.
On its own it knows no other app: its users live in its own folder, under its own cookie, and the page
names it by its scope's title. An app that inherits it (its superclass) says so when it starts it
(liminal_libs.apps.inherited_by: LIMINAL_LOGIN_FOR and its title and address): that superclass's users
then live in a folder of its own here, with its own cookie, the page names it, and the pairs its
plugins ask for are asked of it (GET /api/login/pairs), never read from a plugin here. A sign-up begins with an
email; a six-digit code goes to it through the user's own mail account (liminal_libs.mail); typed
back, the name and the password are chosen and the account is made and signed in. Sessions live in
memory: a token in the page's cookie and in a client's X-Liminal-Session header, the user's vault
open for the session's life and closed at sign-out or once idle too long. The routes are the page's
and the library's LoginClient's."""
from __future__ import annotations

import json
import os
import re
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote, urlencode

from liminal_libs import layout
from liminal_libs.apps import (PAIRS_PATH, REMOTES_VAR, SESSION_HEADER, SUPER_TITLE_VAR, SUPER_URL_VAR, SUPER_VAR, App,
                               Refused, Scope, remotes_from)
from liminal_libs.apps import remote_url as remote_address
from liminal_libs.layout import data_dir
from liminal_libs.mail import MailError, Mailer, mask, mx_records
from liminal_libs.web import WRITE_HEADER
from . import __version__
from .users import CODE_MINUTES, User, UserStore
from .vault import PAIR_NAME, KeyPairStore, store_file

DIR_VAR = "LIMINAL_LOGIN_DIR"  # the login's folder (store/data/login by default): its own users, a superclass's folder each
FOR_VAR = SUPER_VAR  # LIMINAL_LOGIN_FOR: the app that inherits this login, when one does (its superclass)
NAMESPACE = re.compile(r"^[a-z][a-z0-9-]{1,23}$")  # a superclass's short name
RESERVED = frozenset({"users", "logs", "dkim"})  # the login's own folders: never a superclass's
PAIRS_SECONDS = 60.0  # the pairs a superclass's plugins ask for, asked of it again after this long
REMOTE_SECONDS = 15.0  # how long a remote login has to answer
CA_VAR = "LIMINAL_LOGIN_CA"  # a certificate authority (PEM) trusted for remote logins besides the system's: a test front's own
REMOTE_MAX = 1_000_000  # the most of an answer read from it
# what a remote user's session asks of their own login (0.15.0): who they are, their password, their pairs; the rest
# (the status, signing in and out, signing up, the pairs a plugin here asks for) is this login's
REMOTE_ROUTES = ("/api/me", "/api/me/password", "/api/pairs")
SESSION_MINUTES_VAR = "LIMINAL_LOGIN_SESSION_MINUTES"
SESSION_MINUTES = 480.0  # a session ends after this long without a request
FAILURE_DELAY_S = 0.5  # after a wrong name or password: no guessing at speed
# The secret user (0.14.0; the user, 2026-11-10: "for now lets have a secret user, name - secret, no password entry, you
# type secret in to user and click on icon"; "that will be the default"): a local login's way in without a password,
# made the first time it is asked for. Its name and password are values in the login's database (0.14.1, the user: "the
# user and the password should be values in the database for login"; users.py, `settings`), its password random, never
# in the code; a user of that name who has a password of their own is never let in this way, nor is anyone on a
# domain's login. 0.14.0 wrote one password here: a secret user made with it moves onto a random one in the database.
LEGACY_SECRET_PASSWORDS = ("liminal-secret-user",)
CODE_SUBJECT = "Your {title} code"
CODE_TEXT = ("Your code to create a {title} account is\n\n    {code}\n\n"
             "Type it on the page that asked for it within {minutes:g} minutes. If you did not ask for an "
             "account, nothing happens: ignore this message.\n")


def login_dir() -> Path:
    """The login's folder: LIMINAL_LOGIN_DIR, else `login/` in the data folder (store/data), never
    in a repository; the login's own users in it, and a folder in it for each app that inherits it."""
    raw = (os.environ.get(DIR_VAR) or "").strip()
    return Path(raw) if raw else data_dir() / "login"


MX_SECONDS = 600.0  # a domain's mail record is looked up again after this long


@dataclass(frozen=True)
class Superclass:
    """The app that inherits this login, its superclass (charts, platform, integrator, or an app to come), as it said
    when it started the login: its short name (its users' folder and cookie here), how the page names it, and where it
    answers the pairs its plugins ask for (PAIRS_PATH). The login knows nothing else of it."""

    name: str
    title: str = ""
    url: str = ""

    def describe(self) -> dict:
        return {"name": self.name, "title": self.title, "url": self.url}


def superclass_of(name=None, title=None, url=None, env=None) -> Superclass | None:
    """The app this login is inherited by: `name` (else LIMINAL_LOGIN_FOR), its title (else LIMINAL_LOGIN_FOR_TITLE, else
    "Liminal <Name>") and its address (else LIMINAL_LOGIN_FOR_URL). None: no app inherits it, the login on its own."""
    env = os.environ if env is None else env
    raw = str(name or env.get(SUPER_VAR) or "").strip().lower()
    if not raw:
        return None
    if not NAMESPACE.match(raw) or raw in RESERVED:
        raise ValueError(f"the app that inherits a login is named by a short name like charts, platform or integrator, not {raw!r}")
    shown = str(title or env.get(SUPER_TITLE_VAR) or "").strip() or f"Liminal {raw.replace('-', ' ').title()}"
    where = str(url or env.get(SUPER_URL_VAR) or "").strip().rstrip("/")
    if where and not where.lower().startswith(("http://", "https://")):
        raise ValueError(f"the address of the app that inherits a login is an http(s) URL, not {where!r}")
    return Superclass(raw, shown, where)


def remote_tls() -> ssl.SSLContext:
    """How a remote login's certificate is checked: against the system's authorities and, when LIMINAL_LOGIN_CA names one,
    that authority too (0.15.2: a remote login in Docker behind Caddy's own authority, docker/; its root certificate
    copied out of the front once). ValueError when the file named cannot be read as one."""
    context = ssl.create_default_context()
    ca = (os.environ.get(CA_VAR) or "").strip()
    if ca:
        try:
            context.load_verify_locations(cafile=ca)
        except (OSError, ssl.SSLError) as e:
            raise ValueError(f"{CA_VAR} names no certificate authority that can be read ({ca}): {e}") from None
    return context


def folder_for(root: Path, scope: Scope, superclass: Superclass | None = None) -> Path:
    """Where the users live under `root`: the login's own folder on its own, the superclass's folder in it when one
    inherits it; a domain's login keeps a folder per domain first."""
    base = root / scope.domain if scope.kind == "domain" else root
    return base / superclass.name if superclass is not None else base


@dataclass
class Session:
    """A signed-in user's session: its token, the user (with the keys that open their store), their
    store open, and when it was last used."""

    token: str
    user: User
    vault: KeyPairStore
    last: float
    passwordless: bool = False  # the secret user's: in without a password (its keys unprotected by one)

    def close(self) -> None:
        self.vault.close()


@dataclass
class RemoteUser:
    name: str  # as they signed in here: name@their.domain


@dataclass
class RemoteSession:
    """A session of a user of another login (0.15.0; the user, 2026-11-10: "login apps can connect to remote login apps";
    "and shift context to the remote execution"; "remote users are like email format user@remote.domain.tld"; "IPC turns
    in to encrypted internet comms"): their own login did the sign-in, over https, and does everything they ask after
    (who they are, their pairs) with the session it gave; nothing of theirs is kept here but that session's token."""

    token: str
    user: RemoteUser
    remote: str  # their login's address
    remote_token: str  # the session it gave
    last: float
    passwordless: bool = False
    vault = None  # their pairs are theirs, at their login

    def close(self) -> None:
        pass


class LoginApp(App):
    NAME, ICON = "login", "lambda"  # Liminal's sign (the user, 2026-11-10: "replace all user icons (login app) with the lambda sign")
    PORT = 8795
    PORT_VAR = "LIMINAL_LOGIN_PORT"
    STATIC = Path(__file__).parent / "static"
    API = "1.3"  # 1.3 (0.13.0): on its own unless inherited; `for` null on its own, `superclass` in the status

    def __init__(self, directory: Path | None = None, log=print, failure_delay: float = FAILURE_DELAY_S, mailer=None,
                 superclass: Superclass | str | None = None, scope: Scope | None = None, remotes: dict | None = None):
        super().__init__(log)
        # the app that inherits this login, as it said (a Superclass, or its short name), else LIMINAL_LOGIN_FOR; none:
        # the login on its own
        self.superclass = superclass if isinstance(superclass, Superclass) else superclass_of(superclass)
        # What this login is tied to (liminal_libs.apps.scope; the user, 2026-11-06: "login apps tied to domains
        # (with email server) or local (file://project/folder)"): the scope given, else the file found (not
        # when the users' folder is given outright: a test's), else local to the folder, else to the workspace
        self.scope = scope or (Scope.find() if directory is None else None) \
            or Scope.local(Path(directory) if directory else (layout.home() or login_dir()))
        sup = self.superclass
        self.title_for = sup.title if sup is not None else (self.scope.title or "Liminal")  # what the page names
        self.TITLE = f"Login: {sup.title}" if sup is not None else "Login"
        # cookies ignore ports: one a superclass, and the login's own
        self.cookie_name = f"liminal_login_{sup.name.replace('-', '_')}" if sup is not None else "liminal_login"
        self.root = Path(directory) if directory else (login_dir() if (os.environ.get(DIR_VAR) or "").strip()
                                                       else self.scope.data_dir(login_dir()))
        self.dir = folder_for(self.root, self.scope, sup)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.users = UserStore(self.dir / "users.db")
        self.mailer = mailer or Mailer(log=self.log, cfg=self.scope.mail_variables())
        self._exchangers: tuple[float, list[str]] | None = None  # the domain's mail record, looked up now and then
        self.last_sent: dict | None = None  # the mail server's word on the last code sent (the status, the page)
        self.failure_delay = failure_delay
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._secret_lock = threading.Lock()  # the secret user made once, however many ask at the same time
        self._pairs_asked: tuple[float, list[dict]] | None = None  # the superclass's word on its plugins' pairs, and when
        # where the logins of other domains answer (0.15.0): the file's [remotes], LIMINAL_LOGIN_REMOTES, then those given;
        # a domain not named answers at https://its.domain
        self.remotes = {**self.scope.remotes, **remotes_from(os.environ.get(REMOTES_VAR)),
                        **{k.lower().strip("."): remote_address(v) for k, v in (remotes or {}).items()}}
        self._remote_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),  # https, its certificate checked
                                                          urllib.request.HTTPSHandler(context=remote_tls()))

    @property
    def namespace(self) -> str | None:
        """The superclass's short name (its users' folder here), None on its own."""
        return self.superclass.name if self.superclass is not None else None

    def describe(self) -> dict:
        return {**super().describe(), "for": self.namespace, "forTitle": self.title_for,
                "superclass": self.superclass.describe() if self.superclass is not None else None, "scope": self.scope.describe()}

    def port(self) -> int:
        """LIMINAL_LOGIN_PORT, else the scope's file's port, else 8795 (an app that inherits the login starts it at the
        port it binds: `--port`)."""
        raw = (os.environ.get(self.PORT_VAR) or "").strip()
        return int(raw) if raw.isdecimal() else (self.scope.port or self.PORT)

    # -- whether an account can be made with a code (the user, 2026-11-06: "only allow signup if the login app
    # is tied to an smtp server"; "domain w/ email server in mail record (lookup) or specified if none") -----
    def signup_closed_why(self) -> str:
        """Why no sign-up by email here, or "" when there is one: a local login takes none; a domain's needs
        an email server, the one its mail record names or the one its file's [mail] names."""
        if self.scope.kind != "domain":
            return (f"this login is local ({self.scope.label}): no sign-up by email; accounts are made here on the page "
                    "(Sign up) or with `liminal-login user add NAME`")
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
        """The request's session of one of this login's own users (a user of another login is answered by their own:
        what they may ask is passed there before this)."""
        s = self.session(handler)
        if s is None:
            raise Refused(HTTPStatus.UNAUTHORIZED, "not signed in")
        if isinstance(s, RemoteSession):
            raise Refused(HTTPStatus.FORBIDDEN, f"a user of another login: ask your own ({s.remote})")
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

    # -- the users of other logins (0.15.0): name@their.domain signs in at their own login, which does the work -----
    def remote_url(self, host: str) -> str:
        """Where the login of `host` answers: named in [remotes] (this login's file or LIMINAL_LOGIN_REMOTES), else
        https://host."""
        host = str(host or "").strip().lower().strip(".")
        return remote_address(self.remotes.get(host) or host)

    def remote_of(self, who) -> tuple[str, str] | None:
        """(name, domain) when `who` is a user of another login, name@their.domain: not this login's own domain, and
        no user here signs in with that address as their email; None for one of this login's own."""
        who = str(who or "").strip()
        name, at, host = who.rpartition("@")
        host = host.strip().lower().strip(".")
        if not at or not name or not host:
            return None
        if self.scope.kind == "domain" and host == self.scope.domain:
            return None
        if self.users.has_email(who):
            return None
        return name, host

    def own_name(self, who) -> str:
        """name@this.domain as the name alone (one of this login's own users), unless a user here has that address as
        their email."""
        who = str(who or "").strip()
        name, at, host = who.rpartition("@")
        if at and name and self.scope.kind == "domain" and host.strip().lower().strip(".") == self.scope.domain \
                and not self.users.has_email(who):
            return name
        return who

    def _remote_call(self, base: str, method: str, path: str, body: dict | None = None, token: str | None = None,
                     query: dict | None = None) -> tuple[int, dict]:
        """One ask of a remote login, over https (http only to this machine): its status and its JSON; never through a
        proxy; the session it gave in the session header. 503 in words when it does not answer."""
        url = base + path + (("?" + urlencode(query)) if query else "")
        headers = {"Accept": "application/json", "User-Agent": f"liminal-login/{__version__}"}
        if token:
            headers[SESSION_HEADER] = token
        data = None
        if method != "GET":
            headers[WRITE_HEADER] = "1"
            headers["Content-Type"] = "application/json"
            data = json.dumps(body or {}).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._remote_opener.open(request, timeout=REMOTE_SECONDS) as r:
                status, raw = r.status, r.read(REMOTE_MAX)
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read(REMOTE_MAX)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, f"the login at {base} does not answer: {getattr(e, 'reason', e)}") from None
        try:
            out = json.loads(raw) if raw else {}
        except ValueError:
            out = {"error": f"the login at {base} answered something that is not JSON"}
        return status, (out if isinstance(out, dict) else {"error": f"the login at {base} answered something unexpected"})

    def _remote_sign_in(self, name: str, host: str, body: dict, path: str = "/api/sign-in"):
        """A user of another login signed in there (their password, or their login's secret user), the session it gave
        kept here behind one of this login's own; their answer passed back when it says no."""
        base = self.remote_url(host)
        payload = {"name": name, **({"password": body.get("password")} if path == "/api/sign-in" else {})}
        status, data = self._remote_call(base, "POST", path, payload)
        if status != 200 or not data.get("token"):
            self.log(f"login: a sign-in at {base} was refused ({status})")
            raise Refused(status if 400 <= status < 600 else HTTPStatus.BAD_GATEWAY,
                          str(data.get("error") or f"the login at {base} said no"))
        who = f"{(data.get('user') or {}).get('name') or name}@{host}"
        s = RemoteSession(secrets.token_urlsafe(32), RemoteUser(who), base, str(data["token"]), time.monotonic(),
                          bool(data.get("passwordless")))
        with self._lock:
            self._sessions[s.token] = s
        self.log(f"login: {who} signed in at {base}")
        return 200, {"token": s.token, "user": {"name": who, "remote": base}, "passwordless": s.passwordless}, self._cookie(s.token)

    def _remote_ask(self, s: RemoteSession, method: str, path: str, query: dict, body: dict | None):
        """What a remote user asks, asked of their own login with its session; when it has ended there, it ends here."""
        status, data = self._remote_call(s.remote, method, path, body, s.remote_token, query)
        if status == HTTPStatus.UNAUTHORIZED:
            self._end(s.token)
            return 401, {"error": f"your session at {s.remote} has ended: sign in again"}, self._cookie(None)
        if path == "/api/me" and status == 200:
            data = {**data, "name": s.user.name, "remote": s.remote, "passwordless": s.passwordless or bool(data.get("passwordless"))}
        return status, data

    def _secret_sign_in(self, body: dict):
        """The secret user in without a password: a local login only. The name typed is checked against the one the
        database keeps (`secret` before it is made); the user is made the first time, its password a random one kept in
        the database; refused when a user of that name has a password of their own. Any other name: 400 (the page goes
        on to its password). name@their.domain: their login's own secret user, asked there."""
        remote = self.remote_of(body.get("name"))
        if remote is not None:
            return self._remote_sign_in(*remote, body, "/api/sign-in/secret")
        if self.scope.kind == "domain":
            raise Refused(HTTPStatus.FORBIDDEN, "the secret user is only for a local login: sign in with your password")
        typed = str(body.get("name") or "").strip()
        if not typed or typed.lower() != self.users.secret_name().lower():
            raise Refused(HTTPStatus.BAD_REQUEST, "only the secret user comes in without a password: sign in with yours")
        with self._secret_lock:
            made = self.users.secret_kept() is None
            try:
                name, password = self.users.make_secret(LEGACY_SECRET_PASSWORDS)
            except ValueError:
                time.sleep(self.failure_delay)
                raise Refused(HTTPStatus.UNAUTHORIZED, "wrong name or password") from None
        if made:
            self.log("login: the secret user was made (no password: its own is kept in the login's database)")
        user = self.users.verify(name, password)
        if user is None:  # its row changed outside the login: its kept password no longer opens it
            time.sleep(self.failure_delay)
            raise Refused(HTTPStatus.UNAUTHORIZED, "wrong name or password")
        s = self._open(user)
        s.passwordless = True
        self.log(f"login: {user.name} signed in (the secret user, no password)")
        return 200, {"token": s.token, "user": user.as_dict(), "passwordless": True}, self._cookie(s.token)

    # -- the routes ------------------------------------------------------------------------------
    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if path in REMOTE_ROUTES or (path.startswith("/api/pairs/") and path != "/api/pairs/known"):
            s = self.session(handler)
            if isinstance(s, RemoteSession):  # a user of another login: asked there (0.15.0)
                return self._remote_ask(s, method, path, query, body if method != "GET" else None)
        if path == "/api/status" and method == "GET":
            s = self.session(handler)
            return 200, {"users": self.users.count(), "signedIn": s is not None, "name": s.user.name if s else None,
                         "remote": s.remote if isinstance(s, RemoteSession) else None,
                         "for": self.namespace, "forTitle": self.title_for,
                         "superclass": self.superclass.describe() if self.superclass is not None else None,
                         "scope": self.scope.describe(),
                         "signup": self.signup_status(), "app": self.describe()}
        if path == "/api/users" and method == "GET":
            self._require(handler)
            return 200, {"users": self.users.names()}
        if path == "/api/users" and method == "POST":
            # a domain's login: a user signed in adds one, everyone else signs up with a code; a local login: anyone at
            # this machine signs up on the page (0.14.0, the user: "signup and sign-in should be options too")
            if self.users.count() and not isinstance(self.session(handler), Session) and self.scope.kind == "domain":
                raise Refused(HTTPStatus.UNAUTHORIZED, "sign in to add a user")  # one of its own users: not another login's
            if not self.users.count() and self.signup_open():
                raise Refused(HTTPStatus.CONFLICT, "the first account is made with a code sent to your email (sign up)")
            try:
                user = self.users.create(body.get("name"), body.get("password"), body.get("email") or None)
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
            self.log(f"login: user {user.name} created")
            return 201, user.as_dict()
        if path == "/api/sign-in/secret" and method == "POST":
            return self._secret_sign_in(body)
        if path == "/api/signup" and method == "POST":
            return self._signup(body)
        if path == "/api/signup/resend" and method == "POST":
            return self._resend(body)
        if path == "/api/signup/verify" and method == "POST":
            return self._verify(body)
        if path == "/api/signup/complete" and method == "POST":
            return self._complete(body)
        if path == "/api/sign-in" and method == "POST":
            remote = self.remote_of(body.get("name"))
            if remote is not None:  # name@their.domain: their own login signs them in, and does the work after
                return self._remote_sign_in(*remote, body)
            user = self.users.verify(self.own_name(body.get("name")), body.get("password"))
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
                if isinstance(s, RemoteSession):  # and theirs at their own login
                    try:
                        self._remote_call(s.remote, "POST", "/api/sign-out", {}, s.remote_token)
                    except Refused:
                        self.log(f"login: {s.remote} did not answer the sign-out; its session ends there by itself")
            return 200, {"signedOut": True}, self._cookie(None)
        if path == "/api/me" and method == "GET":
            return 200, self._me(self._require(handler))
        if path == "/api/me/password" and method == "PUT":
            s = self._require(handler)
            # the secret user (0.15.1): its current password is the key the login keeps, never typed; the new one becomes
            # the key kept, so the way in by its name goes on working
            kept = self.users.secret_kept() if s.passwordless else None
            if s.passwordless and (kept is None or kept[0].lower() != s.user.name.lower()):
                raise Refused(HTTPStatus.CONFLICT, "the login no longer keeps this user's password: sign in again")
            try:
                s.user = self.users.change_password(s.user.name, kept[1] if kept else body.get("old"), body.get("new"))
            except ValueError as e:
                raise Refused(HTTPStatus.BAD_REQUEST, str(e)) from None
            if kept:
                self.users.set_setting("secret_password", str(body.get("new")))
            self.log(f"login: {s.user.name} changed their password" + (" (the key the login keeps)" if kept else ""))
            return 200, {"changed": True, "unlockFingerprint": s.user.unlock_fingerprint}
        if path == "/api/pairs" and method == "GET":
            return 200, {"pairs": self._require(handler).vault.names()}
        if path == "/api/pairs/known" and method == "GET":
            s = self.session(handler)
            if isinstance(s, RemoteSession):  # the pairs a plugin here asks for, set or not in their own login's store
                status, data = self._remote_call(s.remote, "GET", "/api/pairs", None, s.remote_token)
                have = {p.get("name") for p in data.get("pairs", []) if isinstance(p, dict)} if status == 200 else set()
                return 200, {"known": [{**r, "set": r["name"] in have} for r in self.superclass_pairs()]}
            return 200, {"known": self.known_pairs(s)}
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
        """The pairs the superclass's plugins ask for (the user, 2026-11-06: "By the variables": `massive-api-key` for
        MASSIVE_API_KEY), each marked whether the signed-in user has it. Asked of the superclass, since the login knows
        no plugin itself (0.13.0, the user: "the log-in app should not point to platform, integrator or charts"); none
        for the login on its own, or when its superclass gives no address or does not answer."""
        have = {p["name"] for p in s.vault.names()} if s is not None else set()
        return [{**r, "set": r["name"] in have} for r in self.superclass_pairs()]

    def superclass_pairs(self) -> list[dict]:
        """The superclass's word on the pairs its plugins ask for (GET <its address>/api/login/pairs), kept a minute."""
        sup = self.superclass
        if sup is None or not sup.url:
            return []
        now = time.monotonic()
        with self._lock:
            kept = self._pairs_asked
        if kept is not None and now - kept[0] < PAIRS_SECONDS:
            return kept[1]
        rows = self._ask_pairs(sup)
        with self._lock:
            self._pairs_asked = (now, rows)
        return rows

    def _ask_pairs(self, sup: Superclass) -> list[dict]:
        """One question to the superclass, never through a proxy; its rows kept as data (a name a pair can have, the
        fields the page shows), anything else dropped. A superclass that does not answer: none, said in the log."""
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(sup.url + PAIRS_PATH, headers={"Accept": "application/json"})
        try:
            with opener.open(request, timeout=3) as r:
                data = json.loads(r.read(1_000_000))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
            self.log(f"login: {sup.title} did not say which pairs its plugins ask for ({sup.url}{PAIRS_PATH}: {e})")
            return []
        rows = []
        for r in (data.get("pairs") if isinstance(data, dict) else None) or []:
            if isinstance(r, dict) and isinstance(r.get("name"), str) and PAIR_NAME.match(r["name"]):
                rows.append({"name": r["name"], **{k: str(r.get(k) or "") for k in ("variable", "plugin", "title", "label", "kind", "system")},
                             "secret": bool(r.get("secret"))})
        return rows

    def _me(self, s: Session) -> dict:
        """The signed-in user for the page: who, since when, their store and the fingerprints of the
        keys that mask it (the unlock key from the password, the vault key it wraps); never a key."""
        u = s.user
        return {"name": u.name, "createdAt": u.created_at, "seenAt": u.seen_at, "email": u.email,
                "verified": u.verified_at is not None, "for": self.namespace, "forTitle": self.title_for,
                "store": {"file": str(s.vault.path), "pairs": s.vault.count(), "vaultFingerprint": s.vault.fingerprint,
                          "unlockFingerprint": u.unlock_fingerprint, "kdf": u.kdf, "salt": u.salt.hex(),
                          "usersFile": str(self.users.path)},
                "session": {"minutes": self.session_seconds / 60}, "passwordless": s.passwordless}
