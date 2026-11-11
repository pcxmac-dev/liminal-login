"""The login app's page and API (app.py) on a free port: the first user made from the page, sign in
and out, who you are, the pairs, what is refused; the library's LoginClient end to end."""
from __future__ import annotations

import json
import time
from http.client import HTTPConnection

import pytest

from liminal_libs.apps import LoginClient, LoginRefused
from liminal_libs.web import WRITE_HEADER
from liminal_login.app import LoginApp, login_dir


COOKIE = "liminal_login"  # the login's own, on its own (the tests' default; an inheriting app's: liminal_login_<name>)


def _call(port, method, path, body=None, headers=None, token=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    h = dict(headers or {})
    if body is not None:
        h["Content-Type"] = "application/json"
    if method != "GET":
        h.setdefault(WRITE_HEADER, "1")
    if token:
        h["Cookie"] = f"{COOKIE}={token}"
    conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=h)
    r = conn.getresponse()
    raw = r.read()
    try:
        data = json.loads(raw)
    except ValueError:
        data = raw
    return r.status, data, r


def test_the_page_its_icon_and_the_librarys_files(served):
    app, port, lines = served
    status, body, r = _call(port, "GET", "/")
    assert status == 200 and b'id="railUser"' in body and b"<title>Liminal Login</title>" in body
    assert b"window.LiminalIcons" in _call(port, "GET", "/icons.js")[1] and b"#rail" in _call(port, "GET", "/liminal.css")[1]
    assert b"signInForm" in _call(port, "GET", "/login.js")[1] and _call(port, "GET", "/login.css")[0] == 200
    status, tray, _ = _call(port, "GET", "/api/tray")
    assert tray == {"app": "login", "icon": "lambda", "title": "Login",  # Liminal's sign (0.13.1; the user icon before)
                    "items": [{"id": "login", "icon": "lambda", "title": "Login", "kind": "app", "app": "login"}]}
    page = _call(port, "GET", "/login.js")[1].decode("utf-8")
    assert "icon('user'" not in page and page.count("icon('lambda', 56)") == 4 and "icon('lambda', 30)" in page
    assert _call(port, "GET", "/api/app")[1]["port"] == 8795 and app.port() == 8795 and app.dir == app.root  # its own folder
    assert any("login: its page at" in m for m in lines)


