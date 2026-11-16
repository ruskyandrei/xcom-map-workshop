// The project manager (Project menu, Manage projects; tools/viewer/manager.py): every project with its last build
// (when, of which revision, baked or not, by which editor version) and what is in the game of it. The list filters by
// text and by state, and rows are ticked one by one, by a Shift+click range, or all that the filter shows. The ticked
// projects' last builds are then installed in the game for campaigns or zipped into one map pack, by the chosen way:
// additional maps in the rotation, or replacing the original maps. A row's Install as gives that project its own way,
// so one install or one pack can hold maps that replace their originals beside maps that are added. Taking them out again is the Game maps window's
// (gamemaps.js). Warnings (a quick build, a build older than the project, missions other than abductions) never stop it.
// Build puts the ticked projects in the build queue (build_queue.js, tools/viewer/buildqueue.py): full builds, one
// after another on the server, each of the project as saved when its turn comes. The rows say where each is in the
// queue, and a strip above the footer follows the whole queue with its buttons (Stop, Resume, Clear). The manager can
// be closed meanwhile: the queue goes on, and the editor's chip follows it.
import { savedWhen } from './project_files.js';
import { clock, needsFullBuild, requestOrder, rowLine, stripWords } from './build_queue.js';

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
  pack: (projects, mode, modes, name) => call('POST', '/manager/pack', { projects, mode, modes, name }),
};

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const byName = (a, b) => (a.name ?? '').localeCompare(b.name ?? '', undefined, { sensitivity: 'base' });
const lighting = b => b.quick ? 'not baked' : b.lightingUnchanged ? 'baked (lighting unchanged)' : 'baked';
const inGameText = g => !g ? '' : [g.rotation === 'replace' ? 'Replaces the map' : g.rotation === 'additional' ? 'In rotation' : null,
                                   g.play && !g.rotation ? 'For Play in game' : null].filter(Boolean).join(', ') + (g.current ? '' : ' (an older build)');
const SORTS = {
  name: byName,
  map: (a, b) => (a.mapLabel ?? '').localeCompare(b.mapLabel ?? '') || byName(a, b),
  savedAt: (a, b) => (a.savedAt ?? '').localeCompare(b.savedAt ?? '') || byName(a, b),
  build: (a, b) => (a.build?.builtAt ?? '').localeCompare(b.build?.builtAt ?? '') || byName(a, b),
  inGame: (a, b) => inGameText(a.inGame).localeCompare(inGameText(b.inGame)) || byName(a, b),
};
const SHOWS = {
  all: () => true,
  built: p => Boolean(p.build),
  baked: p => Boolean(p.build) && !p.build.quick,
  unbaked: p => Boolean(p.build) && p.build.quick,
  stale: p => Boolean(p.build) && p.build.stale,
  unbuilt: p => !p.build && !p.error,
  ingame: p => Boolean(p.inGame),
  // not built, not baked, of an older revision, or by another editor version (build_queue.js needsFullBuild)
  needsfull: (p, version) => needsFullBuild(p, version),
};

/**
 * els: the dialog's elements (root, form, close, search, show, head, all, list, count, pickShown, pickNone, mode
 * (the two radio inputs' form name), warnings, message, pack, install, done, where).
 * mapLabel(id): a map's display name. onOpen(summary): open that project. reveal(path): show a file in Explorer.
 * onChanged(): the game install's contents changed (the Project menu's Installs section follows).
 * queue: the page's build queue controller (build_queue.js createQueueController), or none; its elements: build,
 * queueBox, queueTitle, queueClock, queueStep, queueStage, queueBar, queueNote, queueFailures, queueLive, queueStop,
 * queueResume, queueClear, queueReset. ensureSaved(ids): saves the open project first when it is among `ids` and has
 * unsaved changes (true when Build may go on).
 */
