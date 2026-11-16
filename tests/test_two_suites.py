"""Two suites on one machine (0.17.1; the user, 2026-11-15: "i need to run the same suite in a WSL container"): the
suite inside WSL answers at 127.0.0.1 like Windows', on ports of its own, and a cookie belongs to a host whatever the
port. Each login keeps its session under a cookie of its own name, so a browser signed in to both stays signed in to
both. Every store in the test's own folder, the apps on free ports in threads, no process started."""
from __future__ import annotations

import json
from http.client import HTTPConnection

from liminal_libs import web
from liminal_libs.apps import App

from liminal_login import cli
from liminal_login.app import LoginApp


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


def _call(port, method, path, body=None, cookie=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    h = {"Content-Type": "application/json"} if body is not None else {}
    if method != "GET":
        h[web.WRITE_HEADER] = "1"
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


def test_a_browser_signed_in_to_both_suites_logins_stays_signed_in_to_both(folder):
    windows = LoginApp(folder / "windows", log=lambda m: None, failure_delay=0)  # at its usual port, 8795
    linux = LoginApp(folder / "linux", log=lambda m: None, failure_delay=0, port=9795)  # the suite inside WSL
    try:
        assert windows.cookie_name == "liminal_login" and linux.cookie_name == "liminal_login_9795"
        assert linux.port() == 9795 and linux.url() == "http://127.0.0.1:9795/" and windows.port() == 8795
        wport, lport = _port(windows.start(0)), _port(linux.start(0))  # the test's free ports: the names stay as set
        assert windows.cookie_name == "liminal_login" and linux.cookie_name == "liminal_login_9795"
        _, w, wr = _call(wport, "POST", "/api/sign-in/secret", {"name": "secret"})
        _, x, xr = _call(lport, "POST", "/api/sign-in/secret", {"name": "default"})
        assert wr.getheader("Set-Cookie").startswith(f"liminal_login={w['token']};")
        assert xr.getheader("Set-Cookie").startswith(f"liminal_login_9795={x['token']};")
        # the browser sends every cookie of the host to both: each login reads its own, and knows who is in
        both = f"liminal_login={w['token']}; liminal_login_9795={x['token']}"
        assert _call(wport, "GET", "/api/me", cookie=both)[1]["name"] == "secret"
        assert _call(lport, "GET", "/api/me", cookie=both)[1]["name"] == "default"
        # under one name, as before 0.17.1, the second sign-in replaced the first: the other login did not know it
        assert _call(wport, "GET", "/api/me", cookie=f"liminal_login={x['token']}")[0] == 401
        assert _call(lport, "GET", "/api/me", cookie=f"liminal_login={w['token']}")[0] == 401  # nor is its name the other's
        # signing out of one ends its own session and clears its own cookie
        status, _, r = _call(lport, "POST", "/api/sign-out", cookie=both)
        assert status == 200 and r.getheader("Set-Cookie").startswith("liminal_login_9795=;")
        assert _call(lport, "GET", "/api/me", cookie=both)[0] == 401
        assert _call(wport, "GET", "/api/me", cookie=both)[1]["name"] == "secret" and windows.sessions() == ["secret"]
    finally:
        windows.close()
        linux.close()


def test_the_cookies_name_follows_the_port_the_login_is_set_to(folder, monkeypatch):
    assert LoginApp(folder / "a", log=lambda m: None).cookie_name == "liminal_login"
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "9795")  # as the suite's service sets it
    by_variable = LoginApp(folder / "b", log=lambda m: None)
    assert by_variable.cookie_name == "liminal_login_9795" and by_variable.port() == 9795
    assert LoginApp(folder / "c", log=lambda m: None, port=8795).cookie_name == "liminal_login"  # told its usual port
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "8795")
    assert by_variable.cookie_name == "liminal_login"  # the usual port, said outright: the usual name
    monkeypatch.delenv("LIMINAL_LOGIN_PORT")
    for each in (by_variable,):
        each.close()

    class Platformish(App):
        NAME, TITLE, ICON, PORT, PORT_VAR = "platform", "Liminal Platform", "chip", 8775, "LIMINAL_PLATFORM_PORT"

    monkeypatch.delenv("LIMINAL_PLATFORM_PORT", raising=False)
    app = Platformish(log=lambda m: None)
    held = LoginApp(folder, log=lambda m: None, superclass=app)
    try:
        assert held.cookie_name == "liminal_login_platform"
        monkeypatch.setenv("LIMINAL_PLATFORM_PORT", "9775")  # the platform of the suite inside WSL
        assert held.cookie_name == "liminal_login_platform_9775"
    finally:
        held.close()
    # a holder that says nothing of ports (a stand-in): the name as it always was
    assert LoginApp._set_port(type("Held", (), {"holder": object(), "_port_told": None})()) == (None, None)


def test_serve_with_a_port_sets_the_address_and_the_cookie(folder, monkeypatch, capsys):
    seen: list = []
    monkeypatch.setattr(LoginApp, "serve", lambda self, port=None, open_browser=False, stop=None, until_quiet=None:
                        seen.append((port, self.cookie_name, self.url(), self.describe()["port"])) or "url")
    assert cli.main(["serve", "--no-browser", "--port", "9795"]) == 0
    assert seen == [(9795, "liminal_login_9795", "http://127.0.0.1:9795/", 9795)]
    assert "its page at http://127.0.0.1:9795/" in capsys.readouterr().out
    assert cli.main(["serve", "--no-browser"]) == 0 and seen[-1] == (8795, "liminal_login", "http://127.0.0.1:8795/", 8795)
