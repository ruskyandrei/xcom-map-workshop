// The prefab library (private/plans/done/prefab-library-plan.md, 5.6 and 5.7; tools/viewer/prefabs.py keeps the files). A prefab
// is a set of pieces, lights, groups and buildings saved in a space of its own (the tile grid: its origin a tile corner
// at ground level), to place in any map as one thing. The file holds references and numbers only, never game data.
// This module is the server's routes, the document's shape, and the Add panel's Prefabs tab; app.js makes a prefab of
// a selection and a clip to place of a prefab.
export const SCHEMA = 'xcom-map-workshop/prefab', SCHEMA_VERSION = 1;
export const TILE = 96, STOREY = 64;

async function call(method, url, body) {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(value.error || `The server said ${response.status}`), { status: response.status, detail: value });
  return value;
}
const at = id => `/prefabs/${encodeURIComponent(id)}`;
export const api = {
  list: () => call('GET', '/prefabs.json'),
  load: id => call('GET', `${at(id)}/prefab.json`),
  size: document => call('POST', '/prefabs/size', { document }),
  recoverSources: document => call('POST', '/prefabs/recover-sources', { document }),
  recovery: id => call('GET', `${at(id)}/recovery.json`),
  keepRecovery: (id, state) => call('PUT', `${at(id)}/recovery.json`, state),
  dropRecovery: id => call('DELETE', `${at(id)}/recovery.json`),
  save: (id, document, expectedRevision) => call('PUT', `${at(id)}/prefab.json`, { expectedRevision, document }),
  remove: id => call('DELETE', `${at(id)}/prefab.json`),
  // a file from elsewhere; clash: what to do when the library has its id already (null asks: a 409 with `clash`)
  importFile: (document, clash = null) => call('POST', '/prefabs/import', { document, clash }),
  picture: (id, revision) => `${at(id)}/picture.png?r=${revision}`,
  putPicture: (id, blob) => fetch(`${at(id)}/picture.png`, { method: 'PUT', headers: { 'Content-Type': 'image/png' }, body: blob }),
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
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  const parts = [p.pieces && plural(p.pieces, 'piece'), p.lights && plural(p.lights, 'light'), p.buildings && plural(p.buildings, 'building')].filter(Boolean);
  const what = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? 'nothing';
  return Array.isArray(p.tiles) ? `${what} · ${p.tiles[0]} by ${p.tiles[1]} tiles` : what;
}

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };

/**
 * The Add panel's Prefabs tab. els: box, filter, list, foot, note, file (the hidden file input), importButton.
 * onChoose(summary or null): place it (or stop); haveMap(package): whether this install has that map (null: not
 * known); hint(message); download(name, document): hand the user a file.
 */
