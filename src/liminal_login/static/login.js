// The login app's page: signed out, the sign-in form (the first user is created here when there is
// none); signed in, who you are, your store and the fingerprints of the keys that mask it, your
// pairs (masked; revealed one at a time), a form to add one, a password change, sign out.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const KINDS = ['key', 'account', 'password', 'detail'];
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const main = $('main');
  $('railUser').innerHTML = icon('user', 30);

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
    try { st = await api('GET', '/api/status'); }
    catch (e) { main.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    if (!st.signedIn) return signInForm(st.users === 0);
    const me = await api('GET', '/api/me');
    const pairs = (await api('GET', '/api/pairs')).pairs;
    main.innerHTML = userCard(me) + pairsTable(pairs) + addForm() + changeForm();
    wire(me);
  }

  function signInForm(first) {
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>${first ? 'Create the first user' : 'Sign in'}</h1>
      <p class="muted">${first
        ? 'Liminal has no users yet: the first one is yours. The password unlocks your keys and accounts; it is never stored.'
        : 'Your name and password open your keys and accounts.'}</p>
      <form id="signin">
        <div class="field"><label for="name">Name</label>
          <input id="name" type="text" autocomplete="username" maxlength="40" required></div>
        <div class="field"><label for="password">Password</label>
          <input id="password" type="password" autocomplete="${first ? 'new-password' : 'current-password'}" required minlength="8"></div>
        ${first ? `<div class="field"><label for="again">Password, again</label>
          <input id="again" type="password" autocomplete="new-password" required minlength="8"></div>` : ''}
        <div class="row end"><button type="submit" class="accent">${first ? 'Create and sign in' : 'Sign in'}</button></div>
        <p id="err" class="error"></p>
      </form></div>`;
    $('signin').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('name').value, password = $('password').value;
      $('err').textContent = '';
      try {
        if (first) {
          if ($('again').value !== password) throw new Error('the two passwords differ');
          await api('POST', '/api/users', { name, password });
        }
        await api('POST', '/api/sign-in', { name, password });
        $('password').value = '';
        render();
      } catch (err) { $('err').textContent = err.message; }
    });
    $('name').focus();
  }

  function userCard(me) {
    const s = me.store, kdf = s.kdf || {};
    return `<div class="user-head"><div class="avatar">${esc(me.name[0].toUpperCase())}</div>
        <div><h1>${esc(me.name)}</h1><div class="muted">signed in; this session ends after ${esc(me.session.minutes)} minutes without a request</div></div>
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
    $('signout').addEventListener('click', async () => { await api('POST', '/api/sign-out'); render(); });
    main.querySelectorAll('tr[data-name]').forEach((tr) => {
      const name = tr.dataset.name, cell = tr.querySelector('.value');
      tr.querySelector('.reveal').addEventListener('click', async () => {
        if (cell.dataset.shown) { cell.innerHTML = '<span class="masked">••••••••</span>'; delete cell.dataset.shown; return; }
        try { const p = await api('GET', `/api/pairs/${encodeURIComponent(name)}`); cell.textContent = p.value; cell.dataset.shown = '1'; }
        catch (e) { cell.innerHTML = `<span class="error">${esc(e.message)}</span>`; }
      });
      tr.querySelector('.remove').addEventListener('click', async () => {
        if (!window.confirm(`Remove the pair ${name}?`)) return;
        await api('DELETE', `/api/pairs/${encodeURIComponent(name)}`); render();
      });
    });
    $('add').addEventListener('submit', async (e) => {
      e.preventDefault(); $('addErr').textContent = '';
      try {
        await api('PUT', `/api/pairs/${encodeURIComponent($('pName').value.trim().toLowerCase())}`,
          { value: $('pValue').value, kind: $('pKind').value, label: $('pLabel').value });
        render();
      } catch (err) { $('addErr').textContent = err.message; }
    });
    $('change').addEventListener('submit', async (e) => {
      e.preventDefault(); $('chErr').textContent = '';
      try { await api('PUT', '/api/me/password', { old: $('old').value, new: $('new').value }); render(); }
      catch (err) { $('chErr').textContent = err.message; }
    });
  }

  render();
})();
