"""`liminal-login`: the login app's command line. Every command takes `--for charts|integrator`, the
app this login serves (LIMINAL_LOGIN_FOR; charts by default): its users live in that namespace's folder,
with their own cookie and default port (charts 8795, integrator 8796). `serve` keeps the page at its
port (LIMINAL_LOGIN_PORT) until Ctrl+C; `user add NAME [--email ADDRESS]` makes a user (the password
typed hidden, twice; never on the command line; no code: the machine's owner adding one); `user list`
names them; `status` says what is there; `mail test ADDRESS` sends a test message through the mail
account in your environment (LIMINAL_SMTP_*: liminal_libs.mail). The folder of the namespaces is
LIMINAL_LOGIN_DIR, else store/data/login (liminal_libs.layout)."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from liminal_libs import layout, secrets, web
from liminal_libs.docker import DockerError, command_line
from liminal_libs.mailbox import Mailbox
from liminal_libs.apps import FILE_NAME, Scope
from liminal_libs.config import save_user_variable
from liminal_libs.logs import Logger
from liminal_libs.mail import FROM_VAR, HOST_VAR, PASSWORD_VAR, PORT_VAR, SECURITY_VAR, USER_VAR, MailError, Mailer, MailSettings

from . import __version__
from . import mailcheck
from .app import DIR_VAR, LoginApp, folder_for, login_dir, namespace_of
from .users import UserStore


QUIET_SECONDS = 600.0  # `serve --until-quiet`: the server ends after this long without a request (LIMINAL_QUIET_SECONDS)


def _scope(args) -> Scope | None:
    """What the login is tied to: the file named (--cfg, LIMINAL_LOGIN_CFG), else the one found; None: none."""
    cfg = getattr(args, "cfg", None)
    return Scope.read(Path(cfg)) if cfg else Scope.find()


def _root(args) -> Path:
    """Where the users' folders live: --dir, else LIMINAL_LOGIN_DIR, else where the scope keeps them."""
    if getattr(args, "dir", None):
        return Path(args.dir)
    if (os.environ.get(DIR_VAR) or "").strip():
        return login_dir()
    scope = _scope(args)
    return scope.data_dir(login_dir()) if scope is not None else login_dir()


def _namespace(args) -> str:
    return namespace_of(getattr(args, "for_", None))


def _dir(args) -> Path:
    """The namespace's folder: the users' file and the stores of the app this login serves."""
    root = _root(args)
    return folder_for(root, _scope(args) or Scope.local(root), _namespace(args))


def _log(folder: Path) -> Logger:
    return Logger(folder / "logs" / "login.log")


def cmd_serve(args) -> int:
    folder = _dir(args)
    app = LoginApp(_root(args), log=_log(folder), namespace=_namespace(args), scope=_scope(args))
    port = args.port if args.port is not None else app.port()
    mail = app.mailer.settings
    print(f"login app for {app.title_for}: its page at {app.url(port)} (the folder {folder}; "
          f"{'passkeys through ' + mail.host if mail.configured else 'no mail account set (LIMINAL_SMTP_*): no passkeys'}; "
          "Ctrl+C to stop)", flush=True)
    quiet = float(os.environ.get("LIMINAL_QUIET_SECONDS") or QUIET_SECONDS) if args.until_quiet else None
    try:
        app.serve(port, open_browser=not args.no_browser, until_quiet=quiet)
    finally:
        app.close()
    return 0


def cmd_status(args) -> int:
    folder = _dir(args)
    users = UserStore(folder / "users.db")
    try:
        names = users.names()
    finally:
        users.close()
    scope = _scope(args) or Scope.local(_root(args))
    port = LoginApp(_root(args), log=lambda m: None, namespace=_namespace(args), scope=scope).port() if not args.port else args.port
    mail = MailSettings.from_env()
    print(f"login app for {_namespace(args)}: {len(names)} user(s) in {folder / 'users.db'}; "
          f"{'answering' if web.listening(port) else 'not running'} at port {port}; "
          f"mail {'through ' + mail.host + ' as ' + (mail.user or mail.sender) if mail.configured else 'not set up (' + '; '.join(mail.problems()) + ')'}"
          + (f"; signed under {mail.dkim_record}" if mail.signing else "")
          + f"; {scope.label}" + (f" ({scope.path})" if scope.path else ""))
    for u in names:
        print(f"  {u['name']}: created {u['createdAt']}, last sign-in {u['seenAt'] or 'never'}"
              + (f", {u['email']}{' (verified)' if u['verified'] else ''}" if u["email"] else ""))
    return 0


