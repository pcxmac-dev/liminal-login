"""What the login's own code associates with, for its own External API (0.20.1, Monday list item 17; liminal-libs
1.63.0's App.apis; the user, 2026-11-16: "the external should be all the SDKs/APIs the plugin associates with"; "for
all apps, and all plugins").

What the login's own code calls that Liminal does not make, and nothing of its plugins' (each says its own on its
page): its users and their vaults in SQLite files, through Python's sqlite3 (users.py, vault.py); a domain's mail
record, asked of this machine's resolver with nslookup (app.py, mailcheck.py); the mail server container its file
declares, through the docker command (cli.py `server`); and git, which the Codebase every app holds reads the
workspace with. Another domain's login is Liminal's own (a login like this one, over https): it is in its Internal
API, not a card here. Imported only when the login's own External API is asked (LoginApp.apis), so a login an app
holds loads nothing more for it.

Every address is one already read on a maker's own page for a card that landed before this one, with that card's day:
SQLite's and Python's sqlite3 as the database plugins have them (2026-11-16), nslookup's and Docker's as the hw-stats
and docker plugins have them (2026-11-11), git's as the platform's apis.py has it (2026-11-17). The rest were read on their makers' pages
on 2026-11-26 (the user's yes, "Yes, read them"): the mail account's SMTP submission and the mailbox read over IMAP
(the library's mail.py and mailbox.py), the cryptography package's AES-GCM and Python's scrypt (crypto.py), DKIM
(`mail dkim`), Caddy (docker/'s front) and Windows' Credential Manager (`mail setup`). The login never fetches any of
these pages. This is the one .py
of the login that names an outside host (the user, 2026-10-31: the app's code names no provider's host, links for
people excepted): tests/test_api_views.py holds every other to that."""
from __future__ import annotations

from liminal_libs.apis import Api, Area, Call, Link

_SQLITE = "https://www.sqlite.org/"
_SQLITE3 = "https://docs.python.org/3/library/sqlite3.html"
_COMMANDS = "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/"
_BIND = "https://bind9.readthedocs.io/en/latest/manpages.html"
_DOCKER = "https://docs.docker.com/reference/cli/docker/"
_GIT = "https://git-scm.com/docs/"

SQLITE = Api(
    name="SQLite, through Python's sqlite3", maker="The SQLite project; the Python Software Foundation", kind="sdk",
    about=("Where the login keeps its users and their pairs: users.db in its folder (each user's name, salt, verifier "
           "and wrapped vault key, the sign-ups under way, the login's own settings), and one SQLite file for each "
           "user's vault (users/), every value sealed under that user's vault key before it is written. A plugin "
           "may point it at another users file as it starts (place); it is opened the same way."),
    base="users.db and users/<name>.db in the login's folder (store/data/login by default), or the place a plugin gives",
    version="the SQLite library Python is built with (sqlite3.sqlite_version)",
    auth="none: the files' permissions; the values sealed (crypto.py), so a file gives nothing without its key",
    limits="one connection to each file, shared by the login's threads under a lock",
    costs="free (SQLite is in the public domain; Python's sqlite3 module comes with Python)",
    links=(
        Link("SQLite Documentation", _SQLITE + "docs.html", "docs"),
        Link("Python's sqlite3 module (DB-API 2.0 interface for SQLite databases)", _SQLITE3, "reference"),
        Link("Database File Format", _SQLITE + "fileformat2.html", "spec"),
        Link("Release History Of SQLite", _SQLITE + "changes.html", "changelog"),
        Link("SQLite Copyright (public domain)", _SQLITE + "copyright.html", "terms"),
    ),
    areas=(
        Area("Python's sqlite3 module", "the standard library's interface to SQLite", _SQLITE3,
             covered="the users file and each user's vault: made, read and written"),
        Area("Pragmas", "the statements that read and set a database's own settings", _SQLITE + "pragma.html",
             covered="a table's columns read, so a file from an older login gains the ones it lacks"),
    ),
    calls=(
        Call("sqlite3.connect(path, check_same_thread=False)", "a connection to a file, shared by the login's threads",
             "Python's sqlite3 module", used="the users file, each user's vault while they are signed in",
             docs=_SQLITE3),
        Call("executescript(SCHEMA)", "the tables made where they are not there yet", "Python's sqlite3 module",
             used="users, signups and settings in users.db; pairs in a vault", docs=_SQLITE3, writes=True),
        Call("PRAGMA table_info(<table>)", "a table's columns", "Pragmas",
             used="an older users file given the columns it lacks", docs=_SQLITE + "pragma.html"),
        Call("SELECT, INSERT, UPDATE and DELETE on users, signups, settings and pairs", "the rows themselves",
             "Python's sqlite3 module", used="sign-ins, sign-ups, a password changed, a pair kept or removed",
             docs=_SQLITE3, writes=True),
    ),
    verified="2026-11-16")

