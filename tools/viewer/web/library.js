// The Add panel's "All maps": the pieces of every map of the game install (tools/viewer/library.py's index, one entry
// for each distinct piece with the maps it is placed in), to place in the open map. The Build brings a placed piece
// from its home map with what it needs (tools/bake/transplant.py).
// The list is drawn only where it shows: the index holds thousands of entries. A row's picture is kept by the server
// once drawn; until then the page reads the piece (the server exports it on first request) and draws it.
// The user's favourites and recently used pieces are a file beside the settings (GET and PUT /library/state.json), so
// they are the same in every browser; the panel's own view choices stay in this browser.
// The base maps' effects and ambient sounds are listed too (the effects and sounds plan, Part E, stage FX4): a row
// with the Effects view's spark or speaker for its picture, sorted into the panel's effect and sound kinds; placing
// one is app.js's (an effect's template, /library/effect.json). Their lens flares too (stage FX6b): a row with the
// view's star.
// (The look picker, which was a mode of this list, is a panel of its own: look_picker.js.)

import { pieceKind, inKind, setKindOptions, effectKind, SOFT } from './piece_categories.js';
import { pieceRow } from './pieces.js';
import { drawEffectIcon } from './effects_view.js';
import { call, hex16 } from './api.js';

// What the library only holds back (SOFT, piece_categories.js: compiler.py FOREIGN_SOFT): hidden in its own map,
// linked to other pieces, of a kind not brought before, waiting for a game test. Such a piece is placed as any other;
// what shows in the game is tagged (SOFT_TAGS, as compiler.py FOREIGN_WORDS warns of it), never that it is untried (the
// user, 16 November 2026). One that needs something that can't be brought ('closure') can't be placed, nor an effect or
// sound the editor can't bring ('unavailable': a landing's actor, one riding on another).
export { SOFT };
const SOFT_TAGS = { hidden: ['Hidden', 'Hidden in its own map: a helper, not something to see.'],
                    assembly: ['Linked', 'Linked to other pieces in its own map (a car\'s body and its glass, a prop and what it turns into).'] };
