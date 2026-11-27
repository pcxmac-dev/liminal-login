"""The login's own routes, as its Internal API lists them beside the frame's (0.20.1, Monday list item 17;
liminal-libs 1.63.0's internal.py; the user, 2026-11-16: "for all apps, and all plugins, there should be an external
api tab, and an internal api tab"; 2026-11-17: "all plugins all apps").

ROUTES is one row for each route LoginApp._api answers (app.py), then one for each of the frame's routes it narrows
to who may ask them: the code base (0.17.6) and its own two views (0.20.1), to one of its own users signed in to a
local login. The frame's other routes follow them in its Internal API, as the library lists them (FRAME_ROUTES).
Held by an app, the login answers the same routes under that app's /login/, at that app's port.

Each row is (method, path, what it is, its class, who asks it), as liminal_libs.internal.FRAME_ROUTES: `{...}` is a
part that varies; the class is read, change, ask or stream; who asks it is the page, a client (the library's
LoginClient, X-Liminal-Session) or another login (a user of another domain's login, asked there over https). Plain
tuples: nothing is imported with them. tests/test_routes.py holds ROUTES to app.py: a route added there without its
row here fails it."""
from __future__ import annotations

ROUTES = (
    ("GET", "/api/status", "whether it has users, who is signed in in this browser (or with this session), whether "
                           "they are its admin, what it is tied to, where its users are and how sign-up stands",
     "read", "page"),
    ("GET", "/api/users", "the names of its users, for one of them signed in", "read", "page"),
    ("POST", "/api/users", "a user added: by one signed in, or at this machine on a local login (a domain's makes its "
                           "first at its machine with `liminal-login user add NAME`)", "change", "page"),
    ("GET", "/api/login-plugins", "its plugins (0.18.0), each with its tabs, for anyone signed in", "read", "page"),
    ("GET", "/api/login-plugins/{name}/{tab}", "a plugin's tab drawn for the one signed in (the plugin's page hook, "
                                               "with what it keeps here; never a value of their pairs)", "read",
     "page"),
    ("POST", "/api/login-plugins/{name}/{tab}", "a change asked on a plugin's tab (its change hook); on a tab only "
                                                "the admin may change, refused to anyone else before it is asked",
     "change", "page"),
    ("POST", "/api/sign-in/secret", "the way in without a password: the secret user and `default`, on a local login "
                                    "and at its own machine only", "change", "page"),
    ("POST", "/api/signup", "a sign-up begun: a code mailed to the address (a domain's login, sign-up open)", "change",
     "page"),
    ("POST", "/api/signup/resend", "the code mailed again", "change", "page"),
    ("POST", "/api/signup/verify", "the code typed back, counted as a wrong password is when it is wrong", "change",
     "page"),
    ("POST", "/api/signup/complete", "the account made with its name and password, and signed in", "change", "page"),
    ("POST", "/api/sign-in", "a sign-in with a password, throttled; name@their.domain is a user of that domain's "
                             "login, asked there (the library's LoginClient signs in here too)", "change", "page"),
    ("POST", "/api/sign-out", "every session this browser carries ended, and a remote user's at their own login too",
     "change", "page"),
    ("GET", "/api/me", "who is signed in: their name, their store and the fingerprints of the keys that mask it (a "
                       "remote user's asked of their own login)", "read", "page"),
    ("PUT", "/api/me/password", "their password changed, the vault key wrapped again and their other sessions ended "
                                "(never the secret user's); a wrong current password counted as a failed sign-in, 429 "
                                "with Retry-After past the limits", "change", "page"),
    ("GET", "/api/pairs", "the names of their pairs, never a value (the library's LoginClient asks it too)", "read",
     "page"),
    ("GET", "/api/pairs/known", "the pairs the plugins of the app that holds it ask for, each set or not", "read",
     "page"),
    ("GET", "/api/pairs/{name}", "one pair's value, unsealed for the one signed in: revealed on the page, or read by "
                                 "a program given their session", "read", "client"),
    ("PUT", "/api/pairs/{name}", "a pair kept, sealed under their vault key", "change", "client"),
    ("DELETE", "/api/pairs/{name}", "a pair removed", "change", "client"),
    # the frame's routes it narrows to its own users signed in to a local login (a domain's login: anyone who signs up)
    ("GET", "/api/codebase", "the code it is made of, its repositories and their languages (?fresh=1 reads them "
                             "again): for one of its own users signed in to a local login, never on a domain's login",
     "read", "page"),
    ("POST", "/api/codebase/fetch", "its repositories' remotes asked what they have, on that user's click", "change",
     "page"),
    ("GET", "/api/app/apis", "its own External and Internal API: for one of its own users signed in to a local login, "
                             "never on a domain's login; with ?plugin=NAME, one of its plugins' two (as the frame "
                             "answers them), for anyone signed in", "read", "page"),
)
