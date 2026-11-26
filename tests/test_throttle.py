"""Sign-ins throttled (throttle.py; LOG-C1, 2026-11-23): the failed ones counted in memory by where they came from and by
the name tried; past a limit within the window a sign-in is answered 429 at once, before any key is derived, until the
oldest failure is a window old. Counted apart for the machine itself and for what a front hands on, so nobody who
reaches the front keeps anyone at the machine out, and the secret user's way in at the machine is never held back.
Bounded: so many counters at the most, each holding no more than its limit. A clock of the test's own; the app on a
free port in a thread; nothing is sent anywhere.

After the review of LOG-C1's fix (2026-11-25): a try is counted before its key is derived and taken back unless it
failed, so sign-ins sent together are held to the limits; the keys derived at once are bounded; another login's user
is counted once however their domain is typed; and a host typed in a name is never an address, so the login never asks
itself as a program at its own machine. What is about several arriving together is tried by its order (the first ones'
keys held by a stand-in while the next is asked), never by luck.

After its last check (2026-11-25): a sign-up's wrong codes are counted in the same counts, by where they came from and
by the address the code was mailed to; a new code gives no tries back, and none follows a spent one at once."""
from __future__ import annotations

import json
import threading
import urllib.error
from http.client import HTTPConnection
from types import SimpleNamespace

from liminal_libs import web
from liminal_libs.web import WRITE_HEADER
from liminal_login.throttle import Throttle


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_failures_past_a_limit_wait_until_the_oldest_is_a_window_old():
    clock = Clock(0.0)
    t = Throttle(window=100, per_peer=4, per_name=2, kept=100, clock=clock)
    assert t.wait("away", "198.51.100.7", "ada") == 0.0
    assert t.tried("away", "198.51.100.7", "ada") == (0.0, 0.0)  # tried, counted then; it failed, so it stays
    clock.now = 10.0
    assert t.tried("away", "198.51.100.7", " ADA ") == (0.0, 10.0)  # its name's limit: a name as typed, case and spaces aside
    assert t.wait("away", "198.51.100.7", "Ada") == 90.0 and t.wait("away", "203.0.113.5", "ada") == 90.0  # from anywhere
    assert t.tried("away", "203.0.113.5", "ada") == (90.0, None) and len(t) == 2  # not tried, and nothing counted for it
    assert t.wait("here", "127.0.0.1", "ada") == 0.0  # the machine's own are counted apart
    assert t.wait("away", "198.51.100.7", "bob") == 0.0  # the address is still under its own limit
    clock.now = 100.0
    assert t.wait("away", "198.51.100.7", "ada") == 0.0  # the oldest is a window old: tried again
    assert t.tried("away", "198.51.100.7", "ada") == (0.0, 100.0) and t.wait("away", "198.51.100.7", "ada") == 10.0
    clock.now = 110.0
    assert t.wait("away", "198.51.100.7", "ada") == 0.0
    # an address's limit: four failures from it, whatever the names, and it waits for any name
    t2 = Throttle(window=100, per_peer=4, per_name=10, clock=clock)
    for name in ("a", "b", "c", "d"):
        assert t2.tried("away", "198.51.100.7", name) == (0.0, 110.0)
    assert t2.tried("away", "198.51.100.7", "someone else") == (100.0, None)
    assert t2.wait("away", "198.51.100.7", "someone else") == 100.0 and t2.wait("away", "203.0.113.5", "a") == 0.0