def cmd_user(args) -> int:
    folder = _dir(args)
    users = UserStore(folder / "users.db")
    try:
        if args.action == "list":
            for u in users.names():
                print(f"{u['name']}: created {u['createdAt']}, last sign-in {u['seenAt'] or 'never'}"
                      + (f", {u['email']}{' (verified)' if u['verified'] else ''}" if u["email"] else ""))
            if not users.count():
                print("no users yet: `liminal-login user add NAME`, or the page's first visit")
            return 0
        if args.action == "add":
            if not args.name:
                print("a name is needed: liminal-login user add NAME [--email ADDRESS]", file=sys.stderr)
                return 2
            password = getpass.getpass(f"password for {args.name} (typed hidden): ")
            if password != getpass.getpass("the same password, again: "):
                print("the two passwords differ; nothing made", file=sys.stderr)
                return 1
            try:
                user = users.create(args.name, password, args.email)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
            print(f"user {user.name} created (its store opens with that password; nothing of it is stored)")
            return 0
    finally:
        users.close()
    return 2


PRESETS = {  # what to answer at the host prompt of `mail setup`
    "bridge": ("127.0.0.1", 1025, "starttls", "Proton Bridge on this machine (any paid Proton plan): the user and the password the Bridge window shows"),
    "gmail": ("smtp.gmail.com", 587, "starttls", "Gmail: your address and an app password (2-step verification on)"),
    "direct": ("direct", 25, "starttls", "straight to each address's own mail server, no account (a home connection's message may be filed as spam)"),
}


def mail_setup(args, ask=None, hidden=None) -> int:
    """`mail setup [ADDRESS]`: the mail account typed here, once: the settings kept as your user environment
    variables, the password in Windows' Credential Manager (never a file, never the registry in the clear);
    a login app already running uses it at once. With ADDRESS, one test message goes there after."""
    ask, hidden = ask or input, hidden or getpass.getpass  # looked up now: a test stands them in
    now = MailSettings.from_env()
    print("The mail account the codes go through. At the host prompt: bridge, gmail or direct for a preset, or a host.")
    host = (ask(f"Host [{now.host or 'bridge'}]: ").strip() or now.host or "bridge").lower()
    if host in PRESETS:
        host, port, security, note = PRESETS[host]
        print(f"  {note}")
    else:
        port, security = now.port, now.security
    if host == "direct":
        user, password = "", ""
    else:
        raw = ask(f"Port [{port}]: ").strip()
        port = int(raw) if raw.isdecimal() else port
        security = ask(f"Security, starttls/ssl/none [{security}]: ").strip().lower() or security
        user = ask(f"User, the account's address [{now.user}]: ").strip() or now.user
        password = hidden("Password (typed hidden; empty keeps the one kept): ") if user else ""
    sender = ask(f"From, the address the message comes from [{now.sender or user}]: ").strip() or now.sender or user
    scope = _scope(args)
    mailbox: dict = {}
    mailbox_password = ""
    if scope is not None and scope.path is not None and scope.kind == "domain" and host != "direct":
        # the admin mailbox, read by `mail check` to see the login's own message arrive
        box_host = ask(f"Mailbox host, to read the admin account's mail for the checks [{scope.imap.get('host') or host}]: ").strip() or scope.imap.get("host") or host
        raw = ask(f"Mailbox port [{scope.imap.get('port') or 993}]: ").strip()
        box_port = raw if raw.isdecimal() else (scope.imap.get("port") or "993")
        box_user = ask(f"Mailbox user [{scope.imap.get('user') or scope.admin_address}]: ").strip() or scope.imap.get("user") or scope.admin_address
        mailbox = {"host": box_host, "port": box_port, "security": "ssl" if box_port == "993" else "starttls", "user": box_user}
        mailbox_password = hidden("Mailbox password (typed hidden; empty: the sending password, or the one kept): ")
    if scope is not None and scope.path is not None:  # the login's own file holds its mail server
        from dataclasses import replace

        mail = {**scope.mail, "host": host, "port": str(port), "security": security, "user": user, "from": sender}
        scope = replace(scope, mail={k: v for k, v in mail.items() if v}, imap=mailbox or scope.imap)
        scope.write(scope.path)
        print(f"kept in {scope.path} under [mail]" + (" and [imap]" if mailbox else ""))
        if mailbox and (mailbox_password or password):
            secrets.put("LIMINAL_IMAP_PASSWORD", mailbox_password or password)
    else:
        save_user_variable(HOST_VAR, host)
        save_user_variable(PORT_VAR, str(port))
        save_user_variable(SECURITY_VAR, security)
        save_user_variable(USER_VAR, user or None)
        save_user_variable(FROM_VAR, sender or None)
    if password:
        secrets.put(PASSWORD_VAR, password)
        save_user_variable(PASSWORD_VAR, None)  # never in the registry in the clear
    elif not user:
        secrets.remove(PASSWORD_VAR)
    s = MailSettings.from_env(cfg=scope.mail_variables() if scope is not None else None)
    d = s.describe()
    print(f"kept: {d['host']}:{d['port']} {d['security']}, user {d['user'] or '(none)'}, from {d['sender'] or '(none)'}, "
          f"password {'in Windows Credential Manager' if s.password else '(none)'}")
    if not s.configured:
        print("not complete: " + "; ".join(s.problems()), file=sys.stderr)
        return 1
    if args.address:
        return mail_test(args.address)
    print("set; `liminal-login mail test you@...` sends one message and prints the server's answer")
    return 0