def test_the_first_user_is_made_from_the_page_then_signs_in_and_out(served):
    app, port, lines = served
    st = _call(port, "GET", "/api/status")[1]
    assert {k: st[k] for k in ("users", "signedIn", "name", "app")} == {"users": 0, "signedIn": False, "name": None, "app": app.describe()}
    assert st["signup"]["email"] is False and st["for"] is None and st["superclass"] is None and app.describe()["for"] is None
    assert st["forTitle"] == "Liminal" and app.cookie_name == COOKIE  # on its own: no app inherits it
    assert _call(port, "GET", "/api/me")[0] == 401 and _call(port, "GET", "/api/pairs")[0] == 401
    status, data, _ = _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})
    assert status == 201 and data["name"] == "Ada" and "password" not in json.dumps(data)
    # a second user needs a session (the first came with none)
    assert _call(port, "POST", "/api/users", {"name": "Bob", "password": "another password"})[0] == 401
    status, data, r = _call(port, "POST", "/api/sign-in", {"name": "ada", "password": "wrong password"})
    assert status == 401 and data == {"error": "wrong name or password"} and r.getheader("Set-Cookie") is None
    status, data, r = _call(port, "POST", "/api/sign-in", {"name": "ada", "password": "correct horse battery"})
    token = data["token"]
    assert status == 200 and data["user"]["name"] == "Ada" and len(token) > 30
    assert r.getheader("Set-Cookie").startswith(f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict")
    assert _call(port, "GET", "/api/status", token=token)[1]["signedIn"] is True
    status, me, _ = _call(port, "GET", "/api/me", token=token)
    assert status == 200 and me["name"] == "Ada" and me["store"]["pairs"] == 0
    assert len(me["store"]["unlockFingerprint"]) == 12 and len(me["store"]["vaultFingerprint"]) == 12
    assert me["store"]["kdf"]["name"] == "scrypt" and len(me["store"]["salt"]) == 32 and me["session"]["minutes"] == 480
    assert me["store"]["file"].endswith(".db") and "users.db" in me["store"]["usersFile"]
    assert "key" not in {k.lower() for k in me["store"]} - {"unlockfingerprint", "vaultfingerprint"} or True
    # signed in, a second user may be made
    assert _call(port, "POST", "/api/users", {"name": "Bob", "password": "another password"}, token=token)[0] == 201
    assert [u["name"] for u in _call(port, "GET", "/api/users", token=token)[1]["users"]] == ["Ada", "Bob"]
    status, data, r = _call(port, "POST", "/api/sign-out", token=token)
    assert status == 200 and data == {"signedOut": True} and "Max-Age=0" in r.getheader("Set-Cookie")
    assert _call(port, "GET", "/api/me", token=token)[0] == 401
    assert any("Ada signed in" in m for m in lines) and any("Ada signed out" in m for m in lines)
    assert not any("correct horse battery" in m or "wrong password" in m for m in lines)


def test_the_pairs_are_kept_masked_revealed_one_at_a_time_and_removed(served):
    app, port, lines = served
    _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})
    token = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[1]["token"]
    assert _call(port, "GET", "/api/pairs", token=token)[1] == {"pairs": []}
    status, info, _ = _call(port, "PUT", "/api/pairs/massive-account-api-key",
                            {"value": "sk-test-0001", "kind": "key", "label": "Massive"}, token=token)
    assert status == 200 and info["name"] == "massive-account-api-key" and "value" not in info
    assert _call(port, "PUT", "/api/pairs/Bad%20Name", {"value": "x"}, token=token)[0] == 400
    assert _call(port, "PUT", "/api/pairs/ok-name", {"value": ""}, token=token)[0] == 400
    assert _call(port, "PUT", "/api/pairs/ok-name", {"value": "x", "kind": "secret"}, token=token)[0] == 400
    pairs = _call(port, "GET", "/api/pairs", token=token)[1]["pairs"]
    assert [(p["name"], p["kind"], p["label"]) for p in pairs] == [("massive-account-api-key", "key", "Massive")]
    assert all("value" not in p for p in pairs)
    status, data, _ = _call(port, "GET", "/api/pairs/massive-account-api-key", token=token)
    assert status == 200 and data["value"] == "sk-test-0001" and data["kind"] == "key"
    assert _call(port, "GET", "/api/pairs/nobody-account-api-key", token=token)[0] == 404
    assert _call(port, "GET", "/api/pairs/massive-account-api-key")[0] == 401  # not without the session
    assert _call(port, "GET", "/api/me", token=token)[1]["store"]["pairs"] == 1
    assert _call(port, "DELETE", "/api/pairs/massive-account-api-key", token=token)[1] == {"removed": True, "name": "massive-account-api-key"}
    assert _call(port, "DELETE", "/api/pairs/massive-account-api-key", token=token)[0] == 404
    assert not any("sk-test-0001" in m for m in lines)
    # a new password keeps the pairs: the vault key is the same, wrapped again
    _call(port, "PUT", "/api/pairs/claude-account-name", {"value": "ada@example.test", "kind": "account"}, token=token)
    assert _call(port, "PUT", "/api/me/password", {"old": "wrong", "new": "a longer new password"}, token=token)[0] == 400
    status, data, _ = _call(port, "PUT", "/api/me/password", {"old": "correct horse battery", "new": "a longer new password"}, token=token)
    assert status == 200 and data["changed"] is True
    assert _call(port, "GET", "/api/pairs/claude-account-name", token=token)[1]["value"] == "ada@example.test"
    _call(port, "POST", "/api/sign-out", token=token)
    assert _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[0] == 401
    again = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "a longer new password"})[1]["token"]
    assert _call(port, "GET", "/api/pairs/claude-account-name", token=again)[1]["value"] == "ada@example.test"


