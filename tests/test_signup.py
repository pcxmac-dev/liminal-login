"""A sign-up: the email, the six-digit code mailed to it and typed back, then the account name and
the password (users.py's sign-ups, app.py's routes): the code is kept as a hash and never logged, five
tries, fifteen minutes, a new one on request, the first account too; without a mail account the page
falls back to the first-user form and says what to set; on its own the login knows no app, and an app that
inherits it keeps its users apart. The switch that closes sign-up by email on a domain's login and the one
word that opens it (0.20.0) are here too; the Docker recipe's side of it is in test_docker_files, the
counting of wrong codes in test_throttle."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from pathlib import Path

import pytest

from liminal_libs.web import WRITE_HEADER
from liminal_login import crypto
from liminal_login.app import LoginApp, superclass_of
from liminal_login.users import UserStore, WrongCode

COOKIE = "liminal_login"  # the login's own: on its own, no app inherits it


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


def test_a_code_is_six_digits_however_it_is_typed():
    code = crypto.new_code()
    assert len(code) == 6 and code.isdigit()
    assert crypto.normal_code(f" {code[:3]}-{code[3:]} ") == code and crypto.normal_code("12 34 56 78") == "123456"
    salt = crypto.new_salt()
    assert crypto.code_hash(code, salt) == crypto.code_hash(f"{code[:3]} {code[3:]}", salt) != crypto.code_hash("000000", salt)
    assert crypto.token_hash("a") != crypto.token_hash("b") and len(crypto.new_token()) > 20


def test_a_signup_goes_email_code_then_name_and_password(folder):
    users = UserStore(folder / "users.db")
    code = users.start_signup("Ada@Example.test ")
    waiting = users.signup("ada@example.test")
    assert waiting["tries"] == 0 and waiting["verified"] is False and waiting["expiresAt"] > waiting["sentAt"]
    assert users.count() == 0 and users.signup("nobody@example.test") is None
    # the file keeps the code as a hash, never in the clear
    row = sqlite3.connect(str(folder / "users.db")).execute("SELECT * FROM signups").fetchone()
    blob = b"".join(v if isinstance(v, bytes) else str(v).encode() for v in row)
    assert code.encode() not in blob
    # wrong codes spend tries; the right one verifies the address and gives the proof for the next step
    with pytest.raises(ValueError, match="4 tries left"):
        users.verify_signup("ada@example.test", "000000")
    with pytest.raises(ValueError, match="not been verified"):
        users.complete_signup("ada@example.test", "no-token", "Ada", "correct horse battery")
    token = users.verify_signup("ada@example.test", f"{code[:3]} {code[3:]}")
    assert users.signup("ada@example.test")["verified"] is True
    with pytest.raises(ValueError, match="not been verified"):
        users.complete_signup("ada@example.test", "wrong-token", "Ada", "correct horse battery")
    with pytest.raises(ValueError, match="at least 8"):
        users.complete_signup("ada@example.test", token, "Ada", "short")
    user = users.complete_signup("ada@example.test", token, "Ada", "correct horse battery")
    assert user.name == "Ada" and user.email == "ada@example.test" and user.verified_at is not None and len(user.vault_key) == 32
    assert users.signup("ada@example.test") is None and users.count() == 1
    assert users.verify("ada@example.test", "correct horse battery").name == "Ada"  # by email too
    assert users.names()[0]["email"] == "ada@example.test" and users.names()[0]["verified"] is True
    # an address that is a user's already is refused at sign-up; a name at the last step
    with pytest.raises(ValueError, match="sign in instead"):
        users.start_signup("ADA@example.test")
    with pytest.raises(ValueError, match="email"):
        users.start_signup("not an address")
    t2 = users.verify_signup("bob@example.test", users.start_signup("bob@example.test"))
    with pytest.raises(ValueError, match="already"):
        users.complete_signup("bob@example.test", t2, "ada", "another password")
    assert users.complete_signup("bob@example.test", t2, "Bob", "another password").name == "Bob"
    users.close()


def test_five_wrong_codes_spend_a_code_the_time_drops_a_signup_and_a_new_code_can_be_asked(folder):
    """Five wrong codes spend a code: it is compared no more, the right one neither, and its sign-up is kept, so no new
    code follows for a minute from that last try, however late it came (0.20.0, the last check of LOG-C1's fix: the
    sign-up was dropped at the fifth wrong code and begun again at once, five more tries with each new code and no
    minute between them). A wrong code is told apart from the other refusals (WrongCode): it is the one the app
    counts."""
    users = UserStore(folder / "users.db")

    def at(seconds: float) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")

    def as_if(**columns) -> None:
        """The sign-up's row as if time had passed."""
        con = sqlite3.connect(str(folder / "users.db"))
        con.execute(f"UPDATE signups SET {', '.join(f'{k} = ?' for k in columns)} WHERE email = ?",
                    (*columns.values(), "bob@example.test"))
        con.commit()
        con.close()

    code = users.start_signup("bob@example.test")
    wrong = "000000" if code != "000000" else "111111"
    for left in (4, 3, 2, 1):
        with pytest.raises(WrongCode, match=f"{left} tries left"):
            users.verify_signup("bob@example.test", wrong)
    # the last try comes late: the code went out over a minute ago, and has twenty seconds left to live
    as_if(sent_at=at(-61), expires_at=at(20))
    with pytest.raises(WrongCode, match="last try for that code: a new one can be sent in 60 seconds") as last:
        users.verify_signup("bob@example.test", wrong)
    waiting = users.signup("bob@example.test")  # kept, its tries spent: its minute starts at that try, and it lives it
    assert (waiting["tries"], waiting["verified"]) == (5, False) and waiting["sentAt"] >= at(-3) and waiting["expiresAt"] >= at(55)
    for typed in (wrong, code):  # no longer compared: not a guess, and the right code comes too late
        with pytest.raises(ValueError, match="the tries of that code are spent: a new one can be sent 60 seconds after") as refused:
            users.verify_signup("bob@example.test", typed)
        assert not isinstance(refused.value, WrongCode)
    # the page lets go of a sign-up on the words of one that is gone (login.js); a spent code's keep it there, with
    # its "Send it again"
    page = (Path(__file__).resolve().parents[1] / "src" / "liminal_login" / "static" / "login.js").read_text(encoding="utf-8")
    assert "if (/ask for a new one|start one first/.test(err.message)) { signup = null; }" in page
    assert not any(re.search("ask for a new one|start one first", str(e.value)) for e in (last, refused))
    assert users.signup("bob@example.test")["tries"] == 5  # asked again, nothing changed
    for again in (users.start_signup, users.resend_signup):  # no new code at once, begun again or sent again
        with pytest.raises(ValueError, match="the tries of the last code are spent, and a new one goes out no sooner than 60 "
                                             "seconds after the last of them"):
            again("bob@example.test")
    with pytest.raises(ValueError, match="start one first"):
        users.verify_signup("nobody@example.test", "000000")
    # a minute after that last try: a new code, and only it counts; too soon for another
    as_if(sent_at=at(-61))
    first = users.start_signup("bob@example.test")
    assert users.signup("bob@example.test")["tries"] == 0
    with pytest.raises(ValueError, match="seconds ago"):
        users.resend_signup("bob@example.test")
    second = users.resend_signup("bob@example.test", sooner_than=0)
    assert first != second or True  # (a million codes: the same twice is possible, and then both count)
    if first != second:
        with pytest.raises(ValueError, match="tries left"):
            users.verify_signup("bob@example.test", first)
    assert users.verify_signup("bob@example.test", second)
    # expired: dropped, said so
    users.start_signup("cy@example.test", minutes=0)
    with pytest.raises(ValueError, match="expired"):
        users.verify_signup("cy@example.test", "000000")
    assert users.signup("cy@example.test") is None
    # a sign-up already verified is not wiped by wrong codes sent after it, as it was at the fifth: its proof holds
    mailed = users.start_signup("di@example.test")
    token = users.verify_signup("di@example.test", mailed)
    for _ in range(6):
        with pytest.raises(ValueError, match="tries left|last try|are spent"):
            users.verify_signup("di@example.test", "000000" if mailed != "000000" else "111111")
    assert users.complete_signup("di@example.test", token, "Di", "correct horse battery").name == "Di"
    users.close()


