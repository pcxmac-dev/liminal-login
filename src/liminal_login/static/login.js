// The login app's page: signed out, the sign-in form and the way to an account (the user, 2026-11-06:
// "sign up lets you put in an email and sends an email to an email account, which you then enter the
// 4-6 digit code back in to the signup prompt to generate a new user, password, etcc"): the email,
// the code from the email, then the account name and the password; signed in, who you are, your
// store and the fingerprints of the keys that mask it, your pairs (masked; revealed one at a time),
// a form to add one, a password change, sign out. The API paths are relative, so the page works under
// another app's prefix too (the charts app's /login/); inside another app's page (?embedded=1) the
// rail is hidden and the parent page is told when you sign in or out.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const KINDS = ['key', 'account', 'password', 'detail'];
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const main = $('main');
  const embedded = new URLSearchParams(location.search).get('embedded') === '1';
  if (embedded) document.body.classList.add('embedded');
  $('railUser').innerHTML = icon('user', 30);
  let signup = null;  // a sign-up under way: { email, token }
  let forTitle = 'Liminal';
  let mail = {};  // how codes go out (the status's signup: the host, the sender, the last send's receipt)

  function tell(signedIn, name) {
    // the page holding this one (the charts app's) learns who is signed in
    if (embedded && window.parent !== window) window.parent.postMessage({ liminal: 'login', signedIn, name: name || null }, location.origin);
  }

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
    forTitle = st.forTitle || 'Liminal';
    mail = st.signup || {};
    document.title = `${forTitle}: sign in`;
    if (signup) return signup.token ? detailsForm() : codeForm();
    if (!st.signedIn) { tell(false); return signInForm(st); }
    const me = await api('GET', 'api/me');
    const pairs = (await api('GET', 'api/pairs')).pairs;
    const known = (await api('GET', 'api/pairs/known')).known;  // the pairs the plugins here ask for
    main.innerHTML = userCard(me) + pairsTable(pairs) + knownTable(known) + addForm(known) + changeForm();
    wire(me);
    tell(true, me.name);
  }

  // -- signed out: sign in, or sign up -----------------------------------------------------------
  function signInForm(st) {
    const first = st.users === 0;
    const mail = st.signup && st.signup.email;
    if (first && !mail) return firstUserForm();
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>${first ? `Welcome to ${esc(forTitle)}` : `Sign in to ${esc(forTitle)}`}</h1>
      ${st.scope ? `<p class="muted scope">${esc(st.scope.label)}</p>` : ''}
      <p class="muted">${first ? 'No account yet. Sign up: a code goes to your email, then you choose your account name and password.'
        : 'Your account name (or email) and password open your keys and accounts.'}</p>
      ${first ? '' : `<form id="signin">
        <div class="field"><label for="name">Account name or email</label>
          <input id="name" type="text" autocomplete="username" maxlength="254" required></div>
        <div class="field"><label for="password">Password</label>
          <input id="password" type="password" autocomplete="current-password" required minlength="8"></div>
        <div class="row end"><button type="submit" class="accent">Sign in</button></div>
        <p id="err" class="error"></p></form>`}
      <p class="muted">${mail ? `<button type="button" id="toSignup" class="${first ? 'accent' : ''}">Sign up</button>`
        : (st.scope && st.scope.kind === 'local'
          ? 'A local login: the first user is made here, more by a signed-in user or <code>liminal-login user add NAME</code>.'
          : `Signing up needs an email server for ${esc(st.scope ? st.scope.domain : 'the domain')}: none in its mail record and none named in liminal-login.cfg under [mail] (or <code>liminal-login user add NAME</code>).`)}</p>
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
    if (mail) $('toSignup').addEventListener('click', () => emailForm(first));
  }

  function firstUserForm() {
    // no mail account on this machine: the first user is made here, without a code
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>Create the first user</h1>
      <p class="muted">${esc(forTitle)} has no users yet: the first one is yours. The password unlocks your keys and accounts; it is never stored. (Email sending is not set up here, so no code is needed for the first user.)</p>
      <form id="first">
        <div class="field"><label for="name">Account name</label><input id="name" type="text" autocomplete="username" maxlength="40" required></div>
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

  // step 1: the email
  function emailForm(first) {
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>Sign up</h1>
      <p class="muted">Your email first: a six-digit code goes to it ${mail.direct ? 'straight through its own mail server' : `through <b>${esc(mail.host || 'the mail account set here')}</b>`}${mail.sender ? ` as ${esc(mail.sender)}` : ''}. Then you choose your account name and password.</p>
      ${mail.lastSent ? `<p class="muted">The last code went out at ${esc(when(mail.lastSent.at))}: the server answered <span class="mono">${esc(mail.lastSent.code)} ${esc(mail.lastSent.reply)}</span>.</p>` : ''}
      <form id="email">
        <div class="field"><label for="address">Email</label><input id="address" type="email" autocomplete="email" maxlength="254" required></div>
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
    $('address').focus();
  }

  // step 2: the code from the email
  function codeForm() {
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('key', 56)}</div>
      <h1>Your code</h1>
      <p class="muted">A six-digit code went to <b>${esc(signup.email)}</b>. Type it here within 15 minutes (look in spam too).</p>
      ${signup.sent ? `<p class="muted receipt">${esc(signup.sent.host)} took the message at ${esc(when(signup.sent.at))} and answered <span class="mono">${esc(signup.sent.code)} ${esc(signup.sent.reply)}</span>${signup.sent.messageId ? `; message id <span class="mono">${esc(signup.sent.messageId)}</span>` : ''}.</p>` : ''}
      <form id="code">
        <div class="field"><label for="digits">Code</label><input id="digits" type="text" class="mono" inputmode="numeric" autocomplete="one-time-code" placeholder="123456" maxlength="8" required></div>
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
    $('digits').focus();
  }

  // step 3: the account name and the password
  function detailsForm() {
    main.innerHTML = `<div class="card center">
      <div class="login-icon">${icon('user', 56)}</div>
      <h1>Your account</h1>
      <p class="muted"><b>${esc(signup.email)}</b> is verified. Choose your account name and password; the password unlocks your keys and accounts and is never stored.</p>
      <form id="details">
        <div class="field"><label for="name">Account name</label><input id="name" type="text" autocomplete="username" maxlength="40" required></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="new-password" required minlength="8"></div>
        <div class="field"><label for="again">Password, again</label><input id="again" type="password" autocomplete="new-password" required minlength="8"></div>
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
    $('name').focus();
  }

  // -- signed in ---------------------------------------------------------------------------------
  function userCard(me) {
    const s = me.store, kdf = s.kdf || {};
    return `<div class="user-head"><div class="avatar">${esc(me.name[0].toUpperCase())}</div>
        <div><h1>${esc(me.name)}</h1><div class="muted">${me.email ? `${esc(me.email)}${me.verified ? ' (verified)' : ' (not verified)'} · ` : ''}${esc(forTitle)}; signed in; this session ends after ${esc(me.session.minutes)} minutes without a request</div></div>
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
    if (!pairs.length) return `<h2>Your keys and accounts</h2><p class="muted">No pairs yet. Add one below: a pair is named by the plugin's variable, <code>massive-api-key</code> for <code>MASSIVE_API_KEY</code>; the plugins installed here list the pairs they ask for.</p>`;
    const rows = pairs.map((p) => `<tr data-name="${esc(p.name)}">
        <td class="mono">${esc(p.name)}</td><td><span class="kind">${esc(p.kind)}</span></td><td>${esc(p.label)}</td>
        <td class="muted">${esc(when(p.updatedAt))}</td>
        <td class="value"><span class="masked">••••••••</span></td>
        <td class="tools"><button type="button" class="reveal" title="Reveal the value here">${icon('eye', 16)}</button>
          <button type="button" class="remove danger" title="Remove this pair">${icon('trash', 16)}</button></td></tr>`).join('');
    return `<h2>Your keys and accounts</h2><table class="list pairs"><thead><tr><th>Name</th><th>Kind</th><th>Label</th><th>Updated</th><th>Value</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function knownTable(known) {
    // the pairs the plugins installed beside this app ask for (named by their variables: the user,
    // 2026-11-06, "By the variables"), each set already or one click from the form below
    if (!known.length) return '';
    const rows = known.map((k) => `<tr>
        <td>${esc(k.title || k.plugin)}</td><td class="mono">${esc(k.name)}</td><td>${esc(k.label)}</td>
        <td class="muted mono">${esc(k.variable)}</td>
        <td>${k.set ? '<span class="kind">set</span>' : `<button type="button" class="use" data-name="${esc(k.name)}" data-kind="${esc(k.kind)}" data-label="${esc(k.label)}" title="Fill the form below with this pair">Add</button>`}</td></tr>`).join('');
    return `<h2>Pairs your plugins ask for</h2><table class="list known"><thead><tr><th>Plugin</th><th>Name</th><th>For</th><th>Variable</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function addForm(known) {
    const options = known.filter((k) => !k.set).map((k) => `<option value="${esc(k.name)}">${esc(k.title || k.plugin)}: ${esc(k.label)}</option>`).join('');
    return `<form id="add" class="add-pair">
      <div class="field"><label for="pName">Name</label><input id="pName" type="text" list="knownNames" placeholder="massive-api-key" maxlength="64" required pattern="[a-z0-9][a-z0-9._-]*"><datalist id="knownNames">${options}</datalist></div>
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
    $('signout').addEventListener('click', async () => { await api('POST', 'api/sign-out'); tell(false); render(); });
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
    main.querySelectorAll('button.use').forEach((b) => b.addEventListener('click', () => {
      $('pName').value = b.dataset.name; $('pKind').value = b.dataset.kind; $('pLabel').value = b.dataset.label;
      $('pValue').focus();
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

  render();
})();