def test_a_try_is_counted_when_it_is_made_and_taken_back_unless_it_failed():
    """Counted before its key is derived, so the next to arrive finds it though nothing has failed yet; taken back, by
    when it was counted, when its password was right or nothing said it was wrong; one that failed stays."""
    clock = Clock(0.0)
    t = Throttle(window=100, per_peer=4, per_name=2, clock=clock)
    assert t.tried("away", "198.51.100.7", "ada") == (0.0, 0.0)
    clock.now = 10.0
    assert t.tried("away", "203.0.113.5", "ada") == (0.0, 10.0)  # two being tried: the name's limit
    assert t.tried("away", "192.0.2.1", "ada") == (90.0, None) and len(t) == 3  # a third waits, nothing counted for it
    t.forget("away", "203.0.113.5", "ada", 10.0)  # the second's password was right
    assert t.wait("away", "192.0.2.1", "ada") == 0.0 and len(t) == 2  # and its address's counter went with its one time
    t.forget("away", "203.0.113.5", "ada", 10.0)  # taken back twice: nothing more goes
    assert t.tried("away", "192.0.2.1", "ada") == (0.0, 10.0) and t.tried("away", "192.0.2.1", "ada") == (90.0, None)
    t.forget("away", "192.0.2.1", "ada", 10.0)
    t.forget("away", "198.51.100.7", "ada", 0.0)
    assert len(t) == 0  # nothing failed: nothing is left
    # the keys derived at once: a gate for each place, of `at_once` turns
    gated = Throttle(at_once=2)
    here, away = gated.deriving("here"), gated.deriving("away")
    assert here is gated.deriving("here") and here is not away
    assert away.acquire(blocking=False) and away.acquire(blocking=False) and not away.acquire(blocking=False)
    assert here.acquire(blocking=False)  # a front's being full keeps nobody at the machine waiting


def test_the_counts_are_bounded_and_kept_in_memory_alone():
    clock = Clock(0.0)
    t = Throttle(window=1000, per_peer=3, per_name=3, kept=6, clock=clock)
    for i in range(50):  # fifty addresses and names: six counters at the most, the ones touched longest ago dropped
        clock.now = float(i)
        assert t.tried("away", f"10.0.0.{i}", f"name{i}") == (0.0, float(i))
        assert len(t) <= 6
    assert t.wait("away", "10.0.0.49", "x") == 0.0 and len(t) == 6
    assert {k[2] for k in t._counts} == {"10.0.0.47", "name47", "10.0.0.48", "name48", "10.0.0.49", "name49"}
    for _ in range(40):  # one name tried forty times: its counter holds three times, no more
        t.tried("away", "10.0.0.1", "ada")
    assert all(len(times) <= 3 for times in t._counts.values()) and t.tried("away", "10.0.0.1", "ada")[1] is None
    assert len(t._keys("away", "x", "n" * 10_000)[1][2]) == 254  # a long name typed is counted by its start


def _call(port, method, path, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=headers or {})
        r = conn.getresponse()
        raw = r.read()
    finally:
        conn.close()
    return r.status, (json.loads(raw) if raw else None), r


def _front(port, address="198.51.100.7"):
    """A write as the front hands it on: its mark, and the address it was reached from."""
    return {"Host": f"127.0.0.1:{port}", "Sec-Fetch-Site": "same-origin", web.FRONT_HEADER: "1", "X-Forwarded-For": address,
            "X-Forwarded-Proto": "https", "Content-Type": "application/json", WRITE_HEADER: "1"}


