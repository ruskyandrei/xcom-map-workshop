// The Open window's Prefabs side (the prefab menus plan, stage M3): the prefab library as cards with their pictures,
// to open one in the builder, and the one place the library's files are managed (rename, duplicate, export, delete,
// import; decision P9). The window's other side, Maps, is the map browser (map_browser.js); both heads carry the same
// switch, Maps and Prefabs with their counts (openSwitch, below), so the two dialogs read as one window, titled Open.
//
// createPrefabBrowserWindow takes its elements and what it calls as one argument object (map_menu.js makes it). It
// draws from the library store (editor_state.js's prefabLibrary, prefab_library.js), read when the window shows; it
// keeps the keyboard as the other dialogs do (modal.js holds Tab; the arrows move between cards; Esc closes).
import { plural } from './dom_words.js';
import { builder, builderMode, data, prefabLibrary } from './editor_state.js';
import { nextStop, tabOrder } from './modal.js';
import { prefabChips, prefabMaps, prefabWords } from './prefabs.js';

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };
const when = iso => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '');
const NEW = 'new';     // the New prefab card's key

/**
 * The switch both sides of the Open window carry in their heads: Maps and Prefabs with their counts, `lit` the side
 * this head is on. onSide(side): show that side. Gives paint(counts), counts { maps, prefabs } (null: not known yet).
 */
export function openSwitch(head, lit, onSide) {
  const seg = el('div', { className: 'seg opensides' });
  seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'What to open');
  const parts = {};
  for (const [side, word, icon] of [['maps', 'Maps', 'i-map'], ['prefabs', 'Prefabs', 'i-prefab']]) {
    const button = el('button', { type: 'button', className: side === lit ? 'on' : '' });
    button.dataset.side = side;
    button.setAttribute('aria-pressed', side === lit);
    button.innerHTML = `<svg class="i"><use href="#${icon}"/></svg>`;
    const count = el('small');
    button.append(word, count);
    button.title = side === lit ? `The ${word.toLowerCase()} you can open` : `Show the ${word.toLowerCase()} instead`;
    button.onclick = () => { if (side !== lit) onSide(side); };
    parts[side] = count;
    seg.append(button);
  }
  head.querySelector('h2').after(seg);
  return {
    paint({ maps = null, prefabs = null } = {}) {
      parts.maps.textContent = maps == null ? '' : String(maps);
      parts.prefabs.textContent = prefabs == null ? '' : String(prefabs);
    },
    focus() { seg.querySelector('button.on').focus(); },
  };
}

/**
 * els: root, form, filter, order, place, note, cards, acts, importButton, file, count, ok, cancel, close.
 * haveMap(package): whether this install has that map (null: not known). onOpen(id): open that prefab in the builder;
 * onNew(): an empty builder; hint(message).
 */
