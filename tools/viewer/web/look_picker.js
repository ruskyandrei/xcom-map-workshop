// The look picker (private/plans/done/look-picker-and-rock-points-plan.md, L1): a large panel of its own over the
// view, for every place a made wall's, floor's or roof's, or ground shape's look is chosen. Each look is a card with
// a large picture of a sample made in it (what the tool will make: a wall three tiles long, a floor three by three,
// the ground shape being given the look), drawn once in the page and kept by the server
// (/library/pictures/<key>.png), so a kept picture shows at once; the missing ones are drawn one at a time, the cards
// in view first, then the rest while the panel is open.
//
// What it is given: the kind's catalogue entries (looks.js), how a sample is made and drawn (prepare), the tags a
// look shows (looks.js lookTags). What it gives: the entry chosen (onChoose), or the eyedropper (onPick).

import { lookKey } from './looks.js';
import { ask, hex16, sendPng } from './api.js';

/** The pictures' size in pixels, and the version of their drawing (a better drawing replaces the old pictures). */
export const PICTURE = { width: 512, height: 384, version: 1 };
/** The cards' picture sizes, CSS pixels. */
export const SIZES = { small: [180, 135], medium: [280, 210], large: [400, 300] };
const FAVOURITES = 'workshop.lookFavourites', SIZE = 'workshop.lookPictureSize';

/** The 16 hex digits a sample's picture is kept under (the server's key form): its kind, look, sample shape, size and
 *  the drawing's version. */
export const pictureKey = (kind, entry, sample) =>
  hex16(`look-sample|${PICTURE.version}|${kind}|${lookKey(kind, entry.mesh, entry.material)}|${sample}|${PICTURE.width}x${PICTURE.height}`);

// (a catalogue entry's `maps`: { map: times placed })
const mapsOf = entry => Object.keys(entry.maps ?? {});

/** The words a look is found by: its name, setting, home map, the maps it is in, its donor mesh. */
export function lookText(entry) {
  return [entry.name, entry.setting, entry.map, ...mapsOf(entry), entry.mesh, entry.material]
    .filter(Boolean).join(' ').toLowerCase();
}

/** Whether a look shows for the find box's words and the filters ({ setting, favourites, full }): `isFavourite(entry)`,
 *  `tagsOf(entry)` ([[text, title]], looks.js lookTags: "Simpler" is what Full only hides). */
export function shown(entry, words, filters, isFavourite, tagsOf) {
  if (filters.setting && (entry.setting ?? '') !== filters.setting) return false;
  if (filters.favourites && !isFavourite(entry)) return false;
  if (filters.full && tagsOf(entry).some(([t]) => t === 'Simpler')) return false;
  const text = lookText(entry);
  return words.every(w => text.includes(w));
}

/** The looks in the panel's order: the one the piece has, those the project uses, the favourites, then by name. */
export function ordered(entries, { kind, current = null, used = new Set(), isFavourite = () => false }) {
  const rank = e => {
    const k = lookKey(kind, e.mesh, e.material);
    return k === current ? 0 : used.has(k) ? 1 : isFavourite(e) ? 2 : 3;
  };
  return [...entries].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name) || a.mesh.localeCompare(b.mesh));
}

const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children); return e; };

/**
 * prepare(kind, entry, sample): a promise of { paint(canvas) -> bool } (called in a frame, drawFrame) or null when no
 * sample can be made; tagsOf(entry); recall(key), remember(key, value): the browser's own settings; hint(message);
 * held(): Cache everything's pictures are letting go of what they loaded (precache_pictures.js createTableRelease), so
 * no sample is begun meanwhile.
 */