def mail_dkim(args) -> int:
    """`mail dkim init [--domain D] [--selector S] [--new]`: a signing key for your domain (the user, 2026-11-06:
    "it looks like i need a domain/email server for this to work": the domain is yours, the server is this
    app), kept in the login folder (dkim/<domain>.<selector>.pem, in no repository), the three variables
    saved, the DNS record to add printed. `check`: whether the record is published and is this key's.
    `show`: the record again."""
    from liminal_libs import dkim
    from liminal_libs.mail import DKIM_DOMAIN_VAR, DKIM_KEY_VAR, DKIM_SELECTOR_VAR

    s = MailSettings.from_env()
    what = (args.address or "").strip().lower()
    if what == "init":
        domain = (args.domain or s.signing_domain or "").strip().lower()
        if not domain:
            print("a domain is needed: liminal-login mail dkim init --domain your-domain.example "
                  "(or set a From address at it first: liminal-login mail setup)", file=sys.stderr)
            return 2
        selector = (args.selector or s.dkim_selector or "liminal").strip().lower()
        path = _root(args) / "dkim" / f"{domain}.{selector}.pem"
        if path.exists() and not args.new:
            print(f"a key for {selector}._domainkey.{domain} is there already ({path}); --new makes another "
                  "(the DNS record changes with it)", file=sys.stderr)
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        pem, public = dkim.generate_key()
        path.write_bytes(pem)
        save_user_variable(DKIM_KEY_VAR, str(path))
        save_user_variable(DKIM_SELECTOR_VAR, selector)
        save_user_variable(DKIM_DOMAIN_VAR, domain)
        name, value = dkim.dns_record(domain, selector, public)
        print(f"key made: {path} (keep it: the record below is its public half)\n"
              f"Add this TXT record where {domain}'s DNS records live (the registrar or DNS host, not the mailbox provider;\n"
              "a long value may be split there into pieces of 255 characters):\n"
              f"  name:  {name}\n  value: {value}\n"
              f"Then `liminal-login mail dkim check` says when it is published. Messages from an address at {domain} are signed from now on.")
        return 0
    if not s.signing:
        print("no signing key yet: liminal-login mail dkim init --domain your-domain.example", file=sys.stderr)
        return 1
    try:
        public = dkim.public_of(Path(s.dkim_key).read_bytes())
    except (OSError, ValueError) as e:
        print(f"the key file cannot be read ({s.dkim_key}: {e}): liminal-login mail dkim init --new", file=sys.stderr)
        return 1
    name, value = dkim.dns_record(s.signing_domain, s.dkim_selector, public)
    if what == "show":
        print(f"  name:  {name}\n  value: {value}")
        return 0
    if what != "check":
        print("liminal-login mail dkim init | check | show", file=sys.stderr)
        return 2
    found = dkim.published(name)
    if found is None:
        print(f"{name}: no DKIM record found yet (DNS takes minutes, sometimes hours; `mail dkim show` prints what to add)")
        return 1
    if found == public:
        print(f"{name}: published and matching the key here; messages from {s.signing_domain} are signed and provable")
        return 0
    print(f"{name}: a record is published but its key is not the one here (`mail dkim show` prints the right value)", file=sys.stderr)
    return 1