const ROW = 61;         // a row's height, CSS pixels (style.css .libitem.lib)
const THUMB = 48;
const RECENT = 30;
const VIEW = 'workshop.libraryView';
const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name) || a.key.localeCompare(b.key),
  size: (a, b) => b.extent - a.extent || a.name.localeCompare(b.name),
  count: (a, b) => (b.placed?.count ?? 0) - (a.placed?.count ?? 0) || a.name.localeCompare(b.name),
  maps: (a, b) => (b.placed?.maps ?? 0) - (a.placed?.maps ?? 0) || a.name.localeCompare(b.name),
};
const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };
const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;
const kb = bytes => (bytes >= 1 << 20 ? `${(bytes / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
const json = (url, method = 'GET', body = undefined) => call(method, url, body, { fallback: r => `The library didn't answer (${r.status})` });

// The key an effect's picture is kept under: its entry's and the drawing's version, so a better drawing replaces the
// pictures made by an older one (the server keeps a picture under 16 hex digits)
const PICTURE_VERSION = 2;
const pictureKey = entry => (entry.effect ? hex16(`${entry.key}|likeness${PICTURE_VERSION}`) : entry.key);
/**
 * els: box (the scope's part of the panel), scan (the scan offer), filter, kind, home, sort, placeable, elsewhere,
 * favourites (checkboxes), list, foot.
 * mapName(): the open map's package; pixelRatio(); template(source): a promise of what draws the piece (app.js
 * libraryTemplate); paint(template, canvas): draw it into a row's canvas, called while a frame is drawn;
 * recipesForScene(): the map's or builder's light and cover rows; paintRecipe(entry, canvas): draw a cover thumbnail;
 * onChoose(entry or null); onChooseRecipe(entry or null); hint(message).
 */
export function createLibraryBrowser({ els, mapName, pixelRatio, template, paint, recipesForScene, paintRecipe,
                                       onChoose, onChooseRecipe, hint, recall, remember, effectPicture = null, paintObject = null, onHover = null }) {
  let index = null, entries = [], byKey = new Map(), shown = [], chosen = null, status = null, loading = null, scanTimer = null;
  let state = null, stateLoad = null, here = -1;
  let recipes = null;
  const kept = new Set(), failed = new Set(), pictures = new Map();   // thumbnails: on the server; not drawable; loaded images
  const rows = new Map(), toPaint = [];
  let making = false;
  const view = (() => { try { return JSON.parse(recall(VIEW)) ?? {}; } catch { return {}; } })();
  const anyMap = () => new Option('From any map', 'all');
  els.home.replaceChildren(anyMap());
  const spacer = el('div', { className: 'libspace' }), windowed = el('div', { className: 'libwindow' });
  spacer.append(windowed); els.list.append(spacer);
  // a row under the list while a picture's piece is read from its map (the first read of a map is slow): the busy
  // mark (map buildings plan, 4a), put up after a third of a second; the list stays usable meanwhile
  const reading = el('div', { className: 'busyrow', hidden: true }, el('span', { className: 'busyring' }), el('span'));
  els.foot.after(reading);
  let readingTimer = null;
  function readingFrom(entry) {
    clearTimeout(readingTimer);
    if (!entry) { reading.hidden = true; return; }
    readingTimer = setTimeout(() => { reading.lastChild.textContent = `Reading pieces from ${entry.source.package}…`; reading.hidden = els.box.hidden; }, 330);
  }
  els.sort.value = SORTS[view.sort] ? view.sort : 'name';
  els.placeable.checked = view.placeable !== false;
  els.elsewhere.checked = Boolean(view.elsewhere);

  // -- the index -----------------------------------------------------------------------------------------------------
  function take(answer) {
    status = answer.status; index = answer.index;
    kept.clear(); for (const k of answer.thumbs ?? []) kept.add(k);
    entries = []; byKey = new Map(); rows.clear(); windowed.replaceChildren();
    if (!index) {
      els.home.replaceChildren(anyMap());
      setKindOptions(els.kind, recipes);
      return;
    }
    const name = mapName().toLowerCase();
    here = index.donors.findIndex(d => d.package.toLowerCase() === name);
    for (const e of index.entries) {
      if (e.family === 'effect' || e.family === 'sound' || e.family === 'flare') {
        // an effect, a sound or a lens flare: no mesh, no size; its kind the panel's (effect or sound kinds), its
        // package its system's, its first wave's or its flare template's
        const kind = effectKind(e.family, e.kind), pkg = String(e.system ?? e.flare ?? e.waves?.[0] ?? e.cue ?? '').split('.')[0];
        const entry = { ...e, kind, group: e.kind, effect: e.family, floor: false, id: `lib-${e.key}`, library: true, extent: 0,
          here: e.placed.in.includes(here), pkg,
          text: [e.name, e.family === 'effect' ? 'effect particles' : e.family === 'flare' ? 'lens flare glare' : 'sound ambient', e.kind, e.actorClass, e.source.package,
                 e.system ?? '', e.flare ?? '', ...(e.waves ?? []), e.sharedCue ? e.cue : '', e.startsOn === false ? 'starts off' : '',
                 ...(e.emitters ?? [])].join(' ').toLowerCase() };
        entries.push(entry); byKey.set(e.key, entry);
        continue;
      }
      const kind = pieceKind(e.actorClass, e.family), floor = Boolean(e.floorMaps?.length);
      const entry = { ...e, kind, floor, id: `lib-${e.key}`, library: true, extent: Math.hypot(...e.size), here: e.placed.in.includes(here),
        pkg: e.mesh.split('.')[0],
        text: [e.name, e.mesh, kind, floor ? 'floor' : '', e.actorClass, e.recipe.archetype, e.source.package,
               ...e.recipe.parts.flatMap(p => p.materials)].join(' ').toLowerCase() };
      entries.push(entry); byKey.set(e.key, entry);
    }
    const homes = new Map();
    for (const e of entries) {
      for (const n of e.placed.in) homes.set(n, (homes.get(n) ?? 0) + 1);
    }
    const keepValue = (select, options, value) => { select.replaceChildren(...options); if ([...select.options].some(o => o.value === value)) select.value = value; };
    setKindOptions(els.kind, [...entries, ...recipes]);
    keepValue(els.home, [anyMap(), ...[...homes].map(([n, count]) => [index.donors[n].package, n, count])
      .sort((a, b) => a[0].localeCompare(b[0])).map(([pkg, n, count]) => new Option(`${pkg} (${count.toLocaleString()})`, String(n)))], els.home.value);
  }
  function load() {
    loading ??= json('/library.json?index=1').then(answer => { take(answer); offer(); render(); })
      .catch(error => { status = null; els.scan.hidden = false; els.scan.replaceChildren(el('p', { textContent: error.status === 404
        ? 'This viewer shows one export, without the game install\'s other maps.' : `The library could not be read: ${error.message}` })); })
      .finally(() => { loading = null; });
    return loading;
  }
  // The scan: offered where there is no index (as a map's first open offers its export), followed while it runs.
  function offer() {
    clearTimeout(scanTimer);
    const scan = status?.scan, running = scan?.state === 'running';
    els.scan.hidden = Boolean(index) && !running;
    if (els.scan.hidden) return;
    if (running) {
      const p = scan.progress, share = p?.total ? p.done / p.total : 0;
      const bar = el('div', { className: 'loadbar' }, el('span'));
      bar.firstChild.style.width = `${(100 * share).toFixed(1)}%`;
      els.scan.replaceChildren(el('p', { textContent: p?.total ? `Reading the game's maps: ${p.done} of ${p.total}…` : 'Reading the game\'s maps…' }), bar);
      scanTimer = setTimeout(async () => {
        try { status = { ...status, scan: await json('/library/scan.json') }; } catch { /* asked again */ }
        if (status.scan?.state === 'running') offer(); else if (status.scan?.state === 'failed') offer(); else load();
      }, 400);
      return;
    }
    const button = el('button', { type: 'button', className: 'primary', textContent: 'Read the game\'s maps' });
    button.onclick = startScan;
    els.scan.replaceChildren(
      el('p', { textContent: scan?.state === 'failed' ? `Reading the maps failed: ${scan.error ?? 'see the server\'s output'}.`
        : 'The pieces of the game\'s other maps are listed here once the editor has read them. It reads every map of the install, '
          + 'which takes about half a minute, once; nothing in the game is changed.' }), button);
  }
  async function startScan() {
    try { status = { ...(status ?? {}), scan: await json('/library/scan', 'POST') }; offer(); }
    catch (error) { hint(`The maps could not be read: ${error.message}`); }
  }

  // -- favourites and recently used ----------------------------------------------------------------------------------
  // (a failed read is not kept: the next star or placed piece asks again, and says why if it fails again; review
  // finding 31)
  let stateError = null;
  function loadState() {
    stateLoad ??= json('/library/state.json').then(s => { state = s; stateError = null; render(); })
      .catch(error => { state = null; stateLoad = null; stateError = error.message; });
    return stateLoad;
  }
  const favourite = key => Boolean(state?.favourites.some(f => f.key === key));
  async function saveState(change, again = true) {
    if (!state) await loadState();
    if (!state) { hint(`The favourites file could not be read (${stateError ?? 'no answer'}), so this is not kept`); return; }
    const document = change({ favourites: [...state.favourites], recent: [...state.recent] });
    try {
      state = await json('/library/state.json', 'PUT', { expectedRevision: state.revision, document });
    } catch (error) {
      // changed in another window: its state read, and the change made on that
      if (error.status === 409 && again) { stateLoad = null; await loadState(); return saveState(change, false); }
      hint(`Not kept: ${error.message}`);
    }
    render();
  }
  const now = () => new Date().toISOString().slice(0, 19) + 'Z';
  const toggleFavourite = entry => saveState(s => ({ ...s, favourites: favourite(entry.key)
    ? s.favourites.filter(f => f.key !== entry.key) : [...s.favourites, { key: entry.key, name: entry.name, addedAt: now() }] }));
  /** A piece was placed: it heads the recently used ones. */
  const used = entry => saveState(s => ({ ...s, recent: [{ key: entry.key, name: entry.name, usedAt: now() },
                                                         ...s.recent.filter(r => r.key !== entry.key)].slice(0, RECENT) }));

  // -- rows ------------------------------------------------------------------------------------------------------------
  function row(entry) {
    if (rows.has(entry.key)) return rows.get(entry.key);
    if (entry.light || entry.cover || entry.zone || entry.spawnAdd) {     // the recipes: lights, cover, zones, spawn points
      const item = pieceRow(entry, pixelRatio(), () => onChooseRecipe(chosen?.key === entry.key ? null : entry));
      item.classList.add('lib');
      item.dataset.key = entry.key;
      rows.set(entry.key, item);
      return item;
    }
    const soft = !entry.placeable && SOFT.includes(entry.blocked), tag = soft ? SOFT_TAGS[entry.blocked] : null;
    const item = el('div', { className: `libitem lib${entry.placeable || soft ? '' : ' off'}${entry.missing ? ' missing' : ''}`, tabIndex: 0 });
    item.setAttribute('role', 'listitem'); item.dataset.id = entry.id; item.dataset.key = entry.key;
    const thumb = el('canvas');
    thumb.width = thumb.height = Math.round(THUMB * pixelRatio());
    const star = el('button', { type: 'button', className: 'star', textContent: '★' });
    star.onclick = e => { e.stopPropagation(); toggleFavourite(entry); };
    if (entry.missing) {
      item.append(thumb, el('span', {}, el('strong', { textContent: entry.name }),
        el('small', { textContent: 'A favourite this install\'s maps don\'t have' })), el('span', { className: 'tags' }, star));
      item.title = 'Kept as a favourite; no map of this game install has the piece';
    } else if (entry.effect) {
      effectRow(entry, item, thumb, star, soft, tag);
    } else {
      const [w, d, h] = entry.size.map(Math.round), maps = entry.placed.maps;
      const where = maps === 1 ? entry.source.package : `${maps} maps`;
      const tags = el('span', { className: 'tags' }, star);
      if (entry.here) tags.append(el('span', { className: 'tag', textContent: 'Here', title: 'This map has the piece too' }));
      if (tag) tags.append(el('span', { className: 'tag', textContent: tag[0], title: tag[1] }));
      else if (!entry.placeable && !soft) tags.append(el('span', { className: 'tag later', textContent: 'Later', title: entry.reason }));
      item.append(thumb, el('span', {}, el('strong', { textContent: entry.name }),
        el('small', { textContent: `${entry.kind} · ${entry.pkg}` }),
        el('small', { textContent: `${w} × ${d} × ${h} · ${where}` })), tags);
      item.title = [entry.mesh, ...new Set(entry.recipe.parts.flatMap(p => p.materials)).values()].map((t, i) => (i ? `Material: ${t}` : t))
        .concat(`Placed ${plural(entry.placed.count, 'time')} in ${plural(maps, 'map')} (${entry.placed.in.slice(0, 8).map(n => index.donors[n].package).join(', ')}${maps > 8 ? ', …' : ''}); brought from ${entry.source.package}`,
                ...(entry.assembly ? [`${entry.assembly.members} pieces placed as one`] : []),
                entry.placeable || soft ? `Adds up to ${kb(entry.closure.bytes)} to the map (less where the map has its meshes and textures already)`
                  : `Can't be placed yet: ${entry.reason}`, ...(tag ? [tag[1]] : [])).join('\n');
      const choose = () => {
        if (!entry.placeable && !soft) { hint(`${entry.name} can't be placed yet. ${entry.reason}`); return; }
        onChoose(chosen?.key === entry.key ? null : entry);
      };
      item.onclick = choose;
      item.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } };
    }
    item.thumb = thumb; item.star = star;
    rows.set(entry.key, item);
    return item;
  }
  // An effect's or a sound's row: its picture the Effects view's marker, its lines what it plays (an effect's system
  // and the kinds of its emitters, a sound's wave and length) and where it is placed
  function effectRow(entry, item, thumb, star, soft, tag) {
    const maps = entry.placed.maps, where = maps === 1 ? entry.source.package : `${maps} maps`;
    const sound = entry.effect === 'sound', flare = entry.effect === 'flare', label = sound ? 'Sound' : 'Effect';
    const tags = el('span', { className: 'tags' }, star);
    if (entry.here) tags.append(el('span', { className: 'tag', textContent: 'Here', title: 'This map has it too' }));
    if (entry.startsOn === false) tags.append(el('span', { className: 'tag', textContent: 'Starts off',
      title: 'It starts off in its map and waits for the map\'s script to switch it on: a copy comes with no script, so it stays off' }));
    if (tag) tags.append(el('span', { className: 'tag', textContent: tag[0], title: tag[1] }));
    else if (!entry.placeable && !soft) tags.append(el('span', { className: 'tag later', textContent: entry.blocked === 'unavailable' ? 'Not brought' : 'Later', title: entry.reason }));
    const what = sound ? [entry.seconds ? `${entry.seconds.toFixed(entry.seconds < 10 ? 1 : 0)} s` : null, entry.sharedCue ? 'shared cue' : null]
      : flare ? [entry.colour ? `colour ${entry.colour.slice(0, 3).map(v => Number(Number(v).toFixed(2))).join(', ')}` : null]
      : [entry.emitters?.length ? entry.emitters.join(', ') : null, entry.lit ? 'lit' : null];
    item.append(thumb, el('span', {}, el('strong', { textContent: entry.name }),
      el('small', { textContent: flare ? `Lens flare · ${entry.pkg}` : `${label}: ${entry.group} · ${entry.pkg}` }),
      el('small', { textContent: [...what.filter(Boolean), where].join(' · ') })), tags);
    item.title = [sound ? (entry.waves?.length ? entry.waves.map(w => `Wave: ${w}`).join('\n') : 'No wave') : flare ? `Flare template: ${entry.flare}` : `Particle system: ${entry.system}`,
      ...(sound && entry.sharedCue ? [`Its cue is a game asset others play too: ${entry.cue}`] : []),
      ...(entry.scripted ? ['Its map\'s script names it: a copy is an ordinary one, which no script switches'] : []),
      `Placed ${plural(entry.placed.count, 'time')} in ${plural(maps, 'map')} (${entry.placed.in.slice(0, 8).map(n => index.donors[n].package).join(', ')}${maps > 8 ? ', …' : ''}); brought from ${entry.source.package}`,
      entry.placeable || soft ? `Adds up to ${kb(entry.closure.bytes)} to the map (less where the map has its ${sound ? 'waves' : flare ? 'flare template' : 'particle system'} already)`
        : `Can't be placed: ${entry.reason}`, ...(tag ? [tag[1]] : [])].join('\n');
    const choose = () => {
      if (!entry.placeable && !soft) { hint(`${entry.name} can't be placed. ${entry.reason}`); return; }
      onChoose(chosen?.key === entry.key ? null : entry);
    };
    item.onclick = choose;
    item.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } };
    // an effect plays beside its row while the pointer is on it
    if (!sound && !flare && onHover) { item.onmouseenter = () => onHover(entry, item); item.onmouseleave = () => onHover(null, item); }
  }
  function filtered() {
    const words = els.filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const kind = els.kind.value, home = els.home.value === 'all' ? null : Number(els.home.value);
    const list = entries.filter(e => inKind(e, kind) && (home == null || (kind === 'floors' ? e.floorMaps : e.placed.in).includes(home))
      && (!els.placeable.checked || e.placeable) && (!els.elsewhere.checked || !e.here)
      && (!els.favourites.checked || favourite(e.key)) && words.every(w => e.text.includes(w)));
    if (home == null && !els.favourites.checked) {
      list.push(...recipes.filter(e => inKind(e, kind) && words.every(w => e.text.includes(w))));
    }
    if (els.sort.value === 'recent') {
      const order = new Map((state?.recent ?? []).map((r, i) => [r.key, i]));
      list.sort((a, b) => (order.get(a.key) ?? 1e9) - (order.get(b.key) ?? 1e9) || SORTS.name(a, b));
    } else list.sort(SORTS[els.sort.value]);
    // favourites this install's library lacks, by their kept names, last
    if (els.favourites.checked && state) for (const f of state.favourites)
      if (kind === 'all' && home == null && !byKey.has(f.key) && words.every(w => f.name.toLowerCase().includes(w)))
        list.push({ key: f.key, id: `lib-${f.key}`, name: f.name, missing: true, placeable: false });
    return list;
  }
  function render() {
    if (els.box.hidden) return;
    remember(VIEW, JSON.stringify({ sort: els.sort.value, placeable: els.placeable.checked, elsewhere: els.elsewhere.checked }));
    shown = filtered();
    spacer.style.height = `${shown.length * ROW}px`;
    draw();
    const stale = status?.stale ? ` · the game's maps have changed since they were read`
      : index && !index.floorKinds ? ' · read the maps again to list their floors' : '';
    const mapCount = shown.filter(e => e.library || e.missing).length, recipeCount = shown.length - mapCount;
    const counts = [];
    if (mapCount) {
      counts.push(mapCount === entries.length ? plural(entries.length, 'piece') : `${mapCount.toLocaleString()} of ${plural(entries.length, 'piece')}`);
      if (index) counts[0] += ` from ${plural(index.donors.length, 'map')}`;
    }
    if (recipeCount) counts.push(plural(recipeCount, 'recipe'));
    els.foot.replaceChildren(shown.length
      ? `${counts.join(' and ')} · click one, then click in the view to place it${stale}`
      : `No piece matches${stale}`);
    if (stale) {
      const again = el('button', { type: 'button', className: 'textbutton', textContent: 'Read them again' });
      again.onclick = startScan;
      els.foot.append(' ', again);
    }
  }
  // The rows in view (and a few either side), and their pictures asked for.
  function draw() {
    const first = Math.max(0, Math.floor(els.list.scrollTop / ROW) - 4);
    const last = Math.min(shown.length, Math.ceil((els.list.scrollTop + els.list.clientHeight) / ROW) + 4);
    windowed.style.transform = `translateY(${first * ROW}px)`;
    const visible = shown.slice(first, last);
    windowed.replaceChildren(...visible.map(row));
    for (const e of visible) {
      const item = rows.get(e.key);
      item.classList.toggle('on', e.key === chosen?.key);
      if (!item.star) continue;
      item.star.classList.toggle('on', favourite(e.key));
      item.star.title = favourite(e.key) ? 'A favourite: click to take it off the list' : 'Add to the favourites';
      if (!e.missing) picture(e, item.thumb);
    }
    make();
  }
  function picture(entry, canvas) {
    if (canvas.dataset.drawn) return;
    // an effect's or a sound's marker first; an effect's likeness over it once it is drawn (a sound has no look)
    if (entry.effect && !canvas.dataset.icon) { drawEffectIcon(entry.effect, entry.startsOn === false, canvas); canvas.dataset.icon = '1'; }
    if (entry.effect && (entry.effect !== 'effect' || !effectPicture)) { canvas.dataset.drawn = '1'; return; }
    if (failed.has(entry.key)) { if (entry.effect) canvas.dataset.drawn = '1'; return; }    // its marker stays
    const k = pictureKey(entry);
    if (!kept.has(k)) return;       // make() draws it
    if (!pictures.has(k)) {
      const image = new Image();
      pictures.set(k, image);
      image.onload = () => { for (const c of [rows.get(entry.key)?.thumb].filter(Boolean)) show(c, image); };
      image.onerror = () => { kept.delete(k); pictures.delete(k); make(); };
      image.src = `/library/thumbs/${k}.png`;
    } else if (pictures.get(k).complete) show(canvas, pictures.get(k));
  }
  function show(canvas, image) {
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    canvas.dataset.drawn = '1';
    if (canvas.dataset.icon) canvas.dataset.likeness = '1';
  }
  // A picture the server doesn't keep yet: the piece read (one at a time, the last row to come into view first),
  // drawn in a frame (drawThumbs), and put to the server.
  async function make() {
    if (making || els.box.hidden) return;
    const next = [...windowed.children].map(item => byKey.get(item.dataset.key))
      .filter(e => e && (!e.effect || (e.effect === 'effect' && effectPicture && e.placeable)) && !kept.has(pictureKey(e)) && !failed.has(e.key)
        && !rows.get(e.key).thumb.dataset.drawn).at(0);
    if (!next) return;
    making = true;
    readingFrom(next);
    try {
      if (next.effect) {
        // its likeness, warm and with its textures read: drawn in a frame like a piece's picture
        const paintable = await effectPicture(next);
        if (!paintable) throw Error('not drawn');
        toPaint.push({ entry: next, paintable });
      } else toPaint.push({ entry: next, template: await template(next.source) });
      readingFrom(null);
    }
    catch {
      failed.add(next.key); making = false; readingFrom(null);
      if (next.effect && rows.get(next.key)) rows.get(next.key).thumb.dataset.drawn = '1';
      make();
    }
  }
  /** Called each frame before the view is drawn: a picture read by make() is drawn and kept. */
  function drawThumbs() {
    if (!els.box.hidden) {
      for (const entry of recipes ?? []) {
        const item = rows.get(entry.key);
        if (entry.cover && item?.parentElement === windowed && !item.thumb.dataset.drawn) paintRecipe(entry, item.thumb);
      }
    }
    const job = toPaint.shift();
    if (!job) return;
    const canvas = rows.get(job.entry.key)?.thumb, k = pictureKey(job.entry);
    making = false;
    if (canvas && (job.paintable ? paintObject(job.paintable.object, job.paintable.box, canvas) : paint(job.template, canvas))) {
      canvas.dataset.drawn = '1';
      canvas.toBlob(blob => blob && fetch(`/library/thumbs/${k}.png`, { method: 'PUT', headers: { 'Content-Type': 'image/png' }, body: blob })
        .then(r => { if (r.ok) kept.add(k); }).catch(() => {}), 'image/png');
      if (job.entry.effect) canvas.dataset.likeness = '1';
    } else { failed.add(job.entry.key); if (canvas && job.entry.effect) canvas.dataset.drawn = '1'; }
    job.paintable?.dispose();
    make();
  }

  els.filter.addEventListener('input', () => { els.list.scrollTop = 0; render(); });
  els.filter.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (els.filter.value) { els.filter.value = ''; render(); } else els.filter.blur();
    e.preventDefault();
  });
  for (const control of [els.kind, els.home, els.sort, els.placeable, els.elsewhere, els.favourites])
    control.addEventListener('change', () => { els.list.scrollTop = 0; render(); });
  els.list.addEventListener('scroll', () => { if (!els.box.hidden) draw(); });
  new ResizeObserver(() => { if (!els.box.hidden) draw(); }).observe(els.list);

  return {
    /** Show or hide the scope; the index and the favourites are read the first time it shows. */
    show(on) {
      els.box.hidden = !on;
      // (hidden, it leaves no rows in the page)
      if (!on) { clearTimeout(scanTimer); windowed.replaceChildren(); return; }
      if (!recipes) {
        recipes = recipesForScene();
        setKindOptions(els.kind, recipes);
      }
      render();
      if (!index && !loading) load(); else if (status) offer();
      if (!state) loadState();
    },
    get open() { return !els.box.hidden; },
    setChosen(entry) {
      chosen = entry?.library || entry?.light || entry?.cover ? entry : null;
      for (const [k, item] of rows) item.classList.toggle('on', k === chosen?.key);
    },
    used,
    entry: key => byKey.get(key) ?? null,
    entries: () => entries,
    shown: () => shown,
    ready: () => Boolean(index),
    /** The install's maps the library has read, lower case. */
    maps: () => new Set((index?.donors ?? []).map(d => d.package.toLowerCase())),
    status: () => status,
    state: () => state,
    drawThumbs,
  };
}