def test_a_verified_signup_left_too_long_starts_again(folder):
    users = UserStore(folder / "users.db")
    token = users.verify_signup("ada@example.test", users.start_signup("ada@example.test"))
    con = sqlite3.connect(str(folder / "users.db"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    con.execute("UPDATE signups SET expires_at = ?", (past,))
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="took too long"):
        users.complete_signup("ada@example.test", token, "Ada", "correct horse battery")
    assert users.signup("ada@example.test") is None
    users.close()


def test_the_first_account_is_made_with_a_code_when_mail_is_set_up(served_mail):
    app, port, lines, mailer = served_mail
    st = _call(port, "GET", "/api/status")[1]
    assert st["users"] == 0 and st["signup"]["email"] is True and st["signup"]["host"] == "smtp.example.test"
    assert st["for"] is None and st["forTitle"] == "Liminal" and "password" not in json.dumps(st["signup"])
    # a domain's login: its users at the domain, in the domain's folder
    assert st["scope"]["kind"] == "domain" and st["scope"]["domain"] == "example.test" and app.dir == app.root / "example.test"
    status, data, _ = _call(port, "POST", "/api/signup", {"email": "ada@elsewhere.test"})
    assert status == 400 and "example.test" in data["error"]
    # the plain first-user route is closed: a code is the way
    assert _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})[0] == 409
    status, data, _ = _call(port, "POST", "/api/signup", {"email": "ada@example.test"})
    assert status == 202 and data["email"] == "a***@example.test" and data["minutes"] == 15
    # the mail server's word that it took the message, kept for the page and the status
    assert data["sent"] == {"to": "a***@example.test", "host": "smtp.example.test", "port": 587, "code": 250,
                            "reply": "2.0.0 OK queued as fake-1", "at": "2026-11-06T21:00:00+00:00", "messageId": "<fake-1@example.test>",
                            "signed": ""}
    assert _call(port, "GET", "/api/status")[1]["signup"]["lastSent"] == data["sent"]
    assert any("answered 250 2.0.0 OK queued as fake-1" in m for m in lines)
    to, subject, text = mailer.sent[-1]
    code = mailer.last_code()
    assert to == "ada@example.test" and subject == "Your Liminal code" and "a Liminal account" in text and code in text
    assert not any(code in m for m in lines)
    assert any("sign-up began for a***@example.test" in m for m in lines)
    # the code, wrong then right; then the name and the password: made, verified, signed in at once
    status, data, _ = _call(port, "POST", "/api/signup/verify", {"email": "ada@example.test", "code": "000000"})
    assert status == 400 and "4 tries left" in data["error"]
    status, data, _ = _call(port, "POST", "/api/signup/verify", {"email": "ada@example.test", "code": f"{code[:3]}-{code[3:]}"})
    assert status == 200 and data["token"] and data["email"] == "a***@example.test"
    token = data["token"]
    status, data, _ = _call(port, "POST", "/api/signup/complete", {"email": "ada@example.test", "token": "wrong", "name": "Ada", "password": "correct horse battery"})
    assert status == 400 and "not been verified" in data["error"]
    status, data, r = _call(port, "POST", "/api/signup/complete",
                            {"email": "ada@example.test", "token": token, "name": "Ada", "password": "correct horse battery"})
    assert status == 201 and data["user"]["name"] == "Ada" and data["user"]["verified"] is True and data["token"]
    assert r.getheader("Set-Cookie").startswith(f"{COOKIE}={data['token']}")
    me = _call(port, "GET", "/api/me", token=data["token"])[1]
    assert me["email"] == "ada@example.test" and me["verified"] is True and me["for"] is None
    assert _call(port, "GET", "/api/status")[1]["users"] == 1
    assert _call(port, "POST", "/api/sign-in", {"name": "ada@example.test", "password": "correct horse battery"})[0] == 200
    # a new code on request (not twice in a minute), and the resend of nothing
    _call(port, "POST", "/api/signup", {"email": "cy@example.test"})
    status, data, _ = _call(port, "POST", "/api/signup/resend", {"email": "cy@example.test"})
    assert status == 400 and "seconds ago" in data["error"]
    assert _call(port, "POST", "/api/signup/resend", {"email": "nobody@example.test"})[0] == 400
    assert _call(port, "POST", "/api/signup", {"email": "bad"})[0] == 400
    assert _call(port, "POST", "/api/signup", {"email": "ada@example.test"})[0] == 400  # a user's already
    # the mail server refusing: the sign-up is told and nothing is made
    mailer.refuse = "the mail server at smtp.example.test:587 did not take the message: timed out"
    status, data, _ = _call(port, "POST", "/api/signup", {"email": "eve@example.test"})
    assert status == 503 and "could not be sent" in data["error"] and "timed out" in data["error"] and "nothing waits" in data["error"]
    # the sign-up was dropped with the refusal: nothing waits for a code that never went out
    assert app.users.signup("eve@example.test") is None and _call(port, "POST", "/api/signup/resend", {"email": "eve@example.test"})[0] == 400
    assert any("the sign-up dropped" in m for m in lines)


