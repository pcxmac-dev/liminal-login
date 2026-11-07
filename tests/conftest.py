"""The login app's tests: every store in a folder of the test's own (never store/data), the app on a
free port in a thread, no delay after a failed sign-in, no process started, nothing opened in a
browser, no message sent anywhere (a stand-in mailer keeps what it would have sent)."""
from __future__ import annotations

import pytest

from liminal_libs.apps import Scope
from liminal_libs.mail import Mailer, MailSettings

from liminal_login.app import LoginApp


class FakeMailer(Mailer):
    """The mailer as a test sees it: configured or not, every message kept, never sent."""

    def __init__(self, configured: bool = True):
        settings = MailSettings(host="smtp.example.test", user="liminal@example.test", password="x", sender="liminal@example.test") \
            if configured else MailSettings()
        super().__init__(settings, log=lambda m: None)
        self.sent: list[tuple[str, str, str]] = []
        self.refuse: str | None = None  # a MailError's reason, when the server should refuse

    def send(self, to: str, subject: str, text: str):
        from liminal_libs.mail import MailError, Sent

        if not self.configured:
            raise MailError("email sending is not set up: " + "; ".join(self.settings.problems()))
        if self.refuse:
            raise MailError(self.refuse)
        self.sent.append((to, subject, text))
        return Sent(to, self.settings.host, self.settings.port, 250, "2.0.0 OK queued as fake-1", "2026-11-06T21:00:00+00:00",
                    "<fake-1@example.test>")

    def last_code(self) -> str:
        """The six-digit code in the last message (the line of its own)."""
        text = self.sent[-1][2]
        return next(line.strip() for line in text.splitlines() if line.strip().isdigit() and len(line.strip()) == 6)


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMINAL_LOGIN_DIR", str(tmp_path / "login"))
    for name in ("LIMINAL_LOGIN_PORT", "LIMINAL_LOGIN_SESSION_MINUTES", "LIMINAL_LOGIN_FOR",
                 "LIMINAL_SMTP_HOST", "LIMINAL_SMTP_USER", "LIMINAL_SMTP_PASSWORD", "LIMINAL_SMTP_FROM"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "login"


@pytest.fixture
def served(folder):
    """The app for charts without a mail account (the first user made on the page, as 0.1.0 did)."""
    lines: list[str] = []
    app = LoginApp(folder, log=lines.append, failure_delay=0, mailer=FakeMailer(configured=False))
    url = app.start(0)
    yield app, _port(url), lines
    app.close()


@pytest.fixture
def served_mail(folder):
    """The app for charts with a mail account: accounts are made with a code."""
    lines: list[str] = []
    mailer = FakeMailer(configured=True)
    app = LoginApp(folder, log=lines.append, failure_delay=0, mailer=mailer, scope=Scope.for_domain("example.test"))
    url = app.start(0)
    yield app, _port(url), lines, mailer
    app.close()


@pytest.fixture(autouse=True)
def _not_this_machines_mail_account(monkeypatch):
    """The tests never read this machine's mail account: no saved user variables, no secret store, no SMTP
    variables in the environment (the stand-in mailers say what they are)."""
    from liminal_libs import mail

    monkeypatch.setattr(mail, "_saved", lambda: {})
    monkeypatch.setattr(mail, "_secret", lambda name: None)
    monkeypatch.setenv("LIMINAL_LOGIN_CFG", "")  # nor this machine's login file: a test's login is local to its folder
    monkeypatch.setattr(Scope, "find", classmethod(lambda cls, start=None, env=None: None))
    for v in mail.ALL_VARS:
        monkeypatch.delenv(v, raising=False)