def _here(port):
    """A write a program on this machine sends."""
    return {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", WRITE_HEADER: "1"}


def test_sign_ins_are_throttled_and_the_front_never_keeps_anyone_at_the_machine_out(served):
    app, port, lines = served
    clock = Clock()
    app.throttle = Throttle(window=60, per_peer=5, per_name=3, clock=clock)
    app.users.create("Ada", "correct horse battery")
    derived: list = []
    verify = app.users.verify
    app.users.verify = lambda who, password: derived.append(who) or verify(who, password)  # each key derived, noted
    front = {"Host": f"127.0.0.1:{port}", "Sec-Fetch-Site": "same-origin", web.FRONT_HEADER: "1",
             "X-Forwarded-For": "198.51.100.7", "X-Forwarded-Proto": "https", "Content-Type": "application/json",
             WRITE_HEADER: "1"}
    here = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", WRITE_HEADER: "1"}
    wrong = {"name": "ada", "password": "a wrong password"}
    right = {"name": "ADA", "password": "correct horse battery"}
    for _ in range(3):
        assert _call(port, "POST", "/api/sign-in", wrong, front)[0] == 401
    status, data, r = _call(port, "POST", "/api/sign-in", right, front)  # the name's limit: even the right password waits
    assert status == 429 and r.getheader("Retry-After") == "60" and data["error"] == "too many failed sign-ins: try again in 60 s"
    assert len(derived) == 3 and r.getheader("Set-Cookie") is None  # answered before any key was derived
    assert any("too many failed sign-ins from 198.51.100.7" in m for m in lines)
    # at the machine itself nobody is kept out by what came through the front: Ada with her password, the secret user
    assert _call(port, "POST", "/api/sign-in", right, here)[0] == 200
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, here)
    assert status == 200 and data["admin"] is True
    # an address's limit: two more names from it, and it waits whatever the name; another address does not
    assert _call(port, "POST", "/api/sign-in", {"name": "bob", "password": "a wrong password"}, front)[0] == 401
    assert _call(port, "POST", "/api/sign-in", {"name": "cy", "password": "a wrong password"}, front)[0] == 401
    assert _call(port, "POST", "/api/sign-in", {"name": "zed", "password": "a wrong password"}, front)[0] == 429
    elsewhere = {**front, "X-Forwarded-For": "203.0.113.5"}
    assert _call(port, "POST", "/api/sign-in", {"name": "zed", "password": "a wrong password"}, elsewhere)[0] == 401
    # from that address a user of another login waits too, before their own login is asked (asked, it would fail: 500)
    app._remote_opener = type("Opener", (), {"open": lambda *a, **k: (_ for _ in ()).throw(AssertionError("asked"))})()
    assert _call(port, "POST", "/api/sign-in", {"name": "ada@remote.test", "password": "x" * 8}, front)[0] == 429
    # the window passes: the oldest failures age out, and the right password comes in again
    clock.now += 61
    assert _call(port, "POST", "/api/sign-in", right, front)[0] == 200
    # at the machine, past its own limits, the sign-ins with a password wait; the secret user's way in there never does
    for i in range(5):
        assert _call(port, "POST", "/api/sign-in", {"name": f"nobody{i}", "password": "a wrong password"}, here)[0] == 401
    assert _call(port, "POST", "/api/sign-in", right, here)[0] == 429
    for name in ("secret", "default"):
        assert _call(port, "POST", "/api/sign-in/secret", {"name": name}, here)[0] == 200
    assert not any("a wrong password" in m or "correct horse battery" in m for m in lines)


def test_a_wrong_password_at_another_login_counts_here_too(folder):
    """name@their.domain: their login says no (401), and the name typed counts here as one of this login's own would, so
    nobody guesses at speed through this login either; their login is not asked once it waits."""
    from conftest import _port

    from liminal_login.app import LoginApp

    remote = LoginApp(folder / "remote", log=lambda m: None, failure_delay=0)  # standing in for remote.test
    base = f"http://127.0.0.1:{_port(remote.start(0))}"
    local = LoginApp(folder / "local", log=lambda m: None, failure_delay=0, remotes={"remote.test": base},
                     throttle=Throttle(window=60, per_peer=10, per_name=2, clock=Clock()))
    port = _port(local.start(0))
    try:
        remote.users.create("Ada", "correct horse battery")
        here = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", WRITE_HEADER: "1"}
        for _ in range(2):
            assert _call(port, "POST", "/api/sign-in", {"name": "ada@remote.test", "password": "a wrong password"}, here)[0] == 401
        asked = len(remote._sessions)
        status, data, _ = _call(port, "POST", "/api/sign-in", {"name": "ada@remote.test", "password": "correct horse battery"}, here)
        assert status == 429 and len(remote._sessions) == asked == 0  # not asked there
        # one user, one count, however their domain is typed (a dot after it, spaces, its case): each of these was a
        # name of its own to count, as often as wanted, though their login is asked for the same user
        for typed in ("ada@remote.test.", " Ada@Remote.Test.. ", "ada @ remote.test"):
            status, _, _ = _call(port, "POST", "/api/sign-in", {"name": typed, "password": "correct horse battery"}, here)
            assert status == 429 and len(remote._sessions) == 0, typed
        assert _call(port, "POST", "/api/sign-in", {"name": "bo@remote.test", "password": "a wrong password"}, here)[0] == 401
    finally:
        local.close()
        remote.close()


