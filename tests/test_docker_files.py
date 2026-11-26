"""A remote login in Docker (docker/; 0.15.2, the user, 2026-11-10: "just prepare for using docker on platform as a way
to login remotely with only the login-app"): the files the platform will set up from, read as text (nothing is built or
run here); the front's way of handing requests to the app tried against the app itself; and the certificate authority a
login may trust for a remote's front (LIMINAL_LOGIN_CA).

LOG-C1 (2026-11-23; the user: "The two high ones"): the recipe gave anyone who reached it a session without a password,
as the secret user, the login's admin, and let them make accounts without one. Now the container's login is a domain's
(the host its front answers at), the front marks every request it hands on, and only a program at the login's own
machine comes in without a password or makes an account without a session; the port is this machine's alone unless the
deployer says wider, and behind the https front the session cookie is Secure. On the user's own machine, without the
front, everything is as it was: the secret user and `default` come in by their names, from 127.0.0.1. The container's
scope is said to the login's own command line (LIMINAL_LOGIN_SCOPE; the user, 2026-11-24): a login made in code, the
one an app holds, never reads it.

The last check of that fix (2026-11-25; the user: "Closed unless turned on"): a domain's login, the container took
sign-ups by a mailed code as soon as its host had a mail record. The recipe ships with sign-up by email closed (its
file's `signup` line, and compose.yaml's LIMINAL_LOGIN_SIGNUP for a copy of the file without it), and the file's own
`signup = open` opens it. Tried on the login `liminal-login serve` itself makes, the host's mail record and the mailer
stand-ins: no name is looked up and no message leaves."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import _port
from liminal_libs import web
from liminal_libs.apps import SESSION_HEADER, App, Scope
from liminal_libs.mail import Mailer, Sent
from liminal_libs.web import WRITE_HEADER
from liminal_login import app as app_mod
from liminal_login import cli
from liminal_login.app import LoginApp
from liminal_login.cli import scoped

DOCKER = Path(__file__).resolve().parents[1] / "docker"
REAL_FIND = Scope.__dict__["find"]  # the file every app reads, as the container's login reads it (conftest stands it in)


def interpolated(text: str, env: dict) -> str:
    """Compose's ${NAME:-default} filled in as compose fills a file in: the variable's value, else (unset or empty) the
    default."""
    return re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", lambda m: env.get(m.group(1)) or (m.group(2) or ""), text)


def test_the_container_files_run_the_login_app_alone_behind_its_https_front():
    dockerfile = (DOCKER / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.13-slim" in dockerfile and "COPY --from=libs src /src/liminal-libs/src" in dockerfile
    assert "LIMINAL_LOGIN_DIR=/data/login" in dockerfile and "LIMINAL_LOGIN_CFG=/config/liminal-login.cfg" in dockerfile
    assert 'CMD ["liminal-login", "serve", "--no-browser", "--port", "8795"]' in dockerfile
    compose = (DOCKER / "compose.yaml").read_text(encoding="utf-8")
    for line in ("name: liminal-login-remote", "libs: ../../common", 'network_mode: "service:login"', "image: caddy:2.10-alpine",
                 '"${LIMINAL_REMOTE_BIND:-127.0.0.1}:${LIMINAL_REMOTE_PORT:-8443}:8443"',
                 'LIMINAL_LOGIN_SCOPE: "https://${LIMINAL_REMOTE_HOST:-localhost}"', 'LIMINAL_LOGIN_SIGNUP: "closed"',
                 "./liminal-login.cfg:/config/liminal-login.cfg:ro", "login-data:/data"):
        assert line in compose, line
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:  # where PyYAML is installed, the file is read as compose reads it
        services = yaml.safe_load(compose)["services"]
        assert set(services) == {"login", "front"} and services["front"]["network_mode"] == "service:login"
        assert services["login"]["environment"]["LIMINAL_LOGIN_SCOPE"] == "https://${LIMINAL_REMOTE_HOST:-localhost}"
        assert services["login"]["ports"] == ["${LIMINAL_REMOTE_BIND:-127.0.0.1}:${LIMINAL_REMOTE_PORT:-8443}:8443"]
    caddy = (DOCKER / "Caddyfile").read_text(encoding="utf-8")
    assert "{$LIMINAL_REMOTE_HOST}:8443 {" in caddy and "tls internal" in caddy and "reverse_proxy 127.0.0.1:8795 {" in caddy
    assert "header_up Host 127.0.0.1:8795" in caddy and "header_up -Origin" in caddy
    scope = Scope.read(DOCKER / "liminal-login.cfg")  # a domain's login, the front's host: no way in without a password
    assert (scope.kind, scope.title, scope.port, scope.url, scope.domain) == ("domain", "Liminal (remote)", 8795,
                                                                              "https://localhost", "localhost")
    # and no sign-up by email until its own line says open: said by the file and by compose.yaml (the tests below)
    assert app_mod.signup_line(DOCKER / "liminal-login.cfg") == "closed" and (scope.mail, scope.members) == ({}, "domain")


def test_the_port_is_published_on_this_machine_alone_unless_the_deployer_says_wider():
    """The published port named every interface ("8443:8443"): anyone who could reach the machine reached the front.
    It is 127.0.0.1's unless LIMINAL_REMOTE_BIND names a wider address, every interface's (0.0.0.0) or one. And it is
    the one port published: the whole list under the file's one `ports:` is read as text, every entry of it, so a
    second one beside it (unquoted, with a comment after it, in the long form) is seen without PyYAML, which neither
    this machine's Python nor CI has (the half of the files test that reads the YAML runs in neither)."""
    compose = (DOCKER / "compose.yaml").read_text(encoding="utf-8")
    lines = [line.strip() for line in compose.splitlines()]
    assert [line for line in lines if re.match(r"ports\s*:", line)] == ["ports:"], "one service publishes: the login's"
    entries = []
    for line in lines[lines.index("ports:") + 1:]:
        if line and not line.startswith(("#", "-")):
            break  # the next key ends the list
        if line.startswith("-"):
            entries.append(line)
    published = re.findall(r'^-\s*"([^"]*:8443)"$', "\n".join(entries), re.M)
    assert len(entries) == 1 == len(published), ("the front's port is published once, by a line read here", entries)
    for env, address, port in (({}, "127.0.0.1", "8443"), ({"LIMINAL_REMOTE_BIND": ""}, "127.0.0.1", "8443"),
                               ({"LIMINAL_REMOTE_BIND": "0.0.0.0"}, "0.0.0.0", "8443"),
                               ({"LIMINAL_REMOTE_BIND": "100.64.1.2", "LIMINAL_REMOTE_PORT": "9443"}, "100.64.1.2", "9443")):
        for entry in published:
            assert interpolated(entry, env).split(":") == [address, port, "8443"], (entry, env)


