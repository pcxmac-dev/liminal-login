"""The login app's tests: every store in a folder of the test's own (never store/data), the app on a
free port in a thread, no delay after a failed sign-in, no process started, nothing opened in a
browser."""
from __future__ import annotations

import pytest

from liminal_login.app import LoginApp


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMINAL_LOGIN_DIR", str(tmp_path / "login"))
    monkeypatch.delenv("LIMINAL_LOGIN_PORT", raising=False)
    monkeypatch.delenv("LIMINAL_LOGIN_SESSION_MINUTES", raising=False)
    return tmp_path / "login"


@pytest.fixture
def served(folder):
    lines: list[str] = []
    app = LoginApp(folder, log=lines.append, failure_delay=0)
    url = app.start(0)
    port = int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])
    yield app, port, lines
    app.close()