def test_sign_ins_sent_together_are_held_to_the_limits_before_any_has_failed(served):
    """The review of LOG-C1's fix (2026-11-25): a failed sign-in was counted only once its key had been derived, so the
    sign-ins of a burst each found nothing counted yet and every one was tried, whatever the limits (200 passwords for
    one name where 10 were meant, and again every window). A try is counted before its key is derived. By its order,
    not by luck: the keys of the first ones are held (a stand-in) while the next is asked, which is answered 429 with
    no key derived for it. A wrong one stays counted; one whose password was right, or that another login did not
    answer, is taken back."""
    app, port, lines = served
    clock = Clock()
    app.throttle = Throttle(window=60, per_peer=2, per_name=3, at_once=8, clock=clock)  # turns enough for the five held
    app.users.create("Ada", "correct horse battery")
    inside, let_go, derived, answers = threading.Semaphore(0), threading.Event(), [], []
    verify = app.users.verify

    def held(who, password):
        derived.append(who)
        if password == "a held wrong password":
            inside.release()  # its try is counted, its key not yet derived
            assert let_go.wait(30), "the test lets the held keys go"
        return verify(who, password)

    def sign_in(name, address):
        answers.append(_call(port, "POST", "/api/sign-in", {"name": name, "password": "a held wrong password"},
                             _front(port, address))[0])

    app.users.verify = held
    right = {"name": "ADA", "password": "correct horse battery"}
    wrong = {"name": "di", "password": "a wrong password"}
    threads = [threading.Thread(target=sign_in, args=("ada", f"198.51.100.{i}"), daemon=True) for i in (1, 2, 3)]
    threads += [threading.Thread(target=sign_in, args=(name, "192.0.2.9"), daemon=True) for name in ("bo", "cy")]
    try:
        for t in threads:
            t.start()
        for _ in threads:
            assert inside.acquire(timeout=20), "the name's three and the address's two are all being tried"
        # a fourth for that name, from an address of its own and with the right password: at once, and no key derived
        status, data, r = _call(port, "POST", "/api/sign-in", right, _front(port, "203.0.113.5"))
        assert status == 429 and r.getheader("Retry-After") == "60" and data["error"].startswith("too many failed sign-ins")
        # a third from the address whose two are being tried, whatever the name
        assert _call(port, "POST", "/api/sign-in", wrong, _front(port, "192.0.2.9"))[0] == 429
        assert len(derived) == 5 and answers == []  # nothing has failed yet, and nothing more was derived
        # at the machine nobody waits for what a front's are doing
        assert _call(port, "POST", "/api/sign-in", right, _here(port))[0] == 200
    finally:
        let_go.set()
    for t in threads:
        t.join(20)
    assert answers == [401] * 5
    # wrong, all five: they stay as they were counted, and the name and the address go on waiting
    assert _call(port, "POST", "/api/sign-in", right, _front(port, "203.0.113.5"))[0] == 429
    assert _call(port, "POST", "/api/sign-in", wrong, _front(port, "192.0.2.9"))[0] == 429
    # a try that did not fail leaves nothing counted: the right password, however often; a login that does not answer
    app.throttle = Throttle(window=60, per_peer=2, per_name=3, clock=clock)
    for _ in range(4):
        assert _call(port, "POST", "/api/sign-in", right, _front(port))[0] == 200
    assert len(app.throttle) == 0

    def no_answer(*a, **k):
        raise urllib.error.URLError("no route to it")

    app._remote_opener = SimpleNamespace(open=no_answer)
    for _ in range(4):
        assert _call(port, "POST", "/api/sign-in", {"name": "ada@remote.test", "password": "x" * 8}, _front(port))[0] == 503
    assert len(app.throttle) == 0
    assert _call(port, "POST", "/api/sign-in", wrong, _front(port))[0] == 401 and len(app.throttle) == 2  # a wrong one stays
    assert not any("a held wrong password" in m or "correct horse battery" in m for m in lines)


