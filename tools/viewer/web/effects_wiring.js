// The Effects view (refactor stage P6; effects and sounds plan, FX1 to FX6 and the likeness; effects_view.js draws
// the markers and shapes, effects_rules.js says what a record is and what of it can change, effects_preview.js and
// effects_sim.js make the likeness). Each effect, sound and lens flare of the map and its streams is a root of its own
// in effectRoots, drawn as a marker. Here:
// - the roots: made, added and taken away, built from the map's records, where each stands now (deriveEffects: with
//   the piece that carries it, the landing's with its zone), which are drawn (refreshEffects), whether one can be
//   moved, copied or deleted (effectViewOnly);
// - the view on or off (setEffectsShown, setNormalEffects), its kinds' flyout, a marker picked, framed and named
//   under the pointer;
// - the likeness: each effect drawn moving where it stands, a copy being placed, the Add panel's pictures and its
//   hover pane;
// - the panel (effectPanel): what it is, the Wave preview, its values and their controls, the fixed box or the
//   sound's spheres;
// - the project's records of effects and sounds (effectState, applyEffectRecord, addedEffectOf, clearEffectEdits), an
//   added copy (addedEffect).
//
// createEffectsWiring takes what it needs of app.js as one argument object, when app.js makes it: the camera, the
// renderer and the scene, the textures and meshes as the map's pieces are read, the other views' switches, the
// landing zones, the Lights view's switch and its pieces' owners (ownerRoot), and the rail's view buttons
// (lightButton). Its own state is inside it
// (the kinds shown, the likenesses and the hover pane); what other areas read or set (the view's switch, the markers
// drawn, the redraw asked, the Wave preview's player, the likeness's switch and count) is editor_state.js's.
import * as THREE from 'three';
import { clock } from './build_queue.js';
import { onHub } from './edit_hub.js';
import { activeMapId, cleared, copySerial, data, effectIndex, effectMarkers, effectRoots, effectsDirty, effectsOn,
         families, foreignEffects, geometryCache, lightsOn, likenessOn, likenessThin, nextCopySerial, normalEffects,
         pickedEffect, pickedSpawn, pointer, roots, setCopySerial, setEffectMarkers, setEffectsDirty, setEffectsOn,
         setLikenessCount, setLikenessOn, setLikenessThin, setLiveCache, setNormalEffectsValue, setPickCentres,
         setTipDirty, setWavePlayer, spawnsOn, streamSet, volumesOn, wavePlayer, zonesOn } from './editor_state.js';
import { drawable, leftOut, makeLikeness, SWAP, viewHeight } from './effects_preview.js';
import { effectRecords, keptValues, KIND_LABEL, parameterControls, parameterRows, recordChips, recordLines, recordName,
         savedValues, soundReach, survivesClear, tintOf, tintVector, VALUE_LIMITS, valuesViewOnly, withValues } from './effects_rules.js';
import { LIMITS as LIKENESS_LIMITS, parametersOf } from './effects_sim.js';
import { boxShape, makeEffectMarker, nearestMarker, paintEffectMarker, reachShape } from './effects_view.js';
import { actorMatrix } from './gizmo.js';
import { setParagraphs } from './missions.js';
import { isStream, optionsOf, recordOf } from './piece_records.js';
import { targetKey, uuid } from './project.js';
import { landingUnmoved, yawOf } from './spawns.js';
import { recall, remember } from './storage.js';
import { plural, short, text } from './dom_words.js';

