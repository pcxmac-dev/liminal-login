"""The command line (cli.py): a user made with the password typed hidden, the list, the status,
`serve` with its port; no server runs here."""
from __future__ import annotations

import pytest

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
    import socket

    with socket.socket() as free:  # a port nothing answers at (the real login app may well be at 8795)
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    assert cli.main(["status", "--port", str(port)]) == 0
    out = capsys.readouterr().out
    assert "login app for charts: 1 user(s)" in out and f"not running at port {port}" in out
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


def test_the_mail_account_is_set_up_once_from_the_command_line_with_the_password_kept_apart(monkeypatch, capsys):
    from liminal_libs import mail

    saved: dict = {}
    kept: dict = {}
    for v in mail.ALL_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(cli, "save_user_variable", lambda name, value: saved.__setitem__(name, value))
    monkeypatch.setattr(cli.secrets, "put", lambda name, value: kept.__setitem__(name, value))
    monkeypatch.setattr(cli.secrets, "remove", lambda name: kept.pop(name, None) is not None)
    monkeypatch.setattr(mail, "_saved", lambda: {k: v for k, v in saved.items() if v})
    monkeypatch.setattr(mail, "_secret", lambda name: kept.get(name))
    answers = iter(["bridge", "", "", "me@proton.me", "Me <me@proton.me>"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "bridge-pw-1")
    assert cli.main(["mail", "setup"]) == 0
    out = capsys.readouterr().out
    assert saved == {"LIMINAL_SMTP_HOST": "127.0.0.1", "LIMINAL_SMTP_PORT": "1025", "LIMINAL_SMTP_SECURITY": "starttls",
                     "LIMINAL_SMTP_USER": "me@proton.me", "LIMINAL_SMTP_FROM": "Me <me@proton.me>", "LIMINAL_SMTP_PASSWORD": None}
    assert kept == {"LIMINAL_SMTP_PASSWORD": "bridge-pw-1"} and "bridge-pw-1" not in out
    assert "kept: 127.0.0.1:1025 starttls, user me@proton.me, from me@proton.me, password in Windows Credential Manager" in out
    # direct: no account, the password kept so far let go
    answers = iter(["direct", "me@proton.me"])
    assert cli.main(["mail", "setup"]) == 0
    assert saved["LIMINAL_SMTP_HOST"] == "direct" and saved["LIMINAL_SMTP_USER"] is None and saved["LIMINAL_SMTP_FROM"] == "me@proton.me" and kept == {}
    # a user whose password is neither typed nor kept: not complete, said (a host with no user at all is
    # a server that asks for none, like a bridge on this machine)
    answers = iter(["smtp.example.test", "", "", "someone@example.test", ""])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "")
    assert cli.main(["mail", "setup"]) == 1 and "go together" in capsys.readouterr().err


