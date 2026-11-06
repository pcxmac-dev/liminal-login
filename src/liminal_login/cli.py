"""`liminal-login`: the login app's command line. `serve` keeps its page at its port (8795,
LIMINAL_LOGIN_PORT) until Ctrl+C; `user add NAME` makes a user (the password typed hidden, twice;
never on the command line); `user list` names them; `status` says what is there. The folder of the
users' file and the stores is LIMINAL_LOGIN_DIR, else store/data/login (liminal_libs.layout)."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from liminal_libs import web
from liminal_libs.logs import Logger

from . import __version__
from .app import LoginApp, login_dir
from .users import UserStore


def _dir(args) -> Path:
    return Path(args.dir) if getattr(args, "dir", None) else login_dir()


def _log(folder: Path) -> Logger:
    return Logger(folder / "logs" / "login.log")


def cmd_serve(args) -> int:
    folder = _dir(args)
    app = LoginApp(folder, log=_log(folder))
    port = args.port if args.port is not None else app.port()
    print(f"login app: its page at {app.url(port)} (the folder {folder}; Ctrl+C to stop)", flush=True)
    try:
        app.serve(port, open_browser=not args.no_browser)
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
    port = LoginApp().port() if not args.port else args.port
    print(f"login app: {len(names)} user(s) in {folder / 'users.db'}; "
          f"{'answering' if web.listening(port) else 'not running'} at port {port}")
    for u in names:
        print(f"  {u['name']}: created {u['createdAt']}, last sign-in {u['seenAt'] or 'never'}")
    return 0


def cmd_user(args) -> int:
    folder = _dir(args)
    users = UserStore(folder / "users.db")
    try:
        if args.action == "list":
            for u in users.names():
                print(f"{u['name']}: created {u['createdAt']}, last sign-in {u['seenAt'] or 'never'}")
            if not users.count():
                print("no users yet: `liminal-login user add NAME`, or the page's first visit")
            return 0
        if args.action == "add":
            if not args.name:
                print("a name is needed: liminal-login user add NAME", file=sys.stderr)
                return 2
            password = getpass.getpass(f"password for {args.name} (typed hidden): ")
            if password != getpass.getpass("the same password, again: "):
                print("the two passwords differ; nothing made", file=sys.stderr)
                return 1
            try:
                user = users.create(args.name, password)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
            print(f"user {user.name} created (its store opens with that password; nothing of it is stored)")
            return 0
    finally:
        users.close()
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="liminal-login", description="The Liminal login app: the users and their keys and accounts.")
    p.add_argument("--version", action="version", version=f"liminal-login {__version__}")
    p.add_argument("--dir", help="the folder of the users' file and the stores (LIMINAL_LOGIN_DIR; store/data/login by default)")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("serve", help="keep the login's page at its port until Ctrl+C")
    s.add_argument("--port", type=int, default=None, help="the page's port (LIMINAL_LOGIN_PORT, 8795)")
    s.add_argument("--no-browser", action="store_true", help="do not open the page in a browser")
    s.set_defaults(func=cmd_serve)
    st = sub.add_parser("status", help="the users here and whether the page answers")
    st.add_argument("--port", type=int, default=None)
    st.set_defaults(func=cmd_status)
    u = sub.add_parser("user", help="the users: add NAME (the password typed hidden), list")
    u.add_argument("action", choices=("add", "list"))
    u.add_argument("name", nargs="?")
    u.set_defaults(func=cmd_user)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["serve", *argv]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    return args.func(args)
