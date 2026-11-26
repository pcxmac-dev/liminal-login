"""The login's right-hand menu by the library's page standard (0.20.2; Monday list item 31; liminal-libs docs/PAGES.md):
the view picked in the list at the panel's top, the row picked in the middle told in full under it, through the
library's side.js. A pair picked never tells its value. Text assertions on the page's files; the script itself is run
in headless Edge on stand-ins."""
from __future__ import annotations

from liminal_login.app import LoginApp

JS = (LoginApp.STATIC / "login.js").read_text(encoding="utf-8")
HTML = (LoginApp.STATIC / "index.html").read_text(encoding="utf-8")


def body(head: str) -> str:
    at = JS.index(head)
    depth, i = 0, JS.index("{", at)
    for j in range(i, len(JS)):
        depth += {"{": 1, "}": -1}.get(JS[j], 0)
        if depth == 0:
            return JS[at:j + 1]
    raise AssertionError(head)


def test_side_js_after_the_icons_and_before_the_page():
    assert HTML.index('src="icons.js"') < HTML.index('src="side.js"') < HTML.index('src="login.js"')


def test_without_side_js_the_side_is_drawn_whole_as_before():
    assert "const S = window.LiminalSide || null;" in JS
    side = body("function setSide(scope, html) {")
    assert "if (!S) { el.innerHTML = html; return; }" in side and "sidePanel.tool(scope, html);" in side
    assert "${S ? '' : side}</aside>" in JS  # the columns' side whole without it
    assert "side.innerHTML = " not in JS  # every side goes through setSide
    assert "if (!S) return '';" in body("const pickAttr = (key, spec) => {")


def test_the_scopes_are_the_standards_login_tools():
    from liminal_libs.ui import standard

    tools = set(next(g for g in standard.groups("login") if g["id"] == "tool")["tools"])
    used = {"account" if "'login:account'" in JS else "", "codebase" if "scope: 'login:codebase'" in JS else "",
            "plugin" if "`login:plugin:${p.name}/${shown}`" in JS else "", "own" if "`login:own:${ownTab}`" in JS else ""}
    assert used == tools


def test_a_pair_picked_never_tells_its_value():
    spec = body("function pairSpec(p, asking) {")
    assert "p.value" not in spec and "['Value', 'masked: Reveal in its row shows it there']" in spec
    # its spec is made of what the page was given, never read from its cells (a value revealed in its row stays there)
    assert "pickAttr(`pair:${p.name}`, pairSpec(p, asking(p.name)))" in JS
    rows = body("function sideRows() {")
    assert "pickSpecs.get(key) || S.fromRow(tr)" in rows  # every pair's key has its spec: fromRow never reads a pair row
    assert "pickSpecs.clear();" in body("async function render() {")


def test_the_known_pairs_and_a_plugins_tables_pick_too():
    assert "pickAttr(`known:${k.plugin}|${k.name}`, knownSpec(k))" in JS
    page = body("function pageHtml(d) {")
    assert "t.pick === false ? '' : pickAttr(keyOf(r, ri), detailOf(ri))" in page and "pickSpecs.clear();" in page
    assert "sideRows();  // 0.20.2: a row of its tables told in full under the tool" in JS


def test_codebase_is_mounted_with_the_panel():
    assert "panel: sidePanel, scope: 'login:codebase' });" in JS

def test_a_row_without_details_is_told_anew_from_the_row_drawn_now():
    """A row with no details, redrawn after an act, is still the pick: told by its cells, not marked gone."""
    rows = body("function sideRows() {")
    assert "sidePanel.refresh(pickFind);" in rows
    find = body("function pickFind(key) {")
    assert "if (pickSpecs.has(key)) return pickSpecs.get(key);" in find
    assert "x.dataset.pick === key" in find and "return tr ? S.fromRow(tr) : null;" in find