def cmd_server(args) -> int:
    """`server up|down|status|logs|pull|exec` (the user, 2026-11-07: "integrate docker with the liminal framework"):
    the mail server container the login's file declares under [server] (liminal_libs.docker), on this
    machine's Docker or the context's: up makes or starts it, down stops it (its data kept), status says,
    logs prints its last lines, pull fetches its image, exec runs a command inside it."""
    scope = _scope(args)
    if scope is None:
        print("no login file found (liminal-login.cfg): `liminal-login init https://your-domain` first", file=sys.stderr)
        return 2
    service = scope.service(_root(args))
    if service is None:
        print(f"no [server] image in {scope.path or 'the login file'}: the mail server container to run (image = foxcpp/maddy:latest, say)", file=sys.stderr)
        return 2
    docker = scope.docker(log=print)
    what = (args.address or "status").strip().lower()
    try:
        if what == "status":
            d = docker.describe()
            print(f"docker on {d['where']}: " + (f"engine {d['engine']} ({d['os']}/{d['arch']})" if d["available"] else d.get("problem", "not installed")))
            print(f"the mail server container: {service.name} from {service.image}, host name {service.hostname}, ports {', '.join(service.ports) or 'none'}")
            if not d["available"]:
                print("not running: Docker is not available here" + ("" if docker.context or docker.host else "; install Docker Desktop, or name a context under [server] (a VPS)"))
                return 1
            c = docker.container(service.name)
            print(f"{service.name}: " + (f"{c.state} ({c.status}); health {docker.health(c.name)}; ports {c.ports or 'none'}" if c else "not made yet: `liminal-login server up`"))
            return 0 if c and c.running else 1
        if what == "up":
            if not docker.available():
                print(f"Docker is not available on {docker.where}: " + docker.describe().get("problem", "not installed"), file=sys.stderr)
                return 1
            c, done = docker.ensure(service)
            print(f"{service.name} {done}: {c.state} ({c.status}) on {docker.where}; `liminal-login mail check` tells whether it serves")
            return 0
        if what == "down":
            print(f"{service.name}: " + ("stopped (its data kept)" if docker.stop(service.name) else "not there"))
            return 0
        if what == "logs":
            print(docker.logs(service.name, tail=args.tail), end="")
            return 0
        if what == "pull":
            print(docker.pull(service.image), end="")
            return 0
        if what == "exec":
            if not args.command:
                print("a command is needed: liminal-login server exec -- maddy creds list", file=sys.stderr)
                return 2
            print(docker.exec(service.name, *args.command), end="")
            return 0
        if what == "show":
            print(command_line(service))
            return 0
    except DockerError as e:
        print(str(e), file=sys.stderr)
        return 1
    print("liminal-login server up | down | status | logs | pull | exec -- CMD | show", file=sys.stderr)
    return 2


