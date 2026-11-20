// The Game maps window (the Game menu, on the arrow beside Play; tools/viewer/gamemaps.py): the map records of the game install's DefaultMaps.ini
// as the game reads them now, by map. The install's own records have a tick: in use, or switched off (commented out,
// here by hand or because a project's build replaces the map). The records the editor added sit under their base map,
// each with an Undo that takes that build out. Group by turns the list round: each kind of mission with the maps the
// game can play it on (the install's own and the editor's), which is the way to see what a mission draws from. Undo everything takes all of the editor's out of the game: records,
// landing zones, files (what the Project menu's Remove from game did).
import { call } from './api.js';
import { recall, remember } from './storage.js';

export const gameMapsApi = {
  list: () => call('GET', '/gamemaps.json'),
  use: (records, use) => call('POST', '/gamemaps/use', { records, use }),
  undo: variants => call('POST', '/gamemaps/undo', { variants }),
  undoAll: () => call('POST', '/play/remove', {}),
};

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const own = r => r.kind === 'own';
const statusText = r => r.state === 'replaced' ? `Replaced by ${(r.by ?? []).join(', ')}${r.manual ? ' (and switched off)' : ''}`
  : r.state === 'off' ? 'Switched off'
  : r.state === 'install-off' ? 'Commented out by the install'
  : r.kind === 'rotation' ? `Added: ${r.project ?? r.variant} (${r.mode === 'replace' ? 'replaces the map' : 'additional'}${r.quick ? ', not baked' : ''})`
  : r.kind === 'play' ? `Added for Play in game${r.project ? `: ${r.project}` : ''}`
  : '';
const SHOWS = {
  all: () => true,
  changed: r => r.state !== 'on' && r.state !== 'install-off',
  used: r => (own(r) ? r.state === 'on' : true) && r.inRotation,
  off: r => own(r) && r.state !== 'on',
  named: r => !r.inRotation && r.state !== 'install-off',
};

/** What Undo everything did (installs.reset's result), in a sentence. */
function removedText(d) {
  const parts = [];
  if (d.records) parts.push(plural(d.records, 'map record'));
  if (d.rotation) parts.push(`${plural(d.rotation, 'build')} from the campaign's maps`);
  if (d.recordsBack) parts.push(`${plural(d.recordsBack, 'record')} of the game's own back in use`);
  if (d.landingZones) parts.push(`the landing zones of ${plural(d.landingZones, 'map')}`);
  if (d.files.length) parts.push(plural(d.files.length, 'file'));
  if (d.intro) parts.push('the first mission an earlier version installed (the game\'s own again)');
  if (d.playFile) parts.push('the commands file');
  const left = d.left.length ? ` Left as they are: ${d.left.join('; ')}.` : '';
  return (parts.length ? `Taken out of the game: ${parts.join(', ')}.` : 'The editor had nothing in the game.') + left;
}

/**
 * els: the dialog's elements (root, form, close, search, show, group, column, list, count, offShown, onShown, message, undoAll, done,
 * where). onChanged(): the install's contents changed (the Game menu's Installs section follows).
 */