export function createProjectManager({ els, api = managerApi, mapLabel, onOpen, reveal, onChanged, queue = null, ensureSaved = null }) {
  let listed = null, projects = [], picked = new Set(), sort = { key: 'savedAt', down: true }, anchor = null, busy = false;
  let lastFocus = null, queueBusy = false, ticker = null, lastLive = '';
  const mode = () => els.form.elements.managerMode.value;
  // a project's own way (Install as), where it has one; else the choice below
  const own = new Map();
  const modeOf = p => own.get(p.id) ?? mode();
  const modes = list => Object.fromEntries(list.filter(id => own.has(id)).map(id => [id, own.get(id)]));
  const sorter = (a, b) => (sort.down ? -1 : 1) * SORTS[sort.key](a, b);
  const shown = () => {
    const words = els.search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const keep = SHOWS[els.show.value] ?? SHOWS.all;
    // a row with a result in the queue stays shown, though the filter would hide it now it is built
    return projects.filter(p => (keep(p, listed?.editorVersion) || (els.show.value !== 'all' && queued(p)))
      && words.every(w => p.haystack.includes(w))).sort(sorter);
  };
  const queueItem = p => queue?.state?.items?.find(i => i.project === p.id) ?? null;
  const queued = p => Boolean(queueItem(p)) && !['idle', 'unavailable'].includes(queue?.state?.state);
  const chosen = () => projects.filter(p => picked.has(p.id));

  function say(content, warn = false) {
    els.message.replaceChildren(...(content == null ? [] : [].concat(content)));
    els.message.hidden = content == null; els.message.classList.toggle('warn', warn);
  }
  // The row's place in the build queue, above its last build's line (a failed attempt hides no usable last build).
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
    if (p.building && !line) { cell.append('Building…'); return cell; }
    if (!p.build) { if (!line) cell.append(el('em', { textContent: 'Not built' })); return cell; }
    const b = p.build;
    rest.append(savedWhen(b.builtAt), el('small', { textContent: `rev. ${b.revision}`, className: b.stale ? 'warn' : '',
      title: b.stale ? `The project is at revision ${p.revision}: this build is of an older one` : 'The build is of the saved revision' }),
      el('small', { textContent: lighting(b), className: b.quick ? 'warn' : '',
        title: b.quick ? 'A quick build: pathing, cover and line of sight are right, the lighting is not' : 'Its lighting was calculated' }));
    if (b.editorVersion) rest.append(el('small', { textContent: `v${b.editorVersion}`, title: `Built by the XCOM Map Workshop ${b.editorVersion}`,
      className: listed?.editorVersion && b.editorVersion !== listed.editorVersion ? 'warn' : '' }));
    rest.title = `${b.buildId} · built ${savedWhen(b.builtAt)} from revision ${b.revision} · lighting ${lighting(b)}${b.editorVersion ? ` · editor ${b.editorVersion}` : ''}\n${b.folder}`;
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
  // The strip above the footer: the whole queue, its time, its bar (rows processed of all), its buttons.
  function renderStrip() {
    const q = queue?.state, words = stripWords(q);
    els.queueBox.hidden = !words;
    if (!words) { els.queueLive.textContent = ''; lastLive = ''; return; }
    const active = q.state === 'running' || q.state === 'stopping';
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
    for (const button of els.head.querySelectorAll('[data-sort]')) {
      button.classList.toggle('sorted', button.dataset.sort === sort.key);
      button.classList.toggle('down', button.dataset.sort === sort.key && sort.down);
    }
    els.list.replaceChildren();
    for (const p of list) {
      const box = el('input', { type: 'checkbox', checked: picked.has(p.id), disabled: Boolean(p.error), tabIndex: -1 });
      box.setAttribute('aria-label', `Select ${p.name ?? p.id}`);
      const name = el('span', { className: 'fname' }, p.error ? p.id : (p.name ?? p.id));
      const warned = [...(p.warnings ?? []), ...(p.modeWarnings?.[modeOf(p)] ?? [])];
      if (warned.length) name.append(el('small', { className: 'warn', textContent: '!', title: warned.join('\n') }));
      const row = el('div', { className: 'mrow', tabIndex: p.error ? -1 : 0 }, box, name,
        el('span', { textContent: p.error ? 'unreadable' : p.mapLabel, title: p.error ? '' : `${p.map}${p.missions?.length ? ` · ${p.missions.map(m => m.label + (m.inRotation ? '' : ' (out of rotation)')).join(', ')}` : ''}` }),
        el('span', { textContent: savedWhen(p.savedAt), title: p.error ? '' : `Revision ${p.revision}` }),
        p.error ? el('span') : buildCell(p),
        el('span', { textContent: inGameText(p.inGame), title: p.inGame ? `In ${listed?.install?.folder ?? 'the game'}` : '' }));
      if (p.error) row.append(el('span'));
      else {
        const pick = el('select', { tabIndex: -1, title: 'How this project goes into the game or a pack: as the choice below, or its own way' });
        pick.setAttribute('aria-label', `Install ${p.name ?? p.id} as`);
        for (const [value, label] of [['', 'As below'], ['additional', 'Additional'], ['replace', 'Replace']]) pick.append(el('option', { value, textContent: label }));
        pick.value = own.get(p.id) ?? '';
        pick.classList.toggle('own', own.has(p.id));
        pick.onclick = pick.ondblclick = e => e.stopPropagation();
        pick.onkeydown = e => { if (e.key === ' ' || e.key.startsWith('Arrow')) e.stopPropagation(); };
        pick.onchange = () => { pick.value ? own.set(p.id, pick.value) : own.delete(p.id); const at = els.list.scrollTop; render(); els.list.scrollTop = at; };
        row.append(pick);
      }
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
      els.list.append(el('div', { className: 'empty', textContent: !projects.length ? 'No projects yet: save one from the Project menu.'
        : 'No project matches. Clear the filter to see them all.' }));
    }
    update();
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
    const hidden = all.length - ticked;
    els.count.textContent = `${all.length} of ${plural(projects.filter(p => !p.error).length, 'project')} selected`
      + (hidden ? ` (${hidden} not shown by the filter)` : '') + (list.length !== projects.length ? ` · ${list.length} shown` : '');
    els.pickNone.disabled = !all.length;
    const built = all.filter(p => p.build && !p.building);
    const ready = listed?.install?.ready;
    els.pack.disabled = busy || !built.length;
    els.install.disabled = busy || !built.length || !ready;
    // Build: the ticked readable projects into the build queue
    if (els.build) {
      const readable = all.filter(p => !p.error), q = queue?.state;
      const cant = !queue || queue.disabled ? 'this server has no build queue' : !q ? 'asking the server about the build queue'
        : q.state === 'unavailable' ? q.reason : q.state === 'unreadable' ? q.error
        : q.state === 'stopping' ? 'the queue is stopping; add them once it has stopped'
        : q.state === 'stopped' && q.contextChanged ? 'the settings changed since the queue started; clear it first' : null;
      els.build.disabled = queueBusy || !readable.length || Boolean(cant);
      els.build.textContent = readable.length ? `Build (${readable.length})` : 'Build';
      els.build.title = cant ? `Not now: ${cant}` : `Full builds with baked lighting of the selected projects, one after another, each of the project as saved when its turn comes${hidden ? ` (${hidden} selected not shown by the filter)` : ''}. The open project's unsaved changes are saved first. The manager can be closed meanwhile`;
    }
    els.install.title = !listed?.install?.folder ? (listed?.install?.why ?? '') : !ready ? `Not now: ${listed.install.why}`
      : `Install the selected projects' last builds in ${listed.install.folder} for campaigns, each as its row says (${mode() === 'replace' ? 'in place of its base map' : 'beside its base map'} unless it has its own way). Game maps (Project menu) shows what the game then uses, and undoes it`;
    els.where.textContent = listed?.install?.folder ? `Installs into ${listed.install.folder}${listed.install.kind ? ` (${listed.install.kind})` : ''}${ready ? '' : ` · ${listed.install.why}`}`
      : (listed?.install?.why ?? '');
    els.where.classList.toggle('warn', Boolean(listed) && !ready);
    // what to know about the selection before acting on it
    const notes = [];
    const unbuilt = all.filter(p => !p.build);
    if (unbuilt.length) notes.push([`Not built, so Install and Zip leave out: ${unbuilt.map(p => p.name).join(', ')}.`]);
    for (const p of built) {
      const warnings = [...(p.warnings ?? []), ...(p.modeWarnings?.[modeOf(p)] ?? [])];
      if (warnings.length) notes.push([el('b', { textContent: `${p.name}: ` }), warnings.join(' ')]);
    }
    els.warnings.replaceChildren(...notes.map(parts => el('li', {}, ...parts)));
    els.warnings.hidden = !notes.length;
  }
  async function refresh(keep = false) {
    if (!keep) els.list.replaceChildren(el('div', { className: 'empty', textContent: 'Reading the projects and their builds…' }));
    try { take(await api.list()); }
    catch (e) {
      projects = []; listed = null;
      els.list.replaceChildren(el('div', { className: 'empty', textContent: `The projects could not be listed: ${e.message}` }));
      update();
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
  const failed = results => results.filter(r => !r.ok).map(r => `${r.name}: ${r.error}`);

  els.install.onclick = () => act('Installing…', async () => {
    const r = await api.install(ids(), mode(), modes(ids()));
    take(r); onChanged?.();
    const ok = r.results.filter(x => x.ok), bad = failed(r.results);
    const off = ok.reduce((n, x) => n + x.switchedOff, 0);
    const lines = [];
    const replaced = ok.filter(x => x.mode === 'replace'), beside = ok.filter(x => x.mode !== 'replace');
    if (replaced.length) lines.push(`Installed in place of the original${replaced.length === 1 ? '' : 's'}: ${replaced.map(x => x.name).join(', ')}.`
      + (off ? ` ${plural(off, 'record')} of the original map${replaced.length === 1 ? '' : 's'} commented out.` : ''));
    if (beside.length) lines.push(`Installed as additional map${beside.length === 1 ? '' : 's'} in the rotation: ${beside.map(x => x.name).join(', ')}.`);
    if (ok.length) lines.push('A campaign uses them from its next new mission on; Game maps (Project menu) shows it and undoes it.');
    if (bad.length) lines.push(`Not installed: ${bad.join(' ')}`);
    say(lines.map(text => el('div', { textContent: text })), Boolean(bad.length));
  });
  els.pack.onclick = () => act('Zipping…', async () => {
    const r = await api.pack(ids(), mode(), modes(ids()));
    const show = el('button', { type: 'button', className: 'link', textContent: 'Show it in its folder' });
    show.onclick = () => reveal(r.zip).catch(e => say(e.message, true));
    const lines = [el('div', {}, `Zipped ${plural(r.packed.length, 'map')} into ${r.zip} (${(r.size / 1048576).toFixed(1)} MB), with Install.cmd and Uninstall.cmd ${r.mode === 'mixed' ? `to put them into a game (${r.packed.filter(x => x.mode === 'replace').length} replacing their originals, ${r.packed.filter(x => x.mode !== 'replace').length} added to the rotation)` : r.mode === 'replace' ? 'to replace the original maps in a game' : 'to add them to a game\'s rotation'} and undo it. `, show)];
    if (r.skipped.length) lines.push(el('div', { textContent: `Left out: ${r.skipped.map(s => `${s.name}: ${s.error}`).join(' ')}` }));
    say(lines, Boolean(r.skipped.length));
  });
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
  els.all.onchange = () => {
    for (const p of shown()) if (!p.error) els.all.checked ? picked.add(p.id) : picked.delete(p.id);
    render();
  };
  els.pickShown.onclick = () => { for (const p of shown()) if (!p.error) picked.add(p.id); render(); };
  els.pickNone.onclick = () => { picked.clear(); anchor = null; render(); };
  els.search.addEventListener('input', render);
  els.show.addEventListener('change', render);
  for (const radio of els.form.querySelectorAll('[name=managerMode]')) radio.addEventListener('change', render);
  for (const button of els.head.querySelectorAll('[data-sort]')) {
    button.onclick = () => {
      const key = button.dataset.sort;
      sort = sort.key === key ? { key, down: !sort.down } : { key, down: key === 'savedAt' || key === 'build' };
      render();
    };
  }
  els.form.addEventListener('submit', e => e.preventDefault());
  els.close.onclick = els.done.onclick = () => close();
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key, typing = e.target.matches('input[type=search]');
    if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === 'a' && !typing) { e.preventDefault(); els.pickShown.onclick(); }
    else if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'b'].includes(key.toLowerCase())) e.preventDefault();
    else if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === 'f') { e.preventDefault(); els.search.focus(); els.search.select(); }
    else if (key === 'Escape') { e.preventDefault(); if (typing && els.search.value) { els.search.value = ''; render(); } else close(); }
    else if ((key === 'ArrowDown' || key === 'ArrowUp') && (e.target.closest('.mrow') || typing)) {
      e.preventDefault();
      const rows = [...els.list.querySelectorAll('.mrow:not(.off)')], at = rows.indexOf(e.target.closest('.mrow'));
      rows[Math.max(0, Math.min(rows.length - 1, at + (key === 'ArrowDown' ? 1 : -1)))]?.focus();
    } else if (key === 'Tab') {
      const items = [...els.root.querySelectorAll('button:not(:disabled), input:not(:disabled):not([tabindex="-1"]), select:not(:disabled)')].filter(x => x.offsetParent);
      const inRow = e.target.closest('.mrow'), i = items.indexOf(document.activeElement);
      const next = inRow ? (e.shiftKey ? els.all : els.pickShown) : items[(i + (e.shiftKey ? -1 : 1) + items.length) % items.length];
      if (next) { e.preventDefault(); next.focus(); }
    }
    e.stopPropagation();
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
  // again (its new build's line).
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