export function createPrefabBrowser({ els, onChoose, onEdit, haveMap, hint, download }) {
  let prefabs = [], folder = '', chosen = null, loading = null, loaded = false, busy = null;   // busy: { id, mode: 'rename' | 'delete' }
  const names = () => new Set(prefabs.filter(p => !p.error).map(p => p.name.toLowerCase()));

  async function refresh() {
    loading ??= api.list().then(answer => { prefabs = answer.prefabs; folder = answer.folder; loaded = true; })
      .catch(error => { prefabs = []; loaded = false; note(error.status === 404 ? 'This viewer keeps no prefab library.' : `The prefab library could not be read: ${error.message}`); })
      .finally(() => { loading = null; render(); });
    return loading;
  }
  function note(message, ...actions) {
    els.note.hidden = !message;
    els.note.replaceChildren(...(message ? [el('p', { textContent: message }), ...actions] : []));
  }
  const missingMaps = p => (p.maps ?? []).filter(m => haveMap(m) === false);

  function row(p) {
    const item = el('div', { className: `libitem lib prefab${p.error ? ' off' : ''}`, tabIndex: 0 });
    item.setAttribute('role', 'listitem'); item.dataset.id = p.id;
    const picture = el('canvas'); picture.width = picture.height = 96;
    if (p.picture) {
      const image = new Image();
      image.onload = () => picture.getContext('2d').drawImage(image, 0, 0, 96, 96);
      image.src = api.picture(p.id, p.revision);
    }
    if (p.error) {
      item.append(picture, el('span', {}, el('strong', { textContent: p.file }), el('small', { textContent: p.error })));
      item.title = p.error;
      return item;
    }
    const tags = el('span', { className: 'tags' });
    // (the size limits warn and refuse nothing: plan "sturdier prefabs", R7)
    if (p.largeSize?.length) tags.append(el('span', { className: 'tag later', textContent: 'Very large',
      title: `${p.largeSize.join('; ')}. It can be placed all the same.` }));
    else if (p.tall) tags.append(el('span', { className: 'tag later', textContent: 'Tall',
      title: 'It reaches over 18 levels, the height of the game\'s tallest map: not played at this height.' }));
    if (p.unknownFields?.length) tags.append(el('span', { className: 'tag later', textContent: 'Newer fields',
      title: `This prefab has ${p.unknownFields.length === 1 ? 'a field' : `${p.unknownFields.length} fields`} a newer editor wrote (${p.unknownFields.join(', ')}). `
        + 'This editor keeps them as they are and doesn\'t use them.' }));
    const missing = missingMaps(p);
    if (missing.length) tags.append(el('span', { className: 'tag later', textContent: 'Maps missing',
      title: `This game install has no ${missing.join(', ')}. The editor looks for matching recipes when you open or place the prefab.` }));
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
    if (!name || name === p.name) { render(); return; }
    try { const doc = await api.load(p.id); await api.save(p.id, { ...doc, name }, doc.revision); hint(`Renamed to ${name}`); }
    catch (error) { fail('Not renamed', error); }
    refresh();
  }
  const freeName = base => { const taken = names(); let name = base; for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${base} ${n}`; return name; };
  async function duplicate(p) {
    try {
      const doc = await api.load(p.id), id = crypto.randomUUID(), name = freeName(`${p.name} copy`.slice(0, 110));
      const { revision, savedAt, created, ...rest } = doc;
      await api.save(id, { ...rest, id, name }, 0);
      // its picture goes with it
      if (p.picture) { const blob = await fetch(api.picture(p.id, p.revision)).then(r => (r.ok ? r.blob() : null)).catch(() => null); if (blob) await api.putPicture(id, blob); }
      hint(`Made ${name}`);
    } catch (error) { fail('Not duplicated', error); }
    refresh();
  }
  async function exportFile(p) {
    try { const doc = await api.load(p.id); download(`${p.file ?? `${p.name}.json`}`, doc); hint(`Exported ${p.name}: the file holds references and numbers only, no game data`); }
    catch (error) { fail('Not exported', error); }
  }
  async function remove(p) {
    busy = null;
    if (chosen?.id === p.id) onChoose(null);
    try { await api.remove(p.id); hint(`Deleted ${p.name} · its file is kept in the library's deleted folder`); }
    catch (error) { fail('Not deleted', error); }
    refresh();
  }
  // A file from elsewhere: checked by the server; one whose id is here already asks what to do.
  async function importDocument(doc, clash = null) {
    try {
      const taken = await api.importFile(doc, clash);
      note('');
      hint(taken.replaced ? `Replaced ${taken.name} with the file (revision ${taken.revision})` : `Imported ${taken.name}`);
    } catch (error) {
      const here = error.detail?.clash;
      if (error.status !== 409 || !here) { note(`Not imported. ${error.message}`, dismiss()); return; }
      const replace = el('button', { type: 'button', textContent: 'Replace it' }), both = el('button', { type: 'button', textContent: 'Keep both' });
      replace.title = 'The file is saved over the prefab here, as its next revision (the one before is kept)';
      both.title = 'The file is stored as a prefab of its own, with "(imported)" after its name';
      replace.onclick = () => importDocument(doc, 'replace'); both.onclick = () => importDocument(doc, 'copy');
      note(`The library already has this prefab, as “${here.name}” (revision ${here.revision}).`, el('div', { className: 'row' }, replace, both, dismiss('Cancel')));
      return;
    }
    refresh();
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
    refresh, importDocument, freeName,
    list: () => prefabs,
    byName: name => prefabs.find(p => !p.error && p.name.toLowerCase() === name.trim().toLowerCase()) ?? null,
  };
}
