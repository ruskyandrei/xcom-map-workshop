// The prefab library (private/plans/done/prefab-library-plan.md, 5.6 and 5.7; tools/viewer/prefabs.py keeps the files). A prefab
// is a set of pieces, lights, groups and buildings saved in a space of its own (the tile grid: its origin a tile corner
// at ground level), to place in any map as one thing. The file holds references and numbers only, never game data.
// This module is the server's routes, the document's shape, a prefab's words and chips, and the Add panel's Prefabs
// tab, drawn from the library store (prefab_library.js, which holds the list and the actions on a prefab);
// prefab_place.js makes a prefab of a selection and a clip to place of a prefab.
// 2: a copied piece's flags (`flags`; piece flags plan). 3: effects and sounds (pieces with a `kind`: effects and
// sounds plan, stage FX6a; a lens flare is one more kind since FX6b). 4: a piece made from numbers (`generated`) and a
// broken copy's `blasts` (review finding 6: piece_records.js). A prefab of schema 1 to 3 opens, and saves as 4.
import { draftQuery } from './project.js';
import { call, sendPng } from './api.js';
import { plural } from './dom_words.js';

export const SCHEMA = 'xcom-map-workshop/prefab', SCHEMA_VERSION = 5;

const at = id => `/prefabs/${encodeURIComponent(id)}`;
export const api = {
  list: () => call('GET', '/prefabs.json'),
  load: id => call('GET', `${at(id)}/prefab.json`),
  size: document => call('POST', '/prefabs/size', { document }),
  recoverSources: document => call('POST', '/prefabs/recover-sources', { document }),
  // drafts for recovery, one per page session, as projects keep theirs (project.js api)
  recovery: id => call('GET', `${at(id)}/recovery.json`),
  keepRecovery: (id, state) => call('PUT', `${at(id)}/recovery.json`, state),
  dropRecovery: (id, owner, savedAt = null) => call('DELETE', `${at(id)}/recovery.json?${draftQuery(owner, savedAt)}`),
  // extra: { owner }, the page session saving (its draft goes)
  save: (id, document, expectedRevision, extra = {}) => call('PUT', `${at(id)}/prefab.json`, { expectedRevision, document, ...extra }),
  remove: id => call('DELETE', `${at(id)}/prefab.json`),
  // a file from elsewhere; clash: what to do when the library has its id already (null asks: a 409 with `clash`);
  // 'replace' names the revision the user was shown (expectedRevision): one saved since is a clash again
  importFile: (document, clash = null, expectedRevision = null) =>
    call('POST', '/prefabs/import', { document, clash, ...(expectedRevision === null ? {} : { expectedRevision }) }),
  picture: (id, revision) => `${at(id)}/picture.png?r=${revision}`,
  // the picture itself (a duplicate takes it along), or null
  pictureBlob: (id, revision) => fetch(`${at(id)}/picture.png?r=${revision}`).then(r => (r.ok ? r.blob() : null)).catch(() => null),
  putPicture: (id, blob) => sendPng('PUT', `${at(id)}/picture.png`, blob),
  // many pieces of other maps exported at once, each map opened once (a prefab's first use)
  warm: sources => call('POST', '/library/pieces', { sources }),
  // the records themselves, at most 200 a call: {pieces: [{record} or {error}]}
  records: sources => call('POST', '/library/pieces.json', { sources }),
};

/** A new prefab's document around its records. */
export function newPrefab(id, name, { tiles, pieces, groups, buildings, donors }) {
  return { schema: SCHEMA, schemaVersion: SCHEMA_VERSION, id, name, floor: { tiles }, pieces, groups, buildings, donors, mission: null };
}
/** "12 pieces, 2 lights and 1 building · 8 by 6 tiles": what a prefab's summary (or counts like it) holds. */
export function prefabWords(p) {
  const parts = [p.pieces && plural(p.pieces, 'piece'), p.lights && plural(p.lights, 'light'), p.effects && plural(p.effects, 'effect'),
                 p.sounds && plural(p.sounds, 'sound'), p.flares && plural(p.flares, 'lens flare'),
                 p.buildings && plural(p.buildings, 'building')].filter(Boolean);
  const what = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? 'nothing';
  return Array.isArray(p.tiles) ? `${what} · ${p.tiles[0]} by ${p.tiles[1]} tiles` : what;
}

/**
 * The chips a prefab's card or row shows: very large, a newer editor's fields, maps this install lacks. haveMap(package):
 * whether this install has that map (null: not known yet). Each chip: { text, title }.
 */