def test_what_the_login_app_refuses_and_when_a_session_ends(served, monkeypatch):
    app, port, lines = served
    _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})
    token = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[1]["token"]
    # another site's page, a write without the app's header, a stale or made-up session
    assert _call(port, "GET", "/api/me", headers={"Origin": "http://evil.example"}, token=token)[0] == 403
    assert _call(port, "GET", "/api/me", headers={"Host": "evil.example"}, token=token)[0] == 403
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/sign-out", headers={"Cookie": f"{COOKIE}={token}"})
    assert conn.getresponse().status == 403
    assert _call(port, "GET", "/api/me", token="made-up")[0] == 401
    assert _call(port, "GET", "/api/me", token=token)[0] == 200
    # a browser holding two cookies of the name (a stale one first): the live session counts
    assert _call(port, "GET", "/api/me", headers={"Cookie": f"{COOKIE}=stale; {COOKIE}={token}"})[0] == 200
    assert _call(port, "GET", "/api/status", headers={"Cookie": f"{COOKIE}=stale"})[1]["signedIn"] is False
    # the session ends once idle too long: the store closes
    monkeypatch.setenv("LIMINAL_LOGIN_SESSION_MINUTES", "1")
    with app._lock:
        app._sessions[token].last = time.monotonic() - 120
    assert _call(port, "GET", "/api/me", token=token)[0] == 401 and app.sessions() == []
    assert any("Ada's session ended (idle)" in m for m in lines)
    # stopping the app closes every session
    again = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[1]["token"]
    assert app.sessions() == ["Ada"]
    app.stop()
    assert app.sessions() == []
    assert again


def test_the_library_client_against_the_real_app(served, monkeypatch):
    app, port, lines = served
    monkeypatch.setenv("LIMINAL_LOGIN_URL", f"http://127.0.0.1:{port}")
    client = LoginClient()
    assert client.status()["users"] == 0
    _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})
    with pytest.raises(LoginRefused) as e:
        client.sign_in("Ada", "nope")
    assert e.value.status == 401
    assert client.sign_in("Ada", "correct horse battery")["name"] == "Ada" and client.signed_in
    client.put("massive-account-api-key", "sk-test-0002", "key", "Massive")
    client.put("massive-account-name", "ada@example.test", "account")
    assert client.key("massive") == "sk-test-0002" and client.account("massive") == "ada@example.test"
    with pytest.raises(LoginRefused) as e:
        client.password("massive")
    assert e.value.status == 404
    assert [p["name"] for p in client.pairs()] == ["massive-account-api-key", "massive-account-name"]
    assert client.user()["store"]["pairs"] == 2
    # a program given the token (a plugin's host) asks as the user
    worker = LoginClient(token=client.token)
    assert worker.key("massive") == "sk-test-0002"
    client.sign_out()
    with pytest.raises(LoginRefused):
        worker.key("massive")


