# Changelog

## 0.15.3 (2026-11-10)

Held in another app's page (?embedded=1), the login draws no frame or colour of its own (the user, of a lighter box
drawn all round the platform's sign-in: "Yes, fix both"): the page's padding showed the frame's colour as a band round
the login's panel, from the top of the window to the bottom on the sign-in an app opens on, and inside your account and
the charts' bound view; in Light and Paper the panel itself is lighter than the page. Embedded, the page has no padding
and is see-through, its body and its panel alike: behind it the colour of the place holding it, in every theme. It is so
only when really held in a frame: opened on its own, its address asking `?embedded=1` or not, the page is the login's
own, its rail and its colours (see-through there it showed the browser's white canvas behind the dark themes' light
text).

## 0.15.2 (2026-11-10)

A remote login in Docker, prepared (the user: "we are going to use docker to setup such a remote / testing webserver";
"the platform app will be able to setup docker instances"; "just prepare for using docker on platform as a way to login
remotely with only the login-app"; "the login-app can login remotly to any liminal app that includes the platform app
object"). Nothing is built or run yet; the platform's Docker plugin will set it up on the engine chosen there.
- `docker/`: a Dockerfile building the login app from this checkout and liminal-libs' (compose gives it as the `libs`
  context: the code here, pushed or not), its users in the volume /data; compose.yaml with the app and a Caddy https
  front sharing its network, so the app still answers only 127.0.0.1; the Caddyfile (Caddy's own authority signs for
  LIMINAL_REMOTE_HOST, `tls internal`), which hands each request to the app with the app's own address as its Host and
  no Origin (the browser's Sec-Fetch-Site and the write header still guard it); the container's liminal-login.cfg, local
  to /data (no email: its users made on its own page or by its secret user).
- LIMINAL_LOGIN_CA: a certificate authority (PEM) a login trusts for remote logins besides the system's, the front's own
  copied out of it once; one that cannot be read is said when the app starts.

## 0.15.1 (2026-11-10)

The secret user's current password is the key the login keeps (the user: "for secret user the current password should
be a key that is greyed out, and exists but cannot be modified"): on its "Change your password" form the current
password is there, greyed out and never typed or shown; a new one typed becomes the key the database keeps, so the way
in by its name goes on working. Anyone else types their current password, as before. The card's "Kept at" says "over
https" for a remote login over https, "on this machine" otherwise.

## 0.15.0 (2026-11-10)

The users of other logins (the user: "make sure every login instance has a database, it's location can be remote"; "so
domain should be local or some domain remote.tld"; "login apps can connect to remote login apps"; "and shift context
to the remote execution"; "remote users are like email format user@remote.domain.tld"; "IPC turns in to encrypted
internet comms"):
- Every login keeps its own users in its own database, as before. A user of another login signs in here as
  name@their.domain: their login does the sign-in (their password, or their login's secret user by the lambda), over
  https, and everything they ask after (who they are, their password, their pairs) is asked of it with the session it
  gave; their sign-out here signs them out there too, and a session ended there ends here. Nothing of theirs is kept
  here but that session's token, behind this login's own cookie.
- Their login answers at https://their.domain unless liminal-login.cfg's `[remotes]` (or LIMINAL_LOGIN_REMOTES) names
  another address; never over plain http but to this machine.
- name@this.domain (a domain's login) is one of its own users; so is anyone here whose email is the address typed.
- The status says `remote`; `/api/me` gives their name@their.domain and `remote`; the card says where they are kept;
  the pairs a plugin here asks for are marked from their store there; this login's users are not listed to them.

## 0.14.1 (2026-11-10)

The secret user's name and password are values in the login's database (the user: "the user and the password should be
values in the database for login"), never in the code: a `settings` table in users.db keeps `secret_user` (`secret`
when it is made) and `secret_password` (random, made with it). The way in checks the name typed against the one kept,
so the page no longer knows it (it asks; anyone else goes on to their password), and changing the two values signs
another user in that way. A secret user made by 0.14.0 with the password it wrote in its code moves onto a random one
kept in the database, its pairs kept. The password is kept in the clear there: anyone with that file can open the
secret user's store.

## 0.14.0 (2026-11-10)

The secret user, the default way in (the user: "for now lets have a secret user, name - secret, no password entry, you
type secret in to user and click on icon"; "that will be the default"; "signup and sign-in should be options too"):
- Signed out, the page shows the lambda (a button), a User field, and Sign in and Sign up beside it. `secret` and the
  icon (or Enter) come straight in; any other name goes on to the password form with the name filled in.
- `POST /api/sign-in/secret {name: "secret"}`: a local login only (403 on a domain's), the secret user made the first
  time it is asked for. Its store opens with a password written in the code, so its keys are NOT protected by one; the
  page says so while it is signed in (`/api/me` `passwordless`). A user named secret with a password of their own is
  never let in this way (401), and nobody else comes in without a password (400).
- Sign up: a domain's login with an email server sends its code as before; a local login makes the account on the page,
  now without a session too (anyone at this machine; a domain's login still takes no account from the page once it has
  users). Sign in: the account name (or email) and the password, as before, with Back to the way in.

## 0.13.1 (2026-11-10)

The login app's icons are Liminal's sign, the brushed italic lambda (liminal-libs 1.44.0's `lambda`; the user: "replace
all user icons (login app) with the lambda sign"): its master icon (the tray an inheriting app draws, `ICON`), the
page's rail button, and the big icon on the sign-in, first-user and sign-up cards.

## 0.13.0 (2026-11-10)

On its own the login knows no other app (the user: "the log-in app should not point to platform, integrator or charts,
it should be standalone"; "when its inherited it can point to it's superclass, charts, platform, or integrator"):
- Without an app inheriting it, its users live in its own folder (`store/data/login/`, a domain's in its folder there)
  under its own cookie, `liminal_login`, the page names it by its file's title (Liminal) and the tray says Login. Before,
  a login with no `--for` was the charts app's.
- An app that inherits it, its superclass, says so when it starts it (liminal-libs 1.43.0's `inherited_by`:
  `LIMINAL_LOGIN_FOR`, `LIMINAL_LOGIN_FOR_TITLE`, `LIMINAL_LOGIN_FOR_URL`; `--for`, `--for-title`, `--for-url` by hand).
  Its users live apart in `<login folder>/<name>/` under `liminal_login_<name>`, as the charts app's always have, and
  the page names it as it said. No app is known here by name: any short name is one, never `users`, `logs` or `dkim`.
- The pairs a plugin asks for are no longer read from the plugin registry here: the superclass is asked (`GET <its
  address>/api/login/pairs`, kept a minute, its rows kept as data only), and the page lists them under "Pairs the plugins
  of <its title> ask for". On its own the page lists none; its examples name no plugin (`some-api-key`).
- No default port per app: 8795 unless `LIMINAL_LOGIN_PORT`, the file or `--port` says (the app that starts it gives
  the port it binds). `init` takes no `--serves`; `status` says "on its own" or "inherited by NAME". API 1.3: the
  status's `for` is null on its own, and `superclass` says who inherits it.

## 0.12.1 (2026-11-10)

Six things a look at the page found, mended (the user: "Yes, fix them"):
- The email field of the first-user form has a border and a background like the others (liminal-libs 1.42.1's
  liminal.css): it had neither and looked missing.
- The pair name's pattern is one a browser compiles: browsers read a pattern with the `v` flag, which refuses a bare `-`
  in a class, so the page checked nothing (the server's check stayed).
- The store says "1 pair", not "1 pairs".
- The tab is named for where the page is (sign in, the first user, sign up, or who is signed in), not "sign in" throughout.
- A pair is removed once asked in its row (Remove it? Remove / Keep; Escape takes it back), no longer through the
  browser's own confirmation box, which some browsers and views refuse (the pair then never removed). A failed removal
  says why in the row.
- A local login names no mail account: it sends no email, yet its status named this machine's (the sender's address
  among them) and its start-up line said "passkeys through direct". `/api/status`'s `signup` carries `local`; the
  first-user form says the login is local; `liminal-login status` says "no email (a local login)" before this machine's
  mail account (the one `mail test` and `mail dkim` use).

## 0.12.0 (2026-11-10)

Touch screens and the on-screen keyboard (the user: "let's do an update. I want to support touch as well as mouse
clicking on the interface ... We'll make sure it works across all apps"; "Support for virtual keyboard on tablets and
phones"), on liminal-libs 1.42.0's touch.js, which the page loads right after theme.js, and the viewport's
`interactive-widget=resizes-content` (Chrome on Android makes room above its keyboard). A mouse and a hardware keyboard
work as before. Every field calls up its keyboard: account names typed as they are (no capitals, no corrections; the
sign-in's with @ at hand for an email), an email the email keyboard, the mailed code the digits pad (and the code a
phone offers from its messages), a password as a password (a new one as new), a pair's name as it is, its label as free
text, its value a secret kept out of password managers. The keyboard's Enter says Next and moves to the next field until
a form's last field, whose Go, Send or Done sends the form. No keyboard pops up by itself on a phone or a tablet: a form
opens with no field focused until one is tapped (a mouse or a keyboard still finds the first field focused), and Add for
a pair a plugin asks for brings the Value field into view. A long press on the reveal and remove buttons shows what they
do, and screen readers name them; targets are about 40 px and fields' words 16 px on a touch screen (liminal.css); on a
phone the page is one column and the account's head wraps. The library at 1.42.0 or later.

## 0.11.1 (2026-11-07)

The page is painted in the UI's theme (the user: "add a preferences plugin for the 'UI' and add the different
themes"): the library's theme.js (liminal-libs 1.23.0) reads `GET /api/ui`, the theme the platform's Preferences
plugin keeps for every app's page (Dark, Midnight, Graphite, Light, Paper); a `theme` in the address wins.

## 0.11.0 (2026-11-07)

The mail server as a container (the user: "i want to integrate docker with the liminal framework"): the
login file's `[server]` section (image, name, context or host, hostname, ports, volumes, env_NAME, restart,
command) is the container, run through liminal-libs 1.18.0's docker driver: `liminal-login server up | down |
status | logs | pull | exec -- CMD | show`; `mail check` reports the container first. The library at 1.18.0
or later.

## 0.10.0 (2026-11-06)

The admin account of a domain's login, and the server checked with it (the user: "the login-app would need
it's own admin account ie. admin@liminal.domain.tld it would need to be valid in the DNS record ... the admin
account could be used to test the server so that it can send and receive with the user email and also see
if emails can be sent to other servers, without error"; "the container or email server, would be
responsible for services rendered outside the local domain"): `init --admin admin@<host under the
domain>` (the file's `admin`; the codes come from it); `liminal-login mail check [--to ADDRESS ...]
[--wait S]` (mailcheck.py: the admin host in DNS, SPF, the DKIM record when signing, a message to the admin
account and to each address with the server's answer, the admin mailbox read until the message is back;
0 when nothing failed); `mail setup` asks for the admin mailbox ([imap]) of a domain's login and keeps its
password in Windows Credential Manager. The library at 1.17.0 or later.

## 0.9.0 (2026-11-06)

What a login is tied to (the user: "have like a setup.cfg for the login, and then like other web apps use
that cfg file to decide the domain/scope of the login"; "login apps tied to domains (with email server) or
local (file://project/folder)"; "only allow signup if the login app is tied to an smtp server"):
`liminal-login.cfg` (liminal-libs 1.16.0 `apps.scope`), written by `liminal-login init SCOPE`, named by
`--cfg` or LIMINAL_LOGIN_CFG, else found. A local login (`file:///...`) takes no sign-up; a domain's
(`https://domain`) takes sign-ups for addresses at the domain (`members = any` for all) only with an email
server, the one its mail record names or the one under `[mail]`, which `mail setup` now writes there. The
status and the page say what the login is tied to and why a sign-up is off; the users' folder follows the
scope (a domain's under `login/<domain>/`); the file's port counts. The library at 1.16.0 or later.

## 0.8.0 (2026-11-06)

The app as the mail server of your own domain (the user: "it looks like i need a domain/email server for
this to work"): `liminal-login mail dkim init [--domain D] [--selector S]` makes a signing key for the
domain (kept in the login folder, `dkim/<domain>.<selector>.pem`, in no repository), saves
`LIMINAL_SMTP_DKIM_KEY`, `_SELECTOR` and `_DOMAIN`, and prints the TXT record to add at the domain;
`mail dkim check` says when the record is published and is this key's; `mail dkim show` prints it again.
From then on every message from an address at the domain is signed (liminal-libs 1.15.0 `dkim`), the
receipt says so (`sent.signed`), and `status` names the record. The library at 1.15.0 or later.

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