export function prefabChips(p, haveMap) {
  const chips = [];
  // (the size limits warn and refuse nothing: plan "sturdier prefabs", R7)
  if (p.largeSize?.length) chips.push({ text: 'Very large', title: `${p.largeSize.join('; ')}. It can be placed all the same.` });
  if (p.unknownFields?.length) chips.push({ text: 'Newer fields',
    title: `This prefab has ${p.unknownFields.length === 1 ? 'a field' : `${p.unknownFields.length} fields`} a newer editor wrote (${p.unknownFields.join(', ')}). `
      + 'This editor keeps them as they are and doesn\'t use them.' });
  const missing = (p.maps ?? []).filter(m => haveMap(m) === false);
  if (missing.length) chips.push({ text: 'Maps missing',
    title: `This game install has no ${missing.join(', ')}. The editor looks for matching recipes when you open or place the prefab.` });
  return chips;
}
/** "URB_Bar, URB_Boulevard and 2 more": the maps a prefab's pieces come from, shortened. */
export function prefabMaps(p, most = 2) {
  const maps = p.maps ?? [];
  return maps.length > most ? `${maps.slice(0, most).join(', ')} and ${maps.length - most} more` : maps.join(', ');
}

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };

/**
 * The Add panel's Prefabs tab, drawn from the library store. els: box, filter, list, foot, note, file (the hidden file
 * input), importButton. library: the store (prefab_library.js). onChoose(summary or null): place it (or stop);
 * onEdit(id): open it in the builder; haveMap(package): whether this install has that map (null: not known);
 * hint(message).
 */
