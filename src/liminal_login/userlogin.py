"""A browser's session as the library's Login (0.17.7; Monday list item 21; the user, 2026-11-19: "preferences, keys,
licenses all get stored in the individual's login db"): what an app that holds this login asks for the person at a
browser (liminal_libs.apps.App.user_login, through LoginApp.user_login). Their keys, their preferences and the
licences they accepted are pairs of their own store: a preference or a licence a pair of that kind holding JSON
(liminal_libs.apps.authorization.PREFERENCE, LICENCE), never a key read as one. A user of another login is answered
by their own login, with the session it gave, as their pairs are. The vault closed under a request (signed out, idled
out) is a refusal like any other (401), so a reader falls back as it would with nobody signed in."""
from __future__ import annotations

import urllib.parse

from liminal_libs.apps.authorization import (SETTING_KINDS, Login, Unauthorized, decode_setting, encode_setting,
                                             setting_kind)

from .vault import VaultClosed


class SessionLogin(Login):
    """One of this login's own users, signed in at a browser: their store (the session's vault), open while the
    session is."""

    keeps_settings = True

    def __init__(self, app, session):
        self.app, self.session = app, session
        self.NAMESPACE = getattr(app, "namespace", None) or "login"

    def _vault(self):
        vault = getattr(self.session, "vault", None)
        if vault is None:
            raise Unauthorized("this session keeps no store here", 405)
        return vault

    def user(self) -> dict:
        return {"name": self.session.user.name, "email": getattr(self.session.user, "email", None)}

    def vector(self, name: str) -> str:
        try:
            return self._vault().get(name)
        except KeyError:
            raise Unauthorized(f"no {name} here", 404) from None
        except VaultClosed as e:
            raise Unauthorized(str(e), 401) from None
        except ValueError as e:
            raise Unauthorized(str(e), 400) from None

    def names(self) -> set[str] | None:
        try:
            return {p["name"] for p in self._vault().names()}
        except (VaultClosed, Unauthorized):
            return None

    def setting(self, name: str):
        vault = self._vault()
        try:
            info = vault.info(name)
            if info is None:
                return None
            if info["kind"] not in SETTING_KINDS:
                raise Unauthorized(f"the pair {name} is a {info['kind']}, not a preference or a licence", 409)
            return decode_setting(vault.get(name))
        except KeyError:
            return None
        except VaultClosed as e:
            raise Unauthorized(str(e), 401) from None
        except ValueError as e:
            raise Unauthorized(str(e), 400) from None

    def keep_setting(self, name: str, value, kind: str = "preference", label: str = "") -> dict:
        vault = self._vault()
        try:
            info = vault.put(name, encode_setting(value), setting_kind(kind), label)
        except VaultClosed as e:
            raise Unauthorized(str(e), 401) from None
        except ValueError as e:
            raise Unauthorized(str(e), 400) from None
        self.app.log(f"login: {self.session.user.name} kept the pair {info['name']} ({info['kind']})")
        return info


class RemoteSessionLogin(Login):
    """A user of another login, signed in here: their pairs asked of their own login with the session it gave."""

    keeps_settings = True

    def __init__(self, app, session):
        self.app, self.session = app, session
        self.NAMESPACE = getattr(app, "namespace", None) or "login"

    def _ask(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        try:
            return self.app._remote_call(self.session.remote, method, path, body, self.session.remote_token)
        except Exception as e:  # noqa: BLE001 - Refused (it does not answer): a refusal here
            raise Unauthorized(str(getattr(e, "reason", e)), 503) from None

    def _pair(self, name: str) -> str:
        return "/api/pairs/" + urllib.parse.quote(name, safe="")

    def user(self) -> dict:
        return {"name": self.session.user.name, "remote": self.session.remote}

    def vector(self, name: str) -> str:
        status, data = self._ask("GET", self._pair(name))
        if status != 200:
            raise Unauthorized(str(data.get("error") or f"no {name} at {self.session.remote}"), status)
        return str(data.get("value") or "")

    def setting(self, name: str):
        status, data = self._ask("GET", self._pair(name))
        if status == 404:
            return None
        if status != 200:
            raise Unauthorized(str(data.get("error") or f"{self.session.remote} said no"), status)
        if data.get("kind") not in SETTING_KINDS:
            raise Unauthorized(f"the pair {name} is a {data.get('kind') or 'pair'}, not a preference or a licence", 409)
        return decode_setting(data.get("value"))

    def keep_setting(self, name: str, value, kind: str = "preference", label: str = "") -> dict:
        try:
            body = {"value": encode_setting(value), "kind": setting_kind(kind), "label": label}
        except ValueError as e:
            raise Unauthorized(str(e), 400) from None
        status, data = self._ask("PUT", self._pair(name), body)
        if status != 200:
            raise Unauthorized(str(data.get("error") or f"{self.session.remote} said no"), status)
        return data
