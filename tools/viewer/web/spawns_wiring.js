// The Spawns view and the mission objects' moves (refactor stage P6; editor spawns plan, SP3 to SP9; mission types
// plan, Part E; spawns_view.js makes the markers and says what each record is, spawn_rules.js what the game does with
// a spawn point). The base map's spawn points, the objects of the streams the header's mission streams, an added
// bomb's donor objects and an LWR patch's spawn points are drawn as markers. Here:
// - the view on or off (setSpawnsShown, setNormalSpawns) and its families' flyout; a marker picked (setPickedSpawn,
//   spawnClick), shown from the build window (showSpawn), kept one size on screen;
// - the markers drawn (refreshSpawnMarkers), the picked one's panel (spawnPanel) and its controls (turns, values,
//   Copy, Delete, back as the map has it);
// - the project's moves and edits of them (missionMoves: a stream object's group moved; a base pod, Meld point,
//   drop-in point or no-spawn volume moved, turned, given values or deleted; a copy), each one undo step, and what
//   the project records of them (missionOverrides, spawnCopyRecords);
// - the picked marker's gizmo, whose arrows move it by whole tiles and levels;
// - a spawn point added from the Add panel (spawnAddEntries, startSpawnPlacing, placeSpawn);
// - the project's spawn rule (Scripted drop-ins land where placed) and what the install does with spawn points
//   (loadSpawnRules).
//
// createSpawnsWiring takes what it needs of app.js as one argument object, when app.js makes it: the camera, the
// renderer and the scene, the landing zones' layer and the Landing zones view's functions, the other views' switches,
// the header's missions and the Effects view's number field. Its own state is inside it (whether the zones showed
// before the view, the gizmo's drag); what other areas read or set (the Normal button's switch, the families shown,
// the moves and their drag, the entries drawn, the install's rules, a spawn point being placed, the zone described)
// is editor_state.js's.
import * as THREE from 'three';
import { ask } from './api.js';
import { LEVEL, PL, QUARTER, TILE } from './constants.js';
import { onHub } from './edit_hub.js';
import { activeMapId, builderMode, data, effectsOn, families, lightsOn, missionDragView, missionIndex, missionMoves,
         missionPickValue, nextCopySerial, normalSpawns, pickedSpawn, pieces, placing, projectSpawnRules, roots,
         selected, setMissionDragView, setMissionMovesValue, setNormalSpawnsValue, setPickedSpawnValue,
         setProjectSpawnRules, setSpawnEntriesNow, setSpawnFilters, setSpawnPlacing, setSpawnRulesData, setSpawnsOn,
         setSpawnZonePick, spawnEntriesNow, spawnFilters, spawnPlacing, spawnRulesData, spawnsOn, spawnZonePick,
         streamSet, volumesOn, zonesOn } from './editor_state.js';
import { scaleMarker } from './lights_view.js';
import { uuid, validSpawnRules } from './project.js';
import { consumerWords, fromWords, useLines } from './spawn_rules.js';
import { addFacingPointer, addPlace, addTemplate, baseEditWords, boxMiddle, boxWords, copyEntry, copyMarkerRecord,
         copyRecord, copyTemplateWhy, deletedEntry, editCopy, editSpawn, FAMILIES, familyOf, identityLines, KINDS,
         makeSpawnBox, makeSpawnMarker, NEW_VOLUME, paintSpawnMarker, recordBox, shownEntries, SPAWN_COPY_KINDS,
         SPAWN_MARKER_SIZE, SPAWN_VALUE_KEYS, spawnEditable, spawnKey, spawnMoveWords, spawnNamed, spawnOverride,
         spawnRecords, titleOf, volumePlace } from './spawns_view.js';
import { forget, recall, remember } from './storage.js';
import { plural, short, text } from './dom_words.js';
import { isStream } from './piece_records.js';
import { gameToView } from './handles.js';
import { createViewGizmo } from './view_gizmo.js';