def test_the_front_marks_every_request_it_hands_on():
    """Caddy's `header_up X-Liminal-Front 1` sets the mark on every request, over whatever a client sent, inside the
    site's reverse_proxy (the only way in)."""
    caddy = (DOCKER / "Caddyfile").read_text(encoding="utf-8")
    body = re.search(r"reverse_proxy 127\.0\.0\.1:8795 \{(.*?)\n\t\}", caddy, re.S)
    assert body and re.search(rf"^\s*header_up {re.escape(web.FRONT_HEADER)} 1\s*$", body.group(1), re.M)
    assert caddy.count("reverse_proxy") == 1


def _call(port, method, path, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=headers or {})
        r = conn.getresponse()
        raw = r.read()
    finally:
        conn.close()
    return r.status, raw, r


def _front(port, **more):
    """A request as the front hands it on: the app's own Host, no Origin, its mark, and its word on the browser's address
    and scheme (Caddy's X-Forwarded-For and X-Forwarded-Proto); a write's header and type."""
    return {"Host": f"127.0.0.1:{port}", "Sec-Fetch-Site": "same-origin", web.FRONT_HEADER: "1",
            "X-Forwarded-For": "198.51.100.7", "X-Forwarded-Proto": "https", "Content-Type": "application/json",
            WRITE_HEADER: "1", **more}