def test_without_a_mail_account_the_first_user_is_made_on_the_page_and_a_signup_says_what_to_set(served):
    app, port, lines = served
    st = _call(port, "GET", "/api/status")[1]
    assert st["signup"]["email"] is False and st["signup"]["configured"] is False
    status, data, _ = _call(port, "POST", "/api/signup", {"email": "ada@example.test"})
    assert status == 503 and "local" in data["error"] and "user add" in data["error"] and st["scope"]["kind"] == "local"
    status, data, _ = _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery", "email": "ada@example.test"})
    assert status == 201 and data["email"] == "ada@example.test" and data["verified"] is False


def test_on_its_own_the_login_knows_no_app_and_an_app_that_inherits_it_keeps_its_users_apart(folder, monkeypatch):
    """0.13.0 (the user, 2026-11-10: "the log-in app should not point to platform, integrator or charts, it should be
    standalone"; "when its inherited it can point to it's superclass, charts, platform, or integrator"): on its own, its
    users in its own folder under its own cookie, the page naming it by its scope; inherited, the superclass's users in a
    folder of their own under their own cookie, named as that app said. No app is known here by name."""
    own = LoginApp(folder, log=lambda m: None, failure_delay=0)
    charts = LoginApp(folder, log=lambda m: None, failure_delay=0, superclass="charts")
    platform = LoginApp(folder, log=lambda m: None, failure_delay=0,
                        superclass=superclass_of("platform", "The Platform", "http://127.0.0.1:8775/"))
    try:
        assert own.superclass is None and own.dir == folder and own.cookie_name == "liminal_login" and own.TITLE == "Login"
        assert own.title_for == "Liminal" and own.describe()["for"] is None and own.describe()["superclass"] is None
        assert charts.dir == folder / "charts" and charts.cookie_name == "liminal_login_charts" and charts.TITLE == "Login: Liminal Charts"
        assert platform.dir == folder / "platform" and platform.title_for == "The Platform" and platform.tray().title == "Login: The Platform"
        assert platform.describe()["superclass"] == {"name": "platform", "title": "The Platform", "url": "http://127.0.0.1:8775"}
        assert own.port() == charts.port() == platform.port() == 8795  # the app that starts it says its port (--port)
        own.users.create("Ada", "correct horse battery")
        assert own.users.count() == 1 and charts.users.count() == 0 and platform.users.count() == 0  # apart
        charts.users.create("Ada", "another password")  # the same name is free in another
        assert charts.users.verify("Ada", "correct horse battery") is None
        # the superclass as the app that starts the login says it, in its environment (liminal_libs.apps.inherited_by)
        monkeypatch.setenv("LIMINAL_LOGIN_FOR", "integrator")
        monkeypatch.setenv("LIMINAL_LOGIN_FOR_URL", "http://127.0.0.1:8785/")
        sup = superclass_of()
        assert (sup.name, sup.title, sup.url) == ("integrator", "Liminal Integrator", "http://127.0.0.1:8785")
        inherited = LoginApp(folder, log=lambda m: None)
        assert inherited.namespace == "integrator" and inherited.dir == folder / "integrator"
        inherited.close()
        for bad in ("Not A Name!", "users", "logs", "dkim"):  # a short name, never one of the login's own folders
            with pytest.raises(ValueError):
                superclass_of(bad)
        with pytest.raises(ValueError, match="http"):
            superclass_of("charts", url="file:///C:/elsewhere")
        monkeypatch.delenv("LIMINAL_LOGIN_FOR")
        assert superclass_of() is None
    finally:
        own.close()
        charts.close()
        platform.close()


