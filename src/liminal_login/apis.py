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
and docker plugins have them (2026-11-11), git's as the platform's apis.py has it (2026-11-17). Not yet a card, for
want of a maker's page read for it: the mail account's SMTP submission and the mailbox read over IMAP (the library's
mail.py and mailbox.py), the cryptography package's AES-GCM and Python's scrypt (crypto.py), DKIM, Caddy (docker/'s
front) and Windows' Credential Manager (`mail setup`). The login never fetches any of these pages. This is the one .py
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

APIS = (SQLITE, NSLOOKUP, DOCKER, GIT)
