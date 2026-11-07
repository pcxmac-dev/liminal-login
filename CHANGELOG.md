# Changelog

## 0.2.0 (2026-11-06)

An account asked for from the page, its passkey by email (the user: "i need a way to create a user and
send an email out, to an email server with correct credentials so that its not blocked, like proton or
gmail in order to obtain a passkey to create the account"; "this operation can be part lib, and part
login app"): the sending is the library's (liminal-libs 1.8.0 `mail.py`, one SMTP account of yours in
LIMINAL_SMTP_*), the sign-up this app's.

- `users.py`: a user carries an email and when it was verified; the sign-ups waiting for their passkey
  (`start_signup`, `signup`, `resend_signup`, `confirm_signup`): the password's material made at the
  ask, the passkey kept as a salted hash, five tries, fifteen minutes, a new one not sooner than a
  minute; a 0.1.0 file gains the columns. Sign in by name or email.
- `crypto.py`: passkeys (`new_code`: XXXX-XXXX from letters and digits never mistaken for one another,
  `normal_code`, `code_hash`).
- `app.py`: `POST /api/signup` (name, email, password: the passkey goes out, 202), `POST /api/signup/resend`,
  `POST /api/signup/confirm` (email, code, and the password again to be signed in at once); the first
  account is made with a passkey when a mail account is set (`POST /api/users` then refuses it), on the
  page without one when none is (as 0.1.0); `/api/status` says whether mail is set up and through whom.
- The page: Sign in (name or email) with "Create an account"; the account form; the passkey step with
  "Send it again"; the API paths relative, and `?embedded=1` hides the rail inside another app's page.
- `cli.py`: `mail test ADDRESS`, `user add NAME --email ADDRESS`, `status` names the mail account.

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