def _here(port, **more):
    """A request a program on this machine sends: no front's mark."""
    return {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", WRITE_HEADER: "1", **more}


def test_the_front_hands_a_page_s_requests_to_the_app_as_a_page_of_its_own_machine_but_marked(served):
    """Behind the front, a browser's page at https://remote.test sends Host remote.test and Origin https://remote.test:
    the app, answering only its own machine, refuses both. The Caddyfile hands them on with the app's own address as the
    Host, no Origin, and its mark: the app takes them, but nobody it reaches so comes in without a password (the secret
    user, `default`, another login's secret user) or makes an account without a session, whatever the mark says. Until
    then the front's requests were a program's at the machine, and anyone who reached it was the login's admin. Another
    site's page is still refused by its Sec-Fetch-Site, and a write still needs the app's own header. Sent from the
    machine itself, without the mark, the secret user and the page's sign-up are as they were."""
    app, port, lines = served
    asked: list = []
    app._remote_opener = SimpleNamespace(open=lambda *a, **k: asked.append(a) or pytest.fail("no other login is asked"))
    page = {"Host": "remote.test", "Origin": "https://remote.test", "Sec-Fetch-Site": "same-origin"}
    assert _call(port, "GET", "/api/status", headers=page)[0] == 403  # as the browser sent it: not this machine's
    assert _call(port, "GET", "/api/status", headers=_front(port))[0] == 200
    for name in ("secret", " Secret ", "default", "secret@remote.test"):
        status, raw, _ = _call(port, "POST", "/api/sign-in/secret", {"name": name}, _front(port))
        assert status == 403 and json.loads(raw)["error"] == app_mod.NOT_HERE, name
    for mark in ("0", "", "no"):
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, _front(port, **{web.FRONT_HEADER: mark}))[0] == 403
    status, raw, _ = _call(port, "POST", "/api/users", {"name": "Eve", "password": "correct horse battery"}, _front(port))
    assert status == 403 and json.loads(raw)["error"] == app_mod.NO_SESSION_HERE
    # a front that set no mark but said where the browser was or how it came, as Caddy does unasked (a Caddyfile from
    # before the mark): not this machine's either, by liminal-libs' net under the mark
    unmarked = {k: v for k, v in _front(port).items() if k != web.FRONT_HEADER}
    for said in (unmarked, _here(port, **{"X-Forwarded-For": "198.51.100.7"}), _here(port, **{"X-Forwarded-Proto": "https"})):
        status, raw, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, said)
        assert status == 403 and json.loads(raw)["error"] == app_mod.NOT_HERE, said
        status, raw, _ = _call(port, "POST", "/api/users", {"name": "Eve", "password": "correct horse battery"}, said)
        assert status == 403 and json.loads(raw)["error"] == app_mod.NO_SESSION_HERE, said
    assert app.users.count() == 0 and app.sessions() == [] and app.users.secret_kept() is None and asked == []
    # another site's page, and a write without the app's own header, are refused by the frame behind the front as at the
    # machine. Asked of a route that answers the front's own page (a sign-out: 200), and by the frame's own words: on
    # the way in without a password every marked request is refused anyway, and these two lines could not fail
    assert _call(port, "POST", "/api/sign-out", headers=_front(port))[0] == 200
    cross = _call(port, "POST", "/api/sign-out", headers=_front(port, **{"Sec-Fetch-Site": "cross-site"}))
    assert cross[:2] == (403, b"forbidden: not from this app's pages")
    unwritten = {k: v for k, v in _front(port).items() if k != WRITE_HEADER}
    assert _call(port, "POST", "/api/sign-out", headers=unwritten)[:2] == (403, b"missing request header")
    # a program at the machine itself, without the mark: as it always was
    status, raw, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, _here(port))
    assert status == 200 and json.loads(raw)["admin"] is True and json.loads(raw)["passwordless"] is True
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "default"}, _here(port))[0] == 200
    assert _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"}, _here(port))[0] == 201
    # through the front a user signs in with their password, and once signed in adds one
    status, raw, _ = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"}, _front(port))
    assert status == 200
    session = {SESSION_HEADER: json.loads(raw)["token"]}
    assert _call(port, "POST", "/api/users", {"name": "Bob", "password": "another password"}, _front(port, **session))[0] == 201
    assert any("Ada signed in" in m for m in lines) and not any("correct horse battery" in m for m in lines)


def test_behind_the_https_front_the_session_cookie_is_secure(served):
    """The browser reached the front over https (X-Forwarded-Proto, which Caddy writes): the session cookie is Secure,
    set and cleared, so it travels over https alone. At the machine, over http, it is as it always was."""
    app, port, lines = served
    app.users.create("Ada", "correct horse battery")
    status, raw, r = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"}, _front(port))
    token = json.loads(raw)["token"]
    assert status == 200 and r.getheader("Set-Cookie") == f"liminal_login={token}; Path=/; HttpOnly; SameSite=Strict; Secure"
    status, _, r = _call(port, "POST", "/api/sign-out", headers=_front(port, Cookie=f"liminal_login={token}"))
    assert status == 200 and r.getheader("Set-Cookie") == "liminal_login=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Secure"
    status, raw, r = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"}, _here(port))
    assert status == 200 and r.getheader("Set-Cookie") == f"liminal_login={json.loads(raw)['token']}; Path=/; HttpOnly; SameSite=Strict"
    status, raw, r = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, _here(port))
    assert status == 200 and "Secure" not in r.getheader("Set-Cookie")
    # a front reached over plain http says so: no Secure, which its browser would not keep
    status, raw, r = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"},
                           _front(port, **{"X-Forwarded-Proto": "http"}))
    assert status == 200 and "Secure" not in r.getheader("Set-Cookie")
    # the same wrapper still says a store closed under a request as a session ended (0.17.2), behind the front too
    token = json.loads(raw)["token"]
    app._sessions[token].vault.close()  # what a sign-out on another thread does, after the request took its session
    status, raw, _ = _call(port, "GET", "/api/pairs", headers=_front(port, Cookie=f"liminal_login={token}"))
    assert status == 401 and "signed out while this was being asked" in json.loads(raw)["error"]