def test_a_domain_login_takes_signups_only_with_an_email_server(folder, monkeypatch):
    # the user, 2026-11-06: "only allow signup if the login app is tied to an smtp server"; "domain w/ email
    # server in mail record (lookup) or specified if none in the domain lookup"
    from liminal_libs.apps import Scope
    from liminal_libs.mail import MailSettings

    from conftest import FakeMailer
    from liminal_login import app as app_mod

    app = LoginApp(folder, log=lambda m: None, failure_delay=0, mailer=FakeMailer(configured=False), scope=Scope.for_domain("example.test"))
    try:
        assert app.describe()["scope"]["kind"] == "domain" and app.dir == folder / "example.test"
        assert not app.signup_open() and "not set up" in app.signup_closed_why()
        app.mailer.settings = MailSettings(host="direct", sender="login@example.test")  # the domain's own mail record
        monkeypatch.setattr(app_mod, "mx_records", lambda d: [] if d == "example.test" else None)
        assert not app.signup_open() and "none in its mail record" in app.signup_closed_why()
        app._exchangers = None
        monkeypatch.setattr(app_mod, "mx_records", lambda d: ["mx.example.test"])
        assert app.signup_open() and app.signup_closed_why() == ""
        app.mailer.settings = MailSettings(host="127.0.0.1", port=1025, sender="login@example.test")  # a server named
        monkeypatch.setattr(app_mod, "mx_records", lambda d: [])
        app._exchangers = None
        assert app.signup_open()
        local = LoginApp(folder, log=lambda m: None, mailer=FakeMailer(configured=True))
        try:
            assert local.describe()["scope"]["kind"] == "local" and not local.signup_open() and "local" in local.signup_closed_why()
            assert local.dir == folder
        finally:
            local.close()
    finally:
        app.close()


