// The made pieces' looks (refactor stage P7; the custom geometry plan's M4c, the look picker plan and the custom
// geometry editing plan's B2; looks.js holds the looks' catalogues and entries, look_picker.js the picker's panel).
// Here:
// - the look each tool draws in, remembered in this browser (storedLook, rememberLook), and the looks the project's
//   made pieces are in (usedLookKeys, madeLookKey), which the picker lists first;
// - the picker's samples: what the tool makes in a look, drawn large for its card (sampleRequest, prepareSample);
// - the picker opened for a tool or a piece (openLookPicker, closeLookPicker) and what choosing a look does when
//   nothing else was asked (lookChosen);
// - the eyedropper: the next click in the view takes the look of the piece under it (startLookPick, stopLookPick,
//   pieceLook, lookPickAt);
// - a made piece in another look, with the pieces the change takes, in one undo step (lookTargets, setMadeLook);
// - a made piece's Look row in the piece panel (lookRow) and its Choose… and Plain buttons.
//
// createMadeLooksWiring takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// renderer, the made pieces' tests, state and donor template, the drawing tools, the paste, the groups' changes, and
// the meshes' and materials' loading for a sample. It has no state of its own: what other areas read or set (the look
// picker, made with the Add panel's piece browser, and the eyedropper's state) is editor_state.js's.
import * as THREE from 'three';
import { data, geometryCache, groupIndex, lookPicker, lookPicking, pieces, roots, selected,
         setLookPicking } from './editor_state.js';
import { GROUND_LOOKS, groundLookOf } from './ground.js';
import { catalogued, entryForPiece, loadLooks, lookFromEntry, lookKey } from './looks.js';
import { isFree } from './made_free.js';
import { fromOf, stateOfRoot } from './piece_records.js';
import { recall, remember } from './storage.js';
import { openingsInLook, SLAB_LOOKS, slabLookOf, storeysInLook, WALL_LOOKS, withStoreys } from './walls.js';
import { plural, short } from './dom_words.js';

