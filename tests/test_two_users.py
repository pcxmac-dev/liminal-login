"""Two users signed in at once (0.17.0; the user, 2026-11-15: "create a second 'default' user with no login, to test
multiple logins and see if the code holds"; "let the secret user be the admin"): `default` comes in without a password
beside the secret user, each session its own user with its own store and pairs, the secret user alone the login's
admin; on the login's own page and under an app that holds the login as an object. Every store in the test's own
folder, the app on a free port in a thread, no process started."""
from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection

from liminal_libs import web
from liminal_libs.apps import SESSION_HEADER, App, Scope

from liminal_login.app import NOT_PASSWORDLESS, LoginApp
from liminal_login.users import DEFAULT_NAME, PASSWORDLESS, SECRET_KEYS


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


def _call(port, method, path, body=None, token=None, cookie=None):
    """One request: the session by its token (a client's header) or by a browser's cookie."""
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    h = {"Content-Type": "application/json"} if body is not None else {}
    if method != "GET":
        h[web.WRITE_HEADER] = "1"
    if token:
        h[SESSION_HEADER] = token
    if cookie:
        h["Cookie"] = cookie
    try:
        conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=h)
        r = conn.getresponse()
        raw = r.read()
    finally:
        conn.close()
    try:
        return r.status, json.loads(raw), r
    except ValueError:
        return r.status, raw, r


def _names(port, token) -> list[str]:
    return sorted(p["name"] for p in _call(port, "GET", "/api/pairs", token=token)[1]["pairs"])


def test_the_default_user_comes_in_without_a_password_beside_the_secret_user(served):
    app, port, lines = served
    assert DEFAULT_NAME == "default"
    status, secret, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})
    assert status == 200 and secret["user"]["name"] == "secret" and secret["passwordless"] is True and secret["admin"] is True
    status, default, r = _call(port, "POST", "/api/sign-in/secret", {"name": " Default "})  # made the first time
    assert status == 200 and default["user"]["name"] == "default" and default["passwordless"] is True and default["admin"] is False
    assert r.getheader("Set-Cookie").startswith(f"liminal_login={default['token']}")
    assert default["token"] != secret["token"] and app.users.count() == 2 and app.sessions() == ["default", "secret"]
    s, d = secret["token"], default["token"]
    # each session is its own user: who they are, where their store is, whether they are the admin
    me_s, me_d = _call(port, "GET", "/api/me", token=s)[1], _call(port, "GET", "/api/me", token=d)[1]
    assert (me_s["name"], me_s["admin"], me_s["passwordless"]) == ("secret", True, True)
    assert (me_d["name"], me_d["admin"], me_d["passwordless"]) == ("default", False, True)
    assert me_s["store"]["file"] != me_d["store"]["file"] and me_s["store"]["vaultFingerprint"] != me_d["store"]["vaultFingerprint"]
    st_s, st_d = _call(port, "GET", "/api/status", token=s)[1], _call(port, "GET", "/api/status", token=d)[1]
    assert (st_s["name"], st_s["admin"]) == ("secret", True) and (st_d["name"], st_d["admin"]) == ("default", False)
    nobody = _call(port, "GET", "/api/status")[1]
    assert nobody["signedIn"] is False and nobody["admin"] is False and nobody["users"] == 2
    # a pair of the same name holds a value each, and neither sees the other's
    assert _call(port, "PUT", "/api/pairs/acme-api-key", {"value": "the-secret-users-value", "kind": "key"}, token=s)[0] == 200
    assert _call(port, "PUT", "/api/pairs/acme-api-key", {"value": "the-default-users-value", "kind": "key"}, token=d)[0] == 200
    assert _call(port, "PUT", "/api/pairs/only-defaults", {"value": "a detail", "kind": "detail"}, token=d)[0] == 200
    assert _call(port, "GET", "/api/pairs/acme-api-key", token=s)[1]["value"] == "the-secret-users-value"
    assert _call(port, "GET", "/api/pairs/acme-api-key", token=d)[1]["value"] == "the-default-users-value"
    assert _names(port, s) == ["acme-api-key"] and _names(port, d) == ["acme-api-key", "only-defaults"]
    assert _call(port, "GET", "/api/pairs/only-defaults", token=s)[0] == 404
    assert _call(port, "GET", "/api/me", token=s)[1]["store"]["pairs"] == 1 and _call(port, "GET", "/api/me", token=d)[1]["store"]["pairs"] == 2
    # made once each, however often they come in
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "DEFAULT"})[0] == 200 and app.users.count() == 2
    # neither password is ever changed: each is a key the login keeps, in its database
    kept = app.users.passwordless_kept()
    assert list(kept) == ["secret", "default"] and len(kept["default"]) >= 24 and kept["default"] != kept["secret"]
    assert app.users.setting(PASSWORDLESS + "default") == kept["default"] and app.users.secret_kept() == ("secret", kept["secret"])
    for name, token in (("secret", s), ("default", d)):
        status, data, _ = _call(port, "PUT", "/api/me/password", {"old": kept[name], "new": "a brand new one"}, token=token)
        assert status == 403 and data["error"].endswith("cannot be changed")
    keyed = _call(port, "POST", "/api/sign-in", {"name": "default", "password": kept["default"]})[1]  # in with the key itself
    assert keyed["admin"] is False and _call(port, "GET", "/api/me", token=keyed["token"])[1]["passwordless"] is False
    assert _call(port, "PUT", "/api/me/password", {"old": kept["default"], "new": "a brand new one"}, token=keyed["token"])[0] == 403
    assert app.users.verify("default", kept["default"]) is not None and app.users.verify("default", "a brand new one") is None
    assert _call(port, "POST", "/api/sign-in", {"name": "secret", "password": kept["secret"]})[1]["admin"] is True  # however it came in
    # one signing out leaves the other in; back in, its store is as it left it
    assert _call(port, "POST", "/api/sign-out", token=d)[0] == 200 and _call(port, "GET", "/api/me", token=d)[0] == 401
    assert _call(port, "GET", "/api/me", token=s)[1]["name"] == "secret" and _names(port, s) == ["acme-api-key"]
    again = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    assert _call(port, "GET", "/api/pairs/acme-api-key", token=again)[1]["value"] == "the-default-users-value"
    # nobody else comes in without a password; the log says who was made and never a password or a value
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "ada"})
    assert status == 400 and data["error"] == NOT_PASSWORDLESS
    assert sum("the default user was made" in m for m in lines) == 1 and sum("the secret user was made" in m for m in lines) == 1
    assert any("default signed in (the default user, no password)" in m for m in lines)
    assert any("secret signed in (the secret user, no password)" in m for m in lines)
    said = "\n".join(lines)
    assert not any(v in said for v in (*kept.values(), "the-secret-users-value", "the-default-users-value"))
    # the page: the same way in for both, and what it says of whoever came in without a password
    page = (LoginApp.STATIC / "login.js").read_text(encoding="utf-8")
    assert "${me.admin ? 'The secret user' : 'This user'} comes in without a password" in page
    assert "${me.admin ? \"this login's admin · \" : ''}" in page
    assert "This user's password is a key the login keeps: it is never typed and cannot be changed." in page
    assert "'default'" not in page and "=== 'secret'" not in page  # which names come in so stays the login's to say