def test_only_the_files_own_word_opens_sign_up_by_email_once_something_closes_it(folder, tmp_path, monkeypatch):
    """The switch (0.20.0; the user, 2026-11-25: "Closed unless turned on"): `signup` under the file's [login]. `open`
    opens sign-up by email, which still needs its email server; `closed`, or any other word, closes it; and where the
    file has no such line, so does whatever the one who made the login was told (LIMINAL_LOGIN_SIGNUP, which the
    command line hands on and which never opens). With neither it is as it always was (the test above). Closed, it
    says how it is opened and asks for no mail record. A local login has no sign-up by email whatever is said."""
    from dataclasses import replace

    from liminal_libs.apps import Scope

    from conftest import FakeMailer
    from liminal_login import app as app_mod
    from liminal_login import cli

    monkeypatch.setattr(app_mod, "mx_records", lambda d: pytest.fail("no mail record is asked for"))
    cfg = tmp_path / "liminal-login.cfg"

    def made(line, told, scope_line="scope = https://example.test", scope=None):
        cfg.write_text(f"[login]\n{scope_line}\ntitle = Somewhere\n" + (f"{line}\n" if line is not None else "") + "\n[mail]\n",
                       encoding="utf-8")
        app = LoginApp(folder, log=lambda m: None, mailer=FakeMailer(configured=True), scope=scope or Scope.read(cfg), signup=told)
        try:
            return app.signup, app.signup_closed_why(), app.signup_status()["email"], app.mail_words()
        finally:
            app.close()

    how = "`signup = open` under [login] in its liminal-login.cfg opens it"
    assert all(how in why and "`liminal-login user add NAME`" in why
               for why in (app_mod.SIGNUP_CLOSED_WHY, app_mod.SIGNUP_NO_WORD_WHY, app_mod.SIGNUP_UNREAD_WHY))
    opened = ("open", "", True, "passkeys through smtp.example.test")
    closed = ("closed", app_mod.SIGNUP_CLOSED_WHY, False, "sign-up by email closed (`signup = open` in liminal-login.cfg opens it): no passkeys")
    no_word = ("closed", app_mod.SIGNUP_NO_WORD_WHY, False, closed[3])
    as_it_was = (None, "", True, opened[3])
    for told in (None, "closed", "open"):  # whatever was told, the file's own word decides
        assert made("signup = open", told) == opened and made("Signup =  OPEN  ; ours", told) == opened, told
        assert made("signup = closed", told) == closed, told
        assert made("signup = opne", told) == no_word and made("signup =", told) == no_word, told
    # no such line: anything told closes it, `open` too (it never opens); nothing told, and it is as it was
    assert made(None, "closed") == closed and made(None, "open") == closed
    assert made(None, None) == as_it_was and made(None, " ") == as_it_was
    # a login made in code, with no file: what it is told, or as it was
    in_code = Scope.for_domain("example.test")
    assert made(None, "closed", scope=in_code) == closed and made(None, None, scope=in_code) == as_it_was
    # LIMINAL_LOGIN_SIGNUP is the command line's alone, as LIMINAL_LOGIN_SCOPE is: left set on a machine, a login made
    # in code does not read it; the command line does, and hands on `closed` whatever it says
    monkeypatch.setenv("LIMINAL_LOGIN_SIGNUP", "closed")
    assert made(None, None) == as_it_was and made(None, None, scope=in_code) == as_it_was and cli.signup_told() == "closed"
    assert cli.signup_told({"LIMINAL_LOGIN_SIGNUP": "open"}) == "closed"
    assert cli.signup_told({}) is None and cli.signup_told({"LIMINAL_LOGIN_SIGNUP": " "}) is None
    monkeypatch.delenv("LIMINAL_LOGIN_SIGNUP")
    # its file gone since it was read: closed, said
    gone = replace(Scope.read(cfg), path=tmp_path / "gone" / "liminal-login.cfg")
    assert made(None, None, scope=gone) == ("closed", app_mod.SIGNUP_UNREAD_WHY, False, closed[3])
    # a local login: no sign-up by email, whatever its file and the command line say
    for line, told in (("signup = open", None), ("signup = closed", "closed"), ("signup = opne", "open")):
        word, why, email, words = made(line, told, scope_line=f"scope = {tmp_path.as_uri()}")
        assert (word, email, words) == (None, False, "a local login: no email") and "this login is local" in why


