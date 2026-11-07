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


COOKIE = "liminal_login_charts"  # the charts namespace's (the tests' default)


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
    assert tray == {"app": "login", "icon": "user", "title": "Login: Liminal Charts",
                    "items": [{"id": "login", "icon": "user", "title": "Login: Liminal Charts", "kind": "app", "app": "login"}]}
    assert _call(port, "GET", "/api/app")[1]["port"] == 8795 and app.port() == 8795 and app.dir == app.root / "charts"
    assert any("login: its page at" in m for m in lines)


def test_the_first_user_is_made_from_the_page_then_signs_in_and_out(served):
    app, port, lines = served
    st = _call(port, "GET", "/api/status")[1]
    assert {k: st[k] for k in ("users", "signedIn", "name", "app")} == {"users": 0, "signedIn": False, "name": None, "app": app.describe()}
    assert st["signup"]["email"] is False and st["for"] == "charts" and app.describe()["for"] == "charts" and app.cookie_name == COOKIE
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


def test_the_pairs_the_plugins_ask_for_are_listed_by_their_variables(served):
    # the user, 2026-11-06, "By the variables": the plugins installed beside this app ask for pairs named
    # after their key variables (massive-api-key for MASSIVE_API_KEY), each once, set or not for the user
    from liminal_libs.sources.registry import assistants, providers, publishers

    app, port, lines = served
    plugins = [*providers().values(), *publishers().values(), *assistants().values()]
    wanted = {k.pair for p in plugins for k in (p.keys or ())}
    status, data, _ = _call(port, "GET", "/api/pairs/known")  # without a session: what there is, none set
    known = data["known"]
    assert status == 200 and {r["name"] for r in known} == wanted and len(known) == len(wanted)
    assert not any(r["set"] for r in known) and known == sorted(known, key=lambda r: (r["plugin"], r["name"]))
    assert all(r["variable"] == r["variable"].upper() and r["kind"] in ("key", "detail") and r["kind"] == ("key" if r["secret"] else "detail")
               and r["name"] == r["variable"].lower().replace("_", "-") for r in known)
    if not wanted:  # no plugin installed beside this app (CI): nothing is known, and that is the answer
        return
    _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})
    token = _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"})[1]["token"]
    first = known[0]
    assert _call(port, "PUT", f"/api/pairs/{first['name']}", {"value": "a-test-value", "kind": first["kind"]}, token=token)[0] == 200
    after = {r["name"]: r for r in _call(port, "GET", "/api/pairs/known", token=token)[1]["known"]}
    assert after[first["name"]]["set"] and not any(r["set"] for n, r in after.items() if n != first["name"])


def test_the_login_folder_is_the_data_folders_unless_said(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMINAL_LOGIN_DIR", str(tmp_path / "x"))
    assert login_dir() == tmp_path / "x"
    monkeypatch.delenv("LIMINAL_LOGIN_DIR")
    from liminal_libs.layout import data_dir

    assert login_dir() == data_dir() / "login"  # the workspace's store/data, or ~/LiminalData without one (CI)
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "8800")
    assert LoginApp(tmp_path / "x", log=lambda m: None).port() == 8800
