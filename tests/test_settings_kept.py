"""Preferences and licences in each user's own store (0.17.7; Monday list item 21; the user, 2026-11-19: "preferences,
keys, licenses all get stored in the individual's login db"): the vault takes the kinds `preference` and `licence`;
the library's LoginClient keeps and reads them as JSON and never reads a key as one; the login's own GET /api/ui and
an app holding the login as an object answer each browser with its own user's theme, and what a request keeps through
the asking person's login is that user's. Every store in the test's own folder, the app on a free port in a thread,
no process started."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from http.client import HTTPConnection

import pytest

from liminal_libs import ui, web
from liminal_libs.apps import (LICENCE, SESSION_HEADER, App, LoginClient, LoginRefused, Refused, Scope, accept_licence,
                               licence)
from liminal_login.userlogin import SessionLogin
from liminal_login.vault import KINDS


def _call(port, method, path, body=None, token=None, cookie=None):
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
    return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw), r


@pytest.fixture
def ui_file(tmp_path, monkeypatch):
    monkeypatch.setenv(ui.UI_VAR, str(tmp_path / "ui.json"))
    monkeypatch.setenv("LIMINAL_LICENCES_FILE", str(tmp_path / "licences.json"))
    return tmp_path / "ui.json"


def test_the_vault_keeps_preferences_and_licences_beside_the_keys():
    assert KINDS[-2:] == ("preference", "licence") and LICENCE in KINDS


def test_each_user_keeps_their_own_theme_and_licence_through_the_login_client(served, ui_file):
    app, port, lines = served
    url = f"http://127.0.0.1:{port}"
    clients = {}
    for name in ("secret", "default"):
        token = _call(port, "POST", "/api/sign-in/secret", {"name": name})[1]["token"]
        clients[name] = LoginClient(url, token=token)
    s, d = clients["secret"], clients["default"]
    assert ui.save_preferences(login=s, theme="paper")["store"] == "login"
    ui.save_preferences(login=d, theme="midnight")
    assert (ui.preferences(login=s)["theme"], ui.preferences(login=d)["theme"]) == ("paper", "midnight")
    assert not ui_file.exists()  # neither in the file
    row = next(p for p in s.pairs() if p["name"] == "ui-theme")
    assert row["kind"] == "preference"
    # the login's own page reads each browser's own (GET /api/ui, the asking person's login)
    assert _call(port, "GET", "/api/ui", token=s.token)[1]["theme"] == "paper"
    assert _call(port, "GET", "/api/ui", token=d.token)[1]["theme"] == "midnight"
    assert _call(port, "GET", "/api/ui")[1]["theme"] == "dark"  # nobody signed in: the file (none: the default)
    # a licence accepted: kept with what, when and by whom, in that user's store alone
    at = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
    rec = accept_licence(d, "dbip-lite", title="DB-IP IP to City Lite", version="2026-11",
                         url="https://db-ip.com/db/download/ip-to-city-lite", words="CC BY 4.0", at=at)
    assert rec["kept"] == "your login's store" and rec["acceptedBy"] == "default"
    assert licence(d, "dbip-lite")["acceptedAt"] == "2026-11-24T10:00:00Z" and licence(s, "dbip-lite") is None
    status, pair, _ = _call(port, "GET", "/api/pairs/licence-dbip-lite", token=d.token)
    assert status == 200 and pair["kind"] == "licence" and json.loads(pair["value"])["version"] == "2026-11"
    # a key is never read as a setting
    d.put("ui-other", "sk-a-key-value", kind="key")
    with pytest.raises(LoginRefused) as refused:
        d.setting("ui-other")
    assert refused.value.status == 409
    assert "sk-a-key-value" not in "\n".join(lines) and "paper" not in "\n".join(lines)


def test_the_files_theme_moves_into_each_users_store_once(served, ui_file):
    app, port, _ = served
    ui_file.write_text(json.dumps({"theme": "graphite"}), encoding="utf-8")
    token = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    assert _call(port, "GET", "/api/ui", token=token)[1]["theme"] == "graphite"
    ui_file.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    assert _call(port, "GET", "/api/ui", token=token)[1]["theme"] == "graphite"  # theirs now, from the first read
    assert json.loads(ui_file.read_text(encoding="utf-8")) == {"theme": "light"}  # the file as it was left


def test_a_session_signed_out_is_no_store_and_the_file_is_read(served, ui_file):
    app, port, _ = served
    token = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    session = app._sessions[token]
    theirs = SessionLogin(app, session)
    ui.save_preferences(login=theirs, theme="paper")
    assert _call(port, "POST", "/api/sign-out", token=token)[0] == 200
    with pytest.raises(Exception) as closed:
        theirs.setting("ui-theme")
    assert getattr(closed.value, "status", None) == 401  # a refusal, not a server error
    assert ui.preferences(login=theirs)["theme"] == "dark"  # the file's (none), as with nobody signed in


def test_an_app_holding_the_login_answers_each_browser_with_its_own_users_theme(folder, tmp_path, ui_file, monkeypatch):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "index.html").write_text("<html>the platform's page</html>", encoding="utf-8")

    class Holder(App):
        NAME, TITLE, ICON, PORT = "platform", "Liminal Platform", "chip", 8775
        LOGIN, STATIC = True, pages

        def api(self, handler, method, path, query, body):
            if method == "POST" and path == "/api/theme":  # as a plugin's hook asked from the page: no login named
                try:
                    return 200, ui.save_preferences(theme=body.get("theme"))
                except ValueError as e:
                    raise Refused(400, str(e)) from None
            return super().api(handler, method, path, query, body)

    monkeypatch.setattr(Scope, "find", classmethod(lambda cls, start=None, env=None: None))
    app = Holder(log=lambda m: None)
    port = int(app.start(0).rstrip("/").rsplit(":", 1)[1])
    try:
        cookies = {}
        for name in ("secret", "default"):
            r = _call(port, "POST", "/login/api/sign-in/secret", {"name": name})[2]
            cookies[name] = r.getheader("Set-Cookie").split(";", 1)[0]
        assert _call(port, "POST", "/api/theme", {"theme": "paper"}, cookie=cookies["secret"])[1]["store"] == "login"
        assert _call(port, "POST", "/api/theme", {"theme": "midnight"}, cookie=cookies["default"])[0] == 200
        assert _call(port, "GET", "/api/ui", cookie=cookies["secret"])[1]["theme"] == "paper"
        assert _call(port, "GET", "/api/ui", cookie=cookies["default"])[1]["theme"] == "midnight"
        assert not ui_file.exists()
        # nobody signed in at this browser: the app's own login (none here), so the file, as before
        assert _call(port, "POST", "/api/theme", {"theme": "light"})[1]["store"] == "file"
        assert json.loads(ui_file.read_text(encoding="utf-8")) == {"theme": "light"}
        assert _call(port, "GET", "/api/ui", cookie=cookies["secret"])[1]["theme"] == "paper"
    finally:
        app.stop()