def test_the_keys_derived_at_once_are_bounded_and_the_machines_own_never_wait_behind_a_fronts(served):
    """Each key derived takes memory (scrypt: 32 MB), and a burst derived all at once could take the machine's and, with
    the process, the counts. `at_once` are derived at once from each place, the others waiting their turn; this
    machine's own have turns of their own, and the secret user's way in has none to wait for. By its order: two keys
    held (a stand-in) while a third has asked for its turn."""
    app, port, lines = served
    asked = threading.Semaphore(0)

    class Watched(Throttle):
        def deriving(self, where):
            if where == "away":
                asked.release()  # a sign-in a front handed on asks for its turn
            return super().deriving(where)

    app.throttle = Watched(window=60, per_peer=50, per_name=50, at_once=2, clock=Clock())
    app.users.create("Ada", "correct horse battery")
    inside, let_go, counting, answers = threading.Semaphore(0), threading.Event(), threading.Lock(), []
    seen = {"now": 0, "most": 0}
    verify = app.users.verify

    def held(who, password):
        if password != "a held wrong password":
            return verify(who, password)
        with counting:
            seen["now"] += 1
            seen["most"] = max(seen["most"], seen["now"])
        inside.release()
        try:
            assert let_go.wait(30), "the test lets the held keys go"
            return verify(who, password)
        finally:
            with counting:
                seen["now"] -= 1

    def sign_in(i):
        answers.append(_call(port, "POST", "/api/sign-in", {"name": f"user{i}", "password": "a held wrong password"},
                             _front(port, f"198.51.100.{i}"))[0])

    app.users.verify = held
    threads = [threading.Thread(target=sign_in, args=(i,), daemon=True) for i in (1, 2, 3)]
    try:
        for t in threads:
            t.start()
        for _ in threads:
            assert asked.acquire(timeout=20), "each of the three asked for its turn"
        for _ in range(2):
            assert inside.acquire(timeout=20), "two are deriving"
        assert seen == {"now": 2, "most": 2} and not inside.acquire(blocking=False)  # the third waits for a turn
        # at the machine: a sign-in with a password has a turn of its own, and the way in without one asks for none
        assert _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"}, _here(port))[0] == 200
        assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, _here(port))[0] == 200
    finally:
        let_go.set()
    for t in threads:
        t.join(20)
    assert answers == [401] * 3 and seen == {"now": 0, "most": 2}


