"""An account asked for with a name, an email and a password, its passkey mailed and typed back
(users.py's sign-ups, app.py's routes): the passkey is kept as a hash and never logged, five tries,
fifteen minutes, a new one on request, the first account too; without a mail account the page falls
back to the first-user form and says what to set."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection

import pytest

from liminal_libs.web import WRITE_HEADER
from liminal_login import crypto
from liminal_login.app import COOKIE
from liminal_login.users import UserStore


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


def test_a_passkey_looks_the_same_however_it_is_typed():
    code = crypto.new_code()
    assert len(code) == 9 and code[4] == "-" and all(c in crypto.CODE_ALPHABET for c in code.replace("-", ""))
    assert crypto.normal_code(code) == code.replace("-", "")
    assert crypto.normal_code(code.lower().replace("-", " ")) == code.replace("-", "")
    assert crypto.normal_code("ab0d-1xyz") == "ABODIXYZ"
    salt = crypto.new_salt()
    assert crypto.code_hash(code, salt) == crypto.code_hash(code.lower(), salt) != crypto.code_hash(crypto.new_code(), salt)


def test_a_signup_waits_for_its_passkey_in_the_users_file(folder):
    users = UserStore(folder / "users.db")
    code = users.start_signup("Ada", "Ada@Example.test ", "correct horse battery")
    waiting = users.signup("ada@example.test")
    assert waiting["name"] == "Ada" and waiting["tries"] == 0 and waiting["expiresAt"] > waiting["sentAt"]
    assert users.count() == 0 and users.signup("nobody@example.test") is None
    # the file keeps the passkey as a hash, never in the clear, and nothing of the password
    row = sqlite3.connect(str(folder / "users.db")).execute("SELECT * FROM signups").fetchone()
    blob = b"".join(v if isinstance(v, bytes) else str(v).encode() for v in row)
    assert code.encode() not in blob and code.replace("-", "").encode() not in blob and b"correct horse battery" not in blob
    # wrong passkeys spend tries; the right one makes the user, verified, and signs in with the password
    with pytest.raises(ValueError, match="4 tries left"):
        users.confirm_signup("ada@example.test", "XXXX-XXXX")
    made = users.confirm_signup("ada@example.test", code.lower())
    assert made["name"] == "Ada" and made["email"] == "ada@example.test" and made["verified"] is True
    assert users.signup("ada@example.test") is None and users.count() == 1
    user = users.verify("ada@example.test", "correct horse battery")  # by email too
    assert user is not None and user.name == "Ada" and user.verified_at is not None
    assert users.names()[0]["email"] == "ada@example.test" and users.names()[0]["verified"] is True
    # a name or an email already a user's is refused at sign-up
    with pytest.raises(ValueError, match="already"):
        users.start_signup("ada", "other@example.test", "another password")
    with pytest.raises(ValueError, match="already"):
        users.start_signup("Bob", "ADA@example.test", "another password")
    with pytest.raises(ValueError, match="email"):
        users.start_signup("Bob", "not an address", "another password")
    users.close()


def test_five_wrong_passkeys_or_the_time_drop_a_signup_and_a_new_one_can_be_asked(folder, monkeypatch):
    users = UserStore(folder / "users.db")
    users.start_signup("Bob", "bob@example.test", "another password")
    for left in (4, 3, 2, 1):
        with pytest.raises(ValueError, match=f"{left} tries left"):
            users.confirm_signup("bob@example.test", "WRONG-ONE")
    with pytest.raises(ValueError, match="last try"):
        users.confirm_signup("bob@example.test", "WRONG-ONE")
    assert users.signup("bob@example.test") is None
    with pytest.raises(ValueError, match="ask for one first"):
        users.confirm_signup("bob@example.test", "WRONG-ONE")
    # too soon for another; then a new passkey, and only it counts
    first = users.start_signup("Bob", "bob@example.test", "another password")
    with pytest.raises(ValueError, match="seconds ago"):
        users.resend_signup("bob@example.test")
    second = users.resend_signup("bob@example.test", sooner_than=0)
    assert first != second
    with pytest.raises(ValueError, match="tries left"):
        users.confirm_signup("bob@example.test", first)
    # expired: dropped, said so
    users.start_signup("Cy", "cy@example.test", "another password", minutes=0)
    with pytest.raises(ValueError, match="expired"):
        users.confirm_signup("cy@example.test", "ANY-THING")
    assert users.signup("cy@example.test") is None
    assert users.confirm_signup("bob@example.test", second)["name"] == "Bob"
    users.close()


def test_the_first_account_is_made_with_a_passkey_when_mail_is_set_up(served_mail):
    app, port, lines, mailer = served_mail
    st = _call(port, "GET", "/api/status")[1]
    assert st["users"] == 0 and st["signup"]["email"] is True and st["signup"]["host"] == "smtp.example.test"
    assert "password" not in json.dumps(st["signup"])
    # the plain first-user route is closed: a passkey is the way
    assert _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery"})[0] == 409
    status, data, _ = _call(port, "POST", "/api/signup", {"name": "Ada", "email": "ada@example.test", "password": "correct horse battery"})
    assert status == 202 and data["email"] == "a***@example.test" and data["name"] == "Ada" and data["minutes"] == 15
    to, subject, text = mailer.sent[-1]
    code = mailer.last_code()
    assert to == "ada@example.test" and subject == "Your Liminal passkey" and "Ada" in text and code in text
    assert not any(code in m for m in lines) and not any("correct horse" in m for m in lines)
    assert any("passkey went to a***@example.test" in m for m in lines)
    # wrong, then right with the password: made, verified, signed in at once
    status, data, _ = _call(port, "POST", "/api/signup/confirm", {"email": "ada@example.test", "code": "AAAA-AAAA"})
    assert status == 400 and "4 tries left" in data["error"]
    status, data, r = _call(port, "POST", "/api/signup/confirm",
                            {"email": "ada@example.test", "code": code.lower(), "password": "correct horse battery"})
    assert status == 201 and data["user"]["name"] == "Ada" and data["user"]["verified"] is True and data["token"]
    assert r.getheader("Set-Cookie").startswith(f"{COOKIE}={data['token']}")
    me = _call(port, "GET", "/api/me", token=data["token"])[1]
    assert me["email"] == "ada@example.test" and me["verified"] is True
    assert _call(port, "GET", "/api/status")[1]["users"] == 1
    # a second account the same way, confirmed without the password: made, not signed in
    _call(port, "POST", "/api/signup", {"name": "Bob", "email": "bob@example.test", "password": "another password"})
    status, data, r = _call(port, "POST", "/api/signup/confirm", {"email": "bob@example.test", "code": mailer.last_code()})
    assert status == 201 and data == {"user": {**data["user"]}} and "token" not in data and r.getheader("Set-Cookie") is None
    assert _call(port, "POST", "/api/sign-in", {"name": "bob@example.test", "password": "another password"})[0] == 200
    # a new passkey on request (not twice in a minute), and the resend of nothing
    _call(port, "POST", "/api/signup", {"name": "Cy", "email": "cy@example.test", "password": "another password"})
    status, data, _ = _call(port, "POST", "/api/signup/resend", {"email": "cy@example.test"})
    assert status == 400 and "seconds ago" in data["error"]
    assert _call(port, "POST", "/api/signup/resend", {"email": "nobody@example.test"})[0] == 400
    assert _call(port, "POST", "/api/signup", {"name": "Dee", "email": "bad", "password": "another password"})[0] == 400
    # the mail server refusing: the sign-up is told and nothing is made
    mailer.refuse = "the mail server at smtp.example.test:587 did not take the message: timed out"
    status, data, _ = _call(port, "POST", "/api/signup", {"name": "Eve", "email": "eve@example.test", "password": "another password"})
    assert status == 503 and "could not be sent" in data["error"] and "timed out" in data["error"]


def test_without_a_mail_account_the_first_user_is_made_on_the_page_and_a_signup_says_what_to_set(served):
    app, port, lines = served
    st = _call(port, "GET", "/api/status")[1]
    assert st["signup"]["email"] is False and st["signup"]["configured"] is False
    status, data, _ = _call(port, "POST", "/api/signup", {"name": "Ada", "email": "ada@example.test", "password": "correct horse battery"})
    assert status == 503 and "LIMINAL_SMTP_HOST" in data["error"] and "user add" in data["error"]
    status, data, _ = _call(port, "POST", "/api/users", {"name": "Ada", "password": "correct horse battery", "email": "ada@example.test"})
    assert status == 201 and data["email"] == "ada@example.test" and data["verified"] is False


def test_a_signup_expires_by_the_clock(folder):
    users = UserStore(folder / "users.db")
    users.start_signup("Ada", "ada@example.test", "correct horse battery", minutes=1)
    con = sqlite3.connect(str(folder / "users.db"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    con.execute("UPDATE signups SET expires_at = ?", (past,))
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="expired"):
        users.confirm_signup("ada@example.test", "XXXX-XXXX")
    users.close()
