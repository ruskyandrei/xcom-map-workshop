// The project manager (Project menu, Manage projects; tools/viewer/manager.py): every project with its last build
// and what is in the game of it, on the left; the selected projects and what to do with them, on the right.
// The list filters by text and by state (the chips, with their counts), and rows are ticked one by one, by a
// Shift+click range, or all that the filter shows. Each selected project with a build says on the right how it goes
// into the game or a pack: additional (beside its base map in the rotation) or replace (in its place), Additional to
// begin with, or the way it is in the game now. So one install or one pack can hold maps that replace their originals
// beside maps that are added. Install in the game puts the selected projects' last builds into the game for
// campaigns; Export map pack zips them into one map pack, with their editor project files when ticked. Taking them out
// again is the Game maps window's (gamemaps.js). Warnings (a quick build, a build older than the project, missions
// other than abductions) are said under each selected project and never stop anything.
// Build puts the ticked projects in the build queue (build_queue.js, tools/viewer/buildqueue.py): full builds, one
// after another on the server, each of the project as saved when its turn comes. The rows say where each is in the
// queue, and a strip above the footer follows the whole queue with its buttons (Stop, Resume, Clear). The manager can
// be closed meanwhile: the queue goes on, and the editor's chip follows it.
import { savedWhen } from './project_files.js';
import { clock, needsFullBuild, requestOrder, rowLine, stripWords } from './build_queue.js';
import { nextStop, tabOrder } from './modal.js';

async function call(method, url, body) {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(value.error || `The server said ${response.status}`), { status: response.status });
  return value;
}
export const managerApi = {
  list: () => call('GET', '/manager.json'),
  install: (projects, mode, modes) => call('POST', '/manager/install', { projects, mode, modes }),
  // pack: a saved pack's folder (exported again as its next version); name: a new pack's name
  pack: (projects, mode, modes, name, projectFiles = false, pack = undefined, author = undefined) =>
    call('POST', '/manager/pack', { projects, mode, modes, name, projectFiles, pack, author }),
  packs: () => call('GET', '/manager/packs.json'),
  forgetPack: folder => call('DELETE', `/manager/packs/${encodeURIComponent(folder)}`),
};

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const byName = (a, b) => (a.name ?? '').localeCompare(b.name ?? '', undefined, { sensitivity: 'base' });
const lighting = b => b.quick ? 'not baked' : b.lightingUnchanged ? 'baked (lighting unchanged)' : 'baked';
// whose picture the map shows on the game's mission screens (pictures.py status)
const PICTURE_WORDS = { own: 'own picture', base: 'base map\'s picture', none: 'no picture' };
const inGameText = g => !g ? '' : [g.rotation === 'replace' ? 'Replaces the map' : g.rotation === 'additional' ? 'In rotation' : null,
                                   g.play && !g.rotation ? 'For Play in game' : null].filter(Boolean).join(', ') + (g.current ? '' : ' (an older build)');
const MODE_TITLES = {
  additional: 'Additional: its records go into the rotation beside its base map\'s, so missions draw from both',
  replace: 'Replace: as well, its base map\'s own records are commented out, so the game no longer uses the original: missions draw this map where they drew it, and a council mission that asks for the original by name gets this map',
};
const FILES_KEY = 'xcom-map-workshop.manager.projectFiles';
const remembered = () => { try { return localStorage.getItem(FILES_KEY) === '1'; } catch { return false; } };
const remember = on => { try { localStorage.setItem(FILES_KEY, on ? '1' : '0'); } catch { /* not kept: the box still works */ } };
const SORTS = {
  name: byName,
  map: (a, b) => (a.mapLabel ?? '').localeCompare(b.mapLabel ?? '') || byName(a, b),
  savedAt: (a, b) => (a.savedAt ?? '').localeCompare(b.savedAt ?? '') || byName(a, b),
  build: (a, b) => (a.build?.builtAt ?? '').localeCompare(b.build?.builtAt ?? '') || byName(a, b),
};
// the newest first for the dates, A to Z for the names
const DOWN = { savedAt: true, build: true, name: false, map: false };
const SHOWS = {
  all: () => true,
  ready: p => Boolean(p.build) && !p.build.quick && !p.build.stale,
  // not built, not baked, of an older revision, or by another editor version (build_queue.js needsFullBuild)
  needsfull: (p, version) => needsFullBuild(p, version),
  ingame: p => Boolean(p.inGame),
};

