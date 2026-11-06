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
    users = UserStore(folder / "users.db")
    assert users.verify("Ada", "correct horse battery") is not None and users.count() == 1
    users.close()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "1 user(s)" in out and "not running at port 8795" in out


def test_serve_runs_the_app_at_the_port_asked(folder, monkeypatch):
    ran: list = []
    monkeypatch.setattr(LoginApp, "serve", lambda self, port=None, open_browser=False, stop=None: ran.append((self.dir, port, open_browser)) or "url")
    assert cli.main(["serve", "--no-browser", "--port", "8796"]) == 0 and ran == [(folder, 8796, False)]
    assert cli.main(["--no-browser"]) == 0 and ran[-1] == (folder, 8795, False)  # `liminal-login` alone serves
    assert cli.main([]) == 0 and ran[-1] == (folder, 8795, True)
    monkeypatch.setenv("LIMINAL_LOGIN_PORT", "8801")
    assert cli.main(["serve", "--no-browser"]) == 0 and ran[-1][1] == 8801