def cmd_init(args) -> int:
    """`init SCOPE [--title T] [--serves a,b] [--port P] [--members any] [--cfg PATH] [--force]`: the login's file,
    liminal-login.cfg (the user, 2026-11-06: "have like a setup.cfg for the login, and then like other web
    apps use that cfg file to decide the domain/scope of the login"). SCOPE is file:///a/project/folder (a
    local login: no email, no sign-up) or https://a.domain (the domain's users, their codes through its
    mail record's server or the one named in [mail])."""
    from dataclasses import replace

    url = args.scope_url.strip()
    if "://" not in url and not url.lower().startswith("file:"):
        url = Path(url).expanduser().resolve().as_uri() if Path(url).expanduser().is_dir() else f"https://{url}"
    try:
        scope = Scope.parse(f"[login]\nscope = {url}\nmembers = {(args.members or 'domain').strip().lower()}\n"
                            + (f"admin = {args.admin.strip().lower()}\n" if args.admin else ""))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    serves = tuple(s.strip().lower() for s in (args.serves or "charts").replace(";", ",").split(",") if s.strip()) or ("charts",)
    scope = replace(scope, title=(args.title or "").strip(), serves=serves, port=args.port)
    path = Path(args.cfg) if args.cfg else ((scope.root if scope.kind == "local" else (layout.home() or login_dir())) / FILE_NAME)
    if path.exists() and not args.force:
        print(f"{path} is there already; --force replaces it", file=sys.stderr)
        return 1
    scope.write(path)
    print(f"{path}:\n{scope.text()}")
    if scope.kind == "domain":
        print(f"The users of {scope.domain} sign up with a code sent from {scope.admin_address} through "
              + (scope.mail.get("host") or "the domain's own mail record (MX); name a server under [mail] if it has none")
              + f". The admin account's host, {scope.admin_host}, must be valid in DNS; `liminal-login mail check` tells.")
    else:
        print(f"A local login for {scope.root}: no email; the first user is made on the page or with `liminal-login user add NAME`.")
    return 0


def mail_check(args) -> int:
    """`mail check [--to ADDRESS ...] [--wait SECONDS]`: the login's own check of its mail server with its
    admin account (mailcheck.py): the admin host in DNS, a message to the admin account sent and seen back
    in its mailbox, one to each address asked, each with the server's answer. 0 when nothing failed."""
    scope = _scope(args)
    if scope is None:
        print("no login file found (liminal-login.cfg): `liminal-login init https://your-domain` first", file=sys.stderr)
        return 2
    mailer = Mailer(log=print, cfg=scope.mail_variables())
    mailbox = Mailbox(log=print, cfg=scope.imap_variables())
    service = scope.service(_root(args))
    checks = mailcheck.run(scope, mailer, mailbox, to=args.to or (), wait=args.wait, log=print,
                           docker=scope.docker(log=print) if service is not None else None, service=service)
    print(mailcheck.report(checks))
    return 0 if mailcheck.passed(checks) else 1


def cmd_mail(args) -> int:
    """`mail setup [ADDRESS]` keeps the account; `mail test ADDRESS` sends one message through it, so you see
    it arrive and read the server's answer; `mail dkim init|check|show`: the signing key for your domain;
    `mail check`: the server checked with the login's admin account."""
    if args.action == "setup":
        return mail_setup(args)
    if args.action == "check":
        return mail_check(args)
    if args.action == "dkim":
        return mail_dkim(args)
    if not args.address:
        print("an address is needed: liminal-login mail test you@example.com", file=sys.stderr)
        return 2
    return mail_test(args.address)


