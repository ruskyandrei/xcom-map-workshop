// The map browser: every map the game install plays (the server's /maps.json), in sections by mission type, with a
// search over names, packages and missions. A map that serves several mission types (an abduction map that is also a
// terror site, say) is listed under each. A map not exported yet is prepared the first time it is opened: the server
// exports it in the background (tools/viewer/exports.py, about half a minute), and the page then opens it. It is the
// Open window's Maps side: its head carries the window's switch (map_menu.js draws it; prefab_browser.js openSwitch).
import { nextStop, tabOrder } from './modal.js';
import { call as callServer } from './api.js';

const GROUPS = [['abduction', 'Abduction'], ['ufo', 'UFO'], ['terror', 'Terror'], ['council', 'Council'],
  ['exalt', 'EXALT'], ['story', 'Story'], ['other', 'Other']];

const call = (url, post = false) => callServer(post ? 'POST' : 'GET', url, undefined, { fallback: r => `${r.status} ${r.statusText}` });

/**
 * els: the dialog's elements (root, form, search, prepared, groups, list, count, message, bar, ok, cancel, close).
 * maps: /maps.json's maps. current: the open map's id (or null). onOpen(id): open that map (it is exported).
 */
export function createMapBrowser({ els, maps, current, onOpen }) {
  maps = [...maps];
  let group = 'all', chosen = null, chosenRow = null, lastFocus = null, preparing = null, timer = null;
  const byId = new Map(maps.map(m => [m.id, m]));
  const words = m => [m.label, m.name, ...m.missions.flatMap(x => [x.label, x.display])].join(' ').toLowerCase();
  const matches = m => {
    const typed = els.search.value.trim().toLowerCase();
    return (!els.prepared.checked || m.ready) && (!typed || typed.split(/\s+/).every(w => words(m).includes(w)));
  };
  const rows = () => [...els.list.querySelectorAll('.maprow')];
  const element = (tag, className, textContent = '') => Object.assign(document.createElement(tag), { className, textContent });

  function say(message, warn = false) {
    els.message.textContent = message ?? ''; els.message.hidden = !message; els.message.classList.toggle('warn', warn);
    chosenRow?.scrollIntoView({ block: 'nearest' });   // a message takes room from the list: keep the choice in view
  }
  // The export's progress (exports.py: the map's pieces read, then its streamed packages'), or none yet.
  function bar(fraction) {
    els.bar.hidden = fraction == null;
    if (fraction != null) els.bar.firstElementChild.style.width = `${Math.round(100 * Math.min(1, Math.max(0, fraction)))}%`;
  }
  function status(m) {
    if (preparing?.id === m.id) {
      const f = preparing.progress?.fraction;
      return [f != null ? `Preparing… ${Math.round(100 * f)}%` : `Preparing… ${Math.round(preparing.seconds ?? 0)} s`, 'busy'];
    }
    if (m.checked) return ['Checked in game', 'checked'];
    return m.ready ? ['Ready', 'ready'] : ['First open ≈ 30 s', 'new'];
  }
  function update() {
    const m = byId.get(chosen);
    els.ok.disabled = !m || preparing?.id === m.id || (m.id === current && m.ready);
    els.ok.textContent = m && !m.ready ? 'Prepare and open' : 'Open';
  }
  // A map can have a row in several sections: all of them show it chosen; `at` is the one the arrow keys move from.
  function choose(id, at = null, focus = false) {
    chosen = byId.has(id) ? id : null;
    for (const row of rows()) {
      const on = row.dataset.id === chosen;
      row.classList.toggle('on', on); row.setAttribute('aria-selected', on);
    }
    chosenRow = at ?? rows().find(r => r.dataset.id === chosen) ?? null;
    chosenRow?.scrollIntoView({ block: 'nearest' });
    if (focus) chosenRow?.focus();
    update();
  }
  function renderChips() {
    const shown = maps.filter(matches);
    const chips = [['all', 'All', shown.length], ...GROUPS.map(([g, label]) => [g, label, shown.filter(m => m.groups.includes(g)).length])];
    els.groups.replaceChildren(...chips.filter(([g, , n]) => g === 'all' || g === group || maps.some(m => m.groups.includes(g))).map(([g, label, n]) => {
      const chip = element('button', 'mapchip', label);
      chip.type = 'button'; chip.dataset.group = g; chip.setAttribute('aria-pressed', g === group);
      chip.append(element('span', 'n', String(n)));
      chip.onclick = () => { group = g; render(); };
      return chip;
    }));
  }
  function row(m) {
    const button = element('button', 'maprow');
    button.type = 'button'; button.dataset.id = m.id; button.setAttribute('role', 'option');
    const name = element('span', 'mname', m.label);
    if (m.id === current) name.append(element('small', '', 'open'));
    const missions = [...new Set(m.missions.map(x => x.label))];
    const [state, kind] = status(m);
    button.append(name, element('span', 'mpackage', m.name), element('span', 'mmissions', missions.join(' · ')),
      element('span', `mstate ${kind}`, state));
    button.title = `${m.label} (${m.name})\n${m.missions.map(x => `${x.label}: ${x.display}`).join('\n')}`;
    button.onclick = () => choose(m.id, button, true);
    button.ondblclick = () => { choose(m.id, button, true); submit(); };
    return button;
  }
  function render() {
    renderChips();
    const sections = group === 'all' ? GROUPS : GROUPS.filter(([g]) => g === group);
    const parts = [];
    let listed = new Set();
    for (const [g, label] of sections) {
      const items = maps.filter(m => m.groups.includes(g) && matches(m));
      if (!items.length) continue;
      const head = element('div', 'mapgroup', label);
      head.append(element('span', 'n', String(items.length)));
      parts.push(head, ...items.map(row));
      items.forEach(m => listed.add(m.id));
    }
    if (!parts.length) parts.push(element('div', 'empty', els.prepared.checked ? 'No prepared map matches. Untick “Prepared only” to see the others.' : 'No map matches.'));
    els.list.replaceChildren(...parts);
    els.count.textContent = `${listed.size} of ${maps.length} maps · ${maps.filter(m => m.ready).length} prepared`;
    choose(listed.has(chosen) ? chosen : rows()[0]?.dataset.id ?? null);
  }
  function refreshRow(id) {
    for (const r of rows().filter(r => r.dataset.id === id)) {
      const fresh = row(byId.get(id));
      fresh.classList.toggle('on', r.classList.contains('on')); fresh.setAttribute('aria-selected', r.classList.contains('on'));
      const focused = document.activeElement === r;
      r.replaceWith(fresh);
      if (chosenRow === r) chosenRow = fresh;
      if (focused) fresh.focus();
    }
    update();
  }

  async function prepare(m) {
    if (preparing) { say(`${byId.get(preparing.id)?.label ?? preparing.id} is being prepared first: one map at a time.`, true); return; }
    preparing = { id: m.id, seconds: 0 };
    say(`Preparing ${m.label}: reading its package for the first time (about half a minute).`);
    bar(0);
    refreshRow(m.id);
    let state;
    try { state = await call(`/maps/${encodeURIComponent(m.id)}/export`, true); }
    catch (e) { preparing = null; bar(null); refreshRow(m.id); say(`${m.label} could not be prepared: ${e.message}`, true); return; }
    follow(m, state);
  }
  function follow(m, state) {
    clearTimeout(timer);
    if (state.state === 'running') {
      preparing = { id: m.id, seconds: state.seconds, progress: state.progress };
      refreshRow(m.id);
      const p = state.progress, seconds = Math.round(state.seconds ?? 0);
      say(p ? `Preparing ${m.label}: ${p.what}, ${p.done} of ${p.total} pieces · ${seconds} s`
        : `Preparing ${m.label}: starting · ${seconds} s (the first open of a map takes about half a minute).`);
      bar(p?.fraction ?? 0);
      timer = setTimeout(async () => {
        try { follow(m, await call(`/maps/${encodeURIComponent(m.id)}/export.json`)); }
        catch (e) { preparing = null; bar(null); refreshRow(m.id); say(`Lost track of ${m.label}'s export: ${e.message}`, true); }
      }, 1000);
      return;
    }
    preparing = null;
    bar(state.state === 'ready' || state.ready ? 1 : null);
    if (state.state === 'ready' || state.ready) {
      m.ready = true; refreshRow(m.id);
      if (!els.root.hidden && chosen === m.id) { say(`${m.label} is ready: opening it.`); onOpen(m.id); }
      else say(`${m.label} is ready.`);
    } else {
      refreshRow(m.id);
      say(`${m.label} could not be prepared: ${state.error ?? 'the export failed'}. The server's log has more.`, true);
    }
  }
  function submit() {
    const m = byId.get(chosen);
    if (!m) { say('Choose a map.', true); return; }
    if (m.id === current && m.ready) { close(); return; }
    if (m.ready) { onOpen(m.id); return; }
    prepare(m);
  }
  // From the search box the arrows move the choice and leave the typing where it is; from a row they move the focus.
  function move(step) {
    const all = rows();
    if (!all.length) return;
    const inRow = document.activeElement?.closest?.('.maprow');
    const at = all.indexOf(inRow ?? chosenRow);
    const next = all[Math.max(0, Math.min(all.length - 1, at < 0 ? 0 : at + step))];
    choose(next.dataset.id, next, Boolean(inRow));
  }

  els.form.addEventListener('submit', e => { e.preventDefault(); submit(); });
  els.search.addEventListener('input', () => { say(null); render(); });
  els.prepared.addEventListener('change', render);
  els.cancel.onclick = () => close();
  els.close.onclick = () => close();
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key;
    if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f', 'b'].includes(key.toLowerCase())) { e.preventDefault(); if (key.toLowerCase() === 'f') els.search.focus(); }
    else if (key === 'Escape') { e.preventDefault(); close(); }
    else if (key === 'ArrowDown' || key === 'ArrowUp') { e.preventDefault(); move(key === 'ArrowDown' ? 1 : -1); }
    else if (key === 'Enter' && e.target.closest('.maprow')) { e.preventDefault(); submit(); }
    e.stopPropagation();
  });
  // Tab (modal.js) goes round the dialog's controls but the map rows, which the arrow keys move between
  tabOrder(els.root, (e, stops) => nextStop(e, stops.filter(el => !el.classList.contains('maprow'))));

  // show(id, message): open the browser on that map (the open one by default); prepare: start preparing it at once.
  function show(id = current, { message = null, prepare: start = false } = {}) {
    lastFocus = document.activeElement;
    els.root.hidden = false;
    if (!preparing) say(message, Boolean(message));
    chosen = byId.has(id) ? id : null;
    const m = byId.get(chosen);
    if (m && !m.groups.includes(group) && group !== 'all') group = 'all';
    render();
    els.search.focus(); els.search.select();
    if (start && m && !m.ready) prepare(m);
  }
  function close() {
    if (els.root.hidden) return;
    els.root.hidden = true;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, count: () => maps.length, get open() { return !els.root.hidden; } };
}
