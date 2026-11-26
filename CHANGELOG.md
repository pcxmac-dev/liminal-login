# Changelog

## 0.20.0 (2026-11-25)

The remote login in Docker no longer lets in, as its admin, anyone who reaches it: LOG-C1 of the independent review
(checked 2026-11-23, rated high; the user, 2026-11-23: "The two high ones"; with liminal-libs 1.98.0, the floor now).
docker/compose.yaml published the front's port on every interface. The front, Caddy in the login's own network,
connects from 127.0.0.1 and handed every request on as `Host: 127.0.0.1:8795` with no Origin, and the container's
login was local (`scope = file:///data`). So `POST /api/sign-in/secret` signed anyone in as `secret`, the admin, or
as `default`, with no password; `POST /api/users` made accounts without a session; and the session cookie had no
Secure flag. On this machine, without a front, the ways in are as they were: the secret user and `default` come in by
their names, and the page's Sign up makes an account on a local login.
- The container's login is a domain's, the https host its front answers at: docker/liminal-login.cfg says
  `scope = https://localhost`, and compose.yaml says the host once, over that line
  (`LIMINAL_LOGIN_SCOPE: "https://${LIMINAL_REMOTE_HOST:-localhost}"`). A domain's login has no user without a
  password. Its users are kept by domain (the volume's `login/<host>/`): a container made from the recipe before
  this kept them in `login/` itself, and starts here without them.
- LIMINAL_LOGIN_SCOPE is the command line's alone (the user, 2026-11-24). `liminal-login`'s commands read it in one
  place (`cli._scope`, `cli.scoped`): `serve` and `user` in the same folder, `status`, `mail check` and `server` of
  the same login, `mail dkim`'s key in the same folder; `mail setup` writes the file's own scope back. A login made in
  code never reads it, so a variable left set on a machine cannot turn the login an app holds (the platform's, the
  charts') into a domain's, with other users in another folder.
- A domain's login makes no account without a session or a mailed code, not even its first. `POST /api/users` answers
  403 with how the first user is made (`liminal-login user add NAME` at its machine; in Docker `docker compose exec
  login liminal-login user add NAME`) and 401 once it has users. Until now a domain's login without an email server
  made its first account for whoever asked first. The page's Sign up says why instead of drawing the form, and
  `user list` with no users yet no longer names the page's first visit there.
- Only at the login's own machine: a sign-in without a password (`POST /api/sign-in/secret`; another login's secret
  user, asked there, too) and an account made without a session on a local login are refused (403) unless the request
  was sent from this machine itself and not handed on by a front (liminal-libs' `web.from_this_machine`: a loopback
  peer, no X-Liminal-Front and, as a net under the mark, no X-Forwarded-For or X-Forwarded-Proto). The front marks
  every request it hands on (docker/Caddyfile: `header_up X-Liminal-Front 1`). A page here, a program here, an app's
  front passing a page's request on and a login an app holds are answered as before.
- Secure behind TLS: when the front says the browser came over https (X-Forwarded-Proto), every cookie the login sets
  or clears is Secure.
- Published on this machine alone unless said: compose.yaml's port is
  `${LIMINAL_REMOTE_BIND:-127.0.0.1}:${LIMINAL_REMOTE_PORT:-8443}:8443`, and `LIMINAL_REMOTE_BIND` names a wider
  address (`0.0.0.0`, or one of the machine's).
- Sign-ins with a password are throttled (throttle.py; the user, 2026-11-24: it stays as built). After 10 wrong
  passwords for one name, or 30 from one address, within 15 minutes, the next from there or for that name is answered
  429 with Retry-After, before any key is derived or another login is asked, until the oldest is 15 minutes old.
  Counted in memory (a restart forgets), in at most 4096 counters; this machine's own counted too, apart from those of
  what a front hands on; a wrong password at another login (name@their.domain) counted here as well. The secret user
  and `default`, in without a password, never wait. `LoginApp(throttle=...)` takes one of a test's own.
- The README has the deploy steps (LIMINAL_REMOTE_HOST, LIMINAL_REMOTE_PORT, LIMINAL_REMOTE_BIND, the first user, how
  sign-up by email is opened and what that means), what a front of one's own must set (the mark, and nginx's lines in
  full), and its lines on the first user say what is now so.
- What changes here once the login is started again: ten wrong passwords for a name at this machine, or thirty in
  all, make the next sign-ins with a password wait up to 15 minutes; a domain's login without an email server takes its
  first user from `liminal-login user add NAME`, not from the page; a name typed with an address after its @
  (name@http://...) is refused; and a request that carries X-Forwarded-For or X-Forwarded-Proto is no longer at the
  machine (liminal-libs 1.98.0: a browser behind something that adds them loses the secret user's way in).

Reviewed before landing: three lenses (security, what it breaks, whether the tests can fail), each finding put to a
second check. Eighteen held, thirteen of them distinct. Through the recipe's own front none reopened a way in without a
password; one, the library's, was about a front set up without the mark (liminal-libs 1.98.0's net under it). The
throttle's numbers and where they apply are as built. Put right here:
- The limits hold for sign-ins sent together. A failed sign-in was counted only once its key had been derived, so the
  sign-ins of a burst each found nothing counted yet and every one was tried: 200 passwords for one name where 10
  were meant, and again every 15 minutes. A try is now counted before its key is derived, in the same hold of the lock
  that asks whether it must wait, and taken back unless the name or the password was wrong (`Throttle.tried`,
  `forget`). Made one after another, sign-ins are answered as before.
- The keys derived at once are bounded (`Throttle.deriving`, `AT_ONCE`): four from a front and four from this
  machine, the others waiting their turn, so a burst cannot take the machine's memory (32 MB a key) and, with the
  process, the counts. The secret user's way in asks for no turn.
- A user of another login is counted once, however their domain is typed. `ada@remote.test.` and ` ada @ remote.test`
  were names of their own to count, as often as wanted, though their login is asked for the same user.
- A host typed in a name is a domain, never an address (`LoginApp.remote_url`). `name@http://127.0.0.1:8795`, typed
  through a front, had the login ask itself over http as a program at its own machine: the try was counted as the
  machine's own, so whoever reached the front had the machine's tries beside the front's and could make every sign-in
  with a password at the machine wait. An address is taken from `[remotes]` alone; typed with a scheme it is answered
  400, and nothing is asked or counted.
- The page's Sign in form goes on to the way in without a password after a 429 as after a 401 (login.js). It stopped
  there, so the secret user and `default`, typed with anything in the password box, were told to wait once their
  name's ten or the machine's thirty had failed, though the login would let them in at once.
- A liminal-libs older than the one it needs is said in words (`LIBS_FLOOR`, 503 from every route). The floor is
  pip's to check, and an editable install made without its dependencies runs whatever its checkouts hold: every
  sign-in answered 500 with the reason in the log alone. The library is to be landed, pulled and pushed before this.
- The README gives nginx its lines in full. Its one line set the mark alone, and nginx writes no X-Forwarded-For or
  X-Forwarded-Proto of its own and hands a client's on: the counts then went by an address the client wrote, and the
  cookie was not Secure.
- Three tests that could not fail: a second published port beside the first is now seen (the whole list under
  `ports:` read as text; the PyYAML half runs nowhere PyYAML is not installed, which is here and in CI); the frame's
  refusals behind the front are asked of a route that answers a front's own page; and `serve` itself is run with the
  scope said, not rebuilt by hand.

Its last check (2026-11-25) found one more, rated medium, closed here before landing (the user, the same day: "Closed
unless turned on", and wrong codes to count toward the sign-in throttle). Made a domain's so that it has no user
without a password, the container took sign-ups by a mailed code as soon as its host had a mail record (MX), with
nothing else set: a domain's login with no `[mail]` sends direct, and its sign-up routes had no mark, gate or count.
The six-digit code could be guessed, five tries with each code and a new code at once after the fifth: an account
with no session and no mailbox.
- Sign-up by email has a switch, `signup = open` or `signup = closed` under the file's `[login]`, and the recipe ships
  closed: docker/liminal-login.cfg says `signup = closed`, and compose.yaml says `LIMINAL_LOGIN_SIGNUP: "closed"` for a
  copy of that file from before the line. Closed, the status and every step of a sign-up (`/api/signup`, `resend`,
  `verify`, `complete`: 503) say how it is opened, through the front and at the machine, whatever mail record the host
  has, and no mail record is asked for. A deployer opens it with `signup = open` in the file, which is over
  compose.yaml's word; the README's Docker steps say how, and what it means. The variable only closes, whatever it
  says, and is the command line's alone, as LIMINAL_LOGIN_SCOPE is: `serve` reads it (`cli.signup_told`) and hands it
  to the login it makes (`LoginApp(signup=...)`), and a login made in code never reads it. A word in the file that is
  neither closes, and the page says so; `serve`'s first line says closed too.
- What a login with no such line does: as it did, a domain's taking sign-ups when it has an email server (the user,
  2026-11-06), unless its command line was told closed. Why not closed everywhere: a domain's login set up by hand
  (`init`, `mail setup`) was tied to its mail server so that its users sign up, and `init` says so as it writes the
  file; closed at an update, it would stop taking the sign-ups its owner asked for, and the answer of 2026-11-25 is
  about the recipe. The container gets its default from compose.yaml, so an older file there is closed too. The
  other reading, every domain's login closed until its file says open, is put to you below.
- The logins on this machine are local: no sign-up by email before or after, and they read neither the line nor the
  variable. Their page and their ways in are as they were. Of a sign-up's routes, which only ever refuse there,
  `resend` and `verify` answer 429 like a sign-in where the caller is already held back for failed sign-ins.
- `mail setup` keeps the line. It writes the file back through the library's Scope, which knows no such line, so a
  `closed` its owner wrote would have gone with the next `mail setup`, and the login taken sign-ups again.
- A sign-up's wrong codes count in the throttle, in the counts of the wrong passwords and with their numbers: by the
  address they came from (the machine's own apart from a front's) and by the email the code was mailed to. Past
  either, a code typed is answered 429 with Retry-After before it is looked at; it is counted before it is compared
  and taken back unless it was wrong. While an email or an address waits no new code is sent for it either
  (`/api/signup`, `/api/signup/resend`: 429, nothing mailed), so a new code gives no tries back.
- A code whose five tries are spent keeps its sign-up (users.py: `WrongCode`, `_refuse_again`). The sign-up was
  dropped at the fifth wrong code and the next begun at once: five more tries, and a second message inside the
  minute. Now the code is compared no more, the right one neither, and the next goes out no sooner than a minute
  after that last try, however late it came (the row's `sent_at` is moved there, and the row lives that minute at the
  least; no column is added). A sign-up already verified is no longer wiped by wrong codes sent after it. The page
  keeps the sign-up, and its "Send it again" works once the minute is over (what is said no longer holds the words on
  which the page let the sign-up go).
- The secret user and `default` are as they were: their way in asks nothing of this.

Said, and left as they are, each put to you (the first three are the throttle's, which stays as built):
- More names and addresses failing within 15 minutes than there are counters (4096) make the oldest counts forgotten.
  With the limits holding for bursts that takes about 133 addresses kept up. Never dropping a live counter would make
  a flood hold back the sign-ins of everyone new instead.
- An account's email, typed in place of its name, is counted apart: 20 tries for an account that has one. Counted
  together, whoever spent a name's ten would learn which address is its account's, and its owner could no longer come
  in by the other.
- Where every client reaches the front from one address (the port published on 127.0.0.1, Docker Desktop, rootless
  Docker, an engine inside WSL reached from Windows, a tunnel on the host), the 30 from one address are everyone's
  together. The README's Docker steps and the comments in docker/ say so. Not seen in Docker: none is on this machine.
- `status`, `mail check`, `server` and `mail dkim`'s folder read LIMINAL_LOGIN_SCOPE as `serve` and `user` do. The
  answer of 2026-11-24 named `serve` and `user`: with the variable left set in a shell, `mail check` checks and mails
  the admin of the variable's domain. Inside the container `status` and `mail check` have to read it to speak of the
  login served.

Answered 2026-11-25: these four stay as they are, and every command of `liminal-login` reads LIMINAL_LOGIN_SCOPE while
no login an app holds does. From the last check's fix, put to you the same way:
- Whether every domain's login should be closed until its file says `signup = open`, not the container's alone. As
  built, one made by hand with no `signup` line takes sign-ups when its domain has an email server, as it did, and its
  owner closes it with `signup = closed`.
- With sign-up open, wrong codes are a second way to an address's thirty: where every client reaches the front from
  one address, thirty of them make every sign-in with a password through it wait, as thirty wrong passwords do. That
  is the one count asked for; counted apart, an address would have thirty wrong codes beside its thirty wrong
  passwords.
- The library's Scope keeps no `signup` line (of the library, only the headers its fronts pass back were to change
  for this): the login reads the file itself, `init` writes no such line, and `status` does not say whether sign-up is
  open (the page, `/api/status` and `serve`'s first line do).

Tests: tests/test_docker_files.py (3 tests became 14: the files as text, the front's requests and this machine's
against the app, the container's login as `serve` makes it with its first user from `user add`, the scope said to the
command line and never read by a login made in code or held by an app; the recipe as shipped taking no sign-up by
email on a host with a mail record, the file's line opening it, a copy of the file from before the line closed by
compose.yaml's word, each on the login `serve` itself makes), tests/test_throttle.py (11: the counts, a try counted
and taken back, sign-ins sent together and the keys derived at once by their order, another login's user, a host
typed as an address; wrong codes by the address and by the email, a new code giving no tries back, codes typed
together by their order), tests/test_signup.py (the switch's words, and a spent code keeping its sign-up),
tests/test_cli.py (`mail setup` keeping the line) and, in tests/test_app.py, the page's line after a 429 and a
library older than the floor. No message is sent and no name looked up: the mailer and the mail record are stand-ins.

## 0.19.0 (2026-11-25)

Where the users are as a preference, and a local fallback (the user, 2026-11-25: "sqlite for now, but the user
preferences should allow for selecting which kind of database, and it's location (URL) file:// too"; "if the
preference is not locatable, allow for a local fallback, but the location is selectable, ~/app/.data (perhaps)"; with
plugin-login-datastore 0.2.0):
- A plugin's place may be a kind and a location (`pointer`: `kind`, `url`) and may be its fallback folder
  (`pointer.fallback`, with a `note` of why): the note is said in the log before where the users are read from, and the
  status's `place` says `fallback` and the note. The status's pointer leaves out the location (`url`): no file is named
  to someone not signed in.
- A place whose users file cannot be opened at a start (its folder cannot be made, the file is not a database) leaves
  the login on its own folder, said in the log, the status and on the plugin's page, where it stopped the start before.
- A place a plugin refuses at a start is said by what it kept without its location: 0.18.0's engine:instance, or
  "a preferred <kind> location" (the datastore's of a kind it no longer keeps: its own folder, no fallback).
- A plugin's pick may have options shown but not to be picked (`disabled`: the kinds not supported yet).
- A preferred location kept by a plugin that is not installed here (the datastore's `store`) leaves the login on its
  own folder, said, as 0.18.0's `pointer` did.
- A plugin's tab may hold forms (`forms`: a title, a note, its fields, text or a pick, its button and its question):
  asked on the page as a row's change is, the form's question then the login's own second one, each answered under the
  form. The datastore's preferred location and fallback folder are two.

## 0.18.0 (2026-11-25)

The login's plugins, and the first of them, the datastore (Monday list item 12; item 30, step 8; the user, 2026-11-15:
"also create a plugin for the login app that is used to connect to or examine the datastore that has user credentials
and other keys related to the user"; liminal-libs 1.92.0's LoginPlugin):
- The login attaches its plugins (the registry's login plugins; those it is given, in a test) the first time they are
  asked for, never in its constructor, and lets them go when it stops. `GET /api/login-plugins` lists them with their
  tabs to anyone signed in; `GET /api/login-plugins/<name>/<tab>` is a tab's page and `POST` a change on it.
- A plugin sees a `Viewer` made for each request: the person's name, whether they are the login's admin, their own
  keystore (its file, how it is reached, its size, its pairs by name, kind, label and dates; never a value, never
  another user's), where the login keeps its users, and what the plugin keeps. A change on a tab only the admin may
  change is refused to anyone else (403) before the plugin is asked, and said in the log.
- What a plugin keeps (a change's `keep`) is kept in the login's own folder's users file (`settings`, `plugin:<name>`),
  never a file of the plugin's.
- Where the users are is read as the login starts: its own folder, unless a plugin places them elsewhere by what it
  keeps (`place`): the datastore's central database. The users file and the keystores are then read from there; the
  own folder's file still holds the login's own settings. A place that cannot be used at a start (the plugin not
  installed here, the instance gone or no longer a login's) leaves the login on its own folder, said in its log, its
  status (`place`) and on the plugin's page.
- The page lists each plugin under Your account, its tabs (the datastore's Mine and Global) followed by External API and
  Internal API, drawn by the library's apis.js and internal.js (`GET /api/app/apis?plugin=<name>`, the frame's). A
  change in a row is asked in the row, then the login's own second question, each answered there.
- `UserStore.setting_keys(prefix)`; `LoginApp.own_users` (its own folder's users file), `place`, `stores_dir`,
  `login_plugins()`, `kept_of`, `keep_for`, `viewer`. The command line's `user` and `status` still read the own
  folder's users file.

## 0.17.7 (2026-11-24)

Preferences and licences in each user's own store (Monday list item 21; the user, 2026-11-19: "preferences, keys,
licenses all get stored in the individual's login db"; liminal-libs 1.88.0):
- The vault takes two kinds more, `preference` (the UI's theme, the platform's plugins switched off) and `licence`
  (one accepted: what, its version and address, when and by whom), each a JSON value, sealed like every pair.
- `LoginApp.user_login(handler)`: the person at a browser as the library's Login (userlogin.py), for an app that
  holds this login (liminal-libs App.user_login) and for the login's own frame. One of its own users over their
  store (`SessionLogin`), a user of another login over theirs, with the session it gave (`RemoteSessionLogin`);
  neither reads a key as a preference (409), and a store closed under a request (signed out) is a refusal (401), so a
  reader falls back to the file as with nobody signed in. The session is looked at, never kept alive by it: a page's
  polls do not hold open a session its user left.
- So the login's own `GET /api/ui`, and that of an app holding it, answer each browser with its own user's theme,
  and a second user signed in sees their own.

## 0.17.6 (2026-11-24)

Codebase on the login's page (Monday list item 15: "Codebase in the login's, the integrator's and the charts' pages
(the platform has it)"; the user, 2026-11-16: "this class will be added to all the 'apps' just like connections"):
- Signed in on its own, the page is laid out as every app's: its list on the left (Your account, Codebase), the one
  picked in the middle, its specifics on the right, then the rail. Your account is as it was, your store's facts now
  beside it; Codebase is the library's object every App holds (its repositories, how far each is behind its remote,
  each language's share), drawn by the library's own codebase.js as the platform draws it, asked by relative paths.
  Held in another app's page, for a user of another login, on a domain's login or with a library from before 1.59.0,
  the page is one column as before.
- `GET /api/codebase` and `POST /api/codebase/fetch` (the library's routes) answer only one of this login's own users
  signed in to a local login. They answered anyone who reached the login before, signed in or not; a domain's login,
  whose users are anyone who signs up by email, now refuses them.

## 0.17.5 (2026-11-24)

The review of 2026-11-21 (Monday list item 26), five P3s:
- A sign-up is no longer begun again at anyone's word. A start replaced the sign-up under way at once, with no time
  check, so the limit on new codes was nothing and a sign-up already verified (its name and password being chosen)
  could be wiped. A second start for an address within a minute is now refused without a message sent, and a verified
  sign-up is never replaced, by a start or a new code, until it has expired; its proof still completes it.
- A remote user's session ended here is signed out at their own login too. Only a sign-out on the page did that, so
  a session that idled out here, or was left when the login stopped, stayed signed in there. Now each is signed out
  there as well, best effort, on a thread of its own (no request waits for another login; a stop waits two seconds).
- A password changed ends the user's other sessions, their stores closed; the session that changed it stays.
- A name like `a@[` is a 400 with the reason, not a 500.
- `liminal-login mail setup` off Windows says why it cannot keep the account (no secret store, no user variables) and
  ends with 1, instead of a traceback after the settings were written; the password is kept first, so nothing else is
  written when it cannot be.

## 0.17.4 (2026-11-24)

The review of 2026-11-21 (Monday list item 26), two P2s:
- The secret user and `default` are no longer locked out for good when their first sign-in is cut short. The user's
  row was committed, then its password kept in the login's database with commits of its own, so a failure between
  them left a user whose password nobody had, refused at every sign-in without one; a secret user moving off 0.14.0's
  password had its pairs sealed under one nobody kept. The row (or the move) and its password are now written in one
  transaction, undone together on any failure, and the next sign-in makes the user as the first time would.
- Sessions left without a sign-out are closed. One idle too long was ended only when its own token came back, so its
  store stayed open and its key in memory until the process stopped, and every sign-in added one. Each sign-in and
  each request that looks at a session now ends every session idle too long (a remote user's too), closing its store.

## 0.17.3 (2026-11-24)

The review of 2026-11-21 (Monday list item 26), a P1: a user here whose name held an @ (ann@gmail.com, with no email set) had the password typed at every sign-in
posted to that host (https://gmail.com/api/sign-in), taken for a user of another login, and could never sign in here.
A user's name now has no @ (the address goes in the email). A user named so before is still this login's: one whose
name or email matches is never asked of another login, and is looked up by name when no email matches.

## 0.17.2 (2026-11-24)

The review of 2026-11-21 on your desktop (Monday list item 26), checked against the checkout:
- A password is kept exactly as given. Every value was trimmed before it was sealed, so a password beginning or
  ending with a space came back as another one. Keys, accounts' names and details are still trimmed (a key
  pasted with a space after it). A value of nothing but spaces is refused.
- Signing out no longer closes a store under a request using it. A request takes its session and then uses its
  store after the sessions' lock is let go, and a read decrypted with the key outside the store's lock, so a
  sign-out on another thread could close the connection or clear the key under it. Every use of the store now
  holds its lock from the query to the decryption, a close waits for it, and what asks after the close is
  answered 401 "signed out while this was being asked: sign in again" (`VaultClosed`).

## 0.17.1 (2026-11-15)

Two suites on one machine no longer sign each other out (the user: "i need to run the same suite in a WSL container";
the suite inside WSL answers at 127.0.0.1 like Windows', on ports of its own). A cookie belongs to a host, whatever the
port: both logins kept their session under `liminal_login`, so signing in to one replaced the other's, and that one
found a session it did not know and showed its sign-in again. A login set to answer anywhere but at its usual port now
carries that port in its cookie's name: `liminal_login_9795` on its own, `liminal_login_platform_9775` held by an app
whose port is set so. At the usual ports nothing changes, and nobody is signed out by this. `serve --port N` sets the
port for the whole run (its address, its cookie: `LoginApp(port=N)`), as LIMINAL_LOGIN_PORT does.

## 0.17.0 (2026-11-15)

A second user comes in without a password, `default` (the user: "create a second 'default' user with no login, to test
multiple logins and see if the code holds"). Its name typed and the icon clicked sign it in, as the secret user's do. It
is made the first time, its random password kept in the login's database (`settings`, `passwordless:default`), and that
password is never changed, like the secret user's. A user named `default` who has a password of their own is never let
in this way, and a domain's login has no such user. It is an ordinary user. Any other name kept under `passwordless:`
comes in the same way (`UserStore.make_passwordless`); only `default` is made by asking for it.

The secret user is the login's admin (the user: "let the secret user be the admin, and allow secret to alter the global
page/tab of the plugin and where it points to to get user/keystore data"). `/api/me`, `/api/status` and every sign-in's
answer say `admin`: true for this login's secret user alone, however it came in (by its name, or with the key itself);
never for `default`, and never for a user of another login, whatever they are at their own. `LoginApp.is_admin(session)`
is what a route asks. Nothing is restricted by it yet: the datastore plugin's Global tab is its first use. The page
says "this login's admin" under the name.

The tests sign both users in at once (tests/test_two_users.py): each session is its own user with its own store, a pair
of the same name holds a value each, one signing out leaves the other in, many sign-ins at the same moment make each
user once and cross no session, and the same holds under an app that holds the login as an object.

## 0.16.1 (2026-11-15)

The secret user's password is never changed (the user: "secret should not be able to change it's own password under
login"; on 2026-11-10 it was to exist "but cannot be modified"). 0.15.1 had the page offer a new password in place of the
key the login keeps. Now `PUT /api/me/password` answers 403 for the secret user, whether it came in by its name or with the
key itself, and for a remote login's secret user too, refused here without asking that login. The page draws a line saying
so where the password form would be. Anyone else changes theirs as before, typing the current one.

## 0.16.0 (2026-11-14)

An app that inherits the login holds it as an object of its own (the user: "the platform and integrator inherit the
login function, they are separate login instances, class vs object"; "login doesn't point to anything except the app
that inherited it"; liminal-libs 1.52.0 `App.login_object`). `LoginApp(superclass=<the app>)` takes the app object
itself: its name and title as before (its users' folder and cookie), the pairs its plugins ask for asked of that app
directly (`Superclass.app`), no address, no port of its own (`port()` and `url()` are the app's, under /login/).
Nothing starts a login for an app any more and no login listens beside it (the user: "i only want ports for
liminal-login ; liminal-platform ; liminal-charts ; liminal-integrator"; "don't start any of the applications in the
background"). A login run on its own (`liminal-login serve`, 8795) points to nothing; `--for`/LIMINAL_LOGIN_FOR still
names a superclass at an address for one run that way.

## 0.15.4 (2026-11-11)

On the sign-in with a password the icon is the way in too (the user: "if i type in secret w. password i can't click on
the icon"). The lambda was a button only on the page before it (the user's name, then the icon); on the sign-in with a
password it was a picture, so the secret user's name typed there and the icon clicked did nothing, and Sign in refused
an empty password. Now the icon there is the same button, and Sign in and Enter go the same way: a password typed is
tried as that user's; with none typed, or when it is refused, the name is asked the secret user's way in (it has no
password to type, so whatever is in the box does not keep it out); anyone else with no password typed is told theirs is
needed. Which name is the secret user's is still the login's to say, and a domain's login still has none. The page
alone changed: a login already running serves it at its next reload.

A login that does not answer at all says so (the user, of a page whose login had been stopped: "getting a failed to
fetch"): "The login is not answering at HOST: it may have stopped. Start it again (or the app that holds it), then
reload this page", where the page showed the browser's own words.

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