def test_the_containers_login_is_the_domains_of_the_host_its_front_answers_at(folder, monkeypatch, capsys):
    """compose.yaml ties the login to https://<LIMINAL_REMOTE_HOST> (LIMINAL_LOGIN_SCOPE over its file's scope, which is
    a domain's too). The login the container runs, read as it reads it (LIMINAL_LOGIN_CFG, LIMINAL_LOGIN_DIR), lets
    nobody in without a password and makes no account without a session even with no front's mark (a Caddyfile from
    before it) and no user yet; the first user is made inside the container (`liminal-login user add NAME`), in the very
    folder the server reads, and signs in with its password; a user signed in adds the next."""
    compose = (DOCKER / "compose.yaml").read_text(encoding="utf-8")
    said = re.search(r'^\s*LIMINAL_LOGIN_SCOPE:\s*"([^"]+)"\s*$', compose, re.M)
    assert said, "the login's scope is said where the recipe is set up"
    monkeypatch.setattr(Scope, "find", REAL_FIND)  # as the container reads its file
    monkeypatch.setenv("LIMINAL_LOGIN_CFG", str(DOCKER / "liminal-login.cfg"))
    monkeypatch.setenv("LIMINAL_LOGIN_SCOPE", interpolated(said.group(1), {"LIMINAL_REMOTE_HOST": "login.example.test"}))
    monkeypatch.setattr(app_mod, "mx_records", lambda domain: [])  # no mail record looked up: no sign-up by email
    args = cli.build_parser().parse_args(["serve", "--no-browser", "--port", "8795"])
    scope = cli._scope(args)
    assert (scope.kind, scope.domain, scope.title, scope.port) == ("domain", "login.example.test", "Liminal (remote)", 8795)
    # `serve` itself, as the container's command runs it: the login it makes is the one tried below (made by hand
    # alone, nothing failed when `serve` gave its login another scope, or none: its users in a folder `user add` never
    # wrote)
    ran: list = []
    monkeypatch.setattr(LoginApp, "serve", lambda self, port=None, open_browser=False, stop=None, until_quiet=None:
                        ran.append((self.scope.kind, self.scope.domain, self.dir, port)) or "url")
    assert cli.main(["serve", "--no-browser", "--port", "8795"]) == 0
    assert ran == [("domain", "login.example.test", folder / "login.example.test", 8795)]
    app = LoginApp(cli._root(args), log=lambda m: None, failure_delay=0, superclass=cli._superclass(args), scope=scope,
                   port=args.port)  # as `serve` makes it
    try:
        assert app.dir == folder / "login.example.test" and not app.signup_open()
        port = _port(app.start(0))
        for name in ("secret", "default"):
            assert _call(port, "POST", "/api/sign-in/secret", {"name": name}, _here(port))[0] == 403
        status, raw, _ = _call(port, "POST", "/api/users", {"name": "Eve", "password": "correct horse battery"}, _here(port))
        assert status == 403 and json.loads(raw)["error"] == app_mod.FIRST_AT_THE_MACHINE and app.users.count() == 0
        typed = iter(["correct horse battery"] * 2)
        monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
        assert cli.main(["user", "add", "Ada"]) == 0 and "user Ada created" in capsys.readouterr().out
        assert app.users.count() == 1  # the server's own users
        status, raw, _ = _call(port, "POST", "/api/sign-in", {"name": "ada@login.example.test", "password": "correct horse battery"},
                               _front(port))
        assert status == 200 and json.loads(raw)["user"]["name"] == "Ada"
        session = {SESSION_HEADER: json.loads(raw)["token"]}
        assert _call(port, "POST", "/api/users", {"name": "Bob", "password": "another password"}, _here(port))[0] == 401
        assert _call(port, "POST", "/api/users", {"name": "Bob", "password": "another password"}, _front(port, **session))[0] == 201
    finally:
        app.close()


def _composes_word(host: str = "login.example.test") -> dict:
    """What compose.yaml says in the login's own environment, read as text and filled in as compose fills it in for
    the host the deployer names (LIMINAL_REMOTE_HOST)."""
    compose = (DOCKER / "compose.yaml").read_text(encoding="utf-8")
    login = re.search(r"^  login:\n(.*?)^  front:", compose, re.S | re.M)
    assert login, "the login's service is read here"
    said = dict(re.findall(r'^      (LIMINAL_\w+):\s*"([^"]*)"\s*$', login.group(1), re.M))
    return {name: interpolated(value, {"LIMINAL_REMOTE_HOST": host}) for name, value in said.items()}


