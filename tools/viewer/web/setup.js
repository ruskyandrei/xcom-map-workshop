// The game install and the editor's checks (tools/viewer/gamesetup.py): on a first run, before anything else, the page
// asks which XCOM: Enemy Within install to read (with Long War Rebalance, or plain), offering the installs found in
// Steam's libraries, a folder typed in, or a Windows folder dialog; the Project menu's "Game install and checks"
// opens the same dialog later. Choosing an install saves the game setting; the server then lists that install's maps,
// and the page reloads.

async function call(method, url, body) {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(value.error || `The server said ${response.status}`), { status: response.status });
  return value;
}
export const setupApi = {
  status: (checks = true) => call('GET', checks ? '/setup.json' : '/setup.json?checks=0'),
  chooseGame: folder => call('POST', '/setup/game', { folder }),
  browse: () => call('POST', '/setup/browse', {}),
};

const STATUS = { ok: 'OK', warn: 'Warning', missing: 'Missing', wrong: 'Wrong' };

/**
 * els: the dialog's elements (root, form, title, intro, found, folder, browse, ok, close, checks, message, version).
 * onChosen(status): the game install was set (the page reloads).
 */
export function createSetupDialog({ els, onChosen }) {
  let first = false, lastFocus = null, busy = false;
  const element = (tag, className, textContent = '') => Object.assign(document.createElement(tag), { className, textContent });
  const say = (message, warn = false) => {
    els.message.textContent = message ?? ''; els.message.hidden = !message; els.message.classList.toggle('warn', warn);
  };
  function renderFound(status) {
    els.found.replaceChildren();
    if (!status.found.length) {
      els.found.append(element('div', 'empty', 'No install found in Steam\'s libraries: type its folder below, or Browse.'));
      return;
    }
    for (const install of status.found) {
      const row = element('button', 'setuprow');
      row.type = 'button';
      row.append(element('span', 'sname', install.folder), element('small', install.lab ? 'warn' : '', install.label));
      row.title = install.lab ? 'Our lab copy: the editor never reads it' : `Use ${install.folder}`;
      row.disabled = install.lab;
      row.classList.toggle('on', install.folder === els.folder.value);
      row.onclick = () => { els.folder.value = install.folder; els.found.querySelectorAll('.setuprow').forEach(r => r.classList.toggle('on', r === row)); };
      els.found.append(row);
    }
  }
  function renderChecks(checks) {
    els.checks.replaceChildren();
    if (!checks) { els.checks.append(element('div', 'empty', 'Checking…')); return; }
    for (const check of checks) {
      const row = element('div', `checkrow ${check.status}`);
      row.append(element('span', 'cstatus', STATUS[check.status] ?? check.status), element('span', 'cname', check.name),
                 element('span', 'cdetail', check.detail));
      if (check.fix) row.append(element('span', 'cfix', check.fix));
      els.checks.append(row);
    }
  }
  function render(status) {
    const game = status.game;
    els.title.textContent = first ? 'Welcome: choose your game install' : 'Game install and checks';
    els.intro.textContent = first
      ? 'The editor reads maps from XCOM: Enemy Within, with Long War Rebalance or plain. Choose the game folder (the one holding XEW); it is only read.'
      : game.folder ? `Reading ${game.folder} (${game.label}). Choose another install, or check what the editor needs.`
        : `No game install is set${game.setting ? ` (${game.note})` : ''}. Choose one.`;
    els.close.hidden = first;
    if (!els.folder.value) els.folder.value = game.folder ?? status.found.find(f => !f.lab)?.folder ?? '';
    renderFound(status);
    renderChecks(status.checks);
    if (els.version) els.version.textContent = `${status.name} ${status.version} · settings in ${status.settingsFile}`;
  }
  async function refresh() {
    try {
      render(await setupApi.status(false));
      const status = await setupApi.status(true);
      render(status);
    } catch (error) { say(`Could not read the settings: ${error.message}`, true); }
  }
  function show({ firstRun = false } = {}) {
    first = firstRun;
    lastFocus = document.activeElement;
    els.folder.value = '';
    say(null);
    renderChecks(null);
    els.root.hidden = false;
    refresh();
    setTimeout(() => els.folder.focus(), 0);
  }
  function hide() {
    if (first || busy) return;
    els.root.hidden = true;
    lastFocus?.focus?.();
  }
  els.close.onclick = hide;
  els.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); hide(); } });
  els.browse.onclick = async () => {
    els.browse.disabled = true;
    say('A folder dialog is open on this computer (it may be behind the browser).');
    try {
      const { folder } = await setupApi.browse();
      if (folder) els.folder.value = folder;
      say(null);
    } catch (error) { say(error.message, true); }
    finally { els.browse.disabled = false; }
  };
  els.form.onsubmit = async e => {
    e.preventDefault();
    const folder = els.folder.value.trim();
    if (!folder) { say('Choose the game folder first.', true); return; }
    busy = true; els.ok.disabled = true;
    say('Reading the install\'s maps…');
    try {
      const status = await setupApi.chooseGame(folder);
      say(`Set: ${status.game.folder} (${status.game.label}).`);
      onChosen(status);
    } catch (error) { say(error.message, true); }
    finally { busy = false; els.ok.disabled = false; }
  };
  return { show, get open() { return !els.root.hidden; } };
}
