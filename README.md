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
care about there. Sign in (a password) and Sign up are beside it. Nobody comes in without a password, and nobody
makes an account without a session or a mailed code, except at the login's own machine: by a request sent from the
machine itself (127.0.0.1) and not handed on by a front (0.20.0; the next paragraphs).

Sign-ins with a password are counted when they fail (0.20.0): after 10 wrong passwords for one name, or 30 from one
address, within 15 minutes, the next from there or for that name is answered at once (429, with Retry-After) until
the oldest of them is 15 minutes old. A try is counted before its key is derived and taken back unless it failed, so
the limits hold however many arrive together; four keys are derived at once from a front and four from the machine,
the others waiting their turn. The counts are kept in memory, and a restart forgets them. This machine's own are
counted too, apart from those of what a front hands on, so nobody who reaches a front keeps anyone at the machine out.
The secret user and `default`, who have no password to guess, never wait. A password change's current password is
counted the same way when it is wrong, for the user's name, with the failed sign-ins (0.20.3): past the limits the
change waits too, its keys derived behind the same gate. A sign-up's wrong codes are counted in the
same counts, by the address they came from and by the email the code was mailed to (30 and 10, the email as a name):
past either, a code typed is answered 429 before it is looked at, and no new code is sent for that email, or asked
from that address, until the wait is over. What the counts do not do:

- A name is counted as it was typed. An account's email, typed in its place, is counted apart from its name: 20 tries
  for an account that has one. A user of another login is counted once, however their domain is typed.
- There are 4096 counters at the most, the one touched longest ago dropped first: more names and addresses failing
  within 15 minutes than that make the oldest counts forgotten, and their limits start again.
- The address is the one a front was reached from. Behind some engines that is one address for everyone, and the 30
  are then everyone's together (the Docker steps below).