NSLOOKUP = Api(
    name="nslookup (the domain's mail record)",
    maker="Microsoft (Windows' command); BIND on Linux", kind="command",
    about=("A domain's login asks this machine's resolver for its domain's mail exchangers (MX) before it takes a "
           "sign-up by email, a few minutes apart at the most; `liminal-login mail check` asks for the mail host's "
           "addresses, its mail record and its SPF record too. Run windowless through the library's dns.py; nothing "
           "is cached there. A local login asks nothing."),
    base="nslookup -type=<type> <name>, of the machine's own resolver",
    version="Windows' own command; BIND's nslookup on Linux",
    auth="none: an ordinary command, no rights needed",
    limits="15 s for each answer",
    costs="",
    links=(
        Link("nslookup (Windows)", _COMMANDS + "nslookup", "reference"),
        Link("BIND's manual pages (nslookup)", _BIND, "docs"),
    ),
    areas=(
        Area("Asking the resolver", "a record of a name, asked of the machine's resolver", _COMMANDS + "nslookup",
             covered="the domain's mail exchangers; for the mail check, the host's addresses and its SPF record"),
    ),
    calls=(
        Call("nslookup -type=mx <domain>", "the domain's mail exchangers", "Asking the resolver",
             used="a domain's login, before a sign-up by email: whether its domain has an email server",
             docs=_COMMANDS + "nslookup"),
        Call("nslookup -type=a <host>, -type=txt <host>", "a host's addresses, its text records (SPF)",
             "Asking the resolver", used="`liminal-login mail check`", docs=_COMMANDS + "nslookup"),
    ),
    verified="2026-11-11")

DOCKER = Api(
    name="Docker (the mail server container)", maker="Docker, Inc.", kind="command",
    about=("`liminal-login server` runs the mail server container the login's file declares under [server] (its "
           "image, host name and ports) on this machine's Docker or the context the file names: up makes or starts "
           "it, down stops it with its data kept, status, logs, pull and exec say and do what they name. Through the "
           "library's docker.py, windowless; nothing runs it but that command, at the user's word."),
    base="the docker command, on this machine's engine or the [server] context's",
    version="the engine that answers (docker version)",
    auth="the engine's own: the docker group on Linux, Docker Desktop's on Windows",
    limits="600 s for a pull or a run, 30 s for the version",
    costs="free for the engine; Docker Desktop's license as its makers say",
    links=(
        Link("Docker Engine documentation", "https://docs.docker.com/engine/", "docs"),
        Link("docker CLI reference", _DOCKER, "reference"),
        Link("Docker contexts", "https://docs.docker.com/engine/manage-resources/contexts/", "guide"),
        Link("Docker Desktop license agreement", "https://docs.docker.com/subscription-billing/desktop-license/",
             "pricing"),
        Link("Docker Engine release notes", "https://docs.docker.com/engine/release-notes/", "changelog"),
        Link("docker/cli", "https://github.com/docker/cli", "source"),
    ),
    areas=(
        Area("Containers", "a container made, started, stopped, read and run in", _DOCKER,
             covered="the mail server container: up, down, status, logs, exec"),
        Area("Images", "an image fetched from its registry", _DOCKER, covered="`server pull`"),
        Area("Contexts", "which engine the command speaks to", "https://docs.docker.com/engine/manage-resources/contexts/",
             covered="the context the login's file names under [server], else this machine's"),
    ),
    calls=(
        Call("docker version --format {{json .}}", "the engine that answers", "Containers",
             used="`server status`, and before `server up`", docs=_DOCKER),
        Call("docker ps -a --no-trunc --format {{json .}}", "the containers there", "Containers",
             used="`server status`, `server up`", docs=_DOCKER),
        Call("docker inspect --format {{json .}} <name>", "one container's state and health", "Containers",
             used="`server status`", docs=_DOCKER),
        Call("docker run -d --name <name> ...", "the container made and started", "Containers",
             used="`server up`, when it is not made yet", docs=_DOCKER, writes=True),
        Call("docker start <name>; docker stop -t <s> <name>", "the container started again; stopped, its data kept",
             "Containers", used="`server up`, `server down`", docs=_DOCKER, writes=True),
        Call("docker logs --tail <n> <name>", "its last lines", "Containers", used="`server logs`", docs=_DOCKER),
        Call("docker exec <name> <command>", "a command run inside it", "Containers", used="`server exec -- CMD`",
             docs=_DOCKER, writes=True),
        Call("docker pull <image>", "its image fetched", "Images", used="`server pull`", docs=_DOCKER, writes=True),
    ),
    verified="2026-11-11")

