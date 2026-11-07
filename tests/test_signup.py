"""A sign-up: the email, the six-digit code mailed to it and typed back, then the account name and
the password (users.py's sign-ups, app.py's routes): the code is kept as a hash and never logged, five
tries, fifteen minutes, a new one on request, the first account too; without a mail account the page
falls back to the first-user form and says what to set; each login serves one app, its namespace."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection

import pytest

from liminal_libs.web import WRITE_HEADER
from liminal_login import crypto
from liminal_login.app import LoginApp, namespace_of
from liminal_login.users import UserStore

COOKIE = "liminal_login_charts"


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


def test_five_wrong_codes_or_the_time_drop_a_signup_and_a_new_code_can_be_asked(folder):
    users = UserStore(folder / "users.db")
    users.start_signup("bob@example.test")
    for left in (4, 3, 2, 1):
        with pytest.raises(ValueError, match=f"{left} tries left"):
            users.verify_signup("bob@example.test", "000000")
    with pytest.raises(ValueError, match="last try"):
        users.verify_signup("bob@example.test", "000000")
    assert users.signup("bob@example.test") is None
    with pytest.raises(ValueError, match="start one first"):
        users.verify_signup("bob@example.test", "000000")
    # too soon for another; then a new code, and only it counts
    first = users.start_signup("bob@example.test")
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
    assert st["for"] == "charts" and st["forTitle"] == "Liminal Charts" and "password" not in json.dumps(st["signup"])
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
    assert to == "ada@example.test" and subject == "Your Liminal Charts code" and "Liminal Charts" in text and code in text
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
    assert me["email"] == "ada@example.test" and me["verified"] is True and me["for"] == "charts"
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
    assert status == 503 and "LIMINAL_SMTP_HOST" in data["error"] and "user add" in data["error"]
    status, data, _ = _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery", "email": "ada@example.test"})
    assert status == 201 and data["email"] == "ada@example.test" and data["verified"] is False


def test_each_login_serves_one_app_in_its_own_namespace(folder, monkeypatch):
    charts = LoginApp(folder, log=lambda m: None, failure_delay=0, namespace="charts")
    integrator = LoginApp(folder, log=lambda m: None, failure_delay=0, namespace="integrator")
    try:
        assert charts.dir == folder / "charts" and integrator.dir == folder / "integrator"
        assert charts.PORT == 8795 and integrator.PORT == 8796 and charts.port() == 8795 and integrator.port() == 8796
        assert charts.cookie_name == "liminal_login_charts" and integrator.cookie_name == "liminal_login_integrator"
        assert charts.TITLE == "Login: Liminal Charts" and integrator.title_for == "Liminal Integrator"
        assert charts.describe()["for"] == "charts" and integrator.tray().title == "Login: Liminal Integrator"
        charts.users.create("Ada", "correct horse battery")
        assert charts.users.count() == 1 and integrator.users.count() == 0  # the same name is free in the other
        integrator.users.create("Ada", "another password")
        assert integrator.users.verify("Ada", "correct horse battery") is None
        monkeypatch.setenv("LIMINAL_LOGIN_FOR", "integrator")
        assert namespace_of() == "integrator" and LoginApp(folder, log=lambda m: None).namespace == "integrator"
        with pytest.raises(ValueError):
            namespace_of("Not A Name!")
        other = LoginApp(folder, log=lambda m: None, namespace="platform")
        assert other.PORT == 8795 and other.title_for == "Liminal Platform" and other.dir == folder / "platform"
        other.close()
    finally:
        charts.close()
        integrator.close()
