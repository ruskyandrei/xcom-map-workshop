// Copy, paste and placing (refactor stage P8). What is copied is a clip: the selection's pieces, lights, effects and
// floor boxes with their poses and states, a pivot and a name; a paste makes new pieces of it, with links, groups and
// buildings of their own, as one undo step. Here:
// - a clip of the selection (snapshot) and a floor box's matrix in it (boxMatrix, matrixBox);
// - a clip pasted (pasteSnapshot, with its links' tags and groups: linkOf, groupTree, mapChain), Copy and Cut
//   (copySelection) and Paste (paste);
// - placing: a see-through preview of the clip following the cursor (startPlacing, moveGhost, its materials) until a
//   click puts a copy down where it points (dropTarget, with the snap setting's steps; placeMove, moveTo), and stopping
//   (stopPlacing);
// - the Add panel shown and its tab (showPieces, setLibraryScope), and an entry of it chosen and placed: one of this
//   map's pieces, a light, a cover block or a recipe (chooseEntry, entryParts), or one of All maps (chooseLibraryEntry,
//   chooseLibraryEffect);
// - a copy dragged off with Shift on a move handle (copyDragBegin, copyDragEnd);
// - the copy carried to another map or prefab (carried_clip.js: carryCopy as the page leaves, bringCarried on paste,
//   announceCarried as the next page opens);
// - a drawn-only copy of some pieces (previewGroup: the placing preview, the Add panel's thumbnails), and the Add
//   panel's recipes of the areas that make them (pieceRecipes: lights, cover blocks, landing zones, spawn points).
//
// createClipboard takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the scene,
// the pieces' roots made and taken out, the Lights, Effects, Spawns, Landing zones and Buildings views' adding and
// placing, the cover blocks' ground, the templates of other maps' pieces (library_templates.js), the floor boxes'
// outline, the busy mark and the hints. Its own state is inside it (the preview's materials); what other areas read or
// set (the clip, what is being placed, the preview's redraw asked, the Add panel's tab) is
// editor_state.js's.
import * as THREE from 'three';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { LEVEL, PL, QUARTER, TILE } from './constants.js';
import { isFloor } from './cover.js';
import { CARRIED_KEY, CARRIED_TOLD, CARRIED_WORDS, packCarried, unpackCarried } from './carried_clip.js';
import { activeMapId, allRoots, boxesShown, builder, builderMode, buildingMeta, chooseToken, clipboard, copySerial, data, diagonalOn, effectRoots,
         geometryCache, groupIndex, hintTimer, library, libraryScope, lightsShown, nextChooseToken,
         nextCopySerial, ownSet, pickedEffect, pickedSpawn, pieces, placing, pointer, prefabTab, project, roots, setClipboard, setGhostDirty,
         setGroups, setLibraryScopeValue, setPlacing, snapMode, spawnsOn, volumesOn, zonesOn } from './editor_state.js';
import { onHub } from './edit_hub.js';
import { recordName } from './effects_rules.js';
import { makeEffectMarker } from './effects_view.js';
import { actorMatrix, placedPose } from './gizmo.js';
import { makeMarker, paintMarker, valuesOf } from './lights_view.js';
import { fromOf, MADE_KINDS, optionsOf, stateOfRoot } from './piece_records.js';
import { collectPieces } from './pieces.js';
import { buildingKey, groupKey, memberKey, pruneGroups, targetKey, uuid } from './project.js';
import { droppedAcross, stepped, stepsOf } from './snap_steps.js';
import { forgetSession, recallSession, remember, rememberSession } from './storage.js';
import { plural, short, text } from './dom_words.js';

