# liminal-login

The Liminal login app: the users, each with a store of key-vector pairs (API keys, account names,
passwords) that only this app opens, with a key derived from the user's password; its page at its
own port with the one user icon: sign in, sign out, who you are, your pairs and the fingerprints of
the keys that mask them. What every other Liminal program and plugin asks of it is the library's
`liminal_libs.apps.LoginClient` (the user, 2026-11-03: liminal-login is "the root authorization for
all plugins and software integration, it provides the plugins with all the key and account
infrastructure").

## Run

```
pip install -e .
liminal-login                      # the page at http://127.0.0.1:8795/ (LIMINAL_LOGIN_PORT)
liminal-login serve --no-browser --port 8795
liminal-login user add NAME        # a user from the command line (the password typed hidden)
liminal-login user list
liminal-login status
```

The first visit of the page offers to create the first account: a passkey goes to your email (when a mail
account is set, below), or the first user is made on the page without one. Later accounts come from
"Create an account" on the sign-in page, each with its passkey; `user add` makes one from the command
line without. The users' file and the stores live in
`store/data/login/` of the Liminal workspace (`liminal_libs.layout.data_dir()`), or wherever
`LIMINAL_LOGIN_DIR` says; never in this repository.

## How a user's keys are kept

- The password is never stored. Its salted hash (scrypt, a salt and parameters per user) is the
  user's *unlock key*; what the file keeps to check a password is a hash of that key.
- A random *vault key* per user, wrapped under the unlock key (AES-256-GCM), seals every pair's
  value, the pair's name bound in: a value cannot be read without the password, nor moved under
  another name. Changing the password re-wraps the vault key; the pairs stay.
- A pair is named for what it is: `massive-account-api-key`, `claude-account-name`,
  `<plugin>-account-password`; its kind is `key`, `account`, `password` or `detail`.
- A session (sign-in) holds the keys in memory only, for the page (an HttpOnly cookie) and for the
  programs given its token (`X-Liminal-Session`); it ends at sign-out or after
  `LIMINAL_LOGIN_SESSION_MINUTES` (480) without a request.

## Sending the passkeys: your mail account

Set one SMTP account of yours in your user environment variables (never in a file of this app's;
`liminal_libs.mail`), so the receiving server sees a sender it knows and the message is not blocked:

| Variable | Gmail | Proton |
|---|---|---|
| `LIMINAL_SMTP_HOST` | `smtp.gmail.com` | `smtp.protonmail.ch` (Proton Business: an SMTP token), or `127.0.0.1` with Proton Bridge on this machine |
| `LIMINAL_SMTP_PORT` | `587` | `587`; the Bridge's `1025` |
| `LIMINAL_SMTP_SECURITY` | `starttls` | `starttls`; `none` for the Bridge on this machine |
| `LIMINAL_SMTP_USER` | your address | your address, or the Bridge's user |
| `LIMINAL_SMTP_PASSWORD` | an app password (2-step verification on) | the SMTP token, or the Bridge's password |
| `LIMINAL_SMTP_FROM` | `Liminal <you@gmail.com>` | `Liminal <you@proton.me>` |

Then `liminal-login mail test you@example.com` sends one message through it, and `liminal-login status`
says which account is set. A passkey is eight letters and digits in two groups, kept only as a salted
hash; it is good for fifteen minutes and five tries, and a new one can be asked for after a minute.

## The API

Only from this machine, only from the app's own pages or a program here (every write carries the
apps' header). `GET /api/status`, `POST /api/users`, `POST /api/sign-in`, `POST /api/sign-out`,
`POST /api/signup`, `POST /api/signup/resend`, `POST /api/signup/confirm`,
`GET /api/me`, `PUT /api/me/password`, `GET /api/pairs`, `GET|PUT|DELETE /api/pairs/<name>`,
`GET /api/tray`, `GET /api/app`.

Built on liminal-libs 1.8.0 (the apps' frame, outgoing mail). Tests: `pytest -q`.