export function createLookPicker({ prepare, tagsOf, recall, remember, hint = () => {}, held = () => false }) {
  let spec = null, cards = [], kept = null, keptLoad = null, focusIndex = -1;
  const queue = [], toPaint = [], failed = new Set(), seen = new Set();
  let working = false, drawnNow = 0;
  let favourites;
  try { favourites = new Set(JSON.parse(recall(FAVOURITES) ?? '[]')); } catch { favourites = new Set(); }
  const favKey = e => `${spec.kind}|${lookKey(spec.kind, e.mesh, e.material)}`;
  const isFavourite = e => favourites.has(favKey(e));
  let size = SIZES[recall(SIZE)] ? recall(SIZE) : 'medium';

  // -- the panel -------------------------------------------------------------------------------------------------
  const title = el('h2');
  const find = el('input', { type: 'search', placeholder: 'Find a look: its name, setting or map', spellcheck: false, autocomplete: 'off' });
  const setting = el('select', { title: 'Only the looks of one setting' });
  const favOnly = el('input', { type: 'checkbox' }), fullOnly = el('input', { type: 'checkbox' });
  const sizePick = el('select', { title: 'The pictures\' size' },
    ...Object.keys(SIZES).map(k => el('option', { value: k, textContent: `${k[0].toUpperCase()}${k.slice(1)} pictures` })));
  sizePick.value = size;
  const pickButton = el('button', { type: 'button', textContent: 'Pick from the view (I)', title: 'Take the look of a piece in the view: click it there' });
  const closeButton = el('button', { type: 'button', className: 'icon', title: 'Close (Esc)', innerHTML: '<svg class="i"><use href="#i-close"/></svg>' });
  closeButton.setAttribute('aria-label', 'Close');
  const status = el('div', { className: 'lookstatus' });
  const grid = el('div', { className: 'lookgrid', role: 'listbox' });
  const panel = el('div', { className: 'panel lookpanel', role: 'dialog' },
    el('div', { className: 'lookhead' }, title, find, setting,
       el('label', { className: 'check', title: 'Only the looks starred' }, favOnly, ' Favourites only'),
       el('label', { className: 'check', title: 'Hide the looks the Build makes simpler than their donor' }, fullOnly, ' Full only'),
       sizePick, pickButton, closeButton),
    status, grid);
  panel.setAttribute('aria-modal', 'true');
  const box = el('div', { className: 'modal lookpicker', hidden: true }, panel);
  document.body.append(box);
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  closeButton.onclick = () => close();
  pickButton.onclick = () => { const s = spec; close(); s?.onPick?.(); };
  for (const control of [setting, favOnly, fullOnly]) control.addEventListener('change', () => render());
  find.addEventListener('input', () => render());
  sizePick.addEventListener('change', () => { size = sizePick.value; remember(SIZE, size); applySize(); });

  const observer = new IntersectionObserver(items => {
    for (const item of items) if (item.isIntersecting) want(item.target.card, true);
  }, { root: grid, rootMargin: '200px' });

  function applySize() {
    const [w, h] = SIZES[size];
    grid.style.setProperty('--lookw', `${w}px`);
    grid.style.setProperty('--lookh', `${h}px`);
  }
  applySize();

  function settings() {
    const all = [...new Set(spec.entries.map(e => e.setting).filter(Boolean))].sort();
    setting.replaceChildren(el('option', { value: '', textContent: 'Every setting' }), ...all.map(s => el('option', { value: s, textContent: s })));
  }

  function card(entry) {
    const key = lookKey(spec.kind, entry.mesh, entry.material), pk = pictureKey(spec.kind, entry, spec.sample);
    const picture = el('span', { className: 'lookpic' }, el('span', { className: 'lookwait', textContent: 'Drawing…' }));
    const star = el('span', { className: 'lookstar', textContent: '★', title: 'A favourite: starred looks come first and show with Favourites only' });
    star.classList.toggle('on', isFavourite(entry));
    star.addEventListener('click', e => {
      e.stopPropagation();
      const k = favKey(entry);
      if (favourites.has(k)) favourites.delete(k); else favourites.add(k);
      remember(FAVOURITES, JSON.stringify([...favourites]));
      star.classList.toggle('on', favourites.has(k));
      if (favOnly.checked) render();
    });
    const tags = el('span', { className: 'looktags' }, ...tagsOf(entry).map(([text, why]) => el('span', { className: 'tag', textContent: text, title: why })));
    const where = [entry.setting, entry.map].filter(Boolean).join(' · ');
    const b = el('button', { type: 'button', className: 'lookcard', role: 'option' }, picture,
      el('span', { className: 'lookline' }, el('strong', { textContent: entry.name }), star),
      el('small', { textContent: where }), tags);
    b.title = `${entry.name}${entry.setting ? ` (${entry.setting})` : ''}: ${spec.verb ?? 'click to choose this look'}\n`
      + `Its donor: ${String(entry.mesh).split('.').at(-1)} in ${entry.map}${mapsOf(entry).length > 1 ? ` (placed in ${mapsOf(entry).length} maps)` : ''}`
      + `${(entry.warnings ?? []).length ? `\nMade simpler: ${entry.warnings.join('; ')}` : ''}`;
    b.classList.toggle('current', key === spec.current);
    b.dataset.key = key; b.dataset.map = entry.map ?? '';
    b.addEventListener('click', () => choose(entry));
    b.addEventListener('focus', () => { focusIndex = cards.findIndex(c => c.button === b); });
    const c = { entry, key, pk, button: b, picture, state: 'none' };
    b.card = c;
    return c;
  }

  function showPicture(c, source) {
    const img = source instanceof HTMLCanvasElement ? source : el('img', { src: source, alt: '', draggable: false });
    c.picture.replaceChildren(img);
    c.state = 'shown';
  }

  function render() {
    if (!spec) return;
    const words = find.value.toLowerCase().split(/\s+/).filter(Boolean);
    const filters = { setting: setting.value, favourites: favOnly.checked, full: fullOnly.checked };
    for (const c of cards) observer.unobserve(c.button);
    const list = ordered(spec.entries, { kind: spec.kind, current: spec.current, used: spec.used, isFavourite })
      .filter(e => shown(e, words, filters, isFavourite, tagsOf));
    const byKey = new Map(cards.map(c => [c.key, c]));
    cards = list.map(e => byKey.get(lookKey(spec.kind, e.mesh, e.material)) ?? card(e));
    grid.replaceChildren(...cards.map(c => c.button));
    if (!cards.length) grid.append(el('div', { className: 'lookempty', textContent: 'No look of this kind matches.' }));
    for (const c of cards) {
      if (c.state === 'none' && kept?.has(c.pk)) showPicture(c, `/library/pictures/${c.pk}.png`);
      observer.observe(c.button);
    }
    focusIndex = Math.min(focusIndex, cards.length - 1);
    progress();
  }

  function progress() {
    if (!spec) return;
    const missing = spec.entries.length - spec.entries.filter(e => {
      const pk = pictureKey(spec.kind, e, spec.sample);
      return kept?.has(pk) || failed.has(pk);
    }).length;
    status.textContent = `${cards.length.toLocaleString()} of ${spec.entries.length.toLocaleString()} looks`
      + (missing ? ` · Drawing pictures: ${(spec.entries.length - missing).toLocaleString()} of ${spec.entries.length.toLocaleString()}` : '')
      + ' · Click one to choose it; ★ keeps a favourite';
  }

  // -- the pictures ------------------------------------------------------------------------------------------------
  function loadKept() {
    if (kept) return Promise.resolve(kept);
    keptLoad ??= ask('/library/pictures.json')
      .then(answer => { kept = new Set(answer?.pictures ?? []); keptLoad = null; return kept; });
    return keptLoad;
  }
  // a card's sample wanted: those in view first (`now`), the rest after them
  function want(c, now) {
    if (c.state !== 'none' || failed.has(c.pk) || kept?.has(c.pk) || seen.has(c.pk)) return;
    seen.add(c.pk);
    if (now) queue.unshift(c); else queue.push(c);
    work();
  }
  async function work() {
    if (working || !spec || held()) return;
    const c = queue.shift();
    if (!c) {
      // (then the rest, while the panel is open)
      const rest = cards.find(x => x.state === 'none' && !seen.has(x.pk) && !failed.has(x.pk) && !kept?.has(x.pk));
      if (rest) want(rest, false);
      return;
    }
    if (c.state !== 'none' || kept?.has(c.pk)) { work(); return; }
    working = true;
    c.picture.firstChild?.classList?.add('busy');
    const kind = spec.kind, sample = spec.sample;
    try {
      const job = await prepare(kind, c.entry, sample);
      if (!job) throw Error('no sample');
      toPaint.push({ c, job });
    } catch {
      failed.add(c.pk); c.state = 'failed';
      c.picture.replaceChildren(el('span', { className: 'lookwait', textContent: 'No picture: its donor could not be read' }));
      working = false; progress(); work();
    }
  }
  /** Called each frame before the view is drawn: a prepared sample is drawn, shown and kept. */
  function drawFrame() {
    const next = toPaint.shift();
    if (!next) return;
    const { c, job } = next;
    working = false;
    const canvas = el('canvas', { width: PICTURE.width, height: PICTURE.height });
    let ok = false;
    try { ok = job.paint(canvas); } catch { ok = false; }
    job.dispose?.();
    if (ok) {
      showPicture(c, canvas);
      drawnNow++;
      canvas.toBlob(blob => blob && sendPng('PUT', `/library/pictures/${c.pk}.png`, blob)
        .then(r => { if (r.ok) { kept?.add(c.pk); progress(); } }).catch(() => {}), 'image/png');
    } else {
      // (the view too small to draw in this frame: tried again)
      seen.delete(c.pk);
    }
    progress();
    work();
  }

  // -- choosing ----------------------------------------------------------------------------------------------------
  function choose(entry) {
    const s = spec;
    close();
    s?.onChoose(entry);
  }
  function columns() {
    if (cards.length < 2) return 1;
    const top = cards[0].button.offsetTop;
    const n = cards.findIndex(c => c.button.offsetTop !== top);
    return n < 0 ? cards.length : n;
  }
  box.addEventListener('keydown', e => {
    if (!spec) return;
    const inFind = e.target === find;
    if (e.key === 'Escape') {
      if (inFind && find.value) { find.value = ''; render(); } else close();
      e.preventDefault(); e.stopPropagation(); return;
    }
    if (e.key === 'Enter' && inFind && cards.length) { choose(cards[Math.max(0, focusIndex)].entry); e.preventDefault(); return; }
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: columns(), ArrowUp: -columns() }[e.key];
    if (step && !(inFind && (e.key === 'ArrowLeft' || e.key === 'ArrowRight'))) {
      const i = Math.max(0, Math.min(cards.length - 1, (focusIndex < 0 ? -step : focusIndex) + step));
      cards[i]?.button.focus();
      e.preventDefault(); return;
    }
    if ((e.key === 'i' || e.key === 'I') && !inFind && !e.ctrlKey && !e.metaKey && !e.altKey) { pickButton.click(); e.preventDefault(); }
  });

  function open(next) {
    spec = { ...next, used: next.used ?? new Set() };
    title.textContent = spec.title;
    find.value = ''; favOnly.checked = false; fullOnly.checked = false;
    cards = []; queue.length = 0; toPaint.length = 0; seen.clear(); working = false; focusIndex = -1;
    pickButton.hidden = !spec.onPick;
    settings();
    box.hidden = false;
    render();
    loadKept().then(() => render());
    setTimeout(() => find.focus(), 0);
  }
  function close() {
    if (!spec) return;
    for (const c of cards) observer.unobserve(c.button);
    spec = null; cards = []; queue.length = 0; toPaint.length = 0; seen.clear(); working = false;
    box.hidden = true;
    grid.replaceChildren();
    if (drawnNow) hint(`${drawnNow} look picture${drawnNow === 1 ? '' : 's'} drawn and kept: next time they show at once`);
    drawnNow = 0;
  }

  return {
    open, close, drawFrame,
    get isOpen() { return Boolean(spec); },
    /** A picture drawn elsewhere (Cache everything's) is kept by the server: shown from there, not drawn again. */
    markKept: key => { kept?.add(key); },
    /** Whether a card's sample is being read or waits to be painted (it is painted from the page's tables). */
    busy: () => working || toPaint.length > 0,
    /** Carry on drawing the samples (after held()). */
    resume: () => { work(); },
    /** For the tests: what the panel shows. */
    state: () => spec && { kind: spec.kind, sample: spec.sample, cards: cards.map(c => ({ name: c.entry.name, key: c.key, picture: c.state })), status: status.textContent },
  };
}