def _code(sent: list) -> str:
    """The six-digit code in the last message the stand-in mailer kept (the line of its own)."""
    return next(line.strip() for line in sent[-1][1].splitlines() if line.strip().isdigit() and len(line.strip()) == 6)


def _served_as_the_container_serves(monkeypatch, cfg, check, said: dict, records=("mx.login.example.test",)):
    """`liminal-login serve` as the container's command runs it (cli.main), on the login's file `cfg` (LIMINAL_LOGIN_CFG)
    with `said` in its environment (compose.yaml's word for the login, or a part of it). The login it makes is the one
    asked: `check(app, port, sent)` runs while it answers at a free port, before the command ends. The host's mail
    record is a stand-in (`records`) and so is the mailer: no name is looked up, no message leaves. Returns the
    domains whose mail record was asked for and the messages it would have sent (to, text)."""
    monkeypatch.setattr(Scope, "find", REAL_FIND)  # as the container reads its file
    monkeypatch.setenv("LIMINAL_LOGIN_CFG", str(cfg))
    for name in ("LIMINAL_LOGIN_SCOPE", "LIMINAL_LOGIN_SIGNUP"):
        monkeypatch.delenv(name, raising=False)
    for name, value in said.items():
        monkeypatch.setenv(name, value)
    asked: list = []
    sent: list = []
    monkeypatch.setattr(app_mod, "mx_records", lambda domain: asked.append(domain) or list(records))

    def send(self, to, subject, text):
        sent.append((to, text))
        return Sent(to, "mx.login.example.test", 25, 250, "2.0.0 OK queued as stand-in", "2026-11-25T21:00:00+00:00",
                    "<stand-in@login.example.test>")

    def serve(self, port=None, open_browser=False, stop=None, until_quiet=None):
        self.failure_delay = 0
        check(self, _port(self.start(0)), sent)
        return "url"

    monkeypatch.setattr(Mailer, "send", send)
    monkeypatch.setattr(LoginApp, "serve", serve)
    assert cli.main(["serve", "--no-browser", "--port", "8795"]) == 0
    return asked, sent


def _no_sign_up(address: str = "ada@login.example.test"):
    """A check for a login whose switch closes sign-up by email: the status says so, with how it is opened, and every
    step of a sign-up answers 503 with the same words, through the front and at the machine; nothing is counted, no
    sign-up waits, and the first user is still made at its machine."""
    steps = (("/api/signup", {"email": address}), ("/api/signup/resend", {"email": address}),
             ("/api/signup/verify", {"email": address, "code": "123456"}),
             ("/api/signup/complete", {"email": address, "token": "t", "name": "Ada", "password": "correct horse battery"}))

    def check(app, port, sent):
        assert (app.scope.kind, app.scope.domain, app.signup) == ("domain", "login.example.test", "closed")
        for sent_as in (_front(port), _here(port)):  # through the front, and at the machine
            status, raw, _ = _call(port, "GET", "/api/status", headers=sent_as)
            signup = json.loads(raw)["signup"]
            assert status == 200 and (signup["email"], signup["why"]) == (False, app_mod.SIGNUP_CLOSED_WHY)
            for path, body in steps:
                status, raw, _ = _call(port, "POST", path, body, sent_as)
                assert status == 503 and json.loads(raw)["error"] == app_mod.SIGNUP_CLOSED_WHY, path
        status, raw, _ = _call(port, "POST", "/api/users", {"name": "Eve", "password": "correct horse battery"}, _front(port))
        assert status == 403 and json.loads(raw)["error"] == app_mod.FIRST_AT_THE_MACHINE
        assert app.users.count() == 0 and app.users.signup(address) is None and len(app.throttle) == 0 and sent == []

    return check


def test_the_recipe_as_shipped_takes_no_sign_up_by_email_whatever_mail_record_its_host_has(folder, monkeypatch, capsys):
    """The last check of LOG-C1's fix (2026-11-25; the user: "Closed unless turned on"). Made a domain's so that it has
    no user without a password, the container's login took sign-ups by a mailed code as soon as its host had a mail
    record (MX), with nothing else set, and the code could be guessed: an account with no session and no mailbox. As
    shipped it takes none: docker/liminal-login.cfg says `signup = closed` and compose.yaml says closed too. Every
    step of a sign-up answers 503 with how it is opened, through the front and at the machine; no mail record is asked
    for and nothing is mailed. Either word closes it alone: the file's without compose's here, compose's over a file
    without the line in the test after the next."""
    said = _composes_word()
    assert said == {"LIMINAL_LOGIN_SCOPE": "https://login.example.test", "LIMINAL_LOGIN_SIGNUP": "closed"}
    assert "`signup = open` under [login] in its liminal-login.cfg opens it" in app_mod.SIGNUP_CLOSED_WHY
    for word in (said, {"LIMINAL_LOGIN_SCOPE": said["LIMINAL_LOGIN_SCOPE"]}):  # compose's word, then the file's alone
        asked, sent = _served_as_the_container_serves(monkeypatch, DOCKER / "liminal-login.cfg", _no_sign_up(), word)
        assert asked == [] and sent == [], word
        # the start-up line, which `docker compose logs login` shows, says it too
        assert "sign-up by email closed (`signup = open` in liminal-login.cfg opens it)" in capsys.readouterr().out