export function createPrefabBrowserWindow({ els, haveMap, onOpen, onNew, hint }) {
  let chosen = null, order = 'saved', lastFocus = null, busy = null, listening = false;   // busy: { id, mode: 'rename' | 'delete' }
  const library = () => prefabLibrary;
  const openId = () => (builderMode ? builder.doc?.id ?? null : null);
  const cards = () => [...els.cards.querySelectorAll('.card')];

  function note(message, ...actions) {
    els.note.hidden = !message;
    els.note.replaceChildren(...(message ? [el('p', { textContent: message }), ...actions] : []));
  }
  const dismiss = (label = 'OK') => { const b = el('button', { type: 'button', textContent: label }); b.onclick = () => note(''); return b; };

  // The prefabs shown: filtered by name or map, in the order chosen (last saved first, or by name).
  function shown() {
    const words = els.filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const list = library().usable().filter(p => words.every(w => `${p.name} ${(p.maps ?? []).join(' ')}`.toLowerCase().includes(w)));
    return list.sort(order === 'name' ? (a, b) => String(a.name).localeCompare(String(b.name))
      : (a, b) => String(b.savedAt ?? '').localeCompare(String(a.savedAt ?? '')) || String(a.name).localeCompare(String(b.name)));
  }
  function card(p) {
    const item = el('div', { className: 'card prefabcard', tabIndex: -1 });
    item.setAttribute('role', 'option'); item.dataset.id = p ? p.id : NEW;
    if (!p) {
      item.classList.add('newcard');
      item.append(el('span', { className: 'newart', innerHTML: '<svg class="i"><use href="#i-add"/></svg>' }),
                  el('strong', { textContent: 'New prefab' }), el('small', { textContent: 'An empty builder' }));
      item.title = 'Open an empty prefab builder';
    } else {
      const picture = el('img', { alt: '', loading: 'lazy', className: p.picture ? '' : 'none' });
      if (p.picture) picture.src = library().picture(p);
      const tags = el('span', { className: 'tags' });
      if (p.id === openId()) tags.append(el('span', { className: 'tag open', textContent: 'open', title: 'The prefab open in the builder' }));
      for (const chip of prefabChips(p, haveMap)) tags.append(el('span', { className: 'tag later', textContent: chip.text, title: chip.title }));
      item.append(picture, el('strong', { textContent: p.name }), el('small', { textContent: prefabWords(p) }),
                  el('small', { textContent: prefabMaps(p) }), el('small', { textContent: `Revision ${p.revision} · ${when(p.savedAt)}` }), tags);
      item.title = [p.name, prefabWords(p), p.maps?.length ? `Pieces of ${p.maps.join(', ')}` : '', `Revision ${p.revision} · ${p.file}`].filter(Boolean).join('\n');
    }
    item.onclick = () => choose(item.dataset.id, true);
    item.ondblclick = () => { choose(item.dataset.id, true); submit(); };
    return item;
  }
  function render() {
    if (els.root.hidden) return;
    const all = library().usable(), list = shown();
    els.cards.replaceChildren(card(null), ...list.map(card));
    const ids = new Set([NEW, ...list.map(p => p.id)]);
    if (!ids.has(chosen)) chosen = list[0]?.id ?? NEW;
    els.count.textContent = !library().loaded ? (library().error ? '' : 'Reading the library…')
      : list.length === all.length ? plural(all.length, 'prefab') : `${list.length} of ${plural(all.length, 'prefab')}`;
    els.count.title = library().folder() ? `Kept in ${library().folder()}` : '';
    if (library().error) note(library().error.status === 404 ? 'This viewer keeps no prefab library.' : `The prefab library could not be read: ${library().error.message}`);
    paintChosen(false);
  }
  // The chosen card marked, its actions under the cards, Open's words.
  function paintChosen(focus) {
    for (const c of cards()) { const on = c.dataset.id === chosen; c.classList.toggle('on', on); c.setAttribute('aria-selected', on); }
    const at = cards().find(c => c.dataset.id === chosen);
    at?.scrollIntoView({ block: 'nearest' });
    if (focus) at?.focus();
    acts();
    const p = chosen === NEW ? null : library().byId(chosen);
    els.ok.textContent = chosen === NEW ? 'New prefab' : 'Open';
    els.ok.disabled = !chosen || Boolean(busy);
    els.ok.title = p && p.id === openId() ? `${p.name} is open: Open closes this window` : '';
  }
  function choose(id, focus = false) {
    if (busy && busy.id !== id) busy = null;
    chosen = id;
    paintChosen(focus);
  }
  // The chosen prefab's actions: Rename, Duplicate, Export, Delete (rename and delete asking in the row itself).
  function acts() {
    const p = chosen && chosen !== NEW ? library().byId(chosen) : null;
    els.acts.replaceChildren();
    els.acts.hidden = !p;
    if (!p) return;
    const button = (label, title, run, warn = false) => {
      const b = el('button', { type: 'button', className: `textbutton${warn ? ' warn' : ''}`, textContent: label, title });
      b.onclick = run; return b;
    };
    if (busy?.mode === 'rename') {
      const input = el('input', { type: 'text', value: p.name, maxLength: 120, className: 'prefabrename', spellcheck: false });
      input.setAttribute('aria-label', 'The prefab\'s name');
      input.onkeydown = e => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); rename(p, input.value.trim()); }
        else if (e.key === 'Escape') { e.preventDefault(); busy = null; paintChosen(true); }
      };
      els.acts.append(input, el('small', { textContent: 'Enter renames it · Esc leaves it' }));
      setTimeout(() => { input.focus(); input.select(); }, 0);
    } else if (busy?.mode === 'delete') {
      els.acts.append(el('strong', { textContent: `Delete ${p.name}?` }),
        el('small', { textContent: 'Its file is kept in the library\'s deleted folder. What is placed in maps stays.' }),
        button('Delete it', 'Take the prefab out of the library', () => remove(p), true),
        button('Keep it', 'Leave the prefab as it is', () => { busy = null; paintChosen(true); }));
    } else {
      els.acts.append(el('strong', { textContent: p.name }),
        button('Rename', 'Give the prefab another name', () => { busy = { id: p.id, mode: 'rename' }; paintChosen(false); }),
        button('Duplicate', 'A copy of the prefab, to change on its own', () => duplicate(p)),
        button('Export', 'Save the prefab as a file to pass on', () => exportFile(p)),
        button('Delete', 'Take the prefab out of the library', () => { busy = { id: p.id, mode: 'delete' }; paintChosen(false); }));
    }
    els.ok.disabled = Boolean(busy);
  }
  const fail = (what, error) => hint(`${what}: ${error.message}`);
  async function rename(p, name) {
    busy = null;
    try { if (await library().rename(p, name)) hint(`Renamed to ${name}`); }
    catch (error) { fail('Not renamed', error); }
    render();
  }
  async function duplicate(p) {
    try { const name = await library().duplicate(p); hint(`Made ${name}`); chosen = library().byName(name)?.id ?? chosen; }
    catch (error) { fail('Not duplicated', error); }
    render();
  }
  async function exportFile(p) {
    try { await library().exportFile(p); hint(`Exported ${p.name}: the file holds references and numbers only, no game data`); }
    catch (error) { fail('Not exported', error); }
  }
  async function remove(p) {
    busy = null;
    try { await library().remove(p); hint(`Deleted ${p.name} · its file is kept in the library's deleted folder`); }
    catch (error) { fail('Not deleted', error); }
    render();
  }
  // A file from elsewhere: checked by the server; one whose id is here already asks what to do. Replace replaces the
  // revision the question showed (review finding 4): one saved meanwhile asks again, with its revision now.
  async function importDocument(doc, clash = null, revision = null) {
    try {
      const taken = await library().importDocument(doc, clash, revision);
      note('');
      hint(taken.replaced ? `Replaced ${taken.name} with the file (revision ${taken.revision})` : `Imported ${taken.name}`);
      chosen = library().byName(taken.name)?.id ?? chosen;
      render();
    } catch (error) {
      const here = error.body?.clash;
      if (error.status !== 409 || !here) { note(`Not imported. ${error.message}`, dismiss()); return; }
      const replace = el('button', { type: 'button', textContent: 'Replace it' }), both = el('button', { type: 'button', textContent: 'Keep both' });
      replace.title = `The file is saved over revision ${here.revision} of the prefab here, as its next revision (the one before is kept)`;
      both.title = 'The file is stored as a prefab of its own, with "(imported)" after its name';
      replace.onclick = () => importDocument(doc, 'replace', here.revision); both.onclick = () => importDocument(doc, 'copy');
      const again = error.body?.changed ? 'It was saved again meanwhile. ' : '';
      note(`${again}The library already has this prefab, as “${here.name}” (revision ${here.revision}).`, el('div', { className: 'row' }, replace, both, dismiss('Cancel')));
    }
  }
  async function importFile(file) {
    if (!file) return;
    if (file.size > 16 << 20) { note('Not imported. The file is too large to be a prefab.', dismiss()); return; }
    let doc;
    try { doc = JSON.parse(await file.text()); } catch { note('Not imported. The file is not a prefab (it is not JSON).', dismiss()); return; }
    await importDocument(doc);
  }
  function submit() {
    if (busy || !chosen) return;
    if (chosen === NEW) { close(); onNew(); return; }
    if (chosen === openId()) { close(); return; }
    close();
    onOpen(chosen);
  }
  // The arrows: left and right one card, up and down a row; from the filter they move the choice, from a card the focus.
  function move(key) {
    const all = cards();
    if (!all.length) return;
    const across = Math.max(1, Math.round(els.cards.clientWidth / (all[0].getBoundingClientRect().width || 1)));
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -across, ArrowDown: across }[key];
    const at = all.findIndex(c => c.dataset.id === chosen);
    const next = all[Math.max(0, Math.min(all.length - 1, (at < 0 ? 0 : at) + step))];
    choose(next.dataset.id, Boolean(document.activeElement?.closest?.('.card')));
  }

  els.form.addEventListener('submit', e => { e.preventDefault(); submit(); });
  els.filter.addEventListener('input', () => { busy = null; render(); });
  for (const button of els.order.querySelectorAll('button')) {
    button.onclick = () => {
      order = button.dataset.value;
      for (const b of els.order.querySelectorAll('button')) b.classList.toggle('on', b === button);
      render();
    };
  }
  els.importButton.onclick = () => { els.file.value = ''; els.file.click(); };
  els.file.onchange = () => importFile(els.file.files[0]);
  els.cancel.onclick = () => close();
  els.close.onclick = () => close();
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key, inText = e.target.matches?.('input[type=text]');
    if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f', 'b'].includes(key.toLowerCase())) { e.preventDefault(); if (key.toLowerCase() === 'f') els.filter.focus(); }
    else if (key === 'Escape') {
      e.preventDefault();
      if (e.target === els.filter && els.filter.value) { els.filter.value = ''; render(); } else close();
    } else if (['ArrowDown', 'ArrowUp'].includes(key) && !inText) { e.preventDefault(); move(key); }
    else if (['ArrowLeft', 'ArrowRight'].includes(key) && e.target.closest('.card')) { e.preventDefault(); move(key); }
    else if (key === 'Enter' && e.target.closest('.card')) { e.preventDefault(); submit(); }
    e.stopPropagation();
  });
  // Tab (modal.js) goes round the dialog's controls but the cards, which the arrow keys move between
  tabOrder(els.root, (e, stops) => nextStop(e, stops.filter(c => !c.classList.contains('card'))));

  function show() {
    if (!listening && library()) { library().onChange(render); listening = true; }
    lastFocus = document.activeElement;
    els.root.hidden = false;
    busy = null; note('');
    chosen = openId() ?? null;
    els.place.hidden = builderMode || !data;
    render();
    library()?.refresh();
    els.filter.focus(); els.filter.select();
  }
  function close(restore = true) {
    if (els.root.hidden) return;
    els.root.hidden = true;
    busy = null;
    if (!restore) return;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, render, get open() { return !els.root.hidden; } };
}