def test_many_sign_ins_at_the_same_moment_make_each_user_once_and_cross_no_session(served):
    app, port, _ = served
    names = ["secret", "default"] * 5
    out: list = [None] * len(names)
    together = threading.Barrier(len(names))

    def come_in(i: int) -> None:
        together.wait(timeout=20)
        status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": names[i]})
        if status != 200:
            out[i] = (status, data)
            return
        token = data["token"]
        _call(port, "PUT", f"/api/pairs/mine-{i}", {"value": f"value-{i}", "kind": "detail"}, token=token)
        me = _call(port, "GET", "/api/me", token=token)[1]
        out[i] = (200, me["name"], me["admin"], _call(port, "GET", f"/api/pairs/mine-{i}", token=token)[1].get("value"))

    threads = [threading.Thread(target=come_in, args=(i,)) for i in range(len(names))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert out == [(200, n, n == "secret", f"value-{i}") for i, n in enumerate(names)]
    assert app.users.count() == 2 and app.sessions() == ["default", "secret"] and len(app._sessions) == len(names)
    assert list(app.users.passwordless_kept()) == ["secret", "default"]
    # what each wrote is in its own user's store, whichever of that user's sessions asks
    secret = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["token"]
    default = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    assert _names(port, secret) == sorted(f"mine-{i}" for i, n in enumerate(names) if n == "secret")
    assert _names(port, default) == sorted(f"mine-{i}" for i, n in enumerate(names) if n == "default")


def test_a_default_with_a_password_of_their_own_is_never_let_in_without_it(folder):
    from conftest import FakeMailer

    own = LoginApp(folder / "own", log=lambda m: None, failure_delay=0)
    try:
        own.users.create("Default", "a real password")
        port = _port(own.start(0))
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[0] == 401
        assert own.users.passwordless_kept() == {} and not own.users.setting(PASSWORDLESS + "default")
        status, data, _ = _call(port, "POST", "/api/sign-in", {"name": "default", "password": "a real password"})
        assert status == 200 and data["user"]["name"] == "Default" and data["admin"] is False
        assert _call(port, "GET", "/api/me", token=data["token"])[1]["passwordless"] is False
        change = {"old": "a real password", "new": "another real password"}  # theirs to change, as anyone's
        assert _call(port, "PUT", "/api/me/password", change, token=data["token"])[0] == 200
        assert own.users.count() == 1
    finally:
        own.close()
    dom = LoginApp(folder / "dom", log=lambda m: None, failure_delay=0, mailer=FakeMailer(configured=False),
                   scope=Scope.for_domain("example.test"))
    try:  # a domain's login: nobody without a password, `default` no more than the secret user
        assert _call(_port(dom.start(0)), "POST", "/api/sign-in/secret", {"name": "default"})[0] == 403 and dom.users.count() == 0
    finally:
        dom.close()


def test_any_name_the_database_keeps_a_password_for_comes_in_the_same_way(served):
    app, port, _ = served
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "guest"})[0] == 400  # not made by asking: only `default` is
    assert app.users.count() == 0
    name, password = app.users.make_passwordless("Guest")
    assert name == "Guest" and app.users.make_passwordless("guest") == ("Guest", password)  # made once, its name as made
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "GUEST"})
    assert status == 200 and data["user"]["name"] == "Guest" and data["passwordless"] is True and data["admin"] is False
    assert list(app.users.passwordless_kept()) == ["Guest"] and app.users.secret_kept() is None  # no secret user made by it
    assert _call(port, "PUT", "/api/me/password", {"old": password, "new": "a brand new one"}, token=data["token"])[0] == 403
    # the secret user, made after: first among those kept, and the one admin
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["admin"] is True
    assert list(app.users.passwordless_kept()) == ["secret", "Guest"]
    # a secret user under another name is still the admin; `secret` is then nobody's way in
    app.users.set_setting("secret_user", "Guest")
    app.users.set_setting("secret_password", password)
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "guest"})
    assert status == 200 and data["admin"] is True and list(app.users.passwordless_kept()) == ["Guest"]
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[0] == 400