def test_the_files_own_line_opens_sign_up_in_the_recipe_and_it_still_needs_an_email_server(folder, tmp_path, monkeypatch):
    """A deployer turns sign-up on in the login's file: `signup = open` in docker/liminal-login.cfg, over compose.yaml's
    `closed`. Through the front a code is then mailed to an address at the host (a stand-in keeps the message), typed
    back, and the account made and signed in, as on any domain's login with an email server. A host with no mail
    record and no server named takes none still, and says that."""
    shipped = (DOCKER / "liminal-login.cfg").read_text(encoding="utf-8")
    assert shipped.count("\nsignup = closed\n") == 1
    cfg = tmp_path / "liminal-login.cfg"
    cfg.write_text(shipped.replace("\nsignup = closed\n", "\nsignup = open\n"), encoding="utf-8")
    said = _composes_word()
    assert said["LIMINAL_LOGIN_SIGNUP"] == "closed"  # the file's own line is over it
    address = "ada@login.example.test"

    def check(app, port, sent):
        assert (app.scope.domain, app.signup) == ("login.example.test", "open")
        signup = json.loads(_call(port, "GET", "/api/status", headers=_front(port))[1])["signup"]
        assert (signup["email"], signup["why"], signup["direct"]) == (True, "", True)
        status, raw, _ = _call(port, "POST", "/api/signup", {"email": "ada@elsewhere.test"}, _front(port))
        assert status == 400 and "login.example.test" in json.loads(raw)["error"] and sent == []  # addresses at the host alone
        assert _call(port, "POST", "/api/signup", {"email": address}, _front(port))[0] == 202
        status, raw, _ = _call(port, "POST", "/api/signup/verify", {"email": address, "code": _code(sent)}, _front(port))
        assert status == 200
        status, raw, r = _call(port, "POST", "/api/signup/complete", {"email": address, "token": json.loads(raw)["token"],
                                                                     "name": "Ada", "password": "correct horse battery"}, _front(port))
        assert status == 201 and json.loads(raw)["user"]["name"] == "Ada" and r.getheader("Set-Cookie").endswith("; Secure")
        assert app.users.count() == 1

    asked, sent = _served_as_the_container_serves(monkeypatch, cfg, check, said)
    assert asked == ["login.example.test"] and [to for to, _ in sent] == [address]

    def no_server(app, port, sent):
        signup = json.loads(_call(port, "GET", "/api/status", headers=_front(port))[1])["signup"]
        assert app.signup == "open" and signup["email"] is False and "none in its mail record (MX)" in signup["why"]
        status, raw, _ = _call(port, "POST", "/api/signup", {"email": "bo@login.example.test"}, _front(port))
        assert status == 503 and "no email server for login.example.test" in json.loads(raw)["error"]

    asked, sent = _served_as_the_container_serves(monkeypatch, cfg, no_server, said, records=())
    assert asked == ["login.example.test"] and sent == []


def test_a_copy_of_the_file_from_before_the_line_is_closed_by_composes_word_until_its_own_line_opens_it(folder, tmp_path, monkeypatch):
    """A container whose liminal-login.cfg is an older copy, without the `signup` line: the file as 0.19.0 shipped it
    (local, until compose.yaml's scope makes it the host's), and today's without the line. compose.yaml's own
    environment says closed (LIMINAL_LOGIN_SIGNUP, read by the command line alone and handed to the login `serve`
    makes), so on a host with a mail record it takes no sign-up either, through the front or at the machine, and says
    how it is opened. The line, written into that copy, opens it."""
    said = _composes_word()
    shipped = (DOCKER / "liminal-login.cfg").read_text(encoding="utf-8")
    copies = {"0.19.0's": "[login]\n; a remote login in Docker (compose.yaml): local to the container's /data, so no email; its "
                          "users made on its own page\n; (Sign up) or by its secret user, and reached from other logins as "
                          "name@<its domain>\nscope = file:///data\ntitle = Liminal (remote)\nport = 8795\n\n[mail]\n"
                          "; a local login sends no email\n",
              "today's without the line": shipped.replace("\nsignup = closed\n", "\n")}
    cfg = tmp_path / "liminal-login.cfg"
    for which, text in copies.items():
        cfg.write_text(text, encoding="utf-8")
        assert app_mod.signup_line(cfg) is None, which
        asked, sent = _served_as_the_container_serves(monkeypatch, cfg, _no_sign_up(), said)
        assert asked == [] and sent == [], which
        cfg.write_text(text.replace("\nport = 8795\n", "\nport = 8795\nsignup = open\n"), encoding="utf-8")

        def opened(app, port, sent):
            signup = json.loads(_call(port, "GET", "/api/status", headers=_front(port))[1])["signup"]
            assert (app.scope.domain, app.signup, signup["email"], signup["why"]) == ("login.example.test", "open", True, "")

        asked, sent = _served_as_the_container_serves(monkeypatch, cfg, opened, said)
        assert asked == ["login.example.test"] and sent == [], which