The users of other logins sign in as name@their.domain: their own login does the sign-in and everything they
ask after, over https (at https://their.domain, or the address `[remotes]` in liminal-login.cfg names:
`their.domain = https://login.their.domain:8443`). An address is taken from `[remotes]` alone: a host typed in a name
is a domain, and one typed with a scheme (name@http://...) is refused (0.20.0). Every login keeps its own users;
nothing of theirs is kept here but the session their login gave. A remote login is reached the way a page reaches it:
through a TLS front (Caddy, nginx) on its machine that passes requests on to its 127.0.0.1 port.

Such a front connects from 127.0.0.1 as a program on the login's machine does, so it marks every request it hands on:
`X-Liminal-Front: 1`, set over whatever a client sent (Caddy: `header_up X-Liminal-Front 1`; nginx:
`proxy_set_header X-Liminal-Front 1;`). Without the mark the login takes everyone who reaches the front for someone at
its machine, and a local login lets them in as its secret user, the admin. (A net under the mark, liminal-libs
1.98.0's: a request that carries X-Forwarded-For or X-Forwarded-Proto is not taken for the machine's either. It covers
a front that writes them unasked, as Caddy does, and no other.) Tie a login behind a front to its domain
(`scope = https://<its host>`): a domain's login has no user without a password.

The front must also say which address reached it and how, itself, over whatever a client sent: the last address of
X-Forwarded-For is what the sign-in counts go by, and when X-Forwarded-Proto says https the session cookie is Secure.
Caddy's `reverse_proxy` writes both by itself (docker/Caddyfile). nginx writes neither and hands a client's own on, so
its block needs all of these together (a block with a `proxy_set_header` of its own takes none from the levels above
it): `proxy_set_header Host 127.0.0.1:8795;`, `proxy_set_header Origin "";`, `proxy_set_header X-Liminal-Front 1;`,
`proxy_set_header X-Forwarded-For $remote_addr;` and `proxy_set_header X-Forwarded-Proto $scheme;`. With the mark
alone the counts go by an address the client writes, or by the front's own for everyone who writes none, and the
cookie is not Secure. (The nginx lines are as nginx documents them; they were not run here.)

A remote login in Docker (`docker/`, for the platform's Docker plugin to set up): the login app alone, built from this
checkout and liminal-libs', behind a Caddy https front that shares its network. It is the login of a domain, the host
its front answers at, and the front marks what it hands on: nobody comes in through it without a password, and nobody
makes an account through it without a session (0.20.0; until then the container's login was local, and anyone who
reached the front was its secret user). By hand, in that folder:

1. Say where it is deployed, in the environment or an `.env` file beside compose.yaml. `LIMINAL_REMOTE_HOST`: the
   https host the front answers at, which is the login's own domain (`localhost` unless said; the users are kept by
   domain, in the volume's `login/<host>/`, so say it before the first user is made). `LIMINAL_REMOTE_PORT`: the port
   (`8443`). `LIMINAL_REMOTE_BIND`: the address the port is published on, this machine alone (`127.0.0.1`) unless it
   names a wider one (`0.0.0.0` for every interface, or one address, a LAN's or a tailnet's).
2. `docker compose up -d --build`.
3. The first user: `docker compose exec login liminal-login user add NAME` (the password typed hidden, twice). The page
   makes no account there. The next users are made the same way, or by a user signed in (`POST /api/users`).
4. Another login reaches its users as name@<LIMINAL_REMOTE_HOST>: its `[remotes]` names
   `<LIMINAL_REMOTE_HOST> = https://<LIMINAL_REMOTE_HOST>:<LIMINAL_REMOTE_PORT>`, and LIMINAL_LOGIN_CA trusts the
   front's authority (`docker compose cp front:/data/caddy/pki/authorities/local/root.crt ./front-root.crt`).

The sign-in counts go by the address the front itself was reached from, and that is the browser's own only where the
engine hands it through: Docker Engine on Linux with the port published wider than 127.0.0.1. Published on 127.0.0.1
(the default), behind Docker Desktop or rootless Docker, from an engine inside WSL reached from Windows, or behind a
tunnel or a proxy on the host, it is one address for everyone. The 30 from one address are then 30 in all: thirty
wrong passwords from anyone who reaches the front make every sign-in with a password through it wait, the right
password too, up to 15 minutes at a time (the 10 for a name still go by the name). `docker compose restart` (both
services: the front shares the login's network) forgets the counts and signs everyone out. The recipe has not been run
in Docker yet: its files are tested as text and its front's requests against the app, and what each engine hands the
front is said here from how its port publishing is known to work, not from a run.

compose.yaml hands the host to the login as `LIMINAL_LOGIN_SCOPE` (`https://<LIMINAL_REMOTE_HOST>`), said over the
`scope` line of docker/liminal-login.cfg.

Sign-up by email is closed in the recipe, whatever mail record the host has (0.20.0): docker/liminal-login.cfg says
`signup = closed`, and compose.yaml says it too (`LIMINAL_LOGIN_SIGNUP: "closed"`) for a copy of that file from
before the line. The page's Sign up and every step of a sign-up (`/api/signup` and the three under it) then answer
with how it is opened, and accounts are made as in step 3. To open it:

5. Write `signup = open` under `[login]` in docker/liminal-login.cfg and start the login again (`docker compose
   restart`: the file is read when the login starts). The file's own line is over compose.yaml's word, which only
   closes. The host also needs an email server for the codes: the one its mail record (MX) names, or one named under
   the file's `[mail]`.

What opening it means: whoever reaches the front and reads the mail of an address at the host makes an account there,
and nobody at the machine is asked (`members = any` lets an address anywhere in). The code mailed is six digits, good
for fifteen minutes and five tries. Wrong codes are counted with the wrong passwords: ten for the email a code was
mailed to, or thirty from an address, in 15 minutes, and a new code gives none of them back. That slows the guessing
of a code and does not end it, and an account made with a guessed code is one whose maker never read the mailbox.
Where every client reaches the front from one address (above), thirty wrong codes also make every sign-in with a
password through it wait, as thirty wrong passwords do. Leave it closed unless accounts are meant to be made by
whoever holds a mailbox at the host.

Signing up is three steps: your email (a six-digit code goes to it, when a mail account is set, below),
the code, then your account name and password. The first visit offers it; later accounts come from
"Sign up" on the sign-in page; `user add` makes one from the command line without a code. A local login sends no
email: its accounts are made on the page without a code, by anyone at its own machine. A domain's login without an
email server, or with sign-up by email closed (`signup = closed`, below), makes none on the page, not even its first
(0.20.0): its first user is made at its machine with `liminal-login user add NAME`, the next the same way or by a user
signed in (`POST /api/users`).

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
  to send through; a domain with neither takes no sign-up, and its first user is made at its machine with
  `liminal-login user add NAME` (0.20.0: never on the page without a session). The users live under the data
  folder's `login/<domain>/`.

`signup = open` or `signup = closed`, under `[login]`, says whether a domain's login takes sign-ups by email at all
(0.20.0). Closed, it takes none, whatever email server it has, and the page's Sign up and every `/api/signup` route
say how it is opened. Open, it takes them once it has its email server, as above. A file with no such line does as
it always did, a domain's login taking sign-ups when it has an email server, unless `LIMINAL_LOGIN_SIGNUP` is set
where `liminal-login serve` runs (docker/compose.yaml sets it to `closed`): then it is closed until the file's own
line says `open`. The variable only closes, whatever it says; like `LIMINAL_LOGIN_SCOPE` it is the command's alone,
and a login made in code never reads it. A word in the file that is neither `open` nor `closed` closes too, and the
page says so. A local login has no sign-up by email whatever is said. `mail setup`, which writes the file back,
keeps the line; `init` writes none.

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
it finds, and the page says what the login is tied to. `LIMINAL_LOGIN_SCOPE` says the scope over the file's own
line to the `liminal-login` command alone (0.20.0; docker/compose.yaml sets it): `serve` and `user` then speak of
the same login, and so do `status`, `mail check`, `server` and the folder `mail dkim` keeps its key in; `mail setup`
writes the file's own scope back, and a login made in code, the one an app holds, never reads it.

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
minutes and five tries, and a new one can be asked for after a minute. Its five tries spent, a code is
compared no more, and the next goes out no sooner than a minute after the last of them (0.20.0: the
sign-up was dropped then, and begun again at once). Wrong codes are counted with the wrong passwords
(Run, above).

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
apps' header). `GET /api/status`, `POST /api/users` (without a session: a local login only, from its own machine),
`POST /api/sign-in` (429 with Retry-After once too many have failed), `POST /api/sign-in/secret` (a local login's
users without a password, from its own machine),
`POST /api/sign-out`,
`POST /api/signup`, `POST /api/signup/resend`, `POST /api/signup/verify`, `POST /api/signup/complete` (503 with how
it is opened while sign-up by email is closed; the first three 429 with Retry-After once too many codes have been
wrong),
`GET /api/me`, `PUT /api/me/password` (429 with Retry-After once too many passwords have been wrong, 0.20.3),
`GET /api/pairs`, `GET|PUT|DELETE /api/pairs/<name>`,
`GET /api/pairs/known` (the pairs an inheriting app's plugins ask for; none on its own), `GET /api/tray`,
`GET /api/app`, `GET /api/login-plugins`, `GET|POST /api/login-plugins/<name>/<tab>` (0.18.0). On a liminal-libs older
than the one the login needs (1.98.0) every one of them answers 503 and says so (0.20.0).

`GET /api/app/apis` is the login's own External and Internal API (0.20.1), the page's This app: what its own code
associates with (src/liminal_login/apis.py), its routes (routes.py, then the frame's), the apps it reaches and what its
code calls on its plugins. Like `GET /api/codebase`, it is answered to one of its own users signed in to a local login
alone: 401 signed out, 403 to a user of another login and on a domain's login. `GET /api/app/apis?plugin=NAME` is one of
its plugins' two views, as every app answers them, asked with a session as its plugins' list and pages are (401
signed out; any signed-in user, a user of another login too).

## Its plugins (0.18.0)

The login attaches the login plugins installed (liminal-libs 1.92.0's `LoginPlugin`; the first is
`plugin-login-datastore`). Each is a line in the page's list, its own tabs followed by External API and Internal API.
A plugin is shown only what the login hands it for the person asking: their name, whether they are its admin (the
secret user), their own keystore by pair names, kinds and dates (never a value, never another user's), and where the
login keeps its users. A change on a tab only the admin may change is refused to anyone else before the plugin is
asked. What a plugin keeps is kept in the login's own folder's users file (`settings`, `plugin:<name>`).

The datastore's Global tab keeps where the login's users are as a preference (0.19.0, with plugin-login-datastore
0.2.0): a kind of database and its location as a URL (`file:///...` for a SQLite file or folder; a PostgreSQL, MariaDB,
MongoDB or DuckDB location is refused, "not supported yet": the login's stores are SQLite only), an instance of
the platform's Databases section filling it in, and a local fallback folder (`app/.data` in the home folder unless
another is kept) used when the preferred location cannot be used at a start. Changed by the admin alone, confirmed
twice, refused for a location that holds anything but a login's users and whenever there are users on both sides. The
login reads its users and keystores from there from its next start; its own folder's file keeps its own settings, so it
can be pointed back. With no preferred location ever kept nothing changes: its users stay in its own folder. Moving
users is never done, by the page or at a start. A start in the fallback folder, or on its own folder because a place
could not be opened, is said in the log, the status (`place.fallback`, `place.note`; the status never names a location)
and on the Global tab.

Inherited today by the charts app (liminal-charts): its front serves this page under `/login/`, draws the
user icon at the foot of its rail and, when nothing answers at `LIMINAL_LOGIN_URL` (8795), starts this app
for itself as its superclass. Built on liminal-libs 1.43.0 (the apps' frame, outgoing mail, the bindings,
`inherited_by` and `pairs_wanted`). Tests: `pytest -q`.
