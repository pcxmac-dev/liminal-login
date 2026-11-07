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

from liminal_libs import web
from liminal_libs.logs import Logger
from liminal_libs.mail import MailError, Mailer, MailSettings

from . import __version__
from .app import LoginApp, login_dir, namespace_of
from .users import UserStore


QUIET_SECONDS = 600.0  # `serve --until-quiet`: the server ends after this long without a request (LIMINAL_QUIET_SECONDS)


def _root(args) -> Path:
    return Path(args.dir) if getattr(args, "dir", None) else login_dir()


def _namespace(args) -> str:
    return namespace_of(getattr(args, "for_", None))


def _dir(args) -> Path:
    """The namespace's folder: the users' file and the stores of the app this login serves."""
    return _root(args) / _namespace(args)


def _log(folder: Path) -> Logger:
    return Logger(folder / "logs" / "login.log")


def cmd_serve(args) -> int:
    folder = _dir(args)
    app = LoginApp(_root(args), log=_log(folder), namespace=_namespace(args))
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
    port = LoginApp(_root(args), log=lambda m: None, namespace=_namespace(args)).port() if not args.port else args.port
    mail = MailSettings.from_env()
    print(f"login app for {_namespace(args)}: {len(names)} user(s) in {folder / 'users.db'}; "
          f"{'answering' if web.listening(port) else 'not running'} at port {port}; "
          f"mail {'through ' + mail.host + ' as ' + (mail.user or mail.sender) if mail.configured else 'not set up (' + '; '.join(mail.problems()) + ')'}")
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


def cmd_mail(args) -> int:
    """`mail test ADDRESS`: one message through the account in the environment, so you see it arrive."""
    mailer = Mailer(log=print)
    if args.action != "test":
        return 2
    if not args.address:
        print("an address is needed: liminal-login mail test you@example.com", file=sys.stderr)
        return 2
    try:
        mailer.send(args.address, "Liminal: a test message",
                    "This message came from the Liminal login app through the mail account in your environment.\n"
                    "Passkeys for new accounts will come the same way.\n")
    except MailError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"sent to {args.address} through {mailer.settings.host}: look for it (the spam folder too, the first time)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="liminal-login", description="The Liminal login app: the users and their keys and accounts.")
    p.add_argument("--version", action="version", version=f"liminal-login {__version__}")
    p.add_argument("--dir", help="the folder of the namespaces (LIMINAL_LOGIN_DIR; store/data/login by default)")
    p.add_argument("--for", dest="for_", default=None,
                   help="the app this login serves, its users' namespace: charts (the default) or integrator (LIMINAL_LOGIN_FOR)")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("serve", help="keep the login's page at its port until Ctrl+C")
    s.add_argument("--port", type=int, default=None, help="the page's port (LIMINAL_LOGIN_PORT, 8795)")
    s.add_argument("--no-browser", action="store_true", help="do not open the page in a browser")
    s.add_argument("--until-quiet", action="store_true",
                   help=f"end once no page has been in touch for LIMINAL_QUIET_SECONDS ({QUIET_SECONDS:g}): what another app's front starts")
    s.set_defaults(func=cmd_serve)
    st = sub.add_parser("status", help="the users here, whether the page answers, the mail account")
    st.add_argument("--port", type=int, default=None)
    st.set_defaults(func=cmd_status)
    u = sub.add_parser("user", help="the users: add NAME [--email ADDRESS] (the password typed hidden), list")
    u.add_argument("action", choices=("add", "list"))
    u.add_argument("name", nargs="?")
    u.add_argument("--email", default=None, help="the user's email address (not verified: no passkey here)")
    u.set_defaults(func=cmd_user)
    m = sub.add_parser("mail", help="the mail account: test ADDRESS sends one message through it")
    m.add_argument("action", choices=("test",))
    m.add_argument("address", nargs="?")
    m.set_defaults(func=cmd_mail)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    commands = ("serve", "status", "user", "mail")
    if not any(a in commands for a in argv) and not any(a in ("-h", "--help", "--version") for a in argv):
        i = 0  # `liminal-login [--for X] [--dir Y] [serve's options]`: serve, after the options every command takes
        while i < len(argv) and argv[i] in ("--dir", "--for"):
            i += 2
        argv = [*argv[:i], "serve", *argv[i:]]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    return args.func(args)
