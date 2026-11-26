"""Codebase on the login's page (0.17.6; Monday list item 15: "Codebase in the login's, the integrator's and the charts'
pages (the platform has it)"): the library's object every App holds (liminal_libs.apps.Codebase) answered at
api/codebase for one of this login's own users signed in to a local login, and drawn by the library's codebase.js in
the page's list | data | specifics. The code base is given a workspace of the test's own and a stand-in runner: no git
runs, no repository of this machine is read."""
from __future__ import annotations

import json
import time
from http.client import HTTPConnection

from liminal_libs.apps import Codebase
from liminal_libs.web import WRITE_HEADER

from liminal_login.app import LoginApp

COOKIE = "liminal_login"  # the login's own, on its own


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


def _stand_in(app, tmp_path):
    ws = tmp_path / "ws"
    (ws / "login" / ".git").mkdir(parents=True)
    (ws / "login" / "app.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    asked: list[str] = []

    def runner(args, cwd, timeout):
        said = " ".join(args)
        asked.append(said)
        if said.startswith("git status"):
            return 0, b"# branch.head main\n# branch.upstream origin/main\n# branch.ab +1 -3\n", b""
        if said.startswith("git config --get-regexp"):
            return 0, b"remote.origin.url https://example.test/login.git\n", b""
        if said.startswith("git config --get"):
            return 0, b"https://someone:tok3n@example.test/login.git\n", b""
        if said.startswith("git ls-files"):
            return 0, b"app.py\0", b""
        if said.startswith(("git log", "git fetch")):
            return 0, b"", b""
        return 127, b"", b"not installed here"

    app.codebase = Codebase(app, roots=[ws], runner=runner, own_parts=lambda: [("the login app", ws / "login")])
    return app.codebase, asked


def test_the_login_answers_its_code_base_to_its_own_signed_in_user(served, tmp_path):
    app, port, _lines = served
    codebase, asked = _stand_in(app, tmp_path)
    # nobody signed in: nothing of this machine's code is said
    assert _call(port, "GET", "/api/codebase")[0] == 401 and _call(port, "POST", "/api/codebase/fetch", {})[0] == 401
    assert codebase._reading is None and asked == []  # not even read
    token = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["token"]
    status, first, _ = _call(port, "GET", "/api/codebase", token=token)
    assert status == 200 and first["state"] in ("reading", "ready")
    codebase.wait()
    status, got, _ = _call(port, "GET", "/api/codebase", token=token)
    assert status == 200 and got["state"] == "ready" and got["app"] == "login" and got["totals"]["repositories"] == 1
    repo = got["repositories"][0]
    assert (repo["name"], repo["kind"], repo["branch"], repo["ahead"], repo["behind"]) == ("login", "git", "main", 1, 3)
    assert repo["remote"] == "https://example.test/login.git" and "tok3n" not in json.dumps(got)
    assert repo["used"] == ["the login app"] and got["languages"][0]["name"] == "Python" and got["languages"][0]["lines"] == 3
    assert not [a for a in asked if a.startswith("git fetch")]  # a reading asks no remote
    # the remotes asked on the user's click: a write (the page's own header), then read again
    assert _call(port, "POST", "/api/codebase/fetch", {}, headers={"X-Liminal-Charts": "0"}, token=token)[0] == 403
    status, said, _ = _call(port, "POST", "/api/codebase/fetch", {}, token=token)
    assert (status, said) == (202, {"started": True})
    end = time.monotonic() + 10
    while not (codebase.snapshot().get("fetching") or {}).get("ended") and time.monotonic() < end:
        time.sleep(0.02)
    assert "git fetch --quiet" in asked
    # the library's drawing, served beside the page's own files
    status, drawing, _ = _call(port, "GET", "/codebase.js")
    assert status == 200 and b"window.LiminalCodebase = {" in drawing


def test_a_domains_login_shows_no_code_base(served_mail, tmp_path):
    """A domain's login: its users are anyone who signs up by email, so none of them is told this machine's code."""
    app, port, _lines, mailer = served_mail
    codebase, asked = _stand_in(app, tmp_path)
    user = app.users.create("ada", "correct horse battery", "ada@example.test")
    assert user is not None
    token = _call(port, "POST", "/api/sign-in", {"name": "ada", "password": "correct horse battery"})[1]["token"]
    assert _call(port, "GET", "/api/me", token=token)[0] == 200  # signed in
    status, said, _ = _call(port, "GET", "/api/codebase", token=token)
    assert status == 403 and "no code base" in said["error"] and asked == []


def test_the_page_lists_the_account_and_codebase_and_hands_codebase_the_two_panes():
    page = (LoginApp.STATIC / "login.js").read_text(encoding="utf-8")
    assert "const C = window.LiminalCodebase || null;" in page
    assert "item('account', 'key', 'Your account'" in page and "item('codebase', 'branch', 'Codebase'" in page
    assert '<nav class="app-list" id="list"' in page and '<section class="app-data" id="data"' in page
    assert '<aside class="app-side" id="side"' in page and "main.classList.add('cols');" in page
    # relative paths, as every request of this page: under another app's prefix the login's own code base is asked
    assert "C.mount($('data'), $('side'), { get: (path) => api('GET', path.replace(/^\\//, ''))" in page
    assert "leaveCodebase();  // whatever is drawn now" in page and "C.unmount();" in page
    # held in another app's page, a remote user, a domain's login or an older library: one column, as before
    assert "const mayCodebase = !me.remote && !(st.scope && st.scope.kind === 'domain');" in page
    # 0.18.0: the list is drawn for the code base or the login's plugins, each shown only where it may be
    assert "const withCodebase = !!C && mayCodebase;" in page
    # 0.20.1: and for This app, the login's own two views (tests/test_api_views.py)
    assert "const listed = !embedded && (withCodebase || mayOwn || plugins.length > 0);" in page
    assert "main.innerHTML = userCard(me) + storeFacts(me) + rest;" in page
    assert "columns(userCard(me) + rest, storeFacts(me), withCodebase, 'login:account');" in page  # 0.20.2: its scope
    assert "plugins = embedded ? [] : ((await api('GET', 'api/login-plugins')).plugins || []);" in page
    assert "api/app/apis?plugin=${encodeURIComponent(p.name)}" in page  # its External and Internal API, the frame's
    html = (LoginApp.STATIC / "index.html").read_text(encoding="utf-8")
    assert html.index('src="icons.js"') < html.index('src="codebase.js"') < html.index('src="login.js"')
    assert not (LoginApp.STATIC / "codebase.js").exists()  # the library's file, never shadowed by one of the page's own