def test_the_pairs_an_inheriting_apps_plugins_ask_for_are_asked_of_it(served, folder):
    """0.13.0 (the user, 2026-11-10: "the log-in app should not point to platform, integrator or charts, it should be
    standalone"; "when its inherited it can point to it's superclass"): on its own the login lists no plugin's pairs; an
    app that inherits it answers GET /api/login/pairs with its plugins' (the user, 2026-11-06, "By the variables":
    massive-api-key for MASSIVE_API_KEY), kept as data, and the login marks the ones the signed-in user has. A
    superclass that does not answer: none, said in the log."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from conftest import _port
    from liminal_libs.apps import SESSION_HEADER
    from liminal_login.app import superclass_of

    app, port, lines = served
    assert _call(port, "GET", "/api/pairs/known")[1] == {"known": []}  # on its own: no plugin known, none asked
    asked: list[str] = []
    acme = {"name": "acme-api-key", "variable": "ACME_API_KEY", "plugin": "acme", "title": "Acme", "label": "API key",
            "secret": True, "kind": "key", "system": "integrator"}

    class Inheriting(BaseHTTPRequestHandler):  # the app that inherits the login, as far as the login asks it
        def log_message(self, *a):
            pass

        def do_GET(self):
            asked.append(self.path)
            body = json.dumps({"pairs": [acme, {"name": "Not A Pair!", "variable": "X"}, "junk"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Inheriting)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    inherited = LoginApp(folder, log=lines.append, failure_delay=0,
                         superclass=superclass_of("charts", url=f"http://127.0.0.1:{srv.server_address[1]}/"))
    try:
        iport = _port(inherited.start(0))
        st = _call(iport, "GET", "/api/status")[1]
        assert st["for"] == "charts" and st["forTitle"] == "Liminal Charts" and st["superclass"]["name"] == "charts"
        known = _call(iport, "GET", "/api/pairs/known")[1]["known"]
        assert known == [{**acme, "set": False}] and asked == ["/api/login/pairs"]  # what is not a pair dropped
        assert _call(iport, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})[0] == 201
        token = _call(iport, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[1]["token"]
        session = {SESSION_HEADER: token}
        assert _call(iport, "PUT", "/api/pairs/acme-api-key", {"value": "a-test-value", "kind": "key"}, headers=session)[0] == 200
        after = _call(iport, "GET", "/api/pairs/known", headers=session)[1]["known"]
        assert after == [{**acme, "set": True}] and asked == ["/api/login/pairs"]  # kept a minute: asked once
        assert app.users.count() == 0 and inherited.users.count() == 1  # its users apart from the login's own
    finally:
        inherited.close()
        srv.shutdown()
        srv.server_close()
    away = LoginApp(folder, log=lines.append, failure_delay=0, superclass=superclass_of("platform", url=f"http://127.0.0.1:{srv.server_address[1]}"))
    try:
        assert away.known_pairs() == [] and any("Liminal Platform did not say which pairs" in m for m in lines)
    finally:
        away.close()


def test_the_login_folder_is_the_data_folders_unless_said(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMINAL_LOGIN_DIR", str(tmp_path / "x"))
    assert login_dir() == tmp_path / "x"
    monkeypatch.delenv("LIMINAL_LOGIN_DIR")
    from liminal_libs.layout import data_dir

    assert login_dir() == data_dir() / "login"  # the workspace's store/data, or ~/LiminalData without one (CI)
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "8800")
    assert LoginApp(tmp_path / "x", log=lambda m: None).port() == 8800


def test_the_page_answers_a_finger_and_an_on_screen_keyboard(served):
    """0.12.0 (the user, 2026-11-10: "let's do an update. I want to support touch as well as mouse clicking on the
    interface ... We'll make sure it works across all apps"; "Support for virtual keyboard on tablets and phones"): the
    library's touch.js right after theme.js and before the scripts that use it, the keyboard's room in the viewport;
    every field's keyboard (account names typed as they are, emails, the mailed code, a password current or new, a
    pair's name as it is, its label as free text, its value a secret kept out of password managers), each attribute
    once; Next until a form's last field; no field focused by code after a finger's tap; the pairs' icon buttons named.
    No JavaScript runs here: what the page is drawn with."""
    import re

    app, port, lines = served
    body = _call(port, "GET", "/")[1]
    assert b'<meta name="viewport" content="width=device-width, initial-scale=1, interactive-widget=resizes-content">' in body
    at = {name: body.index(f'src="{name}"'.encode()) for name in ("theme.js", "touch.js", "icons.js", "login.js")}
    assert body.count(b'src="touch.js"') == 1 and at["theme.js"] < at["touch.js"] < min(at["icons.js"], at["login.js"])
    status, touch, r = _call(port, "GET", "/touch.js")
    assert status == 200 and b"window.LiminalTouch" in touch and "javascript" in r.getheader("Content-Type")
    page = _call(port, "GET", "/login.js")[1].decode("utf-8")
    for field in ("""<input id="name" type="text" ${kb('username', { inputmode: 'email' })} maxlength="254" required>""",
                  """<input id="password" type="password" ${kb('password')} required minlength="8">""",
                  """<input id="email" type="email" ${kb('email')} maxlength="254">""",
                  """<input id="password" type="password" ${kb('password', NEW_NEXT)} required minlength="8">""",
                  """<input id="again" type="password" ${kb('password', NEW_DONE)} required minlength="8">""",
                  """<input id="address" type="email" ${kb('email', 'send')} maxlength="254" required>""",
                  """<input id="digits" type="text" class="mono" ${kb('code')} placeholder="123456" maxlength="8" required>""",
                  """<input id="pName" type="text" list="knownNames" ${kb('plain', 'next')} placeholder="some-api-key\"""",
                  """<input id="pLabel" type="text" ${kb('text', 'next')} placeholder""",
                  """<input id="pValue" type="password" ${kb('secret')} maxlength="4096" required>""",
                  """<input id="old" type="password" ${kb('password', 'next')} required>""",
                  """<input id="new" type="password" ${kb('password', NEW_DONE)} required minlength="8">"""):
        assert field in page, field
    assert page.count("${kb('username')}") == 2  # the first user's name and a sign-up's: typed as they are, Next
    # each attribute once: a kind's autocomplete and inputmode are its own, never written beside it
    inputs = re.findall(r"<input [^>]*>", page)
    assert inputs and not [i for i in inputs if "${kb(" in i and ("autocomplete=" in i or "inputmode=" in i)]
    assert "NEW_NEXT = { autocomplete: 'new-password', enterkeyhint: 'next' }" in page
    # a form's next field on a phone keyboard's Next (a hardware keyboard's Enter sends the form, as before)
    assert "c.getAttribute('enterkeyhint') !== 'next'" in page and "!fingered()) return;" in page
    # no keyboard called up unasked: every focus by code goes through touch.js's autofocus
    for focus in ("focusFirst($('name'))", "focusFirst($('address'))", "focusFirst($('digits'))", "if (!focusFirst($('pValue')))"):
        assert focus in page, focus
    assert not re.search(r"\$\('\w+'\)\.focus\(\)", page) and "T.autofocus(el)" in page
    assert 'aria-label="Reveal the value of ${esc(p.name)}"' in page and 'aria-label="Remove the pair ${esc(p.name)}"' in page
    css = _call(port, "GET", "/login.css")[1].decode("utf-8")
    assert ":hover" not in css and "@media (max-width: 700px) { .user-head { flex-wrap: wrap; } }" in css