export function createMadeLooksWiring({ $, assetUrl, boundsOf, changeGroups, deleteNow, flashHint, gizmo, gltfLoader,
                                        isMadeGround, isMadeSlab, isMadeWall, isPlain, madeRequest, madeRoot,
                                        madeShape, material, materialCache, materialKey, memberOf, memberRecord,
                                        movedMatrix, pasteSnapshot, pick, plainLook, previewGroup, renderer,
                                        showPieces, startWallDrawing, stopPlacing, stopWallDrawing, track, wallState,
                                        wallTemplate }) {
  // ---- looks from any piece (custom geometry plan, M4c)
  // The look each tool draws in: a look id, or a donor look chosen in the picker (lookFromEntry's), remembered in this
  // browser. A donor look no catalogue read holds is forgotten.
  const CURRENT_LOOK = { wall: 'workshop.wallLook', slab: 'workshop.slabLook', ground: 'workshop.groundLook' };
  function storedLook(kind) {
    try {
      const look = JSON.parse(recall(CURRENT_LOOK[kind]) ?? 'null');
      if (look?.donor && catalogued(kind, look.donor)) return look;
    } catch { /* a look id, or nothing */ }
    return null;
  }
  const rememberLook = (kind, look) => remember(CURRENT_LOOK[kind], look.donor ? JSON.stringify(look) : look.id);
  const LOOK_TITLES = { wall: 'Choose a wall look', slab: 'Choose a floor or roof look', ground: 'Choose a ground look' };
  const LOOK_NOUNS = { wall: 'wall', slab: 'floor or roof', ground: 'ground' };
  // The keys of the looks the project's made pieces of a kind are in (the picker lists them first).
  function usedLookKeys(kind) {
    const key = { wall: 'fracWall', slab: 'fracSlab', ground: 'ground' }[kind], out = new Set();
    for (const r of roots.values()) {
      const g = r.userData.source?.added?.generated, look = g?.[kind]?.look;
      if (g?.kind === key && !r.userData.deleted && look && typeof look === 'object') out.add(lookKey(kind, look.mesh, look.material));
    }
    return out;
  }
  // A made piece's look key (its donor look's), or null.
  function madeLookKey(root, kind) {
    const look = root?.userData.source?.added?.generated?.[kind]?.look;
    return look && typeof look === 'object' ? lookKey(kind, look.mesh, look.material) : null;
  }
  // ---- the look picker's samples (look picker plan, L1): what the tool makes in a look, drawn large for its card
  const SAMPLE_GROUND = {
    patch: { shape: 'patch', x0: 0, x1: 192, y0: 0, y1: 192 },
    block: { shape: 'block', x0: 0, x1: 192, y0: 0, y1: 192, height: 64 },
    ramp: { shape: 'ramp', x0: 0, x1: 192, y0: 0, y1: 96, height: 48 },
    rock: { shape: 'rock', x0: 0, x1: 192, y0: 0, y1: 192, height: 128, seed: 7 },
  };
  function sampleRequest(kind, look, sample) {
    if (kind === 'wall') return madeRequest('fracWall', look, { x0: 0, x1: 288, openings: [], seed: 1 });
    if (kind === 'slab') return madeRequest('fracSlab', look, { x0: 0, x1: 288, y0: 0, y1: 288, holes: [], seed: 1 });
    return madeRequest('ground', look, { ...(SAMPLE_GROUND[sample] ?? SAMPLE_GROUND.patch) });
  }
  /** A look's sample, ready to draw: its donor read (as a placed piece's), the made mesh asked of the server, its
   *  materials loaded; { paint(canvas) } for the picker, or null when it can't be made. */
  async function prepareSample(kind, entry, sample) {
    const look = lookFromEntry(kind, entry);
    const template = await wallTemplate(look);
    const generated = sampleRequest(kind, look, sample);
    const shape = madeShape(template, generated);
    if (!shape.mesh) return null;
    const source = { ...template, ...shape, id: `sample:${kind}:${entry.mesh}`, matrix: new THREE.Matrix4().toArray(), hidden: false,
                     added: { from: fromOf(template), generated } };
    track(geometryCache, source.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[source.mesh].url)));
    await geometryCache.get(source.mesh);     // (one the server can't make throws: no picture, not its donor's)
    for (const m of source.materials) {
      const [key, tint] = materialKey(source, m);
      track(materialCache, key, () => material(m, tint));
      await materialCache.get(key);
    }
    const frame = new THREE.Matrix4(), box = boundsOf([source], frame);
    if (box.isEmpty()) return null;
    return { paint: canvas => pieces.paintPicture(previewGroup([{ source, matrix: new THREE.Matrix4() }], null, frame), box, canvas) };
  }
  // (lookPicker, made with the piece browser since it paints: editor_state.js)
  // What choosing a look does when nothing else was asked: it becomes the tool's look and a wall or slab is drawn in it at
  // once; a ground look goes back to the Ground kind, whose shapes are then drawn in it.
  function lookChosen(kind, look) {
    rememberLook(kind, look);
    if (kind === 'wall') { startWallDrawing(look, {}); return; }
    if (kind === 'slab') { startWallDrawing(look, { slab: true }); return; }
    if (pieces.open) showPieces(true);
    flashHint(`Ground in ${look.name.toLowerCase()}: pick a shape in the Ground kind, then drag it out`);
  }
  /** Open the look picker of `kind` ('wall', 'slab', 'ground'; look picker plan, L1) for a piece being given a look: a
   *  panel of its own over the view, each of the kind's looks a card with a large picture of a sample made in it
   *  (`sample`: a ground look's shape, the piece's or the tool's), a click choosing one (onChoose(look)), "Pick from the
   *  view" (I) for the eyedropper. `current`: the look key of the piece (its card ringed and first). */
  async function openLookPicker(kind, { onChoose, title = null, sample = null, current = null }) {
    const list = await loadLooks(kind);
    if (list.error) { flashHint(`${list.error}: the editor asks again when the looks are opened again`); return; }
    stopWallDrawing(); stopPlacing();
    const stored = storedLook(kind)?.donor;
    const used = usedLookKeys(kind);
    if (stored) used.add(lookKey(kind, stored.mesh, stored.material));
    lookPicker.open({
      kind, title: title ?? LOOK_TITLES[kind], entries: list.looks, used, current,
      sample: kind === 'ground' ? (sample ?? 'patch') : kind,
      verb: 'click to give the piece this look',
      onChoose: entry => onChoose(lookFromEntry(kind, entry)),
      onPick: () => startLookPick(kind, onChoose),
    });
  }
  function closeLookPicker() { lookPicker?.close(); }
  // The eyedropper: the next click in the view takes the look of the piece under it.
  // (lookPicking, { kind, onChoose }: editor_state.js)
  function startLookPick(kind, onChoose = null) {
    closeLookPicker(); stopWallDrawing(); stopPlacing();
    setLookPicking({ kind, onChoose });
    gizmo.hold(true);
    renderer.domElement.style.cursor = 'crosshair';
    flashHint(`Click a piece in the view to draw ${LOOK_NOUNS[kind] === 'ground' ? 'ground' : `${LOOK_NOUNS[kind]}s`} in its look (this map's, a copy, or one from another map) · Esc cancels`);
  }
  function stopLookPick() { if (lookPicking) gizmo.hold(false); setLookPicking(null); renderer.domElement.style.cursor = ''; }
  /** The look of a piece in the view: { kind, cat, source } (its catalogue entry and donor placing), or { why }. A made
   *  piece gives the look it is in. */
  function pieceLook(src) {
    const g = src?.added?.generated, made = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' }[g?.kind];
    const placing = src?.added?.from ? { package: src.added.from.package, actor: src.added.from.actor } : { package: data.name, actor: src?.actor };
    if (made) {
      const look = g[made]?.look, cat = typeof look === 'object' ? catalogued(made, look) : null;
      if (cat) return { kind: made, cat, source: placing };
      const fixed = made === 'wall' ? WALL_LOOKS[0] : made === 'slab' ? slabLookOf(g.slab) : groundLookOf(g.ground);
      return fixed ? { kind: made, fixed } : { why: 'its look is in none of the editor\'s catalogues' };
    }
    const mesh = data.meshes[src?.mesh]?.name, material = data.materials[src?.materials?.[0]]?.name;
    for (const kind of ['wall', 'slab', 'ground']) {
      const cat = entryForPiece(kind, mesh, kind === 'ground' ? material : null);
      if (cat) return { kind, cat, source: placing };
    }
    return { why: `${data.meshes[src?.mesh]?.name?.split('.').at(-1) ?? 'it'} is none of the game's fracturing walls, floors and roofs, or of its ground pieces, `
      + 'so nothing can be made in its look' };
  }
  async function lookPickAt(x, y) {
    const want = lookPicking;
    const hit = pick(x, y), src = hit ? roots.get(hit.object.userData.objectId)?.userData.source : null;
    if (!src) { flashHint('Nothing there: click a wall, a floor or roof, or a ground piece · Esc cancels'); return; }
    const unread = (await Promise.all(['wall', 'slab', 'ground'].map(kind => loadLooks(kind)))).find(l => l.error);
    if (unread) { flashHint(`${unread.error}: click again to ask again · Esc cancels`); return; }
    const found = pieceLook(src);
    if (found.why) { flashHint(`Not a look: ${found.why} · Esc cancels`); return; }
    stopLookPick();
    const look = found.fixed ?? lookFromEntry(found.kind, found.cat, found.source);
    // (a piece of another kind is drawn in its own kind's tool)
    if (found.kind !== want.kind) {
      flashHint(`That is ${found.kind === 'wall' ? 'a wall' : found.kind === 'slab' ? 'a floor or roof' : 'ground'}: drawing ${LOOK_NOUNS[found.kind]}s in its look`);
      lookChosen(found.kind, look);
      return;
    }
    (want.onChoose ?? (l => lookChosen(want.kind, l)))(look);
  }
  /** A made piece in another look (M4c: a look id, or a donor look from the picker or the eyedropper): made again on that
   *  look's donor where it stands, its numbers kept (a wall's openings brought under its new face's top), in one undo
   *  step; the tool's next pieces take the look too. */
  // The pieces a look change takes: the made pieces of its kind picked now; a lone wall picked takes the walls joined to
  // it, end to end or at corners, so a room or a run changes whole (19 November 2026: a room's look changed
  // from the piece panel had come out as one wall of it in the new look).
  const MADE_OF_KIND = { wall: isMadeWall, slab: isMadeSlab, ground: isMadeGround };
  function lookTargets(root, kind) {
    const picked = gizmo.selection().filter(r => !r.userData.deleted && MADE_OF_KIND[kind](r.userData.source));
    if (picked.length > 1) return picked.includes(root) ? picked : [root, ...picked];
    if (kind !== 'wall') return [root];
    const walls = new Map([...roots.values()].filter(r => !r.userData.deleted && isMadeWall(r.userData.source))
      .map(r => [r.userData.source.id, r]));
    const seen = new Set([root.userData.source.id]), queue = [root];
    while (queue.length)
      for (const j of queue.pop().userData.joins?.joins ?? [])
        if (!seen.has(j.other) && walls.has(j.other)) { seen.add(j.other); queue.push(walls.get(j.other)); }
    return [...seen].map(id => id === root.userData.source.id ? root : walls.get(id));
  }
  async function setMadeLook(root, kind, look) {
    if (!look.plain) rememberLook(kind, look);
    const defaults = { wall: WALL_LOOKS[0].id, slab: SLAB_LOOKS[0].id, ground: GROUND_LOOKS[0].id };
    const hasLook = r => {
      const o = r.userData.source, now = o.added.generated[kind]?.look;
      // (a plain piece has no look, whatever its numbers' shape; a plain look is had by plain pieces only)
      if (look.plain || isPlain(o.added.generated)) return Boolean(look.plain) && isPlain(o.added.generated);
      return look.donor ? typeof now === 'object' && now?.mesh === look.donor.mesh && now?.material === look.donor.material
        && short(o.added.from?.actor ?? '') === look.actor : (now ?? defaults[kind]) === look.id;
    };
    const targets = lookTargets(root, kind).filter(r => !hasLook(r));
    if (!targets.length) return;
    // (plain: each in its kind's default look's shape, a slab by its own role)
    const lookOf = r => (look.plain ? plainLook(kind, r.userData.source.added.generated[kind]) : look);
    const templates = new Map();
    try {
      for (const r of targets) {
        const l = lookOf(r), k = l.donor ? JSON.stringify(l.donor) : l.id;
        if (!templates.has(k)) templates.set(k, await wallTemplate(l));
      }
    } catch (error) { flashHint(`${look.name} can't be used: ${error.message}`); return; }
    // each made again in the look where it stands, with its own numbers: one undo step for them all
    const entries = targets.map(r => {
      const gen = r.userData.source.added.generated, state = wallState(r), l = lookOf(r);
      const template = templates.get(l.donor ? JSON.stringify(l.donor) : l.id);
      let numbers = { ...gen[kind] };
      if (l.donor) numbers.look = { ...l.donor }; else if (l.id === defaults[kind]) delete numbers.look; else numbers.look = l.id;
      if (isFree(gen)) {
        // (a free-form piece keeps its extents and its form: its look and `plain` change, nothing else)
        delete numbers.plain;
        if (look.plain) { numbers.plain = true; delete numbers.look; }
        const was = stateOfRoot(r.userData), broken = gen.blasts ? { blasts: gen.blasts, ...(gen.breaksFurther ? { breaksFurther: true } : {}) } : {};
        return { source: template, matrix: movedMatrix(template, state.location, state.rotation),
                 state: { ...was, generated: { kind: gen.kind, version: gen.version, [kind]: numbers, ...broken } } };
      }
      if (kind === 'wall') {
        // (a look of another height: one storey if it was and the new look can be, else the look's own, and the openings
        // under its face's top)
        // (and on its bottom: openingsInLook)
        const { storeys: _, ...rest } = openingsInLook(gen[kind], numbers);
        numbers = withStoreys(rest, storeysInLook(gen[kind], rest)).wall;
      }
      // (its flags, tint and blasts stay with it: only its look changes; piece_records.js)
      const was = stateOfRoot(r.userData), broken = gen.blasts ? { blasts: gen.blasts, ...(gen.breaksFurther ? { breaksFurther: true } : {}) } : {};
      return { source: template, matrix: movedMatrix(template, state.location, state.rotation),
               state: { ...was, generated: { ...madeRequest(gen.kind, l, numbers, Boolean(look.plain)), ...broken } } };
    });
    // (only the pieces made again are deleted, not the rest of their locked group; pieces of one group, a room's,
    // take their places in it)
    const keys = targets.map(r => memberOf(r.userData.source)), held = groupIndex.get(keys[0]);
    const regroup = Boolean(held) && keys.every(k => groupIndex.get(k) === held);
    // The new pieces are made first (their meshes asked of the server), nothing changed meanwhile. Then, in one go after
    // that one wait, the old ones are deleted, the new ones placed and the group mended, joined as one undo step: nothing
    // done during the wait is joined to it, and a mesh that can't be had, or a piece changed meanwhile, leaves
    // everything as it was (review finding 30).
    const poses = targets.map(r => r.matrix.clone());
    const pasted = await pasteSnapshot({ entries, pivotIndex: Math.max(0, targets.indexOf(root)), name: look.name }, new THREE.Matrix4(), null, {
      whole: true,
      first: () => {
        if (targets.some((r, k) => roots.get(r.userData.source.id) !== r || r.userData.deleted || !r.matrix.equals(poses[k]))) return false;
        gizmo.setSelection(targets.map(r => r.userData.source.id));
        deleteNow(true, targets);
        return true;
      } });
    if (pasted.stopped) { flashHint(`${targets.length > 1 ? 'They' : 'It'} changed while the new look was made: choose ${look.name} again`); return; }
    if (pasted.lost) { flashHint(`${look.name} can't be used: ${plural(pasted.lost, 'piece')} in it could not be drawn (${pasted.why}); nothing changed`); return; }
    if (regroup) {
      const made = gizmo.picks().ids.map(id => roots.get(id)).filter(Boolean);
      changeGroups(next => {
        const g = next.get(held.id);
        if (!g) return;
        for (const k of keys) g.members.delete(k);
        for (const r of made) g.members.set(memberOf(r.userData.source), memberRecord(r.userData.source));
      });
    }
    gizmo.joinLast(regroup ? 3 : 2);
    const many = { wall: 'walls', slab: 'floors and roofs', ground: 'ground pieces' }[kind];
    flashHint(`${targets.length > 1 ? `${targets.length} ${many} now` : 'Now'} ${look.plain ? 'plain: the Build makes them in their kind\'s default look until one is chosen'
      : look.name.toLowerCase()} · Ctrl+Z puts the old ${targets.length > 1 ? 'ones' : 'one'} back`);
  }
  // A made piece's Look row (B2): the look it is in, or none chosen (drawn plain; the Build makes it in its kind's default
  // look and says so), Choose… and Plain.
  function lookRow(kind, g, name, tool) {
    const plain = isPlain(g), el = $(`${kind}LookName`);
    el.textContent = plain ? 'Look: none chosen' : `Look: ${name}`;
    el.title = plain ? `Drawn plain until a look is chosen; the Build makes it in ${name}, its kind's default look, and says so` : name;
    el.classList.toggle('warn', plain);
    if ($(`${kind}LookChange`)) $(`${kind}LookChange`).disabled = !tool;
    $(`${kind}LookPlain`).disabled = !tool || plain;
  }
  for (const kind of ['wall', 'slab', 'ground'])
    $(`${kind}LookPlain`).onclick = () => { const root = madeRoot(selected); if (root) setMadeLook(root, kind, plainLook(kind, root.userData.source.added.generated[kind])); };
  $('wallLookChange').onclick = () => { const root = madeRoot(selected); if (root) openLookPicker('wall', { onChoose: look => setMadeLook(root, 'wall', look), current: madeLookKey(root, 'wall') }); };
  $('slabLookChange').onclick = () => { const root = madeRoot(selected); if (root) openLookPicker('slab', { onChoose: look => setMadeLook(root, 'slab', look), current: madeLookKey(root, 'slab') }); };
  $('groundLookChange').onclick = () => {
    const root = madeRoot(selected);
    if (root) openLookPicker('ground', { onChoose: look => setMadeLook(root, 'ground', look), current: madeLookKey(root, 'ground'),
                                         sample: root.userData.source.added.generated.ground?.shape ?? 'patch' });
  };

  return { closeLookPicker, lookPickAt, lookRow, openLookPicker, prepareSample, setMadeLook, startLookPick,
           stopLookPick, storedLook };
}
