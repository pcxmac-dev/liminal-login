// The login app's page: signed out, the sign-in form, and the way to an account (the user, 2026-11-05:
// "i need a way to create a user and send an email out ... in order to obtain a passkey to create the
// account"): a name, an email and a password, then the passkey from the email; signed in, who you
// are, your store and the fingerprints of the keys that mask it, your pairs (masked; revealed one at a
// time), a form to add one, a password change, sign out. The API paths are relative, so the page works
// under another app's prefix too (the charts app's /login/).
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const KINDS = ['key', 'account', 'password', 'detail'];
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const main = $('main');
  const embedded = new URLSearchParams(location.search).get('embedded') === '1';  // inside another app's page
  if (embedded) document.body.classList.add('embedded');
  $('railUser').innerHTML = icon('user', 30);
  let pending = null;  // a sign-up waiting for its passkey: { name, email, password }

  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE,
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    if (!r.ok) throw new Error((data && data.error) || `the login app answered ${r.status}`);
    return data;
  }
  const when = (iso) => (iso ? new Date(iso).toLocaleString() : 'never');

  async function render() {
    let st;
    try { st = await api('GET', 'api/status'); }
    catch (e) { main.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    if (pending) return passkeyForm(st);
    if (!st.signedIn) return signInForm(st);
    const me = await api('GET', 'api/me');
    const pairs = (await api('GET', 'api/pairs')).pairs;
    main.innerHTML = userCard(me) + pairsTable(pairs) + addForm() + changeForm();
    wire(me);
  }

  // -- signed out: sign in, or ask for an account ------------------------------------------------
  function signInForm(st) {
    const first = st.users === 0;
    const mail = st.signup && st.signup.email;
    if (first && !mail) return firstUserForm(st);
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>${first ? 'Welcome to Liminal' : 'Sign in'}</h1>
      <p class="muted">${first ? 'Liminal has no users yet. Create the first account: a passkey goes to your email.'
        : 'Your name (or email) and password open your keys and accounts.'}</p>
      ${first ? '' : `<form id="signin">
        <div class="field"><label for="name">Name or email</label>
          <input id="name" type="text" autocomplete="username" maxlength="254" required></div>
        <div class="field"><label for="password">Password</label>
          <input id="password" type="password" autocomplete="current-password" required minlength="8"></div>
        <div class="row end"><button type="submit" class="accent">Sign in</button></div>
        <p id="err" class="error"></p></form>`}
      <p class="muted">${mail ? `<button type="button" id="toSignup" class="${first ? 'accent' : ''}">Create an account</button>`
        : 'Creating an account needs email sending set up on this machine (LIMINAL_SMTP_HOST, _USER, _PASSWORD, _FROM), or <code>liminal-login user add NAME</code> at the command line.'}</p>
    </div>`;
    if (!first) {
      $('signin').addEventListener('submit', async (e) => {
        e.preventDefault();
        $('err').textContent = '';
        try { await api('POST', 'api/sign-in', { name: $('name').value, password: $('password').value }); $('password').value = ''; render(); }
        catch (err) { $('err').textContent = err.message; }
      });
      $('name').focus();
    }
    if (mail) $('toSignup').addEventListener('click', () => signupForm(st));
  }

  function firstUserForm(st) {
    // no mail account on this machine: the first user is made here, without a passkey
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>Create the first user</h1>
      <p class="muted">Liminal has no users yet: the first one is yours. The password unlocks your keys and accounts; it is never stored. (Email sending is not set up here, so no passkey is needed for the first user.)</p>
      <form id="first">
        <div class="field"><label for="name">Name</label><input id="name" type="text" autocomplete="username" maxlength="40" required></div>
        <div class="field"><label for="email">Email (optional)</label><input id="email" type="email" autocomplete="email" maxlength="254"></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="new-password" required minlength="8"></div>
        <div class="field"><label for="again">Password, again</label><input id="again" type="password" autocomplete="new-password" required minlength="8"></div>
        <div class="row end"><button type="submit" class="accent">Create and sign in</button></div>
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
    $('name').focus();
  }

  function signupForm(st) {
    const first = st.users === 0;
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>${first ? 'Create the first account' : 'Create an account'}</h1>
      <p class="muted">A passkey goes to your email from ${esc(st.signup.sender || 'the login app')}; type it on the next step. The password unlocks your keys and accounts and is never stored.</p>
      <form id="signup">
        <div class="field"><label for="name">Name</label><input id="name" type="text" autocomplete="username" maxlength="40" required></div>
        <div class="field"><label for="email">Email</label><input id="email" type="email" autocomplete="email" maxlength="254" required></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="new-password" required minlength="8"></div>
        <div class="field"><label for="again">Password, again</label><input id="again" type="password" autocomplete="new-password" required minlength="8"></div>
        <div class="row end">${first ? '' : '<button type="button" id="back">Back</button>'}<button type="submit" class="accent">Send my passkey</button></div>
        <p id="err" class="error"></p>
      </form></div>`;
    $('signup').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('name').value, email = $('email').value, password = $('password').value;
      $('err').textContent = '';
      try {
        if ($('again').value !== password) throw new Error('the two passwords differ');
        await api('POST', 'api/signup', { name, email, password });
        pending = { name, email, password };
        render();
      } catch (err) { $('err').textContent = err.message; }
    });
    if (!first) $('back').addEventListener('click', () => render());
    $('name').focus();
  }

  function passkeyForm() {
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('key', 56)}</div>
      <h1>Your passkey</h1>
      <p class="muted">A passkey went to <b>${esc(pending.email)}</b> for the account <b>${esc(pending.name)}</b>. Type it here within 15 minutes.</p>
      <form id="confirm">
        <div class="field"><label for="code">Passkey</label><input id="code" type="text" class="mono" autocomplete="one-time-code" placeholder="XXXX-XXXX" maxlength="9" required></div>
        <div class="row end"><button type="button" id="resend">Send it again</button><button type="button" id="cancel">Start over</button><button type="submit" class="accent">Create my account</button></div>
        <p id="err" class="error"></p><p id="note" class="muted"></p>
      </form></div>`;
    $('confirm').addEventListener('submit', async (e) => {
      e.preventDefault();
      $('err').textContent = '';
      try {
        await api('POST', 'api/signup/confirm', { email: pending.email, code: $('code').value, password: pending.password });
        pending = null;
        render();
      } catch (err) { $('err').textContent = err.message; if (/ask for a new one|ask for one first/.test(err.message)) pending = null; }
    });
    $('resend').addEventListener('click', async () => {
      $('err').textContent = ''; $('note').textContent = '';
      try { await api('POST', 'api/signup/resend', { email: pending.email }); $('note').textContent = 'A new passkey went out; the old one no longer counts.'; }
      catch (err) { $('err').textContent = err.message; }
    });
    $('cancel').addEventListener('click', () => { pending = null; render(); });
    $('code').focus();
  }

  // -- signed in ---------------------------------------------------------------------------------
  function userCard(me) {
    const s = me.store, kdf = s.kdf || {};
    return `<div class="user-head"><div class="avatar">${esc(me.name[0].toUpperCase())}</div>
        <div><h1>${esc(me.name)}</h1><div class="muted">${me.email ? `${esc(me.email)}${me.verified ? ' (verified)' : ' (not verified)'} · ` : ''}signed in; this session ends after ${esc(me.session.minutes)} minutes without a request</div></div>
        <div class="row" style="margin-left:auto"><button type="button" id="signout" title="Sign out: your store closes">${icon('logout', 18)} Sign out</button></div></div>
      <h2>Your store</h2>
      <dl class="facts">
        <dt>Created</dt><dd>${esc(when(me.createdAt))}</dd>
        <dt>Last sign-in</dt><dd>${esc(when(me.seenAt))}</dd>
        <dt>Key-value database</dt><dd class="mono">${esc(s.file)} <span class="muted">(${esc(s.pairs)} pairs)</span></dd>
        <dt>Users file</dt><dd class="mono">${esc(s.usersFile)}</dd>
        <dt>Unlock key</dt><dd><span class="mono">${esc(s.unlockFingerprint)}</span> <span class="muted">the salted hash of your password (${esc(kdf.name)} n=${esc(kdf.n)} r=${esc(kdf.r)} p=${esc(kdf.p)}, salt ${esc(s.salt)}); never stored, derived at sign-in</span></dd>
        <dt>Vault key</dt><dd><span class="mono">${esc(s.vaultFingerprint)}</span> <span class="muted">masks every value (AES-256-GCM); kept wrapped under the unlock key</span></dd>
      </dl>`;
  }

  function pairsTable(pairs) {
    if (!pairs.length) return `<h2>Your keys and accounts</h2><p class="muted">No pairs yet. Add one below: a plugin's API key is named <code>&lt;plugin&gt;-account-api-key</code>, its account name <code>&lt;plugin&gt;-account-name</code>.</p>`;
    const rows = pairs.map((p) => `<tr data-name="${esc(p.name)}">
        <td class="mono">${esc(p.name)}</td><td><span class="kind">${esc(p.kind)}</span></td><td>${esc(p.label)}</td>
        <td class="muted">${esc(when(p.updatedAt))}</td>
        <td class="value"><span class="masked">••••••••</span></td>
        <td class="tools"><button type="button" class="reveal" title="Reveal the value here">${icon('eye', 16)}</button>
          <button type="button" class="remove danger" title="Remove this pair">${icon('trash', 16)}</button></td></tr>`).join('');
    return `<h2>Your keys and accounts</h2><table class="list pairs"><thead><tr><th>Name</th><th>Kind</th><th>Label</th><th>Updated</th><th>Value</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function addForm() {
    return `<form id="add" class="add-pair">
      <div class="field"><label for="pName">Name</label><input id="pName" type="text" placeholder="massive-account-api-key" maxlength="64" required pattern="[a-z0-9][a-z0-9._-]*"></div>
      <div class="field"><label for="pKind">Kind</label><select id="pKind">${KINDS.map((k) => `<option value="${k}">${k}</option>`).join('')}</select></div>
      <div class="field"><label for="pLabel">Label</label><input id="pLabel" type="text" placeholder="Massive, the paid plan" maxlength="80"></div>
      <div class="field"><label for="pValue">Value</label><input id="pValue" type="password" autocomplete="off" maxlength="4096" required></div>
      <button type="submit" class="accent">Add</button>
      <p id="addErr" class="error" style="grid-column: 1 / -1"></p></form>`;
  }

  function changeForm() {
    return `<details class="change"><summary>Change your password</summary><form id="change">
      <div class="field"><label for="old">Current password</label><input id="old" type="password" autocomplete="current-password" required></div>
      <div class="field"><label for="new">New password</label><input id="new" type="password" autocomplete="new-password" required minlength="8"></div>
      <div class="row end"><button type="submit">Change</button></div><p id="chErr" class="error"></p></form></details>`;
  }

  function wire(me) {
    $('signout').addEventListener('click', async () => { await api('POST', 'api/sign-out'); render(); });
    main.querySelectorAll('tr[data-name]').forEach((tr) => {
      const name = tr.dataset.name, cell = tr.querySelector('.value');
      tr.querySelector('.reveal').addEventListener('click', async () => {
        if (cell.dataset.shown) { cell.innerHTML = '<span class="masked">••••••••</span>'; delete cell.dataset.shown; return; }
        try { const p = await api('GET', `api/pairs/${encodeURIComponent(name)}`); cell.textContent = p.value; cell.dataset.shown = '1'; }
        catch (e) { cell.innerHTML = `<span class="error">${esc(e.message)}</span>`; }
      });
      tr.querySelector('.remove').addEventListener('click', async () => {
        if (!window.confirm(`Remove the pair ${name}?`)) return;
        await api('DELETE', `api/pairs/${encodeURIComponent(name)}`); render();
      });
    });
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

  render();
})();
