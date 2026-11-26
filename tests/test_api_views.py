"""The login's own two views (0.20.1; Monday list item 17; the user, 2026-11-16: "for all apps, and all plugins, there
should be an external api tab, and an internal api tab"): GET /api/app/apis, the frame's, answered here only to one of
its own users signed in to a local login, as its code base is; a plugin's two (?plugin=NAME) to anyone signed in. The
login on a free port in a thread, stand-in mail; nothing of a plugin is asked, nothing reached outside this
machine."""
from __future__ import annotations

import ast
import json
import re
import time
from http.client import HTTPConnection
from pathlib import Path

from liminal_libs.apis import problems

import liminal_login
from liminal_login import apis, routes
from liminal_login.app import NO_OWN_APIS, LoginApp, RemoteSession, RemoteUser

COOKIE = "liminal_login"


def _get(port, path, token=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path, headers={"Cookie": f"{COOKIE}={token}"} if token else {})
        r = conn.getresponse()
        return r.status, json.loads(r.read())
    finally:
        conn.close()


def _secret(port, name="secret"):
    from liminal_libs.web import WRITE_HEADER

    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", "/api/sign-in/secret", body=json.dumps({"name": name}).encode(),
                     headers={"Content-Type": "application/json", WRITE_HEADER: "1"})
        return json.loads(conn.getresponse().read())["token"]
    finally:
        conn.close()


def test_its_own_views_answer_its_own_users_on_a_local_login(served):
    app, port, _lines = served
    status, said = _get(port, "/api/app/apis")
    assert status == 401 and "not signed in" in said["error"]  # nothing of it is said to nobody
    for name in ("secret", "default"):  # its admin, and an ordinary user of its own
        status, got = _get(port, "/api/app/apis", _secret(port, name))
        assert status == 200 and got["app"]["app"] == "login"
    inner = got["internal"]
    assert inner["name"] == "login" and inner["counts"]["own"] == len(routes.ROUTES)
    assert [(r["method"], r["path"]) for r in inner["routes"] if r["own"]] == [(r[0], r[1]) for r in routes.ROUTES]
    assert [ln["name"] for ln in inner["linked"]] == ["its superclass", "other logins"]
    assert [ln["variable"] for ln in inner["linked"]] == ["LIMINAL_LOGIN_FOR_URL", "LIMINAL_LOGIN_REMOTES"]
    assert inner["notes"] == list(LoginApp.INTERNAL_NOTES) and all(len(n) <= 400 for n in LoginApp.INTERNAL_NOTES)
    assert set(inner["calls"]) == {"login"} and set(inner["calls"]["login"]) == set(LoginApp.CALLS["login"])
    # its External API: the cards of what its own code associates with
    assert [a["name"] for a in got["apis"]] == [a.name for a in apis.APIS]


def test_a_domains_login_shows_no_api_views_of_its_own(served_mail):
    app, port, _lines, _mailer = served_mail
    app.users.create("ada", "correct horse battery", "ada@example.test")
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    from liminal_libs.web import WRITE_HEADER

    conn.request("POST", "/api/sign-in", body=json.dumps({"name": "ada", "password": "correct horse battery"}).encode(),
                 headers={"Content-Type": "application/json", WRITE_HEADER: "1"})
    token = json.loads(conn.getresponse().read())["token"]
    conn.close()
    assert _get(port, "/api/me", token)[0] == 200  # signed in
    status, said = _get(port, "/api/app/apis", token)
    assert (status, said["error"]) == (403, NO_OWN_APIS)


def test_a_user_of_another_login_is_sent_to_their_own(served):
    app, port, _lines = served
    s = RemoteSession("t0ken-of-a-remote-user", RemoteUser("ada@example.test"), "https://example.test", "theirs",
                      time.monotonic())
    app._sessions[s.token] = s  # signed in at their own login (none is asked: the request is refused first)
    try:
        status, said = _get(port, "/api/app/apis", s.token)
    finally:
        app._sessions.pop(s.token, None)  # gone before the stop, which would sign them out there
    assert status == 403 and "another login" in said["error"]


def test_a_plugins_two_views_ask_a_session(folder):
    from test_login_plugins import Probe

    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[Probe()])
    try:
        port = int(app.start(0).split("127.0.0.1:", 1)[1].split("/", 1)[0])
        token = _secret(port)
        assert _get(port, "/api/login-plugins", token)[0] == 200  # attached when first asked for
        status, said = _get(port, "/api/app/apis?plugin=probe")  # the frame's, asked with a session (the user, 2026-11-26)
        assert status == 401 and "not signed in" in said["error"]
        status, got = _get(port, "/api/app/apis?plugin=probe", token)
        assert status == 200 and got["name"] == "probe"
        hooks = {h["name"]: h for h in got["internal"]["hooks"]}
        assert hooks["page"]["how"] == LoginApp.CALLS["login"]["page"]  # what the login's code does with it
        assert got["internal"]["attributes"] == list(LoginApp.ATTRIBUTES["login"])
        assert _get(port, "/api/app/apis?plugin=nope", token)[0] == 404
    finally:
        app.close()


