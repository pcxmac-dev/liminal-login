"""The login's plugins (0.18.0; Monday list item 12, item 30 step 8; liminal-libs 1.92.0's LoginPlugin), on a stand-in
plugin: attached when first asked for, their tabs' pages for anyone signed in, a change on an admin tab refused to
anyone but the secret user before the plugin is asked, what a plugin keeps kept in the login's own settings and handed
back, where the users are read from at the next start, and the plugins let go at the stop. The secret user and
`default` signed in side by side, as the other tests do; no value ever reaches a plugin."""
from __future__ import annotations

import json
from pathlib import Path
from http.client import HTTPConnection

from liminal_libs import web
from liminal_libs.apps import SESSION_HEADER
from liminal_libs.sources.plugin import LoginPlugin, LoginRefusal, LoginTab, UsersPlace

from liminal_login.app import ADMIN_ONLY, PLUGIN_KEPT, LoginApp
from liminal_login.users import UserStore

VALUE = "a-value-no-plugin-is-ever-handed-91d2"


class Probe(LoginPlugin):
    name, title, about, api, version = "probe", "Probe", "a stand-in", "2.4", "0.0.1"
    TABS = (LoginTab("mine", "Mine"), LoginTab("global", "Global", admin=True))
    seen: list = []
    users_file = ""

    def page(self, tab, viewer):
        self.seen.append(viewer)
        store = viewer.keystore
        return {"title": tab, "name": viewer.name, "admin": viewer.admin, "kept": dict(viewer.kept),
                "pairs": [dict(p) for p in store.pairs] if store else None, "where": store.where if store else None,
                "users": viewer.place.users, "own": viewer.place.own}

    def change(self, tab, viewer, body):
        if body.get("refuse"):
            raise LoginRefusal("asked again", 409, accept="accept_it")
        return {"keep": {"where": body.get("where")}, "said": "kept"}

    def place(self, kept):
        if not kept.get("where"):
            return None
        return UsersPlace(own=False, users_file=kept["where"], stores=kept["where"] + ".stores",
                          pointer={"engine": "sqlite", "instance": "probe"})


def _call(port, method, path, body=None, token=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    h = {"Content-Type": "application/json"} if body is not None else {}
    if method != "GET":
        h[web.WRITE_HEADER] = "1"
    if token:
        h[SESSION_HEADER] = token
    try:
        conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=h)
        r = conn.getresponse()
        raw = r.read()
    finally:
        conn.close()
    return r.status, json.loads(raw), raw.decode("utf-8")


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


def _two(app):
    port = _port(app.start(0))
    s = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["token"]
    d = _call(port, "POST", "/api/sign-in/secret", {"name": "default"})[1]["token"]
    return port, s, d


def test_its_plugins_are_attached_when_asked_and_let_go_at_the_stop(folder):
    probe = Probe()
    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[probe])
    try:
        assert probe.app is None  # nothing attached in the constructor
        port, s, d = _two(app)
        assert _call(port, "GET", "/api/login-plugins")[0] == 401
        status, out, _ = _call(port, "GET", "/api/login-plugins", token=d)
        assert status == 200 and out["admin"] is False and out["plugins"][0]["name"] == "probe"
        assert [t["id"] for t in out["plugins"][0]["tabs"]] == ["mine", "global"] and out["plugins"][0]["tabs"][1]["admin"]
        assert probe.app is app and app.plugin("probe") is probe
        # its two API views, as every app's plugins have them (the frame's route), asked with a session (0.20.1)
        assert _call(port, "GET", "/api/app/apis?plugin=probe")[0] == 401
        status, apis, _ = _call(port, "GET", "/api/app/apis?plugin=probe", token=d)
        assert status == 200 and apis["name"] == "probe" and apis["internal"]
        assert _call(port, "GET", "/api/login-plugins/nope/mine", token=s)[0] == 404
        assert _call(port, "GET", "/api/login-plugins/probe/nope", token=s)[0] == 404
    finally:
        app.close()
    assert probe.app is None and app.plugin("probe") is None


def test_each_is_shown_their_own_keystore_and_never_a_value(folder):
    probe = Probe()
    probe.seen = []
    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[probe])
    try:
        port, s, d = _two(app)
        assert _call(port, "PUT", "/api/pairs/acme-api-key", {"value": VALUE, "kind": "key"}, token=s)[0] == 200
        mine_s = _call(port, "GET", "/api/login-plugins/probe/mine", token=s)
        mine_d = _call(port, "GET", "/api/login-plugins/probe/mine", token=d)
        assert mine_s[1]["admin"] is True and mine_d[1]["admin"] is False
        assert [p["name"] for p in mine_s[1]["pairs"]] == ["acme-api-key"] and mine_d[1]["pairs"] == []
        assert set(mine_s[1]["pairs"][0]) <= {"name", "kind", "label", "createdAt", "updatedAt"}
        assert mine_s[1]["where"] != mine_d[1]["where"] and mine_s[1]["users"] == 2 and mine_s[1]["own"] is True
        assert VALUE not in mine_s[2] and all(VALUE not in repr(v) for v in probe.seen)  # never handed to the plugin
    finally:
        app.close()


