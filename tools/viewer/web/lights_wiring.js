// The Lights view (refactor stage P6; editor lights plan 4.6; lights_view.js draws its markers, shapes and handles,
// light_rules.js holds a light value's rules). Each light with a place is a root of its own in lightRoots, picked,
// moved and turned with the pieces, and changed in the panel's light section; generated area lights follow their
// glowing pieces. Here:
// - the roots: made, added and taken away, their values set and painted, which are drawn (refreshLightVisibility);
//   whether a light can be edited (lightViewOnly, lightsBlocked);
// - the view on or off (setLightsShown, setNormalLights), a light picked on screen, the markers kept one size;
// - the area lights following their glowing pieces (deriveAreaLights), set by the project (setBinding, Assign);
// - Solo, the selected light's reach and emission shapes, the panel's light section (lightPanel, showLight) and its
//   commits;
// - the drag handles on the selected light, and on the picked effect or sound (an effect's size, a sound's radii);
// - the Add panel's lights, a light made from a recipe, an added light; the project's light records (lightState,
//   applyLightRecord, addedLightOf, clearLightEdits), the map's lights built (buildLights), the page's lights after
//   an edit (lightsChanged) and the warning while the family is refused.
//
// createLightsWiring takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// camera and the view's layers, the panel's helpers, the other views' switches and the Effects view's handles' needs.
// Its own state is inside it (the shapes' keys, the handles' hover, the fixed lights, the owners' index); what other
// areas read or set (the views' switches, Solo, the drag, the handles, the reach, the area lights' copies, the lights'
// sync) is editor_state.js's. The view's storage keys (View options' Area lights, reach outlines and sun and sky
// list: AREA_SHOWN, REACH_SHOWN, SKY_SHOWN) are plain exports at the top, before the factory: app.js reads the
// switches from them as the page loads and its View options' handlers write them.
import * as THREE from 'three';
import { QUARTER } from './constants.js';
import { sentence } from './dom_words.js';
import { onHub } from './edit_hub.js';
import { areaBindings, areaShown, assigning, cleared, clearKeepsOutside, copySerial, data, derivedCopies, effectRoots,
         effectsOn, families, handleDefs, hintTimer, lightDrag, lightIndex, lighting, lightRadius, lightRoots,
         lightsDirty, lightsOn, lightsShown, nextCopySerial, pickedEffect, placing, reachKey, reachNow, reachShown,
         roots, selected, setAreaBindings, setAssigning, setCopySerial, setDerivedCopies, setHandleDefs,
         setLastLightSync, setLightDrag, setLightsDirty, setLightsOn, setNormalLightsValue, setReachKey, setReachNow,
         setSoloOn, soloOn, spawnsOn, streamSet, volumesOn, zonesOn } from './editor_state.js';
import { soundReach, VALUE_LIMITS } from './effects_rules.js';
import { actorMatrix } from './gizmo.js';
import { effectiveConeDegrees, LIGHT_LIMITS, storableCone } from './light_rules.js';
import { boxInReach, boxLines, createSolo, emissionShape, HANDLE_COLOURS, lightHandles, makeHandle, makeMarker,
         nearestValue, paintMarker, recordNow, scaleMarker, SOLO_MAX, valuesOf } from './lights_view.js';
import { optionsOf, recordOf } from './piece_records.js';
import { targetKey, uuid } from './project.js';

// The Lights view's storage keys.
export const AREA_SHOWN = 'workshop.areaLights', SKY_SHOWN = 'workshop.sunSky', REACH_SHOWN = 'workshop.lightReach';

