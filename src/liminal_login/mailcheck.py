"""The login's own check of its mail server, with its admin account (the user, 2026-11-06: "the admin
account could be used to test the server so that it can send and receive with the user email and also see
if emails can be sent to other servers, without error"; "the container or email server would be responsible
for services rendered outside the local domain"): the admin address's host valid in DNS, a message to the
admin account itself sent and seen back in its mailbox, one to each address asked (yours, and others on
other servers), each with the mail server's own answer. The login only submits to the server; the server
(the container) carries everything beyond the local domain."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from liminal_libs import dns
from liminal_libs.mail import MailError
from liminal_libs.mailbox import MailboxError

POLL_SECONDS = 5.0


@dataclass
class Check:
    name: str
    ok: bool | None  # None: not checked (nothing to check it with)
    detail: str

    @property
    def word(self) -> str:
        return "ok" if self.ok else ("skipped" if self.ok is None else "FAILED")


def run(scope, mailer, mailbox, to=(), wait: float = 60.0, log=print, sleep=time.sleep) -> list[Check]:
    """The checks, in order; `to`: the addresses to send to besides the admin account (yours, one at another
    server); `wait`: how long to look for the message to the admin account in its mailbox."""
    out: list[Check] = []
    if scope.kind != "domain":
        return [Check("the login", False, f"a local login ({scope.label}) sends no email: nothing to check")]
    admin, host = scope.admin_address, scope.admin_host
    addresses = dns.addresses(host)
    exchangers = dns.mx_records(host)
    valid = bool(addresses) or bool(exchangers)
    out.append(Check(f"{host} in DNS", valid, (f"addresses {', '.join(addresses or []) or 'none'}; mail record {', '.join(exchangers or []) or 'none'}")
                     + ("" if valid else ": the admin account's host needs an address or a mail record")))
    spf = dns.spf_record(host) if valid else None
    out.append(Check(f"SPF for {host}", (True if spf else None) if spf is not None else None,
                     spf or "none published: receivers may doubt the sender (the server's own domain may carry it)"))
    s = mailer.settings
    out.append(Check("the mail server", s.configured, (f"{'the admin host\'s own mail record' if s.direct else s.host + ':' + str(s.port)} as {s.sender}"
                                                      if s.configured else "not set up: " + "; ".join(s.problems()))))
    if s.signing:
        from liminal_libs import dkim

        published = dkim.published(s.dkim_record)
        out.append(Check(f"DKIM record {s.dkim_record}", published is not None, "published" if published else "not found: `liminal-login mail dkim check`"))
    if not s.configured:
        return out
    token = f"liminal-check-{secrets.token_hex(4)}"
    text = (f"This is the Liminal login app checking its own mail server with its admin account ({admin}).\n"
            f"Check {token}. If you asked for this, nothing else is needed.\n")
    sent_self = False
    for address, what in [(admin, "to the admin account itself"), *((a, f"to {a}") for a in to)]:
        try:
            sent = mailer.send(address, f"Liminal check {token}", text)
            out.append(Check(f"sent {what}", True, f"{sent}, message id {sent.message_id}"))
            sent_self = sent_self or address == admin
        except MailError as e:
            out.append(Check(f"sent {what}", False, str(e)))
    if not mailbox.configured:
        out.append(Check("received back in the admin mailbox", None, "no mailbox set to read ([imap] in liminal-login.cfg: `mail setup`)"))
        return out
    if not sent_self:
        out.append(Check("received back in the admin mailbox", False, "nothing was sent to it"))
        return out
    deadline = time.monotonic() + wait
    found = 0
    while True:
        try:
            found = mailbox.find(token)
        except MailboxError as e:
            out.append(Check("received back in the admin mailbox", False, str(e)))
            return out
        if found or time.monotonic() >= deadline:
            break
        log(f"check: not in the admin mailbox yet; looking again in {POLL_SECONDS:g} s")
        sleep(POLL_SECONDS)
    out.append(Check("received back in the admin mailbox", found > 0,
                     f"{found} message(s) with the check's subject" if found else f"not there after {wait:g} s: the server took it but did not deliver it to {admin}"))
    return out


def report(checks: list[Check]) -> str:
    width = max((len(c.name) for c in checks), default=0)
    return "\n".join(f"{c.word:>7}  {c.name:<{width}}  {c.detail}" for c in checks)


def passed(checks: list[Check]) -> bool:
    return all(c.ok is not False for c in checks)
