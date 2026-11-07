# Changelog

## 0.7.0 (2026-11-06)

`liminal-login mail setup [ADDRESS]` (the user: "the server isn't taking the email, its probably being
discarded"; "so it looks like i need a domain/email server"): the mail account typed once at the command
line (presets `bridge` for Proton Bridge on this machine, `gmail`, `direct`), the settings kept as your user
environment variables and the password in Windows' Credential Manager (liminal-libs 1.14.0 `secrets`), never
in the clear; a login app already running uses it at once; with ADDRESS a test message goes there after.
The README puts the account first (Proton Bridge, Gmail) and direct delivery as the fallback it is: a
message claiming your address from a home connection fails the provider's own checks and is filed away.
The library at 1.14.0 or later.

## 0.6.0 (2026-11-06)

Codes with no mail account (the user: "I only need you to send email, and the signup should take the
email, there should be no example domains used"; "you can use a terminal to send email if to the correct
port with right protocol"): with liminal-libs 1.13.0's direct delivery (`LIMINAL_SMTP_HOST=direct`,
`LIMINAL_SMTP_FROM` your address) a sign-up's code goes straight to the mail exchangers of the address
given, port 25 with TLS; the page says so on the email step; the README puts it first. The library at
1.13.0 or later.

## 0.5.0 (2026-11-06)

The mail server's word before you wait for a code (the user: "i never received an email ... i will need a
way to check the server response to see if it received the email and only if it did, does it wait for the
response, if no valid response than don't have me wait to enter a code"): `POST /api/signup` and
`/api/signup/resend` answer 202 only once the server took the message, with `sent` (the server, its reply
with the code, when, the message id: liminal-libs 1.12.0 `mail.Sent`), and the page shows it on the code
step; a refusal drops the sign-up and answers 503 in the server's own words, so nothing waits for a code
that never went out. `GET /api/status` carries the last send (`signup.lastSent`), shown on the email step
with the route the codes take (the host and the sender); `liminal-login mail test` prints the server's
answer and the message id.

## 0.4.0 (2026-11-06)

The pairs the plugins ask for (the user: "By the variables"): `GET /api/pairs/known` lists every key
variable of the plugins installed beside this app as a pair (`massive-api-key` for MASSIVE_API_KEY), with
the plugin, its label, whether it is a secret and whether the signed-in user has it; the page shows them
under your pairs, an Add on each fills the form, and the name field offers the ones you lack. The library
at 1.11.0 or later (`KeyVar.pair`).

## 0.3.1 (2026-11-06)

A browser carrying several cookies of this app's name (another path, an earlier sign-in): the live
session counts, and sign-out ends every session the browser carries.

## 0.3.0 (2026-11-06)

The sign-up in the user's order ("sign up lets you put in an email and sends an email to an email account,
which you then enter the 4-6 digit code back in to the signup prompt to generate a new user, password,
etcc"; "the user then has the ability to create an account name, and password"), and one login per
app ("each login-app instance is either tied to the chart app or the integrator app ... the context/name
space under which the user exists is either for the integrator or the chart app").

- A sign-up is the email first (`POST /api/signup {email}`: a six-digit code goes out), the code
  (`POST /api/signup/verify {email, code}`: the proof for the last step), then the account name and the
  password (`POST /api/signup/complete {email, token, name, password}`: the account made, verified,
  signed in). `/api/signup/confirm` and the eight-character passkey are gone; the page's three steps.
- `--for charts|integrator` (LIMINAL_LOGIN_FOR; charts by default): the app this instance serves. Its
  users live in that namespace's folder (`store/data/login/<for>/`), its cookie is `liminal_login_<for>`
  (cookies ignore ports) and its default port 8795 for charts, 8796 for the integrator; the page and the
  codes say which app ("Your Liminal Charts code"); `/api/status`, `/api/me` and `/api/app` carry `for`.
- The page tells the page holding it (the charts app's) when you sign in or out (postMessage).

## 0.2.1 (2026-11-06)

Bound into the charts app: `serve --until-quiet` ends the server once no page has been in touch for
LIMINAL_QUIET_SECONDS (600), what the charts app's front starts for itself when nothing answers at
LIMINAL_LOGIN_URL (liminal-libs 1.9.0's bindings); the page hides its own rail inside another app's page
(`?embedded=1`), that page's rail holding the user icon.

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