def test_a_signing_key_for_the_users_domain_its_record_and_whether_it_is_published(folder, monkeypatch, capsys):
    # the user, 2026-11-06: "it looks like i need a domain/email server for this to work": the key here, the
    # record at the domain; the app signs what it sends from the domain
    pytest.importorskip("cryptography")
    from liminal_libs import dkim, mail

    saved: dict = {}
    monkeypatch.setattr(cli, "save_user_variable", lambda name, value: saved.__setitem__(name, value))
    monkeypatch.setattr(mail, "_saved", lambda: {k: v for k, v in saved.items() if v})
    assert cli.main(["--dir", str(folder), "mail", "dkim", "init"]) == 2  # no domain known yet
    assert "a domain is needed" in capsys.readouterr().err
    assert cli.main(["--dir", str(folder), "mail", "dkim", "init", "--domain", "Your-Domain.example"]) == 0
    out = capsys.readouterr().out
    key = folder / "dkim" / "your-domain.example.liminal.pem"
    assert key.is_file() and saved == {"LIMINAL_SMTP_DKIM_KEY": str(key), "LIMINAL_SMTP_DKIM_SELECTOR": "liminal",
                                       "LIMINAL_SMTP_DKIM_DOMAIN": "your-domain.example"}
    public = dkim.public_of(key.read_bytes())
    assert "name:  liminal._domainkey.your-domain.example" in out and f"value: v=DKIM1; k=rsa; p={public}" in out
    assert cli.main(["--dir", str(folder), "mail", "dkim", "init"]) == 1 and "there already" in capsys.readouterr().err
    assert cli.main(["--dir", str(folder), "mail", "dkim", "show"]) == 0 and public in capsys.readouterr().out
    assert cli.main(["--dir", str(folder), "mail", "dkim", "other"]) == 2
    monkeypatch.setattr(dkim, "published", lambda name: None)
    assert cli.main(["--dir", str(folder), "mail", "dkim", "check"]) == 1 and "no DKIM record found yet" in capsys.readouterr().out
    monkeypatch.setattr(dkim, "published", lambda name: public)
    assert cli.main(["--dir", str(folder), "mail", "dkim", "check"]) == 0 and "published and matching" in capsys.readouterr().out
    monkeypatch.setattr(dkim, "published", lambda name: "another")
    assert cli.main(["--dir", str(folder), "mail", "dkim", "check"]) == 1 and "not the one here" in capsys.readouterr().err
    # the status names the signing; a mailer in direct mode signs from the domain
    saved.update({"LIMINAL_SMTP_HOST": "direct", "LIMINAL_SMTP_FROM": "liminal@your-domain.example"})
    assert cli.main(["--dir", str(folder), "status", "--port", "1"]) == 0 and "signed under liminal._domainkey.your-domain.example" in capsys.readouterr().out


