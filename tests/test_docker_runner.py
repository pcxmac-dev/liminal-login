"""A stand-in for the docker command (liminal_libs.docker.Docker's runner), for the login's tests of its
mail server container: the same as the library's tests use."""
from __future__ import annotations

import json

VERSION = {"Client": {"Version": "28.1.1"}, "Server": {"Version": "28.1.1", "Os": "linux", "Arch": "amd64"}}


class Runner:
    def __init__(self, rows=None, version=VERSION, fail=()):
        self.calls: list[list[str]] = []
        self.rows = list(rows or [])
        self.version = version
        self.fail = set(fail)

    def __call__(self, args, timeout):
        self.calls.append(list(args))
        verb = next((a for a in args[1:] if not a.startswith("-")), "")
        if args[1] in ("--context", "-H"):
            verb = args[3]
        if verb in self.fail:
            return 1, "", f"Error response from daemon: {verb} failed"
        if verb == "version":
            return 0, json.dumps(self.version), ""
        if verb == "ps":
            return 0, "\n".join(json.dumps(r) for r in self.rows) + "\n", ""
        if verb == "run":
            name = args[args.index("--name") + 1]
            self.rows.append({"ID": "new789", "Names": name, "Image": args[-1], "State": "running", "Status": "Up 1 second", "Ports": ""})
            return 0, "new789\n", ""
        if verb == "start":
            for r in self.rows:
                if r["Names"] == args[-1]:
                    r["State"], r["Status"] = "running", "Up 1 second"
            return 0, "", ""
        if verb == "stop":
            for r in self.rows:
                if r["Names"] == args[-1]:
                    r["State"], r["Status"] = "exited", "Exited (0) 1 second ago"
            return 0, args[-1] + "\n", ""
        if verb == "rm":
            self.rows = [r for r in self.rows if r["Names"] != args[-1]]
            return 0, "", ""
        if verb == "logs":
            return 0, "maddy started\n", ""
        if verb == "exec":
            return 0, "ok from inside\n", ""
        if verb == "inspect":
            return 0, json.dumps([{"State": {"Status": "running", "Health": {"Status": "healthy"}}}]), ""
        if verb == "pull":
            return 0, "Status: Image is up to date\n", ""
        if verb == "compose":
            return 0, "composed\n", ""
        return 1, "", f"unknown {verb}"
