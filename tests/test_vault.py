"""A user's store of pairs (vault.py): the names in the open, the values only with the key, a value
bound to its name."""
from __future__ import annotations

import sqlite3

import pytest

from liminal_login import crypto
from liminal_login.vault import KeyPairStore, store_file


def test_pairs_are_kept_sealed_and_listed_without_their_values(folder):
    key = crypto.new_key()
    store = KeyPairStore(folder / "users" / "ada.db", key)
    assert store.names() == [] and store.count() == 0 and store.fingerprint == crypto.fingerprint(key)
    info = store.put("Massive-Account-API-Key", "sk-live-0001", "key", "Massive, the paid plan")
    assert info["name"] == "massive-account-api-key" and info["kind"] == "key" and info["label"] == "Massive, the paid plan"
    store.put("massive-account-name", "ada@example.test", "account")
    assert [p["name"] for p in store.names()] == ["massive-account-api-key", "massive-account-name"]
    assert all("value" not in p for p in store.names())
    assert store.get("massive-account-api-key") == "sk-live-0001" and store.get("massive-account-name") == "ada@example.test"
    # the file gives nothing of a value
    blob = b"".join(bytes(v) if isinstance(v, bytes) else str(v).encode()
                    for row in sqlite3.connect(str(store.path)).execute("SELECT * FROM pairs") for v in row)
    assert b"sk-live-0001" not in blob and b"ada@example.test" not in blob
    # a new value for a name there already keeps its first date
    again = store.put("massive-account-api-key", "sk-live-0002", "key", "renewed")
    assert again["createdAt"] == info["createdAt"] and store.get("massive-account-api-key") == "sk-live-0002"
    assert store.count() == 2
    assert store.remove("massive-account-name") and not store.remove("massive-account-name")
    with pytest.raises(KeyError):
        store.get("massive-account-name")
    store.close()


def test_a_value_opens_only_with_the_key_and_under_its_own_name(folder):
    key = crypto.new_key()
    store = KeyPairStore(folder / "users" / "ada.db", key)
    store.put("claude-account-api-key", "the-key")
    store.close()
    other = KeyPairStore(folder / "users" / "ada.db", crypto.new_key())
    assert [p["name"] for p in other.names()] == ["claude-account-api-key"]  # the names, freely
    with pytest.raises(crypto.Locked):
        other.get("claude-account-api-key")
    other.close()
    con = sqlite3.connect(str(folder / "users" / "ada.db"))  # the row moved under another name
    con.execute("UPDATE pairs SET name = 'grok-account-api-key' WHERE name = 'claude-account-api-key'")
    con.commit()
    con.close()
    mine = KeyPairStore(folder / "users" / "ada.db", key)
    with pytest.raises(crypto.Locked):
        mine.get("grok-account-api-key")
    mine.close()


def test_what_a_pair_may_be_named_and_hold(folder):
    store = KeyPairStore(folder / "users" / "ada.db", crypto.new_key())
    for bad in ("", "-leading", "has space", "x" * 65, "UPPER CASE", "a/b"):
        with pytest.raises(ValueError):
            store.put(bad, "v")
    for bad in ("", "   ", "x" * 4097, "line\nbreak"):
        with pytest.raises(ValueError):
            store.put("ok-name", bad)
    with pytest.raises(ValueError):
        store.put("ok-name", "v", "secret")
    assert store.put("ok-name", "  v  ")["kind"] == "key" and store.get("ok-name") == "v"
    assert store.put("ok-name", "v", "detail", "x" * 200)["label"] == "x" * 80
    store.close()


def test_a_users_store_file_is_named_safely_and_uniquely(tmp_path):
    a = store_file(tmp_path, "Ada Lovelace")
    b = store_file(tmp_path, "Ada/Lovelace")
    assert a.parent == tmp_path and a.name.startswith("ada_lovelace-") and a.suffix == ".db" and a != b
    assert store_file(tmp_path, "../../etc") .parent == tmp_path and "/" not in store_file(tmp_path, "../../etc").name
    assert store_file(tmp_path, "日本語").name.startswith("user-")
