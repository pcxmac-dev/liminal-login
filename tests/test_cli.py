"""The command line (cli.py): a user made with the password typed hidden, the list, the status,
`serve` with its port; no server runs here."""
from __future__ import annotations

from liminal_login import cli
from liminal_login.app import LoginApp
from liminal_login.users import UserStore


def test_a_user_is_added_with_the_password_typed_hidden(folder, monkeypatch, capsys):
    typed = iter(["correct horse battery", "correct horse battery"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
    assert cli.main(["user", "add", "Ada"]) == 0
    out = capsys.readouterr().out
    assert "user Ada created" in out and "correct horse battery" not in out
    typed = iter(["one password", "another one"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
    assert cli.main(["user", "add", "Bob"]) == 1 and "differ" in capsys.readouterr().err
    typed = iter(["short", "short"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
    assert cli.main(["user", "add", "Bob"]) == 1
    assert cli.main(["user", "add"]) == 2
    assert cli.main(["user", "list"]) == 0 and "Ada: created" in capsys.readouterr().out
    users = UserStore(folder / "charts" / "users.db")  # the charts namespace, the default
    assert users.verify("Ada", "correct horse battery") is not None and users.count() == 1
    users.close()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "login app for charts: 1 user(s)" in out and "not running at port 8795" in out
    # the integrator's namespace: its own users, cookie and port
    assert cli.main(["--for", "integrator", "user", "list"]) == 0 and "no users yet" in capsys.readouterr().out
    assert cli.main(["--for", "integrator", "status"]) == 0 and "port 8796" in capsys.readouterr().out
    assert (folder / "charts" / "users.db").is_file() and (folder / "integrator" / "users.db").is_file()


def test_a_test_message_goes_through_the_mail_account_or_says_why_not(folder, monkeypatch, capsys):
    from liminal_libs.mail import MailError, MailSettings, Sent

    sent: list = []

    class FakeMailer:
        def __init__(self, log=None):
            self.settings = MailSettings(host="smtp.example.test", user="me@example.test", password="x", sender="me@example.test")

        def send(self, to, subject, text):
            if to == "down@example.test":
                raise MailError("the mail server at smtp.example.test:587 did not take the message: refused")
            sent.append((to, subject))
            return Sent(to, "smtp.example.test", 587, 250, "2.0.0 OK queued as t-1", "2026-11-06T21:00:00+00:00", "<t-1@example.test>")
    monkeypatch.setattr(cli, "Mailer", FakeMailer)
    assert cli.main(["mail", "test", "ada@example.test"]) == 0 and sent == [("ada@example.test", "Liminal: a test message")]
    out = capsys.readouterr().out  # the server's own answer, and the id to find the message by
    assert "sent to ada@example.test: smtp.example.test:587 answered 250 2.0.0 OK queued as t-1 at 2026-11-06T21:00:00+00:00, message id <t-1@example.test>" in out
    assert cli.main(["mail", "test", "down@example.test"]) == 1 and "did not take" in capsys.readouterr().err
    assert cli.main(["mail", "test"]) == 2
    # a user added from the command line may carry an email, unverified
    typed = iter(["correct horse battery", "correct horse battery"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
    assert cli.main(["user", "add", "Ada", "--email", "ada@example.test"]) == 0
    assert cli.main(["user", "list"]) == 0 and "ada@example.test" in capsys.readouterr().out
    assert cli.main(["status"]) == 0 and "mail not set up" in capsys.readouterr().out


def test_serve_runs_the_app_at_the_port_asked(folder, monkeypatch):
    ran: list = []
    monkeypatch.setattr(LoginApp, "serve", lambda self, port=None, open_browser=False, stop=None, until_quiet=None:
                        ran.append((self.dir, port, open_browser, until_quiet)) or "url")
    assert cli.main(["serve", "--no-browser", "--port", "8796"]) == 0 and ran == [(folder / "charts", 8796, False, None)]
    assert cli.main(["--no-browser"]) == 0 and ran[-1] == (folder / "charts", 8795, False, None)  # `liminal-login` alone serves
    assert cli.main([]) == 0 and ran[-1] == (folder / "charts", 8795, True, None)
    assert cli.main(["--for", "integrator", "serve", "--no-browser"]) == 0 and ran[-1] == (folder / "integrator", 8796, False, None)
    monkeypatch.setenv("LIMINAL_LOGIN_FOR", "integrator")
    assert cli.main(["serve", "--no-browser"]) == 0 and ran[-1][0] == folder / "integrator"
    monkeypatch.delenv("LIMINAL_LOGIN_FOR")
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "8801")
    assert cli.main(["serve", "--no-browser"]) == 0 and ran[-1][1] == 8801
    # started by another app's front: until quiet, LIMINAL_QUIET_SECONDS
    assert cli.main(["serve", "--no-browser", "--until-quiet"]) == 0 and ran[-1][3] == 600.0
    monkeypatch.setenv("LIMINAL_QUIET_SECONDS", "30")
    assert cli.main(["serve", "--no-browser", "--until-quiet"]) == 0 and ran[-1][3] == 30.0