export function createSpawnsWiring({ $, camera, controls, flashHint, floorStays, gizmo, groundAt, groundHeight,
                                    headerMission, headerMissions, landingLayer, lightButton, movedMatrix, numberField,
                                    pick, pickZone, projectsAvailable, rayAt, renderer, restingHint, select,
                                    setEffectsShown, setLightsShown, setVolumesShown, setZonesShown, stopPickBox,
                                    tileCorner, world, zoneHit, zoneState }) {
  // ---------------------------------------------------------------- spawn points and objectives (spawns plan, SP3)
  // The Spawns view (Shift+U, the rail's button) and the Normal button's "Spawn points and objectives" switch draw one
  // list of markers (spawns_view.js spawnRecords): the base map's spawn points (export 33), the objects of the streams
  // the header's mission streams, an added bomb's donor objects, an LWR patch's spawn points. A click on one opens its
  // panel (spawnPanel): what it is, its values and where each comes from, its group, what uses it and what it uses, and
  // what the game does with it (spawn_rules.js, from /maps/<id>/spawn-rules.json). In the view a click picks a marker,
  // or a landing zone to describe it, or lets the picked one go, never a piece; in Normal with the switch on, a marker
  // is picked ahead of the piece behind it. A stream object's arrows move its group by whole tiles (mission types plan,
  // Part E: missionMoves). The switch replaced View options' Mission objects (decision D2): a saved choice carries over.
  const NORMAL_SPAWNS = 'workshop.normalSpawns', SPAWN_FILTERS = 'workshop.spawnFilters';
  {
    const old = recall('workshop.missionObjects');
    if (old !== null && recall(NORMAL_SPAWNS) === null) remember(NORMAL_SPAWNS, old === '0' ? '0' : '1');
    forget('workshop.missionObjects');
  }
  setNormalSpawnsValue(recall(NORMAL_SPAWNS) === '1');
  const spawnLayer = new THREE.Group(); world.add(spawnLayer);
  spawnLayer.visible = false;
  setSpawnFilters((() => { try { return JSON.parse(recall(SPAWN_FILTERS) || '{}') || {}; } catch { return {}; } })());
  // (the families shown, spawnFilters, and the picked marker's key, pickedSpawn: editor_state.js)
  // (a landing zone picked in the Spawns view, described only (decision D3), spawnZonePick: editor_state.js)
  let spawnLandingBefore = true;     // whether the landing zones showed before the Spawns view showed them
  // (what the install does with spawn points (spawn-rules.json), read as a map opens, spawnRulesData: editor_state.js)
  // (spawnRecords' entries for the mission the header shows, spawnEntriesNow: editor_state.js)
  const spawnsAvailable = () => Boolean(data) && data.scope === 'map' && !data.preview && !builderMode;
  const spawnsShown = () => spawnsAvailable() && (spawnsOn || (normalSpawns && !volumesOn && !lightsOn && !zonesOn && !effectsOn));
  // A mission's objects moved in their streams (mission types plan, Part E): `${stream}|${actor}` -> {stream, actor,
  // location, rotation}, saved as overrides of `level: "stream"` (the stream as the package). The Build moves each in
  // place in the variant's copy of the stream. An object moves with its group (a capture point with its volume, a bomb
  // or a power node with its button, emitters, rebuild volume and, for the bomb, its helper point), by whole tiles and
  // levels, one undo step a drag. The key is the marker's (spawnKey).
  // The base map's pods, Meld points and drop-in points the project edits (the editor spawns plan, SP6) are kept here
  // too, as `base|${actor}` -> {stream: null, actor, location, rotation, spawn}: where each stands and faces now and the
  // values it changes (spawns_view.js editSpawn), saved as overrides of `level: "base"`. Each moves alone, by whole tiles
  // and levels, a drop-in point turns by quarters in its panel, and each takes its values there; the Build edits it in place.
  // (missionMoves, and missionDragView while a drag lasts: editor_state.js)
  const missionKey = (stream, actor) => spawnKey(stream, actor);
  const missionMoveOf = (stream, actor) => (missionDragView ?? missionMoves).get(missionKey(stream, actor));
  const missionAt = (stream, o) => missionMoveOf(stream, o.actor)?.location ?? o.location;
  // a stream's mission objects: a stream of the export's, else the donor stream an added kind takes them from
  const streamObjects = stream => data?.streams?.[stream]?.missionObjects
    ?? Object.values(data?.donors ?? {}).find(d => d.stream === stream)?.missionObjects ?? [];
  function missionMembers(stream, o) {
    const objects = streamObjects(stream);
    return o.group ? objects.filter(x => x.group === o.group) : [o];
  }
  function missionOverrides() {
    return [...missionMoves.values()].filter(m => m.stream !== 'copy').map(m => (m.stream === null ? spawnOverride(data.name, baseSpawnOf(m.actor), m)
      : { target: { package: m.stream, level: 'stream', actor: m.actor }, location: [...m.location], rotation: [...m.rotation] }));
  }
  // the project's copies of the map's pods and Meld points (SP7), as its added records
  const spawnCopyRecords = () => [...missionMoves.values()].filter(m => m.stream === 'copy').map(m => copyRecord(data.name, m));
  // a base spawn point's record (export 33), but a landing's
  const baseSpawnOf = actor => (data?.spawns ?? []).find(r => r.actor === actor && !r.landing) ?? null;
  const spawnFamilyBuilds = () => Boolean(families?.families?.spawn?.builds);
  // The moves with an object's group shifted by `delta` (game units): a member back at its own place is no move. A base
  // spawn point (stream null) moves alone.
  function movedMissions(stream, actor, delta, from = missionMoves) {
    if (stream === null) return editedSpawns(actor, { delta }, from);
    if (stream === 'copy') return editedCopies(actor, { delta }, from);
    const o = streamObjects(stream).find(x => x.actor === actor);
    const next = new Map(from);
    if (!o) return next;
    for (const m of missionMembers(stream, o)) {
      const k = missionKey(stream, m.actor), at = from.get(k)?.location ?? m.location;
      const location = at.map((v, i) => Math.round((v + delta[i]) * 1000) / 1000);
      if (location.every((v, i) => Math.abs(v - m.location[i]) < 1e-3)) next.delete(k);
      else next.set(k, { stream, actor: m.actor, location, rotation: (m.rotation ?? [0, 0, 0]).map(v => Math.round(v)) });
    }
    return next;
  }
  // A project saved before export 33 moved the bomb without its helper point (F-124; decision D6): the helper gets the
  // group's move where every other part of the bomb shares one offset and the helper has none. Returns the moves with
  // it added, or null when nothing needs it.
  function bombHelperFix(moves = missionMoves) {
    let next = null;
    for (const stream of new Set([...moves.values()].map(m => m.stream))) {
      const parts = streamObjects(stream).filter(o => o.group === 'bomb');
      const helpers = parts.filter(o => o.role === 'point'), others = parts.filter(o => o.role !== 'point');
      if (!helpers.length || !others.length || helpers.some(h => moves.has(missionKey(stream, h.actor)))) continue;
      const offsets = new Set(others.map(o => { const m = moves.get(missionKey(stream, o.actor));
        return (m ? m.location.map((v, i) => v - o.location[i]) : [0, 0, 0]).map(v => Math.round(v * 10) / 10).join(','); }));
      if (offsets.size !== 1) continue;
      const delta = [...offsets][0].split(',').map(Number);
      if (delta.every(v => !v)) continue;
      next = next ?? new Map(moves);
      for (const h of helpers) next.set(missionKey(stream, h.actor), { stream, actor: h.actor,
        location: h.location.map((v, i) => Math.round((v + delta[i]) * 1000) / 1000), rotation: (h.rotation ?? [0, 0, 0]).map(v => Math.round(v)) });
    }
    return next;
  }
  // The streamed pieces of the moved objects (a power node's mesh, the bomb's) drawn where they stand now.
  function placeStreamRoots() {
    const moves = missionDragView ?? missionMoves;
    for (const root of roots.values()) {
      const s = root.userData.source;
      if (!isStream(s)) continue;
      const m = moves.get(missionKey(s.stream ?? s.sourcePackage, s.actor));
      if (!m && !root.userData.streamMoved) continue;
      root.matrix.copy(m ? movedMatrix(s, m.location, m.rotation) : new THREE.Matrix4().fromArray(s.matrix));
      root.matrixWorldNeedsUpdate = true;
      root.userData.streamMoved = Boolean(m);
    }
  }
  function setMissionMoves(next) {
    setMissionMovesValue(next); setMissionDragView(null);
    placeStreamRoots(); refreshSpawnMarkers(); placeMissionGizmo();
  }
  // The edits with a base spawn point's changed (spawns_view.js editSpawn: delta, turn, spawn values).
  function editedSpawns(actor, change, from = missionMoves) {
    const o = baseSpawnOf(actor), next = new Map(from), k = missionKey(null, actor);
    if (!o) return next;
    const entry = editSpawn(o, from.get(k) ?? null, change);
    if (entry) next.set(k, entry); else next.delete(k);
    return next;
  }
  // One undo step: a base spawn point turned or given values (its panel's controls; also the test's way in).
  function editBaseSpawn(actor, change, hint) {
    const before = new Map(missionMoves), after = editedSpawns(actor, change);
    if (stateKeyOf(after) === stateKeyOf(before)) return false;
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    if (hint) flashHint(hint);
    return true;
  }
  const stateKeyOf = moves => JSON.stringify([...moves.entries()]);
  // The edits with a copy's changed (spawns_view.js editCopy), and one undo step of it (SP7).
  function editedCopies(actor, change, from = missionMoves) {
    const k = spawnKey('copy', actor), entry = from.get(k), o = copyTemplateOf(entry), next = new Map(from);
    if (o) next.set(k, editCopy(o, entry, change));
    return next;
  }
  function editSpawnCopy(actor, change, hint) {
    const before = new Map(missionMoves), after = editedCopies(actor, change);
    if (stateKeyOf(after) === stateKeyOf(before)) return false;
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    if (hint) flashHint(hint);
    return true;
  }
  // One undo step: a copy of a base pod or Meld point (or of a copy: its template's, with its values and turn), a tile
  // east of it, picked (SP7). Returns the copy's key, or null where it can't be copied.
  function copySpawn(key, delta = [TILE, 0, 0]) {
    const e = spawnEntry(key);
    const o = e?.layer === 'copy' ? copyTemplateOf(missionMoves.get(key)) : e?.layer === 'base' ? e.record : null;
    if (!o || copyTemplateWhy(o) || missionMoves.get(key)?.deleted) return null;
    const at = spawnAt(e), now = missionMoves.get(key);
    const actor = copyName(o), k = spawnKey('copy', actor), box = o.kind === 'noSpawn' ? spawnBoxNow(e) : null;
    const entry = copyEntry(o, { id: uuid(), actor, location: [0, 1, 2].map(k => at[k] + delta[k]), box: box && box.map((v, k) => v + delta[k % 3]),
                                 rotation: now?.rotation ?? (o.rotation ?? [0, 0, 0]).map(v => Math.round(v)), spawn: now?.spawn ?? {} });
    const before = new Map(missionMoves), after = new Map(missionMoves).set(k, entry);
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    setPickedSpawn(k);
    flashHint(`Copied ${short(e.record.actor)} a tile east · drag its arrows to place it`);
    return k;
  }
  // The picked spawn point as a copy carries it (Ctrl+C, Ctrl+X): its template, its values and turn and where it stands,
  // so a cut one is placed again; { why } where it isn't copied (a mission's object, a kind not copied), null with none
  // picked.
  function spawnClip(key = pickedSpawn) {
    const e = key ? spawnEntry(key) : null;
    if (!e) return null;
    const o = e.layer === 'copy' ? copyTemplateOf(missionMoves.get(key)) : e.layer === 'base' ? e.record : null;
    if (!o) return { why: 'A mission\'s object isn\'t copied: it is the mission\'s own' };
    if (copyTemplateWhy(o)) return { why: copyTemplateWhy(o) };
    const now = missionMoves.get(key);
    return { thing: 'spawn', name: `${KINDS[o.kind]?.label ?? 'spawn point'} ${short(e.record.actor)}`, o, at: spawnAt(e),
             box: o.kind === 'noSpawn' ? spawnBoxNow(e) : null, rotation: now?.rotation ?? (o.rotation ?? [0, 0, 0]).map(v => Math.round(v)),
             spawn: now?.spawn ?? {} };
  }
  // a copy's template: the base record it copies, or NEW_VOLUME for a no-spawn volume made fresh (no `from`)
  const copyTemplateOf = m => (m?.stream !== 'copy' ? null : m.copy.from ? baseSpawnOf(m.copy.from) : m.copy.kind === 'noSpawn' ? NEW_VOLUME : null);
  // a new copy's name: its template's with a serial (a fresh volume's after the class)
  const copyName = o => `${o.actor ?? `${PL}${o.actorClass}`}_copy${nextCopySerial()}`;
  // a no-spawn volume's box now (the drag's, the project's, else the map's): [x0, y0, z0, x1, y1, z1]
  const spawnBoxNow = e => missionMoveOf(e.stream, e.record.actor)?.box ?? recordBox(e.record);
  // A new pod or Meld point from the Add panel (its Spawn points kind): the Spawns view is shown with the kind's family,
  // and the next click places a copy of the kind's template (spawns_view.js addTemplate) on the tile under it
  // (the kind being placed, spawnPlacing: editor_state.js)
  // (`clip`: a pasted copy, spawnClip's: its kind's family shown, and the next click places it)
  function startSpawnPlacing(kind, clip = null) {
    if (clip) kind = clip.o.kind;
    const template = clip ? clip.o : addTemplate(data?.spawns, kind);
    if (!template || !spawnFamilyBuilds()) return;
    setSpawnsShown(true);
    const family = KINDS[kind].family;
    if (spawnFilters[family] === false) {
      setSpawnFilters({ ...spawnFilters, [family]: true }); remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); syncSpawnFilters(); refreshSpawnMarkers();
    }
    // (the picked point goes, so its arrows are never under the click)
    if (pickedSpawn) setPickedSpawn(null);
    setSpawnPlacing(clip ?? kind); renderer.domElement.style.cursor = 'crosshair';
    placeMissionGizmo();
    flashHint(`Click the tile the ${clip ? `copy of ${clip.name}` : `new ${KINDS[kind].label.toLowerCase()}`} is to stand ${kind === 'noSpawn' ? 'over' : 'on'} · Esc cancels`);
  }
  function stopSpawnPlacing() {
    if (!spawnPlacing) return;
    setSpawnPlacing(null); renderer.domElement.style.cursor = ''; pieces.setChosen?.(null); restingHint();
    placeMissionGizmo();
  }
  // One undo step: the copy placed where the click falls (on a piece, else on the ground grid's plane), on the tile under
  // it by whole tiles from its template, at the template's height above its own floor; then picked
  // (a pasted copy, spawnPlacing a clip: its template where it stood, with its values and turn, placed as the kind's is)
  function placeSpawn(clientX, clientY) {
    const clip = typeof spawnPlacing === 'object' ? spawnPlacing : null, kind = clip ? clip.o.kind : spawnPlacing;
    const template = clip ? { ...clip.o, location: clip.at, rotation: clip.rotation, ...(clip.box ? { box: { min: clip.box.slice(0, 3), max: clip.box.slice(3) } } : {}) }
      : addTemplate(data?.spawns, kind);
    stopSpawnPlacing();
    if (!template) return null;
    const hit = pick(clientX, clientY)?.point
      ?? rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundHeight()), new THREE.Vector3());
    if (!hit) return null;
    const actor = copyName(template), k = spawnKey('copy', actor);
    let entry;
    if (kind === 'noSpawn') {
      // a volume: its box over whole tiles round the click, its bottom on the level of the surface under it
      const grid = { origin: data?.tileGrid?.origin ?? [0, 0, 0], size: data?.tileGrid?.size ?? [TILE, TILE, LEVEL] };
      const box = volumePlace(template, [hit.x, hit.z, hit.y], groundAt(hit.x, hit.z, hit.y + 64), grid);
      entry = copyEntry(template, { id: uuid(), actor, box, spawn: clip?.spawn ?? {} });
    } else {
      const [tx, ty, tz] = template.location;
      const place0 = addPlace(template, [hit.x, hit.z, hit.y], null, null);
      const at = addPlace(template, [hit.x, hit.z, hit.y], groundAt(place0[0], place0[1], hit.y + 64), groundAt(tx, ty, tz + 64));
      entry = copyEntry(template, { id: uuid(), actor, location: at, rotation: (template.rotation ?? [0, 0, 0]).map(v => Math.round(v)), spawn: clip?.spawn ?? {} });
    }
    const before = new Map(missionMoves), after = new Map(missionMoves).set(k, entry);
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    setPickedSpawn(k);
    if (clip) flashHint(`Placed a copy of ${clip.name} · its arrows move it`);
    else flashHint(kind === 'noSpawn' ? `Added a no-spawn volume${template.fresh ? '' : `, a copy of ${short(template.actor)}`} · its arrows move it, its white handles stretch a side`
      : `Added a ${KINDS[kind].label.toLowerCase()}, a copy of ${short(template.actor)} · its arrows move it`);
    return k;
  }
  // One undo step: a base pod, Meld point, drop-in point or no-spawn volume deleted (its moves and values go with it), or
  // a copy taken away (SP7).
  function deleteSpawn(key) {
    const e = spawnEntry(key);
    if (!e || !['base', 'copy'].includes(e.layer) || (e.layer === 'base' && (!spawnEditable(e.record) || missionMoves.get(key)?.deleted))) return false;
    const before = new Map(missionMoves), after = new Map(missionMoves);
    if (e.layer === 'copy') after.delete(key);
    else after.set(key, deletedEntry(e.record));
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    flashHint(e.layer === 'copy' ? 'Copy taken away' : spawnNamed(e.record) ? 'Deleted · something names it, so the Build keeps it and warns' : 'Deleted · the Build takes it out of the level\'s list');
    return true;
  }
  // One undo step: the picked object's group moved by `delta` (also the test's way in).
  function moveMissionGroup(stream, actor, delta) {
    if (!delta.some(v => Math.abs(v) > 1e-6)) return false;
    if (stream === null) return editBaseSpawn(actor, { delta }, 'Moved the spawn point · the Build moves it in place');
    if (stream === 'copy') return editSpawnCopy(actor, { delta }, 'Moved the copy');
    const before = new Map(missionMoves), after = movedMissions(stream, actor, delta);
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    const o = streamObjects(stream).find(x => x.actor === actor), n = missionMembers(stream, o).length;
    flashHint(`Moved ${n > 1 ? `the group of ${n}` : 'the mission object'} · the Build moves ${n > 1 ? 'them' : 'it'} in the stream's copy`);
    return true;
  }
  // the donor an added kind's objects come from (an added council bomb: Slaughterhouse's stream), or null
  function spawnDonor() {
    if (missionIndex >= 0 || !missionPickValue.startsWith('kind:')) return null;
    const kind = missionPickValue.slice(5), d = data?.donors?.[kind];
    return d ? { kind, ...d } : null;
  }
  const spawnEntry = key => (key ? spawnEntriesNow.find(e => e.key === key) ?? null : null);
  // where a marker stands now: where the project's move puts it (a stream's or donor's object, a base spawn point), else
  // where its map has it
  // (a no-spawn volume's: its box's middle)
  const spawnAt = e => (e.record.kind === 'noSpawn' && (e.record.box || missionMoveOf(e.stream, e.record.actor)?.box)
    ? boxMiddle(spawnBoxNow(e)) : missionAt(e.stream, e.record));
  // the spawn points the panel turns: a drop-in point's facing picks the side its units drop from (a unit dropped from a
  // height, as a wave's are from 768 up, starts a tile behind it and lands on it facing its way:
  // XGAISpawnMethod_DropIn.OnActivate_UpdateSpawnPoint, XComWaveSystem's DropHeight); a pod's only says where on a ring
  // round it its other aliens start (XComAlienPod.GetDistributedLocationAround), which aims nothing, so the panel has no
  // turn for it, nor for any other point (18 November 2026: only where it changes the game)
  const TURNED_KINDS = ['dropIn'];
  // which way a base drop-in point faces now (its yaw), or null for one that isn't edited here or saves no rotation
  function spawnFacing(e) {
    if (!['base', 'copy'].includes(e.layer) || !TURNED_KINDS.includes(e.record.kind)) return null;
    const m = missionMoveOf(e.stream, e.record.actor);
    if (m?.deleted) return null;
    return m ? m.rotation[1] : e.record.savesRotation || spawnMovable(e) ? Math.round(e.record.rotation?.[1] ?? 0) : null;
  }
  // the project's copies as the view's entries (SP7): `copy|${actor}`, layer 'copy', their template's record under their
  // own name (spawns_view.js copyMarkerRecord)
  function copyEntries() {
    const out = [];
    for (const m of missionMoves.values()) {
      const o = copyTemplateOf(m);
      if (o) out.push({ key: spawnKey('copy', m.actor), layer: 'copy', stream: 'copy', record: copyMarkerRecord(o, m), readOnly: false });
    }
    return out;
  }
  const spawnDeleted = e => e?.layer === 'base' && Boolean(missionMoves.get(e.key)?.deleted);
  function refreshSpawnMarkers() {
    // (a halo's geometry is three.js's one for every sprite: only its material is the marker's own)
    for (const child of [...spawnLayer.children]) { child.traverse(o => (o.isSprite ? o.material.dispose() : o.geometry?.dispose())); spawnLayer.remove(child); }
    setSpawnEntriesNow(spawnsAvailable() ? [...spawnRecords(data, streamSet, spawnDonor()), ...copyEntries()] : []);
    // (a deleted base point shows only with the flyout's Deleted points switch on)
    const shown = shownEntries(spawnEntriesNow, spawnFilters, spawnDeleted);
    if (pickedSpawn && !shown.some(e => e.key === pickedSpawn)) setPickedSpawnValue(null);      // another mission's, or a family hidden
    spawnLayer.visible = spawnsShown();
    for (const e of shown) {
      const marker = makeSpawnMarker(THREE, e.record.kind, e.readOnly || spawnDeleted(e));
      marker.position.copy(gameToView(spawnAt(e)));
      marker.userData.spawn = e.key;
      // (the picked pod or drop-in point shows the way it faces)
      const yaw = e.key === pickedSpawn ? spawnFacing(e) : null;
      if (yaw !== null) addFacingPointer(THREE, marker, yaw);
      paintSpawnMarker(THREE, marker, e.key === pickedSpawn);
      spawnLayer.add(marker);
      // a no-spawn volume's box round its marker (not picked: the marker is)
      const b = e.record.kind === 'noSpawn' ? spawnBoxNow(e) : null;
      if (b) {
        const box = makeSpawnBox(THREE, 'noSpawn', gameToView(boxMiddle(b)), [b[3] - b[0], b[5] - b[2], b[4] - b[1]],
                                 { pale: e.readOnly || spawnDeleted(e), picked: e.key === pickedSpawn });
        box.userData.spawnBox = e.key;
        spawnLayer.add(box);
      }
    }
    spawnPanel();
  }
  // The picked marker's panel (or the picked zone's, in the Spawns view)
  function spawnPanel() {
    const e = spawnEntry(pickedSpawn), shown = spawnsShown();
    const zones = spawnsOn && spawnZonePick && !e ? zoneState() : null, k = zones ? zones.zones.findIndex(z => z.id === spawnZonePick) : -1;
    $('spawnPanel').hidden = !shown || (!e && k < 0);
    $('spawnZoneEdit').hidden = k < 0;
    $('spawnEdit').hidden = true;
    const info = $('spawnInfo');
    info.replaceChildren();
    const line = (head, value) => { const p = document.createElement('p'); if (head) text(p, 'strong', `${head}: `); p.append(value); info.append(p); return p; };
    // (the About fold's one line: the first thing said of it)
    queueMicrotask(() => { $('spawnAboutSum').textContent = $('spawnAboutSum').title = info.firstElementChild?.textContent ?? ''; });
    if (k >= 0) {
      const z = zones.zones[k], ewSlot = zones.slots.has(k);
      $('spawnTitle').textContent = `Landing zone ${k + 1} of ${zones.zones.length}`;
      line('', `${z.lwr === false ? 'Long War doesn\'t use it' : 'Long War lands the squad here (one of its landing lines)'}${ewSlot ? '; plain Enemy Within lands here in place of one of the map\'s own landings' : '; plain Enemy Within lands at the map\'s own landing instead'}.`);
      if (z.missionType || z.councilType) line('', `Kept for ${[z.missionType, z.councilType].filter(Boolean).join(', ')}.`);
      line('', 'Landing zones are moved, turned, copied and deleted in the Landing zones view.');
      return;
    }
    if (!e) return;
    const label = headerMissions().find(m => m.value === missionPickValue)?.label;
    // a base spawn point the project edits shows the project's values, marked as its own (SP6); a copy (SP7) its own
    const baseEdit = e.layer === 'base' || e.layer === 'copy' ? missionMoves.get(e.key) ?? null : null;
    const o = e.layer === 'base' && baseEdit && Object.keys(baseEdit.spawn).length ? { ...e.record, values: { ...e.record.values,
      ...Object.fromEntries(Object.entries(baseEdit.spawn).map(([k, v]) => [k, { value: v, from: 'project' }])) } } : e.record;
    const volume = o.kind === 'noSpawn', fresh = e.layer === 'copy' && !o.copyOf;
    $('spawnTitle').textContent = e.layer === 'copy' ? `${KINDS[o.kind]?.label ?? o.kind}: ${fresh ? 'a new one' : `a copy of ${short(o.copyOf)}`}` : titleOf(e, spawnEntriesNow, label);
    for (const l of identityLines({ ...e, record: o }, spawnEntriesNow, fromWords)) line(l.head, l.text);
    if (volume && spawnBoxNow(e)) { const b = spawnBoxNow(e); line('Box', `${boxWords(b)}, from ${Math.round(b[2])} to ${Math.round(b[5])} up.`); }
    const movable = e.layer === 'stream' || e.layer === 'donor';
    const moved = movable ? missionMoves.get(missionKey(e.stream, o.actor)) : null;
    const n = movable ? missionMembers(e.stream, o).length : 1;
    const { usedBy, uses } = useLines(o);
    if (e.layer === 'copy') line('Used by', `nothing: the copy is the project's own${o.kind === 'pod' ? ', with a pod index no pod of the map or its streams has and no pod event names' : ''}.`);
    else if (volume && !usedBy.length) line('Used by', 'nothing names it: the game finds its no-spawn volumes itself.');
    else line('Used by', usedBy.length ? `${usedBy.slice(0, 8).join('; ')}${usedBy.length > 8 ? `; and ${usedBy.length - 8} more` : ''}.`
      : `nothing found in ${e.layer === 'base' ? 'the map' : e.stream}. ${familyOf(o) === 'objectives' ? "The mission's code finds its objectives itself." : `Another layer, ${o.kind === 'pod' ? 'its pod index' : 'a pod index'} or the game's code may still use it.`}`);
    if (uses.length) line('Uses', `${uses.join('; ')}.`);
    const words = consumerWords(o, { rules: spawnRulesData, mission: headerMission(), placed: validSpawnRules(projectSpawnRules), mapExcluded: Boolean(spawnRulesData?.excluded) });
    if (words.length) line('In the game', words.join(' '));
    if (!moved && missionReached(o) && missionFloorLost(o)) line('', 'The edit leaves no floor of the map under it: the Build warns of it.');
    // (a base pod or Meld point: the Build counts the places left, mission_edits.py spawn_places, spawns plan SP5; one
    // the project moved, at its new place)
    else if (!moved && e.layer === 'base' && ['pod', 'meld'].includes(o.kind) && missionFloorLost(baseEdit ? { ...o, location: baseEdit.location } : o)) {
      line('', `The edit leaves no floor of the map under it: the Build counts its place as lost${o.kind === 'pod' ? ' and warns when fewer pod places are left than the map had' : ' and warns when its spawn group is left without a hard point'}.`);
    }
    if (e.layer === 'patch') line('', `From ${e.stream}, Long War's patch: shown, not edited.`);
    else if (e.layer === 'copy' && fresh) {
      line('', `A new no-spawn volume: the Build makes it from one of the map's plain volumes, made a no-spawn volume and stretched over this box, with ${Object.keys(baseEdit?.spawn ?? {}).length ? 'the values above' : 'the class\'s values (it keeps aliens and civilians out)'}.`);
      if (!spawnFamilyBuilds()) line('', 'This editor version doesn\'t build edits of spawn points: the Build refuses the project\'s.');
    } else if (e.layer === 'copy') {
      line('', `A copy of ${short(o.copyOf)}: the Build clones it with its components${o.kind === 'pod' ? ' and gives it a pod index of its own' : volume ? ', stretched over this box' : ''}, with ${Object.keys(baseEdit?.spawn ?? {}).length ? 'the values above' : 'its template\'s values'}.`);
      if (!spawnFamilyBuilds()) line('', 'This editor version doesn\'t build edits of spawn points: the Build refuses the project\'s.');
    } else if (e.layer === 'base' && baseEdit?.deleted) {
      line('', spawnNamed(e.record) ? 'Deleted, but something names it (Used by above): the Build keeps it, and warns, so what names it isn\'t left pointing at nothing.'
        : 'Deleted: the Build takes it out of the level\'s list, so the game never has it.');
    } else if (e.layer === 'base' && baseEdit) {
      const words = spawnMoveWords(e.record, baseEdit);
      line('', `${words ? `${words} ` : ''}The Build ${words ? (volume ? 'moves and stretches it and sets its values' : 'moves it and sets its values') : 'sets its values'} in place: it keeps its name, so what uses it still does${o.links?.length && words ? `; what it links to (${o.links.map(k => k.property).join(', ')}) stays where the map has it` : ''}.`);
      if (!spawnFamilyBuilds()) line('', 'This editor version doesn\'t build edits of spawn points: the Build refuses the project\'s.');
    } else if (e.layer === 'base') line('', spawnMovable(e) ? 'It stands where the map has it.' : baseEditWords);
    else if (!moved) line('', e.layer === 'donor' ? `It stands where ${e.stream} has it on its own map: Long War moves it when it finds places, else it plays there.` : 'It stands where the original map has it.');
    else {
      const d = moved.location.map((v, i) => v - o.location[i]);
      const levels = Math.abs(Math.round(d[2] / LEVEL));
      line('', `Moved ${Math.round(Math.hypot(d[0], d[1]) / TILE)} tiles across${levels ? ` and ${levels} ${levels === 1 ? 'level' : 'levels'} ${d[2] > 0 ? 'up' : 'down'}` : ''} from where ${e.layer === 'donor' ? 'its stream' : 'the original map'} has it${n > 1 ? ', with its group' : ''}: the Build moves ${n > 1 ? 'them' : 'it'} in the variant's copy of ${e.stream}.`);
    }
    if (movable) {
      // a stream's copy replaces it in every record that streams it (keyed by the source package): name them all
      const using = streamMissions(e.stream);
      if (using.length > 1) line('', `The Build moves it for every mission of the variant that streams ${e.stream}: ${using.join(', ')}.`);
    }
    if (movable && projectsAvailable() && spawnMovable(e)) line('', `Drag the arrows to move it${n > 1 ? ` with its group (${n} parts)` : ''} by whole tiles and levels; Ctrl+Z undoes.`).className = 'how';
    if (['base', 'copy'].includes(e.layer) && projectsAvailable() && spawnMovable(e)) {
      const below = [TURNED_KINDS.includes(o.kind) && 'turn it', SPAWN_VALUE_KEYS[o.kind].length && (volume ? 'set what it keeps out' : 'set its values')].filter(Boolean);
      line('', `Drag the arrows to move it by whole tiles and levels${volume ? ', its white handles to stretch a side to the tile lines and levels (Alt: steps of 8)' : ''}${below.length ? `; ${below.join(' and ')} below` : ''}; Ctrl+Z undoes.`).className = 'how';
      spawnEditControls(e, baseEdit);
    } else if (spawnDeleted(e) && projectsAvailable()) spawnEditControls(e, baseEdit);
  }
  // A base pod's, Meld point's, drop-in point's or no-spawn volume's controls (SP6), or a copy's (SP7): quarter turns
  // for a drop-in point, a pod's commander, secondary and use ticks, a Meld point's difficulty, turn it is
  // destroyed on and spawn group, a volume's aliens and civilians ticks; back to the map's; Copy (a plain pod, any Meld
  // point or volume: spawns_view.js copyTemplateWhy) and Delete. A deleted point has Restore alone. Each change is one
  // undo step.
  function spawnEditControls(e, entry) {
    const box = $('spawnEdit'), copy = e.layer === 'copy';
    const base = copy ? copyTemplateOf(entry) : e.record, actor = e.record.actor;
    if (!base) return;
    box.replaceChildren();
    box.hidden = false;
    // (a row with the turns and As the map has it, or Restore, where it has any; a row with Copy and Delete)
    const row = text(box, 'div', '', 'row turnrow');
    const button = (label, title, act) => { const b = text(row, 'button', label); b.type = 'button'; b.title = title; b.onclick = act; return b; };
    if (entry?.deleted) {
      button('Restore', 'Back as the map has it', () => resetBaseSpawn(actor));
      return;
    }
    const edit = (change, hint) => (copy ? editSpawnCopy(actor, change, hint) : editBaseSpawn(actor, change, hint));
    const now = key => (entry && key in entry.spawn ? entry.spawn[key] : base.values?.[key]?.value);
    const set = (key, value, hint) => edit({ spawn: { [key]: value } }, hint);
    if (TURNED_KINDS.includes(base.kind)) {
      for (const [label, turn, title] of [['Turn left', -QUARTER, 'A quarter turn to the left ([)'], ['Turn right', QUARTER, 'A quarter turn to the right (])']]) {
        button(label, `${title}: its units drop in from a tile behind it (high up, for a wave's) and land facing its way`, () => edit({ turn }, `Turned the drop-in point a quarter ${turn > 0 ? 'right' : 'left'}`));
      }
    }
    if (entry && !copy) button('As the map has it', base.kind === 'noSpawn' ? 'Back where the map has it, its size and its own values'
      : 'Back where the map has it, facing its way, with its own values', () => resetBaseSpawn(actor));
    if (!row.childElementCount) row.remove();
    const row2 = text(box, 'div', '', 'row copyrow');
    const why = copyTemplateWhy(base);
    const c = text(row2, 'button', 'Copy');
    c.type = 'button'; c.disabled = Boolean(why);
    c.title = why ? `Not copied: ${why}` : base.kind === 'noSpawn' ? 'A copy a tile east, its size and values (Ctrl+D)'
      : 'A copy a tile east, with its values and turn: the Build clones it with its components (Ctrl+D)';
    c.onclick = () => copySpawn(e.key);
    const d = text(row2, 'button', copy ? 'Delete copy' : 'Delete');
    d.type = 'button';
    d.title = `${copy ? 'The copy taken away' : spawnNamed(base) ? 'Something names it (Used by): a delete keeps it in the map, with a warning' : 'Out of the level\'s list: the game never has it'} (Delete)`;
    d.onclick = () => deleteSpawn(e.key);
    if (base.kind === 'pod') {
      for (const [key, label, title] of [
        ['commander', ' Commander\'s place', 'The mission\'s commander pod takes a commander\'s place first'],
        ['secondary', ' Secondary', 'The pod\'s Secondary flag (bSecondaryPod)'],
        ['use', ' Use', 'Off, the deployment leaves it out where the Overmind decides so (bUse)']]) {
        const wrap = text(box, 'label', '', `check${entry && key in entry.spawn ? ' edited' : ''}`);
        const tick = document.createElement('input');
        tick.type = 'checkbox'; tick.checked = now(key) === true;
        tick.onchange = () => set(key, tick.checked, `${label.trim()} ${tick.checked ? 'on' : 'off'}`);
        wrap.append(tick, label);
        wrap.title = title;
      }
    } else if (base.kind === 'noSpawn') {
      // (the game's class keeps both out: an older export without its values reads as that)
      for (const [key, label, title] of [
        ['aliens', ' Keeps aliens out', 'The game places no alien inside it when it looks for a free spot: a pod deploying its aliens, a unit dropped in (AlienNoSpawnZone)'],
        ['civilians', ' Keeps civilians out', 'The game places no civilian inside it (CivilianNoSpawnZone)']]) {
        const wrap = text(box, 'label', '', `check${entry && key in entry.spawn ? ' edited' : ''}`);
        const tick = document.createElement('input');
        tick.type = 'checkbox'; tick.checked = now(key) !== false;
        tick.onchange = () => set(key, tick.checked, `${label.trim()}: ${tick.checked ? 'on' : 'off'}`);
        wrap.append(tick, label);
        wrap.title = title;
      }
    } else if (base.kind === 'meld') {
      const pick = text(box, 'label', 'Difficulty ', `valueline${entry && 'difficulty' in entry.spawn ? ' edited' : ''}`);
      pick.title = 'The game draws a hard point of a spawn group first';
      const select = document.createElement('select');
      for (const v of ['Easy', 'Hard']) select.append(new Option(v, v));
      select.value = now('difficulty') === 'Hard' ? 'Hard' : 'Easy';
      select.onchange = () => set('difficulty', select.value, `Meld point ${select.value.toLowerCase()}`);
      pick.append(select);
      const turnRow = text(box, 'div', '', `valuepair${entry && 'destroyedOnTurn' in entry.spawn ? ' edited' : ''}`);
      numberField(turnRow, 'Destroyed on turn', now('destroyedOnTurn') ?? -1, { lo: -1, hi: 99, step: 1,
        title: 'The turn its canister is destroyed on, 1 to 99; 0 or -1 for no countdown',
        onCommit: v => set('destroyedOnTurn', Math.round(v), Math.round(v) > 0 ? `Destroyed on turn ${Math.round(v)}` : 'No countdown') });
      const groupRow = text(box, 'div', '', `valuepair${entry && 'spawnGroup' in entry.spawn ? ' edited' : ''}`);
      numberField(groupRow, 'Spawn group', now('spawnGroup') ?? 0, { lo: 0, hi: 99, step: 1,
        title: 'The game draws canisters from the points of a spawn group, 0 to 99',
        onCommit: v => set('spawnGroup', Math.round(v), `Spawn group ${Math.round(v)}`) });
    }
  }
  // One undo step: a base spawn point back where and as the map has it.
  function resetBaseSpawn(actor) {
    const k = missionKey(null, actor);
    if (!missionMoves.has(k)) return false;
    const before = new Map(missionMoves), after = new Map(missionMoves);
    after.delete(k);
    gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
    flashHint('As the map has it');
    return true;
  }
  // the missions the header lists (the project's, or the map's) that stream a package: a record that streams it, or an
  // added kind whose donor it is
  function streamMissions(stream) {
    return headerMissions().filter(m => (m.mission?.streams ?? []).includes(stream)
      || (m.value.startsWith('kind:') && data?.donors?.[m.value.slice(5)]?.stream === stream)).map(m => m.label);
  }
  const missionReached = o => ['capturePoint', 'radar', 'bomb', 'powerNode', 'use', 'soldier', 'landing', 'operative', 'vip'].includes(o.kind)
    && !['effect', 'rebuild', 'visible', 'waypoint', 'volume', 'point'].includes(o.role);
  // Whether the map's saved floor tiles under an object (its level and the one below) had floor and the edit took all
  // of it away (mission_edits.py mission_objects' rule, on the saved tiles only).
  function missionFloorLost(o) {
    const grid = data?.tileGrid, tiles = data?.tactical?.floorTiles;
    if (!grid?.origin || !tiles?.length) return false;
    const [ox, oy, oz] = tileCorner(), [sx, sy, sz] = grid.size ?? [TILE, TILE, LEVEL];
    const tx = Math.floor((o.location[0] - ox) / sx), ty = Math.floor((o.location[1] - oy) / sy), tz = Math.floor((o.location[2] - oz) / sz);
    const under = tiles.filter(f => f.tile[0] === tx && f.tile[1] === ty && (f.tile[2] === tz || f.tile[2] === tz - 1));
    return under.length > 0 && under.every(f => f.actor && !floorStays(f.actor));
  }
  function setPickedSpawn(key) {
    if (key && selected) select(null);
    setPickedSpawnValue(key ?? null); setSpawnZonePick(null);
    refreshSpawnMarkers(); placeMissionGizmo();
  }
  // A stream object's group moves by its arrows (a donor's too, an added bomb's: stage SP4), and so does a base pod, Meld
  // point or drop-in point where the spawn family builds (SP6)
  const spawnMovable = e => Boolean(e) && (e.layer === 'stream' || e.layer === 'donor'
    || (e.layer === 'base' && spawnEditable(e.record) && spawnFamilyBuilds() && !spawnDeleted(e))
    || (e.layer === 'copy' && spawnFamilyBuilds()));
  // The picked spawn point's or mission object's gizmo, made by view_gizmo.js as every view's is: arrows on its marker
  // that move it (a stream object with its group) by whole tiles across and whole levels (64 units) up, a landing
  // zone's do, whatever Snap says: it stands on a tile, and the Snap button shows that step while it is picked. A drop-in
  // point turns by quarters on its ring (R) as by [ and ]. Escape during a drag puts it back; Shift on an arrow drags off
  // a copy of one of the map's pods, Meld points and no-spawn volumes, or of a copy.
  const missionGizmoWanted = () => Boolean(spawnMovable(spawnEntry(pickedSpawn)) && spawnsShown() && projectsAvailable() && !placing
    && !spawnPlacing && !volumesOn && !lightsOn && !zonesOn && !effectsOn);
  // (a drop-in point of the map, or a copy, turns: a pod's facing aims nothing, 18 November 2026)
  const pickedTurns = () => { const e = spawnEntry(pickedSpawn); return Boolean(e) && ['base', 'copy'].includes(e.layer) && TURNED_KINDS.includes(e.record.kind) && spawnMovable(e); };
  const missionView = createViewGizmo({ camera, dom: renderer.domElement, world, orbit: controls, flashHint, leastSnap: 'tile',
    at: () => { const e = missionGizmoWanted() ? spawnEntry(pickedSpawn) : null; return e ? gameToView(spawnAt(e)) : null; },
    modes: () => (pickedTurns() ? ['translate', 'rotate'] : ['translate']),
    what: () => (['stream', 'donor'].includes(spawnEntry(pickedSpawn)?.layer) ? 'a mission object moves with its group by whole tiles' : 'a spawn point stands on a tile'),
    noTurn: 'A pod\'s or Meld point\'s facing aims nothing: only a drop-in point turns',
    noCopy: () => {
      const e = spawnEntry(pickedSpawn);
      if (!e || !['base', 'copy'].includes(e.layer)) return 'A mission\'s object isn\'t copied: it is the mission\'s own; moved, it takes its group along';
      const o = e.layer === 'copy' ? copyTemplateOf(missionMoves.get(pickedSpawn)) : e.record;
      return !o ? 'It isn\'t copied' : copyTemplateWhy(o);
    },
    preview: change => {
      const e = spawnEntry(pickedSpawn);
      setMissionDragView(change?.move && e ? movedMissions(e.stream, e.record.actor, change.move) : null);
      placeStreamRoots(); refreshSpawnMarkers();
    },
    commit: change => {
      const e = spawnEntry(pickedSpawn);
      setMissionDragView(null);
      if (e && change.move && moveMissionGroup(e.stream, e.record.actor, change.move)) return;
      if (e && change.turns) {
        const turn = change.turns * QUARTER, hint = `Turned a quarter ${change.turns === 3 ? 'left' : change.turns === 1 ? 'right' : 'twice'}`;
        if (e.layer === 'copy') editSpawnCopy(e.record.actor, { turn }, hint); else editBaseSpawn(e.record.actor, { turn }, hint);
        return;
      }
      placeStreamRoots(); refreshSpawnMarkers();
    },
    revert: () => { setMissionDragView(null); placeStreamRoots(); refreshSpawnMarkers(); },
    copy: change => { setMissionDragView(null); placeStreamRoots(); copySpawn(pickedSpawn, change.move); } });
  const { controls: missionGizmo, proxy: missionProxy, place: placeMissionGizmo } = missionView;
  // The spawn markers within 18 pixels of a screen point (about the halo's size on screen): [{ key, d (pixels),
  // distance (from the camera) }], nearest the camera first (Ctrl and the wheel: pick_step.js). A click takes the one
  // nearest the pointer.
  function spawnMarkersAt(clientX, clientY) {
    if (!spawnLayer.visible || !spawnLayer.children.length) return [];
    const rect = renderer.domElement.getBoundingClientRect(), out = [];
    for (const marker of spawnLayer.children) {
      if (!marker.userData.spawn) continue;       // (a volume's box: its marker is picked)
      marker.updateWorldMatrix(true, false);
      const at = new THREE.Vector3().setFromMatrixPosition(marker.matrixWorld), p = at.clone().project(camera);
      if (p.z > 1 || p.z < -1) continue;
      const d = Math.hypot(rect.left + (p.x + 1) / 2 * rect.width - clientX, rect.top + (1 - p.y) / 2 * rect.height - clientY);
      if (d < 18) out.push({ key: marker.userData.spawn, d, distance: at.distanceTo(camera.position) });
    }
    return out.sort((a, b) => a.distance - b.distance);
  }
  const pickSpawnMarker = (clientX, clientY) => spawnMarkersAt(clientX, clientY).reduce((best, c) => (!best || c.d < best.d ? c : best), null)?.key ?? null;
  // A click in the Spawns view: a marker, else a landing zone to describe, else the picked one let go
  function spawnClick(e) {
    const key = pickSpawnMarker(e.clientX, e.clientY);
    if (key) { setPickedSpawn(key); return; }
    const z = zoneHit(e.clientX, e.clientY);
    setPickedSpawn(null);
    setSpawnZonePick(z ? z.id : null);
    spawnPanel();
  }
  // A spawn point or mission object named in the build window (`stream`: its stream, null for the base map's): the
  // mission that streams it picked in the header, its marker shown (the Normal switch turned on where neither control
  // shows it, its family too) and picked, the camera on it.
  function showSpawn(actor, stream = null) {
    if (!data) return;
    if (stream === undefined || stream === null) {
      stream = (data.spawns ?? []).some(r => r.actor === actor) ? null
        : Object.entries(data.streams ?? {}).find(([, s]) => (s.missionObjects ?? []).some(o => o.actor === actor))?.[0]
          ?? Object.values(data.donors ?? {}).find(d => (d.missionObjects ?? []).some(o => o.actor === actor))?.stream ?? null;
    }
    if (stream && data.streams?.[stream] && !streamSet.has(stream)) {
      const index = (data.missions ?? []).findIndex(m => (m.streams ?? []).includes(stream));
      if (index >= 0 && headerMissions().some(m => m.index === index)) { $('mission').value = String(index); $('mission').onchange({ target: $('mission') }); }
    }
    if (stream && !data.streams?.[stream]) {
      const kind = Object.entries(data.donors ?? {}).find(([, d]) => d.stream === stream)?.[0];
      const pick = kind && headerMissions().find(m => m.value === `kind:${kind}`);
      if (pick && missionPickValue !== pick.value) { $('mission').value = pick.value; $('mission').onchange({ target: $('mission') }); }
    }
    if (!spawnsShown()) setNormalSpawns(true);
    const key = spawnKey(stream, actor), entry = spawnRecords(data, streamSet, spawnDonor()).find(x => x.key === key)
      ?? spawnRecords(data, streamSet, spawnDonor()).find(x => x.record.actor === actor);
    if (!entry) { flashHint(`${short(actor)} is no spawn point or mission object of the mission the header shows`); return; }
    const family = familyOf(entry.record);
    if (spawnFilters[family] === false || (!(family in spawnFilters) && FAMILIES.find(f => f.id === family)?.on === false)) {
      setSpawnFilters({ ...spawnFilters, [family]: true }); remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); syncSpawnFilters();
    }
    refreshSpawnMarkers();
    setPickedSpawn(entry.key);
    const at = gameToView(spawnAt(entry));
    camera.position.add(at.clone().sub(controls.target)); controls.target.copy(at); controls.update();
  }
  function scaleSpawnMarkers() {
    if (!spawnLayer.visible) return;
    for (const marker of spawnLayer.children) {
      if (!marker.userData.spawn) continue;       // (a volume's box keeps its size in the world)
      scaleMarker(marker, camera, marker.position); marker.scale.multiplyScalar(SPAWN_MARKER_SIZE);
    }
  }
  // The Spawns view on or off (Shift+U, the rail's button): the other views step aside, the selection goes, and the
  // landing zones show (a click on one describes it)
  function setSpawnsShown(on) {
    on = Boolean(on) && spawnsAvailable();
    if (on === spawnsOn) return;
    if (on) {
      if (volumesOn) setVolumesShown(false);
      if (lightsOn) setLightsShown(false);
      if (zonesOn) setZonesShown(false);
      if (effectsOn) setEffectsShown(false);
      stopPickBox(); select(null);
      spawnLandingBefore = landingLayer.visible;
      landingLayer.visible = true;
    } else {
      setSpawnZonePick(null);
      stopSpawnPlacing();     // a spawn point asked for from the Add panel and not placed yet goes with its view
      if (!spawnLandingBefore) landingLayer.visible = false;
    }
    setSpawnsOn(on);
    refreshSpawnMarkers(); lightButton(); placeMissionGizmo();
    if (on) {
      const shown = shownEntries(spawnEntriesNow, spawnFilters), n = kinds => shown.filter(e => kinds.includes(e.record.kind)).length;
      flashHint(`Spawns view: ${plural(n(['pod']), 'pod')}, ${plural(n(['meld']), 'Meld point')}, ${plural(n(['dropIn']), 'drop-in point')}`
        + `${n(['bomb', 'powerNode', 'capturePoint', 'radar', 'use']) ? `, ${plural(n(['bomb', 'powerNode', 'capturePoint', 'radar', 'use']), 'objective')}` : ''} · click one to see what it is · Shift+U leaves it`);
    }
  }
  // The Normal button's switch: the markers drawn and picked with pieces in the normal view (remembered)
  function setNormalSpawns(on) {
    setNormalSpawnsValue(Boolean(on));
    remember(NORMAL_SPAWNS, normalSpawns ? '1' : '0');
    if (!spawnsShown() && pickedSpawn) setPickedSpawn(null);
    refreshSpawnMarkers(); lightButton(); placeMissionGizmo();
  }
  function syncSpawnFilters() {
    for (const f of FAMILIES) { const box = $(`spawnShow-${f.id}`); if (box) box.checked = f.id in spawnFilters ? spawnFilters[f.id] !== false : f.on; }
  }
  $('normalSpawns').onchange = e => { setNormalSpawns(e.target.checked); e.target.blur(); };
  $('spawnZoneEdit').onclick = () => { const id = spawnZonePick; setZonesShown(true); if (id) pickZone(id); };
  for (const f of FAMILIES) {
    const box = $(`spawnShow-${f.id}`);
    if (!box) continue;
    box.onchange = e => { setSpawnFilters({ ...spawnFilters, [f.id]: e.target.checked }); remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); refreshSpawnMarkers(); placeMissionGizmo(); e.target.blur(); };
  }
  syncSpawnFilters();
  // What the install does with spawn points, read as a map opens (spawn-rules.json); the panel says it once it is here
  // The Spawns flyout's "Scripted drop-ins land where placed" (spawns plan, SP8): ticked when the project has the rule;
  // off and greyed, with the reason, where the install plays them where placed already (plain Enemy Within, or a Long War
  // whose loader lacks the drop-in mutator); on a map the install's ExcludeMaps names (the Chryssalid Hive) and no rule,
  // a line says the variant, under a name of its own, loses that. A ticked box stays clickable, to take the rule off.
  function syncSpawnRule() {
    const box = $('dropInsPlaced'), note = $('dropInsNote');
    if (!box || !note) return;
    const on = validSpawnRules(projectSpawnRules), r = spawnRulesData;
    const why = !r ? '' : r.kind === 'ew' ? 'Plain Enemy Within lands scripted drop-ins where they are placed already.'
      : r.dropIns === 'absent' ? 'This install\'s Long War has no drop-in mutator in its loader: scripted drop-ins land where placed already.' : '';
    box.checked = on;
    box.disabled = Boolean(why) && !on;
    box.indeterminate = projectSpawnRules != null && !on;     // a rule this page can't read: saved back as it is
    const lines = [];
    if (why) lines.push(why);
    if (projectSpawnRules != null && !on) lines.push('The project has a spawn rule this editor doesn\'t know; the Build refuses it. Click to take it off.');
    if (!on && !why && r?.excluded) lines.push(`Long War's ExcludeMaps names ${activeMapId}, so it lands its scripted drop-ins where placed; the variant has a name of its own and loses that unless this is ticked.`);
    note.textContent = lines.join(' ');
    note.hidden = !lines.length;
  }
  function setSpawnRule(next) {
    const before = projectSpawnRules;
    if (JSON.stringify(before) === JSON.stringify(next)) return;
    const put = v => { setProjectSpawnRules(v); syncSpawnRule(); spawnPanel(); };
    gizmo.record({ redo: () => put(next), undo: () => put(before) });
    flashHint(next ? 'Scripted drop-ins land where placed: the Build excludes the variant from Long War\'s drop-in mutator' : 'Scripted drop-ins as the install plays them');
  }
  $('dropInsPlaced').onchange = e => setSpawnRule(e.target.checked ? { dropIns: 'placed' } : null);
  function loadSpawnRules() {
    setSpawnRulesData(null);
    if (!spawnsAvailable()) return;
    const id = activeMapId;
    ask(`/maps/${encodeURIComponent(id)}/spawn-rules.json`).then(rules => {
      if (id === activeMapId) { setSpawnRulesData(rules); spawnPanel(); syncSpawnRule(); }
    }).catch(() => {});
  }
  // The piece list's Spawn points kind (18 November 2026: new spawns from the Add panel too): a Pod and a Meld
  // point, each placed with a click as a copy of the map's first plain pod or first Meld point (SP7's copies: the Build
  // clones the template, a pod with a pod index of its own), where the spawn family builds
  function spawnAddEntries() {
    if (!spawnsAvailable() || !spawnFamilyBuilds()) return [];
    const out = [];
    for (const kind of SPAWN_COPY_KINDS) {
      const template = addTemplate(data.spawns, kind);
      if (!template) continue;
      const name = KINDS[kind].label, of = template.fresh ? '' : short(template.actor), volume = kind === 'noSpawn';     // (a fresh volume has no actor: a map with no no-spawn volume of its own)
      out.push({ key: `spawn:${kind}`, id: `spawn-new-${kind}`, spawnAdd: kind, name, kind: 'Spawn points',
                 pkg: template.fresh ? 'made from one of the map\'s volumes' : `a copy of ${of}`,
                 detail: kind === 'pod' ? 'Placed on a tile, with a pod index of its own' : volume ? 'Placed over the tiles round the click; keeps aliens and civilians out'
                   : 'Placed on a tile, with its values',
                 count: (data.spawns ?? []).filter(o => o.kind === kind && !o.landing).length, builds: true,
                 title: volume ? `A new no-spawn volume: click the tile it is to stand over. ${template.fresh ? 'It is 3 by 3 tiles and four levels high, made from one of the map\'s plain volumes'
                   : `It is a copy of ${of}, its size and values`}; the game places no alien or civilian inside it. Move, size, copy, delete and set what it keeps out in the Spawns view`
                   : `A new ${name.toLowerCase()}: click the tile it is to stand on. It is a copy of ${of}, with its values and the way it faces; `
                   + 'move, turn, copy, delete and give it values in the Spawns view',
                 sources: [], pivotIndex: 0, materials: [], milestone: 1, role: null, size: [0, 0, 0], extent: 0, mesh: '',
                 text: `${name} spawn point ${kind === 'pod' ? 'pod aliens enemies' : volume ? 'no spawn volume block keep out aliens civilians' : 'meld canister'}`.toLowerCase() });
    }
    return out;
  }

  // The mission picked changed (the edit hub's mission run, edit_hub.js): the markers and the picked one's gizmo.
  onHub('mission', 'spawns', () => { refreshSpawnMarkers(); placeMissionGizmo(); });
  // A no-spawn volume's box dragged by a face handle (the edit hub's spawn-box run): the markers.
  onHub('spawn-box', 'spawns', () => { refreshSpawnMarkers(); });

  return { baseSpawnOf, bombHelperFix, copySpawn, spawnClip, deleteSpawn, editBaseSpawn, editedCopies,
           editedSpawns, editSpawnCopy, loadSpawnRules, missionFloorLost, missionGizmo, missionGizmoWanted, missionKey,
           missionOverrides, missionProxy, missionReached, moveMissionGroup, NORMAL_SPAWNS, pickSpawnMarker, spawnMarkersAt,
           placeMissionGizmo, placeSpawn, refreshSpawnMarkers, resetBaseSpawn, scaleSpawnMarkers, setMissionMoves,
           setNormalSpawns, setPickedSpawn, setSpawnRule, setSpawnsShown, showSpawn, spawnAddEntries, spawnAt,
           spawnBoxNow, spawnClick, spawnCopyRecords, spawnDeleted, spawnEntry, spawnFamilyBuilds, spawnLayer,
           spawnMovable, spawnPanel, spawnsAvailable, spawnsShown, startSpawnPlacing, stopSpawnPlacing, streamObjects,
           syncSpawnFilters, syncSpawnRule, TURNED_KINDS };
}