def mail_test(address: str) -> int:
    mailer = Mailer(log=print)
    try:
        sent = mailer.send(address, "Liminal: a test message",
                           "This message came from the Liminal login app through the mail account in your environment.\n"
                           "Sign-up codes will come the same way.\n")
    except MailError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"sent to {address}: {sent} at {sent.at}, message id {sent.message_id}; "
          "look for it (the spam folder too, the first time)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="liminal-login", description="The Liminal login app: the users and their keys and accounts.")
    p.add_argument("--version", action="version", version=f"liminal-login {__version__}")
    p.add_argument("--dir", help="the folder of the namespaces (LIMINAL_LOGIN_DIR; store/data/login by default)")
    p.add_argument("--cfg", default=None, help=f"the login's file, {FILE_NAME} (LIMINAL_LOGIN_CFG; else the one found: the workspace's, the working folder's)")
    p.add_argument("--for", dest="for_", default=None,
                   help="the app this login serves, its users' namespace: charts (the default) or integrator (LIMINAL_LOGIN_FOR)")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("serve", help="keep the login's page at its port until Ctrl+C")
    s.add_argument("--port", type=int, default=None, help="the page's port (LIMINAL_LOGIN_PORT, 8795)")
    s.add_argument("--no-browser", action="store_true", help="do not open the page in a browser")
    s.add_argument("--until-quiet", action="store_true",
                   help=f"end once no page has been in touch for LIMINAL_QUIET_SECONDS ({QUIET_SECONDS:g}): what another app's front starts")
    s.set_defaults(func=cmd_serve)
    i = sub.add_parser("init", help=f"write {FILE_NAME}: SCOPE is file:///a/project/folder (local) or https://a.domain (the domain's users)")
    i.add_argument("scope_url")
    i.add_argument("--title", default=None)
    i.add_argument("--serves", default=None, help="the apps this login serves: charts, integrator (charts)")
    i.add_argument("--port", type=int, default=None)
    i.add_argument("--members", default=None, help="a domain's login: domain (addresses at the domain only) or any")
    i.add_argument("--admin", default=None, help="a domain's login: its own account, admin@<a host under the domain> (admin@<domain>)")
    i.add_argument("--cfg", default=None, help="where to write it (the folder itself for file:, the workspace for a domain)")
    i.add_argument("--force", action="store_true", help="replace a file that is there")
    i.set_defaults(func=cmd_init)
    sv = sub.add_parser("server", help="the mail server container the login file declares under [server]: up, down, status, logs, pull, exec -- CMD, show")
    sv.add_argument("address", nargs="?", default="status", metavar="what", help="up | down | status | logs | pull | exec | show")
    sv.add_argument("--tail", type=int, default=100, help="logs: how many last lines")
    sv.add_argument("command", nargs="*", help="exec: the command inside the container, after --")
    sv.set_defaults(func=cmd_server)
    st = sub.add_parser("status", help="the users here, whether the page answers, the mail account, what the login is tied to")
    st.add_argument("--port", type=int, default=None)
    st.set_defaults(func=cmd_status)
    u = sub.add_parser("user", help="the users: add NAME [--email ADDRESS] (the password typed hidden), list")
    u.add_argument("action", choices=("add", "list"))
    u.add_argument("name", nargs="?")
    u.add_argument("--email", default=None, help="the user's email address (not verified: no passkey here)")
    u.set_defaults(func=cmd_user)
    m = sub.add_parser("mail", help="the mail account: setup keeps it (typed here once), test ADDRESS sends one message through it, "
                                   "dkim init|check|show: the signing key for your own domain")
    m.add_argument("action", choices=("setup", "test", "dkim", "check"))
    m.add_argument("address", nargs="?", help="test: where to; setup: where a test message goes once the account is kept; dkim: init, check or show")
    m.add_argument("--domain", default=None, help="dkim init: the domain to sign for (the From address's unless said)")
    m.add_argument("--selector", default=None, help="dkim init: the record's selector (liminal)")
    m.add_argument("--new", action="store_true", help="dkim init: a new key though one is there (the DNS record changes)")
    m.add_argument("--to", action="append", default=None, help="check: an address to send to besides the admin account (yours; one on another server)")
    m.add_argument("--wait", type=float, default=60.0, help="check: how long to look for the message in the admin mailbox (60 s)")
    m.set_defaults(func=cmd_mail)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    commands = ("serve", "status", "user", "mail", "init", "server")
    if not any(a in commands for a in argv) and not any(a in ("-h", "--help", "--version") for a in argv):
        i = 0  # `liminal-login [--for X] [--dir Y] [serve's options]`: serve, after the options every command takes
        while i < len(argv) and argv[i] in ("--dir", "--for", "--cfg"):
            i += 2
        argv = [*argv[:i], "serve", *argv[i:]]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    return args.func(args)