export function createClipboard({ $, actorPose, addedEffect, addedLight, addedObject, addEffectRoots, addLightRoots,
                                  addRoots, askLineCollision, assemblyOf, banner, boundsOf, buildRoots, busy,
                                  BUSY_PIECES, busyStart, cloneGroup, cloneGroups, copyVolumes,
                                  coverEntries, deleteSelection, effectFollows, effectTemplate, effectViewOnly,
                                  flashHint, FLOOR_CLEARANCE, floorSupportOf, ghostEdges, ghostLikeness, ghostLine,
                                  gizmo, gridOrigin, groundAt, groundHeight, groupChain, hoverLikeness,
                                  isForeignTarget, libraryTemplate, lightClip, lightEntries, lightViewOnly,
                                  loaded, madeShape, makeVolume, materialCache, materialKey, memberOf,
                                  memberRecord, newBuildingId, nextFrame, ownerRoot, ownVolumeLayer, partsOf,
                                  pasteVolumes, pick, prefabClip, prefabPlacementProblem, prefabRecords, rayAt, removeEffectRoots,
                                  removeLightRoots, removeRoots, restingHint, sceneChanged, selectionWords,
                                  setLightsShown, setNormalLights, setVolumeBox, spawnAddEntries, startSpawnPlacing,
                                  startZonePlacing, stopSpawnPlacing, stopWallDrawing, stopZonePlacing,
                                  unscaled, volumeBox, volumeCopy, world, zoneEntries, diagonalEntries, startDiagonalPlacing,
                                  stopDiagonalPlacing, zoneClip, spawnClip, markClip, deleteZone, deleteSpawn, deletePicked }) {
  // What the selection is now (moved pieces at their moved pose), with the pivot piece's game location and a name
  // for hints.
  function snapshot(selection = gizmo.selection(), own = ownSet) {
    let list = selection.filter(r => !r.userData.deleted && !r.userData.volume && (r.userData.light ? !lightViewOnly(r.userData.source)
      : r.userData.effect ? !effectViewOnly(r.userData.source, 'copy') && !r.userData.derivedGone
      : !r.userData.source.hidden && !r.userData.source.environment));
    // an effect its piece carries, copied with the piece: the piece's copy carries a copy of it (the Build's carrying),
    // so it isn't copied a second time (effects and sounds plan, Part C)
    list = list.filter(r => !(r.userData.effect && effectFollows(r) && list.includes(ownerRoot(r.userData.source.carriedBy))));
    const boxes = selection.filter(r => r.userData.volume && !r.userData.deleted);
    if (!list.length && !boxes.length && !own.size) return null;
    const pivotRoot = list.includes(allRoots.get(gizmo.active)) ? allRoots.get(gizmo.active) : list[0];
    const name = !pivotRoot ? 'Building' : pivotRoot.userData.light ? short(pivotRoot.userData.source.actor)
      : pivotRoot.userData.effect ? recordName(pivotRoot.userData.source, data) : short(data.meshes[pivotRoot.userData.source.mesh].name);
    // the buildings selected with them: their boxes go along, and a paste makes new buildings of them
    // and the map's own buildings selected with them: their boxes as they are, for a building of the project
    const owns = ownVolumeLayer.children.filter(c => c.userData.own && own.has(c.userData.own.building)).map(c => c.userData.own);
    const ownMatrix = boxMatrix;
    return { volumes: [...boxes.map(r => ({ matrix: r.matrix.clone(), building: r.userData.volume.building, floor: r.userData.volume.floor })),
                       ...owns.map(o => ({ matrix: ownMatrix(o.box), building: `own:${o.building.name}`, floor: o.floor }))],
             buildingMeta: Object.fromEntries([...[...new Set(boxes.map(r => r.userData.volume.building))].map(id => [id, { ...buildingMeta.get(id) }]),
                                               ...[...own].map(b => [`own:${b.name}`, { name: short(b.name), kind: 'building' }])]),
             // (a piece's state: its tint, flags, made numbers and blasts, piece_records.js)
             entries: list.map(r => ({ source: r.userData.source, matrix: r.matrix.clone(),
                                       ...(r.userData.light ? { values: { ...r.userData.values } } : {}),
                                       ...(r.userData.effect && r.userData.values ? { values: structuredClone(r.userData.values) } : {}),
                                       ...(r.userData.light || r.userData.effect ? {} : { state: stateOfRoot(r.userData) }) })),
             pivot: pivotRoot ? placedPose(pivotRoot.userData.source, pivotRoot.matrix).location : (boxes.length ? volumeBox(boxes[0]) : owns[0].box).slice(0, 3), pivotIndex: Math.max(0, list.indexOf(pivotRoot)),
             name: list.length > 1 ? `${name} and ${plural(list.length - 1, 'other piece')}` : name, words: selectionWords(list),
             // a clip of effects and sounds alone (the Effects view's): placed where they were, by the drop's move
             effectsOnly: list.length > 0 && list.every(r => r.userData.effect) && !boxes.length };
  }
  // A floor box as a clip carries it: the matrix that takes a unit cube to the box ([x0, y0, z0, x1, y1, z1], game units).
  const boxMatrix = b => new THREE.Matrix4().makeScale(b[3] - b[0], b[5] - b[2], b[4] - b[1]).setPosition((b[0] + b[3]) / 2, (b[2] + b[5]) / 2, (b[1] + b[4]) / 2);
  const UNIT_BOX = new THREE.Box3(new THREE.Vector3(-0.5, -0.5, -0.5), new THREE.Vector3(0.5, 0.5, 0.5));
  // (and back: the box a clip's volume covers, in game units)
  const matrixBox = matrix => { const b = UNIT_BOX.clone().applyMatrix4(matrix); return [b.min.x, b.min.z, b.min.y, b.max.x, b.max.z, b.max.y]; };
  // New pieces from a snapshot, moved by `delta` (viewer space), as one undo step; they become the selection.
  // Links stay inside the copy: a copied car's body, glass and light bar move with each other, not the original.
  // Each copied actor gets an entity id and an output name of its own: its original's name and a serial of its own. Two
  // pieces copied from one original (two copies of a console, pasted together) must not share a name: a project keeps
  // an actor's pieces together by name, and would merge them into one actor with one pose.
  // The copies of an assembly whose pieces share no prefab (a door's leaf and frame) share a prefab-style tag instead,
  // copy<serial>:<the assembly's pivot>, so they move together as their originals do; a piece without a prefab in an
  // assembly whose other pieces have one (Police Station's standalone light bar) takes theirs.
  // Each set of linked pieces copied gets a tag of its own: two copies of one car pasted together (or two of the same
  // car in a prefab) stay two cars, where one tag would make the editor move them as one. The first set with a tag
  // takes the paste's number, any other a number of its own.
  // A clip's entry can say more than its source does (a prefab's pieces, prefabClip): `unit`, what it is a piece of (two
  // of one original stay two); `link`, its set of linked pieces; `partner`, its partner's unit; `key`, what its group
  // calls it; `tinted`. And the clip its own groups (`groups`: [{ id, breakTogether, members: [key] }]) in place of the
  // map's, and `wrap` ({ id, name, revision } of a prefab): everything placed becomes one group marked with it.
  const linkOf = e => (e.link !== undefined ? e.link : e.source.prefab ?? assemblyOf(e.source)?.tag ?? null);
  // The groups some copied things make: `copied` is [member key, the copy's record] for each, chainOf(key) the groups
  // the original is in from the inside out. The copies form the same tree; a group with fewer than two of its members
  // copied isn't made (its one member stands in its place). A Map id -> group.
  function groupTree(copied, chainOf) {
    const made = new Map(), twin = g => {
      if (!made.has(g.id)) made.set(g.id, { id: uuid(), locked: true, breakTogether: g.breakTogether === true, members: new Map(),
                                            ...(g.prefab ? { prefab: { ...g.prefab } } : {}) });
      return made.get(g.id);
    };
    for (const [key, record] of copied) {
      const chain = chainOf(key);
      if (!chain.length) continue;
      twin(chain[0]).members.set(memberKey(record), record);
      chain.slice(1).forEach((outer, k) => twin(outer).members.set(groupKey(twin(chain[k]).id), { group: twin(chain[k]).id }));
    }
    return pruneGroups(new Map([...made.values()].map(g => [g.id, g])));
  }
  const mapChain = key => groupChain(groupIndex.get(key));
  async function pasteSnapshot(clip, delta, step = null, { whole = false, first = null } = {}) {
    const serial = copySerial + 1;   // the paste's own number, for its prefab groups
    // (the parts of one actor are pasted as one copy; a made piece is one piece on its own, though a room's walls or a
    // look change's pieces share a donor actor: the user's quick Build of 19 November 2026 refused a room saved as one
    // actor naming its donor's component four times, its other walls' numbers lost)
    // (an entry's state: its own when the clip has it, a copy's or a prefab's piece's; else its source's, as a piece of
    // the Add panel or a drawn piece is)
    const stateOfEntry = e => e.state ?? stateOfRoot({ source: e.source });
    const copies = new Map(), unitOf = e => e.unit ?? (MADE_KINDS.has(stateOfEntry(e).generated?.kind) ? e : e.source.actor);
    const keyOf = e => e.key ?? memberOf(e.source);
    const lightEntries = clip.entries.filter(e => e.source.isLight), effectEntries = clip.entries.filter(e => e.source.isEffect);
    clip = { ...clip, entries: clip.entries.filter(e => !e.source.isLight && !e.source.isEffect) };
    for (const e of clip.entries)
      if (!copies.has(unitOf(e))) copies.set(unitOf(e), { name: `${fromOf(e.source).actor}_copy${nextCopySerial()}`, entity: uuid() });
    const tags = new Map(), tagged = new Set();
    const linkTag = e => {
      const was = linkOf(e);
      if (!was) return null;
      if (!tags.has(was)) {
        const tag = was.replace(/^copy\d+:/, '');
        tags.set(was, `copy${tagged.has(tag) ? nextCopySerial() : serial}:${tag}`);
        tagged.add(tag);
      }
      return tags.get(was);
    };
    const lights = lightEntries.map(e => addedLight(e.source, delta.clone().multiply(e.matrix), e.values));
    const effects = effectEntries.map(e => addedEffect(e.source, delta.clone().multiply(e.matrix), null, null, e.values));
    // the copied buildings: each a new building with the same floors, its boxes moved (and turned) as the pieces are
    const twins = new Map(), names = new Set([...buildingMeta.values()].map(m => m.name));
    const boxes = (clip.volumes ?? []).map(v => {
      if (!twins.has(v.building)) {
        // (a prefab's building keeps its name; a copy's says it is one)
        const meta = clip.buildingMeta?.[v.building] ?? {}, base = (clip.wrap ? meta.name || 'Building' : `${meta.name || 'Building'} copy`).slice(0, 56);
        let name = base;
        for (let n = 2; names.has(name); n++) name = `${base} ${n}`;
        names.add(name);
        twins.set(v.building, { id: newBuildingId(), meta: { name, kind: meta.kind ?? 'building',
                                                             ...(meta.cursorFloors === true && !meta.map ? { cursorFloors: true } : {}) } });
      }
      const root = makeVolume([0, 0, 0, TILE, TILE, LEVEL], twins.get(v.building).id, v.floor);
      root.matrix.copy(delta.clone().multiply(v.matrix));
      setVolumeBox(root, volumeBox(root));
      root.userData.deleted = true;
      return root;
    });
    const objs = clip.entries.map(e => {
      const { source, matrix } = e, placed = delta.clone().multiply(matrix), copy = copies.get(unitOf(e));
      return addedObject(source, placed, optionsOf({ actor: copy.name, id: copy.entity, ...actorPose(source, placed),
        prefab: linkTag(e),
        partner: copies.get(e.partner !== undefined ? e.partner : source.partner)?.name ?? null }, 'piece', stateOfEntry(e)));
    });
    // (giving way by time, so that the busy mark keeps turning through a large paste and a small one never waits)
    // A piece that can't be drawn (its mesh, a material or a texture not had) is left out, all its parts, and the hint
    // says so (review finding 29); the rest is placed.
    const failed = [], made = await buildRoots(objs, step, failed);
    const lost = new Set(failed.map(f => f.obj.actor)), built = made.filter(r => !lost.has(r.userData.source.actor));
    if (failed.length) {
      for (const f of failed) console.error(f.obj.actor, f.error);
      flashHint(`${plural(lost.size, 'piece')} of ${clip.name ?? 'the copy'} could not be drawn, so ${lost.size === 1 ? 'it is' : 'they are'} not placed: `
        + `${failed[0].error?.message ?? failed[0].error}`);
    }
    // A copied group stays a group, and so do the groups it is in and the ones inside it (groupTree), each with its
    // options as the original has them. A prefab's clip brings its own groups.
    // (each copied member's key, and its copy's record: pieces, lights and buildings)
    const copied = [...clip.entries.filter(e => !lost.has(copies.get(unitOf(e)).name)).map(e => [keyOf(e), { added: copies.get(unitOf(e)).name }]),
                    ...lightEntries.map((e, k) => [keyOf(e), memberRecord(lights[k].userData.source)]),
                    ...effectEntries.map((e, k) => [keyOf(e), memberRecord(effects[k].userData.source)]),
                    ...[...twins].map(([was, t]) => [buildingKey(was), { building: t.id }])];
    let chainOf = mapChain;
    if (clip.groups) {
      const holder = new Map();
      for (const g of clip.groups) for (const k of g.members) holder.set(k, g);
      chainOf = key => { const out = []; for (let g = holder.get(key); g && out.length < 64; g = holder.get(groupKey(g.id))) out.push(g); return out; };
    }
    const tree = groupTree(copied, chainOf);
    if (clip.wrap) {
      // a placed prefab is one group: what stands free of the groups made (pieces and groups) is held by a new one,
      // marked with the prefab it came from; a prefab that is one group already has that one marked
      const inner = new Set([...tree.values()].flatMap(g => [...g.members.keys()])), top = new Map();
      for (const [, record] of copied) if (!inner.has(memberKey(record))) top.set(memberKey(record), record);
      for (const g of tree.values()) if (!inner.has(groupKey(g.id))) top.set(groupKey(g.id), { group: g.id });
      const only = top.size === 1 ? [...top.values()][0].group : null;
      if (top.size >= 2) { const id = uuid(); tree.set(id, { id, locked: true, breakTogether: false, prefab: { ...clip.wrap }, members: top }); }
      else if (only) tree.get(only).prefab = { ...clip.wrap };
    }
    const newGroups = [...tree.values()];
    // (what it gives back says how many pieces it left out and why: `lost`, `why`, so a caller's own hint can say so;
    // `stopped`: its `first` said no)
    Object.assign(built, { lost: lost.size, why: failed[0] ? failed[0].error?.message ?? String(failed[0].error) : null });
    // whole: all or nothing; first(): run after the pieces are made and just before the paste is recorded (a look
    // change's delete), false to place nothing (setMadeLook)
    if (whole && lost.size) return built;
    if (first && first() === false) return Object.assign(built, { stopped: true });
    const before = gizmo.picks(), ids = [...built.map(r => r.userData.source.id), ...lights.map(r => r.userData.source.id),
                                         ...effects.map(r => r.userData.source.id),
                                         ...(boxesShown ? boxes.map(r => r.userData.source.id) : [])];
    if (!built.length && !lights.length && !effects.length && !boxes.length) return built;     // (nothing could be placed)
    gizmo.record({
      size: built.length,
      redo: () => {
        addRoots(built); addLightRoots(lights); addEffectRoots(effects);
        for (const r of boxes) r.userData.deleted = false;
        for (const { id, meta } of twins.values()) buildingMeta.set(id, { ...meta });
        if (newGroups.length) { const next = cloneGroups(); for (const g of newGroups) next.set(g.id, cloneGroup(g)); setGroups(next); }
        gizmo.setSelection(ids, ids[Math.min(clip.pivotIndex, ids.length - 1)]); sceneChanged();
      },
      undo: () => {
        removeRoots(built); removeLightRoots(lights); removeEffectRoots(effects);
        for (const r of boxes) r.userData.deleted = true;
        // (the copied buildings' names go with them, so the next paste isn't named "copy 2": review finding 34)
        for (const { id } of twins.values()) buildingMeta.delete(id);
        if (newGroups.length) { const next = cloneGroups(); for (const g of newGroups) next.delete(g.id); setGroups(next); }
        gizmo.setSelection(before.ids, before.active, before.loose); sceneChanged();
      },
    });
    return built;
  }
  // A landing zone, a spawn point or diagonal cover marks picked (they are no selection of the gizmo's): copied as a
  // clip of their own kind, the one clipboard's (Ctrl+C, Ctrl+X, a zone panel's Copy); Ctrl+V places it with its
  // view's own placing (pasteThing). False where none is picked.
  function copyThing(cut = false) {
    // (a piece selected is the copy, whatever was left picked in a view)
    const clip = gizmo.selection().length ? null : zonesOn ? zoneClip() : spawnsOn || pickedSpawn ? spawnClip() : diagonalOn ? markClip() : null;
    if (!clip) return false;
    if (clip.why) { flashHint(`It isn't copied: ${clip.why}`); return true; }
    setClipboard({ ...clip, copied: true });
    if (cut) { if (clip.thing === 'zone') deleteZone(); else if (clip.thing === 'spawn') deleteSpawn(pickedSpawn); else deletePicked(); }
    flashHint(`${cut ? 'Cut' : 'Copied'} ${clip.name} · Ctrl+V to place a copy`);
    return true;
  }
  function pasteThing(clip) {
    stopPlacing(); stopWallDrawing();
    if (clip.thing === 'zone') { stopSpawnPlacing(); stopDiagonalPlacing(); startZonePlacing(clip.zone); }
    else if (clip.thing === 'spawn') { stopZonePlacing(); stopDiagonalPlacing(); startSpawnPlacing(null, clip); }
    else { stopZonePlacing(); stopSpawnPlacing(); startDiagonalPlacing(clip.marks); }
  }
  function copySelection(cut = false) {
    if (volumesOn) { copyVolumes(cut); return; }
    if (copyThing(cut)) return;
    const clip = snapshot();
    if (!clip) {
      // (a view-only effect is picked but no selection takes it in: the picked one says why)
      const fx = gizmo.selection().find(r => r.userData.effect) ?? effectRoots.get(pickedEffect);
      flashHint(fx ? `It isn't copied: ${effectViewOnly(fx.userData.source, 'copy') ?? 'it is deleted'}` : 'Select a piece, light or floor box to copy');
      return;
    }
    // (a copy: what the tab carries to another map or prefab, carryCopy)
    setClipboard({ ...clip, copied: true });
    const made = new Set(clip.volumes.map(v => v.building)).size;
    if (cut) deleteSelection(true);
    flashHint(`${cut ? 'Cut' : 'Copied'} ${clip.words}${made ? ` and ${plural(made, 'building')}` : ''} · Ctrl+V to place a copy`);
  }
  // Where a paste or placement puts the pivot piece: the point under the screen point `at` (on a piece, or else
  // level with where it was copied from), in game units, or null. Across the floor it moves from where the piece
  // stands in the map in the snap setting's steps (snap_steps.js: fine 24, tile whole tiles), so a piece keeps its
  // offset from the grid; with snap off it goes where the cursor is. A floor piece is placed as any piece is (Align to
  // level puts it on its levels: align.js).
  function dropTarget(clip, at) {
    if (!at) return null;
    let point = pick(...at)?.point;
    // over nothing: on the ground grid's plane on a map (Clear map plan, section 3), else level with where it was copied
    const plane = !builderMode && data?.scope === 'map' && !data.preview && data.tileGrid?.origin ? groundHeight() : clip.pivot[2];
    if (!point) point = rayAt(...at).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -plane), new THREE.Vector3());
    if (!point) return null;
    let [x, y, z] = [point.x, point.z, point.y];
    const [px, py] = clip.pivot;
    // a prefab with a building goes by whole tiles and levels, whatever the snap (a building's box is one of the tile
    // grid): its pivot is a tile corner at ground level
    if (clip.gridLocked) return [px + Math.round((x - px) / TILE) * TILE, py + Math.round((y - py) / TILE) * TILE, clip.pivot[2] + Math.round((z - clip.pivot[2]) / LEVEL) * LEVEL];
    [x, y] = droppedAcross([x, y], [px, py], snapMode);
    // a prefab from the library (its pivot on the tile grid's base): up and down in the snap's steps from there too, so
    // its pieces with a pose rule keep their height on the grid under a snap; snap off, as picked
    if (clip.wrap && stepsOf(snapMode).up) z = clip.pivot[2] + stepped(z - clip.pivot[2], stepsOf(snapMode).up);
    // a light from the Add panel: at its template's height above what is under the cursor
    if (clip.lightHeight != null) z += clip.lightHeight;
    // an invisible floor from the Add panel: its top just over the ground at the centre of the tile under its pivot (its
    // first tile's), where the game looks for that tile's floor and the panel measures (floorCentres), whatever the snap:
    // with snap off the pivot stands anywhere in that tile, and the ground there can be a kerb's height off
    if (clip.groundFloor) {
      const o = gridOrigin(), at = o ? [0, 1].map(k => o[k] + TILE * Math.floor(([x, y][k] - o[k]) / TILE) + TILE / 2) : [x, y];
      const g = groundAt(at[0], at[1], z + 96); if (g != null) z = g + FLOOR_CLEARANCE;
    }
    return [x, y, z];
  }
  // The move (viewer space) that takes the clip's pivot to a game location, turned by quarter turns about the pivot
  // (R while placing). Game (x, y, z up) is viewer (x, z, y).
  const moveTo = (clip, [x, y, z], turns = 0) => new THREE.Matrix4().makeTranslation(x, z, y)
    .multiply(actorMatrix([0, 0, 0], [0, turns * QUARTER, 0]))
    .multiply(new THREE.Matrix4().makeTranslation(-clip.pivot[0], -clip.pivot[2], -clip.pivot[1]));
  // The move that places a clip: moveTo. (A ladder, door, car, van or fracturing piece placed under tile snap from a
  // pose on its rule stays on it; Align to game pose puts one on it: the custom geometry improvements plan, D4.)
  const placeMove = (clip, target, turns) => moveTo(clip, target, turns);
  // Paste (Ctrl+V) places what was copied: a preview follows the cursor until a click puts it down. While placing,
  // Ctrl+V puts it down under the cursor, as a click does.
  function paste() {
    if (placing) { if (pointer) placeAt(pointer, false); return; }
    if (volumesOn) { pasteVolumes(); return; }
    if (!clipboard) { void bringCarried(); return; }
    if (clipboard.thing) { pasteThing(clipboard); return; }
    // a large copy's preview takes a moment to make: the busy mark meanwhile
    if (clipboard.entries.length >= BUSY_PIECES) {
      const clip = clipboard;
      busy(`Getting ${plural(clip.entries.length, 'piece')} ready to place…`, () => { startPlacing(clip); return nextFrame(); }, { now: true });
      return;
    }
    startPlacing(clipboard);
  }

  // (walls, floors, roofs and ground are drawn from the Build menu on the Add button, no longer listed here: B1)
  const pieceRecipes = () => [...lightEntries(), ...coverEntries(), ...zoneEntries(), ...spawnAddEntries(), ...diagonalEntries()];
  // A drawn-only copy of some pieces (the placing preview, a piece-list thumbnail) from the loaded meshes and
  // materials, or `override` for every part. It is never picked. parts: { source, matrix }; `frame` moves them all.
  // (The clipboard's: it falls back on the clipboard's ghost material.)
  function previewGroup(parts, override, frame) {
    const group = new THREE.Group();
    for (const { source, matrix: placed, values, state } of parts) {
      // (a made piece of a prefab, its donor's source and its numbers: drawn from its made mesh once loaded, prefabClip)
      const made = state?.generated && !data.meshes[source.mesh]?.made ? madeShape(source, state.generated) : null;
      const drawn = made?.mesh && loaded(geometryCache, made.mesh) ? made : null, matrix = drawn ? unscaled(placed) : placed;
      if (source.isEffect) {
        const holder = new THREE.Group(), marker = makeEffectMarker(source);
        holder.add(marker); holder.matrix.multiplyMatrices(frame, matrix); holder.matrixAutoUpdate = false;
        group.add(holder);
        ghostLikeness(holder, source);
        continue;
      }
      if (source.isLight) {
        const holder = new THREE.Group(), marker = makeMarker(source.kind);
        paintMarker(marker, values ?? valuesOf(source));
        marker.scale.setScalar(24); holder.add(marker);
        holder.matrix.multiplyMatrices(frame, matrix); holder.matrixAutoUpdate = false;
        group.add(holder);
        continue;
      }
      const mesh = drawn?.mesh ?? source.mesh, materials = drawn?.materials ?? source.materials, gltf = loaded(geometryCache, mesh);
      if (!gltf) continue;
      const root = data.meshes[mesh].kind === 'skeletal' ? cloneSkeleton(gltf.scene) : gltf.scene.clone(true);
      let i = 0;
      root.traverse(part => {
        if (!part.isMesh) return;
        part.material = override ?? loaded(materialCache, materialKey(source, materials[i])[0]) ?? ghostMaterial;
        part.raycast = () => {}; i++;
      });
      root.matrix.multiplyMatrices(frame, matrix); root.matrixAutoUpdate = false;
      group.add(root);
    }
    return group;
  }

  // Placing, for paste and the piece list: a see-through preview of the clip follows the cursor, a click places a
  // copy there (Shift+click keeps placing), Escape stops. The gizmo is held meanwhile, so a click never grabs a handle.
  // (ghostDirty, what is being placed, placing, and pieces: editor_state.js)
  // The preview is drawn twice: plainly where it is in view, faintly where walls or roofs hide it.
  const ghostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.45, depthWrite: false });
  const ghostHidden = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.15, depthWrite: false, depthTest: false });
  // (libraryScope, the All maps library, library, and chooseToken: editor_state.js)
  const LIBRARY_SCOPES = { map: 'libFilter', all: 'libAllFilter', prefabs: 'prefabFilter' };
  function setLibraryScope(scope) {
    setLibraryScopeValue(LIBRARY_SCOPES[scope] ? scope : 'map');
    remember('workshop.libraryScope', libraryScope);
    $('libScope').value = libraryScope;
    $('libMap').hidden = libraryScope !== 'map';
    // (This prefab, the builder's first tab, lists the prefab as it is now)
    if (builderMode && pieces.open && libraryScope === 'map') pieces.show(true, pieceEntries, true);
    library.show(pieces.open && libraryScope === 'all');
    prefabTab.show(pieces.open && libraryScope === 'prefabs');
    if (libraryScope !== 'all') hoverLikeness(null);
    if (placing?.entry) stopPlacing();
    if (pieces.open) $(LIBRARY_SCOPES[libraryScope]).focus({ preventScroll: true });
  }
  // An entry of All maps: its piece read (exported by the server the first time), then placed as a copy is.
  async function chooseLibraryEntry(entry) {
    const token = nextChooseToken();
    if (!entry) { stopPlacing(); return; }
    if (entry.effect) { chooseLibraryEffect(entry, token); return; }
    let template;
    if (!isForeignTarget({ ...entry.source, level: 'base' })) {
      // the map's own piece: a copy of it, as from This map
      const sources = partsOf(targetKey({ package: data.name, level: 'base', actor: `${PL}${entry.source.actor}` }));
      if (!sources.length) { flashHint(`${entry.name} is not in this export of the map`); return; }
      template = { sources, pivotIndex: 0 };
    } else {
      flashHint(`Reading ${entry.name} from ${entry.source.package}…`);
      const done = busyStart(`Reading ${entry.name} from ${entry.source.package}…`);
      try { template = await libraryTemplate(entry.source); }
      catch (error) { if (token === chooseToken) flashHint(`${entry.name} could not be placed: ${error.message}`); return; }
      finally { done(); }
      if (token !== chooseToken || !pieces.open || libraryScope !== 'all') return;
    }
    const { sources, pivotIndex } = template;
    setClipboard({ entries: sources.map(source => ({ source, matrix: new THREE.Matrix4().fromArray(source.matrix) })),
                  pivot: [...sources[pivotIndex].location], pivotIndex, name: entry.name, libraryEntry: entry });
    startPlacing(clipboard, entry);
  }
  // An effect, sound or lens flare of All maps (effects and sounds plan, stage FX4): this map's own copied as the Effects view's
  // Ctrl+C copies it, another map's read from it (effectTemplate); then placed as a copied effect is.
  async function chooseLibraryEffect(entry, token) {
    let source;
    if (!isForeignTarget({ ...entry.source, level: 'base' })) {
      source = [...effectRoots.values()].map(r => r.userData.source)
        .find(o => !o.added && o.layer === 'base' && short(o.actor) === entry.source.actor);
      if (!source) { flashHint(`${entry.name} is not in this export of the map`); return; }
    } else {
      flashHint(`Reading ${entry.name} from ${entry.source.package}…`);
      const done = busyStart(`Reading ${entry.name} from ${entry.source.package}…`);
      try { source = await effectTemplate(entry.source); }
      catch (error) { if (token === chooseToken) flashHint(`${entry.name} could not be placed: ${error.message}`); return; }
      finally { done(); }
      if (token !== chooseToken || !pieces.open || libraryScope !== 'all') return;
    }
    if (effectViewOnly({ ...source, added: true }, 'copy')) { flashHint(`${entry.name} can't be placed: ${effectViewOnly({ ...source, added: true }, 'copy')}`); return; }
    setClipboard({ entries: [{ source, matrix: new THREE.Matrix4().fromArray(source.matrix) }], pivot: [...source.location], pivotIndex: 0,
                  name: entry.name, libraryEntry: entry });
    startPlacing(clipboard, entry);
  }
  // The Add panel's first tab: This map, the map's pieces as exported; in the prefab builder This prefab, the pieces the
  // prefab holds now, each where it stands with its state (S19). Floor pieces are marked (the Kind menu's Floors, and a
  // search for "floor" finds them).
  // (an added piece's source as it stands: its matrix and pose where it was moved to, so its row's picture and copy are
  // the piece as it is)
  const liveSource = r => ({ ...r.userData.source, matrix: r.matrix.toArray(), ...placedPose(r.userData.source, r.matrix) });
  const pieceEntries = () => collectPieces({ roots, data, frameOf: s => actorMatrix(s.location, s.rotation).invert(), boundsOf,
    ...(builderMode ? { groups: gizmo.linkedGroups([...roots.values()].filter(r => r.userData.source.added)), live: liveSource }
                    : { groups: gizmo.linkedGroups([...roots.values()].filter(r => !r.userData.source.added)) }) })
    .map(e => (floorSupportOf(e.sources) != null ? Object.assign(e, { floor: true, text: `${e.text} floor` }) : e))
    .concat(pieceRecipes());
  // The Add panel made large (its maximise button): over most of the view, each tab's pieces as cards with large
  // pictures, as the look picker shows looks. Back to its size by the button again, Esc, a row chosen (so the click
  // that places it falls in the view) or the panel shut.
  let large = false;
  function setAddLarge(on) {
    large = Boolean(on) && pieces.open;
    $('library').classList.toggle('large', large);
    const button = $('libraryLarge');
    button.setAttribute('aria-pressed', String(large)); button.setAttribute('aria-label', large ? 'Back to its size' : 'Larger');
    button.title = large ? 'Back to its size (Esc)' : 'Larger: the panel over most of the view, the pieces as cards with large pictures (a click on one, or Esc, brings it back to its size)';
    button.querySelector('use').setAttribute('href', large ? '#i-restore' : '#i-maximise');
    pieces.setLarge(large); library.setLarge(large);
  }
  function showPieces(on) {
    if (!on && large) setAddLarge(false);
    $('libMap').hidden = libraryScope !== 'map';
    library.show(on && libraryScope === 'all');
    prefabTab.show(on && libraryScope === 'prefabs');
    pieces.show(on, pieceEntries, builderMode);
    if (!on && placing?.entry) stopPlacing();
    if (!on) stopWallDrawing();
    // the hover pane goes with the panel or its All maps tab (closed with the pointer still on a row, it stayed)
    if (!on || libraryScope !== 'all') hoverLikeness(null);
    $('editAdd').classList.toggle('on', on); $('editAdd').setAttribute('aria-pressed', on);
  }
  // The parts of a piece-list entry where the map has them (This prefab's: where the prefab has them, each with its
  // state).
  const entryParts = entry => entry.sources.map((source, k) => ({ source, matrix: new THREE.Matrix4().fromArray(source.matrix),
                                                                 ...(entry.states ? { state: entry.states[k] } : {}) }));
  // Choosing an entry puts it on the clipboard and places it; choosing it again (null) stops.
  function chooseEntry(entry) {
    nextChooseToken();
    if (entry && large) setAddLarge(false);
    if (!entry) { stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopDiagonalPlacing(); stopWallDrawing(); return; }
    stopWallDrawing(); stopDiagonalPlacing();
    if (entry.zone) { stopPlacing(); stopSpawnPlacing(); startZonePlacing(); return; }      // the Landing zones kind
    if (entry.spawnAdd) { stopPlacing(); stopZonePlacing(); startSpawnPlacing(entry.spawnAdd); return; }      // Spawn points
    if (entry.diagonal) { stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); startDiagonalPlacing(); return; }     // Diagonal cover
    if (entry.light) {    // the Lights kind's Point Light and Spot Light
      const clip = lightClip(entry.light);
      if (!clip) return;
      if (!lightsShown) { if (volumesOn) setLightsShown(true); else setNormalLights(true); }
      setClipboard(clip);
      startPlacing(clip, entry);
      return;
    }
    // a cover block is placed by its first tile: the centre of the tile at its corner goes under the cursor
    const at = entry.sources[entry.pivotIndex].location;
    // (a row of This prefab is a piece, not the groups it stands in: its copy is in none)
    setClipboard({ entries: entryParts(entry), pivot: entry.cover ? [at[0] + 48, at[1] + 48, at[2]] : [...at],
                  pivotIndex: entry.pivotIndex, name: entry.name, groundFloor: isFloor(entry.cover),
                  ...(entry.inPrefab ? { groups: [] } : {}) });
    if (clipboard.groundFloor) askLineCollision();     // the ground's collision on its way before the floor goes down
    startPlacing(clipboard, entry);
  }
  // The floor boxes that come with a clip (a building copied, a prefab's), as outlines added to `group`: the preview
  // placed and a copy's stand-in show them alike.
  function addBoxOutlines(group, clip) {
    for (const v of clip.volumes ?? []) {
      const line = new THREE.LineSegments(ghostEdges, ghostLine);
      line.matrix.copy(v.matrix); line.matrixAutoUpdate = false; line.raycast = () => {};
      group.add(line);
    }
  }
  function startPlacing(clip, entry = null) {
    stopPlacing(); stopWallDrawing();
    if (entry && large) setAddLarge(false);       // (an Add panel row: the click that places it falls in the view)
    // a floor piece snaps by levels (dropTarget): its saved floor's height over its pivot
    clip.floor = clip.prefab || clip.entries.some(e => e.source.isLight || e.source.isEffect) ? null : floorSupportOf(clip.entries.map(e => e.source));
    const ghost = new THREE.Group(), here = new THREE.Matrix4();
    ghost.add(previewGroup(clip.entries, ghostHidden, here), previewGroup(clip.entries, ghostMaterial, here));
    addBoxOutlines(ghost, clip);
    ghost.visible = false; ghost.matrixAutoUpdate = false; world.add(ghost);
    setPlacing({ clip, entry, ghost, turns: 0 }); setGhostDirty(true);
    gizmo.hold(true); pieces.setChosen(entry); library.setChosen(entry); prefabTab.setChosen(entry); restingHint();
  }
  function stopPlacing() {
    if (!placing) return;
    world.remove(placing.ghost);
    placing.ghost.traverse(part => part.isSkinnedMesh && part.skeleton.dispose());
    setPlacing(null); gizmo.hold(false); pieces.setChosen(null); library.setChosen(null); prefabTab.setChosen(null);
    clearTimeout(hintTimer); restingHint();
  }
  // The preview sits where a click would place the piece; it hides when the cursor is off the view.
  function moveGhost() {
    setGhostDirty(false);
    const target = dropTarget(placing.clip, pointer);
    placing.ghost.visible = Boolean(target);
    if (target) { placing.ghost.matrix.copy(placeMove(placing.clip, target, placing.turns)); placing.ghost.matrixWorldNeedsUpdate = true; }
  }
  async function placeAt(at, keep) {
    const { clip, turns } = placing, target = dropTarget(clip, at);
    if (!target) return;
    const delta = placeMove(clip, target, turns);
    // (a warning, not a refusal: plan "sturdier prefabs", R7; the Build's stage-outside says the same)
    const problem = prefabPlacementProblem(clip, delta);
    if (!keep) stopPlacing();
    // (a paste that fails says why: placeAt is called without waiting for it, by a click or Ctrl+V)
    let placed;
    try {
      placed = clip.entries.length >= BUSY_PIECES
        ? await busy(`Placing ${clip.prefab ? clip.name : 'the copy'}: pieces made`, step => pasteSnapshot(clip, delta, step), { total: clip.entries.length, now: true })
        : await pasteSnapshot(clip, delta);
    } catch (error) { console.error(error); flashHint(`${clip.name ?? 'The copy'} could not be placed: ${error?.message ?? error}`); return; }
    if (clip.libraryEntry) library.used(clip.libraryEntry);     // it heads the recently used pieces
    if (problem) banner(problem, [['Undo', () => gizmo.undo()]]);
    if (!keep && !placed?.lost) flashHint(`Placed ${clip.name} · Ctrl+V places another`);
  }
  // Shift held as a move handle is taken (an axis or a plane): the drag moves a copy along it (the gizmo's copyDrag).
  // The selection itself is what moves under the cursor, with the snaps of any drag, and a drawn-only stand-in keeps
  // its place; on release the selection is back where it was and the copy is pasted where it was dragged to, as any
  // paste is (one undo step, the copy selected). Escape, or a drag that went nowhere, makes no copy.
  // In the Buildings view the boxes picked are copied into their own buildings on their own floors (boxCopy).
  function copyDragBegin() {
    if (placing) return null;
    if (volumesOn) return boxCopyBegin();
    const clip = snapshot();
    if (!clip) return null;
    const stand = new THREE.Group(), here = new THREE.Matrix4();
    stand.add(previewGroup(clip.entries, null, here));
    addBoxOutlines(stand, clip);
    stand.matrixAutoUpdate = false; world.add(stand);
    const hint = $('dragHint');
    hint.hidden = false;
    hint.replaceChildren(`Moving a copy of ${clip.name} · `);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
    return { clip, stand };
  }
  // The Buildings view's Shift+drag: the picked boxes, their stand-ins' outlines where they are
  function boxCopyBegin() {
    const boxes = gizmo.selection().filter(r => r.userData.volume && !r.userData.deleted);
    if (!boxes.length) return null;
    const clip = { volumes: boxes.map(r => ({ matrix: r.matrix.clone(), building: r.userData.volume.building, floor: r.userData.volume.floor })) };
    const stand = new THREE.Group();
    addBoxOutlines(stand, clip);
    stand.matrixAutoUpdate = false; world.add(stand);
    const hint = $('dragHint');
    hint.hidden = false;
    hint.replaceChildren(`Moving a copy of ${boxes.length === 1 ? 'the box' : `${boxes.length} boxes`} · `);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
    return { boxes: clip.volumes, stand };
  }
  // ...and on release: a copy of each where the drag ended, in its own building and floor, picked; one undo step
  function boxCopyEnd({ boxes, stand }, delta) {
    world.remove(stand);
    if (!delta) return;
    const made = boxes.map(v => {
      const root = makeVolume([0, 0, 0, TILE, TILE, LEVEL], v.building, v.floor);
      root.matrix.copy(delta.clone().multiply(v.matrix));
      setVolumeBox(root, volumeBox(root));
      root.userData.deleted = true;
      return root;
    });
    const ids = made.map(r => r.userData.source.id), before = gizmo.picks();
    gizmo.record({
      redo: () => { for (const r of made) r.userData.deleted = false; gizmo.setSelection(ids); sceneChanged(); },
      undo: () => { for (const r of made) r.userData.deleted = true; gizmo.setSelection(before.ids, before.active, before.loose); sceneChanged(); },
    });
    flashHint(`Copied ${made.length === 1 ? 'the box' : `${made.length} boxes`} into ${made.length === 1 ? 'its building, on its floor' : 'their buildings, on their floors'}`);
  }
  async function copyDragEnd(token, delta) {
    if (token.boxes) { boxCopyEnd(token, delta); return; }
    const { clip, stand } = token;
    try {
      const placed = delta && clip.entries.length >= BUSY_PIECES
        ? await busy('Placing the copy: pieces made', step => pasteSnapshot(clip, delta, step), { total: clip.entries.length, now: true })
        : delta ? await pasteSnapshot(clip, delta) : null;
      if (placed?.lost) delta = null;      // (its hint says what was left out)
    } catch (error) {
      console.error(error); flashHint(`The copy of ${clip.name} could not be placed: ${error?.message ?? error}`); delta = null;
    } finally {
      // (the stand-in goes once the copy's original is drawn in its place again)
      world.remove(stand);
      stand.traverse(part => part.isSkinnedMesh && part.skeleton.dispose());
    }
    if (delta) flashHint(`Copied ${clip.name}`);
  }

  // ---- The copy carried to another map or prefab (Discord S17; carried_clip.js). What Ctrl+V would place, when it is a
  // copy (Ctrl+C or Ctrl+X: pieces, lights, effects, sounds, flares and buildings; and the Buildings view's boxes), is
  // packed as the page leaves for another map or prefab (document_session.js goTo) and kept by the tab, for the tab
  // alone. Ctrl+V there, with nothing copied of its own, brings it: its pieces read as the Add panel's All maps reads
  // another map's, the destination's own pieces its own again, what can't be had said. An Add panel entry or a prefab
  // chosen last is not carried (a click away in any map), and the tab then carries nothing; with nothing on the
  // clipboard, what the tab carries stays for the next map.
  function carryCopy() {
    const boxes = volumeCopy(), live = clipboard?.copied ? clipboard : null;
    // (a landing zone or diagonal cover marks: plain data, the zone's place from the tile grid's corner; a spawn point is
    // a copy of the map's own actor, and stays in its map)
    if (live?.thing) {
      const o = gridOrigin() ?? [0, 0, 0], id = uuid();
      // (a zone's height may be unset: the ground's)
      const thing = live.thing === 'zone' ? { kind: 'zone', zone: { ...live.zone, location: live.zone.location.map((v, k) => (v == null ? null : v - (o[k] ?? 0))) } }
        : live.thing === 'marks' ? { kind: 'marks', marks: live.marks } : null;
      if (!thing && !boxes) { forgetSession(CARRIED_KEY); return; }
      rememberSession(CARRIED_KEY, packCarried({ id, name: live.name, from: { map: activeMapId ?? null }, pivot: [0, 0, 0], boxes, ...(thing ? { thing } : {}) }).text);
      return;
    }
    if (!live && !boxes) { if (clipboard) forgetSession(CARRIED_KEY); return; }
    // (the copy brought here and not copied again: carried on as it came)
    if (live?.carried && !boxes) { rememberSession(CARRIED_KEY, live.carried); return; }
    // (the copy's records as a prefab's, its pivot in their space: prefab_place.js, run on the clip's own entries)
    const records = live ? prefabRecords({ clip: live }) : null, pivotEntry = live?.entries[live.pivotIndex], id = uuid();
    const name = live?.name ?? (boxes.length === 1 ? 'The floor box' : 'The floor boxes');
    const packed = packCarried({ id, name, words: live?.words ?? '',
      from: { map: activeMapId ?? data?.name ?? null, prefab: builderMode ? builder.doc?.id ?? null : null, project: project?.doc?.id ?? null },
      pivot: records ? live.pivot.map((v, k) => v - records.base[k]) : [0, 0, 0],
      pivotActor: records && pivotEntry ? records.names.get(pivotEntry.source.actor) ?? null : null,
      pieces: records?.pieces, groups: records?.groups, buildings: records?.buildings, donors: records?.donors, left: records?.left, boxes });
    // (too large for the tab's storage: a marker, which says so on arrival)
    if (!(packed.text && rememberSession(CARRIED_KEY, packed.text))) rememberSession(CARRIED_KEY, packed.tooLarge ?? packCarried({ id, name }, 0).tooLarge);
  }
  // Ctrl+V with nothing copied in this page: the copy the tab carried from the last map or prefab, made into a clip
  // (prefab_place.js prefabClip, as a copy's: no group round it, held by its own pivot) and placed as any copy is. The
  // first time its pieces are read from the game's maps, under the busy mark; the clip made is the page's own then, so
  // the next Ctrl+V is at once.
  async function bringCarried() {
    const text = recallSession(CARRIED_KEY), carried = unpackCarried(text);
    if (carried?.error) { flashHint(carried.error); return; }
    if (carried?.tooLarge !== undefined) { flashHint(CARRIED_WORDS.tooLarge(carried.tooLarge)); return; }
    const doc = carried?.doc;
    // (a landing zone or marks carried: the clip of their kind again, on this map's grid, placed by its view)
    if (doc?.thing?.kind === 'zone' || doc?.thing?.kind === 'marks') {
      const o = gridOrigin() ?? [0, 0, 0];
      setClipboard(doc.thing.kind === 'zone' ? { thing: 'zone', name: doc.name, copied: true, zone: { ...doc.thing.zone, location: doc.thing.zone.location.map((v, k) => (v == null ? null : v + (o[k] ?? 0))) } }
        : { thing: 'marks', name: doc.name, copied: true, marks: doc.thing.marks });
      pasteThing(clipboard);
      return;
    }
    if (!doc || (!doc.pieces.length && !doc.buildings.length)) {
      flashHint(doc?.boxes?.length ? 'The copy is floor boxes: Ctrl+V places them in the Buildings view (Shift+B)' : 'Nothing copied yet: select a piece and press Ctrl+C');
      return;
    }
    const token = nextChooseToken();
    let clip;
    try {
      clip = await busy(`Bringing ${doc.name}: pieces read`, step => prefabClip(doc, step, { plain: { pivot: doc.pivot, pivotActor: doc.pivotActor } }), { now: true });
    } catch (error) { console.error(error); flashHint(`${doc.name} could not be brought here: ${error?.message ?? error}`); return; }
    if (token !== chooseToken || clipboard) return;       // (something else was copied or chosen meanwhile)
    const left = [...doc.left, ...clip.left];
    if (left.length) banner(`${doc.name}: ${plural(left.length, 'piece')} could not be brought here. ${left[0]}`);
    if (!clip.entries.length && !clip.volumes.length) return;
    setClipboard({ ...clip, words: doc.words, copied: true, carried: text });
    startPlacing(clipboard);
  }
  // As a page opens: the hint says once that a copy came along (or was too large to)
  function announceCarried() {
    if (clipboard) return;
    const carried = unpackCarried(recallSession(CARRIED_KEY)), id = carried?.doc?.id ?? carried?.id;
    if (!id || recallSession(CARRIED_TOLD) === id) return;
    rememberSession(CARRIED_TOLD, id);
    flashHint(carried.doc ? CARRIED_WORDS.arrived : CARRIED_WORDS.tooLarge(carried.tooLarge));
  }

  // This prefab follows the prefab: a piece added, deleted, moved or changed shows without closing the panel, the list
  // collected again once a frame at most while the tab is shown
  let recollect = false;
  onHub('edit', 'add-panel', () => {
    if (!builderMode || recollect || !pieces.open || libraryScope !== 'map') return;
    recollect = true;
    requestAnimationFrame(() => {
      recollect = false;
      if (pieces.open && libraryScope === 'map') pieces.show(true, pieceEntries, true);
    });
  });

  return { addLarge: () => large, announceCarried, boxMatrix, carryCopy, chooseEntry, chooseLibraryEntry, copyDragBegin, copyDragEnd, copySelection, copyThing, dropTarget,
           entryParts, groupTree, LIBRARY_SCOPES, linkOf, mapChain, matrixBox, moveGhost, paste,
           pasteSnapshot, pieceRecipes, placeAt, placeMove, previewGroup, setAddLarge, setLibraryScope, showPieces, snapshot,
           startPlacing, stopPlacing };
}