// A build's state in one word, with a note: { text, kind (ok, warn, none), note, noteWarn, title }.
export function buildStatus(p, editorVersion) {
  const b = p.build;
  if (!b) return { text: 'Not built', kind: 'none', note: '', title: 'Never built: Build makes a full build of it' };
  const older = Boolean(editorVersion && b.editorVersion && b.editorVersion !== editorVersion);
  const note = b.stale ? `rev. ${b.revision} of ${p.revision}` : older ? `v${b.editorVersion}` : `rev. ${b.revision}`;
  const title = [`Built ${savedWhen(b.builtAt)} from revision ${b.revision}${b.stale ? ` (the project is at revision ${p.revision})` : ''}`,
    `lighting ${lighting(b)}`, b.editorVersion ? `by the editor ${b.editorVersion}` : null].filter(Boolean).join(' · ') + `\n${b.buildId}\n${b.folder}`;
  if (b.quick) return { text: 'Not baked', kind: 'warn', note, noteWarn: b.stale || older, title: `A quick build: pathing, cover and line of sight are right, the lighting is not.\n${title}` };
  if (b.stale) return { text: 'Out of date', kind: 'warn', note, noteWarn: true, title: `The project was saved again after this build.\n${title}` };
  return { text: 'Ready', kind: 'ok', note, noteWarn: older, title };
}

/**
 * els: the dialog's elements (root, form, close, search, show (the chips' group), sort, all, shownLabel, list, count,
 * pickNone, allModes, picked (the selected projects' list), message, pack, projectFiles, install, where).
 * mapLabel(id): a map's display name. onOpen(summary): open that project. reveal(path): show a file in Explorer.
 * onChanged(): the game install's contents changed (the Game menu's Installs section follows).
 * queue: the page's build queue controller (build_queue.js createQueueController), or none; its elements: build,
 * queueBox, queueTitle, queueClock, queueStep, queueStage, queueBar, queueNote, queueFailures, queueLive, queueStop,
 * queueResume, queueClear, queueReset. ensureSaved(ids): saves the open project first when it is among `ids` and has
 * unsaved changes (true when Build may go on).
 */