def test_a_domains_login_says_how_its_codes_go_out(served_mail):
    """0.12.1: the start-up line and the status name the mail account for a domain's login, which sends the codes; a
    local login names none (test_app)."""
    app, port, lines, mailer = served_mail
    st = _call(port, "GET", "/api/status")[1]
    assert st["signup"]["local"] is False and st["signup"]["email"] is True
    assert st["signup"]["host"] == "smtp.example.test" and st["signup"]["sender"] == "liminal@example.test"
    assert app.mail_words() == "passkeys through smtp.example.test"


def test_a_signup_is_begun_again_only_as_a_new_code_would_be_never_over_a_verified_one(folder):
    """The review of 2026-11-21, item 26: a sign-up begun again replaced the one under way at once, with no time check,
    so anyone could send an address codes as fast as they liked and wipe a sign-up already verified, its proof then
    worth nothing. Now a start is refused as a resend is (not twice in a minute), and never replaces a verified one
    until it has expired."""
    users = UserStore(folder / "users.db")
    first = users.start_signup("ada@example.test")
    with pytest.raises(ValueError, match="seconds ago"):  # at once: refused, nothing changed
        users.start_signup("ada@example.test")
    token = users.verify_signup("ada@example.test", first)  # the first code still counts
    with pytest.raises(ValueError, match="verified already"):  # however long after the code went out
        users.start_signup("ada@example.test", sooner_than=0)
    with pytest.raises(ValueError, match="verified already"):
        users.resend_signup("ada@example.test", sooner_than=0)
    assert users.complete_signup("ada@example.test", token, "Ada", "correct horse battery").name == "Ada"  # its proof holds
    # one verified and left to expire begins again; one not verified, its code older than the limit, gets a new code
    users.verify_signup("bo@example.test", users.start_signup("bo@example.test"))
    con = sqlite3.connect(str(folder / "users.db"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    con.execute("UPDATE signups SET expires_at = ? WHERE email = ?", (past, "bo@example.test"))
    con.commit()
    con.close()
    again = users.start_signup("bo@example.test")
    assert users.signup("bo@example.test")["verified"] is False and users.verify_signup("bo@example.test", again)
    users.start_signup("cy@example.test")
    newer = users.start_signup("cy@example.test", sooner_than=0)
    assert users.verify_signup("cy@example.test", newer)
    users.close()


def test_a_second_signup_for_an_address_within_the_limit_sends_nothing(served_mail):
    """The same, through the page: the second start is a 400 and no second message goes out."""
    app, port, lines, mailer = served_mail
    assert _call(port, "POST", "/api/signup", {"email": "ada@example.test"})[0] == 202
    code = mailer.last_code()
    status, data, _ = _call(port, "POST", "/api/signup", {"email": "ada@example.test"})
    assert status == 400 and "seconds ago" in data["error"] and len(mailer.sent) == 1
    assert _call(port, "POST", "/api/signup/verify", {"email": "ada@example.test", "code": code})[0] == 200