URL = re.compile(r"\b(?:https?|wss?|ftp)://([A-Za-z0-9.-]+)")  # a scheme://host literal, as the charts' boundary test


def test_its_cards_are_sound():
    assert problems(apis.APIS) == []
    assert {a.name for a in apis.APIS} == {"SQLite, through Python's sqlite3", "nslookup (the domain's mail record)",
                                           "Docker (the mail server container)", "git"}


def test_no_other_py_of_the_login_names_an_outside_host():
    """The user's rule of 2026-10-31 (the app's code names no provider's host; links for people excepted): the login's
    card links are in apis.py alone; every other module names this machine, an example's or a domain in its words."""
    root = Path(liminal_login.__file__).parent
    found = {(p.relative_to(root).as_posix(), h.lower().rstrip("."))
             for p in root.rglob("*.py") for h in URL.findall(p.read_text(encoding="utf-8"))}
    others = {h for f, h in found if f != "apis.py"}
    assert others <= {"127.0.0.1", "its.domain", "your-domain", "a.domain", "host", "localhost"}, others
    assert {"www.sqlite.org", "docs.python.org", "learn.microsoft.com", "bind9.readthedocs.io", "docs.docker.com",
            "git-scm.com"} <= {h for f, h in found if f == "apis.py"}


def _taken(tree, name: str) -> tuple[set[str], set[str]]:
    taken = {n.attr for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == name}
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
              and n.func.value.id == name}
    read = {n.args[1].value for n in ast.walk(tree)  # getattr(p, "ICON", ...)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) >= 2
            and isinstance(n.args[0], ast.Name) and n.args[0].id == name and isinstance(n.args[1], ast.Constant)}
    return taken | read, called


def test_its_calls_and_attributes_are_what_its_code_takes_of_its_plugins():
    """What app.py takes of a plugin (`p`) where it attaches them, reads where its users are and answers their routes,
    and the hooks it asks of them by name (self.ask(name, "page", ...))."""
    tree = ast.parse(Path(liminal_login.app.__file__).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LoginApp")
    fns = [n for n in cls.body if isinstance(n, ast.FunctionDef)
           and n.name in ("login_plugins", "_users_place", "_plugin_route")]
    taken, called = set(), set()
    for fn in fns:
        t, c = _taken(fn, "p")
        taken |= t
        called |= c
    asked = {n.args[1].value for fn in fns for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "ask"
             and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)}
    assert asked == {"page", "change"}
    assert set(LoginApp.CALLS) == {"login"} and set(LoginApp.ATTRIBUTES) == {"login"}
    assert set(LoginApp.CALLS["login"]) == called | asked
    assert set(LoginApp.ATTRIBUTES["login"]) == taken - called


def test_the_page_lists_this_app_last_for_whom_codebase_is_shown_and_never_embedded():
    page = (LoginApp.STATIC / "login.js").read_text(encoding="utf-8")
    entry = "${mayOwn ? item('app', 'sort', 'This app', 'its own External and Internal API') : ''}</nav>"
    assert entry in page and page.index("item('codebase', 'branch', 'Codebase'") < page.index(entry)  # last, after it
    assert "mayOwn = !!I && mayCodebase && !embedded;" in page  # its own users on a local login, never in another page
    assert "if (listed && view === 'app' && mayOwn) { columns('', '', withCodebase); return showOwn(me); }" in page
    # its two tabs beside its title, asked only while shown, relative (under another app's /login/: the login's own)
    assert "d = await api('GET', 'api/app/apis');" in page and "api('GET', '/api/app/apis')" not in page
    assert "{ id: 'external', title: 'External API' }" in page and "{ id: 'internal', title: 'Internal API' }" in page
    assert "I.html(inner, { owner: 'app:login'" in page and "A.html(d.apis || [], d.apiFacts || {}, { fold: true" in page
    # a login from before: the frame's defaults (no route of its own) or a 404, said in words
    assert "if (!inner || !(inner.counts && inner.counts.own > 0))" in page
    assert "This login was started before it could show its own APIs: restart it (or the app that holds it)" in page
    assert "e.status === 404 ? OWN_OLDER : e.message" in page
    html = (LoginApp.STATIC / "index.html").read_text(encoding="utf-8")
    assert html.index('src="apis.js"') < html.index('src="internal.js"') < html.index('src="login.js"')