def test_an_admin_tab_is_changed_by_the_secret_user_alone_and_kept_in_the_logins_settings(folder):
    lines: list[str] = []
    probe = Probe()
    app = LoginApp(folder, log=lines.append, failure_delay=0, login_plugins=[probe])
    try:
        port, s, d = _two(app)
        status, out, _ = _call(port, "POST", "/api/login-plugins/probe/global", {"where": "x"}, token=d)
        assert status == 403 and out["error"] == ADMIN_ONLY and app.kept_of("probe") == {}
        status, out, _ = _call(port, "POST", "/api/login-plugins/probe/global", {"refuse": True}, token=s)
        assert status == 409 and out == {"error": "asked again", "accept": "accept_it"}  # a refusal with its second question
        status, out, _ = _call(port, "POST", "/api/login-plugins/probe/global", {"where": "somewhere"}, token=s)
        assert status == 200 and out == {"said": "kept", "kept": ["where"]}
        assert app.kept_of("probe") == {"where": "somewhere"}
        assert json.loads(app.own_users.setting(PLUGIN_KEPT + "probe")) == {"where": "somewhere"}
        assert _call(port, "GET", "/api/login-plugins/probe/global", token=d)[1]["kept"] == {"where": "somewhere"}
        assert _call(port, "POST", "/api/login-plugins/probe/mine", {"where": "y"}, token=d)[0] == 200  # not an admin tab
        assert _call(port, "POST", "/api/login-plugins/probe/global", {"where": None}, token=s)[0] == 200
        assert app.kept_of("probe") == {}  # None forgets it
        assert any("changed probe's global tab: where kept" in l for l in lines)
        assert any("default was refused a change on probe's global tab" in l for l in lines)
    finally:
        app.close()


def test_the_next_start_reads_its_users_where_a_plugin_places_them(folder, tmp_path):
    central = tmp_path / "central" / "users.db"
    there = UserStore(central)
    there.create("ann", "a-long-password-1")
    there.close()
    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[Probe()])
    app.keep_for("probe", {"where": str(central)})
    assert app.place.own  # taken at the next start
    app.close()
    lines: list[str] = []
    again = LoginApp(folder, log=lines.append, failure_delay=0, login_plugins=[Probe()])
    try:
        assert not again.place.own and [u["name"] for u in again.users.names()] == ["ann"]
        assert again.own_users.count() == 0 and again.stores_dir.name == "users.db.stores"
        port = _port(again.start(0))
        assert _call(port, "GET", "/api/status")[1]["place"] == {"own": False, "pointer": {"engine": "sqlite", "instance": "probe"},
                                                                 "fallback": False, "note": ""}
        s = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]
        assert s["admin"] is True and again.users.count() == 2 and again.own_users.count() == 0
        me = _call(port, "GET", "/api/me", token=s["token"])[1]
        assert me["store"]["usersFile"] == str(central) and me["store"]["file"].startswith(str(again.stores_dir))
    finally:
        again.close()
    alone = LoginApp(folder, log=lines.append, failure_delay=0, login_plugins=[])  # the plugin not installed here
    try:
        assert alone.place.own and alone.users is alone.own_users
    finally:
        alone.close()


class Located(Probe):
    """A stand-in placing the users by a kind and a location (0.19.0), or in its fallback folder with a note."""

    name = "located"

    def place(self, kept):
        if not kept.get("file"):
            return None
        pointer = {"kind": "sqlite", "url": Path(kept["file"]).as_uri(), "fallback": bool(kept.get("fallback")),
                   "at": "2026-11-25T00:00:00+00:00", "by": "secret"}
        return UsersPlace(own=False, users_file=kept["file"], stores=kept["file"] + ".stores", pointer=pointer,
                          note="its preferred location could not be used at this start: its fallback folder" if kept.get("fallback") else "")


def test_a_fallback_place_is_said_in_the_log_and_the_status_and_no_location_is_named_there(folder, tmp_path):
    fb = tmp_path / "fallback" / "login" / "users.db"
    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[Located()])
    app.keep_for("located", {"file": str(fb), "fallback": True})
    app.close()
    lines: list[str] = []
    again = LoginApp(folder, log=lines.append, failure_delay=0, login_plugins=[Located()])
    try:
        assert not again.place.own and again.users.path == fb and fb.is_file()
        assert lines.index("login: its preferred location could not be used at this start: its fallback folder") <             next(i for i, l in enumerate(lines) if "its users are read from its fallback folder" in l)
        port = _port(again.start(0))
        st = _call(port, "GET", "/api/status")[1]["place"]
        assert st == {"own": False, "fallback": True, "note": "its preferred location could not be used at this start: its fallback folder",
                      "pointer": {"kind": "sqlite", "fallback": True, "at": "2026-11-25T00:00:00+00:00", "by": "secret"}}
        assert str(tmp_path) not in json.dumps(st)  # no file named to someone not signed in
    finally:
        again.close()


def test_a_place_that_cannot_be_opened_leaves_the_login_on_its_own_folder(folder, tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a folder", encoding="utf-8")
    app = LoginApp(folder, log=lambda m: None, failure_delay=0, login_plugins=[Located()])
    app.keep_for("located", {"file": str(blocker / "users.db")})  # its folder cannot be made: a file is in the way
    app.close()
    lines: list[str] = []
    again = LoginApp(folder, log=lines.append, failure_delay=0, login_plugins=[Located()])
    try:
        assert again.place.own and again.users is again.own_users and again.stores_dir == folder / "users"
        assert "could not be opened at this start" in again.place.note and again.place.pointer["kind"] == "sqlite"
        assert any("could not be opened at this start" in l and "its own folder's users are used" in l for l in lines)
        port = _port(again.start(0))
        st = _call(port, "GET", "/api/status")[1]["place"]
        assert st["own"] is True and "could not be opened" in st["note"] and str(tmp_path) not in json.dumps(st)
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"})[1]["admin"] is True
        assert again.own_users.count() == 1
    finally:
        again.close()

