// Cache everything's pictures (the Settings menu's window, precache.js; the server's precache.py reads the pieces and
// the maps): the pictures the page draws and the server keeps, drawn now rather than the first time each is shown.
// They are every look's sample in the look picker (look_picker.js: a wall look's, a floor or roof look's, and a ground
// look's in each of the ground's four shapes) and every piece's and effect's picture in the Add panel's All maps
// (library.js: the list's and the large panel's, each kept under a key of its own). The page draws them as those
// panels do, with their own drawing (a sample or a piece read, then painted in a frame before the view), so they are
// the same pictures; the page has to stay open meanwhile, and a hidden tab draws nothing until it shows again.
//
// They go map by map, by each look's and piece's donor (a few maps at a time where each has only a few, so that several
// are read at once): what a batch's pictures loaded into the page's tables (the meshes, materials and textures, the
// pieces' records and collision) is let go once they are kept, unless the view draws it (createTableRelease), so the
// page holds about one map's worth at a time, however many it draws.
//
// Here: what there is to draw (lookItems, pieceItems, batches, estimate: pure, precache_pictures_test.mjs), the tables
// let go (createTableRelease) and the job (createPicturePrecache: plan, start, cancel, state, and drawFrame, called
// each frame before the view is drawn).
import { GROUND_SHAPES } from './ground.js';

/** The look picker's samples of each kind (made_looks_wiring.js openLookPicker: a wall's and a slab's are named by their
 *  kind, a ground look's by the ground shape being given the look). */
export const LOOK_SAMPLES = { wall: ['wall'], slab: ['slab'], ground: GROUND_SHAPES };
export const LOOK_KINDS = Object.keys(LOOK_SAMPLES);
const KIND_WORDS = { wall: 'wall', slab: 'floor or roof', ground: 'ground' };
/** What a picture takes, going by runs on a test server (the plan's estimates): an item's seconds (a look's sample, the
 *  server making its mesh; a piece's or effect's two pictures from one read, an effect's likeness run warm first) and
 *  a picture's bytes in the cache. */
export const COST = { look: { seconds: 0.35, bytes: 110_000 }, piece: { seconds: 0.03, bytes: 8_000 }, effect: { seconds: 0.25, bytes: 8_000 } };
const AHEAD = 6;            // items read ahead of their painting
const BATCH = 32;           // the fewest items a batch of maps has (a map with more is a batch of its own)
const FRAME_MS = 8;         // the most a frame spends painting them
const FAILURES_SHOWN = 50;

/** The looks' samples to draw: { total, missing, items } from the kinds' catalogues ([{ kind, looks }], looks.js
 *  loadLooks), the keys the server keeps (`kept`) and a sample's key (look_picker.js pictureKey). An item is one sample:
 *  { type: 'look', map (its donor's), name, kind, entry, sample, want: [{ size: 'look', key }] }. */
export function lookItems(lists, kept, keyOf) {
  let total = 0;
  const items = [];
  for (const list of lists) {
    for (const entry of list.looks ?? []) {
      for (const sample of LOOK_SAMPLES[list.kind] ?? []) {
        const key = keyOf(list.kind, entry, sample);
        total++;
        if (kept.has(key)) continue;
        const what = list.kind === 'ground' ? `ground look, as a ${sample}` : `${KIND_WORDS[list.kind]} look`;
        items.push({ type: 'look', map: entry.map ?? '', name: `${entry.name} (${what})`, kind: list.kind, entry, sample,
                     want: [{ size: 'look', key }] });
      }
    }
  }
  return { total, missing: items.length, items };
}

/** The Add panel's pictures to draw: { total, missing, items } from the library index's entries (library.py), the keys
 *  the server keeps and an entry's two keys (library.js thumbKeys: { small, large }). A piece has both pictures, an
 *  effect too while `effects` (the View options' Effects as they look: else the panel shows its marker); a sound and
 *  a lens flare keep their marker. An item is one entry, with the pictures of it the server lacks:
 *  { type: 'piece' | 'effect', map (its home map), name, entry, want: [{ size: 'small' | 'large', key }] }. */
export function pieceItems(entries, kept, keysOf, { effects = true } = {}) {
  let total = 0, missing = 0;
  const items = [];
  for (const entry of entries ?? []) {
    const effect = entry.family === 'effect';
    if (entry.family === 'sound' || entry.family === 'flare' || (effect && (!effects || !entry.placeable))) continue;
    const { small, large } = keysOf(entry);
    total += 2;
    const want = [{ size: 'small', key: small }, { size: 'large', key: large }].filter(w => !kept.has(w.key));
    if (!want.length) continue;
    missing += want.length;
    items.push({ type: effect ? 'effect' : 'piece', map: entry.source?.package ?? '', name: entry.name, entry, want });
  }
  return { total, missing, items };
}