def test_the_logins_file_ties_it_to_a_folder_or_a_domain(folder, tmp_path, monkeypatch, capsys):
    # the user, 2026-11-06: "use a url regardless, file if local, domain w/ email server in mail record"
    project = tmp_path / "project"
    project.mkdir()
    assert cli.main(["init", str(project), "--title", "My project", "--serves", "charts, integrator"]) == 0
    out = capsys.readouterr().out
    cfg = project / "liminal-login.cfg"
    assert cfg.is_file() and "scope = file:///" in out and "A local login" in out and "serves = charts, integrator" in cfg.read_text()
    assert cli.main(["init", str(project)]) == 1 and "there already" in capsys.readouterr().err
    assert cli.main(["--cfg", str(cfg), "status", "--port", "1"]) == 0 and f"local to {project.resolve()}" in capsys.readouterr().out
    domain_cfg = tmp_path / "domain.cfg"
    assert cli.main(["init", "Example.test", "--members", "any", "--port", "8811", "--cfg", str(domain_cfg)]) == 0
    out = capsys.readouterr().out
    assert "scope = https://example.test" in out and "members = any" in out and "the domain's own mail record" in out
    assert cli.main(["init", "https:///", "--cfg", str(tmp_path / "bad.cfg")]) == 2
    # the file decides the users' folder and the port; the status says what the login is tied to
    monkeypatch.delenv("LIMINAL_LOGIN_DIR", raising=False)
    monkeypatch.setattr(cli, "login_dir", lambda: tmp_path / "data" / "login")
    typed = iter(["correct horse battery", "correct horse battery"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(typed))
    assert cli.main(["--cfg", str(domain_cfg), "user", "add", "Ada"]) == 0
    assert (tmp_path / "data" / "login" / "example.test" / "charts" / "users.db").is_file()  # the domain's folder, then the app's
    assert cli.main(["--cfg", str(domain_cfg), "status", "--port", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 user(s)" in out and "@example.test" in out


def test_the_login_checks_its_mail_server_with_its_admin_account(tmp_path, monkeypatch, capsys):
    # the user, 2026-11-06: the admin account "would need to be valid in the DNS record ... could be used to test
    # the server so that it can send and receive with the user email and also see if emails can be sent to
    # other servers, without error"
    from liminal_libs import dns
    from liminal_libs.mail import MailError, Sent
    from liminal_libs.mailbox import MailboxError

    from liminal_login import mailcheck

    cfg = tmp_path / "domain.cfg"
    assert cli.main(["init", "example.test", "--admin", "Admin@liminal.example.test", "--cfg", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "admin = admin@liminal.example.test" in out and "liminal.example.test, must be valid in DNS" in out
    assert cli.main(["init", "example.test", "--admin", "admin@other.test", "--cfg", str(tmp_path / "bad.cfg")]) == 2
    sent: list = []

    class FakeMailer:
        def __init__(self, log=None, cfg=None):
            from liminal_libs.mail import MailSettings

            self.settings = MailSettings.from_env(cfg)

        def send(self, to, subject, text):
            if "down" in to:
                raise MailError("the mail server at mail.liminal.example.test:587 refused the address: 550 no such user")
            sent.append((to, subject))
            return Sent(to, "mail.liminal.example.test", 587, 250, "2.0.0 Ok: queued as 1", "2026-11-06T22:00:00+00:00", "<1@liminal.example.test>")

    class FakeMailbox:
        configured = True
        looked = 0

        def __init__(self, log=None, cfg=None):
            self.cfg = cfg

        def find(self, text):
            FakeMailbox.looked += 1
            return 1 if FakeMailbox.looked >= 2 and any(text in s for _, s in sent) else 0
    monkeypatch.setattr(cli, "Mailer", FakeMailer)
    monkeypatch.setattr(cli, "Mailbox", FakeMailbox)
    monkeypatch.setattr(dns, "addresses", lambda host: ["203.0.113.5"] if host == "liminal.example.test" else [])
    monkeypatch.setattr(dns, "mx_records", lambda host: ["mail.liminal.example.test"] if host == "liminal.example.test" else [])
    monkeypatch.setattr(dns, "spf_record", lambda host: "v=spf1 mx -all")
    monkeypatch.setattr(mailcheck, "POLL_SECONDS", 0.0)
    monkeypatch.setattr(mailcheck.time, "sleep", lambda s: None)
    # no server named: the admin host's own mail record; the mailbox named through the file
    from dataclasses import replace

    from liminal_libs.apps import Scope

    replace(Scope.read(cfg), imap={"host": "mail.liminal.example.test"}).write(cfg)
    assert cli.main(["--cfg", str(cfg), "mail", "check", "--to", "you@proton.test", "--to", "down@other.test", "--wait", "1"]) == 1
    out = capsys.readouterr().out
    assert "     ok  liminal.example.test in DNS" in out and "203.0.113.5" in out and "ok  SPF for liminal.example.test" in out
    assert "ok  the mail server" in out and "admin@liminal.example.test" in out
    assert "ok  sent to the admin account itself" in out and "ok  sent to you@proton.test" in out and "FAILED  sent to down@other.test" in out and "550 no such user" in out
    assert "ok  received back in the admin mailbox" in out and [t for t, _ in sent] == ["admin@liminal.example.test", "you@proton.test"]
    # a host not in DNS and nothing received: said, and the check fails
    monkeypatch.setattr(dns, "addresses", lambda host: [])
    monkeypatch.setattr(dns, "mx_records", lambda host: [])
    FakeMailbox.find = lambda self, text: 0
    assert cli.main(["--cfg", str(cfg), "mail", "check", "--wait", "0"]) == 1
    out = capsys.readouterr().out
    assert "FAILED  liminal.example.test in DNS" in out and "FAILED  received back in the admin mailbox" in out and "not there after 0 s" in out
    FakeMailbox.find = lambda self, text: (_ for _ in ()).throw(MailboxError("the mailbox at mail.liminal.example.test:993 refused: bad password"))
    assert cli.main(["--cfg", str(cfg), "mail", "check", "--wait", "0"]) == 1 and "refused: bad password" in capsys.readouterr().out
    # no mailbox: the receiving is skipped, not failed; a local login has nothing to check
    FakeMailbox.configured = False
    monkeypatch.setattr(dns, "addresses", lambda host: ["203.0.113.5"])
    assert cli.main(["--cfg", str(cfg), "mail", "check"]) == 0 and "skipped  received back" in capsys.readouterr().out
    local = tmp_path / "local.cfg"
    assert cli.main(["init", str(tmp_path), "--cfg", str(local)]) == 0 and capsys.readouterr()
    assert cli.main(["--cfg", str(local), "mail", "check"]) == 1 and "sends no email" in capsys.readouterr().out
    assert cli.main(["mail", "check"]) == 2  # no file found (the tests' login is local to its folder)


def test_the_mail_server_runs_as_a_container_the_login_file_declares(tmp_path, monkeypatch, capsys):
    # the user, 2026-11-07: "i want to integrate docker with the liminal framework": the [server] section, run
    # through the framework's docker driver, here through its stand-in runner
    from dataclasses import replace

    from liminal_libs import dns
    from liminal_libs.apps import Scope
    from liminal_libs.docker import Docker

    try:
        from test_docker_runner import Runner
    except ImportError:
        from tests.test_docker_runner import Runner

    cfg = tmp_path / "domain.cfg"
    assert cli.main(["init", "example.test", "--admin", "admin@liminal.example.test", "--cfg", str(cfg)]) == 0 and capsys.readouterr()
    assert cli.main(["--cfg", str(cfg), "server", "status"]) == 2 and "no [server] image" in capsys.readouterr().err
    replace(Scope.read(cfg), server={"image": "foxcpp/maddy:0.8", "ports": "25:25, 587:587, 993:993", "volumes": "./mail:/data",
                                     "env_MADDY_DOMAIN": "example.test"}).write(cfg)
    runner = Runner(rows=[])
    monkeypatch.setattr(Scope, "docker", lambda self, **kw: Docker(runner=runner, env={}, **kw))
    assert cli.main(["--cfg", str(cfg), "server", "show"]) == 0
    line = capsys.readouterr().out
    assert line.startswith("docker run -d --name liminal-mail-example-test") and "--hostname liminal.example.test" in line and "-e MADDY_DOMAIN=example.test" in line
    assert cli.main(["--cfg", str(cfg), "server", "status"]) == 1 and "not made yet" in capsys.readouterr().out
    assert cli.main(["--cfg", str(cfg), "server", "up"]) == 0 and "liminal-mail-example-test made: running" in capsys.readouterr().out
    assert cli.main(["--cfg", str(cfg), "server", "status"]) == 0 and "health healthy" in capsys.readouterr().out
    assert cli.main(["--cfg", str(cfg), "server", "logs", "--tail", "3"]) == 0 and "maddy started" in capsys.readouterr().out
    assert cli.main(["--cfg", str(cfg), "server", "exec", "--", "maddy", "creds", "list"]) == 0 and "ok from inside" in capsys.readouterr().out
    assert runner.calls[-1][1:] == ["exec", "liminal-mail-example-test", "maddy", "creds", "list"]
    # the check names the container first
    monkeypatch.setattr(dns, "addresses", lambda host: ["203.0.113.5"])
    monkeypatch.setattr(dns, "mx_records", lambda host: [])
    monkeypatch.setattr(dns, "spf_record", lambda host: "")
    monkeypatch.setattr(cli, "Mailer", lambda log=None, cfg=None: type("M", (), {"settings": type("S", (), {"configured": False, "signing": False, "problems": lambda self: ["no server"]})()})())
    assert cli.main(["--cfg", str(cfg), "mail", "check"]) == 1
    out = capsys.readouterr().out
    assert "     ok  the container liminal-mail-example-test" in out and "running" in out
    assert cli.main(["--cfg", str(cfg), "server", "down"]) == 0 and "stopped (its data kept)" in capsys.readouterr().out
    assert cli.main(["--cfg", str(cfg), "mail", "check"]) == 1 and "FAILED  the container liminal-mail-example-test" in capsys.readouterr().out
    # without Docker: said, and nothing else pretends
    monkeypatch.setattr(Scope, "docker", lambda self, **kw: Docker(runner=Runner(rows=[], version={"Client": {"Version": "1"}}), env={}, **kw))
    assert cli.main(["--cfg", str(cfg), "server", "up"]) == 1 and "no Docker engine answers" in capsys.readouterr().err
    assert cli.main(["--cfg", str(cfg), "server", "status"]) == 1 and "not running: Docker is not available" in capsys.readouterr().out


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
