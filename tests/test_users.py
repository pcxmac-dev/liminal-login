"""The users' file (users.py) and the cryptography behind it (crypto.py): a password is never
stored, its salted hash opens the vault key, a wrong one opens nothing, a change re-wraps."""
from __future__ import annotations

import json
import sqlite3

import pytest

from liminal_login import crypto
from liminal_login.users import UserStore


def test_a_user_is_made_from_a_name_and_a_password_and_nothing_of_either_is_kept(folder):
    users = UserStore(folder / "users.db")
    ada = users.create("Ada", "correct horse battery")
    assert ada.name == "Ada" and ada.seen_at is None and len(ada.vault_key) == 32 and len(ada.unlock_key) == 32
    assert ada.kdf["name"] == "scrypt" and ada.kdf["n"] == 2 ** 15
    assert users.count() == 1 and users.exists("Ada") and users.exists("ada") and not users.exists("Bob")
    assert ada.as_dict() == {"name": "Ada", "createdAt": ada.created_at, "seenAt": None}
    assert "vault_key" not in repr(ada) and "unlock_key" not in repr(ada)
    # the file holds the salt, the parameters, a verifier and the wrapped vault key: not the password, not the keys
    row = sqlite3.connect(str(folder / "users.db")).execute("SELECT * FROM users").fetchone()
    blob = b"".join(v if isinstance(v, bytes) else str(v).encode() for v in row)
    assert b"correct horse battery" not in blob and ada.vault_key not in blob and ada.unlock_key not in blob
    assert json.loads(row[2])["n"] == 2 ** 15
    users.close()


def test_the_password_opens_the_vault_key_and_a_wrong_one_opens_nothing(folder):
    users = UserStore(folder / "users.db")
    ada = users.create("Ada", "correct horse battery")
    back = users.verify("ada", "correct horse battery")  # the name is matched without regard to case
    assert back is not None and back.name == "Ada" and back.vault_key == ada.vault_key and back.seen_at is not None
    assert back.unlock_fingerprint == ada.unlock_fingerprint and back.vault_fingerprint == crypto.fingerprint(ada.vault_key)
    assert users.verify("Ada", "correct horse batter") is None and users.verify("Bob", "correct horse battery") is None
    assert users.verify("", "") is None and users.verify(None, None) is None
    assert users.names()[0]["seenAt"] == back.seen_at
    users.close()


def test_what_a_name_and_a_password_may_be(folder):
    users = UserStore(folder / "users.db")
    with pytest.raises(ValueError):
        users.create("", "correct horse battery")
    with pytest.raises(ValueError):
        users.create("x" * 41, "correct horse battery")
    with pytest.raises(ValueError):
        users.create("Ada\x00", "correct horse battery")
    with pytest.raises(ValueError):
        users.create("Ada", "short")
    users.create("Ada", "correct horse battery")
    with pytest.raises(ValueError):
        users.create("ADA", "another password")  # the same name, however written
    users.close()


def test_a_new_password_wraps_the_same_vault_key_again_and_a_new_name_binds_it(folder):
    users = UserStore(folder / "users.db")
    ada = users.create("Ada", "correct horse battery")
    with pytest.raises(ValueError):
        users.change_password("Ada", "wrong", "a longer new password")
    with pytest.raises(ValueError):
        users.change_password("Ada", "correct horse battery", "short")
    changed = users.change_password("Ada", "correct horse battery", "a longer new password")
    assert changed.vault_key == ada.vault_key and changed.unlock_key != ada.unlock_key and changed.salt != ada.salt
    assert users.verify("Ada", "correct horse battery") is None
    assert users.verify("Ada", "a longer new password").vault_key == ada.vault_key
    renamed = users.rename("Ada", "Ada Lovelace", "a longer new password")
    assert renamed.name == "Ada Lovelace" and renamed.vault_key == ada.vault_key
    assert users.verify("Ada Lovelace", "a longer new password") is not None and users.verify("Ada", "a longer new password") is None
    users.create("Bob", "another password")
    with pytest.raises(ValueError):
        users.rename("Bob", "ada lovelace", "another password")
    users.close()


def test_the_cryptography_binds_what_it_seals():
    key = crypto.new_key()
    nonce, sealed = crypto.seal(key, b"the value", b"massive-account-api-key")
    assert crypto.unseal(key, nonce, sealed, b"massive-account-api-key") == b"the value"
    with pytest.raises(crypto.Locked):
        crypto.unseal(key, nonce, sealed, b"another-name")  # moved under another name
    with pytest.raises(crypto.Locked):
        crypto.unseal(crypto.new_key(), nonce, sealed, b"massive-account-api-key")
    assert crypto.seal(key, b"x", b"n")[0] != crypto.seal(key, b"x", b"n")[0]  # a fresh nonce every time
    salt = crypto.new_salt()
    a, b = crypto.derive("pw", salt), crypto.derive("pw", salt)
    assert a == b and crypto.derive("pw", crypto.new_salt()) != a and crypto.derive("pW", salt) != a
    assert crypto.same(crypto.verifier(a), crypto.verifier(b)) and not crypto.same(crypto.verifier(a), crypto.verifier(crypto.new_key()))
    assert len(crypto.fingerprint(a)) == 12 and crypto.fingerprint(a) != crypto.fingerprint(crypto.verifier(a))
    with pytest.raises(ValueError):
        crypto.derive("pw", salt, {"name": "argon2"})