export function createLightsWiring({ $, actorPose, applyLighting, banner, baseMatrix, camera, copyable, copyText,
                                    drawEffectShape, editChanged, effectNow, effectsShown, effectValuesEditable, field,
                                    flashHint, gizmo, HANDLE_PICK, highlight, isStream, ladderMarks, lightLayer,
                                    pickables, PL, plural, pointOutside, projector, renderer, restingHint, select,
                                    setEffectsShown, setEffectValues, setSpawnsShown, setVolumesShown, setZonesShown,
                                    short, showPop, stopPickBox, sun, syncLights, text, world }) {
  // Lights (private/plans/done/editor-lights-plan.md, 4.6). Each light with a place (point and spot lights: placed, generated area,
  // toggleable, a streamed level's) is a root of its own in lightRoots: a marker, picked on screen ahead of the piece
  // behind it, moved and turned by the gizmo with pieces (allRoots), and changed in the panel's light section. A root
  // keeps its values in the package's terms (plan 9.1) now (`values`) and as exported or placed (`baseValues`).
  // Generated area lights are never edited: they follow their glowing piece (deriveAreaLights), which the export's
  // matcher found or the project binds (areaBindings). A light that can be edited joins a group as a piece does
  // (groupables); a generated one follows its piece instead.
  let warnedLights = false;     // (soloOn, lightsDirty, lastLightSync, assigning: editor_state.js)
  let fixedLights = [], ownerIndex = null, paintedLights = new Set();     // (derivedCopies: editor_state.js)
  let handleHover = null;   // the selected light's drag handles (below commitColour; handleDefs, lightDrag: editor_state.js)
  // (an area light's glowing piece as the project sets it, areaBindings: editor_state.js)
  const derivedMarks = new THREE.Group(); world.add(derivedMarks);
  const lightShapes = new THREE.Group(); world.add(lightShapes);
  const solo = createSolo(world);
  // (a light value's limits: light_rules.js LIGHT_LIMITS)
  const LIGHT_LABELS = { brightness: 'Brightness', radius: 'Radius', falloffExponent: 'Falloff', innerConeAngle: 'The inner cone',
                         outerConeAngle: 'The outer cone' };
  const REACH_WARN = 300;
  const lightKey = o => targetKey({ package: o.sourcePackage, level: o.layer, actor: o.actor });
  const sameValue = (a, b) => (Array.isArray(a) ? Array.isArray(b) && a.length === b.length && a.every((v, k) => v === b[k]) : a === b);
  function changedValues(values, base) {
    const out = {};
    for (const k of Object.keys(values)) if (!sameValue(values[k], base?.[k])) out[k] = Array.isArray(values[k]) ? [...values[k]] : values[k];
    return out;
  }
  const valuesEdited = root => Object.keys(changedValues(root.userData.values, root.userData.baseValues)).length > 0;
  const lightEdited = root => Boolean(root.userData.edit || root.userData.deleted || root.userData.source.added || valuesEdited(root));
  // Why the map's lights can't be edited at all (an older export or server), or null.
  function lightsBlocked() {
    if (!families?.lightRules) return 'the editor\'s server is older than its page: restart it (xcom_editor.cmd restart) to edit lights';
    if (!(data.exporterVersion >= 18) || !data.lightMetadata) return `this map's export predates the light data (export ${families.exportMinimum ?? 18}): prepare it again to edit lights`;
    return null;
  }
  // Why a light is view only (the compiler's light_rule, families.json), or null when it can be edited.
  function lightViewOnly(o) {
    if (isStream(o)) return 'it is a light of a streamed level (a patch\'s own)';
    const blocked = lightsBlocked();
    if (blocked) return blocked;
    if (o.added) return o.added.template ? null : families.lightRules[o.added.fromId] ?? null;
    return o.id in families.lightRules ? families.lightRules[o.id] : 'the server didn\'t list it among the map\'s lights';
  }
  const lightSource = record => ({ ...record, isLight: true, matrix: actorMatrix(record.location, record.rotation).toArray() });
  function makeLightRoot(source, values, baseValues = values) {
    const root = new THREE.Group();
    root.matrixAutoUpdate = false; root.matrix.fromArray(source.matrix);
    const marker = makeMarker(source.role === 'area' ? 'area' : source.kind);
    root.add(marker);
    root.userData = { source, light: true, values: { ...values }, baseValues: { ...baseValues }, marker, deleted: false, edit: null, parts: [] };
    paintMarker(marker, root.userData.values, { viewOnly: Boolean(lightViewOnly(source)) });
    return root;
  }
  function addLightRoots(list) {
    for (const root of list) {
      const o = root.userData.source;
      lightRoots.set(o.id, root); lightLayer.add(root);
      if (!o.added) lightIndex.set(lightKey(o), root);
    }
    refreshLightVisibility();
  }
  function removeLightRoots(list) {
    for (const root of list) { lightRoots.delete(root.userData.source.id); lightLayer.remove(root); }
  }
  // A light's actor pose where it is drawn: a point light keeps its rotator (it has no direction to edit).
  function lightPose(root, matrix = root.matrix) {
    const o = root.userData.source, pose = actorPose(o, matrix);
    if (o.kind === 'point') pose.rotation = [...o.rotation];
    return pose;
  }
  const directionOf = matrix => { const e = matrix.elements, d = new THREE.Vector3(e[0], e[2], e[1]).normalize(); return [d.x, d.y, d.z]; };
  // The light as edited, as the Map lighting mode and Solo read it (export terms: colour 0-1, game units).
  function lightRecordOf(root, matrix = root.matrix) {
    const pose = lightPose(root, matrix);
    return recordNow(root.userData.source, root.userData.values, pose.location, pose.rotation, directionOf(matrix));
  }
  function paintLight(root) {
    const selected = gizmo.picks().ids.includes(root.userData.source.id);
    paintMarker(root.userData.marker, root.userData.values, { viewOnly: Boolean(lightViewOnly(root.userData.source)), selected });
  }
  function setLightValues(root, values) {
    root.userData.values = { ...values };
    paintLight(root); setLightsDirty(true);
  }
  function refreshLightVisibility() {
    lightLayer.visible = lightsShown;
    derivedMarks.visible = lightsShown && areaShown;
    // Interior shows the lights whose radius reaches the play area (view basis, as playableBounds)
    const play = data?.scope === 'map' && $('scenery').value === 'interior' ? data.playableBounds : null;
    const reachesPlay = root => {
      const e = root.matrix.elements, r = root.userData.values.radius ?? 0;
      return [0, 1, 2].every(k => e[12 + k] >= play.min[k] - r && e[12 + k] <= play.max[k] + r);
    };
    for (const root of lightRoots.values()) {
      const o = root.userData.source;
      root.visible = !root.userData.deleted && !root.userData.derivedGone && (o.role !== 'area' || areaShown)
        && (!isStream(o) || streamSet.has(o.stream)) && (!play || root.userData.source.added || reachesPlay(root))
        && !(cleared && !o.added && !(o.kind === 'directional' || o.kind === 'sky' || o.role === 'dominant' || o.role === 'sky')
             && (isStream(o) || o.role === 'area' || lightViewOnly(o))
             && !(clearKeepsOutside && !isStream(o) && pointOutside(root.matrix.elements[12], root.matrix.elements[14])));
    }
  }
  // The lights toggle (Shift+L, the rail's bulb, View options): off, the map looks as it did and lights can't be picked.
  // The Lights view on or off: while it is on only lights are picked, and each moves on its own.
  function setLightsShown(on) {
    on = Boolean(on) && Boolean(data);
    if (on === lightsOn) { syncLights(); return; }
    if (on && volumesOn) setVolumesShown(false);
    if (on && zonesOn) setZonesShown(false);
    if (on && effectsOn) setEffectsShown(false);
    if (on && spawnsOn) setSpawnsShown(false);
    if (on) stopPickBox();
    setLightsOn(on);
    syncLights();
    if (on) flashHint('Lights view: only lights are selected · Shift+L leaves it');
  }
  // The Normal button's Lights switch: the lights drawn and picked with pieces in the normal view.
  function setNormalLights(on) {
    setNormalLightsValue(Boolean(on) && Boolean(data));
    syncLights();
  }
  // A light under a screen point: the nearest marker centre within 13 pixels, or null. (A spot's cone hangs from the light
  // along its direction: its centre is half a cone from the light.)
  function pickLight(clientX, clientY) {
    if (!lightsShown) return null;
    const rect = renderer.domElement.getBoundingClientRect(), p = new THREE.Vector3();
    let best = null, bestD = 13;
    for (const root of lightRoots.values()) {
      if (!root.visible) continue;
      const front = root.userData.marker.userData.front;
      if (!front.geometry.boundingSphere) front.geometry.computeBoundingSphere();
      front.updateWorldMatrix(true, false);
      p.copy(front.geometry.boundingSphere.center).applyMatrix4(front.matrixWorld).project(camera);
      if (p.z > 1 || p.z < -1) continue;
      const d = Math.hypot(rect.left + (p.x + 1) / 2 * rect.width - clientX, rect.top + (1 - p.y) / 2 * rect.height - clientY);
      if (d < bestD) { bestD = d; best = root; }
    }
    return best;
  }
  // Markers keep one size on screen.
  const markerAt = new THREE.Vector3();
  function scaleMarkers() {
    if (!lightsShown) return;
    for (const root of lightRoots.values()) if (root.visible) scaleMarker(root.userData.marker, camera, markerAt.setFromMatrixPosition(root.matrix));
    for (const holder of derivedMarks.children) scaleMarker(holder.children[0], camera, markerAt.setFromMatrixPosition(holder.matrix));
  }

  // Area lights following their glowing pieces (plan 4.8): an area light's glowing piece is the project's binding, else
  // the export's verified association. A moved original carries its light (its edit times the light's pose), a deleted
  // one takes it away, and each copy of it gets a copy of the light at the copy's place (drawn, never picked).
  function areaOwner(o) {
    if (areaBindings.has(o.actor)) {
      const b = areaBindings.get(o.actor);
      return { owner: b ? { actor: b.target.actor, component: b.component } : null, how: b ? 'project' : 'kept' };
    }
    const a = o.emitterAttachment;
    if (a?.status === 'verified' && a.owner) return { owner: { actor: a.owner.target.actor, component: a.owner.component }, how: 'export' };
    return { owner: null, how: a?.status ?? 'none' };
  }
  function ownerRoot(actor, component) {
    if (!ownerIndex) {
      ownerIndex = new Map();
      for (const r of roots.values()) {
        const o = r.userData.source;
        if (o.added || o.layer !== 'base') continue;
        ownerIndex.set(`${o.actor}|${o.component}`, r);
        if (!ownerIndex.has(o.actor)) ownerIndex.set(o.actor, r);
      }
    }
    return ownerIndex.get(`${actor}|${component}`) ?? ownerIndex.get(actor) ?? null;
  }
  function deriveAreaLights() {
    for (const holder of derivedMarks.children) {
      holder.children[0].userData.solid.dispose();
      holder.children[0].userData.ghost.dispose();
    }
    derivedMarks.clear();
    setDerivedCopies([]);
    function addDerived(root, matrix, owner) {
      derivedCopies.push({ root, matrix, owner });
      const holder = new THREE.Group(), marker = makeMarker('area');
      paintMarker(marker, root.userData.values, { viewOnly: true });
      holder.matrixAutoUpdate = false; holder.matrix.copy(matrix); holder.add(marker);
      derivedMarks.add(holder);
    }
    const copies = new Map();
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (!o.added) continue;
      if (o.foreign) {
        if (!r.userData.deleted && o.foreignAreaLights?.length) {
          const pose = actorPose(o, r.matrix);
          const frame = actorMatrix(pose.location, pose.rotation);
          for (const light of o.foreignAreaLights) addDerived(light.root, frame.clone().multiply(light.relative), r);
        }
        continue;
      }
      const k = `${o.added.from.actor}|${o.component}`;
      if (!copies.has(k)) copies.set(k, []);
      copies.get(k).push(r);
    }
    for (const root of lightRoots.values()) {
      const o = root.userData.source;
      if (o.role !== 'area' || o.added || o.layer !== 'base') continue;
      const base = baseMatrix(root), { owner } = areaOwner(o), r = owner && ownerRoot(owner.actor, owner.component);
      root.userData.derivedGone = Boolean(r?.userData.deleted);
      root.matrix.copy(r?.userData.edit && !r.userData.deleted ? r.userData.edit.clone().multiply(base) : base);
      root.matrixWorldNeedsUpdate = true;
      if (!r) continue;
      const back = baseMatrix(r).invert();
      for (const copy of copies.get(`${r.userData.source.actor}|${r.userData.source.component}`) ?? []) {
        addDerived(root, copy.matrix.clone().multiply(back).multiply(base), copy);
      }
    }
    refreshLightVisibility();
    setLightsDirty(true);
  }
  // The lights as edited, for the Map lighting mode: placed lights moved, changed, added and deleted, the area lights
  // as their pieces take them, and the map's sun and sky as exported. Streamed levels' lights are left out, as before.
  function lightRecords() {
    const out = [];
    for (const root of lightRoots.values()) {
      if (root.userData.deleted || root.userData.derivedGone || isStream(root.userData.source)) continue;
      out.push(lightRecordOf(root));
    }
    for (const d of derivedCopies) out.push(lightRecordOf(d.root, d.matrix));
    return out.concat(fixedLights);
  }
  // An area light's glowing piece set by the project: owner { target, component }, null to keep it fixed, undefined to
  // take the export's again. One undo step.
  function setBinding(root, owner) {
    const actor = root.userData.source.actor, had = areaBindings.has(actor), before = areaBindings.get(actor);
    if (owner === undefined ? !had : had && JSON.stringify(before) === JSON.stringify(owner)) return;
    gizmo.record({
      redo: () => { if (owner === undefined) areaBindings.delete(actor); else areaBindings.set(actor, owner); deriveAreaLights(); },
      undo: () => { if (!had) areaBindings.delete(actor); else areaBindings.set(actor, before); deriveAreaLights(); },
    });
    flashHint(owner === undefined ? 'The export\'s glowing piece again' : owner ? `Follows ${short(owner.target.actor)} now` : 'Kept where it is: no piece takes it along');
  }
  // Assign glowing piece: the next piece clicked becomes the light's (an original's own component; a copy's original).
  function assignOwner(hit) {
    const root = lightRoots.get(assigning), piece = roots.get(hit.object.userData.objectId);
    setAssigning(null); $('lightAssign').classList.remove('on');
    if (!root || !piece) return;
    const o = piece.userData.source;
    if (isStream(o) || o.layer === 'inherited') { flashHint('A streamed or patch piece can\'t be a glowing piece: pick one of the map\'s own'); return; }
    const target = o.added ? o.added.from : { package: o.sourcePackage, level: o.layer, actor: o.actor };
    setBinding(root, { target, component: o.component });
  }

  // Solo (the panel's button, O with a light selected): the map dims to a faint neutral and only the selected lights
  // shine, up to four, with live shadows: the direct light the bake will put down.
  function soloRoots() {
    return gizmo.picks().ids.map(id => lightRoots.get(id))
      .filter(r => r && !r.userData.deleted && ['point', 'spot'].includes(r.userData.source.kind)).slice(0, SOLO_MAX);
  }
  function setSolo(on) {
    setSoloOn(Boolean(on) && soloRoots().length > 0);
    if (on && !soloOn) flashHint('Select a light to solo it');
    updateSolo();
  }
  function updateSolo() {
    const targets = soloOn ? soloRoots() : [];
    if (soloOn && !targets.length) setSoloOn(false);
    $('lightSolo').classList.toggle('on', soloOn);
    $('lightSolo').textContent = soloOn ? 'Solo on' : 'Solo';
    if (!soloOn) { if (solo.count) { solo.clear(); applyLighting(); } return; }
    solo.show(targets.map(r => lightRecordOf(r)));
    lighting.dim(sun.target.position, lightRadius);
  }

  // Where the selected light emits, and the pieces it lights: for an original as exported, the pieces its bake lists it
  // in (export 18's bakedInto); for one moved, changed or added, the pieces its new reach touches, which a full build
  // relights. Box outlines, not a material change (instances share materials).
  const boxCache = new WeakMap(), floorCache = new Map(), down = new THREE.Vector3(0, -1, 0);
  function rootBox(r) {
    const key = r.matrix.elements.join(',');
    const cached = boxCache.get(r);
    if (cached?.key === key) return cached.box;
    r.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(r);
    boxCache.set(r, { key, box });
    return box;
  }
  function floorBelow(location) {
    const key = location.map(v => Math.round(v)).join(',');
    if (!floorCache.has(key)) {
      const hit = new THREE.Raycaster(new THREE.Vector3(location[0], location[2], location[1]), down).intersectObjects(pickables)
        .find(h => roots.get(h.object.userData.objectId)?.visible);
      floorCache.set(key, hit ? hit.point.y : null);
    }
    return floorCache.get(key);
  }
  function lightReach(root) {
    const o = root.userData.source, record = lightRecordOf(root);
    if (!lightEdited(root) && o.bakedInto) {
      const boxes = o.bakedInto.map(id => roots.get(id)).filter(r => r?.visible && !r.userData.deleted).map(rootBox);
      return { changed: false, count: o.bakedInto.length, boxes };
    }
    if (!record.radius) return { changed: true, count: 0, boxes: [] };
    const boxes = [];
    for (const r of roots.values()) {
      const s = r.userData.source;
      if (r.userData.deleted || !r.visible || isStream(s) || s.layer === 'inherited') continue;
      const box = rootBox(r);
      if (boxInReach(box, record.location, record.radius)) boxes.push(box);
    }
    return { changed: true, count: boxes.length, boxes };
  }
  let shapeKey = '', reachLines = null;     // (reachKey, reachNow: editor_state.js)
  function refreshLightShapes() {
    const root = lightRoots.get(gizmo.active);
    const key = root && root.visible ? `${root.userData.source.id}|${root.matrix.elements.join(',')}|${JSON.stringify(root.userData.values)}` : '';
    const dragging = gizmo.controls.dragging || Boolean(lightDrag);
    if (key !== shapeKey || (!dragging && key && key !== reachKey)) {
      for (const child of [...lightShapes.children]) if (child !== reachLines) lightShapes.remove(child);
      shapeKey = key;
      if (root && root.visible) {
        const record = lightRecordOf(root);
        lightShapes.add(emissionShape(record, root.matrix, floorBelow(record.location)));
      }
    }
    if (dragging && key === shapeKey) return;
    if (key !== reachKey) {
      if (reachLines) { lightShapes.remove(reachLines); reachLines.geometry.dispose(); reachLines = null; }
      setReachKey(key); setReachNow(null);
      if (root && root.visible && !dragging) {
        setReachNow(lightReach(root));
        // the outlines only with View options' "Outline the pieces a light reaches"; the panel gives the count either way
        if (reachShown && reachNow.boxes.length) { reachLines = boxLines(reachNow.boxes, reachNow.changed ? 0xf0a050 : 0x6fd3c8); lightShapes.add(reachLines); }
      }
    }
  }

  // The light section of the panel: the selected light's values (a spot light's effective cones, plan 4.2), its reach,
  // and for a generated area light its glowing piece.
  const ROLE_WORDS = { static: 'Placed light', area: 'Made by the bake for a glowing surface', toggleable: 'Lit live',
                       dominant: 'The sun or moon', sky: 'The sky' };
  const hex2 = v => v.toString(16).padStart(2, '0');
  function lightPanel() {
    const root = lightRoots.get(selected);
    $('lightBox').hidden = !root;
    if (!root) return;
    const o = root.userData.source, v = root.userData.values, viewOnly = lightViewOnly(o), focused = document.activeElement;
    const put = (id, value) => { if (focused !== $(id)) $(id).value = value; };
    put('lightColor', `#${v.color.map(hex2).join('')}`);
    ['lightR', 'lightG', 'lightB'].forEach((id, k) => put(id, String(v.color[k])));
    const spot = o.kind === 'spot';
    put('lightBrightness', String(v.brightness));
    put('lightRadius', String(v.radius ?? ''));
    put('lightFalloff', String(v.falloffExponent ?? ''));
    $('lightInnerRow').hidden = $('lightOuterRow').hidden = !spot;
    if (spot) {
      const [inner, outer] = effectiveConeDegrees(v.innerConeAngle, v.outerConeAngle);
      put('lightInner', String(Number(inner.toFixed(2))));
      put('lightOuter', String(Number(outer.toFixed(2))));
    }
    $('lightOn').checked = v.enabled;
    $('lightKind').textContent = `${o.kind} light`;
    for (const id of ['lightColor', 'lightR', 'lightG', 'lightB', 'lightBrightness', 'lightRadius', 'lightFalloff', 'lightInner', 'lightOuter', 'lightOn'])
      $(id).disabled = Boolean(viewOnly);
    const note = [];
    if (viewOnly) note.push(`View only: ${viewOnly}.`);
    if (spot && !viewOnly && (Math.abs(effectiveConeDegrees(v.innerConeAngle, v.outerConeAngle)[1] - v.outerConeAngle) > 1e-6
                 || Math.abs(effectiveConeDegrees(v.innerConeAngle, v.outerConeAngle)[0] - v.innerConeAngle) > 1e-6))
      note.push(`Its stored cone (inner ${v.innerConeAngle}°, outer ${v.outerConeAngle}°) is wider than the game draws it: the cones shown are the ones it lights with, and the stored values stay unless you change them.`);
    $('lightNote').textContent = note.join(' ');
    const reach = reachNow && reachKey === shapeKey ? reachNow : null;
    const reachText = $('lightReach');
    reachText.classList.toggle('warn', Boolean(reach?.changed && reach.count > REACH_WARN));
    const outlined = reachShown ? ' (outlined)' : '';
    reachText.textContent = !reach ? '' : !reach.changed
      ? `Baked into ${plural(reach.count, 'piece')}${outlined}: where the game lights it now.`
      : `Reaches about ${plural(reach.count, 'piece')}${outlined}: a full build relights them${reach.count > REACH_WARN ? ', which takes a good while' : ''}.`;
    const area = o.role === 'area' && !isStream(o);
    for (const id of ['lightAssign', 'lightKeep', 'lightAuto']) $(id).hidden = !area;
    $('lightSolo').hidden = !['point', 'spot'].includes(o.kind);
    $('lightArea').hidden = !area;
    if (area) {
      const { owner, how } = areaOwner(o), a = o.emitterAttachment;
      const why = { export: 'found by the export', project: 'set in this project', kept: 'kept fixed in this project',
                    ambiguous: 'the export found several pieces it may glow from', unmatched: 'the export found no piece it glows from',
                    unsupported: 'the export couldn\'t tell', none: 'the export has no glowing pieces (prepare the map again)' }[how] ?? how;
      $('lightArea').textContent = owner
        ? `Follows ${short(owner.actor)} (${why}): it moves, copies and goes with that piece.`
        : how === 'kept' ? 'Kept where it is: no piece takes it along (set in this project).'
          : `It stays where it is: ${why}${a?.candidates?.length ? ` (${a.candidates.map(c => short(c.actor ?? c.objectId)).join(', ')})` : ''}. Assign its glowing piece, or keep it fixed, before moving a piece it may glow from.`;
      $('lightKeep').disabled = how === 'kept';
      $('lightAuto').disabled = !areaBindings.has(o.actor);
      $('lightAssign').classList.toggle('on', assigning === o.id);
    }
  }
  // A typed value commits on Enter or when the field is left; one undo step. A spot light's cone fields show its
  // effective cones: leaving one unchanged commits nothing, so a stored 580-degree cone stays 580.
  function changeLight(changes) {
    const root = lightRoots.get(selected);
    if (!root || lightViewOnly(root.userData.source)) return;
    const before = { ...root.userData.values }, after = { ...before, ...changes };
    if (!Object.keys(changedValues(after, before)).length) return;
    gizmo.record({ redo: () => setLightValues(root, after), undo: () => setLightValues(root, before) });
  }
  function commitLightField(key, input) {
    const root = lightRoots.get(selected);
    if (!root) return;
    const value = Number(input.value), [lo, hi] = LIGHT_LIMITS[key], v = root.userData.values;
    const back = message => { if (message) flashHint(message); lightPanel(); };
    // a point light has no cone (its fields are hidden; the compiler refuses cone values on one too)
    if ((key === 'innerConeAngle' || key === 'outerConeAngle') && root.userData.source.kind !== 'spot') { back(); return; }
    if (!input.value.trim() || !Number.isFinite(value)) { back(); return; }
    if (value < lo || value > hi) { back(`${LIGHT_LABELS[key]} must be ${lo} to ${hi}`); return; }
    if (key === 'innerConeAngle' && value > v.outerConeAngle) { back('The inner cone can\'t be wider than the outer cone'); return; }
    if (key === 'outerConeAngle' && value < v.innerConeAngle) { back('The outer cone can\'t be narrower than the inner cone'); return; }
    changeLight({ [key]: value });
  }
  function commitColour(bytes) {
    if (bytes.every(b => Number.isInteger(b) && b >= 0 && b <= 255)) changeLight({ color: bytes });
    else { flashHint('Colour values are whole numbers 0 to 255'); lightPanel(); }
  }

  // Drag handles on the selected light (lights_view.js lightHandles): its radius (a point light's on the left edge of its
  // sphere, a spot light's at the end of its axis), and a spot light's outer cone (the rim's left) and inner cone (its
  // right). A press on one drags it, ahead of the gizmo and the camera, the light's look following live; the release makes
  // it one undo step, and Escape puts it back. Radii go in whole units, cones in half degrees.
  const handleLayer = new THREE.Group(); world.add(handleLayer);
  const handleMeshes = new Map();
  const handleGuide = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
                                     new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5, depthTest: false }));
  handleGuide.renderOrder = 8; handleGuide.raycast = () => {}; handleLayer.add(handleGuide);
  const HANDLE_WORDS = { radius: 'Radius', outer: 'Outer cone', inner: 'Inner cone', size: 'Size',
                         radiusMin: 'Heard fully within', radiusMax: 'Fades out by' };
  const HANDLE_TITLES = { radius: 'Drag to change the radius', outer: 'Drag to widen or narrow the outer cone',
                          inner: 'Drag to widen or narrow the inner cone', size: 'Drag to make the effect larger or smaller',
                          radiusMin: 'Drag to change where the sound is heard at full volume',
                          radiusMax: 'Drag to change where the sound fades out' };
  // The selected light when its handles show: shown, editable, with a radius, and nothing being placed.
  function handleRoot() {
    const root = lightRoots.get(selected);
    if (!root || !lightsShown || !root.visible || root.userData.deleted || placing || root.userData.values.radius == null
        || lightViewOnly(root.userData.source)) return effectHandleRoot();
    return root;
  }
  // The picked effect or sound when its handles show (stage FX5): alone in the selection, drawn, its values editable;
  // a sound only where its record gives it spheres.
  function effectHandleRoot() {
    if (!effectsShown() || placing || gizmo.picks().ids.length !== 1) return null;
    const root = pickedEffect ? effectRoots.get(pickedEffect) : null;
    if (!root?.visible || !effectValuesEditable(root)) return null;
    return root.userData.source.kind === 'effect' || soundReach(effectNow(root)) ? root : null;
  }
  // Its handles: an effect's size on the camera's left at a distance that grows with it (its fixed box, as the map
  // sizes it, else 64 units, at 1), a sound's outer radius on the left and its inner one on the right (game units).
  function effectHandles(root, side) {
    const origin = new THREE.Vector3().setFromMatrixPosition(root.matrix), out = side.clone().normalize(), now = effectNow(root);
    if (now.kind === 'sound') {
      const reach = soundReach(now), back = out.clone().negate(), [, top] = VALUE_LIMITS.radius;
      return [{ key: 'radiusMax', value: reach.outer, lo: Math.max(1, reach.inner), hi: top, log: true, origin, at: s => origin.clone().addScaledVector(out, s) },
              { key: 'radiusMin', value: Math.max(1, reach.inner), lo: 1, hi: Math.max(1, reach.outer), log: true, origin, at: s => origin.clone().addScaledVector(back, s) }];
    }
    const box = data.effectSystems?.[now.system]?.fixedBox, mapScale = Math.max(...(root.userData.source.added?.base ?? root.userData.source).scale ?? [1]);
    const unit = box?.used && box.valid ? Math.max(16, Math.max(...box.max.map((v, k) => v - box.min[k])) / 2 * mapScale) : 64;
    const m = root.userData.values?.scale ?? 1, [lo, hi] = VALUE_LIMITS.scale;
    return [{ key: 'size', value: m, lo, hi, log: true, origin, at: x => origin.clone().addScaledVector(out, unit * x) }];
  }
  // An effect's or sound's values after a drag of handle `h` to `raw`: a size to three places (1 is the map's own, no
  // value), radii in whole units, the inner never beyond the outer.
  function effectHandleValues(before, h, raw) {
    const next = structuredClone(before ?? {});
    if (h.key === 'size') {
      const value = Math.min(h.hi, Math.max(h.lo, Number(raw.toFixed(3))));
      if (Math.abs(value - 1) < 1e-3) delete next.scale; else next.scale = value;
      return { next, value };
    }
    const value = Math.min(h.hi, Math.max(h.key === 'radiusMin' ? 0 : h.lo, Math.round(raw)));
    next[h.key] = value;
    return { next, value };
  }
  // the camera's left: the panel covers the view's right
  const cameraSide = () => new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0).normalize().negate();
  // Each frame: the handles where the selected light's shapes are (they lean to the camera's right).
  function updateLightHandles() {
    const root = lightDrag?.root ?? handleRoot();
    setHandleDefs(!root ? [] : root.userData.effect ? effectHandles(root, lightDrag?.side ?? cameraSide())
      : lightHandles(root.userData.source.kind, root.userData.values, root.matrix, lightDrag?.side ?? cameraSide()));
    handleLayer.visible = handleDefs.length > 0;
    if (!handleDefs.length && handleHover) hoverHandle(null);
    for (const mesh of handleMeshes.values()) mesh.visible = false;
    const lit = lightDrag?.handle?.h.key ?? handleHover;
    for (const h of handleDefs) {
      if (!handleMeshes.has(h.key)) { const mesh = makeHandle(h.key); handleMeshes.set(h.key, mesh); handleLayer.add(mesh); }
      const mesh = handleMeshes.get(h.key);
      mesh.visible = true; mesh.position.copy(h.at(h.value));
      mesh.userData.material.color.setHex(h.key === lit ? HANDLE_COLOURS.hover : HANDLE_COLOURS[h.key]);
      scaleMarker(mesh, camera, mesh.position);
    }
    // a thin line from the light to its radius handle (an effect's to its size handle, a sound's to its outer radius's)
    const radius = handleDefs.find(h => h.key === 'radius' || h.key === 'size' || h.key === 'radiusMax');
    if (radius) {
      const at = handleGuide.geometry.attributes.position;
      at.setXYZ(0, ...radius.origin.toArray()); at.setXYZ(1, ...radius.at(radius.value).toArray()); at.needsUpdate = true;
      handleGuide.geometry.computeBoundingSphere();
    }
  }
  // The handles within reach of a screen point, nearest first.
  function handlesNear(x, y) {
    const project = projector();
    return handleDefs.map(h => { const s = project(h.at(h.value)); return s && { h, s, d: Math.hypot(s[0] - x, s[1] - y) }; })
      .filter(c => c && c.d <= HANDLE_PICK).sort((a, b) => a.d - b.d);
  }
  function hoverHandle(key) {
    if (key === handleHover) return;
    handleHover = key;
    renderer.domElement.style.cursor = key ? 'grab' : '';
    renderer.domElement.title = key ? HANDLE_TITLES[key] : '';
  }
  // A handle's value in the light's values: a cone kept the right side of the other (a stored inner wider than 89 degrees
  // comes down to the one the game uses), rounded to whole units or half degrees.
  function handleValues(before, h, raw) {
    const step = h.key === 'radius' ? 1 : 0.5, value = Math.min(h.hi, Math.max(h.lo, Math.round(raw / step) * step));
    const next = { ...before };
    if (h.key === 'radius') next.radius = value;
    else if (h.key === 'outer') { next.outerConeAngle = value; if (before.innerConeAngle > value) next.innerConeAngle = h.lo; }
    else { next.innerConeAngle = value; if (before.outerConeAngle < value) next.outerConeAngle = value; }
    return { next, value };
  }
  function lightDragHint(key, value) {
    const hint = $('dragHint');
    clearTimeout(hintTimer);
    hint.hidden = false;
    hint.replaceChildren(`${HANDLE_WORDS[key]} ${key === 'size' ? `${value} times the map's size` : key === 'radius' || key.startsWith('radius') ? `${value} units` : `${value}°`} · `);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
  }
  function startLightDrag(e) {
    if (e.button !== 0 || lightDrag || gizmo.controls.dragging) return false;
    const near = handlesNear(e.clientX, e.clientY), root = handleRoot();
    if (!near.length || !root) return false;
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    // two handles under the press (a spot's inner cone at 0 sits on its radius handle): the first move picks the one
    // whose way it goes
    const handle = near.length === 1 || near[1].d - near[0].d > 3 ? near[0] : null;
    setLightDrag({ root, before: root.userData.effect ? structuredClone(root.userData.values ?? {}) : { ...root.userData.values },
                  side: cameraSide(), start: [e.clientX, e.clientY], pointerId: e.pointerId,
                  near, handle, offset: handle ? [handle.s[0] - e.clientX, handle.s[1] - e.clientY] : null });
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  function moveLightDrag(e) {
    const d = lightDrag;
    if (!d.handle) {
      const mx = e.clientX - d.start[0], my = e.clientY - d.start[1], moved = Math.hypot(mx, my);
      if (moved < 3) return;
      const project = projector(), along = c => {
        const h = c.h, eps = (h.hi - h.lo) * 1e-3, up = h.value + eps <= h.hi;
        const a = project(h.at(h.value)), b = project(h.at(up ? h.value + eps : h.value - eps));
        if (!a || !b) return 0;
        const tx = b[0] - a[0], ty = b[1] - a[1], len = Math.hypot(tx, ty) || 1;
        return Math.abs((tx * mx + ty * my) / (len * moved));
      };
      d.handle = d.near.reduce((best, c) => (along(c) > along(best) ? c : best));
      d.offset = [d.handle.s[0] - d.start[0], d.handle.s[1] - d.start[1]];
    }
    const h = d.handle.h, raw = nearestValue(h, projector(), [e.clientX + d.offset[0], e.clientY + d.offset[1]]);
    if (d.root.userData.effect) {
      // an effect's size or a sound's radius: drawn live, one undo step at the release (endLightDrag)
      const { next, value } = effectHandleValues(d.before, h, raw);
      lightDragHint(h.key, value);
      d.root.userData.values = Object.keys(next).length ? next : null;
      drawEffectShape();
      return;
    }
    const { next, value } = handleValues(d.before, h, raw);
    lightDragHint(h.key, value);
    if (!Object.keys(changedValues(next, d.root.userData.values)).length) return;
    setLightValues(d.root, next);
    refreshLightShapes(); lightPanel();
    if (soloOn) updateSolo();
  }
  // The drag's end: kept as one undo step, or (Escape, a cancelled pointer) put back. True when there was one.
  function endLightDrag(keep) {
    const d = lightDrag;
    if (!d) return false;
    setLightDrag(null);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
    renderer.domElement.style.cursor = handleHover ? 'grab' : '';
    if (d.root.userData.effect) {
      const after = d.root.userData.values ? structuredClone(d.root.userData.values) : null, before = Object.keys(d.before).length ? d.before : null;
      setEffectValues(d.root, before);
      if (keep && JSON.stringify(after) !== JSON.stringify(before)) {
        const id = d.root.userData.source.id;
        gizmo.record({ redo: () => { setEffectValues(d.root, after); select(id, false, true); },
                       undo: () => { setEffectValues(d.root, before); select(id, false, true); } });
      }
      restingHint();
      return true;
    }
    const after = { ...d.root.userData.values };
    setLightValues(d.root, d.before);
    if (keep && Object.keys(changedValues(after, d.before)).length)
      gizmo.record({ redo: () => setLightValues(d.root, after), undo: () => setLightValues(d.root, d.before) });
    else lightsChanged();
    restingHint();
    return true;
  }

  // The selected light in the panel.
  function showLight(root) {
    const o = root.userData.source, viewOnly = lightViewOnly(o), v = root.userData.values;
    highlight.visible = false; ladderMarks.visible = false;
    const details = $('details');
    details.replaceChildren();
    text(details, 'h2', short(o.actor));
    text(details, 'div', `${o.actorClass} · ${o.kind} light${o.sourcePackage ? ` · ${o.sourcePackage}` : ''}`, 'sub');
    const chips = text(details, 'div', '', 'chips');
    const role = o.role === 'static' && o.bakedInto ? `Placed light, baked into ${plural(o.bakedInto.length, 'piece')}`
      : o.role === 'area' ? 'Made by the bake for a glowing surface' : o.role === 'toggleable'
        ? `Lit live${o.referencedBy?.length ? `; switched off when ${o.referencedBy.map(r => r.split(' ')[0]).join(', ')} breaks` : ''}`
        : ROLE_WORDS[o.role] ?? o.role;
    if (!o.added) text(chips, 'span', role, 'chip').title = o.role === 'area'
      ? 'Lightmass made it for a glowing surface when the map was baked; it lights soldiers and other things lit live. It follows the piece it glows from'
      : role;
    if (o.added) text(chips, 'span', o.added.template ? `Recipe ${o.kind} light` : 'Added copy', 'chip').title = o.added.template
      ? `A ${o.kind} light the editor makes from its built-in recipe (version ${o.added.template.version}), for a map with no ${o.kind} light to copy, or placed with a prefab`
      : `A copy of ${short(o.added.from.actor)}`;
    if (viewOnly) text(chips, 'span', 'View only', 'chip warn').title = sentence(viewOnly);
    else if (families?.families?.light && !families.families.light.builds)
      text(chips, 'span', 'Builds after its game test', 'chip warn').title = families.families.light.note;
    if (isStream(o)) text(chips, 'span', 'Streamed level', 'chip warn').title = `From ${o.stream}: shown for reference`;
    $('editCopy').disabled = !copyable().length;
    const dl = $('sourceFields');
    dl.replaceChildren();
    field(dl, 'Actor', short(o.actor));
    if (o.component) field(dl, 'Component', short(o.component));
    if (o.added && !o.added.template) field(dl, 'Copied from', short(o.added.from.actor));
    field(dl, 'Class', o.actorClass);
    field(dl, 'Role', o.role);
    if (o.lightGuid) field(dl, 'Light GUID', o.lightGuid);
    if (o.lightmapGuid) field(dl, 'Lightmap GUID', o.lightmapGuid);
    if (o.bakedInto) field(dl, 'Baked into', plural(o.bakedInto.length, 'piece'));
    if (o.shadowMapped?.length) field(dl, 'Shadow maps', plural(o.shadowMapped.length, 'piece'));
    if (o.channels) field(dl, 'Channels', 'its own lighting channels');
    if (o.kind === 'spot') {
      const [i, out] = effectiveConeDegrees(v.innerConeAngle, v.outerConeAngle);
      field(dl, 'Cones', `stored ${v.innerConeAngle}° / ${v.outerConeAngle}°, drawn ${Number(i.toFixed(2))}° / ${Number(out.toFixed(2))}°`);
    }
    if (o.referencedBy?.length) field(dl, 'Named by', o.referencedBy.join('\n'));
    if (o.saved?.length) field(dl, 'Saved values', o.saved.join(', '));
    if (o.emitterAttachment) field(dl, 'Glowing piece', `${o.emitterAttachment.status}${o.emitterAttachment.reason ? `: ${o.emitterAttachment.reason}` : ''}`);
    field(dl, 'Map location', o.location.map(x => x.toFixed(2)).join(', '));
    $('copyPaths').onclick = () => copyText($('copyPaths'), [`Actor: ${o.actor}`, o.component ? `Component: ${o.component}` : null].filter(Boolean).join('\n'));
    editChanged();
  }

  // The Add panel's lights: Point light and Spot light, from the map's first light of that kind that can be edited, its
  // values to start; a spot light from the built-in recipe where the map has none (plan 3.3, 4.9). Placed as pieces are,
  // at the template's height above the floor.
  function lightClip(kind) {
    if (lightsBlocked()) { flashHint(sentence(lightsBlocked())); return null; }
    const template = [...lightRoots.values()].map(r => r.userData.source)
      .find(o => !o.added && o.kind === kind && o.role === 'static' && !lightViewOnly(o));
    let source, values, height;
    if (template) {
      source = template; values = valuesOf(template);
      const floor = floorBelow(template.location);
      height = floor == null ? 200 : Math.max(16, template.location[2] - floor);
    } else if (families?.lightRecipes?.[kind]) {
      // a map without one: the editor's own, made from its built-in recipe (a spot light points down)
      ({ source, values } = recipeLight({ kind, version: families.lightRecipes[kind].latest }, null, [0, 0, 0], kind === 'spot' ? [-QUARTER, 0, 0] : [0, 0, 0]));
      height = 256;
    } else { flashHint(`This map has no ${kind} light to copy`); return null; }
    return { entries: [{ source, matrix: new THREE.Matrix4().fromArray(source.matrix), values }], pivot: [...source.location],
             pivotIndex: 0, name: `${kind === 'spot' ? 'Spot' : 'Point'} light (${template ? short(template.actor) : 'recipe'})`,
             light: true, lightHeight: height };
  }
  // The piece list's Lights kind: Point Light and Spot Light, each where lightClip has a light to start from.
  function lightEntries() {
    if (data.scope !== 'map' || data.preview || lightsBlocked()) return [];
    const family = families?.families?.light, out = [];
    for (const kind of ['point', 'spot']) {
      const template = [...lightRoots.values()].map(r => r.userData.source)
        .find(o => !o.added && o.kind === kind && o.role === 'static' && !lightViewOnly(o));
      const recipe = !template ? families?.lightRecipes?.[kind] ?? null : null;
      if (!template && !recipe) continue;
      const values = template ? valuesOf(template) : recipe.values, name = kind === 'point' ? 'Point Light' : 'Spot Light';
      const cone = kind === 'spot' ? ` · cone ${Number(effectiveConeDegrees(values.innerConeAngle, values.outerConeAngle)[1].toFixed(1))}°` : '';
      out.push({
        key: `light:${kind}`, id: `light-${kind}`, light: kind, name, kind: 'Lights',
        pkg: template ? `starts as ${short(template.actor)}` : `the editor's own ${kind} light (recipe ${recipe.latest})`,
        detail: `radius ${Math.round(values.radius)} · brightness ${Number(values.brightness.toFixed(2))}${cone}`,
        colour: values.color.map(c => c / 255),
        count: [...lightRoots.values()].filter(r => !r.userData.source.added && !isStream(r.userData.source) && r.userData.source.kind === kind
                                                && !['area', 'dominant', 'sky'].includes(r.userData.source.role)).length,
        builds: Boolean(family?.builds), note: family?.note ?? '',
        title: `A new ${kind} light, placed as a piece is, at ${template ? `${short(template.actor)}'s` : 'its'} height above the floor. `
          + `It starts with ${template ? `that light's values` : `the recipe's values (white${kind === 'spot' ? ', pointing down' : ''})`}; select it to change any of them`,
        sources: [], pivotIndex: 0, materials: [], milestone: 1, role: null, size: [0, 0, 0], extent: 0, mesh: '',
        text: `${name} lights lamp ${kind === 'point' ? 'bulb point' : 'spot spotlight'}`.toLowerCase(),
      });
    }
    return out;
  }
  // A light made from a built-in recipe (families.json lightRecipes: spot, and point once the Build makes them), as a
  // source to copy: { source, values }, or null for a kind or version this page doesn't know.
  // A made light's values with its cone (a spot light's) in the ranges the Build takes, lighting as before (storableCone).
  function withStorableCone(values) {
    if (values.innerConeAngle == null || values.outerConeAngle == null) return values;
    const [innerConeAngle, outerConeAngle] = storableCone(values.innerConeAngle, values.outerConeAngle);
    return { ...values, innerConeAngle, outerConeAngle };
  }
  function recipeLight(template, light, location, rotation, actor = null) {
    const recipe = families?.lightRecipes?.[template?.kind];
    if (!recipe?.versions?.includes(template.version)) return null;
    const kind = template.kind, cls = kind === 'point' ? 'PointLight' : 'SpotLight';
    // (a prefab saved before its cones were capped may hold a map's wide cone: it is made as the cone it lights as)
    const values = withStorableCone({ ...recipe.values, ...Object.fromEntries(Object.keys(recipe.values).filter(k => light?.[k] !== undefined).map(k => [k, light[k]])) });
    const direction = directionOf(actorMatrix(location, rotation));
    const source = lightSource({ id: `recipe:${kind}`, actor: actor ?? `${PL}${cls}`, component: null, actorClass: cls, componentClass: `${cls}Component`,
                                 sourcePackage: data.name, layer: 'base', kind, role: 'static', location: [...location], rotation: [...rotation],
                                 direction, castShadows: true, recipe: { kind, version: template.version },
                                 ...recordNow({}, values, location, rotation, direction) });
    return { source, values };
  }
  // An added light: a copy of a light (its template the original's: a copy of a copy keeps it), or of a recipe light.
  // `actor`: its output name (a project's record), else a new one with the next serial.
  function addedLight(source, placed, values, actor = null) {
    const recipe = source.added?.template ?? source.recipe ?? null;
    const from = recipe ? null : source.added ? source.added.from : { package: source.sourcePackage, level: source.layer, actor: source.actor };
    actor ??= `${recipe ? `${PL}${recipe.kind === 'point' ? 'PointLight' : 'SpotLight'}` : from.actor}_copy${nextCopySerial()}`;
    // its pose read against its source's own place (a light's matrix is its actor's); a point light keeps its rotator
    const pose = actorPose(source, placed);
    if (source.kind === 'point') pose.rotation = [...source.rotation];
    const o = { ...source, id: `light-added:${uuid()}`, actor, layer: 'added', isLight: true, matrix: placed.toArray(),
                location: pose.location, rotation: pose.rotation, direction: directionOf(placed),
                added: { from, template: recipe, entity: uuid(), component: recipe ? null : source.added?.component ?? source.component,
                         fromId: recipe ? null : source.added?.fromId ?? source.id,
                         templateValues: recipe ? null : source.added?.templateValues ?? valuesOf(source) } };
    delete o.recipe; delete o.emitterAttachment; delete o.bakedInto; delete o.shadowMapped;
    return makeLightRoot(o, values);
  }
  // The project's light records (plan 3.5): overrides of original lights, added lights, and the area lights' bindings.
  function lightState(overrides, added) {
    for (const root of lightRoots.values()) {
      const o = root.userData.source;
      if (o.added) {
        const pose = lightPose(root);
        if (o.added.template) added.set(o.actor, recordOf({ form: 'light', id: o.added.entity, actor: o.actor, template: { ...o.added.template }, ...pose,
                                                           light: { ...root.userData.values } }));
        else added.set(o.actor, recordOf({ form: 'light', id: o.added.entity, actor: o.actor, from: o.added.from, component: o.added.component, ...pose,
                                           light: changedValues(root.userData.values, o.added.templateValues) }));
        continue;
      }
      if (isStream(o) || lightViewOnly(o)) continue;
      const target = { package: o.sourcePackage, level: o.layer, actor: o.actor };
      if (root.userData.deleted) { overrides.set(lightKey(o), { target, deleted: true }); continue; }
      const light = changedValues(root.userData.values, root.userData.baseValues);
      if (root.userData.edit || Object.keys(light).length)
        overrides.set(lightKey(o), { target, ...lightPose(root), ...(Object.keys(light).length ? { light } : {}) });
    }
    return [...areaBindings].map(([actor, owner]) => ({ target: { package: data.name, level: 'base', actor }, owner }));
  }
  // Back to the lights as exported: added ones go, deleted ones return, moved and changed ones go back, bindings end.
  function clearLightEdits() {
    removeLightRoots([...lightRoots.values()].filter(r => r.userData.source.added));
    const moved = [...lightRoots.values()].filter(r => r.userData.edit);
    gizmo.applyMatrices(moved, moved.map(r => baseMatrix(r)));
    for (const r of lightRoots.values()) { r.userData.deleted = false; setLightValues(r, r.userData.baseValues); }
    setAreaBindings(new Map());
  }
  // Light records of a project state put on the map; those naming lights this export lacks are returned to be carried.
  function applyLightRecord(record) {
    const root = lightIndex.get(targetKey(record.target));
    if (!root) return false;
    if (record.deleted) root.userData.deleted = true;
    else {
      gizmo.applyMatrices([root], [actorMatrix(record.location, record.rotation)]);
      if (record.light) setLightValues(root, { ...root.userData.baseValues, ...record.light });
    }
    return true;
  }
  function addedLightOf(entity) {
    const l = optionsOf(entity, 'light');      // (piece_records.js: its names, pose, recipe or original, and values)
    const serial = Number(/_copy(\d+)$/.exec(l.actor)?.[1]);
    if (serial > copySerial) setCopySerial(serial);
    let source, values;
    if (l.recipe) {
      const made = recipeLight(l.recipe, l.light, l.location, l.rotation, l.actor);
      if (!made) return null;
      ({ source, values } = made);
    } else {
      const template = lightIndex.get(targetKey(l.from))?.userData.source;
      if (!template || l.component !== template.component) return null;
      source = template; values = { ...valuesOf(template), ...(l.light ?? {}) };
    }
    const root = addedLight(source, actorMatrix(l.location, l.rotation), values, l.actor);
    const o = root.userData.source;
    Object.assign(o, { location: l.location, rotation: l.rotation });
    o.added.entity = l.entity;
    return root;
  }
  // The Map lighting mode's buttons as a scene opens (app.js's startScene): the map's own modes only where its lighting
  // can be had.
  function lightingModes() {
    for (const button of $('lighting').querySelectorAll('button')) button.disabled = button.dataset.value !== 'neutral' && !lighting.available;
    // Neutral light by default: our map lighting is an approximation (the user's choice, 7 November).
    $('lighting').value = 'neutral';
  }
  // The view lit as the Map lighting mode says, with the lights as edited: app.js's applyLighting once a scene has
  // started (before, it does nothing).
  function applyMapLighting() {
    // the lights as edited (lightRecords), when they changed since
    if (lightsDirty && data.scope === 'map' && !data.preview) {
      lighting.setLights(lightRecords()); setLightsDirty(false); setLastLightSync(performance.now());
    }
    if (soloOn) { lighting.dim(sun.target.position, lightRadius); return; }
    const result = lighting.apply($('lighting').value, sun.target.position, lightRadius);
    $('lightCount').textContent = $('lighting').value === 'neutral' ? '' : `${result.local} local lights`;
  }
  // The lights of a map once its pieces are built: placed, area, toggleable and streamed levels' lights with a place; the
  // sun and sky without one (listed in View options).
  function buildLights(streamLights) {
    const all = [...(data.lights ?? []), ...streamLights];
    fixedLights = (data.lights ?? []).filter(l => !['point', 'spot'].includes(l.kind));
    addLightRoots(all.filter(l => ['point', 'spot'].includes(l.kind) && Array.isArray(l.location))
      .map(l => makeLightRoot(lightSource(l), valuesOf(l))));
    const sky = $('skyList');
    sky.replaceChildren();
    for (const l of fixedLights) text(sky, 'div', `${short(l.actor)} · ${l.kind}${l.role === 'dominant' ? ' (sun or moon)' : ''} · brightness ${Number(l.brightness.toFixed(2))}${l.enabled ? '' : ' · off'}`);
    if (!fixedLights.length) text(sky, 'div', 'This map has no sun, moon or sky light.');
    $('skyRow').hidden = !(data.lights ?? []).length;
    deriveAreaLights();
  }
  // The page's lights after any edit: markers painted for the selection, the panel, the shapes, Solo, the area lights
  // following their pieces and the Map lighting mode (throttled while a drag lasts).
  function lightsChanged() {
    const picked = new Set(gizmo.picks().ids.filter(id => lightRoots.has(id)));
    for (const id of new Set([...paintedLights, ...picked])) { const r = lightRoots.get(id); if (r) paintLight(r); }
    paintedLights = picked;
    deriveAreaLights();
    refreshLightShapes();   // first: the panel says what the outlines show
    lightPanel();
    if (soloOn) updateSolo();
  }
  // Light edits are drawn and saved; while the family is refused, said once, as warnNotBuilt does for pieces. A glowing
  // piece moved, copied or deleted takes its light along, so it waits for the same test.
  function warnLights() {
    if (warnedLights || !families?.families?.light || families.families.light.builds) return;
    const edited = [...lightRoots.values()].some(r => !isStream(r.userData.source) && lightEdited(r));
    const glowing = derivedCopies.length || [...lightRoots.values()].some(r => r.userData.source.role === 'area'
      && (r.userData.derivedGone || !r.matrix.equals(baseMatrix(r))));
    if (!edited && !glowing) return;
    warnedLights = true;
    banner(`${edited ? 'Light edits are' : 'A glowing piece moved, copied or deleted takes its generated light along, which is'} drawn and saved, `
           + 'but not built yet: the Build makes lights once their game test passes, and refuses the project until then.',
           [['Undo', () => gizmo.undo()]]);
  }

  // After an edit, and while a gizmo handle is held (the edit hub, edit_hub.js).
  onHub('edit', 'lights', () => {
    lightsChanged();
    warnLights();
  });
  onHub('drag', 'lights', () => { if (lightsShown) lightsChanged(); });
  // As something is picked (the edit hub's select runs): the light section shown for a light, and a light's panel.
  onHub('select-sections', 'lights', root => { $('lightBox').hidden = !root?.userData.light; });
  onHub('select-light', 'lights', root => { showLight(root); });

  return { addedLight, addedLightOf, addLightRoots, applyLightRecord, applyMapLighting, areaOwner, assignOwner,
           buildLights, changeLight, clearLightEdits, commitColour, commitLightField, endLightDrag, handlesNear,
           hoverHandle, lightClip, lightEdited, lightEntries, lightingModes, lightPanel, lightPose, lightRecords,
           lightsBlocked, lightShapes, lightSource, lightState, lightViewOnly, moveLightDrag, ownerRoot, pickLight,
           recipeLight, refreshLightShapes, refreshLightVisibility, removeLightRoots, scaleMarkers, setBinding,
           setLightsShown, setLightValues, setNormalLights, setSolo, startLightDrag, updateLightHandles, valuesEdited,
           withStorableCone };
}
