"""The login held as an object by the app that inherits it (0.16.0; the user, 2026-11-14: "the platform and integrator
inherit the login function, they are separate login instances, class vs object"; "login doesn't point to anything except
the app that inherited it"): its superclass the app itself, its users in that app's folder under that app's cookie, the
pairs its plugins ask for asked of the app directly, no address and no port of its own; served under the app's /login/
(liminal-libs 1.52.0 App.login_object)."""
from __future__ import annotations

import json
import urllib.request
from http.client import HTTPConnection

import pytest

from liminal_libs import web
from liminal_libs.apps import App, Scope

from liminal_login.app import LoginApp, Superclass, superclass_from


class Platformish(App):
    NAME, TITLE, ICON, PORT = "platform", "Liminal Platform", "chip", 8775

    def login_pairs(self):
        return [{"name": "namecheap-api-key", "variable": "NAMECHEAP_API_KEY", "plugin": "namecheap", "secret": True},
                {"name": "Not A Pair!"}]


def _call(port, method, path, body=None, cookie=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Content-Type": "application/json"} if body is not None else {}
    if method != "GET":
        h[web.WRITE_HEADER] = "1"
    if cookie:
        h["Cookie"] = cookie
    conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=h)
    r = conn.getresponse()
    raw = r.read()
    return r.status, raw, r


def test_a_login_made_with_the_app_that_inherits_it_points_to_that_app_alone(folder, monkeypatch):
    app = Platformish(log=lambda m: None)
    login = LoginApp(folder, log=lambda m: None, failure_delay=0, superclass=app)
    try:
        sup = login.superclass
        assert (sup.name, sup.title, sup.url) == ("platform", "Liminal Platform", "") and sup.app is app and login.holder is app
        assert login.dir == folder / "platform" and login.cookie_name == "liminal_login_platform"
        assert login.port() == 8775 and login.url() == "http://127.0.0.1:8775/login/"  # no port of its own: the app's
        assert login.describe()["superclass"] == {"name": "platform", "title": "Liminal Platform", "url": ""}
        # the pairs its plugins ask for asked of the app itself, never over the network
        monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: pytest.fail("no address to ask"))
        rows = login.superclass_pairs()
        assert [r["name"] for r in rows] == ["namecheap-api-key"]
        assert rows[0]["variable"] == "NAMECHEAP_API_KEY" and rows[0]["plugin"] == "namecheap" and rows[0]["secret"] is True
    finally:
        login.close()
    # a short name, a Superclass, or nothing: as before
    assert superclass_from("charts") == Superclass("charts", "Liminal Charts") and superclass_from("charts").app is None
    assert superclass_from(None) is None and superclass_from(Superclass("x", "X")) == Superclass("x", "X")


def test_the_app_that_inherits_the_login_serves_it_at_its_own_port(folder, tmp_path, monkeypatch):
    """The libs' App holding this login class (its default LOGIN_CLASS): the first user made and signed in at the app's
    /login/, the app's page opening once signed in, the login's word on where it is (the app's address)."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "index.html").write_text("<html>the platform's page</html>", encoding="utf-8")

    class Holder(Platformish):
        LOGIN, STATIC = True, pages

    monkeypatch.setattr(Scope, "find", classmethod(lambda cls, start=None, env=None: None))  # no login file here
    app = Holder(log=lambda m: None)
    port = int(app.start(0).rstrip("/").rsplit(":", 1)[1])
    try:
        status, body, _ = _call(port, "GET", "/")
        assert status == 200 and b'id="signinFrame"' in body  # not signed in: the sign-in
        st = json.loads(_call(port, "GET", "/login/api/status")[1])
        assert st["for"] == "platform" and st["signedIn"] is False and st["superclass"]["url"] == ""
        assert st["app"]["url"] == f"http://127.0.0.1:{port}/login/" and st["app"]["port"] == port
        status, body, _ = _call(port, "POST", "/login/api/users", {"name": "Ada", "password": "correct horse battery"})
        assert status == 201, body
        status, body, r = _call(port, "POST", "/login/api/sign-in", {"name": "ada", "password": "correct horse battery"})
        assert status == 200, body
        cookie = r.getheader("Set-Cookie").split(";", 1)[0]
        assert cookie.startswith("liminal_login_platform=")
        assert b"the platform's page" in _call(port, "GET", "/", cookie=cookie)[1]  # signed in there: the app's page
        assert (folder / "platform" / "users.db").exists()  # its users the platform's, in its folder
        assert app.login_object().superclass.app is app
    finally:
        app.stop()
