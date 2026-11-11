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
liminal-login serve --no-browser --until-quiet   # what an app that inherits it starts: ends when no page is in touch
liminal-login user add NAME        # a user from the command line (the password typed hidden)
liminal-login user list
liminal-login status
```

The way in, for now: type `secret` as the user and click the lambda (or press Enter): the secret user comes in
without a password on a local login, made the first time. Its keys are not protected by a password: keep nothing you
care about there. Sign in (a password) and Sign up are beside it.

The users of other logins sign in as name@their.domain: their own login does the sign-in and everything they
ask after, over https (at https://their.domain, or the address `[remotes]` in liminal-login.cfg names:
`their.domain = https://login.their.domain:8443`). Every login keeps its own users; nothing of theirs is kept here
but the session their login gave. A remote login is reached the way a page reaches it: through a TLS front (Caddy,
nginx) on its machine that passes requests on to its 127.0.0.1 port.

Signing up is three steps: your email (a six-digit code goes to it, when a mail account is set, below),
the code, then your account name and password. The first visit offers it; later accounts come from
"Sign up" on the sign-in page; `user add` makes one from the command line without a code, and without a
mail account the first user is made on the page without one.

On its own the login knows no other app: its users, their stores and its cookie (`liminal_login`) are its
own, and the page names it by its file's title. An app that inherits it (its superclass: charts, the
platform, the integrator) says so when it starts it, with `liminal_libs.apps.inherited_by`: `LIMINAL_LOGIN_FOR`
(its short name), `LIMINAL_LOGIN_FOR_TITLE` (how the page names it) and `LIMINAL_LOGIN_FOR_URL` (its address),
or `--for`, `--for-title` and `--for-url` by hand. That app's users then live apart, in
`store/data/login/<name>/` under the cookie `liminal_login_<name>`, and the pairs its plugins ask for are asked
of it (`GET <its address>/api/login/pairs`, which every app of the library's frame answers from its plugins):
the login reads no plugin itself. The users' files and the stores live in `store/data/login/` of the Liminal
workspace (`liminal_libs.layout.data_dir()`), or wherever `LIMINAL_LOGIN_DIR` says; never in this repository.

## How a user's keys are kept

- The password is never stored. Its salted hash (scrypt, a salt and parameters per user) is the
  user's *unlock key*; what the file keeps to check a password is a hash of that key.
- A random *vault key* per user, wrapped under the unlock key (AES-256-GCM), seals every pair's
  value, the pair's name bound in: a value cannot be read without the password, nor moved under
  another name. Changing the password re-wraps the vault key; the pairs stay.
- A pair is named by the plugin's variable: `massive-api-key` for `MASSIVE_API_KEY`, `claude-account` for
  `CLAUDE_ACCOUNT` (the page lists the pairs the plugins installed here ask for); its kind is `key`,
  `account`, `password` or `detail`.
- A session (sign-in) holds the keys in memory only, for the page (an HttpOnly cookie) and for the
  programs given its token (`X-Liminal-Session`); it ends at sign-out or after
  `LIMINAL_LOGIN_SESSION_MINUTES` (480) without a request.

## What a login is tied to: liminal-login.cfg

The user's words: "have like a setup.cfg for the login, and then like other web apps use that cfg file to
decide the domain/scope of the login"; "login apps tied to domains (with email server) or local
(file://project/folder)". The file's `[login] scope` is a URL:

- `file:///C:/Users/you/source/liminal`: a local login for that project folder. No email, no sign-up: the
  first user is made on the page or with `liminal-login user add NAME`, the next by a signed-in user. The
  users live in the folder's `store/data/login/` (or `.liminal/login/`).
- `https://your-domain.example`: the domain's users (`members = any` lets other addresses in). Codes go
  through the domain's own email server, the one its mail record (MX) names, unless `[mail]` names a server
  to send through; a domain with neither takes no sign-up. The users live under the data folder's
  `login/<domain>/`.

A domain's login has an account of its own, `admin = admin@<a host under the domain>` (`admin@liminal.your-domain.example`,
say; `admin@<domain>` unless said): the codes come from it, and its host must be valid in DNS (an address or
a mail record). With it the login checks its mail server: `liminal-login mail check --to you@... --to
someone@another-server` looks the host up, sends a message to the admin account itself and to each address
given (yours; one on another server), each with the server's own answer, and reads the admin mailbox (the
file's `[imap]` section, asked by `mail setup`) until its own message is there. The mail server, your own
container or a relay, carries everything beyond the local domain; the login only hands it the messages.

The mail server itself can be a container the file declares under `[server]` (`image = foxcpp/maddy:latest`,
say, with its `ports`, `volumes` such as `./mail:/data` under the login's data, `env_NAME = value` for its
environment, and a `context` when it runs on another machine's Docker, a VPS over SSH: `docker context
create vps --docker host=ssh://user@vps`). `liminal-login server up` makes or starts it, `down` stops it
with its data kept, `status`, `logs`, `pull`, `exec -- CMD` (a command inside it, `maddy creds create
admin@...`), `show` (the docker run line); `mail check` reports the container first. The framework's
driver is `liminal_libs.docker`, over the docker command alone.

`liminal-login init file:///... | https://domain [--title T] [--port P] [--admin A]` writes
the file (a local one into the folder itself, a domain's into the workspace); `liminal-login --cfg PATH`
or `LIMINAL_LOGIN_CFG` names it, else every app finds `liminal-login.cfg` in the workspace, in the working
folder or one above it, or in the data folder's `login/`. The charts front starts the login with the file
it finds, and the page says what the login is tied to.

## Sending the codes

Set it once from the command line: `liminal-login mail setup` asks for the account and keeps the settings as
your user environment variables and the password in Windows' Credential Manager (never a file, never the
registry in the clear; `liminal_libs.mail`, `liminal_libs.secrets`). `liminal-login mail test you@proton.me`
then sends one message and prints the server's answer. A login app already running uses the account at once.

**Through a mail account of yours**, so the receiving server sees a sender it knows and signs for:

- Proton (a custom domain means a paid plan, and every paid plan includes Proton Bridge): install the
  Bridge, sign in to it, and answer `bridge` at the host prompt (127.0.0.1, port 1025, STARTTLS with the
  Bridge's own certificate); the user and the password are the ones the Bridge window shows for your
  account. Proton for Business can use an SMTP token at smtp.protonmail.ch:587 instead.
- Gmail: `gmail` at the host prompt (smtp.gmail.com, 587, STARTTLS); your address and an app password
  (2-step verification on).

The variables, should you set them by hand:

| Variable | Gmail | Proton |
|---|---|---|
| `LIMINAL_SMTP_HOST` | `smtp.gmail.com` | `smtp.protonmail.ch` (Proton Business: an SMTP token), or `127.0.0.1` with Proton Bridge on this machine |
| `LIMINAL_SMTP_PORT` | `587` | `587`; the Bridge's `1025` |
| `LIMINAL_SMTP_SECURITY` | `starttls` | `starttls`; `none` for the Bridge on this machine |
| `LIMINAL_SMTP_USER` | your address | your address, or the Bridge's user |
| `LIMINAL_SMTP_PASSWORD` | an app password (2-step verification on) | the SMTP token, or the Bridge's password |
| `LIMINAL_SMTP_FROM` | `Liminal <you@gmail.com>` | `Liminal <you@proton.me>` |

**Direct, no account** (`direct` at the host prompt: `LIMINAL_SMTP_HOST=direct`, `LIMINAL_SMTP_FROM` your
address): each message goes straight to the mail exchangers of the address it is for, on port 25 with TLS,
the way one mail server hands a message to another; the machine announces itself as `LIMINAL_SMTP_HELO`,
else its full name, else `liminal.local`. A fallback, not the way: a message that claims your address but
comes from a home connection fails your provider's own checks (SPF, DKIM, DMARC: Proton quarantines such
a message for proton.me even after answering 250), so it lands in spam or nowhere. The app keeps the
server's answer, shows it on the page and waits for a code only once the answer was 250.

`liminal-login mail test you@proton.me` sends one message and prints the server's answer, and `liminal-login status`
says which account is set. A code is six digits, kept only as a salted hash; it is good for fifteen
minutes and five tries, and a new one can be asked for after a minute.

## Your own domain: the app as its mail server

The user's words: "it looks like i need a domain/email server for this to work". A domain whose mailboxes a
provider holds (Proton, Gmail) has its mail server already: that provider, which signs and vouches for the
domain; send through it (`liminal-login mail setup`, above). What follows is for a domain, or a subdomain,
that no provider holds: the domain is yours and the server can be this app. It signs what it sends for the
domain (DKIM, `liminal_libs.dkim`), and one DNS record at the domain lets any receiving server check the
signature, so a message from an address at the domain passes the domain's own policy (DMARC) wherever it
lands, home connection or not:

1. `liminal-login mail setup`: `direct` at the host prompt, and a From address at your domain.
2. `liminal-login mail dkim init`: a signing key, kept in the login folder (`dkim/<domain>.<selector>.pem`,
   in no repository); it prints the TXT record to add, `liminal._domainkey.<domain>`, where the domain's
   DNS records live (the registrar or DNS host, not the mailbox provider).
3. `liminal-login mail dkim check` once the record is published; `liminal-login mail test you@...` then
   shows the server's answer, and at the receiving end the message's own headers say `dkim=pass`.

Two more records help: the domain's SPF record may name this machine's address (`ip4:...`, which changes
with the connection), and `LIMINAL_SMTP_HELO` may be a name under your domain with an A record for this
machine (`host.your-domain.example`). Some receivers also want a reverse name for the sending address,
which only the connection's provider can set; a message to such a receiver goes through an account.

## The API

Only from this machine, only from the app's own pages or a program here (every write carries the
apps' header). `GET /api/status`, `POST /api/users`, `POST /api/sign-in`, `POST /api/sign-in/secret` (a local login's secret user),
`POST /api/sign-out`,
`POST /api/signup`, `POST /api/signup/resend`, `POST /api/signup/verify`, `POST /api/signup/complete`,
`GET /api/me`, `PUT /api/me/password`, `GET /api/pairs`, `GET|PUT|DELETE /api/pairs/<name>`,
`GET /api/pairs/known` (the pairs an inheriting app's plugins ask for; none on its own), `GET /api/tray`,
`GET /api/app`.

Inherited today by the charts app (liminal-charts): its front serves this page under `/login/`, draws the
user icon at the foot of its rail and, when nothing answers at `LIMINAL_LOGIN_URL` (8795), starts this app
for itself as its superclass. Built on liminal-libs 1.43.0 (the apps' frame, outgoing mail, the bindings,
`inherited_by` and `pairs_wanted`). Tests: `pytest -q`.