GIT = Api(
    name="git", maker="The Git project", kind="command",
    about=("The version control command the login's Codebase reads the workspace's git working copies with (the "
           "frame's Codebase, the page's Codebase view; GET /api/codebase, for one of its own users signed in to a "
           "local login): each one's branch, the commit checked out, its remote, what is changed and not committed, "
           "how far ahead and behind its upstream as of its last fetch, and its tracked files, counted by language. "
           "git is told to take no lock and to ask nothing at a terminal; no remote is asked but on the user's Fetch."),
    base="git, in each working copy of the workspace",
    version="git status's porcelain v2",
    auth="none of its own: a remote's credentials are git's and the user's (asked at no terminal: a fetch that needs "
         "them fails in words)",
    limits="20 s for each command, 90 s for a fetch; read at most once in 10 minutes unless asked fresh",
    costs="free (GPL 2)",
    links=(
        Link("Git reference", _GIT, "reference"),
        Link("git status", _GIT + "git-status", "reference"),
        Link("git log", _GIT + "git-log", "reference"),
        Link("git config", _GIT + "git-config", "reference"),
        Link("git ls-files", _GIT + "git-ls-files", "reference"),
        Link("git fetch", _GIT + "git-fetch", "reference"),
        Link("Install Git", "https://git-scm.com/install/", "tool"),
        Link("git/git", "https://github.com/git/git", "source"),
    ),
    areas=(
        Area("The working copy", "status: the branch, its upstream, ahead and behind, what is changed",
             _GIT + "git-status", covered="each repository's branch, changes and distance from its upstream"),
        Area("History", "log: the commits", _GIT + "git-log", covered="the commit checked out: its hash, date and subject"),
        Area("Configuration", "config: the repository's settings", _GIT + "git-config",
             covered="its remote's address (shown with no name or token in it)"),
        Area("The index", "ls-files: the files git tracks", _GIT + "git-ls-files", covered="the code counted"),
        Area("Remotes", "fetch: what a remote has", _GIT + "git-fetch",
             covered="Fetch, on the user's click: the remote-tracking branches move, nothing checked out does"),
    ),
    calls=(
        Call("git status --porcelain=v2 --branch", "the working copy's state and its branch's headers",
             "The working copy", used="Codebase: the branch, ahead and behind, the changes", docs=_GIT + "git-status"),
        Call("git log -1 --format=%h%x1f%cI%x1f%s", "the last commit: its short hash, its date, its subject", "History",
             used="Codebase: the commit checked out", docs=_GIT + "git-log"),
        Call("git config --get remote.NAME.url", "the address of the remote its branch follows", "Configuration",
             used="Codebase: its remote", docs=_GIT + "git-config"),
        Call("git ls-files -z", "the files git tracks, each ended by a NUL", "The index",
             used="Codebase: the files counted by language", docs=_GIT + "git-ls-files"),
        Call("git fetch --quiet", "what the remote has (its remote-tracking branches move)", "Remotes",
             used="Fetch, on the user's click (POST /api/codebase/fetch)", docs=_GIT + "git-fetch", writes=True),
    ),
    verified="2026-11-17")

_SMTPLIB = "https://docs.python.org/3/library/smtplib.html"
_IMAPLIB = "https://docs.python.org/3/library/imaplib.html"
_HASHLIB = "https://docs.python.org/3/library/hashlib.html"
_AEAD = "https://cryptography.io/en/latest/hazmat/primitives/aead/"
_AESGCM = _AEAD + "#cryptography.hazmat.primitives.ciphers.aead.AESGCM"
_RSA = "https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/"
_RFC = "https://www.rfc-editor.org/rfc/"
_CADDY = "https://caddyserver.com/docs/"
_WINCRED = "https://learn.microsoft.com/en-us/windows/win32/api/wincred/"

# The six below were read on their makers' pages on 2026-11-26 (the user's yes, "Yes, read them")