/** The items in batches: each map's together (its name's case aside), the maps in the order they first come, maps
 *  joined into one batch until it has `size` items at least: [{ maps: [name], items }]. */
export function batches(items, size = BATCH) {
  const groups = new Map();
  for (const item of items) {
    const key = String(item.map).toLowerCase();
    if (!groups.has(key)) groups.set(key, { map: item.map, items: [] });
    groups.get(key).items.push(item);
  }
  const out = [];
  for (const group of groups.values()) {
    const last = out.at(-1);
    if (last && last.items.length < size) { last.maps.push(group.map); last.items.push(...group.items); }
    else out.push({ maps: [group.map], items: [...group.items] });
  }
  return out;
}

/** What drawing `items` takes: { seconds, bytes }. */
export function estimate(items) {
  let seconds = 0, bytes = 0;
  for (const item of items) {
    const cost = COST[item.type];
    seconds += cost.seconds;
    bytes += cost.bytes * item.want.length;
  }
  return { seconds: Math.round(seconds), bytes };
}

/**
 * What a run of drawing loaded into the page's tables, let go: snapshot() before, release(snapshot) after, which
 * takes out of the tables what was put in since and frees it (its GPU copies; the rest goes with the last reference),
 * except what the view draws now (a piece placed meanwhile keeps its mesh, materials and textures, and its record) and
 * what is still loading (someone else's). It runs at once, all of it in one go, so that nothing can come between.
 * releaseWhenIdle(snapshot) does it once no panel is drawing a picture of its own (`busy()`: such a picture is painted
 * a frame after its piece is read, from the tables): meanwhile `holding` says so, and the panels start no other
 * picture, finishing the one in hand; after it they carry on (`resume()`). idle(snapshot) is that wait, which also
 * waits for the records read since to come in (their loads are not the tables' track, so what each gave is noted
 * here as it comes).
 * tables: { meshes, materials, textures, records } (Maps of promises: editor_state.js geometryCache, scene_pieces.js
 * materialCache, app.js texturePromises, editor_state.js libraryRecords); loaded(map, key): the value a table's load
 * gave, or nothing while it loads or if it failed (scene_pieces.js loaded); collision(): editor_state.js lineCollision
 * (a Map by mesh, or null); world: the scene the view draws; roots(): the pieces (editor_state.js roots); busy(): a
 * panel is drawing a picture (the Add panel's, the look picker's, a prefab's); resume(): the panels may draw again.
 */
export function createTableRelease({ tables, loaded, collision, world, roots, busy = () => false, resume = () => {}, wait = 30 }) {
  const records = new WeakMap();      // what a record's load gave (null: it failed)
  let holding = false;
  function snapshot() {
    return { meshes: new Set(tables.meshes.keys()), materials: new Set(tables.materials.keys()),
             textures: new Set(tables.textures.keys()), records: new Set(tables.records.keys()),
             collision: new Set(collision()?.keys() ?? []) };
  }
  async function idle(before) {
    for (;;) {
      while (busy()) await new Promise(resolve => setTimeout(resolve, wait));
      const coming = [...tables.records].filter(([key, promise]) => !before.records.has(key) && !records.has(promise));
      if (!coming.length) return;
      await Promise.all(coming.map(([, promise]) => Promise.resolve(promise).then(v => records.set(promise, v ?? null),
                                                                              () => records.set(promise, null))));
    }
  }
  // the geometries, materials and textures the view draws now (a part's material that a highlight stands in for too)
  function drawn() {
    const geometries = new Set(), materials = new Set(), textures = new Set();
    const takeMaterial = m => {
      if (!m || materials.has(m)) return;
      materials.add(m);
      for (const value of Object.values(m)) if (value?.isTexture) textures.add(value);
    };
    world.traverse(o => {
      if (o.geometry) geometries.add(o.geometry);
      for (const m of [o.material ?? []].flat()) takeMaterial(m);
      takeMaterial(o.userData?.baseMaterial);
    });
    return { geometries, materials, textures };
  }
  function release(before) {
    const used = drawn(), kept = new Set();
    const valueOf = (name, key) => (name === 'records' ? records.get(tables.records.get(key)) : loaded(tables[name], key));
    const added = (name, had) => [...tables[name].keys()].filter(key => !had.has(key))
      .map(key => [key, valueOf(name, key)]).filter(([, value]) => value);
    for (const [key, gltf] of added('meshes', before.meshes)) {
      const parts = [];
      gltf.scene?.traverse(o => { if (o.geometry) parts.push(o); });
      if (parts.some(o => used.geometries.has(o.geometry))) { kept.add(key); continue; }
      tables.meshes.delete(key);
      for (const o of parts) { o.geometry.dispose(); for (const m of [o.material ?? []].flat()) m.dispose?.(); }
    }
    for (const [key, material] of added('materials', before.materials)) {
      if (used.materials.has(material)) continue;
      tables.materials.delete(key);
      material.dispose?.();
    }
    for (const [key, texture] of added('textures', before.textures)) {
      if (used.textures.has(texture)) continue;
      tables.textures.delete(key);
      texture.dispose?.();
    }
    // a record goes with its meshes (placed again, it is read again and its meshes with it)
    for (const [key, template] of added('records', before.records)) {
      if (template.sources?.some(s => kept.has(s.mesh))) continue;
      tables.records.delete(key);
    }
    const lines = collision();
    if (lines) {
      const placed = new Set([...roots().values()].map(r => r.userData.source?.mesh));
      for (const key of [...lines.keys()].filter(k => !before.collision.has(k))) if (!kept.has(key) && !placed.has(key)) lines.delete(key);
    }
  }
  async function releaseWhenIdle(before) {
    holding = true;
    try {
      await idle(before);
      release(before);
    } finally {
      holding = false;
      resume();
    }
  }
  return { snapshot, idle, release, releaseWhenIdle, get holding() { return holding; } };
}