export function createPrefabTab({ els, library, onChoose, onEdit, haveMap, hint }) {
  let chosen = null, busy = null;   // busy: { id, mode: 'rename' | 'delete' }
  library.onChange(() => {
    const error = library.error;
    if (error) note(error.status === 404 ? 'This viewer keeps no prefab library.' : `The prefab library could not be read: ${error.message}`);
    render();
  });
  const refresh = () => library.refresh();
  function note(message, ...actions) {
    els.note.hidden = !message;
    els.note.replaceChildren(...(message ? [el('p', { textContent: message }), ...actions] : []));
  }
  function row(p) {
    const item = el('div', { className: `libitem lib prefab${p.error ? ' off' : ''}`, tabIndex: 0 });
    item.setAttribute('role', 'listitem'); item.dataset.id = p.id;
    // (a prefab saved since 24 November 2026 has a picture 256 pixels square, the large panel's; an older one 96)
    const picture = el('canvas'); picture.width = picture.height = 256;
    if (p.picture) {
      const image = new Image();
      image.onload = () => picture.getContext('2d').drawImage(image, 0, 0, 256, 256);
      image.src = api.picture(p.id, p.revision);
    }
    if (p.error) {
      item.append(picture, el('span', {}, el('strong', { textContent: p.file }), el('small', { textContent: p.error })));
      item.title = p.error;
      return item;
    }
    const tags = el('span', { className: 'tags' });
    for (const chip of prefabChips(p, haveMap)) tags.append(el('span', { className: 'tag later', textContent: chip.text, title: chip.title }));
    const text = el('span');
    if (busy?.id === p.id && busy.mode === 'rename') {
      const input = el('input', { type: 'text', value: p.name, maxLength: 120, className: 'prefabrename', spellcheck: false });
      input.setAttribute('aria-label', 'The prefab\'s name');
      input.onclick = e => e.stopPropagation();
      input.onkeydown = e => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); rename(p, input.value.trim()); }
        else if (e.key === 'Escape') { e.preventDefault(); busy = null; render(); }
      };
      text.append(input, el('small', { textContent: 'Enter renames it · Esc leaves it' }));
      setTimeout(() => { input.focus(); input.select(); }, 0);
    } else if (busy?.id === p.id && busy.mode === 'delete') {
      const yes = el('button', { type: 'button', className: 'textbutton warn', textContent: 'Delete it' });
      const no = el('button', { type: 'button', className: 'textbutton', textContent: 'Keep it' });
      yes.onclick = e => { e.stopPropagation(); remove(p); };
      no.onclick = e => { e.stopPropagation(); busy = null; render(); };
      text.append(el('strong', { textContent: `Delete ${p.name}?` }),
                  el('small', { textContent: 'Its file is kept in the library\'s deleted folder. What is placed in maps stays.' }),
                  el('small', { className: 'prefabacts' }, yes, no));
    } else {
      const acts = el('small', { className: 'prefabacts' });
      for (const [label, title, run] of [
        ['Edit', 'Open this prefab in the builder', () => onEdit(p.id)],
        ['Rename', 'Give the prefab another name', () => { busy = { id: p.id, mode: 'rename' }; render(); }],
        ['Duplicate', 'A copy of the prefab, to change on its own', () => duplicate(p)],
        ['Export', 'Save the prefab as a file to pass on', () => exportFile(p)],
        ['Delete', 'Take the prefab out of the library', () => { busy = { id: p.id, mode: 'delete' }; render(); }]]) {
        const button = el('button', { type: 'button', className: 'textbutton', textContent: label, title });
        button.onclick = e => { e.stopPropagation(); run(); };
        acts.append(button);
      }
      text.append(el('strong', { textContent: p.name }), el('small', { textContent: prefabWords(p) }), acts);
    }
    item.append(picture, text, tags);
    item.title = [p.name, prefabWords(p), p.maps?.length ? `Pieces of ${p.maps.join(', ')}` : '', `Revision ${p.revision} · ${p.file}`].filter(Boolean).join('\n');
    const choose = () => { if (!busy) onChoose(chosen?.id === p.id ? null : p); };
    item.onclick = choose;
    item.onkeydown = e => { if (e.target === item && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); choose(); } };
    item.classList.toggle('on', p.id === chosen?.id);
    return item;
  }
  function render() {
    if (els.box.hidden) return;
    const prefabs = library.list(), loaded = library.loaded, folder = library.folder();
    const words = els.filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const shown = prefabs.filter(p => words.every(w => `${p.name} ${(p.maps ?? []).join(' ')}`.toLowerCase().includes(w)))
      .sort((a, b) => String(a.name).localeCompare(String(b.name)));
    els.list.replaceChildren(...shown.map(row));
    els.foot.textContent = !loaded ? '' : !prefabs.length
      ? 'No prefabs yet. Select what should be one (Box select takes a whole building), then Save selection.'
      : `${shown.length === prefabs.length ? `${prefabs.length} prefab${prefabs.length === 1 ? '' : 's'}` : `${shown.length} of ${prefabs.length} prefabs`} · click one, then click in the view to place it`;
    els.foot.title = folder ? `Kept in ${folder}` : '';
  }
  const fail = (what, error) => hint(`${what}: ${error.message}`);
  async function rename(p, name) {
    busy = null;
    render();
    try { if (await library.rename(p, name)) hint(`Renamed to ${name.trim()}`); }
    catch (error) { fail('Not renamed', error); }
  }
  async function duplicate(p) {
    try { hint(`Made ${await library.duplicate(p)}`); }
    catch (error) { fail('Not duplicated', error); }
  }
  async function exportFile(p) {
    try { await library.exportFile(p); hint(`Exported ${p.name}: the file holds references and numbers only, no game data`); }
    catch (error) { fail('Not exported', error); }
  }
  async function remove(p) {
    busy = null;
    if (chosen?.id === p.id) onChoose(null);
    try { await library.remove(p); hint(`Deleted ${p.name} · its file is kept in the library's deleted folder`); }
    catch (error) { fail('Not deleted', error); }
  }
  // A file from elsewhere: checked by the server; one whose id is here already asks what to do. Replace replaces the
  // revision the question showed (review finding 4): one saved meanwhile asks again, with its revision now.
  async function importDocument(doc, clash = null, revision = null) {
    try {
      const taken = await library.importDocument(doc, clash, revision);
      note('');
      hint(taken.replaced ? `Replaced ${taken.name} with the file (revision ${taken.revision})` : `Imported ${taken.name}`);
    } catch (error) {
      const here = error.body?.clash;
      if (error.status !== 409 || !here) { note(`Not imported. ${error.message}`, dismiss()); return; }
      const replace = el('button', { type: 'button', textContent: 'Replace it' }), both = el('button', { type: 'button', textContent: 'Keep both' });
      replace.title = `The file is saved over revision ${here.revision} of the prefab here, as its next revision (the one before is kept)`;
      both.title = 'The file is stored as a prefab of its own, with "(imported)" after its name';
      replace.onclick = () => importDocument(doc, 'replace', here.revision); both.onclick = () => importDocument(doc, 'copy');
      const again = error.body?.changed ? `It was saved again meanwhile. ` : '';
      note(`${again}The library already has this prefab, as “${here.name}” (revision ${here.revision}).`, el('div', { className: 'row' }, replace, both, dismiss('Cancel')));
    }
  }
  const dismiss = (label = 'OK') => { const b = el('button', { type: 'button', textContent: label }); b.onclick = () => note(''); return b; };
  async function importFile(file) {
    if (!file) return;
    if (file.size > 16 << 20) { note('Not imported. The file is too large to be a prefab.', dismiss()); return; }
    let doc;
    try { doc = JSON.parse(await file.text()); } catch { note('Not imported. The file is not a prefab (it is not JSON).', dismiss()); return; }
    await importDocument(doc);
  }
  els.importButton.onclick = () => { els.file.value = ''; els.file.click(); };
  els.file.onchange = () => importFile(els.file.files[0]);
  els.filter.addEventListener('input', render);
  els.filter.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (els.filter.value) { els.filter.value = ''; render(); } else els.filter.blur();
    e.preventDefault();
  });

  return {
    show(on) { els.box.hidden = !on; if (on) { render(); refresh(); } else els.list.replaceChildren(); },
    get open() { return !els.box.hidden; },
    setChosen(entry) { chosen = entry?.prefab ? entry.prefab : null; for (const item of els.list.children) item.classList.toggle('on', item.dataset.id === chosen?.id); },
    refresh,
    list: () => library.list(),
    byName: name => library.byName(name),
  };
}
