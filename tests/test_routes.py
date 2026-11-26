"""The login's route table (0.20.1; Monday list item 17): routes.py holds a row for each route app.py answers, and its
Internal API lists them first, the frame's after them, each once. Read from the source and the class: nothing is
served, nothing is asked."""
from __future__ import annotations

from pathlib import Path

from liminal_libs.apps.app import APIS_PATH, CODEBASE_PATH
from liminal_libs.internal import FRAME_ROUTES, ROUTE_WHO, literals_in, route_problems

import liminal_login.app as app_module
from liminal_login import routes
from liminal_login.app import LoginApp


def test_every_route_the_login_answers_has_its_row():
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    # the code base and its own two views are the frame's paths, narrowed here by name (CODEBASE, APIS_PATH)
    assert route_problems(routes.ROUTES, literals_in(source) | {CODEBASE_PATH, APIS_PATH}) == []
    assert LoginApp.ROUTES is routes.ROUTES
    assert {r[4] for r in routes.ROUTES} <= set(ROUTE_WHO)


def test_a_row_missing_is_found():
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    fewer = [r for r in routes.ROUTES if r[1] != "/api/signup/resend"]
    assert any("/api/signup/resend" in p for p in route_problems(fewer, literals_in(source)))


def test_its_internal_api_lists_its_own_then_the_frames(folder):
    app = LoginApp(folder, log=lambda m: None, failure_delay=0)
    try:
        inner = app.internal()
    finally:
        app.close()
    rows = inner["routes"]
    own = [(r["method"], r["path"]) for r in rows if r["own"]]
    assert own == [(r[0], r[1]) for r in routes.ROUTES] and inner["counts"]["own"] == len(routes.ROUTES) == 23
    assert rows[:len(own)] == [r for r in rows if r["own"]]  # its own first
    # the three it narrows are its own rows, said for whom; the frame's other rows follow, each once
    narrowed = {("GET", CODEBASE_PATH), ("POST", CODEBASE_PATH + "/fetch"), ("GET", APIS_PATH)}
    assert narrowed <= set(own) and {(r[0], r[1]) for r in FRAME_ROUTES} - narrowed <= {(r["method"], r["path"])
                                                                                         for r in rows if not r["own"]}
    assert len({(r["method"], r["path"]) for r in rows}) == len(rows)
    said = {(r["method"], r["path"]): r["about"] for r in rows}
    assert "local login" in said[("GET", APIS_PATH)] and "local login" in said[("GET", CODEBASE_PATH)]
