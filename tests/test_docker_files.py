"""A remote login in Docker (docker/; 0.15.2, the user, 2026-11-10: "just prepare for using docker on platform as a way
to login remotely with only the login-app"): the files the platform will set up from, read as text (nothing is built or
run here); the front's way of handing requests to the app tried against the app itself; and the certificate authority a
login may trust for a remote's front (LIMINAL_LOGIN_CA)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from pathlib import Path

import pytest

from liminal_libs.apps import Scope
from liminal_libs.web import WRITE_HEADER
from liminal_login import app as app_mod
from liminal_login.app import LoginApp

DOCKER = Path(__file__).resolve().parents[1] / "docker"


def test_the_container_files_run_the_login_app_alone_behind_its_https_front():
    dockerfile = (DOCKER / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.13-slim" in dockerfile and "COPY --from=libs src /src/liminal-libs/src" in dockerfile
    assert "LIMINAL_LOGIN_DIR=/data/login" in dockerfile and "LIMINAL_LOGIN_CFG=/config/liminal-login.cfg" in dockerfile
    assert 'CMD ["liminal-login", "serve", "--no-browser", "--port", "8795"]' in dockerfile
    compose = (DOCKER / "compose.yaml").read_text(encoding="utf-8")
    for line in ("name: liminal-login-remote", "libs: ../../common", 'network_mode: "service:login"', "image: caddy:2.10-alpine",
                 '"${LIMINAL_REMOTE_PORT:-8443}:8443"', "./liminal-login.cfg:/config/liminal-login.cfg:ro", "login-data:/data"):
        assert line in compose, line
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:  # where PyYAML is installed, the file is read as compose reads it
        services = yaml.safe_load(compose)["services"]
        assert set(services) == {"login", "front"} and services["front"]["network_mode"] == "service:login"
    caddy = (DOCKER / "Caddyfile").read_text(encoding="utf-8")
    assert "{$LIMINAL_REMOTE_HOST}:8443 {" in caddy and "tls internal" in caddy and "reverse_proxy 127.0.0.1:8795 {" in caddy
    assert "header_up Host 127.0.0.1:8795" in caddy and "header_up -Origin" in caddy
    scope = Scope.read(DOCKER / "liminal-login.cfg")  # local to the container's /data: no email, users on its own page
    assert (scope.kind, scope.title, scope.port, scope.url) == ("local", "Liminal (remote)", 8795, "file:///data")


def _call(port, method, path, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=headers or {})
    r = conn.getresponse()
    raw = r.read()
    return r.status, raw


def test_the_front_hands_a_page_s_requests_to_the_app_as_a_page_of_its_own_machine(served):
    """Behind the front, a browser's page at https://remote.test sends Host remote.test and Origin https://remote.test:
    the app, answering only its own machine, refuses both. The Caddyfile hands them on with the app's own address as the
    Host and no Origin, and the app takes them; another site's page is still refused by its Sec-Fetch-Site, and a write
    still needs the app's own header."""
    app, port, lines = served
    page = {"Host": "remote.test", "Origin": "https://remote.test", "Sec-Fetch-Site": "same-origin"}
    assert _call(port, "GET", "/api/status", headers=page)[0] == 403  # as the browser sent it: not this machine's
    handed = {"Host": f"127.0.0.1:{port}", "Sec-Fetch-Site": "same-origin", "X-Forwarded-Proto": "https"}
    assert _call(port, "GET", "/api/status", headers=handed)[0] == 200
    write = {**handed, "Content-Type": "application/json", WRITE_HEADER: "1"}
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, write)[0] == 200
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, {**write, "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert _call(port, "POST", "/api/sign-in/secret", {"name": "secret"}, {k: v for k, v in write.items() if k != WRITE_HEADER})[0] == 403


def test_a_login_may_trust_a_remote_front_s_own_authority(folder, monkeypatch, tmp_path):
    """LIMINAL_LOGIN_CA: a certificate authority (PEM) trusted for remote logins besides the system's (the front's own,
    copied out of its container); one that cannot be read is said, never passed over."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "a test front's authority")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    pem = tmp_path / "front-root.crt"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setenv(app_mod.CA_VAR, str(pem))
    context = app_mod.remote_tls()
    assert any(c.get("subject") and "a test front's authority" in str(c["subject"]) for c in context.get_ca_certs())
    LoginApp(folder / "trusting", log=lambda m: None, failure_delay=0).close()
    monkeypatch.setenv(app_mod.CA_VAR, str(tmp_path / "missing.crt"))
    with pytest.raises(ValueError, match="LIMINAL_LOGIN_CA"):
        app_mod.remote_tls()