/**
 * The job. What it is given:
 * - readIndex(): the library index with the pictures the server keeps ({ index, thumbs }: GET /library.json?index=1,
 *   or null); readLookPictures(): the look pictures kept ({ pictures }: GET /library/pictures.json, or null);
 *   loadLooks(kind): a kind's catalogue (looks.js);
 * - keysOf(entry): an index entry's two picture keys (library.js thumbKeys); lookKeyOf(kind, entry, sample)
 *   (look_picker.js pictureKey); effects(): whether effects have pictures (the View options' Effects as they look);
 * - the drawing: pieceTemplate(source) (library_templates.js libraryTemplate), paintPiece(template, canvas),
 *   effectPicture(entry) ({ object, box, dispose } or null: effects_wiring.js), paintEffect(object, box, canvas),
 *   lookSample(kind, entry, sample) ({ paint(canvas) } or null: made_looks_wiring.js prepareSample); a paint is called
 *   only in drawFrame and says false when the view is too small to draw in this frame;
 * - canvasSize(size): a picture's [width, height] in pixels ('small', 'large', 'look');
 * - send(url, blob): the picture put to the server (a fetch Response); onKept(kind, key): it is kept ('thumb' or
 *   'look': the panels show it from the server from now on);
 * - release: createTableRelease's (releaseWhenIdle between batches); onChange(): the job's state changed.
 */