export function createGameMaps({ els, api = gameMapsApi, onChanged }) {
  let listed = null, busy = false, lastFocus = null;
  const ready = () => Boolean(listed?.install?.ready);
  function say(text, warn = false) { els.message.textContent = text ?? ''; els.message.hidden = !text; els.message.classList.toggle('warn', warn); }
  function shown() {
    if (!listed) return [];
    const words = els.search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const keep = SHOWS[els.show.value] ?? SHOWS.all;
    return listed.maps.map(m => ({ map: m, records: m.records.filter(r => keep(r) && words.every(w => r.haystack.includes(w))) }))
      .filter(g => g.records.length);
  }
  // The shown records by kind of mission, in the map browser's order of kinds (abductions first), each kind's maps
  // by name: [{ title, note, records: [{ record, map }] }].
  function byMission(groups) {
    const found = new Map();
    for (const { map, records } of groups) for (const record of records) {
      const key = record.mission.replace(/ \d+$/, '');
      if (!found.has(key)) found.set(key, { title: key, group: record.group, rows: [] });
      found.get(key).rows.push({ record, map });
    }
    const order = ['abduction', 'ufo', 'terror', 'council', 'exalt', 'story', 'other'];
    return [...found.values()].sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group) || a.title.localeCompare(b.title))
      .map(g => {
        g.rows.sort((a, b) => a.map.label.localeCompare(b.map.label) || (own(a.record) ? 0 : 1) - (own(b.record) ? 0 : 1));
        const used = g.rows.filter(x => own(x.record) ? x.record.state === 'on' : x.record.kind === 'rotation').length;
        return { title: g.title, note: `${plural(used, 'record')} in use of ${g.rows.length} shown`, rows: g.rows };
      });
  }
  function render() {
    const groups = shown(), at = els.list.scrollTop, missions = els.group.value === 'mission';
    els.column.textContent = missions ? 'Map' : 'Mission';
    const sections = missions ? byMission(groups)
      : groups.map(({ map, records }) => ({ title: map.label, note: map.name, rows: records.map(record => ({ record, map })) }));
    els.list.replaceChildren();
    for (const section of sections) {
      els.list.append(el('div', { className: 'gmap' }, el('b', { textContent: section.title }), el('span', { textContent: section.note })));
      for (const { record: r, map } of section.rows) {
        const row = el('div', { className: `grow ${r.state}` });
        if (own(r)) {
          const box = el('input', { type: 'checkbox', checked: r.state === 'on', disabled: busy || !ready() || r.state === 'replaced' || r.state === 'install-off' });
          box.setAttribute('aria-label', `Use ${r.display || r.name}`);
          box.title = r.state === 'replaced' ? 'A project\'s build replaces this map: undo that build to bring it back'
            : r.state === 'install-off' ? 'The install itself comments this record out; the editor leaves it'
            : !ready() ? `Not now: ${listed?.install?.why ?? ''}`
            : r.state === 'on' ? 'In use. Untick to switch it off: its line is commented out, and the game no longer uses it'
            : 'Switched off. Tick to bring it back as the install had it';
          box.onchange = () => act(box.checked ? 'Switching it on…' : 'Switching it off…', async () => {
            const res = await api.use([r.id], box.checked);
            take(res); onChanged?.();
            say(`${r.display || r.name}: ${box.checked ? (res.replaced ? 'still off, because a build replaces its map' : 'in use again') : 'switched off'}.`);
          });
          row.append(box);
        } else row.append(el('span', { className: 'gplus', textContent: '+' }));
        row.append(missions ? el('span', { textContent: map.label, title: map.name }) : el('span', { textContent: r.mission }),
          el('span', { className: 'gname', textContent: r.display || r.name, title: `${r.display}\nName="${r.name}"` }),
          el('span', { textContent: r.state === 'install-off' ? '' : r.inRotation ? 'In rotation' : 'By name',
            title: r.inRotation ? 'bInRotation=True: missions of its kind draw it' : 'bInRotation=False: the game asks for it by its record\'s name (council missions, the story\'s), or not at all' }),
          el('span', { className: 'gstate', textContent: statusText(r), title: statusText(r) }));
        if (!own(r)) {
          const undo = el('button', { type: 'button', textContent: 'Undo', disabled: busy || !ready(),
            title: `Take ${r.project ?? r.variant} out of the game's maps: all of its records and landing zones, and the map it replaced back in use. Its files stay until Undo everything` });
          undo.onclick = () => act('Undoing…', async () => {
            const res = await api.undo([r.variant]);
            take(res); onChanged?.();
            say(res.undone.length ? `${r.project ?? r.variant} is out of the game's maps. Its files stay in the game until Undo everything.` : 'There was nothing of it to undo.');
          });
          row.append(undo);
        } else row.append(el('span'));
        els.list.append(row);
      }
    }
    if (!groups.length) els.list.append(el('div', { className: 'empty', textContent: listed ? 'No record matches. Clear the filter to see them all.' : 'Reading the game\'s maps…' }));
    els.list.scrollTop = at;
    update(groups);
  }
  function update(groups = shown()) {
    const records = groups.flatMap(g => g.records), all = listed ? listed.maps.flatMap(m => m.records) : [];
    const on = records.filter(r => own(r) && r.state === 'on'), off = records.filter(r => own(r) && r.state === 'off');
    const inUse = all.filter(r => (own(r) ? r.state === 'on' : true) && r.inRotation).length;
    const changed = all.filter(SHOWS.changed).length;
    els.count.textContent = listed ? `${plural(records.length, 'record')} shown of ${all.length} · ${inUse} in rotation · ${changed ? `${changed} changed or added by the editor` : 'nothing changed by the editor'}` : '';
    els.offShown.disabled = busy || !ready() || !on.length; els.offShown.textContent = `Switch off the ${on.length} shown`;
    els.onShown.disabled = busy || !ready() || !off.length; els.onShown.textContent = `Switch on the ${off.length} shown`;
    els.undoAll.disabled = busy || !ready() || !listed?.anything;
    els.undoAll.title = !listed ? '' : !ready() ? `Not now: ${listed.install.why}` : !listed.anything ? 'The editor has nothing in the game'
      : 'Take everything the editor put in the game back out: its builds\' files, map records and landing zones, and every record it switched off back in use. The config files are then as the install had them';
    els.where.textContent = listed ? `${listed.install.folder}${listed.install.kind ? ` (${listed.install.kind})` : ''}${ready() ? '' : ` · ${listed.install.why}: nothing can be changed now`}` : '';
    els.where.classList.toggle('warn', Boolean(listed) && !ready());
  }
  function take(value) {
    listed = value;
    for (const m of listed.maps) for (const r of m.records) {
      r.haystack = [m.label, m.name, r.name, r.display, r.mission, r.project, r.variant, statusText(r), r.inRotation ? 'in rotation' : 'by name']
        .filter(Boolean).join(' ').toLocaleLowerCase();
    }
    render();
  }
  async function act(what, run) {
    if (busy) return;
    busy = true; say(what); update();
    try { await run(); }
    catch (e) { say(e.message, true); if (listed) { busy = false; render(); } }
    busy = false; render();
  }
  async function refresh() {
    try { take(await api.list()); }
    catch (e) {
      listed = null;
      els.list.replaceChildren(el('div', { className: 'empty', textContent: `The game's maps could not be read: ${e.message}` }));
      update();
    }
  }
  const bulk = useThem => () => {
    const ids = shown().flatMap(g => g.records).filter(r => own(r) && r.state === (useThem ? 'off' : 'on')).map(r => r.id);
    if (!ids.length) return;
    if (!useThem && ids.length > 5 && !window.confirm(`Switch off ${ids.length} map records? The game stops using them until they are switched on again here.`)) return;
    act(useThem ? 'Switching them on…' : 'Switching them off…', async () => {
      const res = await api.use(ids, useThem);
      take(res); onChanged?.();
      say(`${plural(res.changed, 'record')} ${useThem ? 'in use again' : 'switched off'}.${res.replaced ? ` ${res.replaced} stay off because a build replaces their map.` : ''}`);
    });
  };
  els.offShown.onclick = bulk(false);
  els.onShown.onclick = bulk(true);
  els.undoAll.onclick = () => act('Taking everything out…', async () => {
    const res = await api.undoAll();
    say(removedText(res.removed), Boolean(res.removed.left.length));
    onChanged?.();
    await refresh();
  });
  els.search.addEventListener('input', render);
  els.show.addEventListener('change', render);
  // the grouping chosen is kept for next time
  if (recall('workshop.gameMapsGroup') === 'mission') els.group.value = 'mission';
  els.group.addEventListener('change', () => {
    remember('workshop.gameMapsGroup', els.group.value);
    els.list.scrollTop = 0;
    render();
  });
  els.form.addEventListener('submit', e => e.preventDefault());
  els.close.onclick = els.done.onclick = () => close();
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key, typing = e.target.matches('input[type=search]');
    if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'b'].includes(key.toLowerCase())) e.preventDefault();
    else if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === 'f') { e.preventDefault(); els.search.focus(); els.search.select(); }
    else if (key === 'Escape') { e.preventDefault(); if (typing && els.search.value) { els.search.value = ''; render(); } else close(); }
    e.stopPropagation();
  });

  function show() {
    if (!els.root.hidden) return;
    lastFocus = document.activeElement;
    say(null); busy = false; listed = null;
    els.root.hidden = false;
    render();
    els.search.focus();
    return refresh();
  }
  function close() {
    if (els.root.hidden) return;
    els.root.hidden = true;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, get open() { return !els.root.hidden; } };
}