def test_a_host_typed_in_a_name_is_a_domain_never_an_address(served):
    """The review of LOG-C1's fix (2026-11-25): name@http://127.0.0.1:<its own port>, typed through a front, was taken
    for another login's host, and the login asked itself over http as a program at its own machine. The try was then
    counted as the machine's own: whoever reached the front had the machine's tries beside the front's, and thirty of
    them made every sign-in with a password at the machine wait. An address is taken only from what [remotes] names;
    typed in a name it is refused (400), and nothing is asked or counted."""
    app, port, lines = served
    app.users.create("Ada", "correct horse battery")
    asked: list = []
    call = app._remote_call
    app._remote_call = lambda *a, **k: asked.append(a) or call(*a, **k)
    for typed in (f"ada@http://127.0.0.1:{port}", f"ada@HTTP://127.0.0.1:{port}/?1", f"ada@http://localhost:{port}.",
                  "ada@https://remote.test"):
        status, data, _ = _call(port, "POST", "/api/sign-in", {"name": typed, "password": "a wrong password"}, _front(port))
        assert status == 400 and "not by an address" in data["error"], typed
    assert asked == [] and len(app.throttle) == 0
    # at the machine too, and on the way in without a password
    status, data, _ = _call(port, "POST", "/api/sign-in/secret", {"name": f"secret@http://127.0.0.1:{port}"}, _here(port))
    assert status == 400 and "not by an address" in data["error"] and asked == [] and app.users.secret_kept() is None
    assert _call(port, "POST", "/api/sign-in", {"name": "Ada", "password": "correct horse battery"}, _here(port))[0] == 200
    # a domain typed is asked over https as before, and an address [remotes] names is taken (http to this machine too)
    assert app.remote_url("Remote.Test.") == "https://remote.test"
    app.remotes["remote.test"] = f"http://127.0.0.1:{port}"
    assert app.remote_url("remote.test") == f"http://127.0.0.1:{port}"


def _begun(port, mailer, email, sent_as) -> str:
    """A sign-up begun for `email`, its code mailed (the stand-in keeps the message): the code."""
    status, data, _ = _call(port, "POST", "/api/signup", {"email": email}, sent_as)
    assert status == 202, (email, data)
    return mailer.last_code()


def _other(code: str) -> str:
    """A code that is not `code`."""
    return "000000" if code != "000000" else "111111"


def _typed(port, email, code, sent_as):
    return _call(port, "POST", "/api/signup/verify", {"email": email, "code": code}, sent_as)