export function createProjectManager({ els, api = managerApi, mapLabel, onOpen, reveal, onChanged, queue = null, ensureSaved = null }) {
  let listed = null, projects = [], picked = new Set(), showing = 'all', anchor = null, busy = false;
  let lastFocus = null, queueBusy = false, ticker = null, lastLive = '';
  // a project's way, where one was chosen here; else the way it is in the game now, else additional
  const own = new Map();
  const modeOf = p => own.get(p.id) ?? (p.inGame?.rotation || 'additional');
  const sortKey = () => (SORTS[els.sort.value] ? els.sort.value : 'savedAt');
  const sorter = (a, b) => (DOWN[sortKey()] ? -1 : 1) * SORTS[sortKey()](a, b);
  const words = () => els.search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const shown = () => {
    const w = words(), keep = SHOWS[showing] ?? SHOWS.all;
    // a row with a result in the queue stays shown, though the filter would hide it now it is built
    return projects.filter(p => (keep(p, listed?.editorVersion) || (showing !== 'all' && queued(p)))
      && w.every(x => p.haystack.includes(x))).sort(sorter);
  };
  const queueItem = p => queue?.state?.items?.find(i => i.project === p.id) ?? null;
  const queued = p => Boolean(queueItem(p)) && !['idle', 'unavailable'].includes(queue?.state?.state);
  const chosen = () => projects.filter(p => picked.has(p.id)).sort(sorter);
  const warningsOf = p => [...(p.warnings ?? []), ...(p.modeWarnings?.[modeOf(p)] ?? [])];
  els.projectFiles.checked = remembered();
  // The saved packs (packs.py): choosing one selects its maps, each its way, and the export goes out as its next
  // version under the same folder and card number. "New pack" takes a name.
  let packs = [];
  const packOf = () => packs.find(p => p.folder === els.packChoice?.value) ?? null;
  function renderPacks(keep = els.packChoice?.value ?? '') {
    if (!els.packChoice) return;
    els.packChoice.replaceChildren(el('option', { value: '', textContent: 'New pack' }),
      ...packs.map(p => el('option', { value: p.folder, textContent: `${p.name}${p.source === 'zip' ? ' (from its zip)' : ''}` })));
    els.packChoice.value = packs.some(p => p.folder === keep) ? keep : '';
    packInfo();
  }
  function packInfo() {
    if (!els.packChoice) return;
    const p = packOf();
    els.packNameRow.hidden = Boolean(p);
    els.packForget.hidden = !p || p.source !== 'record';
    els.packInfo.hidden = !p;
    if (!p) return;
    const gone = p.maps.filter(m => m.missing).map(m => m.name ?? m.variant ?? m.project);
    const lines = [el('div', { textContent: `${p.card == null ? 'Its card number is drawn at the export' : `Card ${String(p.card).padStart(4, '0')}`} · folder ${p.folder} · the export is version ${(p.version ?? 0) + 1}` })];
    if (gone.length) lines.push(el('div', { className: 'warn', textContent: `Not in the projects folder, left out: ${gone.join(', ')}` }));
    els.packInfo.replaceChildren(...lines);
  }
  async function loadPacks(keep) {
    if (!els.packChoice || !api.packs) return;
    try { packs = (await api.packs()).packs ?? []; } catch { packs = []; }
    renderPacks(keep);
  }
  if (els.packChoice) {
    els.packChoice.onchange = () => {
      const p = packOf();
      if (p) {
        // its maps ticked, each its way; a map whose project is gone is named and left out
        picked = new Set(p.maps.filter(m => !m.missing && projects.some(x => x.id === m.project && !x.error)).map(m => m.project));
        for (const m of p.maps) if (m.mode === 'replace' || m.mode === 'additional') own.set(m.project, m.mode);
        els.projectFiles.checked = Boolean(p.projectFiles);
        els.packAuthor.value = p.author ?? '';
        anchor = null;
        render();
      }
      packInfo();
    };
    els.packForget.onclick = async () => {
      const p = packOf();
      if (!p || busy) return;
      try { packs = (await api.forgetPack(p.folder)).packs ?? []; renderPacks(''); say(`${p.name} is forgotten; its zips stay in the Map packs folder.`); }
      catch (e) { say(e.message, true); }
    };
  }

  function say(content, warn = false) {
    els.message.replaceChildren(...(content == null ? [] : [].concat(content)));
    els.message.hidden = content == null; els.message.classList.toggle('warn', warn);
  }
  // The row's place in the build queue, above its last build's state (a failed attempt hides no usable last build).
  function queueLine(p, cell) {
    const item = queued(p) ? queueItem(p) : null, line = item ? rowLine(item, queue.state) : null;
    if (!line) return null;
    cell.classList.add('queued');
    const head = el('span', { className: `mqline ${line.kind}`, title: line.title });
    head.append(line.text);
    if (item.state === 'waiting' && queue.state.actions?.remove) {
      const remove = el('button', { type: 'button', className: 'link mqremove', textContent: 'Remove', title: `Take ${p.name ?? 'it'} out of the queue (it is not built)` });
      remove.setAttribute('aria-label', `Take ${p.name ?? p.id} out of the build queue`);
      remove.onclick = e => { e.stopPropagation(); removeFromQueue(item); };
      remove.ondblclick = e => e.stopPropagation();
      remove.onkeydown = e => { if (e.key === ' ' || e.key === 'Enter') e.stopPropagation(); };
      head.append(remove);
    }
    cell.append(head);
    if (line.progress != null) {
      const bar = el('span', { className: 'mqrowbar' }, el('span'));
      bar.firstChild.style.width = `${(100 * line.progress).toFixed(1)}%`;
      cell.append(bar);
    }
    return line;
  }
  function buildCell(p) {
    const cell = el('span', { className: 'mbuild' });
    const line = queueLine(p, cell);
    const rest = line ? el('span', { className: 'mqrest' }) : cell;
    if (line) cell.append(rest);
    cell.dataset.sig = JSON.stringify([line, p.build?.buildId, p.building, queue?.state?.actions?.remove]);
    if (p.building && !line) { cell.append(el('span', { className: 'pmstate', textContent: 'Building…' })); return cell; }
    if (!p.build && line) return cell;
    const s = buildStatus(p, listed?.editorVersion);
    if (s.note) rest.append(el('small', { className: s.noteWarn ? 'warn' : '', textContent: s.note }));
    rest.append(el('span', { className: `pmstate ${s.kind}`, textContent: s.text }));
    rest.title = s.title;
    return cell;
  }
  // A new answer from the queue: only the cells that changed are drawn again (focus, scroll and the rest stay).
  function refreshCells() {
    for (const row of els.list.querySelectorAll('.mrow[data-id]')) {
      const p = projects.find(x => x.id === row.dataset.id), old = row.querySelector('.mbuild');
      if (!p || p.error || !old) continue;
      const fresh = buildCell(p);
      if (fresh.dataset.sig !== old.dataset.sig) old.replaceWith(fresh);
    }
  }
  // The strip above the footer: the whole queue, its time, its bar (rows processed of all), its buttons; one line
  // once every project in it is built.
  function renderStrip() {
    const q = queue?.state, words = stripWords(q);
    els.queueBox.hidden = !words;
    if (!words) { els.queueLive.textContent = ''; lastLive = ''; return; }
    const active = q.state === 'running' || q.state === 'stopping';
    els.queueBox.classList.toggle('done', q.state === 'finished' && !words.failures.length && !q.fault && !q.notice);
    els.queueTitle.textContent = words.title;
    els.queueClock.textContent = active ? clock(queue.activeSeconds()) : q.activeSeconds ? `${clock(q.activeSeconds)} in all` : '';
    els.queueStep.textContent = words.step ?? '';
    els.queueStep.hidden = !words.step;
    els.queueStage.hidden = words.stage == null;
    els.queueStage.firstElementChild.style.width = `${(100 * (words.stage ?? 0)).toFixed(1)}%`;
    els.queueBar.firstElementChild.style.width = `${(100 * words.progress).toFixed(1)}%`;
    els.queueBar.classList.toggle('done', q.state === 'finished');
    els.queueNote.textContent = words.note;
    els.queueFailures.replaceChildren(...words.failures.map(text => el('li', { textContent: text })));
    els.queueFailures.hidden = !words.failures.length;
    const a = q.actions ?? {};
    els.queueStop.hidden = !(a.stop || q.state === 'stopping');
    els.queueStop.disabled = queueBusy || q.state === 'stopping';
    els.queueStop.textContent = q.state === 'stopping' ? 'Stopping…' : 'Stop';
    els.queueResume.hidden = q.state !== 'stopped';
    els.queueResume.disabled = queueBusy || !a.resume;
    els.queueResume.title = a.resume ? 'Build the waiting projects, from the first, each as it is saved now'
      : q.recovering ? 'Not yet: the builds from before the restart are still being checked'
      : q.contextChanged ? 'Not possible: the settings changed since the queue started; clear it and queue again' : 'Nothing is waiting';
    els.queueClear.hidden = !a.clear;
    els.queueClear.disabled = queueBusy;
    els.queueReset.hidden = !a.reset;
    els.queueReset.disabled = queueBusy;
    // said to a screen reader when the queue's state or count changes, not every tick
    const live = `${q.state} ${q.counts?.processed ?? ''}`;
    if (live !== lastLive) { lastLive = live; els.queueLive.textContent = words.title; }
  }
  async function queueAct(what, action, fields) {
    if (queueBusy || !queue) return null;
    queueBusy = true; update(); renderStrip();
    try { return await queue.send(action, fields); }
    catch (e) { say(`${what}: ${e.message}`, true); return null; }
    finally { queueBusy = false; update(); renderStrip(); }
  }
  const removeFromQueue = item => queueAct('Not removed', 'remove', { items: [item.itemId] });
  function render() {
    const list = shown();
    els.list.replaceChildren();
    for (const p of list) {
      const box = el('input', { type: 'checkbox', checked: picked.has(p.id), disabled: Boolean(p.error), tabIndex: -1 });
      box.setAttribute('aria-label', `Select ${p.name ?? p.id}`);
      const title = el('span', { className: 'pmtitle' }, el('span', { className: 'fname', textContent: p.error ? p.id : (p.name ?? p.id) }));
      if (p.inGame) title.append(el('small', { className: `pmgame${p.inGame.current ? '' : ' warn'}`, textContent: inGameText(p.inGame),
        title: `In ${listed?.install?.folder ?? 'the game'}${p.inGame.current ? '' : ': an older build than the last one'}` }));
      const meta = el('small', { className: 'pmmeta', textContent: p.error ? 'Unreadable' : `${p.mapLabel} · saved ${savedWhen(p.savedAt)}${PICTURE_WORDS[p.picture] ? ` · ${PICTURE_WORDS[p.picture]}` : ''}`,
        title: p.error ? '' : `${p.map} · revision ${p.revision}${p.missions?.length ? ` · ${p.missions.map(m => m.label + (m.inRotation ? '' : ' (out of rotation)')).join(', ')}` : ''}` });
      const row = el('div', { className: 'mrow', tabIndex: p.error ? -1 : 0 }, box, el('span', { className: 'pmname' }, title, meta),
        p.error ? el('span') : buildCell(p));
      row.dataset.id = p.id; row.setAttribute('role', 'option'); row.setAttribute('aria-selected', picked.has(p.id));
      row.classList.toggle('on', picked.has(p.id)); row.classList.toggle('off', Boolean(p.error));
      if (p.error) row.title = `${p.file ?? p.id}: ${p.error}`;
      else {
        row.onclick = e => { if (e.detail > 1) return; toggle(p.id, e.shiftKey, list); };
        row.ondblclick = () => { close(); onOpen(p); };
        row.onkeydown = e => { if (e.key === ' ') { e.preventDefault(); toggle(p.id, e.shiftKey, list); } };
      }
      els.list.append(row);
    }
    if (!list.length) {
      els.list.append(el('div', { className: 'empty', textContent: !projects.length ? (listed ? 'No projects yet: save one from the Project menu.' : '')
        : 'No project matches. Clear the filter to see them all.' }));
    }
    renderPicked();
    update();
  }
  // The selected projects on the right, in the list's order: how each goes into the game or a pack, and its warnings.
  function renderPicked() {
    const all = chosen();
    els.picked.replaceChildren();
    if (!all.length) {
      els.picked.append(el('li', { className: 'pmhint', textContent: 'Select projects on the left to build them, install them in the game or export them as a map pack. Shift+click selects a run of them, Ctrl+A all shown; a double-click opens one.' }));
    }
    for (const p of all) {
      const drop = el('button', { type: 'button', className: 'icon pmdrop', textContent: '×', title: 'Take it out of the selection' });
      drop.setAttribute('aria-label', `Take ${p.name ?? p.id} out of the selection`);
      drop.onclick = () => { picked.delete(p.id); redraw(); };
      const item = el('li', { className: 'pmitem' }, el('div', { className: 'pmitemhead' }, el('span', { className: 'fname', textContent: p.name ?? p.id, title: `${p.mapLabel}` }), drop));
      if (p.build && !p.building) {
        const seg = el('div', { className: 'pmseg', role: 'radiogroup' });
        seg.setAttribute('aria-label', `How ${p.name ?? p.id} goes into the game`);
        for (const [value, label] of [['additional', 'Additional'], ['replace', 'Replace']]) {
          const on = modeOf(p) === value;
          const button = el('button', { type: 'button', textContent: label, title: MODE_TITLES[value], className: on ? 'on' : '' });
          button.setAttribute('role', 'radio'); button.setAttribute('aria-checked', on);
          button.onclick = () => { own.set(p.id, value); renderPicked(); update(); };
          seg.append(button);
        }
        item.append(seg);
      } else {
        item.append(el('div', { className: 'pmnote', textContent: p.building ? 'Building: Install and Export can use it once it is built.'
          : 'Not built: Install and Export leave it out. Build builds it.' }));
      }
      const warned = p.build ? warningsOf(p) : [];
      if (warned.length) item.append(el('ul', { className: 'pmwarn' }, ...warned.map(text => el('li', { textContent: text }))));
      els.picked.append(item);
    }
    const built = all.filter(p => p.build && !p.building);
    els.allModes.hidden = built.length < 2;
  }
  // A click ticks or unticks a row; Shift+click does the same for every shown row from the last one clicked.
  function toggle(id, range, list) {
    const on = !picked.has(id);
    const ids = list.filter(p => !p.error).map(p => p.id);
    const from = range && anchor ? ids.indexOf(anchor) : -1, to = ids.indexOf(id);
    for (const each of from < 0 ? [id] : ids.slice(Math.min(from, to), Math.max(from, to) + 1)) on ? picked.add(each) : picked.delete(each);
    anchor = id;
    const at = els.list.scrollTop;
    render();
    els.list.scrollTop = at;
    els.list.querySelector(`[data-id="${id}"]`)?.focus({ preventScroll: true });
  }
  function update() {
    const list = shown().filter(p => !p.error), all = chosen(), ticked = list.filter(p => picked.has(p.id)).length;
    els.all.checked = list.length > 0 && ticked === list.length;
    els.all.indeterminate = ticked > 0 && ticked < list.length;
    els.all.disabled = !list.length;
    els.shownLabel.textContent = list.length === projects.length ? `Select all ${list.length}` : `Select all ${list.length} shown`;
    for (const chip of els.show.querySelectorAll('[data-show]')) {
      const on = chip.dataset.show === showing;
      chip.classList.toggle('on', on); chip.setAttribute('aria-checked', on);
      chip.querySelector('span').textContent = projects.filter(p => !p.error && SHOWS[chip.dataset.show](p, listed?.editorVersion)).length;
    }
    const hidden = all.length - ticked;
    els.count.textContent = all.length ? `${all.length} selected${hidden ? ` (${hidden} not shown)` : ''}` : 'Nothing selected';
    els.pickNone.hidden = !all.length;
    const built = all.filter(p => p.build && !p.building);
    const ready = listed?.install?.ready;
    els.pack.disabled = busy || !built.length;
    els.install.disabled = busy || !built.length || !ready;
    els.pack.textContent = `Export map pack${built.length > 1 ? ` (${built.length})` : ''}`;
    els.install.textContent = `Install in the game${built.length > 1 ? ` (${built.length})` : ''}`;
    // Build: the ticked readable projects into the build queue
    if (els.build) {
      const readable = all.filter(p => !p.error), q = queue?.state;
      const cant = !queue || queue.disabled ? 'this server has no build queue' : !q ? 'asking the server about the build queue'
        : q.state === 'unavailable' ? q.reason : q.state === 'unreadable' ? q.error
        : q.state === 'stopping' ? 'the queue is stopping; add them once it has stopped'
        : q.state === 'stopped' && q.contextChanged ? 'the settings changed since the queue started; clear it first' : null;
      els.build.disabled = queueBusy || !readable.length || Boolean(cant);
      els.build.textContent = `Build${readable.length > 1 ? ` (${readable.length})` : ''}`;
      els.build.title = cant ? `Not now: ${cant}` : `Full builds with baked lighting of the selected projects, one after another, each of the project as saved when its turn comes${hidden ? ` (${hidden} selected not shown by the filter)` : ''}. The open project's unsaved changes are saved first. The manager can be closed meanwhile`;
    }
    els.install.title = !listed?.install?.folder ? (listed?.install?.why ?? '') : !ready ? `Not now: ${listed.install.why}`
      : `Install the selected projects' last builds in ${listed.install.folder} for campaigns, each as it says above. Game maps (the arrow beside Play) shows what the game then uses, and undoes it`;
    els.where.textContent = listed?.install?.folder ? `Installs into ${listed.install.folder}${listed.install.kind ? ` (${listed.install.kind})` : ''}${ready ? '' : ` · ${listed.install.why}`}`
      : (listed?.install?.why ?? '');
    els.where.classList.toggle('warn', Boolean(listed) && !ready);
  }
  async function refresh(keep = false) {
    if (!keep) els.list.replaceChildren(el('div', { className: 'empty', textContent: 'Reading the projects and their builds…' }));
    loadPacks();
    try { take(await api.list()); }
    catch (e) {
      projects = []; listed = null;
      els.list.replaceChildren(el('div', { className: 'empty', textContent: `The projects could not be listed: ${e.message}` }));
      renderPicked(); update();
    }
  }
  function take(value) {
    listed = value;
    projects = value.projects.map(p => {
      const label = p.error ? '' : mapLabel(p.map);
      return { ...p, mapLabel: label, haystack: [p.name, p.map, label, p.variant, p.file, p.build ? `built ${lighting(p.build)}` : 'not built',
        inGameText(p.inGame), ...(p.missions ?? []).map(m => m.label)].filter(Boolean).join(' ').toLocaleLowerCase() };
    });
    picked = new Set([...picked].filter(id => projects.some(p => p.id === id && !p.error)));
    redraw();
  }
  // drawn again whole: the list's scroll and the focused row kept
  function redraw() {
    const at = els.list.scrollTop, focused = els.list.contains(document.activeElement) ? document.activeElement.closest('.mrow')?.dataset.id : null;
    render();
    els.list.scrollTop = at;
    if (focused) [...els.list.querySelectorAll('.mrow')].find(r => r.dataset.id === focused)?.focus({ preventScroll: true });
  }
  async function act(what, run) {
    if (busy) return;
    busy = true; say(what); update();
    try { await run(); }
    catch (e) { say(e.message, true); }
    busy = false; update();
  }
  const ids = () => chosen().filter(p => p.build).map(p => p.id);
  // every project its own way (the request's "modes"); "mode" is only what a project without one would take
  const modes = list => Object.fromEntries(list.map(id => [id, modeOf(projects.find(p => p.id === id))]));
  const failed = results => results.filter(r => !r.ok).map(r => `${r.name}: ${r.error}`);

  els.install.onclick = () => act('Installing…', async () => {
    const r = await api.install(ids(), 'additional', modes(ids()));
    take(r); onChanged?.();
    const ok = r.results.filter(x => x.ok), bad = failed(r.results);
    const off = ok.reduce((n, x) => n + x.switchedOff, 0);
    const lines = [];
    const replaced = ok.filter(x => x.mode === 'replace'), beside = ok.filter(x => x.mode !== 'replace');
    if (replaced.length) lines.push(`Installed in place of the original${replaced.length === 1 ? '' : 's'}: ${replaced.map(x => x.name).join(', ')}.`
      + (off ? ` ${plural(off, 'record')} of the original map${replaced.length === 1 ? '' : 's'} commented out.` : ''));
    if (beside.length) lines.push(`Installed as additional map${beside.length === 1 ? '' : 's'} in the rotation: ${beside.map(x => x.name).join(', ')}.`);
    if (ok.length) lines.push('A campaign uses them from its next new mission on; Game maps (the arrow beside Play) shows it and undoes it.');
    if (bad.length) lines.push(`Not installed: ${bad.join(' ')}`);
    say(lines.map(text => el('div', { textContent: text })), Boolean(bad.length));
  });
  els.pack.onclick = () => act('Exporting…', async () => {
    const saved = packOf();
    const r = await api.pack(ids(), 'additional', modes(ids()), saved ? undefined : (els.packName?.value.trim() || undefined),
      els.projectFiles.checked, saved?.folder, els.packAuthor ? els.packAuthor.value.trim() : undefined);
    await loadPacks(r.folder);
    const show = el('button', { type: 'button', className: 'link', textContent: 'Show it in its folder' });
    show.onclick = () => reveal(r.zip).catch(e => say(e.message, true));
    const n = r.projects?.length ?? 0;
    const shared = !n ? '' : n === r.packed.length ? `${n === 1 ? 'Its editor project is' : 'Their editor projects are'} in its projects folder. `
      : `${plural(n, 'editor project')} ${n === 1 ? 'is' : 'are'} in its projects folder. `;
    const lines = [el('div', {}, `Exported ${r.name} version ${r.version}: ${plural(r.packed.length, 'map')} into ${r.zip} (${(r.size / 1048576).toFixed(1)} MB). Its folder ${r.folder} with card ${String(r.card).padStart(4, '0')} is the pack for Long War Rebalance 3; Install.cmd and Uninstall.cmd ${r.mode === 'mixed' ? `put them into any game (${r.packed.filter(x => x.mode === 'replace').length} replacing their originals, ${r.packed.filter(x => x.mode !== 'replace').length} added to the rotation)` : r.mode === 'replace' ? 'put them into any game in place of the original maps' : 'add them to any game\'s rotation'} and undo it. ${shared}`, show)];
    for (const note of r.notes ?? []) lines.push(el('div', { textContent: note }));
    if (r.skipped.length) lines.push(el('div', { textContent: `Left out: ${r.skipped.map(s => `${s.name}: ${s.error}`).join(' ')}` }));
    say(lines, Boolean(r.skipped.length));
  });
  els.projectFiles.onchange = () => remember(els.projectFiles.checked);
  // Build: the open project saved first if it is ticked and changed, then the ticked readable projects queued in the
  // list's order (the ones the filter hides too). A stopped queue takes them and stays stopped.
  if (els.build) els.build.onclick = async () => {
    if (queueBusy || !queue) return;
    const ids = requestOrder([...projects].sort(sorter), picked);
    if (!ids.length) return;
    queueBusy = true; update(); say('Queuing…');
    try {
      if (ensureSaved && !(await ensureSaved(ids))) { say('Not queued: the open project was not saved.', true); return; }
      const r = await queue.send('add', { projects: ids });
      const added = r.appended.length + r.reset.length, names = id => projects.find(p => p.id === id)?.name ?? id;
      const lines = [];
      if (added) lines.push(`${plural(added, 'project')} queued for a full build${r.queue.state === 'stopped' ? '. The queue is stopped: Resume builds them.' : ': built one after another, each as it is saved when its turn comes. The manager can be closed meanwhile.'}`);
      if (r.alreadyQueued.length) lines.push(`Already in the queue: ${r.alreadyQueued.map(names).join(', ')}.`);
      say(lines.map(text => el('div', { textContent: text })));
    } catch (e) { say(`Not queued: ${e.message}`, true); }
    finally { queueBusy = false; update(); renderStrip(); refreshCells(); }
  };
  if (els.queueStop) {
    els.queueStop.onclick = () => queueAct('Not stopped', 'stop');
    els.queueResume.onclick = () => queueAct('Not resumed', 'resume');
    els.queueClear.onclick = () => queueAct('Not cleared', 'clear');
    els.queueReset.onclick = async () => {
      if (queueBusy || !queue) return;
      queueBusy = true;
      try { await queue.send('reset', { confirm: true }); say('The queue file that could not be read is set aside; the queue is empty.'); }
      catch (e) { say(`Not reset: ${e.message}`, true); }
      finally { queueBusy = false; renderStrip(); update(); }
    };
  }
  const pickShown = () => { for (const p of shown()) if (!p.error) picked.add(p.id); render(); };
  els.all.onchange = () => {
    for (const p of shown()) if (!p.error) els.all.checked ? picked.add(p.id) : picked.delete(p.id);
    render();
  };
  els.pickNone.onclick = () => { picked.clear(); anchor = null; render(); };
  for (const button of els.allModes.querySelectorAll('[data-mode]')) {
    button.onclick = () => { for (const p of chosen()) if (p.build) own.set(p.id, button.dataset.mode); renderPicked(); update(); };
  }
  els.search.addEventListener('input', render);
  for (const chip of els.show.querySelectorAll('[data-show]')) chip.onclick = () => { showing = chip.dataset.show; render(); };
  els.sort.addEventListener('change', render);
  els.form.addEventListener('submit', e => e.preventDefault());
  els.close.onclick = () => close();
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key, typing = e.target.matches('input[type=search]');
    if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === 'a' && !typing) { e.preventDefault(); pickShown(); }
    else if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'b'].includes(key.toLowerCase())) e.preventDefault();
    else if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === 'f') { e.preventDefault(); els.search.focus(); els.search.select(); }
    else if (key === 'Escape') { e.preventDefault(); if (typing && els.search.value) { els.search.value = ''; render(); } else close(); }
    else if ((key === 'ArrowDown' || key === 'ArrowUp') && (e.target.closest('.mrow') || typing)) {
      e.preventDefault();
      const rows = [...els.list.querySelectorAll('.mrow:not(.off)')], at = rows.indexOf(e.target.closest('.mrow'));
      rows[Math.max(0, Math.min(rows.length - 1, at + (key === 'ArrowDown' ? 1 : -1)))]?.focus();
    }
    e.stopPropagation();
  });
  // Tab (modal.js): the rows are one stop, Tab leaves the list for the selection's controls, Shift+Tab for the header's box
  tabOrder(els.root, (e, stops) => {
    const items = stops.filter(x => !x.closest('.mrow'));
    if (!e.target.closest?.('.mrow')) return nextStop(e, items);
    return e.shiftKey ? els.all : items.find(x => els.list.compareDocumentPosition(x) & Node.DOCUMENT_POSITION_FOLLOWING);
  });

  function show() {
    if (!els.root.hidden) return;
    lastFocus = document.activeElement;
    say(null); busy = false;
    els.root.hidden = false;
    els.search.focus();
    queue?.setOpen(true);
    if (els.queueBox) { renderStrip(); clearInterval(ticker); ticker = setInterval(() => { if (['running', 'stopping'].includes(queue?.state?.state)) els.queueClock.textContent = clock(queue.activeSeconds()); }, 1000); }
    return refresh();
  }
  // Each answer of the page's queue controller: the cells and the strip follow; a row that ended brings the listing
  // again (its new build's state).
  let queuedKey = '';
  function queueChanged(state, info) {
    if (els.root.hidden) return;
    // which rows the queue has decides which rows a filter keeps: a change of those draws the list again
    const key = projects.filter(queued).map(p => p.id).join(',');
    if (key !== queuedKey) { queuedKey = key; redraw(); } else refreshCells();
    renderStrip(); update();
    if (info?.ended?.length) refresh(true);
  }
  function close() {
    if (els.root.hidden) return;
    queue?.setOpen(false);
    clearInterval(ticker);
    els.root.hidden = true;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, refresh: () => refresh(true), queueChanged, get open() { return !els.root.hidden; } };
}