export function createEffectsWiring({ $, actorPose, assetUrl, baseMatrix, camera, carried, controls, effectTemplate,
                                     flashHint, gizmo, gltfLoader, isForeignTarget, lightButton, ownerRoot,
                                     pointOutside, renderer, sceneChanged, select, setLightsShown, setPickedSpawn,
                                     setSpawnsShown, setVolumesShown, setZonesShown, stopPickBox, texture, track,
                                     viewport, world, zoneState }) {
  // ---------------------------------------------------------------- the Effects view (effects and sounds plan, FX1)
  // The map's effects, sounds and lens flares (export 28; effects_view.js draws them, effects_rules.js says what they
  // are), and those of the streams the header's Mission picker shows. Shift+X (the rail's spark) shows them as markers
  // drawn over everything; while it is on a click picks one, never a piece, a light or a zone, and its panel says what
  // it is, where its values come from and what of the map uses it. View only. Each marker stands where the Build will
  // have it: an effect a piece carries follows the piece's move and goes with its delete, and each copy of the piece
  // gets one (drawn greyed, never picked); the landing's follow their moved zone; a cleared map keeps what clear_level
  // keeps. The rail button's flyout chooses which of the three kinds show.
  const EFFECT_FILTERS = 'workshop.effectFilters';
  const effectLayer = new THREE.Group(); effectLayer.visible = false; world.add(effectLayer);
  const effectShapes = new THREE.Group(); world.add(effectShapes);
  const effectFilters = { effect: true, sound: true, flare: true };
  try { Object.assign(effectFilters, JSON.parse(recall(EFFECT_FILTERS) || '{}')); } catch { /* the defaults */ }
  const effectsAvailable = () => Boolean(data) && data.scope === 'map' && !data.preview;
  // An actor's matrix (view basis) with its scale, as a record has its pose
  function effectMatrix(location, rotation, scale = [1, 1, 1]) {
    return actorMatrix(location, rotation ?? [0, 0, 0]).multiply(new THREE.Matrix4().makeScale(scale[0], scale[2], scale[1]));
  }
  // The map's own landings moved to another zone (as the Build reckons it: spawns.js landingUnmoved): actor path ->
  // { from, to } for their Skyrangers' actors
  function landingShifts() {
    const out = new Map();
    if (!effectsAvailable()) return out;
    const { zones, own, slots } = zoneState();
    for (const [k, j] of slots) {
      const o = own[j], z = zones[k];
      if (landingUnmoved(z, o)) continue;
      for (const a of o.landing?.skyranger?.actors ?? []) out.set(a.path, { from: o.zone, to: z });
    }
    return out;
  }
  // The roots (effects and sounds plan, FX3): one per record, its marker a child at the actor's place, its matrix the
  // actor's pose (view basis, no scale: a box or a sphere is drawn with it). A copy is a root whose source is its
  // original's record under its own output name (`added`: from, entity, kind, base: the original's record).
  const derivedEffects = new THREE.Group(); effectLayer.add(derivedEffects);
  const effectKey = o => targetKey({ package: o.sourcePackage, level: o.layer, actor: o.actor });
  const effectSource = rec => ({ ...rec, isEffect: true, matrix: actorMatrix(rec.location, rec.rotation ?? [0, 0, 0]).toArray() });
  function makeEffectRoot(source) {
    const root = new THREE.Group();
    root.matrixAutoUpdate = false; root.matrix.fromArray(source.matrix);
    const marker = makeEffectMarker(source);
    marker.userData.record = source;
    root.add(marker);
    root.userData = { source, effect: true, marker, deleted: false, edit: null, stays: false, parts: [], values: null };
    marker.userData.root = root;
    return root;
  }
  function addEffectRoots(list) {
    for (const root of list) {
      const o = root.userData.source;
      effectRoots.set(o.id, root); effectLayer.add(root);
      if (!o.added && !isStream(o)) effectIndex.set(effectKey(o), root);
    }
    setEffectsDirty(true); setLiveCache(null);
  }
  function removeEffectRoots(list) {
    for (const root of list) { effectRoots.delete(root.userData.source.id); effectLayer.remove(root); }
    setEffectsDirty(true); setLiveCache(null);
  }
  // The map's records and every stream's, as roots, once the map's pieces are built (a stream's show with its mission)
  function buildEffects() {
    removeEffectRoots([...effectRoots.values()]);
    effectIndex.clear();
    if (!effectsAvailable()) return;
    const all = [...effectRecords(data, null), ...Object.values(data.streams ?? {}).flatMap(st => [...(st.effects ?? []), ...(st.sounds ?? []), ...(st.flares ?? [])])];
    addEffectRoots(all.filter(r => r.kind && Array.isArray(r.location)).map(r => makeEffectRoot(effectSource(r))));
  }
  // Why an effect, sound or flare can't be moved, copied or deleted (`cap`), or null: a stream's is view only, as are
  // all of a kind whose family doesn't build (families.json: effect, sound, flare); an original as its record's `can`
  // says.
  function effectViewOnly(o, cap = 'move') {
    if (isStream(o)) return `it belongs to the stream ${o.stream}, which the editor shows but doesn't change`;
    if (!families?.families?.[o.kind]?.builds) return `${o.kind === 'sound' ? 'sounds' : o.kind === 'flare' ? 'lens flares' : 'effects'} are shown, not changed, in this editor version`;
    if (o.added) return null;
    return o.can?.[cap] ? null : (o.why?.[cap] ?? 'the map\'s export doesn\'t say it can');
  }
  // Whether an effect follows the piece that carries it (no pose of its own, not kept where it is, not deleted)
  const effectFollows = r => Boolean(r.userData.source.carriedBy && !r.userData.source.added && !r.userData.source.landingRole
    && !r.userData.edit && !r.userData.stays && !r.userData.deleted);
  const effectEdited = r => !isStream(r.userData.source) && Boolean(r.userData.source.added || r.userData.deleted || r.userData.edit
    || (r.userData.stays && r.userData.source.carriedBy) || r.userData.values);
  // The record as the project has it (stage FX5): its values put on it (a copy's on its original's record)
  const effectNow = (root, r = root.userData.source) => withValues(r.added ? { ...r.added.base, ...poseOf(r) } : r, root.userData.values, effectSystemsOf(r));
  const poseOf = r => ({ location: r.location, rotation: r.rotation, actor: r.actor });
  // The particle systems effects name: the map's, with those of other maps' copies joined (effectTemplate)
  const effectSystemsOf = () => data?.effectSystems;
  // Where each original stands now (a carried one with its piece, the landing's with its zone, one with a pose of its
  // own where it was put), whether its piece's delete takes it away, and the copies each copy of its piece carries
  // (markers of their own, drawn greyed, never picked)
  function deriveEffects() {
    for (const m of [...derivedEffects.children]) { m.material.dispose(); derivedEffects.remove(m); }
    const shifts = landingShifts(), copies = new Map();
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (!o.added?.from || o.foreign || r.userData.deleted) continue;
      const k = `${o.added.from.actor}|${o.component}`;
      if (!copies.has(k)) copies.set(k, []);
      copies.get(k).push(r);
    }
    for (const root of effectRoots.values()) {
      const o = root.userData.source;
      root.userData.derivedGone = false; root.userData.carrierMoved = false;
      if (o.added || isStream(o)) continue;
      const base = baseMatrix(root);
      const carrier = effectFollows(root) ? ownerRoot(o.carriedBy) : null;
      if (!root.userData.edit) {
        let matrix = base;
        const shift = o.landingRole ? shifts.get(o.actor) : null;
        if (shift) {
          const d = yawOf(shift.to.direction) - yawOf(shift.from.direction), [pi, y, w] = o.rotation ?? [0, 0, 0];
          matrix = actorMatrix(carried(o.location, shift.from, shift.to), [pi, y + d, w]);
        } else if (carrier?.userData.deleted) root.userData.derivedGone = true;
        else if (carrier?.userData.edit) { matrix = carrier.userData.edit.clone().multiply(base); root.userData.carrierMoved = true; }
        root.matrix.copy(matrix); root.matrixWorldNeedsUpdate = true;
      }
      if (!carrier || carrier.userData.deleted) continue;
      const back = baseMatrix(carrier).invert();
      for (const copy of copies.get(`${carrier.userData.source.actor}|${carrier.userData.source.component}`) ?? []) {
        const m = makeEffectMarker(o);
        m.position.setFromMatrixPosition(copy.matrix.clone().multiply(back).multiply(base));
        Object.assign(m.userData, { derived: true, matrix: copy.matrix.clone().multiply(back).multiply(base) });   // (its colour kept)
        derivedEffects.add(m);
      }
    }
  }
  // The Effects view, or the normal view with its Effects switch: the markers are drawn and picked
  const effectsShown = () => effectsAvailable() && (effectsOn || (normalEffects && !volumesOn && !lightsOn && !zonesOn));
  const pickedMarker = () => { const root = pickedEffect ? effectRoots.get(pickedEffect) : null; return root?.visible ? root.userData.marker : null; };
  function paintEffects() {
    const picks = new Set(gizmo.picks().ids);
    for (const m of effectMarkers) {
      const o = m.userData.record;
      paintEffectMarker(m, { picked: !m.userData.derived && picks.has(o.id), dim: m.userData.derived || isStream(o) || Boolean(effectViewOnly(o, 'move') && effectViewOnly(o, 'copy')) });
    }
  }
  // What is drawn now: each root shown or not (its kind ticked, not deleted or taken by its piece's delete, its stream's
  // mission chosen, kept by a clear, in the play area under Interior), and the carried copies
  function refreshEffects() {
    setEffectsDirty(false); setPickCentres(null);
    if (!effectsAvailable()) { setEffectMarkers([]); effectLayer.visible = false; refreshLikenesses(); return; }
    deriveEffects();
    const shown = effectsShown();
    effectLayer.visible = shown;
    // Interior shows what stands in the play area (view basis, as playableBounds)
    const play = $('scenery').value === 'interior' ? data.playableBounds : null;
    const at = new THREE.Vector3(), inAnyPlay = v => !play || [0, 1, 2].every(k => v.getComponent(k) >= play.min[k] - 48 && v.getComponent(k) <= play.max[k] + 48);
    setEffectMarkers([]);
    for (const root of effectRoots.values()) {
      const o = root.userData.source;
      at.setFromMatrixPosition(root.matrix);
      // (the Build will have it, and the view shows where it stands: what its likeness needs too)
      root.userData.there = !root.userData.deleted && !root.userData.derivedGone
        && (!isStream(o) || streamSet.has(o.stream))
        && (Boolean(o.added) || survivesClear(o, { cleared, outside: pointOutside, carrierMoved: root.userData.carrierMoved, moved: Boolean(root.userData.edit) }))
        && inAnyPlay(at);
      root.visible = shown && effectFilters[o.kind] !== false && root.userData.there;
      if (root.visible) effectMarkers.push(root.userData.marker);
    }
    for (const m of derivedEffects.children) {
      m.userData.there = inAnyPlay(m.position);
      m.visible = shown && effectFilters[m.userData.record.kind] !== false && m.userData.there;
      if (m.visible) effectMarkers.push(m);
    }
    // what can't be seen can't stay selected
    const picks = gizmo.picks(), keep = picks.ids.filter(id => !effectRoots.has(id) || effectRoots.get(id).visible || !shown);
    if (keep.length !== picks.ids.length) gizmo.setSelection(keep, keep.includes(picks.active) ? picks.active : keep[0] ?? null);
    paintEffects(); effectPanel(); drawEffectShape(); refreshLikenesses();
  }
  // ---- The likeness (effects and sounds plan, Part J2, stage FXV2; effects_preview.js, effects_sim.js): each effect the
  // Build will have, drawn where it stands, moving, roughly as the game draws it, in every view (View options' Effects
  // as they look). One that starts off is drawn only while it is picked. A likeness is never picked: its marker is the
  // handle. `likenesses`: a root's or a carried copy's marker -> { likeness, key }.
  const likenessLayer = new THREE.Group(); world.add(likenessLayer);
  const likenesses = new Map();
  setLikenessOn(recall('workshop.likeness') !== '0');     // (likenessOn, likenessThin, likenessCount: editor_state.js)
  const likenessDeps = {
    texture: key => texture(key, true),
    // a mesh particle's mesh as the map's pieces' are read, each drawn part with its material's colour texture
    async meshParts(draw) {
      if (!data.meshes[draw.mesh]) return [];
      track(geometryCache, draw.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[draw.mesh].url)));
      const gltf = await geometryCache.get(draw.mesh), parts = [];
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse(child => { if (child.isMesh) parts.push(child); });
      return Promise.all(parts.map(async (child, i) => {
        const info = data.materials[draw.materials?.[i] ?? draw.materials?.[0]];
        return { geometry: child.geometry, map: info?.diffuse ? await texture(info.diffuse, true).catch(() => null) : null };
      }));
    },
  };
  function dropLikeness(owner) {
    const kept = likenesses.get(owner);
    if (!kept) return;
    likenessLayer.remove(kept.likeness.group); kept.likeness.dispose(); likenesses.delete(owner);
  }
  // What a likeness is made of: its system, the effect's parameters as edited and its seed; a change makes it anew
  function refreshLikenesses() {
    const wanted = new Map();
    if (likenessOn && effectsAvailable()) {
      const want = (owner, record, id) => {
        const system = effectSystemsOf(record)?.[record.system];
        if (drawable(system)) wanted.set(owner, { record, system, id });
      };
      for (const root of effectRoots.values()) {
        const o = root.userData.source;
        if (o.kind !== 'effect' || !root.userData.there) continue;
        const now = effectNow(root, o);
        if (now.startsOn === false && pickedEffect !== o.id) continue;
        want(root, now, o.id);
      }
      for (const m of derivedEffects.children) if (m.userData.there && m.userData.record.kind === 'effect' && m.userData.record.startsOn !== false) want(m, m.userData.record, `derived:${m.id}`);
    }
    for (const owner of [...likenesses.keys()]) if (!wanted.has(owner)) dropLikeness(owner);
    for (const [owner, { record, system, id }] of wanted) {
      const params = parametersOf(record), key = `${record.system}|${system.fingerprint}|${JSON.stringify(params)}`;
      if (likenesses.get(owner)?.key === key) { likenesses.get(owner).record = record; continue; }
      dropLikeness(owner);
      let seed = 0;
      for (const c of String(id)) seed = (seed * 31 + c.charCodeAt(0)) >>> 0;
      const likeness = makeLikeness(system, likenessDeps, { params, seed: seed % 100003 });
      likenessLayer.add(likeness.group);
      likenesses.set(owner, { likeness, key, record });
    }
  }
  const likenessBox = new THREE.Box3(), likenessFrustum = new THREE.Frustum(), likenessAt = new THREE.Vector3(), likenessMatrix = new THREE.Matrix4();
  // Each frame: every likeness put where its effect stands now (a drag moves it) and stepped, unless it is out of the
  // picture or too far to tell; over the view's budget of particles, what they spawn is thinned evenly
  function stepLikenesses(dt) {
    if (!likenesses.size) { setLikenessCount(0); return; }
    likenessFrustum.setFromProjectionMatrix(likenessMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse));
    let count = 0;
    const pixelsPerUnit = renderer.domElement.clientHeight / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
    for (const [owner, { likeness, record }] of likenesses) {
      const matrix = owner.userData.effect ? owner.matrix : owner.userData.matrix, cp = record.componentPose;
      const s = record.scale ?? [1, 1, 1], cs = cp?.scale ?? [1, 1, 1];
      const g = likeness.group;
      g.matrix.copy(matrix).multiply(likenessMatrix.makeScale(s[0], s[2], s[1]));
      if (cp) g.matrix.multiply(effectMatrix(cp.translation, cp.rotation, cp.scale));
      g.matrix.multiply(SWAP);
      g.matrixWorldNeedsUpdate = true;
      likenessAt.setFromMatrixPosition(matrix);
      const reach = 1200 * Math.max(Math.abs(s[0]), Math.abs(s[1]), Math.abs(s[2]), 1);
      likenessBox.setFromCenterAndSize(likenessAt, likenessAt.clone().setScalar(2 * reach));
      // (in the picture, and more than a few pixels of it: a whole large map seen from afar steps nothing)
      g.visible = likenessFrustum.intersectsBox(likenessBox) && reach * pixelsPerUnit / Math.max(1, camera.position.distanceTo(likenessAt)) > 6;
      if (!g.visible) continue;
      likeness.step(dt, likenessThin, [Math.abs(s[0] * cs[0]), Math.abs(s[1] * cs[1])]);
      count += likeness.count();
    }
    setLikenessCount(count);
    // towards the budget, a little a frame, so nothing pops
    const want = count > LIKENESS_LIMITS.view ? likenessThin * LIKENESS_LIMITS.view / count : Math.min(1, likenessThin * 1.05);
    setLikenessThin(Math.max(0.02, likenessThin + (want - likenessThin) * 0.2));
  }
  // A drawn-only copy of an effect (what is being placed, under the cursor): its likeness plays there while the copy is
  // in the view; it goes a little after the copy does.
  const ghostLikenesses = [];
  function ghostLikeness(holder, source) {
    if (!likenessOn || source.kind !== 'effect' || !data) return;
    const record = source.added ? { ...source.added.base, scale: source.scale ?? source.added.base.scale } : source;
    const system = effectSystemsOf(record)?.[record.system];
    if (!drawable(system)) return;
    const likeness = makeLikeness(system, likenessDeps, { params: parametersOf(record), seed: 11 });
    holder.add(likeness.group);
    ghostLikenesses.push({ likeness, holder, record, idle: 0 });
  }
  function stepGhostLikenesses(dt) {
    for (let k = ghostLikenesses.length - 1; k >= 0; k--) {
      const g = ghostLikenesses[k];
      let top = g.holder;
      while (top.parent) top = top.parent;
      if (top !== world) { if (++g.idle > 180) { g.likeness.dispose(); g.holder.remove(g.likeness.group); ghostLikenesses.splice(k, 1); } continue; }
      g.idle = 0;
      const s = g.record.scale ?? [1, 1, 1], cp = g.record.componentPose, cs = cp?.scale ?? [1, 1, 1], m = g.likeness.group.matrix;
      m.makeScale(s[0], s[2], s[1]);
      if (cp) m.multiply(effectMatrix(cp.translation, cp.rotation, cp.scale));
      m.multiply(SWAP);
      g.likeness.group.matrixWorldNeedsUpdate = true;
      g.likeness.step(dt, 1, [Math.abs(s[0] * cs[0]), Math.abs(s[1] * cs[1])]);
    }
  }
  // ---- An effect of the Add panel as a picture and as a moving preview (stage FXV3). The picture: its likeness, warm,
  // with its textures read, handed to the list to draw in a frame as a piece's is. The preview: the likeness of the row
  // under the pointer, played in a small pane beside the list, turning slowly over a tile's square.
  async function likenessOfEntry(entry, seed) {
    if (!data) return null;
    const source = await effectTemplateOf(entry);
    const system = source && effectSystemsOf(source)?.[source.system];
    if (!drawable(system)) return null;
    const likeness = makeLikeness(system, likenessDeps, { params: parametersOf(source), seed });
    const s = source.scale ?? [1, 1, 1];
    likeness.group.matrix.makeScale(s[0], s[2], s[1]).multiply(SWAP);
    likeness.group.matrixWorldNeedsUpdate = true;
    return { likeness, scale: [Math.abs(s[0]), Math.abs(s[1])], source, system };
  }
  // this map's own effect by its record, another map's by its template (read from its map)
  async function effectTemplateOf(entry) {
    if (!isForeignTarget({ ...entry.source, level: 'base' })) {
      return [...effectRoots.values()].map(r => r.userData.source).find(o => !o.added && o.layer === 'base' && short(o.actor) === entry.source.actor) ?? null;
    }
    return effectTemplate(entry.source);
  }
  async function effectPicture(entry) {
    const made = await likenessOfEntry(entry, 7);
    if (!made) return null;
    const { likeness, scale } = made;
    await likeness.ready();
    likeness.step(1 / 30, 1, scale);
    // one that has nothing alive at its warm start (a rare spark) is run on until it has, for a few seconds
    // (framed on what most of it fills: a fire's far sparks would make its flames a speck)
    let box = likeness.bounds(0.8);
    for (let t = 0; !box && t < 6; t += 1 / 15) { likeness.step(1 / 15, 1, scale); box = likeness.bounds(0.8); }
    if (!box) { likeness.dispose(); return null; }
    return { object: likeness.group, box: box.applyMatrix4(likeness.group.matrix), dispose: () => likeness.dispose() };
  }
  const likenessPane = { scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(32, 1, 1, 100000), shown: null, token: 0, turn: 0, sphere: new THREE.Sphere(new THREE.Vector3(), 96) };
  likenessPane.scene.background = new THREE.Color(0x10161b);
  {
    // a tile's square on the ground, for size
    const h = 48, pts = [[-h, -h], [h, -h], [h, -h], [h, h], [h, h], [-h, h], [-h, h], [-h, -h]].map(([x, z]) => new THREE.Vector3(x, 0, z));
    const tile = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0x5f7684 }));
    likenessPane.scene.add(tile);
  }
  let likenessHover = null;
  function hoverLikeness(entry, item) {
    clearTimeout(likenessHover);
    const pane = $('likenessPane'), token = ++likenessPane.token;
    const close = () => { if (likenessPane.shown) { likenessPane.scene.remove(likenessPane.shown.likeness.group); likenessPane.shown.likeness.dispose(); likenessPane.shown = null; } pane.hidden = true; };
    // the row's tip is said in the pane while the pointer is on the row: the browser's own tooltip would cover it
    // (a call with no row, as the panel closes, gives the last row hovered its tip back)
    const row = item ?? likenessPane.item;
    const giveBack = () => { if (row && row.dataset.tip !== undefined) { row.title = row.dataset.tip; delete row.dataset.tip; } if (likenessPane.item === row) likenessPane.item = null; };
    if (!entry || !likenessOn) { giveBack(); close(); return; }
    const tip = item.dataset.tip ?? item.title ?? '';
    item.dataset.tip = tip; item.title = '';
    likenessPane.item = item;
    likenessHover = setTimeout(async () => {
      const made = await likenessOfEntry(entry, 3).catch(() => null);
      if (token !== likenessPane.token) { made?.likeness.dispose(); return; }
      close();
      if (!made) { giveBack(); return; }
      likenessPane.shown = made; likenessPane.sphere.set(new THREE.Vector3(0, 48, 0), 96);
      likenessPane.scene.add(made.likeness.group);
      const row = item.getBoundingClientRect(), host = viewport.getBoundingClientRect();
      pane.style.left = `${row.right - host.left + 10}px`;
      pane.style.top = `${Math.max(8, Math.min(row.top - host.top - 90, host.height - 290))}px`;
      const paneText = $('likenessText');
      paneText.replaceChildren();
      paneText.append(entry.name);
      const out = leftOut(made.system), small = document.createElement('small');
      small.textContent = [`${entry.group} · the square is one tile`, out.ignored.length ? 'drawn roughly' : null].filter(Boolean).join(' · ');
      paneText.append(small);
      for (const line of tip.split('\n').filter(Boolean)) { const more = document.createElement('small'); more.textContent = line; paneText.append(more); }
      pane.hidden = false;
    }, 300);
  }
  // Each frame, before the view is drawn: the pane's likeness stepped and drawn into its canvas (through the view's own
  // renderer, as the list's pictures are)
  function drawLikenessPane(dt) {
    const shown = likenessPane.shown, canvas = renderer.domElement, size = renderer.getSize(new THREE.Vector2());
    if (!shown || $('likenessPane').hidden || size.x < 220 || size.y < 220) return;
    shown.likeness.step(dt, 1, shown.scale);
    const box = shown.likeness.bounds(0.85);
    if (box) {
      // the camera follows what is alive, easing, and never closer than a tile
      const s = box.applyMatrix4(shown.likeness.group.matrix).getBoundingSphere(new THREE.Sphere());
      likenessPane.sphere.center.lerp(s.center, 0.08);
      likenessPane.sphere.radius += (Math.max(70, s.radius) - likenessPane.sphere.radius) * 0.08;
    }
    likenessPane.turn += dt * 0.35;
    const c = likenessPane.camera, r = likenessPane.sphere.radius, d = r / Math.sin(THREE.MathUtils.degToRad(c.fov / 2)) * 1.05;
    c.position.set(Math.cos(likenessPane.turn) * d * 0.87, d * 0.5, Math.sin(likenessPane.turn) * d * 0.87).add(likenessPane.sphere.center);
    c.near = Math.max(1, d - r * 3); c.far = d + r * 4;
    c.lookAt(likenessPane.sphere.center); c.updateProjectionMatrix();
    const px = Math.round(220 * renderer.getPixelRatio());
    renderer.setScissorTest(true);
    renderer.setViewport(0, 0, 220, 220); renderer.setScissor(0, 0, 220, 220);
    const height = viewHeight.value;
    viewHeight.value = 220;
    renderer.render(likenessPane.scene, c);
    viewHeight.value = height;
    renderer.setScissorTest(false); renderer.setViewport(0, 0, size.x, size.y);
    const out = $('likenessCanvas');
    if (out.width !== px) out.width = out.height = px;
    out.getContext('2d').drawImage(canvas, 0, canvas.height - px, px, px, 0, 0, px, px);
  }
  function setLikeness(on) {
    setLikenessOn(Boolean(on));
    remember('workshop.likeness', likenessOn ? '1' : '0');
    $('likenessToggle').checked = likenessOn;
    refreshLikenesses();
  }
  $('likenessToggle').checked = likenessOn;
  $('likenessToggle').onchange = e => { setLikeness(e.target.checked); e.target.blur(); };
  function effectPanel() {
    const m = effectsShown() ? pickedMarker() : null;
    if (wavePlayer && (!m || m.userData.record.id !== wavePlayer.record)) stopWave();
    $('effectPanel').hidden = !m;
    if (!m) return;
    const root = m.userData.root, r = m.userData.record, now = effectNow(root, r), { title, lines } = recordLines(now, { ...data, effectSystems: effectSystemsOf(r) });
    // what an edit does with it here (effects and sounds plan, FX3), where its family builds
    if (!effectViewOnly(r, 'move') || !effectViewOnly(r, 'copy') || !effectViewOnly(r, 'delete')) {
      if (r.added?.base?.foreign) lines.unshift(`A copy of ${short(r.added.from.actor)} of ${r.added.from.package}: the Build brings it into this map with the ${r.kind === 'sound' ? 'waves' : r.kind === 'flare' ? 'flare template' : 'particle system'} it needs (or this map's, where it has them already) and makes it an actor of its own.`);
      else if (r.added) lines.unshift(`A copy of ${short(r.added.from.actor)}: the Build makes it an actor of its own.`);
      else if (root.userData.deleted) lines.unshift('Deleted: the Build takes it out of the level (Ctrl+Z brings it back).');
      else if (root.userData.edit) lines.unshift(`Moved${r.carriedBy ? `: it stays where it is put when ${short(r.carriedBy)} moves` : ''}. Reset puts it back${r.carriedBy ? ' and lets it follow its piece again' : ''}.`);
      else if (r.carriedBy && root.userData.stays) lines.unshift(`Kept where it is: it doesn't move with ${short(r.carriedBy)}. Reset lets it follow again.`);
      else if (r.carriedBy && !r.landingRole) lines.unshift(`It moves with ${short(r.carriedBy)}; moved by itself, it stays where it is put.`);
      const can = ['move', 'copy', 'delete'].filter(c => !effectViewOnly(r, c));
      lines.push(`The gizmo ${can.includes('move') ? 'moves and turns it' : 'doesn\'t move it'}${can.includes('copy') ? ', Ctrl+C and Ctrl+V copy it' : ''}${can.includes('delete') ? ', Delete deletes it' : ''}.`);
    }
    const stayButton = $('effectStay');
    stayButton.hidden = !(r.carriedBy && !r.added && !r.landingRole && !root.userData.edit && !root.userData.deleted && !effectViewOnly(r, 'move'));
    stayButton.textContent = root.userData.stays ? `Follow ${short(r.carriedBy ?? '')}` : 'Keep where it is';
    stayButton.title = root.userData.stays ? `It moves, copies and deletes with ${short(r.carriedBy ?? '')} again` : `It stays where it is when ${short(r.carriedBy ?? '')} moves or is deleted, and the piece's copies don't carry it`;
    $('effectTitle').textContent = title;
    const chips = $('effectChips');
    chips.replaceChildren();
    for (const c of recordChips(r.added ? { ...now, carriedBy: null, landingRole: null, referencedBy: [], floors: [], prefab: null } : now, data)) text(chips, 'span', c.text, 'chip').title = c.title;
    chips.hidden = !chips.children.length;
    // what its likeness leaves out, in words about the drawing
    if (r.kind === 'effect' && likenessOn) {
      const system = effectSystemsOf(r)?.[r.system], out = leftOut(system);
      const WORDS = { Orbit: 'its swirl', Collision: 'its bounces', CollisionPrediction: 'its bounces', AttractorPoint: 'its pull to a point', EventGenerator: 'what its particles set off', EventReceiverSpawn: 'what another emitter sets off' };
      const named = [...new Set(out.ignored.map(k => WORDS[k]).filter(Boolean))];
      if (system && !drawable(system)) lines.push(`Not drawn here${out.undrawn.length ? `: ${out.undrawn[0]}` : ''}.`);
      else if (named.length) lines.push(`Drawn here without ${named.length > 1 ? `${named.slice(0, -1).join(', ')} and ${named.at(-1)}` : named[0]}.`);
    }
    setParagraphs($('effectInfo'), lines.join('\n'));
    $('effectAboutSum').textContent = lines[0] ?? '';      // (the fold's one line: what was done to it, else what it is)
    $('effectAboutSum').title = lines[0] ?? '';
    // a sound's waves, each with its Play button
    const waves = r.kind === 'sound' ? [...new Set(r.waves ?? [])] : [], box = $('effectWaves');
    box.replaceChildren();
    box.hidden = !waves.length;
    if (waves.length) {
      text(box, 'div', 'Wave preview', 'posehead').title = 'Plays the wave by itself at a preview volume: the game\'s sound (its reach, volume, pitch, random choice and looping) is not reproduced';
      for (const w of waves) {
        const info = data.soundWaves?.[w], line = text(box, 'div', '', 'waverow');
        text(line, 'span', info?.name ?? w.split('|').at(-1), 'name').title = w.split('|').at(-1);
        const button = text(line, 'button', 'Play');
        button.type = 'button'; button.dataset.wave = w;
        if (info?.playable) button.onclick = () => playWave(r, w);
        else { button.disabled = true; button.title = `It can't be played: ${info?.why ?? 'the map doesn\'t describe it'}`; }
        text(line, 'span', '', 'status').dataset.wave = w;
      }
    }
    paintWaves();
    // its values, where they build and its record says they can change (stage FX5); else what it has, read only
    const valueBox = $('effectValues'), editable = effectValuesEditable(root);
    valueBox.replaceChildren();
    valueBox.hidden = !editable;
    if (editable) effectValueControls(valueBox, root, now);
    const rows = r.kind === 'effect' && !editable ? parameterRows(now, { ...data, effectSystems: effectSystemsOf(r) }) : [], table = $('effectParams');
    table.replaceChildren();
    table.hidden = !rows.length;
    if (rows.length) {
      const head = text(table, 'div', `Particle parameters${r.parametersFrom && r.parametersFrom !== 'actor' ? ` (${r.parametersFrom === 'archetype' ? 'its archetype\'s' : 'its class\'s'})` : ''}`, 'posehead');
      head.title = 'What the map sets on this effect\'s particle system: values its system reads by name';
      for (const row of rows) {
        const line = text(table, 'div', '', 'effectparam');
        text(line, 'span', row.name, 'name');
        const value = text(line, 'span', row.text, 'value');
        if (row.colour) {
          const swatch = document.createElement('i');
          swatch.className = 'swatch';
          swatch.style.background = `rgb(${row.colour.map(v => Math.round(Math.pow(Math.max(0, Math.min(1, v)), 1 / 2.2) * 255)).join(',')})`;
          value.prepend(swatch);
        }
        if (row.note) { line.classList.add('odd'); line.title = row.note; }
      }
    }
  }
  // The Wave preview (effects and sounds plan, FX2): one wave of the picked sound at a time, played by a click through
  // /maps/<id>/wave.ogg (audio.py), which checks it before sending it. Picking something else, leaving the view or
  // opening another map or project stops it and lets it go; a refusal shows the server's reason.
  function stopWave() {
    const player = wavePlayer;
    setWavePlayer(null);
    if (player) { player.audio.pause(); player.audio.removeAttribute('src'); player.audio.load(); }
    paintWaves();
  }
  function ownWave(wave) {
    const pkg = wave.split('|')[0].toLowerCase(), file = String(data.source?.file ?? '').split(/[\\/]/).pop().replace(/\.upk$/i, '');
    return [data.name, file, ...Object.keys(data.streams ?? {})].some(n => String(n).toLowerCase() === pkg);
  }
  function playWave(record, wave) {
    const again = wavePlayer?.wave === wave && wavePlayer.record === record.id && wavePlayer.state !== 'failed';
    stopWave();
    if (again) return;      // its Stop button
    // a wave of this map or its streams through the map's export; another map's (a copy of its sound: FX4) from that map
    const url = ownWave(wave) ? `/maps/${encodeURIComponent(activeMapId)}/wave.ogg?id=${encodeURIComponent(wave)}`
      : `/library/wave.ogg?${new URLSearchParams({ package: wave.split('|')[0], id: wave })}`;
    const audio = new Audio(), player = setWavePlayer({ audio, wave, record: record.id, state: 'loading', why: null });
    const mine = () => wavePlayer === player;
    audio.volume = 0.6;
    audio.addEventListener('playing', () => { if (mine()) { player.state = 'playing'; paintWaves(); } });
    audio.addEventListener('timeupdate', () => { if (mine()) paintWaves(); });
    audio.addEventListener('ended', () => { if (mine()) stopWave(); });
    audio.addEventListener('error', () => { if (mine()) waveFailed(player, url); });
    audio.src = url;
    audio.play().catch(e => { if (mine() && e.name !== 'AbortError') waveFailed(player, url, e); });
    paintWaves();
  }
  async function waveFailed(player, url, error) {
    if (player.state === 'failed') return;
    player.state = 'failed';
    player.audio.pause(); player.audio.removeAttribute('src');
    paintWaves();
    // the server's reason when it refused the wave; else the browser couldn't play what it was sent
    let why = error?.name === 'NotAllowedError' ? 'the browser did not let it play' : 'the browser could not decode it';
    try {
      const reply = await fetch(url, { headers: { Range: 'bytes=0-0' } });
      if (!reply.ok) why = (await reply.json().catch(() => null))?.error ?? `the server answered ${reply.status}`;
    } catch { why = 'the server did not answer'; }
    player.why = why;
    if (wavePlayer === player) paintWaves();
  }
  function paintWaves() {
    const time = t => (Number.isFinite(t) ? clock(t) : '');
    for (const el of $('effectWaves').querySelectorAll('[data-wave]')) {
      const p = wavePlayer?.wave === el.dataset.wave && wavePlayer.record === pickedEffect ? wavePlayer : null;
      if (el.tagName === 'BUTTON') {
        if (el.disabled) continue;
        el.textContent = p && p.state !== 'failed' ? 'Stop' : 'Play';
        el.classList.toggle('on', Boolean(p && p.state !== 'failed'));
      } else {
        el.textContent = !p ? '' : p.state === 'loading' ? 'loading…' : p.state === 'failed' ? (p.why ? `Not played: ${p.why}` : 'Not played…')
          : `${time(p.audio.currentTime)} / ${time(p.audio.duration)}`;
        el.classList.toggle('bad', p?.state === 'failed');
      }
    }
  }
  // The picked effect's fixed box through its pose, scale and component, or a picked sound's spheres
  function drawEffectShape() {
    for (const c of [...effectShapes.children]) { c.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); effectShapes.remove(c); }
    const m = effectsShown() ? pickedMarker() : null;
    if (!m) return;
    const r = effectNow(m.userData.root, m.userData.record), matrix = m.userData.root.matrix;
    if (r.kind === 'effect') {
      const cp = r.componentPose;
      const component = cp ? effectMatrix(cp.translation, cp.rotation, cp.scale) : new THREE.Matrix4();
      const scaled = matrix.clone().multiply(new THREE.Matrix4().makeScale(r.scale?.[0] ?? 1, r.scale?.[2] ?? 1, r.scale?.[1] ?? 1));
      const shape = boxShape(effectSystemsOf(m.userData.record)?.[r.system], scaled.multiply(component));
      if (shape) effectShapes.add(shape);
    } else if (r.kind === 'sound') effectShapes.add(reachShape(soundReach(r), new THREE.Vector3().setFromMatrixPosition(matrix)));
  }
  // One effect, sound or flare selected by its id (the chip on a carrying piece, the tests), or none
  function pickEffect(id, add = false) {
    if (effectsDirty) refreshEffects();
    const root = id ? effectRoots.get(id) : null;
    if (id && !root?.visible) {
      const r = root?.userData.source;
      if (r) flashHint(effectFilters[r.kind] === false ? `${KIND_LABEL[r.kind]}s are hidden: tick them in the Effects view's flyout`
        : $('scenery').value === 'interior' ? 'It stands outside the play area: Full shows it' : 'It isn\'t drawn: it is deleted, its piece is, or the clear takes it out');
    }
    select(root?.visible ? id : null, add && Boolean(root?.visible));
  }
  // F in the Effects view: the camera on the picked marker, brought within `reach` of it (a sound: its reach)
  function frameEffect() {
    const m = pickedMarker();
    if (!m) return false;
    // (far enough to see a sound's outer sphere and its handles whole)
    const r = effectNow(m.userData.root, m.userData.record), reach = Math.max(600, Math.min(8000, (soundReach(r)?.outer ?? 240) * 2.6));
    const at = new THREE.Vector3().setFromMatrixPosition(m.userData.root.matrix), away = camera.position.clone().sub(controls.target);
    // (a sound from as far as shows its spheres whole; an effect from no further than that)
    if (away.length() > reach || (r.kind === 'sound' && soundReach(r))) away.setLength(reach);
    controls.target.copy(at); camera.position.copy(at).add(away); controls.update();
    return true;
  }
  // The root whose marker is under a screen point (within 13 pixels), or null
  function effectAt(clientX, clientY) {
    const m = nearestMarker(effectMarkers.filter(x => !x.userData.derived), camera, renderer.domElement.getBoundingClientRect(), clientX, clientY);
    return m ? m.userData.root : null;
  }
  function pickEffectAt(clientX, clientY, add = false) {
    const root = effectAt(clientX, clientY);
    if (root) select(root.userData.source.id, add); else if (!add) select(null);
  }
  // Keep where it is / Follow (the panel's button): a carried effect kept from its piece's moves, or following again;
  // one undo step (its record's effect.follow: none, or none at all)
  function setEffectStays(root, stays) {
    if (Boolean(root.userData.stays) === stays) return;
    gizmo.record({ redo: () => { root.userData.stays = stays; sceneChanged(); select(root.userData.source.id, false, true); },
                   undo: () => { root.userData.stays = !stays; sceneChanged(); select(root.userData.source.id, false, true); } });
  }
  // An effect's or sound's values (stage FX5): offered where their family builds (families.json effect-values,
  // sound-values) and the record (a copy's original's) says they can change. Each change is one undo step.
  function effectValuesEditable(root) {
    const o = root.userData.source, base = o.added ? o.added.base : o;
    if (isStream(o) || o.kind === 'flare' || root.userData.deleted) return false;
    if (!families?.families?.[`${o.kind}-values`]?.builds) return false;
    return !valuesViewOnly(base);
  }
  function setEffectValues(root, values) {
    const v = values && Object.keys(values).length ? values : null;
    root.userData.values = v ? structuredClone(v) : null;
    sceneChanged();
  }
  // One change of values: `patch` merged in (a key set to undefined goes back to the map's), one undo step
  function changeEffectValues(root, patch) {
    const before = root.userData.values ? structuredClone(root.userData.values) : null;
    const after = { ...(before ?? {}) };
    for (const [k, v] of Object.entries(patch)) {
      if (k === 'parameters') {
        const params = { ...(after.parameters ?? {}) };
        for (const [name, value] of Object.entries(v)) { if (value === undefined) delete params[name]; else params[name] = value; }
        if (Object.keys(params).length) after.parameters = params; else delete after.parameters;
      } else if (v === undefined) delete after[k];
      else after[k] = v;
    }
    if (JSON.stringify(after) === JSON.stringify(before ?? {})) return;
    const id = root.userData.source.id;
    gizmo.record({ redo: () => { setEffectValues(root, after); select(id, false, true); },
                   undo: () => { setEffectValues(root, before); select(id, false, true); } });
  }
  const fixed = (v, places = 3) => Number(Number(v).toFixed(places));
  const hexOf = rgb => `#${rgb.slice(0, 3).map(v => Math.round(Math.pow(Math.max(0, Math.min(1, v)), 1 / 2.2) * 255).toString(16).padStart(2, '0')).join('')}`;
  const rgbOf = hex => [1, 3, 5].map(k => fixed(Math.pow(parseInt(hex.slice(k, k + 2), 16) / 255, 2.2), 4));
  const byteRgbOf = hex => [1, 3, 5].map(k => fixed(parseInt(hex.slice(k, k + 2), 16) / 255, 4));
  const byteHexOf = rgb => `#${rgb.slice(0, 3).map(v => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, '0')).join('')}`;
  // A number field: committed on change when finite and within [lo, hi], else put back with why
  function numberField(parent, label, value, { lo = -VALUE_LIMITS.parameter, hi = VALUE_LIMITS.parameter, step = 'any', title = '', onCommit }) {
    const wrap = text(parent, 'label', label);
    wrap.title = title;
    const input = document.createElement('input');
    input.type = 'number'; input.step = step; input.value = String(fixed(value, 4));
    input.onchange = () => {
      const v = Number(input.value);
      if (!input.value.trim() || !Number.isFinite(v) || v < lo || v > hi) { flashHint(`${label || 'It'} is ${fixed(lo, 4)} to ${fixed(hi, 4)}`); input.value = String(fixed(value, 4)); return; }
      onCommit(v);
    };
    wrap.append(input);
    return input;
  }
  function effectValueControls(box, root, now) {
    const o = root.userData.source, kind = o.kind, values = root.userData.values ?? {}, base = o.added ? o.added.base : o;
    const head = text(box, 'div', kind === 'effect' ? 'Values' : 'Sound', 'posehead');
    head.title = 'What the Build sets on this one (its own actor: a copy\'s are its own)';
    const on = text(box, 'label', '', 'check');
    const tick = document.createElement('input');
    tick.type = 'checkbox'; tick.checked = now.startsOn !== false;
    tick.onchange = () => changeEffectValues(root, { startsOn: tick.checked === (base.startsOn !== false) ? undefined : tick.checked });
    on.append(tick, kind === 'effect' ? ' Starts with the mission' : ' Plays from the start');
    on.title = kind === 'effect' ? 'Off, its particles wait for the mission\'s script to start them' : 'Off, it waits for the mission\'s script to start it';
    if (kind === 'effect') {
      const line = text(box, 'div', '', 'valueline');
      const m = values.scale ?? 1;
      text(line, 'span', m === 1 ? 'Size as the map has it' : `Size ${fixed(m, 3)} times the map's`);
      line.title = 'Drag the handle beside its marker to make it larger or smaller';
      if (values.scale != null) { const b = text(line, 'button', 'Reset'); b.type = 'button'; b.onclick = () => changeEffectValues(root, { scale: undefined }); }
      const controls = parameterControls(base, effectSystemsOf(o), values.parameters ?? {});
      if (controls.length) text(box, 'div', 'Particle parameters', 'posehead').title = 'Values its particle system reads by name: a parameter the effect saves keeps its kind; one it doesn\'t is set in the kind its system reads';
      for (const c of controls) effectParameterRow(box, root, c);
      return;
    }
    const v = now.values ?? {};
    const reach = text(box, 'div', '', 'valueline');
    text(reach, 'span', `Heard fully within ${Math.round(v.radiusMin ?? 0)}, fading out by ${Math.round(v.radiusMax ?? 0)} units`);
    reach.title = 'Drag the handles on its spheres to change where it is heard';
    if (values.radiusMin != null || values.radiusMax != null) { const b = text(reach, 'button', 'Reset'); b.type = 'button'; b.onclick = () => changeEffectValues(root, { radiusMin: undefined, radiusMax: undefined }); }
    for (const [key, label, [lo, hi]] of [['volume', 'Volume', VALUE_LIMITS.volume], ['pitch', 'Pitch', VALUE_LIMITS.pitch]]) {
      const row = text(box, 'div', '', 'valuepair');
      text(row, 'span', label, 'name');
      const pair = [v[`${key}Min`] ?? 1, v[`${key}Max`] ?? 1];
      const commit = (k, x) => {
        const next = [...pair]; next[k] = x;
        if (next[0] > next[1]) next[1 - k] = x;
        const same = next[0] === (base.values?.[`${key}Min`]) && next[1] === (base.values?.[`${key}Max`]);
        changeEffectValues(root, { [key]: same ? undefined : next });
      };
      numberField(row, 'least', pair[0], { lo, hi, title: `The least ${key} it plays at (${lo} to ${hi}): each time it plays, the game picks one between least and most`, onCommit: x => commit(0, x) });
      numberField(row, 'most', pair[1], { lo, hi, title: `The most ${key} it plays at (${lo} to ${hi})`, onCommit: x => commit(1, x) });
      if (values[key]) { const b = text(row, 'button', '↺'); b.type = 'button'; b.title = 'As the map has it'; b.onclick = () => changeEffectValues(root, { [key]: undefined }); }
    }
  }
  function effectParameterRow(box, root, c) {
    const row = text(box, 'div', '', `effectvalue${c.edited ? ' edited' : ''}`);
    text(row, 'span', c.name, 'name');
    const set = value => changeEffectValues(root, { parameters: { [c.name]: value } });
    if (c.readOnly) { row.classList.add('odd'); row.title = `Kept as the map has it: ${c.readOnly}`; text(row, 'span', '—', 'value'); return; }
    if (c.control === 'scalar') {
      const slider = document.createElement('input');
      slider.type = 'range'; slider.min = String(c.guide[0]); slider.max = String(c.guide[1]); slider.step = 'any'; slider.value = String(c.value);
      const field = numberField(row, '', c.value, { title: `${c.name}: a number`, onCommit: set });
      slider.oninput = () => { field.value = String(fixed(slider.value, 4)); };
      slider.onchange = () => set(fixed(slider.value, 4));
      row.insertBefore(slider, field.parentElement);
    } else if (c.control === 'vector') {
      const parts = c.channels ? [['r', 'red'], ['g', 'green'], ['b', 'blue']] : [['x', 'x'], ['y', 'y'], ['z', 'z']];
      parts.forEach(([label, part], k) => numberField(row, label, c.value[k], { title: `${c.name}: its ${part}`, onCommit: v => { const next = [...c.value]; next[k] = v; set(next); } }));
    } else if (c.control === 'tint') {
      const { colour, strength } = tintOf(c.value);
      const swatch = document.createElement('input');
      swatch.type = 'color'; swatch.value = hexOf(colour); swatch.title = `${c.name}: its colour`;
      swatch.onchange = () => set(tintVector(rgbOf(swatch.value), strength || 1));
      row.append(swatch);
      numberField(row, '×', strength, { lo: 0, title: `${c.name}: its strength (how bright; the map's go past 1)`, onCommit: v => set(tintVector(colour, v)) });
    } else if (c.control === 'colour') {
      const swatch = document.createElement('input');
      swatch.type = 'color'; swatch.value = byteHexOf(c.value); swatch.title = `${c.name}: its colour (saved as a colour)`;
      swatch.onchange = () => set([...byteRgbOf(swatch.value), c.value[3] ?? 1]);
      row.append(swatch);
    }
    if (c.edited) { const b = text(row, 'button', '↺'); b.type = 'button'; b.title = 'As the map has it'; b.onclick = () => set(undefined); }
  }

  // The project's records of effects and sounds (effects and sounds plan, Part C): an original moved (with
  // effect.follow none where a piece carries it), kept where it is (follow none alone) or deleted; a copy with its kind
  // and the original it copies. A stream's and those the view can't change are never saved.
  function effectState(overrides, added) {
    for (const root of effectRoots.values()) {
      const o = root.userData.source;
      if (isStream(o)) continue;
      const values = savedValues(root.userData.values);
      if (o.added) {
        added.set(o.actor, recordOf({ form: 'effect', id: o.added.entity, actor: o.actor, kind: o.added.kind, from: { ...o.added.from },
                                      ...actorPose(o, root.matrix), values }));
        continue;
      }
      const target = { package: o.sourcePackage, level: o.layer, actor: o.actor };
      // its values object: what the project sets (stage FX5), with an effect's follow none where a piece carries it
      const follow = o.carriedBy && o.kind === 'effect' && (root.userData.edit || root.userData.stays) ? { follow: 'none' } : {};
      const own = values || Object.keys(follow).length ? { [o.kind]: { ...follow, ...(values ?? {}) } } : {};
      if (root.userData.deleted) overrides.set(effectKey(o), { target, deleted: true });
      else if (root.userData.edit) overrides.set(effectKey(o), { target, ...actorPose(o, root.matrix), ...own });
      else if (Object.keys(own).length) overrides.set(effectKey(o), { target, ...own });
    }
  }
  // Back to the effects as exported
  function clearEffectEdits() {
    removeEffectRoots([...effectRoots.values()].filter(r => r.userData.source.added));
    const moved = [...effectRoots.values()].filter(r => r.userData.edit);
    gizmo.applyMatrices(moved, moved.map(r => baseMatrix(r)));
    for (const r of effectRoots.values()) { r.userData.deleted = false; r.userData.stays = false; r.userData.values = null; }
    setEffectsDirty(true);
  }
  // An override of a project state put on the map, or false when it names no effect, sound or flare of this export
  function applyEffectRecord(record) {
    const root = effectIndex.get(targetKey(record.target));
    if (!root) return false;
    if (record.deleted) root.userData.deleted = true;
    else if (Array.isArray(record.location)) gizmo.applyMatrices([root], [actorMatrix(record.location, record.rotation ?? root.userData.source.rotation)]);
    else if (record.effect?.follow === 'none') root.userData.stays = true;
    // its values (stage FX5), as saved: a deleted one's are kept for an undo, as the Build ignores them
    root.userData.values = keptValues(record[root.userData.source.kind]);
    return true;
  }
  // A copy of an effect, sound or flare (`source`: an original's or a copy's), at a render matrix; `actor` its output
  // name (a project's record), else a new one with the next serial
  function addedEffect(source, placed, actor = null, entity = null, values = null) {
    const base = source.added ? source.added.base : source;
    const from = source.added ? source.added.from : { package: source.sourcePackage, level: source.layer, actor: source.actor };
    actor ??= `${from.actor}_copy${nextCopySerial()}`;
    const pose = actorPose(source, placed);
    const o = { ...base, id: `effect-added:${uuid()}`, actor, layer: 'added', isEffect: true, matrix: placed.toArray(),
                location: pose.location, rotation: pose.rotation, referencedBy: [], floors: [], carriedBy: null, carriedHow: null,
                landingRole: null, landingActor: false, listed: true, prefab: null, attachedTo: null,
                added: { from, entity: entity ?? uuid(), kind: base.kind, base } };
    const root = makeEffectRoot(o);
    root.userData.values = values ? structuredClone(values) : null;
    return root;
  }
  function addedEffectOf(entity) {
    const e = optionsOf(entity, 'effect');      // (piece_records.js: its names, original, pose and values)
    // the map's own, or one of another map (its template read first: loadForeignTemplates)
    const template = effectIndex.get(targetKey(e.from ?? {}))?.userData.source ?? foreignEffects.get(targetKey(e.from ?? {}));
    if (!template || template.kind !== e.kind || !Array.isArray(e.location) || !Array.isArray(e.rotation)) return null;
    const serial = Number(/_copy(\d+)$/.exec(e.actor)?.[1]);
    if (serial > copySerial) setCopySerial(serial);
    const root = addedEffect(template, actorMatrix(e.location, e.rotation), e.actor, e.entity, e.values);
    Object.assign(root.userData.source, { location: [...e.location], rotation: [...e.rotation] });
    return root;
  }
  // The name of the marker under the pointer (the floor tiles' tip)
  function effectTip() {
    setTipDirty(false);
    const tip = $('floorTip');
    const m = pointer && !gizmo.controls.dragging && !gizmo.busy() ? nearestMarker(effectMarkers, camera, renderer.domElement.getBoundingClientRect(), ...pointer) : null;
    tip.hidden = !m;
    if (!m) return;
    const r = m.userData.record;
    tip.replaceChildren();
    text(tip, 'strong', recordName(r, data));
    text(tip, 'small', `${KIND_LABEL[r.kind]} · ${short(r.actor)}${r.stream ? ` · ${r.stream}` : ''}${r.added ? ` · a copy of ${short(r.added.from.actor)}` : ''}`);
    if (m.userData.derived) text(tip, 'small', `the copy the Build makes with a copy of ${short(r.carriedBy)}`);
    const rect = viewport.getBoundingClientRect();
    tip.style.left = `${pointer[0] - rect.left}px`; tip.style.top = `${pointer[1] - rect.top}px`;
  }
  // The Effects view on or off (Shift+X, the rail's spark): the other views step aside and the selection goes
  function setEffectsShown(on) {
    on = Boolean(on) && effectsAvailable();
    if (on === effectsOn) return;
    if (on) {
      if (volumesOn) setVolumesShown(false);
      if (lightsOn) setLightsShown(false);
      if (zonesOn) setZonesShown(false);
      stopPickBox();
      // (an effect selected in the normal view stays selected)
      if (gizmo.picks().ids.some(id => !effectRoots.has(id))) select(null);
      if (spawnsOn) setSpawnsShown(false);
      if (pickedSpawn) setPickedSpawn(null);
    } else {
      $('floorTip').hidden = true;
      stopWave();
    }
    setEffectsOn(on);
    // in or out, the selection goes: the view picks its markers only, and the normal view moves groups whole
    if (!on && gizmo.picks().ids.some(id => effectRoots.has(id))) select(null);
    refreshEffects(); lightButton();
    if (on) {
      const all = [...effectRecords(data, streamSet), ...[...effectRoots.values()].filter(r => r.userData.source.added && !r.userData.deleted).map(r => r.userData.source)];
      const n = kind => all.filter(r => r.kind === kind).length;
      const editable = ['effect', 'sound', 'flare'].some(k => families?.families?.[k]?.builds);
      flashHint(`Effects view: ${plural(n('effect'), 'effect')}, ${plural(n('sound'), 'sound')}, ${plural(n('flare'), 'lens flare')} · click one to ${editable ? 'select it (Ctrl adds)' : 'see what it is'} · Shift+X leaves it`);
    }
  }
  // The Normal button's Effects switch: the markers drawn and picked with pieces in the normal view
  function setNormalEffects(on) {
    setNormalEffectsValue(Boolean(on) && effectsAvailable());
    if (!normalEffects && !effectsOn && gizmo.picks().ids.some(id => effectRoots.has(id))) select(null);
    setEffectsDirty(true); lightButton();
  }
  $('effectStay').onclick = e => { const root = effectRoots.get(pickedEffect); if (root) setEffectStays(root, !root.userData.stays); e.target.blur(); };
  $('normalEffects').onchange = e => { setNormalEffects(e.target.checked); e.target.blur(); };
  for (const kind of ['effect', 'sound', 'flare']) {
    const box = $(`effectShow-${kind}`);
    box.checked = effectFilters[kind] !== false;
    box.onchange = e => { effectFilters[kind] = e.target.checked; remember(EFFECT_FILTERS, JSON.stringify(effectFilters)); setEffectsDirty(true); e.target.blur(); };
  }

  // After an edit (the edit hub, edit_hub.js): what is drawn is worked out again before it is next read.
  onHub('edit', 'effects', () => {
    setEffectsDirty(true);     // (the Effects view's markers follow the pieces that carry them)
  });
  // As nothing, a building's box or an effect is picked (the edit hub's select runs): the markers painted, the panel,
  // the picked one's shape.
  onHub('select-none', 'effects', () => { paintEffects(); effectPanel(); drawEffectShape(); });

  return { addedEffect, addedEffectOf, addEffectRoots, applyEffectRecord, buildEffects, clearEffectEdits,
           drawEffectShape, drawLikenessPane, effectAt, effectEdited, effectFollows, effectLayer, effectNow,
           effectPicture, effectShapes, effectSource, effectsShown, effectState, effectTip, effectValuesEditable,
           effectViewOnly, frameEffect, ghostLikeness, ghostLikenesses, hoverLikeness, likenesses, likenessLayer,
           likenessPane, numberField, pickEffect, pickEffectAt, playWave, refreshEffects, removeEffectRoots,
           setEffectsShown, setEffectStays, setEffectValues, setLikeness, setNormalEffects, stepGhostLikenesses,
           stepLikenesses, stopWave };
}