SMTP = Api(
    name="SMTP submission, through Python's smtplib", maker="The IETF (RFC 6409); the Python Software Foundation",
    kind="sdk",
    about=("The mail account of yours the login sends from (the library's mail.py, the LIMINAL_SMTP_* variables, "
           "set by you alone): a domain's login sends a sign-up's six-digit code through it, and `liminal-login mail "
           "test` and `mail check` send a test message. Submission over STARTTLS (port 587) by default, or TLS from "
           "the start (465), or none for a bridge on this machine only; signed for your domain when a DKIM key is "
           "kept (the DKIM card). A local login sends no email."),
    base="your mail account's submission server (LIMINAL_SMTP_HOST, LIMINAL_SMTP_PORT)",
    version="ESMTP with STARTTLS (RFC 6409's submission); smtplib of Python 3.12 to 3.15",
    auth="your account's user and password (Gmail: an app password; Proton: an SMTP token), from the environment or "
         "Windows' Credential Manager, never a file",
    limits="30 s for each connection; your mail provider's own sending limits",
    costs="your mail provider's (free for an account you already have)",
    links=(
        Link("smtplib: SMTP protocol client", _SMTPLIB, "reference"),
        Link("RFC 6409: Message Submission for Mail", _RFC + "rfc6409.html", "spec"),
    ),
    areas=(
        Area("Connecting", "a connection to the server, in the clear then STARTTLS, or TLS from the start",
             _SMTPLIB + "#smtplib.SMTP", covered="the account's server, its certificate checked"),
        Area("Sending", "the account signed in to, a message handed over", _SMTPLIB + "#smtplib.SMTP.send_message",
             covered="one message at a time: a sign-up's code, a test message"),
    ),
    calls=(
        Call("smtplib.SMTP(host, port, timeout=30); starttls(context=...)", "a connection, upgraded to TLS",
             "Connecting", used="security starttls (the default)", docs=_SMTPLIB + "#smtplib.SMTP.starttls"),
        Call("smtplib.SMTP_SSL(host, port, timeout=30, context=...)", "a connection in TLS from its start",
             "Connecting", used="security ssl", docs=_SMTPLIB + "#smtplib.SMTP_SSL"),
        Call("SMTP.login(user, password)", "the account signed in to", "Sending",
             used="before each message", docs=_SMTPLIB + "#smtplib.SMTP.login"),
        Call("SMTP.send_message(msg)", "the message handed to the server", "Sending",
             used="a sign-up's code (a domain's login); `mail test`, `mail check`",
             docs=_SMTPLIB + "#smtplib.SMTP.send_message", writes=True),
    ),
    verified="2026-11-26")

IMAP = Api(
    name="IMAP, through Python's imaplib", maker="The Python Software Foundation", kind="sdk",
    about=("The admin mailbox `liminal-login mail check` reads (the library's mailbox.py), to see the login's own "
           "test message arrive: the inbox opened read-only and searched by the message's subject, nothing moved, "
           "marked or deleted. Asked only by that command, at your word."),
    base="the mailbox host and port kept for the checks ([imap] in the login's file; 993 by default)",
    version="IMAP4rev1; imaplib of Python 3.12 to 3.15",
    auth="the mailbox's user and password (LIMINAL_IMAP_PASSWORD, or the sending one), from the environment or "
         "Windows' Credential Manager",
    limits="30 s for each connection; a look every 5 s until the check's wait (60 s by default) is over",
    costs="your mail provider's (free for an account you already have)",
    links=(
        Link("imaplib: IMAP4 protocol client", _IMAPLIB, "reference"),
    ),
    areas=(
        Area("Connecting", "a connection in TLS from its start, or upgraded with STARTTLS",
             _IMAPLIB + "#imaplib.IMAP4_SSL", covered="the admin mailbox, its certificate checked"),
        Area("Reading", "a mailbox selected and searched", _IMAPLIB + "#imaplib.IMAP4.search",
             covered="the test message looked for by its subject, read-only"),
    ),
    calls=(
        Call("imaplib.IMAP4_SSL(host, port, timeout=30, ssl_context=...)", "a connection in TLS", "Connecting",
             used="`mail check`, security ssl (the default)", docs=_IMAPLIB + "#imaplib.IMAP4_SSL"),
        Call("IMAP4.login(user, password)", "the mailbox signed in to", "Connecting", used="`mail check`",
             docs=_IMAPLIB + "#imaplib.IMAP4.login"),
        Call("IMAP4.select('INBOX', readonly=True)", "a folder opened, nothing in it changed", "Reading",
             used="`mail check`", docs=_IMAPLIB + "#imaplib.IMAP4.select"),
        Call("IMAP4.search(None, 'SUBJECT', text)", "the messages whose subject holds the text", "Reading",
             used="`mail check`: whether the test message arrived", docs=_IMAPLIB + "#imaplib.IMAP4.search"),
    ),
    verified="2026-11-26")