def test_a_sign_ups_wrong_codes_are_counted_as_wrong_passwords_are_by_the_address_and_by_the_email(served_mail):
    """The last check of LOG-C1's fix (2026-11-25; the user: wrong codes count toward the sign-in throttle): a
    sign-up's six-digit code could be guessed at speed, with no count on its routes. A wrong code is counted where a
    wrong password is, with its numbers: by where it came from, with the failed sign-ins from there, and by the address
    the code was mailed to. Past either limit a code typed is answered 429 with Retry-After before it is looked at,
    the right one too; the machine's own are counted apart from a front's; and what was no guess (the right code, no
    sign-up under way, no address) leaves nothing counted."""
    app, port, lines, mailer = served_mail
    clock = Clock()
    app.throttle = Throttle(window=60, per_peer=5, per_name=3, clock=clock)
    looked: list = []
    verify = app.users.verify_signup
    app.users.verify_signup = lambda email, code: looked.append(email) or verify(email, code)  # each code looked at, noted
    here = _here(port)
    # by the email: three wrong codes for one address, each from an address of its own
    code = _begun(port, mailer, "ada@example.test", _front(port, "192.0.2.1"))
    for i, left in enumerate((4, 3, 2)):
        status, data, _ = _typed(port, " Ada@Example.test ", _other(code), _front(port, f"192.0.2.{i + 1}"))
        assert status == 400 and f"wrong code ({left} tries left)" in data["error"]
    status, data, r = _typed(port, "ada@example.test", code, _front(port, "192.0.2.9"))  # the right code, from elsewhere
    assert status == 429 and r.getheader("Retry-After") == "60"
    assert data["error"] == "too many wrong codes or failed sign-ins: try again in 60 s" and r.getheader("Set-Cookie") is None
    assert len(looked) == 3 and app.users.signup("ada@example.test")["tries"] == 3  # answered before the code was looked at
    assert any("too many wrong codes or failed sign-ins from 192.0.2.3" in m for m in lines)
    # the machine's own are counted apart: nobody who reaches the front keeps a code typed at the machine out
    status, data, _ = _typed(port, "ada@example.test", code, here)
    assert status == 200 and data["token"]
    # by the address: five wrong codes from one, for five addresses, and it waits whatever the address; another does not
    codes = {email: _begun(port, mailer, email, here) for email in (f"b{i}@example.test" for i in range(6))}
    busy = _front(port, "203.0.113.5")
    for email in list(codes)[:5]:
        status, data, _ = _typed(port, email, _other(codes[email]), busy)
        assert status == 400 and "4 tries left" in data["error"], email
    status, data, r = _typed(port, "b5@example.test", codes["b5@example.test"], busy)
    assert status == 429 and r.getheader("Retry-After") == "60" and app.users.signup("b5@example.test")["tries"] == 0
    assert _typed(port, "b5@example.test", codes["b5@example.test"], _front(port, "203.0.113.6"))[0] == 200
    # counted with the failed sign-ins from there: that address waits for a sign-in too, and wrong passwords hold a code back
    wrong = {"name": "nobody", "password": "a wrong password"}
    status, data, _ = _call(port, "POST", "/api/sign-in", wrong, busy)
    assert status == 429 and data["error"] == "too many failed sign-ins: try again in 60 s"
    guessing = _front(port, "198.51.100.20")
    for i in range(5):
        assert _call(port, "POST", "/api/sign-in", {**wrong, "name": f"nobody{i}"}, guessing)[0] == 401
    late = _begun(port, mailer, "late@example.test", here)
    assert _typed(port, "late@example.test", late, guessing)[0] == 429
    assert not any(c in m for m in lines for c in (code, late, *codes.values()))  # no code in the log
    # the window passes: the address is heard again
    clock.now += 61
    assert _typed(port, "late@example.test", late, guessing)[0] == 200
    # what was no guess leaves nothing counted: the right code, however often; no sign-up under way; no address
    app.throttle = Throttle(window=60, per_peer=2, per_name=2, clock=clock)
    for i in range(4):
        right = _begun(port, mailer, f"right{i}@example.test", here)
        assert _typed(port, f"right{i}@example.test", right, _front(port))[0] == 200
    for _ in range(4):
        assert _typed(port, "nobody@example.test", "123456", _front(port))[0] == 400
        assert _typed(port, "", "123456", _front(port))[0] == 400
    assert len(app.throttle) == 0