def test_what_a_look_at_the_page_found_is_mended(served):
    """0.12.1 (the user, 2026-11-10, of six things a look at the page found: "Yes, fix them"): the email field filled and
    bordered like every field typed into (the library's liminal.css, 1.42.1: it had neither and looked missing); the pair
    name's pattern one a browser compiles (it reads a pattern with the `v` flag, which refuses a bare - in a class, and
    then checks nothing); "1 pair", not "1 pairs"; the tab named for where the page is, not "sign in" throughout; a pair
    removed once asked in its row, never through the browser's own confirmation box (which some browsers and views
    refuse); a local login's status and start-up line naming no mail account, since it sends no email. No JavaScript
    runs here: what the page is drawn with."""
    import re

    from conftest import FakeMailer

    app, port, lines = served
    css = _call(port, "GET", "/liminal.css")[1].decode("utf-8")
    rule = re.search(r'\ninput\[type="text"\], input\[type="password"\][^{]*\{([^}]*)\}', css)
    assert rule and 'input[type="email"]' in rule.group(0) and "background: var(--bg)" in rule.group(1)
    assert "border-color: var(--border)" in rule.group(1)
    page = _call(port, "GET", "/login.js")[1].decode("utf-8")
    patterns = re.findall(r'pattern="([^"]*)"', page)
    assert patterns
    for written in patterns:
        value = written.replace("\\\\", "\\")  # the template literal's two backslashes are the attribute's one
        re.compile(value)
        for inside in re.findall(r"\[((?:\\.|[^\]\\])*)\]", value):  # each class: no - left once escapes and ranges are out
            assert "-" not in re.sub(r".-.", "", re.sub(r"\\.", "", inside)), written
    # and the check itself: the old pattern's bare - is caught
    assert "-" in re.sub(r".-.", "", re.sub(r"\\.", "", "a-z0-9._-"))
    assert "(${esc(s.pairs)} ${s.pairs === 1 ? 'pair' : 'pairs'})" in page
    assert "titled(me.name);" in page and "titled('the first user');" in page and page.count("titled('sign up');") == 3
    assert "titled('sign in');" in page and "document.title = `${forTitle}: sign in`" not in page
    assert not re.search(r"\b(window\.)?(confirm|alert)\(", page)
    assert ('<span class="ask" hidden>Remove it? <button type="button" class="yes danger">Remove</button>'
            '<button type="button" class="no">Keep</button></span>') in page
    assert "if (e.key === 'Escape') { e.preventDefault(); asking(false); }" in page
    # a local login: no mail account named, even when this machine has one
    st = _call(port, "GET", "/api/status")[1]
    assert st["signup"] == {"email": False, "local": True, "configured": False, "lastSent": None, "why": app.signup_closed_why()}
    assert app.mail_words() == "a local login: no email" and st["scope"]["kind"] == "local"
    other = LoginApp(app.root / "other", log=lambda m: None, failure_delay=0, mailer=FakeMailer(configured=True))
    try:
        said = other.signup_status()
        assert said["local"] is True and "host" not in said and "sender" not in said and other.mail_words() == "a local login: no email"
    finally:
        other.close()
    assert "This login is local: it sends no email, so no code is needed." in page