def test_two_browsers_signed_in_to_an_app_that_holds_the_login(folder, tmp_path, monkeypatch):
    """The login an app holds as an object (liminal-libs App.login_object): two browsers at the app's /login/, one the
    secret user and one `default`. The app tells them apart by their cookies: each sees the app's page, each its own
    user at /login/api/me, and one signing out sends only that browser back to the sign-in."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "index.html").write_text("<html>the platform's page</html>", encoding="utf-8")

    class Holder(App):
        NAME, TITLE, ICON, PORT = "platform", "Liminal Platform", "chip", 8775
        LOGIN, STATIC = True, pages

    monkeypatch.setattr(Scope, "find", classmethod(lambda cls, start=None, env=None: None))  # no login file here
    app = Holder(log=lambda m: None)
    port = int(app.start(0).rstrip("/").rsplit(":", 1)[1])
    try:
        assert b'id="signinFrame"' in _call(port, "GET", "/")[1]  # nobody in: the sign-in
        cookies = {}
        for name in ("secret", "default"):
            status, data, r = _call(port, "POST", "/login/api/sign-in/secret", {"name": name})
            assert status == 200 and data["user"]["name"] == name and data["admin"] is (name == "secret")
            cookies[name] = r.getheader("Set-Cookie").split(";", 1)[0]
            assert cookies[name] == f"liminal_login_platform={data['token']}"
        login = app.login_object()
        assert login.users.count() == 2 and login.sessions() == ["default", "secret"] and login.superclass.app is app
        assert (folder / "platform" / "users.db").exists()  # the platform's own users, in its folder
        for name, cookie in cookies.items():
            assert b"the platform's page" in _call(port, "GET", "/", cookie=cookie)[1]  # signed in: the app's page
            me = _call(port, "GET", "/login/api/me", cookie=cookie)[1]
            assert (me["name"], me["admin"], me["for"]) == (name, name == "secret", "platform")
            assert _call(port, "PUT", "/login/api/pairs/acme-api-key", {"value": f"{name}-value", "kind": "key"}, cookie=cookie)[0] == 200
        for name, cookie in cookies.items():
            assert _call(port, "GET", "/login/api/pairs/acme-api-key", cookie=cookie)[1]["value"] == f"{name}-value"
        # one signs out: only that browser goes back to the sign-in
        assert _call(port, "POST", "/login/api/sign-out", cookie=cookies["default"])[0] == 200
        assert b'id="signinFrame"' in _call(port, "GET", "/", cookie=cookies["default"])[1]  # that browser: the sign-in again
        assert b"the platform's page" in _call(port, "GET", "/", cookie=cookies["secret"])[1]  # the other: still in
        assert _call(port, "GET", "/login/api/me", cookie=cookies["secret"])[1]["name"] == "secret" and login.sessions() == ["secret"]
    finally:
        app.stop()


class _FailsOnce:
    """The users' connection, but the write that keeps one of these passwords fails once (a disk full, the process
    stopped there): everything else passes through."""

    def __init__(self, con, keys):
        self._con, self.keys, self.failed = con, set(keys), []

    def execute(self, sql, params=()):
        if "INSERT INTO settings" in sql and params and params[0] in self.keys and params[0] not in self.failed:
            self.failed.append(params[0])
            raise OSError("the disk is full (a stand-in)")
        return self._con.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._con, name)


def test_a_first_sign_in_cut_short_never_locks_the_secret_or_default_user_out(served):
    """The review of 2026-11-21, item 26 (19): the user's row was committed, then its password kept with commits of its
    own; a failure between them left a user whose password nobody had, refused at every sign-in without one for good.
    Now it is all or nothing: the next sign-in makes the user as if for the first time."""
    app, port, lines = served
    real = app.users._con
    app.users._con = _FailsOnce(real, {SECRET_KEYS[1], PASSWORDLESS + "default"})
    try:
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[0] != 200
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[0] != 200
        assert len(app.users._con.failed) == 2
    finally:
        app.users._con = real
    for name in ("secret", "default"):
        status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": name})
        assert status == 200 and data["user"]["name"] == name and data["passwordless"] is True
    assert app.users.count() == 2 and sorted(app.users.passwordless_kept()) == ["default", "secret"]


def test_a_secret_user_moved_off_its_legacy_password_keeps_its_pairs_when_cut_short(served):
    """The same (19), on the way a secret user made with 0.14.0's password moves onto a kept one: the new password was
    written, then kept apart; cut short between them, the user's pairs were sealed under a password nobody had."""
    app, port, lines = served
    from liminal_login.app import LEGACY_SECRET_PASSWORDS

    app.users.create("secret", LEGACY_SECRET_PASSWORDS[0])
    token = _call(port, "POST", "/api/sign-in", {"name": "secret", "password": LEGACY_SECRET_PASSWORDS[0]})[1]["token"]
    assert _call(port, "PUT", "/api/pairs/acme-api-key", {"value": "kept from before", "kind": "key"}, token=token)[0] == 200
    _call(port, "POST", "/api/sign-out", token=token)
    real = app.users._con
    app.users._con = _FailsOnce(real, {SECRET_KEYS[1]})
    try:
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[0] != 200
    finally:
        app.users._con = real
    assert app.users.verify("secret", LEGACY_SECRET_PASSWORDS[0]) is not None  # undone: still on its old password
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})
    assert status == 200 and data["user"]["name"] == "secret"
    assert _call(port, "GET", "/api/pairs/acme-api-key", token=data["token"])[1]["value"] == "kept from before"


def test_a_session_left_without_a_sign_out_is_closed_without_its_own_token(served, monkeypatch):
    """The review of 2026-11-21, item 26 (20): a session idle too long was ended only when its own token came back, so
    one left without a sign-out kept its store open and its key in memory for the process's life. Now any request
    looking at a session, and any sign-in, ends every idle one."""
    app, port, lines = served
    monkeypatch.setenv("LIMINAL_LOGIN_SESSION_MINUTES", "1")
    first = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["token"]
    second = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    with app._lock:
        left = app._sessions[first]
        left.last = time.monotonic() - 120
    assert _call(port, "GET", "/api/me", token=second)[1]["name"] == "default"  # any request with the other token
    assert first not in app._sessions and app.sessions() == ["default"]
    assert left.vault._key is None  # its store closed, its key forgotten
    assert any("secret's session ended (idle)" in m for m in lines)
    # a sign-in ends them too
    with app._lock:
        kept = app._sessions[second]
        kept.last = time.monotonic() - 120
    third = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["token"]
    assert second not in app._sessions and kept.vault._key is None and list(app._sessions) == [third]
