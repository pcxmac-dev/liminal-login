// The login app's page: signed out, the sign-in form and the way to an account (the user, 2026-11-06:
// "sign up lets you put in an email and sends an email to an email account, which you then enter the
// 4-6 digit code back in to the signup prompt to generate a new user, password, etcc"): the email,
// the code from the email, then the account name and the password; signed in, who you are, your
// store and the fingerprints of the keys that mask it, your pairs (masked; revealed one at a time),
// a form to add one, a password change, sign out. The API paths are relative, so the page works under
// another app's prefix too (an inheriting app's /login/, say); inside another app's page (?embedded=1) the
// rail is hidden and the parent page is told when you sign in or out.
// 0.12.0 (the user, 2026-11-10: "let's do an update. I want to support touch as well as mouse clicking on the
// interface ... We'll make sure it works across all apps"; "Support for virtual keyboard on tablets and phones"): every
// field calls up its keyboard (the library's touch.js), its Enter says Next until the last field, and no keyboard is
// called up before a field is tapped. A mouse and a hardware keyboard work as they did.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const KINDS = ['key', 'account', 'password', 'detail'];
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const main = $('main');
  // a finger, a pen and the on-screen keyboard (liminal-libs 1.42.0's touch.js, loaded before this file); without it, the
  // fields as a mouse and a keyboard had them
  const T = window.LiminalTouch || null;
  const AS_BEFORE = { username: 'username', email: 'email', password: 'current-password', code: 'one-time-code', secret: 'off', plain: 'off' };
  function kb(kind, more) {  // a field's keyboard, as attributes (the kinds: LiminalTouch.KEYBOARDS)
    if (T) return T.keyboard(kind, more);
    const ac = (more && typeof more === 'object' && more.autocomplete) || AS_BEFORE[kind];
    return `${ac ? `autocomplete="${ac}"` : ''}${kind === 'code' ? ' inputmode="numeric"' : ''}`;
  }
  const NEW_NEXT = { autocomplete: 'new-password', enterkeyhint: 'next' }, NEW_DONE = { autocomplete: 'new-password', enterkeyhint: 'done' };  // a password chosen
  const fingered = () => !!T && (T.lastInput === 'touch' || T.lastInput === 'pen');  // the user's last move was a finger's
  // a form's first field focused for a mouse or a keyboard; after a finger's tap (and on a phone or a tablet before any
  // move) left for the user to tap, so the keyboard does not cover the card unasked
  function focusFirst(el) {
    if (!el) return false;
    if (T) return T.autofocus(el);
    el.focus();
    return true;
  }
  const embedded = new URLSearchParams(location.search).get('embedded') === '1';
  if (embedded) document.body.classList.add('embedded');
  $('railUser').innerHTML = icon('lambda', 30);  // Liminal's sign, the login's master icon (0.13.1; the user icon until then)
  let signup = null;  // a sign-up under way: { email, token }
  let forTitle = 'Liminal';
  let mail = {};  // how codes go out (the status's signup: the host, the sender, the last send's receipt)

  function tell(signedIn, name) {
    // the page holding this one (the page of an app that inherits the login) learns who is signed in
    if (embedded && window.parent !== window) window.parent.postMessage({ liminal: 'login', signedIn, name: name || null }, location.origin);
  }

  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE,
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    if (!r.ok) {
      const err = new Error((data && data.error) || `the login app answered ${r.status}`);
      err.status = r.status;  // what the caller may go on by (the way in: 400, not the secret user)
      throw err;
    }
    return data;
  }
  const when = (iso) => (iso ? new Date(iso).toLocaleString() : 'never');

  // the tab says where the page is: sign in, the first user, sign up, or who is signed in (0.12.1: it said "sign in"
  // throughout, signed in too)
  const titled = (what) => { document.title = `${forTitle}: ${what}`; };

  async function render() {
    let st;
    try { st = await api('GET', 'api/status'); }
    catch (e) { main.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    forTitle = st.forTitle || 'Liminal';
    mail = st.signup || {};
    titled('sign in');
    if (signup) return signup.token ? detailsForm() : codeForm();
    if (!st.signedIn) { tell(false); return entryForm(st); }
    const me = await api('GET', 'api/me');
    const pairs = (await api('GET', 'api/pairs')).pairs;
    const known = (await api('GET', 'api/pairs/known')).known;  // the pairs the plugins here ask for
    main.innerHTML = userCard(me) + pairsTable(pairs, known) + knownTable(known) + addForm(known) + changeForm();
    titled(me.name);
    wire(me);
    tell(true, me.name);
  }

  // -- signed out: the way in, or sign in with a password, or sign up ---------------------------------------------
  // The way in (0.14.0; the user, 2026-11-10: "for now lets have a secret user, name - secret, no password entry, you
  // type secret in to user and click on icon"; "that will be the default"; "signup and sign-in should be options too"):
  // the user's name, then the icon (or Enter): secret comes straight in (a local login), anyone else goes on to their
  // password; Sign in and Sign up beside it
  function entryForm(st, said = '') {
    titled('sign in');
    main.innerHTML = `<div class="card center">
      <button type="button" id="enter" class="login-icon" aria-label="${esc(forTitle)}">${icon('lambda', 56)}</button>
      <h1>${esc(forTitle)}</h1>
      ${st.scope ? `<p class="muted scope">${esc(st.scope.label)}</p>` : ''}
      <form id="entry">
        <div class="field"><label for="user">User</label><input id="user" type="text" ${kb('username', 'go')} maxlength="254" required></div>
        <div class="row end"><button type="button" id="toSignIn">Sign in</button><button type="button" id="toSignUp">Sign up</button></div>
        <p id="err" class="error">${esc(said)}</p>
      </form></div>`;
    // the secret user's name is the login's own, a value in its database (0.14.1): asked of it, never written here;
    // anyone else (400), or any name on a domain's login (403), goes on to their password
    const enter = async () => {
      const name = $('user').value.trim();
      $('err').textContent = '';
      if (!name) { focusFirst($('user')); return; }
      try { await api('POST', 'api/sign-in/secret', { name }); render(); }
      catch (err) { if (err.status === 400 || err.status === 403) signInForm(st, name); else $('err').textContent = err.message; }
    };
    $('enter').addEventListener('click', enter);
    $('entry').addEventListener('submit', (e) => { e.preventDefault(); enter(); });
    $('toSignIn').addEventListener('click', () => signInForm(st, $('user').value.trim()));
    $('toSignUp').addEventListener('click', () => signUp(st));
    focusFirst($('user'));
  }

  function signInForm(st, name = '') {
    titled('sign in');
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('lambda', 56)}</div>
      <h1>Sign in to ${esc(forTitle)}</h1>
      ${st.scope ? `<p class="muted scope">${esc(st.scope.label)}</p>` : ''}
      <p class="muted">Your account name (or email) and password open your keys and accounts.</p>
      <form id="signin">
        <div class="field"><label for="name">Account name or email</label>
          <input id="name" type="text" ${kb('username', { inputmode: 'email' })} maxlength="254" required></div>
        <div class="field"><label for="password">Password</label>
          <input id="password" type="password" ${kb('password')} required minlength="8"></div>
        <div class="row end"><button type="button" id="back">Back</button><button type="submit" class="accent">Sign in</button></div>
        <p id="err" class="error"></p></form>
    </div>`;
    $('name').value = name;
    $('signin').addEventListener('submit', async (e) => {
      e.preventDefault();
      $('err').textContent = '';
      try { await api('POST', 'api/sign-in', { name: $('name').value, password: $('password').value }); $('password').value = ''; render(); }
      catch (err) { $('err').textContent = err.message; }
    });
    $('back').addEventListener('click', () => entryForm(st));
    focusFirst(name ? $('password') : $('name'));
  }

  // Sign up: a domain's login with an email server sends a code first; a local login (or a domain's first user while it
  // has no email server) makes the account here
  function signUp(st) {
    if (st.signup && st.signup.email) return emailForm(false);
    if (st.scope && st.scope.kind === 'domain' && st.users > 0) return entryForm(st, (st.signup && st.signup.why) || 'signing up needs an email server');
    return createForm(st);
  }

  function createForm(st) {
    // no code: a local login sends no email, a domain's has no email server yet
    const local = !st.scope || st.scope.kind !== 'domain';
    const first = st.users === 0;
    titled(first ? 'the first user' : 'sign up');
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('lambda', 56)}</div>
      <h1>${first ? 'Create the first user' : 'Sign up'}</h1>
      <p class="muted">${first ? `${esc(forTitle)} has no users yet: the first one is yours. ` : ''}The password unlocks your keys and accounts; it is never stored. (${local ? 'This login is local: it sends no email, so no code is needed.' : 'Email sending is not set up here, so no code is needed for the first user.'})</p>
      <form id="first">
        <div class="field"><label for="name">Account name</label><input id="name" type="text" ${kb('username')} maxlength="40" required></div>
        <div class="field"><label for="email">Email (optional)</label><input id="email" type="email" ${kb('email')} maxlength="254"></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" ${kb('password', NEW_NEXT)} required minlength="8"></div>
        <div class="field"><label for="again">Password, again</label><input id="again" type="password" ${kb('password', NEW_DONE)} required minlength="8"></div>
        <div class="row end"><button type="button" id="back">Back</button><button type="submit" class="accent">Create and sign in</button></div>
        <p id="err" class="error"></p>
      </form></div>`;
    $('first').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('name').value, password = $('password').value;
      $('err').textContent = '';
      try {
        if ($('again').value !== password) throw new Error('the two passwords differ');
        await api('POST', 'api/users', { name, password, email: $('email').value || null });
        await api('POST', 'api/sign-in', { name, password });
        render();
      } catch (err) { $('err').textContent = err.message; }
    });
    $('back').addEventListener('click', () => entryForm(st));
    focusFirst($('name'));
  }

  // step 1: the email
  function emailForm(first) {
    titled('sign up');
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('lambda', 56)}</div>
      <h1>Sign up</h1>
      <p class="muted">Your email first: a six-digit code goes to it ${mail.direct ? 'straight through its own mail server' : `through <b>${esc(mail.host || 'the mail account set here')}</b>`}${mail.sender ? ` as ${esc(mail.sender)}` : ''}. Then you choose your account name and password.</p>
      ${mail.lastSent ? `<p class="muted">The last code went out at ${esc(when(mail.lastSent.at))}: the server answered <span class="mono">${esc(mail.lastSent.code)} ${esc(mail.lastSent.reply)}</span>.</p>` : ''}
      <form id="email">
        <div class="field"><label for="address">Email</label><input id="address" type="email" ${kb('email', 'send')} maxlength="254" required></div>
        <div class="row end">${first ? '' : '<button type="button" id="back">Back</button>'}<button type="submit" class="accent">Send my code</button></div>
        <p id="err" class="error"></p>
      </form></div>`;
    $('email').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = $('address').value.trim();
      $('err').textContent = '';
      try { const out = await api('POST', 'api/signup', { email }); signup = { email, token: null, sent: out.sent }; render(); }
      catch (err) { $('err').textContent = err.message; }
    });
    if (!first) $('back').addEventListener('click', () => render());
    focusFirst($('address'));
  }

  // step 2: the code from the email
  function codeForm() {
    titled('sign up');
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('key', 56)}</div>
      <h1>Your code</h1>
      <p class="muted">A six-digit code went to <b>${esc(signup.email)}</b>. Type it here within 15 minutes (look in spam too).</p>
      ${signup.sent ? `<p class="muted receipt">${esc(signup.sent.host)} took the message at ${esc(when(signup.sent.at))} and answered <span class="mono">${esc(signup.sent.code)} ${esc(signup.sent.reply)}</span>${signup.sent.messageId ? `; message id <span class="mono">${esc(signup.sent.messageId)}</span>` : ''}.</p>` : ''}
      <form id="code">
        <div class="field"><label for="digits">Code</label><input id="digits" type="text" class="mono" ${kb('code')} placeholder="123456" maxlength="8" required></div>
        <div class="row end"><button type="button" id="resend">Send it again</button><button type="button" id="cancel">Start over</button><button type="submit" class="accent">Continue</button></div>
        <p id="err" class="error"></p><p id="note" class="muted"></p>
      </form></div>`;
    $('code').addEventListener('submit', async (e) => {
      e.preventDefault();
      $('err').textContent = '';
      try { const out = await api('POST', 'api/signup/verify', { email: signup.email, code: $('digits').value }); signup.token = out.token; render(); }
      catch (err) { $('err').textContent = err.message; if (/ask for a new one|start one first/.test(err.message)) { signup = null; } }
    });
    $('resend').addEventListener('click', async () => {
      $('err').textContent = ''; $('note').textContent = '';
      try {
        const out = await api('POST', 'api/signup/resend', { email: signup.email });
        signup.sent = out.sent;
        $('note').textContent = `A new code went out${out.sent ? ` (${out.sent.host} answered ${out.sent.code} ${out.sent.reply})` : ''}; the old one no longer counts.`;
      }
      catch (err) { $('err').textContent = err.message; }
    });
    $('cancel').addEventListener('click', () => { signup = null; render(); });
    focusFirst($('digits'));
  }

  // step 3: the account name and the password
  function detailsForm() {
    titled('sign up');
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('lambda', 56)}</div>
      <h1>Your account</h1>
      <p class="muted"><b>${esc(signup.email)}</b> is verified. Choose your account name and password; the password unlocks your keys and accounts and is never stored.</p>
      <form id="details">
        <div class="field"><label for="name">Account name</label><input id="name" type="text" ${kb('username')} maxlength="40" required></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" ${kb('password', NEW_NEXT)} required minlength="8"></div>
        <div class="field"><label for="again">Password, again</label><input id="again" type="password" ${kb('password', NEW_DONE)} required minlength="8"></div>
        <div class="row end"><button type="button" id="cancel">Start over</button><button type="submit" class="accent">Create my account</button></div>
        <p id="err" class="error"></p>
      </form></div>`;
    $('details').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('name').value, password = $('password').value;
      $('err').textContent = '';
      try {
        if ($('again').value !== password) throw new Error('the two passwords differ');
        await api('POST', 'api/signup/complete', { email: signup.email, token: signup.token, name, password });
        signup = null;
        render();
      } catch (err) { $('err').textContent = err.message; if (/start the sign-up again|start it again/.test(err.message)) signup = null; }
    });
    $('cancel').addEventListener('click', () => { signup = null; render(); });
    focusFirst($('name'));
  }

  // -- signed in ---------------------------------------------------------------------------------
  function userCard(me) {
    const s = me.store, kdf = s.kdf || {};
    return `<div class="user-head"><div class="avatar">${esc(me.name[0].toUpperCase())}</div>
        <div><h1>${esc(me.name)}</h1><div class="muted">${me.email ? `${esc(me.email)}${me.verified ? ' (verified)' : ' (not verified)'} · ` : ''}${esc(forTitle)}; signed in; this session ends after ${esc(me.session.minutes)} minutes without a request</div></div>
        <div class="row" style="margin-left:auto"><button type="button" id="signout" title="Sign out: your store closes">${icon('logout', 18)} Sign out</button></div></div>
      ${me.passwordless ? '<p class="muted note">The secret user: in without a password, so its keys are not protected by one.</p>' : ''}
      <h2>Your store</h2>
      <dl class="facts">
        <dt>Created</dt><dd>${esc(when(me.createdAt))}</dd>
        <dt>Last sign-in</dt><dd>${esc(when(me.seenAt))}</dd>
        <dt>Key-value database</dt><dd class="mono">${esc(s.file)} <span class="muted">(${esc(s.pairs)} ${s.pairs === 1 ? 'pair' : 'pairs'})</span></dd>
        <dt>Users file</dt><dd class="mono">${esc(s.usersFile)}</dd>
        <dt>Unlock key</dt><dd><span class="mono">${esc(s.unlockFingerprint)}</span> <span class="muted">the salted hash of your password (${esc(kdf.name)} n=${esc(kdf.n)} r=${esc(kdf.r)} p=${esc(kdf.p)}, salt ${esc(s.salt)}); never stored, derived at sign-in</span></dd>
        <dt>Vault key</dt><dd><span class="mono">${esc(s.vaultFingerprint)}</span> <span class="muted">masks every value (AES-256-GCM); kept wrapped under the unlock key</span></dd>
      </dl>`;
  }

  function pairsTable(pairs, known) {
    // the login knows no plugin of its own (0.13.0): the pairs a plugin asks for are listed only when an app inherits it
    // and says which (knownTable)
    if (!pairs.length) return `<h2>Your keys and accounts</h2><p class="muted">No pairs yet. Add one below: a pair is named after the variable it stands for, <code>some-api-key</code> for <code>SOME_API_KEY</code>${known.length ? `; the pairs the plugins of ${esc(forTitle)} ask for are listed below` : ''}.</p>`;
    const rows = pairs.map((p) => `<tr data-name="${esc(p.name)}">
        <td class="mono">${esc(p.name)}</td><td><span class="kind">${esc(p.kind)}</span></td><td>${esc(p.label)}</td>
        <td class="muted">${esc(when(p.updatedAt))}</td>
        <td class="value"><span class="masked">••••••••</span></td>
        <td class="tools"><span class="acts"><button type="button" class="reveal" title="Reveal the value here" aria-label="Reveal the value of ${esc(p.name)}">${icon('eye', 16)}</button>
          <button type="button" class="remove danger" title="Remove this pair" aria-label="Remove the pair ${esc(p.name)}">${icon('trash', 16)}</button></span>
          <span class="ask" hidden>Remove it? <button type="button" class="yes danger">Remove</button><button type="button" class="no">Keep</button></span></td></tr>`).join('');
    return `<h2>Your keys and accounts</h2><table class="list pairs"><thead><tr><th>Name</th><th>Kind</th><th>Label</th><th>Updated</th><th>Value</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function knownTable(known) {
    // the pairs the plugins of the app that inherits this login ask for, as that app said (named by their variables:
    // the user, 2026-11-06, "By the variables"), each set already or one click from the form below; none on its own
    if (!known.length) return '';
    const rows = known.map((k) => `<tr>
        <td>${esc(k.title || k.plugin)}</td><td class="mono">${esc(k.name)}</td><td>${esc(k.label)}</td>
        <td class="muted mono">${esc(k.variable)}</td>
        <td>${k.set ? '<span class="kind">set</span>' : `<button type="button" class="use" data-name="${esc(k.name)}" data-kind="${esc(k.kind)}" data-label="${esc(k.label)}" title="Fill the form below with this pair">Add</button>`}</td></tr>`).join('');
    return `<h2>Pairs the plugins of ${esc(forTitle)} ask for</h2><table class="list known"><thead><tr><th>Plugin</th><th>Name</th><th>For</th><th>Variable</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function addForm(known) {
    const options = known.filter((k) => !k.set).map((k) => `<option value="${esc(k.name)}">${esc(k.title || k.plugin)}: ${esc(k.label)}</option>`).join('');
    return `<form id="add" class="add-pair">
      <div class="field"><label for="pName">Name</label><input id="pName" type="text" list="knownNames" ${kb('plain', 'next')} placeholder="some-api-key" maxlength="64" required pattern="[a-z0-9][a-z0-9._\\-]*"><datalist id="knownNames">${options}</datalist></div>
      <div class="field"><label for="pKind">Kind</label><select id="pKind">${KINDS.map((k) => `<option value="${k}">${k}</option>`).join('')}</select></div>
      <div class="field"><label for="pLabel">Label</label><input id="pLabel" type="text" ${kb('text', 'next')} placeholder="what it is for" maxlength="80"></div>
      <div class="field"><label for="pValue">Value</label><input id="pValue" type="password" ${kb('secret')} maxlength="4096" required></div>
      <button type="submit" class="accent">Add</button>
      <p id="addErr" class="error" style="grid-column: 1 / -1"></p></form>`;
  }

  function changeForm() {
    return `<details class="change"><summary>Change your password</summary><form id="change">
      <div class="field"><label for="old">Current password</label><input id="old" type="password" ${kb('password', 'next')} required></div>
      <div class="field"><label for="new">New password</label><input id="new" type="password" ${kb('password', NEW_DONE)} required minlength="8"></div>
      <div class="row end"><button type="submit">Change</button></div><p id="chErr" class="error"></p></form></details>`;
  }

  function wire(me) {
    $('signout').addEventListener('click', async () => { await api('POST', 'api/sign-out'); tell(false); render(); });
    main.querySelectorAll('tr[data-name]').forEach((tr) => {
      const name = tr.dataset.name, cell = tr.querySelector('.value');
      tr.querySelector('.reveal').addEventListener('click', async () => {
        if (cell.dataset.shown) { cell.innerHTML = '<span class="masked">••••••••</span>'; delete cell.dataset.shown; return; }
        try { const p = await api('GET', `api/pairs/${encodeURIComponent(name)}`); cell.textContent = p.value; cell.dataset.shown = '1'; }
        catch (e) { cell.innerHTML = `<span class="error">${esc(e.message)}</span>`; }
      });
      // a pair removed once asked on the page itself, in its row (0.12.1: the browser's own confirmation box was the one
      // dialog the page did not draw, and a browser or a view that refuses those boxes never removed the pair); Keep or
      // Escape takes the question back
      const acts = tr.querySelector('.acts'), ask = tr.querySelector('.ask');
      const asking = (on) => { acts.hidden = on; ask.hidden = !on; focusFirst(on ? ask.querySelector('.no') : tr.querySelector('.remove')); };
      tr.querySelector('.remove').addEventListener('click', () => asking(true));
      ask.querySelector('.no').addEventListener('click', () => asking(false));
      ask.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); asking(false); } });
      ask.querySelector('.yes').addEventListener('click', async () => {
        try { await api('DELETE', `api/pairs/${encodeURIComponent(name)}`); render(); }
        catch (err) { asking(false); cell.innerHTML = `<span class="error">${esc(err.message)}</span>`; }
      });
    });
    main.querySelectorAll('button.use').forEach((b) => b.addEventListener('click', () => {
      $('pName').value = b.dataset.name; $('pKind').value = b.dataset.kind; $('pLabel').value = b.dataset.label;
      if (!focusFirst($('pValue'))) $('pValue').scrollIntoView({ block: 'nearest' });  // after a tap: in view, its keyboard up once it is tapped
    }));
    $('add').addEventListener('submit', async (e) => {
      e.preventDefault(); $('addErr').textContent = '';
      try {
        await api('PUT', `api/pairs/${encodeURIComponent($('pName').value.trim().toLowerCase())}`,
          { value: $('pValue').value, kind: $('pKind').value, label: $('pLabel').value });
        render();
      } catch (err) { $('addErr').textContent = err.message; }
    });
    $('change').addEventListener('submit', async (e) => {
      e.preventDefault(); $('chErr').textContent = '';
      try { await api('PUT', 'api/me/password', { old: $('old').value, new: $('new').value }); render(); }
      catch (err) { $('chErr').textContent = err.message; }
    });
  }

  // an on-screen keyboard's Next: the form's next field, the form not sent yet (Safari sends it otherwise; Chrome on
  // Android moves on by itself); the last field's Go, Send or Done sends it, and a hardware keyboard's Enter sends it
  // from any field, as before
  main.addEventListener('keydown', (e) => {
    const c = e.target;
    if (e.key !== 'Enter' || e.isComposing || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || !fingered()) return;
    if (!c.matches || !c.matches('form input') || c.getAttribute('enterkeyhint') !== 'next' || !c.form) return;
    const fields = [...c.form.elements].filter((x) => x.matches('input, select, textarea') && !x.disabled && x.type !== 'hidden' && x.offsetParent !== null);
    const next = fields[fields.indexOf(c) + 1];
    if (!next) return;
    e.preventDefault();
    next.focus({ preventScroll: true });  // touch.js brings it into view above the keyboard
  });

  render();
})();
