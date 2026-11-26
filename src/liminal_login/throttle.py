"""Sign-ins throttled (LOG-C1, 2026-11-23: the Docker login let anyone who reached it guess at speed): the failed ones
counted in memory, by where they came from and by the name tried. Past PER_PEER failures from one address, or PER_NAME
for one name, within WINDOW_S, a sign-in from there or for that name is answered at once (429, before any key is
derived) until the oldest of them is WINDOW_S old; nothing is locked for good.

A try is counted before its key is derived and taken back unless it failed (`tried`, `forget`), so the limits hold
however many arrive together (the review of LOG-C1's fix, 2026-11-25: counted only once it had failed, a burst sent at
once was all tried, each asked before any had failed). The keys derived at once are bounded too (`deriving`: AT_ONCE
from each place, the others waiting their turn), so a burst cannot take the machine's memory and, with the process,
the counts.

The counts of this machine itself and of what a front hands on are kept apart (`where`), so that nobody who reaches the
front can keep anyone at the machine out, the secret user least of all: its way in without a password, here, is never
asked (app.py). Bounded: at most KEPT counters, the one touched longest ago dropped first, each holding no more than its
limit's times; more names and addresses failing within a window than there are counters make it forget the oldest of
them, whose limits start again. A name is counted as it was typed, its case and the spaces around it aside: an
account's email, typed in its place, is counted apart from its name. Nothing is written anywhere, and a restart forgets
them.

A sign-up's wrong codes are counted in the same counts, with the same numbers (the last check of LOG-C1's fix,
2026-11-25: a six-digit code could be guessed at speed): by where they came from, with the failed sign-ins from there,
and by the address the code was mailed to, as a name is (app.py's _verify). A new code gives none of them back."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque

WINDOW_S = 900.0  # a failure counts this long (15 minutes)
PER_PEER = 30  # failures from one address within the window before its sign-ins wait
PER_NAME = 10  # failures for one name within the window before its sign-ins wait
KEPT = 4096  # counters kept at the most
NAME_CHARS = 254  # of a name typed, what is counted (an address's length)
AT_ONCE = 4  # keys derived at once for sign-ins with a password, from each place (scrypt: 32 MB and about 0.1 s each)


class Throttle:
    """The sign-ins tried, counted: the failed ones for a window, the others while they are being tried. `where` is
    "here" (a program on this machine: liminal_libs.web.from_this_machine) or "away" (handed on by a front, or from
    another machine); `peer` the address (web.peer); `name` the name typed (for a sign-up's code, the address it was
    mailed to)."""

    def __init__(self, window: float = WINDOW_S, per_peer: int = PER_PEER, per_name: int = PER_NAME, kept: int = KEPT,
                 clock=time.monotonic, at_once: int = AT_ONCE):
        self.window = float(window)
        self.limits = {"peer": max(1, int(per_peer)), "name": max(1, int(per_name))}
        self.kept = max(2, int(kept))
        self.at_once = max(1, int(at_once))
        self.clock = clock
        self._counts: OrderedDict[tuple, deque] = OrderedDict()
        self._gates: dict[str, threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(where: str, peer: str, name: str) -> tuple[tuple, tuple]:
        return ("peer", str(where), str(peer)), ("name", str(where), str(name or "").strip().lower()[:NAME_CHARS])

    def wait(self, where: str, peer: str, name: str) -> float:
        """Seconds before a sign-in from `peer` for `name` may be tried again; 0.0: now."""
        now = self.clock()
        out = 0.0
        with self._lock:
            for key in self._keys(where, peer, name):
                times = self._counts.get(key)
                if times is not None and len(times) >= self.limits[key[0]]:
                    out = max(out, times[0] + self.window - now)
        return max(out, 0.0)

    def tried(self, where: str, peer: str, name: str) -> tuple[float, float | None]:
        """A sign-in from `peer` for `name` about to be tried: (0.0, when it was counted), counted for both before its
        key is derived; or, with either at its limit, (the seconds to wait, None) and nothing counted. Asked and counted
        in one hold of the lock: however many arrive together, no more than a limit's are being tried or have failed
        within the window. A try that did not fail is taken back (`forget`); one that failed stays as it was counted."""
        keys = self._keys(where, peer, name)
        with self._lock:
            now = self.clock()
            wait = 0.0
            for key in keys:
                times = self._counts.get(key)
                if times is not None and len(times) >= self.limits[key[0]]:
                    wait = max(wait, times[0] + self.window - now)
            if wait > 0:
                return wait, None
            for key in keys:
                times = self._counts.pop(key, None)
                if times is None:
                    times = deque(maxlen=self.limits[key[0]])
                times.append(now)  # a full one's oldest is a window old here, and goes as this one comes
                self._counts[key] = times  # the one touched last, last: dropped last
            while len(self._counts) > self.kept:
                self._counts.popitem(last=False)
        return 0.0, now

    def forget(self, where: str, peer: str, name: str, at: float) -> None:
        """A try taken back out of both counts, by when it was counted: its password was right, or nothing said it was
        wrong (another login did not answer, an error). One dropped since to make room is gone already: nothing."""
        with self._lock:
            for key in self._keys(where, peer, name):
                times = self._counts.get(key)
                if times is None or at not in times:
                    continue
                times.remove(at)
                if not times:
                    del self._counts[key]

    def deriving(self, where: str) -> threading.BoundedSemaphore:
        """The gate a sign-in's key is derived behind (`with throttle.deriving(where): ...`): `at_once` of them at once
        from each place, the others waiting their turn. This machine's own and a front's wait apart, as they are
        counted apart: nobody who reaches a front makes a sign-in at the machine wait."""
        with self._lock:
            gate = self._gates.get(str(where))
            if gate is None:
                gate = self._gates[str(where)] = threading.BoundedSemaphore(self.at_once)
        return gate

    def __len__(self) -> int:
        with self._lock:
            return len(self._counts)