def test_a_scope_said_to_the_command_line_ties_its_login_there_and_is_never_written_back(folder, tmp_path, monkeypatch, capsys):
    """LIMINAL_LOGIN_SCOPE (cli.scoped): the scope of the file found or named, the rest of the file kept; every command
    of the command line reads it so (`serve` and `user` in the same folder), and `mail setup`, which writes the file
    back, writes the file's own scope."""
    cfg = tmp_path / "liminal-login.cfg"
    cfg.write_text("[login]\nscope = https://localhost\ntitle = Somewhere\nport = 8811\n\n[remotes]\n"
                   "other.test = https://login.other.test:8443\n", encoding="utf-8")
    own = Scope.read(cfg)
    assert scoped(own, env={}) is own and scoped(None, env={}) is None
    told = scoped(own, env={"LIMINAL_LOGIN_SCOPE": " https://Login.Example.Test/ "})
    assert (told.url, told.domain, told.title, told.port, told.path) == ("https://login.example.test", "login.example.test",
                                                                         "Somewhere", 8811, cfg)
    assert told.remotes == {"other.test": "https://login.other.test:8443"} and told.admin_address == "admin@login.example.test"
    assert scoped(None, env={"LIMINAL_LOGIN_SCOPE": "login.example.test"}).url == "https://login.example.test"
    assert scoped(own, env={"LIMINAL_LOGIN_SCOPE": tmp_path.as_uri()}).kind == "local"
    with pytest.raises(ValueError, match="LIMINAL_LOGIN_SCOPE"):
        scoped(own, env={"LIMINAL_LOGIN_SCOPE": "https:///"})
    said = {"LIMINAL_LOGIN_SCOPE": "https://login.example.test"}
    # an admin of the file's own choosing is kept, and must be at the domain said; its domain's default is the new one's
    chosen = scoped(Scope.parse("[login]\nscope = https://example.test\nadmin = boss@login.example.test\n"), env=said)
    assert chosen.admin_address == "boss@login.example.test"
    with pytest.raises(ValueError, match="admin"):
        scoped(Scope.parse("[login]\nscope = https://example.test\nadmin = boss@mail.example.test\n"), env=said)
    default = scoped(Scope.parse("[login]\nscope = https://localhost\nadmin = admin@localhost\n"), env=said)
    assert default.admin_address == "admin@login.example.test"
    monkeypatch.setenv("LIMINAL_LOGIN_SCOPE", "https://login.example.test")
    for command in (["--cfg", str(cfg), "serve", "--no-browser"], ["--cfg", str(cfg), "status", "--port", "1"],
                    ["--cfg", str(cfg), "user", "list"]):
        args = cli.build_parser().parse_args(command)
        assert cli._scope(args).domain == "login.example.test" and cli._dir(args) == folder / "login.example.test", command
    assert cli._scope(cli.build_parser().parse_args(["--cfg", str(cfg), "status"]), told=False).domain == "localhost"
    assert cli.main(["--cfg", str(cfg), "user", "list"]) == 0
    out = capsys.readouterr().out  # a domain's login: no first user from the page's first visit any more
    assert "no users yet: `liminal-login user add NAME`" in out and "only by a mailed code" in out and "first visit" not in out
    assert (folder / "login.example.test" / "users.db").is_file() and not (folder / "localhost").exists()
    monkeypatch.setattr(cli.secrets, "put", lambda name, value: pytest.fail("no password typed here"))
    monkeypatch.setattr(cli.secrets, "remove", lambda name: False)
    answers = iter(["direct", "login@login.example.test"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli.main(["--cfg", str(cfg), "mail", "setup"]) == 0 and f"kept in {cfg}" in capsys.readouterr().out
    written = Scope.read(cfg)
    assert written.url == "https://localhost" and written.mail["host"] == "direct" and written.title == "Somewhere"
    assert scoped(written, env=said).admin_address == "admin@login.example.test"  # as the next start reads it


def test_a_login_made_in_code_never_reads_the_scope_said_to_the_command_line(folder, tmp_path, monkeypatch):
    """The user, 2026-11-24: LIMINAL_LOGIN_SCOPE is the login's own command line's (cli._scope: `serve`, `user`), never
    read by a login made in code. Read by every login, as it first was, a variable left set on a machine turned its
    logins into a domain's: other users, in another folder, and nobody in without a password. A login made in code is
    tied to the scope it is given, else to its file, else it is local."""
    monkeypatch.setenv("LIMINAL_LOGIN_SCOPE", "https://login.example.test")
    cfg = tmp_path / "liminal-login.cfg"
    cfg.write_text(f"[login]\nscope = {(tmp_path / 'project').as_uri()}\ntitle = Somewhere\n", encoding="utf-8")
    seen: dict = {}

    def made(how: str, *args, **kw) -> None:
        app = LoginApp(*args, log=lambda m: None, failure_delay=0, **kw)
        try:
            seen[how] = (app.scope.kind, app.scope.domain, app.scope.path, app.dir)
        finally:
            app.close()

    made("a scope given", folder / "given", scope=Scope.for_domain("example.test"))
    made("a folder given", folder / "own")
    made("neither, and no file found")  # conftest: no file; its folder is LIMINAL_LOGIN_DIR
    monkeypatch.setattr(Scope, "find", REAL_FIND)  # the file every app reads
    monkeypatch.setenv("LIMINAL_LOGIN_CFG", str(cfg))
    made("neither, and its file found")
    assert seen == {"a scope given": ("domain", "example.test", None, folder / "given" / "example.test"),
                    "a folder given": ("local", "", None, folder / "own"),
                    "neither, and no file found": ("local", "", None, folder),
                    "neither, and its file found": ("local", "", cfg, folder)}
    # the command line, asked at the same moment, does read it
    assert cli._scope(cli.build_parser().parse_args(["serve"])).domain == "login.example.test"


def test_the_login_an_app_holds_never_reads_it_either(folder, monkeypatch):
    """What the rule is for: the platform and the charts hold their login as an object, made with neither a scope nor a
    folder (liminal_libs.apps.App.make_login). With LIMINAL_LOGIN_SCOPE left set on their machine it is still their own
    local login: its users in its own folder, its secret user in by its name."""
    monkeypatch.setenv("LIMINAL_LOGIN_SCOPE", "https://login.example.test")

    class Holder(App):
        NAME, TITLE, ICON, PORT, LOGIN = "platform", "Liminal Platform", "chip", 8775, True

    app = Holder(log=lambda m: None)
    port = _port(app.start(0))
    try:
        status, raw, _ = _call(port, "GET", "/login/api/status")
        st = json.loads(raw)
        assert status == 200 and (st["scope"]["kind"], st["scope"]["domain"], st["for"]) == ("local", "", "platform")
        assert app.login_object().dir == folder / "platform" and not (folder / "login.example.test").exists()
        status, raw, _ = _call(port, "POST", "/login/api/sign-in/secret", {"name": "secret"}, _here(port))
        assert status == 200 and json.loads(raw)["admin"] is True
    finally:
        app.stop()


def test_the_page_makes_no_account_on_a_domains_login_without_email(served):
    """A domain's login without an email server takes no account from the page, not even its first (the page drew the
    form, and the login made the account): Sign up says how the first is made; a local login's page is as it was. No
    JavaScript runs here: what the page is drawn with."""
    _app, port, _lines = served
    page = _call(port, "GET", "/login.js")[1].decode("utf-8")
    sign_up = page[page.index("function signUp("):page.index("function createForm(")]
    assert "if (st.scope && st.scope.kind === 'domain') return entryForm(st, (st.signup && st.signup.why)" in sign_up
    assert "st.users > 0" not in sign_up and "Email sending is not set up here" not in page
    assert "This login is local: it sends no email, so no code is needed." in page


def test_a_login_may_trust_a_remote_front_s_own_authority(folder, monkeypatch, tmp_path):
    """LIMINAL_LOGIN_CA: a certificate authority (PEM) trusted for remote logins besides the system's (the front's own,
    copied out of its container); one that cannot be read is said, never passed over."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "a test front's authority")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    pem = tmp_path / "front-root.crt"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setenv(app_mod.CA_VAR, str(pem))
    context = app_mod.remote_tls()
    assert any(c.get("subject") and "a test front's authority" in str(c["subject"]) for c in context.get_ca_certs())
    LoginApp(folder / "trusting", log=lambda m: None, failure_delay=0).close()
    monkeypatch.setenv(app_mod.CA_VAR, str(tmp_path / "missing.crt"))
    with pytest.raises(ValueError, match="LIMINAL_LOGIN_CA"):
        app_mod.remote_tls()