export function createPicturePrecache({ readIndex, readLookPictures, loadLooks, keysOf, lookKeyOf, effects,
                                        pieceTemplate, paintPiece, effectPicture, paintEffect, lookSample,
                                        canvasSize, send, onKept, release, onChange = () => {} }) {
  let job = null;
  const toPaint = [];

  /** What there is to draw now: { looks, pieces: { ..., ready: whether the library is read }, estimate, errors }. */
  async function plan() {
    const [lists, keptLooks, library] = await Promise.all([Promise.all(LOOK_KINDS.map(kind => loadLooks(kind))),
                                                            readLookPictures(), readIndex()]);
    const errors = lists.filter(l => l.error).map(l => l.error);
    if (!keptLooks) errors.push('The kept look pictures could not be listed');
    const looks = lookItems(lists.filter(l => !l.error), new Set(keptLooks?.pictures ?? []), lookKeyOf);
    const pieces = { ...pieceItems(library?.index?.entries, new Set(library?.thumbs ?? []), keysOf, { effects: effects() }),
                     ready: Boolean(library?.index) };
    return { looks, pieces, estimate: estimate([...looks.items, ...pieces.items]), errors };
  }

  function state() {
    if (!job) return { state: 'idle' };
    const seconds = job.state === 'running' ? Math.round((performance.now() - job.started) / 100) / 10 : job.seconds;
    return { state: job.state, what: job.what, done: job.done, total: job.total, drawn: job.drawn, skipped: job.skipped,
             failed: job.failed, failures: job.failures.slice(0, FAILURES_SHOWN), error: job.error, seconds,
             fraction: job.total ? Math.round(job.done / job.total * 1e4) / 1e4 : null };
  }

  /** Start drawing (the job's state; the running job's if there is one). For the browser check: `limit`, only the first
   *  so many items; `types`, only items of these types ('look', 'piece', 'effect'). */
  function start({ limit = Infinity, types = null } = {}) {
    if (job?.state === 'running') return state();
    job = { state: 'running', what: 'Counting the pictures', done: 0, total: 0, drawn: 0, skipped: 0, failed: 0,
            failures: [], error: null, cancelled: false, started: performance.now(), seconds: 0 };
    run(job, limit, types);
    onChange();
    return state();
  }
  function cancel() {
    if (job?.state !== 'running') return state();
    job.cancelled = true;
    for (const waiting of toPaint.splice(0)) waiting.resolve(null);
    onChange();
    return state();
  }

  async function run(current, limit, types) {
    try {
      const counted = await plan();
      const items = [...counted.looks.items, ...counted.pieces.items].filter(item => !types || types.includes(item.type)).slice(0, limit);
      current.total = items.reduce((n, item) => n + item.want.length, 0);
      onChange();
      for (const batch of batches(items)) {
        if (current.cancelled) break;
        const [first, ...more] = batch.maps;
        current.what = `Drawing the pictures of ${first || 'the editor\'s own looks'}${more.length ? ` and ${more.length} more map${more.length === 1 ? '' : 's'}` : ''}`;
        onChange();
        const before = release.snapshot();
        try { await pool(batch.items, item => draw(current, item), () => current.cancelled); }
        // (what is not let go stays loaded: no harm to the pictures)
        finally { await release.releaseWhenIdle(before).catch(() => {}); }
      }
    } catch (error) {
      current.error = error?.message ?? String(error);
    }
    current.seconds = Math.round((performance.now() - current.started) / 100) / 10;
    current.state = current.cancelled ? 'cancelled' : current.error ? 'failed' : 'done';
    onChange();
  }
  // `work` on each item, `n` at a time, none started once `stop()`
  async function pool(items, work, stop, n = AHEAD) {
    let next = 0;
    const lane = async () => { while (next < items.length && !stop()) await work(items[next++]); };
    await Promise.all(Array.from({ length: Math.min(n, items.length) }, lane));
  }
  function fail(current, item, why) {
    current.failed += item.want.length;
    current.done += item.want.length;
    current.failures.push(`${item.name}, of ${item.map || 'the editor'}: ${why}`);
    onChange();
  }
  async function prepare(item) {
    if (item.type === 'look') {
      const sample = await lookSample(item.kind, item.entry, item.sample);
      return sample && { paint: (size, canvas) => sample.paint(canvas) };
    }
    if (item.type === 'effect') {
      const picture = await effectPicture(item.entry);
      return picture && { paint: (size, canvas) => paintEffect(picture.object, picture.box, canvas), dispose: () => picture.dispose?.() };
    }
    const template = await pieceTemplate(item.entry.source);
    return { paint: (size, canvas) => paintPiece(template, canvas) };
  }
  async function draw(current, item) {
    let made;
    try { made = await prepare(item); }
    catch (error) { if (!current.cancelled) fail(current, item, error?.message ?? 'it could not be read'); return; }
    if (current.cancelled) { made?.dispose?.(); return; }
    if (!made) {
      // an effect that draws nothing (its system can't be drawn, or nothing lives at its start): its marker stays,
      // as in the panel; a look with no sample: its donor could not be read
      if (item.type === 'effect') { current.skipped += item.want.length; current.done += item.want.length; onChange(); }
      else fail(current, item, 'no sample could be made: its donor could not be read');
      return;
    }
    const pictures = await new Promise(resolve => toPaint.push({ made, item, resolve }));
    made.dispose?.();
    if (current.cancelled) return;
    if (!pictures) { fail(current, item, 'it could not be drawn'); return; }
    const answers = await Promise.all(pictures.map(p => keep(p)));
    const refused = answers.find(a => a !== true);
    if (refused) { fail(current, item, refused); return; }
    current.drawn += pictures.length;
    current.done += pictures.length;
    onChange();
  }
  // a picture put to the server: true, or why not
  async function keep({ size, key, canvas }) {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) return 'it could not be made a PNG';
    const look = size === 'look';
    try {
      const response = await send(`/library/${look ? 'pictures' : 'thumbs'}/${key}.png`, blob);
      if (!response.ok) return `the server answered ${response.status}`;
    } catch (error) { return `the server did not answer (${error?.message ?? error})`; }
    onKept(look ? 'look' : 'thumb', key);
    return true;
  }

  /** Called each frame before the view is drawn: the items read are painted, as many as FRAME_MS allows. */
  function drawFrame() {
    const began = performance.now();
    while (toPaint.length && performance.now() - began < FRAME_MS) {
      const { made, item, resolve } = toPaint[0];
      let pictures = [];
      for (const { size, key } of item.want) {
        const [width, height] = canvasSize(size);
        const canvas = Object.assign(document.createElement('canvas'), { width, height });
        let painted;
        try { painted = made.paint(size, canvas); } catch { painted = null; }
        if (painted === false) return;          // (the view too small to draw in: tried again next frame)
        if (!painted) { pictures = null; break; }
        pictures.push({ size, key, canvas });
      }
      toPaint.shift();
      resolve(pictures);
    }
  }

  return { plan, start, cancel, state, drawFrame, get running() { return job?.state === 'running'; } };
}
