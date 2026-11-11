"""The Liminal login app (the user, 2026-11-03: "the authorization app, liminal-login, is kind of the
root authorization for all plugins and software integration, it provides the plugins with all the
key and account infrastructure"): the users (users.py), each with a store of key-vector pairs
(vault.py: API keys, account names, passwords, named `massive-account-api-key` and the like) that
only this app opens, with a key derived from the user's password; its page at its own port with the
one user icon (app.py, static/): sign in, sign out, who you are, your pairs and the fingerprints of
the keys that mask them. What other programs ask of it is the library's `liminal_libs.apps.LoginClient`."""

__version__ = "0.14.1"