CRYPTO = Api(
    name="AES-GCM and scrypt (the cryptography package; Python's hashlib)",
    maker="The Python Cryptographic Authority; the Python Software Foundation", kind="sdk",
    about=("How a user's vault is sealed (crypto.py): the unlock key is scrypt of the password with the user's own "
           "salt (n 2^15, r 8, p 1: 32 MB and about a tenth of a second for each sign-in), and every value and the "
           "vault's key are sealed with AES-256-GCM under a fresh nonce, with associated data binding each to its "
           "place, so a file gives nothing without the key."),
    base="the cryptography package's AESGCM, and hashlib.scrypt, in the login's own process",
    version="cryptography 2.0 and later (AESGCM); Python 3.12 to 3.15 (hashlib.scrypt, from OpenSSL)",
    auth="none: the keys are the users' own, never written in the clear",
    limits="scrypt's memory capped at 256 MB (maxmem); sign-ins counted by the throttle (throttle.py)",
    costs="free (cryptography: Apache 2.0 or BSD; Python's hashlib comes with Python)",
    links=(
        Link("Authenticated encryption (AESGCM)", _AEAD, "reference"),
        Link("hashlib: secure hashes and message digests (scrypt)", _HASHLIB + "#hashlib.scrypt", "reference"),
    ),
    areas=(
        Area("Authenticated encryption", "AES-GCM: a value sealed and opened, its tag checked", _AESGCM,
             covered="every value of a vault, and the vault's key under the unlock key"),
        Area("Key derivation", "scrypt: a key from a password and a salt", _HASHLIB + "#hashlib.scrypt",
             covered="the unlock key, at each sign-in and password change"),
    ),
    calls=(
        Call("hashlib.scrypt(password, salt=..., n=2**15, r=8, p=1, dklen=32, maxmem=256 MB)", "the unlock key",
             "Key derivation", used="a sign-in, a sign-up, a password changed", docs=_HASHLIB + "#hashlib.scrypt"),
        Call("AESGCM(key).encrypt(nonce, data, associated_data)", "a value sealed", "Authenticated encryption",
             used="a pair kept, a vault key wrapped", docs=_AESGCM),
        Call("AESGCM(key).decrypt(nonce, data, associated_data)", "a value opened (InvalidTag when the key or the "
             "associated data is wrong)", "Authenticated encryption", used="a pair read, a vault opened at sign-in",
             docs=_AESGCM),
    ),
    verified="2026-11-26")

DKIM = Api(
    name="DKIM (the domain's signing key)", maker="The IETF (RFC 6376); the Python Cryptographic Authority",
    kind="sdk",
    about=("`liminal-login mail dkim init|check|show` (cli.py, through the library's dkim.py): a 2048-bit RSA key "
           "made for your domain and kept in the login folder (dkim/<domain>.<selector>.pem, in no repository), the "
           "TXT record to publish at <selector>._domainkey.<domain> printed, and whether it is published asked of "
           "this machine's resolver (the nslookup card). The login's messages from an address at that domain are "
           "then signed rsa-sha256, relaxed/relaxed."),
    base="the key file in the login folder; the record in your domain's DNS",
    version="DKIM signatures, RFC 6376 (rsa-sha256)",
    auth="none: the key file's permissions; the DNS record is published by you where your domain's records live",
    limits="none of its own",
    costs="free",
    links=(
        Link("RFC 6376: DomainKeys Identified Mail (DKIM) Signatures", _RFC + "rfc6376.html", "spec"),
        Link("RSA (the cryptography package)", _RSA, "reference"),
    ),
    areas=(
        Area("The key", "an RSA key made, its public half read", _RSA, covered="`mail dkim init`, `show`, `check`"),
        Area("Signing", "a message's headers and body hashed and signed", _RFC + "rfc6376.html",
             covered="each message from an address at your domain, once a key is kept"),
    ),
    calls=(
        Call("rsa.generate_private_key(public_exponent=65537, key_size=2048)", "a new signing key", "The key",
             used="`mail dkim init` (again with --new)", docs=_RSA, writes=True),
        Call("<selector>._domainkey.<domain> TXT, v=DKIM1; k=rsa; p=...", "the record that proves the key",
             "Signing", used="`mail dkim show` prints it, `mail dkim check` looks for it", docs=_RFC + "rfc6376.html"),
    ),
    verified="2026-11-26")