def test_a_new_code_gives_no_tries_back_and_none_follows_a_spent_one_at_once(served_mail):
    """A fresh code is no way round the count. While the wrong codes for an address are held back no new code is sent
    for it, begun again or sent again, from anywhere a front hands on (429, nothing mailed); and a new code, had one
    gone out, gives none of the throttle's tries back, the right one typed too. And a code whose own five tries are
    spent is not followed by another at once: its sign-up was dropped at the fifth wrong code, and the next begun at
    once, with five more."""
    app, port, lines, mailer = served_mail
    clock = Clock()
    app.throttle = Throttle(window=60, per_peer=50, per_name=3, clock=clock)
    front = _front(port)
    code = _begun(port, mailer, "eve@example.test", front)
    for _ in range(3):
        assert _typed(port, "eve@example.test", _other(code), front)[0] == 400
    for path in ("/api/signup/resend", "/api/signup"):  # the address's three are spent: no new code, from here or elsewhere
        for sent_as in (front, _front(port, "203.0.113.5")):
            status, data, r = _call(port, "POST", path, {"email": " EVE@example.test"}, sent_as)
            assert status == 429 and r.getheader("Retry-After") == "60", (path, data)
            assert data["error"] == "too many wrong codes or failed sign-ins: try again in 60 s"
    assert len(mailer.sent) == 1 and app.users.signup("eve@example.test")["tries"] == 3  # nothing sent, nothing changed
    # a new code, as its minute passing would give one (asked of the store): the code's own tries start again, the
    # throttle's do not, and the right new code waits like any other
    fresh = app.users.resend_signup("eve@example.test", sooner_than=0)
    assert app.users.signup("eve@example.test")["tries"] == 0
    status, data, r = _typed(port, "eve@example.test", fresh, front)
    assert status == 429 and r.getheader("Retry-After") == "60" and app.users.signup("eve@example.test")["verified"] is False
    # at the machine nothing of this waits: a new code is refused there only as any is, a minute after the last
    status, data, _ = _call(port, "POST", "/api/signup/resend", {"email": "eve@example.test"}, _here(port))
    assert status == 400 and "seconds ago" in data["error"]
    clock.now += 61  # the oldest of the three a window old
    assert _typed(port, "eve@example.test", fresh, front)[0] == 200
    # a code's own five tries (the address's ten are not spent): the fifth wrong one spends it, the right one comes too
    # late, and no new code follows at once, begun again or sent again
    app.throttle = Throttle(window=60, per_peer=50, per_name=10, clock=clock)
    code = _begun(port, mailer, "fay@example.test", front)
    mailed = len(mailer.sent)
    for left in (4, 3, 2, 1):
        status, data, _ = _typed(port, "fay@example.test", _other(code), front)
        assert status == 400 and f"{left} tries left" in data["error"]
    status, data, _ = _typed(port, "fay@example.test", _other(code), front)
    assert status == 400 and "that was the last try for that code" in data["error"]
    status, data, _ = _typed(port, "fay@example.test", code, front)
    assert status == 400 and "the tries of that code are spent" in data["error"]
    for path in ("/api/signup", "/api/signup/resend"):
        status, data, _ = _call(port, "POST", path, {"email": "fay@example.test"}, front)
        assert status == 400 and "the tries of the last code are spent" in data["error"], path
    assert len(mailer.sent) == mailed and app.users.signup("fay@example.test")["tries"] == 5
    assert len(app.throttle._counts[("name", "away", "fay@example.test")]) == 5  # the spent code's answer was no guess


def test_codes_typed_together_are_held_to_the_limits_before_any_is_looked_at(served_mail):
    """As a sign-in is: a code typed is counted before it is compared, in the same hold of the lock that asks whether
    it must wait, so codes sent at once are held to the limits (counted once found wrong, each of a burst would find
    nothing counted yet). By its order: the first two are held (a stand-in) while the third is asked, which is
    answered 429 and not looked at, though it is the right one."""
    app, port, lines, mailer = served_mail
    app.throttle = Throttle(window=60, per_peer=50, per_name=2, clock=Clock())
    code = _begun(port, mailer, "ada@example.test", _here(port))
    inside, let_go, looked, answers = threading.Semaphore(0), threading.Event(), [], []
    verify = app.users.verify_signup

    def held(email, typed):
        looked.append(typed)
        if typed != code:
            inside.release()  # its try is counted, its code not yet compared
            assert let_go.wait(30), "the test lets the held codes go"
        return verify(email, typed)

    def guess(i):
        answers.append(_typed(port, "ada@example.test", _other(code), _front(port, f"198.51.100.{i}"))[0])

    app.users.verify_signup = held
    threads = [threading.Thread(target=guess, args=(i,), daemon=True) for i in (1, 2)]
    try:
        for t in threads:
            t.start()
        for _ in threads:
            assert inside.acquire(timeout=20), "the address's two are both being tried"
        status, data, r = _typed(port, "ada@example.test", code, _front(port, "203.0.113.5"))
        assert status == 429 and r.getheader("Retry-After") == "60" and len(looked) == 2 and answers == []
    finally:
        let_go.set()
    for t in threads:
        t.join(20)
    assert answers == [400, 400]
    # wrong, both: they stay as they were counted, and the right code goes on waiting
    assert _typed(port, "ada@example.test", code, _front(port, "203.0.113.5"))[0] == 429 and len(looked) == 2
