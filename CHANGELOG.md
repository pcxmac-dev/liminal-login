# Changelog

## 0.1.0 (2026-11-05)

The login app, the first app on liminal-libs' apps frame (the user, 2026-11-04: "let's just start
working on the login app specifically ... just have a port for that so that I can see just that one
icon, that basically lets me log in, lets me log out, gives me basic user information. When I click
on the icon, when I'm logged in, gives me an idea about the key value, database that's associated
with my user, and the encrypted hash that is used to mask the values").

- `users.py`: the users' file (a salt and scrypt parameters per user, a verifier of the unlock key,
  the vault key wrapped under it); create, verify, change the password (the vault key wrapped
  again), rename.
- `vault.py`: a user's store of key-vector pairs, every value sealed under the vault key with its
  name bound in (AES-256-GCM); the names listed in the open, the values only with the key.
- `app.py`: `LoginApp`, an `App` with the user icon at port 8795 (LIMINAL_LOGIN_PORT); sessions in
  memory (the page's HttpOnly cookie, a client's X-Liminal-Session), ended at sign-out or when idle
  (LIMINAL_LOGIN_SESSION_MINUTES); the routes of the page and of `liminal_libs.apps.LoginClient`.
- `static/`: the page: the first user created on the first visit, sign in, the user card (the store's
  file, the unlock key's and the vault key's fingerprints, the KDF), the pairs masked with a reveal
  each, add and remove, a password change, sign out.
- `cli.py`: `liminal-login serve`, `user add NAME` (the password typed hidden), `user list`, `status`.
- The folder: `LIMINAL_LOGIN_DIR`, else `store/data/login` of the workspace; never in a repository.