CADDY = Api(
    name="Caddy (the remote login's https front)", maker="The Caddy project", kind="file",
    about=("docker/Caddyfile, the front a remote login runs in Docker (docker/compose.yaml, caddy:2.10-alpine): "
           "https on 8443 with a certificate from Caddy's own authority (tls internal), each request handed to the "
           "login at 127.0.0.1:8795 with the app's own address as its Host, no Origin, and the front's mark "
           "(X-Liminal-Front) set over a client's. The login's code never calls Caddy: Caddy reads the file when you "
           "bring the front up."),
    base="docker/Caddyfile, read by Caddy in the front container",
    version="Caddy 2.10 (the image compose.yaml names)",
    auth="none of its own: the login's sign-in behind it",
    limits="none of its own; the login's throttle counts sign-ins by the address the front says (X-Forwarded-For)",
    costs="free (Apache 2.0)",
    links=(
        Link("Caddy Documentation", _CADDY, "docs"),
        Link("reverse_proxy (Caddyfile directive)", _CADDY + "caddyfile/directives/reverse_proxy", "reference"),
        Link("tls (Caddyfile directive)", _CADDY + "caddyfile/directives/tls", "reference"),
    ),
    areas=(
        Area("The reverse proxy", "requests handed to a backend, their headers set or removed",
             _CADDY + "caddyfile/directives/reverse_proxy", covered="the login behind it, Host and Origin rewritten"),
        Area("TLS", "the site's certificate", _CADDY + "caddyfile/directives/tls",
             covered="tls internal: Caddy's own, locally trusted authority"),
    ),
    calls=(
        Call("reverse_proxy 127.0.0.1:8795 { header_up ... }", "each request handed to the login",
             "The reverse proxy", used="the remote login's front", docs=_CADDY + "caddyfile/directives/reverse_proxy"),
        Call("tls internal", "a certificate from Caddy's internal authority", "TLS", used="the remote login's front",
             docs=_CADDY + "caddyfile/directives/tls"),
    ),
    verified="2026-11-26")

CREDENTIALS = Api(
    name="Windows' Credential Manager", maker="Microsoft", kind="system",
    about=("Where `liminal-login mail setup` keeps the mail account's password and the mailbox's (the library's "
           "secrets.py, through advapi32): generic credentials of this Windows user, kept on this computer, never a "
           "file and never the registry in the clear; read back when the variables do not hold them, removed when `mail setup` is "
           "left without a user. Off Windows the variables are the only place."),
    base="advapi32's credential functions, for this Windows user",
    version="Windows' own (wincred.h, Advapi32.dll)",
    auth="this Windows user's logon session: no rights beyond it",
    limits="a credential's secret at most 5*512 bytes (CRED_MAX_CREDENTIAL_BLOB_SIZE)",
    costs="free (part of Windows)",
    links=(
        Link("CredWriteW function (wincred.h)", _WINCRED + "nf-wincred-credwritew", "reference"),
        Link("CredReadW function (wincred.h)", _WINCRED + "nf-wincred-credreadw", "reference"),
        Link("CredDeleteW function (wincred.h)", _WINCRED + "nf-wincred-creddeletew", "reference"),
        Link("CREDENTIALW (wincred.h)", _WINCRED + "ns-wincred-credentialw", "reference"),
    ),
    areas=(
        Area("Generic credentials", "a secret kept for the user under a name", _WINCRED + "ns-wincred-credentialw",
             covered="the mail account's password, the mailbox's (CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE)"),
    ),
    calls=(
        Call("CredWriteW(credential, 0)", "a credential made or replaced", "Generic credentials",
             used="`mail setup`: the passwords kept", docs=_WINCRED + "nf-wincred-credwritew", writes=True),
        Call("CredReadW(target, CRED_TYPE_GENERIC, 0, &found); CredFree", "a credential read", "Generic credentials",
             used="sending or reading mail, when the variables hold no password", docs=_WINCRED + "nf-wincred-credreadw"),
        Call("CredDeleteW(target, CRED_TYPE_GENERIC, 0)", "a credential removed", "Generic credentials",
             used="`mail setup` left without a user", docs=_WINCRED + "nf-wincred-creddeletew", writes=True),
    ),
    verified="2026-11-26")

APIS = (SQLITE, NSLOOKUP, DOCKER, GIT, SMTP, IMAP, CRYPTO, DKIM, CADDY, CREDENTIALS)
