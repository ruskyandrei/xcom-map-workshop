import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createGizmo } from './gizmo.js';
import { createPieceBrowser } from './pieces.js';
import { api as projectApi, stateKey, targetKey, uuid } from './project.js';
import { createProjectDialog, savedWhen } from './project_files.js';
import { createProjectManager } from './manager.js';
import { createQueueController } from './build_queue.js';
import { createGameMaps } from './gamemaps.js';
import { createSetupDialog, setupApi } from './setup.js';
import { viewHeight } from './effects_preview.js';
import { recordName } from './effects_rules.js';
import { createPrecache } from './precache.js';
import { createLibraryBrowser } from './library.js';
import { createPrefabBrowser } from './prefabs.js';
import { emptyPrefabScene, orderedWrites } from './prefab_document.js';
import { activeMapId, allRoots, areaBindings, areaShown, assigning, boxesShown, breaking, builder, builderMode,
         buildingMeta, cachePrefix, cleared, coverDrag, data, effectRoots, effectsDirty, effectsOn, eventMemo,
         floorTileLayer, ghostDirty, gridDrag, gridTool, groupIndex, groups, landingZones, lastBuild, lastLightSync,
         leaving, levelSnap, library, libraryScope, lightDrag, lightRoots, lightsDirty, lightsOn, lightsShown,
         likenessOn, lookPicker, lookPicking, mapBrowser, mapCatalogue, missionMoves, missionPickValue, normalEffects,
         normalLights, normalSpawns, ownSet, pickBox, pickDrag, pickedSpawn, pieces, placing, prefabParameter, project,
         projectMissions, projectSpawnRules, reachShown, roots, selected, setActiveMapId, setAlignTarget, setAreaShown,
         setAskedPick, setAssigning, setBoxesShownValue, setCachePrefix, setCleared, setClearKeepsOutside, setData,
         setEffectsDirty, setEffectsOn, setEventMemo, setGhostDirty, setGroups, setLandingZones, setLibrary,
         setLibraryScopeValue, setLighting, setLightsOn, setLightsShownValue, setLiveCache, setLookPicker,
         setLooksReady, setMapCatalogue, setMergedBuildings, setNormalEffectsValue, setNormalLightsValue,
         setNormalSpawnsValue, setOwnGrid, setOwnPickedValue, setPickedEffect, setPickedSpawnValue, setPieces,
         setPointer, setPrefabTab, setProjectMissions, setProjectPicture, setProjectSpawnRules, setReachKey,
         setReachShown, setSpawnRulesData, setSpawnsOn, setSpawnZonePick, setTileKey, setTipDirty, setZonesOn, soloOn,
         spawnLayerReady, spawnPlacing, spawnsOn, stage, streamSet, tipDirty, volumeDrag, volumeRoots, volumesOn,
         wallDrag, wallDrawing, zonePlacing, zonesOn } from './editor_state.js';
import { createDocumentSession } from './document_session.js';
import { createDocumentState } from './document_state.js';
import { createBuildPlay } from './build_play.js';
import { createBuilderSession } from './builder_session.js';
import { createPrefabPlace } from './prefab_place.js';
import { createLightsWiring } from './lights_wiring.js';
import { createEffectsWiring } from './effects_wiring.js';
import { createSpawnsWiring } from './spawns_wiring.js';
import { createZonesWiring } from './zones_wiring.js';
import { createBuildingsWiring } from './buildings_wiring.js';
import { createCoverWiring } from './cover_wiring.js';
import { createFlagsPanel } from './flags_panel.js';
import { createSelectKind } from './select_kind.js';
import { cloneGroup, cloneGroups, createGroups, groupChain, memberOf, memberRecord, topLocked } from './groups.js';
import { createAlign } from './align.js';
import { createLibraryTemplates } from './library_templates.js';
import { createClipboard } from './clipboard.js';
import { createMadeLooksWiring } from './made_looks_wiring.js';
import { createMadeDrawing } from './made_drawing.js';
import { createMadeHandles } from './made_handles.js';
import { createMadePanel } from './made_panel.js';
import { createMadeBreaking } from './made_breaking.js';
import { createMapGrid, gridOrigin, tileCorner } from './map_grid.js';
import { createMapFamilies } from './map_families.js';
import { createClearMap } from './clear_map.js';
import { actorPose, createScenePieces, movedMatrix } from './scene_pieces.js';
import { isPlain, madeRequest, plainLook } from './made_requests.js';
import { createCutaway } from './cutaway.js';
import { createFloorListings } from './floor_listings.js';
import { createLevelSnap } from './level_snap.js';
import { createDeleteReset } from './delete_reset.js';
import { createPrepare } from './prepare.js';
import { onHub, runHub, STOP } from './edit_hub.js';
import { createSelection, selectionWords } from './selection.js';
import { showImportNotes, showLinked, showSceneMenus, showSceneTitle } from './scene_start.js';
import { createTestApi } from './test_api.js';
import { createNavigation, RECIPE_NOTE } from './navigation.js';
import { createLoading } from './loading.js';
import { createHints } from './hints.js';
import { createBusy } from './busy.js';
import { createPopups } from './popups.js';
import { createMapMenu } from './map_menu.js';
import { anyModal, holdModals, releaseAfterChange } from './modal.js';
import { call } from './api.js';
import { recall, remember } from './storage.js';
import { copyText, field, plural, segButton, segmented, short, text } from './dom_words.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createMapLighting } from './lighting.js';
import { COVER_KIND } from './cover.js';
import { TILE } from './constants.js';
import { loadLooks, lookTags } from './looks.js';
import { createLookPicker } from './look_picker.js';

const $ = id => document.getElementById(id);
// Every dialog keeps the keyboard while open: Tab goes round its controls, the focus goes back when it closes
// (modal.js; put in first, so the build window's own key catcher doesn't keep Tab from it)
holdModals();
releaseAfterChange();     // (selects, tick boxes and sliders let the shortcuts work once changed: review finding 33)
// Whether a dialog (or the look picker) is open: the editor's shortcuts take no keys then, and no other window opens.
function modalOpen() { return anyModal() || Boolean(lookPicker?.isOpen); }
const documentWrites = orderedWrites();
const viewport = $('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
// The sun's shadow map is drawn again when something changed, not every frame (plan "faster editor", P5): an edit,
// a cutaway, pieces coming or going, the lighting. touchShadows() asks for it over the next third of a second (a
// change's frames), and the draw loop asks once a second besides, for what no hook saw (a material still loading).
renderer.shadowMap.autoUpdate = false;
let shadowsUntil = Infinity, shadowBeat = 0;
const touchShadows = () => { shadowsUntil = performance.now() + 330; };
renderer.localClippingEnabled = true;
viewport.append(renderer.domElement);
const world = new THREE.Scene();
world.background = new THREE.Color('#27333d');
const camera = new THREE.PerspectiveCamera(45, 1, 2, 100000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
const hemisphere = new THREE.HemisphereLight(0xcce3f2, 0x4a4540, 2);
const sun = new THREE.DirectionalLight(0xfff0d9, 3);
sun.position.set(1600, 2600, -1400);
sun.castShadow = true;
sun.shadow.mapSize.set(2048,2048);
sun.shadow.normalBias = 1;
world.add(hemisphere, sun, sun.target);
const content = new THREE.Group(); world.add(content);
const grid = new THREE.Group(); world.add(grid);
const highlight = new THREE.Box3Helper(new THREE.Box3(), 0x96e5d7);
highlight.visible = false; world.add(highlight);
// A selected ladder's climb ends (ladders.js): a square on its foot tile and on its top tile, green where the map's
// original floor data has floor, red where not. Drawn over everything, so the top shows on a roof.
const ladderMarks = new THREE.Group();
ladderMarks.visible = false; world.add(ladderMarks);
for (let k = 0; k < 2; k++) {
  const mark = new THREE.Mesh(new THREE.PlaneGeometry(80, 80).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.55, depthTest: false, side: THREE.DoubleSide }));
  mark.renderOrder = 10; ladderMarks.add(mark);
}
const pickables = [], texturePromises = new Map();
// The layer of the map's lights' roots (editor_state.js: lightRoots; the Lights view: lights_wiring.js, made below).
const lightLayer = new THREE.Group();
world.add(lightLayer);
// The layer of the project's building boxes' roots (editor_state.js: volumeRoots; the Buildings view:
// buildings_wiring.js).
const volumeLayer = new THREE.Group();
// Box select (buildings_wiring.js, with the Buildings view): the tool waiting for a drag, the box, the drag, what the
// box would take, and the pieces' middles while it is up.
// (pickTool, pickBox, pickDrag, pickHits, pickCentres: editor_state.js)
// The three views (the user, 11 November 2026): Normal, Buildings (volumesOn) and Lights (lightsOn), one at a time.
// In the Buildings view only boxes are picked, in the Lights view only lights. In the normal view pieces are, and
// with the Normal button's two switches also lights (normalLights) and the project's floor boxes (boxesShown), a
// building whole. Both switches are off whenever a map opens.
// (lightsOn, normalLights, boxesShown: editor_state.js)
// the Effects view (effects and sounds plan, FX1; effects_wiring.js): its markers, and only they are picked.
// Since FX3 each effect, sound and lens flare is a root of its own (effectRoots, an original's also by its key in
// effectIndex), moved and turned by the gizmo, copied and deleted as pieces are where its family builds; the Normal
// button's Effects switch (normalEffects) draws and picks them with pieces in the normal view. effectMarkers: the
// markers drawn now, the roots' and the copies a piece's copy carries.
// (effectsOn, pickedEffect, effectsDirty, effectMarkers, normalEffects: editor_state.js)
// the Spawns view (editor spawns plan, SP3; spawns_wiring.js): only its markers are picked; the Normal button's switch
// (normalSpawns, remembered) draws and picks them with pieces
// (spawnsOn, normalSpawns, spawnLayerReady: editor_state.js)
// (the Wave preview's player, wavePlayer: editor_state.js)
world.add(volumeLayer);
const cutMaterials = new Map();
const helperMaterial = new THREE.MeshBasicMaterial({color:0x59d5df,wireframe:true,transparent:true,opacity:0.65,depthWrite:false});
const textureLoader = new THREE.TextureLoader();
const gltfLoader = new GLTFLoader();
// Edits: the gizmo moves whole actors (all their components); a project keeps the edits (Ctrl+S) and the Build makes them.
// Pieces of the packages a mission streams into the map (LWR's patches, mission objects): shown for reference, never
// edited (a project edits the map's own pieces; the Build makes nothing of theirs).
const isStream = o => o?.layer === 'stream';
// The looks made walls, slabs and ground shapes can take (custom geometry plan, M4: looks.js), read once; a project
// opens once they are, so its pieces in a donor look are drawn in it. A read that fails isn't kept (review finding
// 31): the banner says why, and Try again reads it again.
setLooksReady(readLooks());
function readLooks() {
  const ready = Promise.all(['wall', 'slab', 'ground'].map(kind => loadLooks(kind)));
  ready.then(lists => {
    const failed = lists.filter(l => l.error);
    if (failed.length)
      banner(`${failed.map(l => l.error).join('; ')}, so pieces made in those looks are drawn as the piece they copy and the look picker lists none of them.`,
             [['Try again', () => { setLooksReady(readLooks()); }]]);
  });
  return ready;
}
// The original a piece is, or was copied from: package, level and actor (a project's key for it).
const fromOf = o => (o.added ? o.added.from : { package: o.sourcePackage, level: o.layer, actor: o.actor });
// (The map's size as the project sets it, the cleared map, its landing zones, missions, picture and spawn rules, the
// buildings, and the install's landing lines for the map with the read a project waits for: editor_state.js.)
// The scene's pieces (scene_pieces.js): picking, textures and materials, the meshes' and materials' loads, a
// piece's root built, added and taken away, an original's parts and boxes, a piece's box, an added piece made from
// its template, a record's template and an original's recipe pose; made before the gizmo, which is given baseMatrix
// (nothing of it runs as the page loads but a few tables and vectors made).
const { addedObject, addRoots, baseMatrix, boundsOf, boxOf, buildPieces, buildRoot, loaded, madeShape, material,
        materialCache, materialKey, movedBox, originalOf, partsOf, pick, placeObjects, rayAt, recipeOf, removeRoots,
        templateFor, texture, track, unscaled, vertexBox } = createScenePieces({
  camera, content, fromOf, gltfLoader, gridOrigin, isStream, pickables, renderer, textureLoader, texturePromises,
  // (made further down: called through, since they are not made yet while this runs)
  loadingState: (message, fraction, detail) => loadingState(message, fraction, detail),
  assetUrl: url => assetUrl(url), coverVersion: (version, type) => coverVersion(version, type),
  drawBroken: root => drawBroken(root), flashHint: message => flashHint(message), isMade: o => isMade(o),
  select: (id, add, keep) => select(id, add, keep), sourceKey: o => sourceKey(o) });
const gizmo = createGizmo({ world, camera, dom: renderer.domElement, orbit: controls, roots: allRoots, baseMatrix, onEdit: editChanged,
                            // a group's lights and buildings move with it, drawn or not; a building is whole (all its boxes)
                            // outside the Buildings view, where each box is on its own
                            lockedGroup: o => {
                              if ((o.isVolume && volumesOn) || lightsOn || effectsOn) return null;
                              const g = groupIndex.get(memberOf(o));
                              return g ? topLocked(g)?.id ?? null : o.isVolume ? memberOf(o) : null;
                            },
                            fixed: o => isStream(o) || Boolean(o.isLight && lightViewOnly(o)) || Boolean(o.isEffect && effectViewOnly(o, 'move')),
                            assemblyOf: o => (o.isLight || o.isVolume || o.isEffect ? null : assemblyOf(o)?.pivot ?? null),
                            recipe: root => (root.userData.light || root.userData.volume || root.userData.effect ? null : recipeOf(root.userData.source)), gridOrigin,
                            // a building's box moves by whole tiles and levels, whatever the snap
                            tiles: root => Boolean(root.userData.volume),
                            // Shift on a move handle drags a copy
                            copyDrag: { begin: () => copyDragBegin(), end: (token, delta) => copyDragEnd(token, delta) },
                            // Level snap: a floor piece moved up or down keeps to whole levels (64 units)
                            levels: root => !root.userData.light && !root.userData.volume && !root.userData.effect && levelSnap && floorSupportOf([root.userData.source]) != null });
// The map's families and assemblies (map_families.js): the families set as the map's arrive, each original's assembly
// with its link tag, and a piece's assembly (the map's own, or another map's as its records are read); made where the
// families' use was, after the gizmo, which it regroups (nothing of it runs as the page loads but its two tables made).
const { assemblyOf, foreignAssemblies, useMapFamilies } = createMapFamilies({
  fromOf, gizmo });
// (the Map lighting mode, lighting, and the pieces that could not be drawn, loadErrorCount: editor_state.js)
// (the server's map list, mapCatalogue, the map browser, mapBrowser, and cachePrefix: editor_state.js)
// (the lights' reach, lightRadius: editor_state.js)

// The loading overlay (loading.js): its message, bar and detail line, an opening document's steps on it, and a
// JSON file read with its progress; made as soon as the words it needs are (nothing of it runs as the page loads).
const { fetchJson, loadingState, openingProgress } = createLoading({
  $, plural });
// The selection's group as a chip beside its name; groupPanel keeps it up to date. (The selection, selection.js,
// puts it in the piece panel; both it and the groups are given it.)
const groupChip = document.createElement('span');
groupChip.hidden = true;
// The Flags group of the piece panel and its chip (flags_panel.js): a piece's flags as the project has them,
// the chip, the group's rows and a change of them (one undo step).
const { flagContract, flagKey, flagSource, resetFlags } = createFlagsPanel({
  $, boxOf, gizmo, isStream, plural, text, tileCorner,
  // (made further down: called through, since they are not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep), sourceKey: o => sourceKey(o) });
const poseInputs = ['posX','posY','posZ','rotP','rotY','rotR'].map($);
// Unsaved changes by kind. A deleted original counts as deleted only; an added piece as added only. A grid of the
// project's size (stage) and the project's own landing zones count once each.
function changes() {
  let moved = 0, added = 0, deleted = 0, lights = 0;
  const flagged = new Set(), broken = new Set();     // (broken: the map's pieces broken where they stand, E6)
  for (const root of roots.values()) {
    if (root.userData.source.added) added++;
    else if (root.userData.deleted) deleted++;
    else if (root.userData.edit) moved++;
    if (!root.userData.source.added && !root.userData.deleted && root.userData.flags) flagged.add(sourceKey(root.userData.source));
    if (!root.userData.source.added && !root.userData.deleted && !root.userData.edit && root.userData.blasts?.length) broken.add(sourceKey(root.userData.source));
  }
  for (const root of lightRoots.values()) if (!isStream(root.userData.source) && root.userData.source.role !== 'area' && lightEdited(root)) lights++;
  let effects = 0;
  for (const root of effectRoots.values()) if (effectEdited(root)) effects++;
  const grid = stage ? 1 : 0, zones = landingZones ? 1 : 0;
  // the buildings the project saves: its own, and the map's it changed or deleted
  const built = data ? savedBuildings().length : 0;
  // a mission's objects moved in their streams (mission types plan, Part E), and the base spawn points edited (SP6)
  const spawns = [...missionMoves.values()].filter(m => m.stream === null || m.stream === 'copy').length, missions = missionMoves.size - spawns;
  return { moved, added, deleted, lights, effects, grid, zones, buildings: built, missions, spawns, flags: flagged.size, broken: broken.size,
           total: moved + added + deleted + lights + effects + areaBindings.size + grid + zones + built + missions + spawns + flagged.size + broken.size };
}
// After any trial edit, undo or selection: the highlight, the pose fields, the tool states and the edit status.
// Undo, redo and the "not saved" chip appear only once something has changed.
// One edit event builds the document's state once (plan "faster editor", P2): while editChanged runs, editState,
// builderDocument and builderKey give what they worked out first, where each was built again by every reader (the
// save state, the title, the size line, the recovery timer: six times an event in the builder).
// (that memo, eventMemo: editor_state.js)
function editChanged() {
  touchShadows();
  if (eventMemo) return editChangedNow();
  setEventMemo({});
  try { return editChangedNow(); } finally { setEventMemo(null); }
}
function editChangedNow() {
  runHub('edit');
}
// app.js's own refreshes of the edit hub's run (edit_hub.js lists them with the other areas' and calls them in
// order):
onHub('edit', 'piece-status', () => {
  const pose = gizmo.pose(), count = changes();
  if (pose) [...pose.location, ...pose.rotation].forEach((v, i) => {
    if (document.activeElement !== poseInputs[i]) poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2);
  });
  // while a handle is held, only what is seen to move is kept up: the pieces, the highlight, the pose fields, the
  // grid chip. The status, the save state, the panels, the size line and the warnings wait for the drag's end, which
  // runs this again in full (the gizmo's dragging-changed).
  if (gizmo.controls.dragging) { runHub('drag'); return STOP; }
  // a streamed piece, or a view-only light, is shown, not edited: its place, read only
  const pickedRoot = allRoots.get(selected), pickedSource = pickedRoot?.userData.source;
  const fixedPick = isStream(pickedSource) || Boolean(pickedRoot?.userData.light && lightViewOnly(pickedSource));
  if (fixedPick && !pose) {
    const at = pickedRoot.userData.light ? lightPose(pickedRoot) : pickedSource;
    [...at.location, ...at.rotation.map(r => r * 360 / 65536)].forEach((v, i) => { poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2); });
  }
  { const n = i => Math.round(Number(poseInputs[i].value) || 0);
    $('poseSum').textContent = `${n(0)}, ${n(1)}, ${n(2)} · ${n(4)}°`;
    $('sourceSum').textContent = pickedSource?.actorClass ?? ''; }
  poseInputs.forEach((input, i) => { input.disabled = fixedPick || (i >= 3 && pickedRoot?.userData.light && pickedSource.kind === 'point'); });
  $('editDelete').disabled = fixedPick;
  // (in the builder every piece is the prefab's own, so only whether it is saved is said)
  $('editCount').hidden = builderMode ? !count.total && !builder.doc?.revision : !count.total;
  $('editCount').textContent = builderMode ? saveState() : [count.moved && `${count.moved} moved`, count.added && `${count.added} added`,
    count.deleted && `${count.deleted} deleted`, count.lights && plural(count.lights, 'light edit'),
    count.effects && plural(count.effects, 'effect or sound edit'),
    count.grid && `grid ${data.tileGrid.dimensions[0]} × ${data.tileGrid.dimensions[1]}${cleared ? ` × ${data.tileGrid.dimensions[2]}` : ''}`,
    count.zones && 'landing zones changed', count.buildings && plural(count.buildings, 'building'),
    count.missions && `${plural(count.missions, 'mission object')} moved`, count.spawns && plural(count.spawns, 'spawn point edit'), count.flags && `${plural(count.flags, 'piece')} with flags changed`, count.broken && `${plural(count.broken, 'piece')} broken`,
    saveState()].filter(Boolean).join(' · ');
  $('editCount').classList.toggle('warn', saveState() !== 'saved');
  $('editUndo').hidden = $('editRedo').hidden = !(count.total || gizmo.canUndo() || gizmo.canRedo());
  $('editUndo').disabled = !gizmo.canUndo(); $('editRedo').disabled = !gizmo.canRedo();
  $('editReset').disabled = !gizmo.selection().some(r => r.userData.edit || (r.userData.light && valuesEdited(r)) || (r.userData.effect && r.userData.values));
  $('editResetAll').hidden = builderMode || (!count.total && !groups.size && !cleared);
});
// The hint line under the view (hints.js): while a gizmo handle is held, a short notice, and with nothing else to say
// what is being placed; and the busy mark for slow steps (busy.js), the page giving way in a long loop and many pieces
// built a few at a time, whose listeners hold the view's clicks and keys while a mark put up at once is shown. Made
// where their code was: the busy mark's listeners are set here, as before.
const { dragHint, flashHint, restingHint } = createHints({
  $, gizmo });
const { BUSY_PIECES, buildRoots, busy, busyPaint, busyStart, nextFrame } = createBusy({
  $, buildRoot });

// What a selected root is called in a list: a piece by its mesh, a light by its actor.
const rootName = r => (r.userData.volume ? `Floor box of ${buildingMeta.get(r.userData.volume.building)?.name || 'a building'}`
  : r.userData.light ? short(r.userData.source.actor) : r.userData.effect ? recordName(r.userData.source, data)
  : short(data.meshes[r.userData.source.mesh].name));
// The floor boxes selected with pieces in the normal view (View options' Floor boxes): each building's, whole.
const selectedBoxes = () => (volumesOn ? [] : gizmo.selection().filter(r => r.userData.volume && !r.userData.deleted));
// The selection's pieces that can be copied or deleted: hidden helpers shown for inspection are left out.
function copyable() {
  return gizmo.selection().filter(r => !r.userData.volume).filter(r => (r.userData.light ? !lightViewOnly(r.userData.source)
    : r.userData.effect ? !effectViewOnly(r.userData.source, 'copy') || !effectViewOnly(r.userData.source, 'delete')
    : !r.userData.source.hidden && !r.userData.source.environment));
}
// (Align lines up pieces only: lights and effects have no box of their own to line up)
const copyablePieces = () => copyable().filter(r => !r.userData.light && !r.userData.effect);
// What a group can hold of the selection: pieces, lights that can be edited, and the buildings picked with them.
const groupables = () => [...copyable(), ...selectedBoxes()];
function sceneChanged() { touchShadows(); setLiveCache(null); setEffectsDirty(true); cutaway(); refreshGroundGrid(false); refreshJoins(); }
// The pieces and effects of other maps read as templates (library_templates.js): their records read, a
// piece's or an effect's template, the templates a project's records name, and what such a piece costs and
// says.
const { assetUrl, bakeNote, effectTemplate, foreignCost, foreignNote, isForeignTarget, libraryTemplate,
        loadForeignTemplates, readEffectRecords, readLibraryRecords, recordId } = createLibraryTemplates({
  boundsOf, buildRoot, foreignAssemblies, fromOf, plural, short,
  // (made further down: called through, since they are not made yet while this runs)
  collisionMesh: c => collisionMesh(c), effectSource: rec => effectSource(rec),
  lightSource: record => lightSource(record) });
// The outline of a floor box that comes with a clip, while the clip is placed or dragged off (clipboard.js) and as a
// prefab is placed (prefab_place.js, made before the clipboard's module): made here, where it always was, and given to
// both.
const ghostEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1));
const ghostLine = new THREE.LineBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.7, depthTest: false });

// Floor pieces and Level snap (level_snap.js): the floor pieces and their supports, Level snap and its button,
// and the Floor picker's floor under a point.
const { chosenStorey, floorData, floorSupportOf, levelButton, setLevelSnap } = createLevelSnap({
  $, restingHint,
  // (made further down: called through, since it is not made yet while this runs)
  allBuildings: () => allBuildings() });

// The user's groups (groups.js): a group's pieces on the map now, what the selection is to the groups, the
// piece panel's group section, and the groups changed (each change one undo step).
const { addToGroup, changeGroups, groupShortcut, liveGroup, liveKeys, liveMembers, lockAsGroup,
        selectionGroup, ungroup } = createGroups({
  $, flashHint, gizmo, groupables, groupChip, highlight, isStream, plural,
  // (made with the selection, further down: called through, since it is not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep) });

// Align (align.js): the others of the selection lined up with a target, the piece panel's Align section and
// its white box on the target.
const { align, alignPanel, saveAlignPrefs } = createAlign({
  $, copyablePieces, flashHint, gizmo, liveGroup, memberOf, plural, short, world,
  // (made with the clipboard, further down: called through, since it is not made yet while this runs)
  keepRecipe: (move, parts) => keepRecipe(move, parts) });

// The Lights view's storage keys, and its switches read from them (the view: lights_wiring.js, made below).
const AREA_SHOWN = 'workshop.areaLights', SKY_SHOWN = 'workshop.sunSky', REACH_SHOWN = 'workshop.lightReach';
const PL = 'TheWorld.PersistentLevel.';
setAreaShown(recall(AREA_SHOWN) === '1');     // (lightsShown, areaShown: editor_state.js)
setReachShown(recall(REACH_SHOWN) === '1');   // the selected light's reach outlined (View options; off at first)
// The normal view: out of the Buildings view, the Lights view, the Landing zones view and the Effects view.
function setNormalView() {
  if (volumesOn) setVolumesShown(false);
  if (lightsOn) setLightsShown(false);
  if (zonesOn) setZonesShown(false);
  if (effectsOn) setEffectsShown(false);
  if (spawnsOn) setSpawnsShown(false);
}
// After a view or a switch changed: whether lights are drawn, what stays selected, the buttons.
function syncLights() {
  setLightsShownValue(lightsOn || (normalLights && !volumesOn));
  if (volumesOn || lightsOn || !boxesShown) { ownSet.clear(); if (!volumesOn) setOwnPickedValue(null); }
  const picks = gizmo.picks();
  const keep = picks.ids.filter(id => (lightRoots.has(id) ? lightsShown : volumeRoots.has(id) ? volumesOn || (boxesShown && !lightsOn) : !lightsOn));
  if (keep.length !== picks.ids.length) gizmo.setSelection(keep, picks.active); else gizmo.regroup();
  refreshLightVisibility(); lightButton(); refreshLightShapes(); refreshVolumes();
  if (pickBox) refreshPickBox(true);
  if (data) select(gizmo.active, false, true);
}
function lightButton() {
  for (const [id, on] of [['editNormal', !volumesOn && !lightsOn && !zonesOn && !effectsOn && !spawnsOn], ['editBuildings', volumesOn], ['editLights', lightsOn],
                          ['editZones', zonesOn], ['editEffects', effectsOn], ['editSpawns', spawnsOn]]) {
    $(id).classList.toggle('on', on); $(id).setAttribute('aria-pressed', on);
  }
  $('normalLights').checked = normalLights; $('boxesToggle').checked = boxesShown; $('normalEffects').checked = normalEffects;
  $('normalSpawns').checked = normalSpawns;
  // (the spawn markers show with the view, or with the switch in the normal view)
  if (spawnLayerReady) { spawnLayer.visible = spawnsShown(); spawnPanel(); }
  $('areaToggle').checked = areaShown; $('reachToggle').checked = reachShown;
  $('areaToggle').disabled = $('reachToggle').disabled = !lightsShown;
}
const HANDLE_PICK = 10;
// Screen positions (client pixels) for points in the view, or null behind the camera.
function projector() {
  const rect = renderer.domElement.getBoundingClientRect(), p = new THREE.Vector3();
  return v => {
    p.copy(v).project(camera);
    if (p.z < -1 || p.z > 1) return null;
    return [rect.left + (p.x + 1) / 2 * rect.width, rect.top + (1 - p.y) / 2 * rect.height];
  };
}
// The header's menus (popups.js): one open at a time, a press elsewhere closing it; made before the first area
// that is given showPop.
const { showPop } = createPopups({
  $, renderProjectMenu, viewport,
  // (made further down: called through, since they are not made yet while this runs)
  refreshInstalls: () => refreshInstalls(), refreshSquadLine: () => refreshSquadLine() });
// The Lights view (lights_wiring.js): the map's lights as roots, the view, the panel's light section, Solo, the
// area lights following their glowing pieces, the reach, the drag handles (the picked effect's and sound's too),
// and the project's light records.
const { addedLight, addedLightOf, addLightRoots, applyLightRecord, applyMapLighting, areaOwner, assignOwner,
        buildLights, changeLight, clearLightEdits, commitColour, commitLightField, endLightDrag, handlesNear,
        hoverHandle, lightClip, lightEdited,
        lightEntries, lightingModes, lightPanel, lightPose, lightRecords, lightsBlocked, lightShapes, lightSource,
        lightState, lightViewOnly, moveLightDrag, ownerRoot, pickLight, recipeLight, refreshLightShapes,
        refreshLightVisibility, removeLightRoots, scaleMarkers, setBinding, setLightsShown, setLightValues,
        setNormalLights, setSolo, startLightDrag, updateLightHandles, valuesEdited,
        withStorableCone } = createLightsWiring({
  $, actorPose, baseMatrix, camera, copyable, copyText, editChanged, field, flashHint, gizmo, HANDLE_PICK, highlight,
  isStream, ladderMarks, lightLayer, pickables, PL, plural, projector, renderer, restingHint, short, showPop,
  sun, syncLights, text, world,
  // (made further down: called through, since they are not made yet while this runs)
  applyLighting: () => applyLighting(), banner: (message, actions, options) => banner(message, actions, options),
  // (made with Clear map, further down: called through)
  pointOutside: (x, y) => pointOutside(x, y),
  // (made with the selection, further down: called through)
  select: (id, add, keep) => select(id, add, keep),
  // (made with the Spawns, Landing zones and Buildings views, further down: called through)
  setSpawnsShown: on => setSpawnsShown(on), setVolumesShown: on => setVolumesShown(on),
  setZonesShown: on => setZonesShown(on), stopPickBox: () => stopPickBox(),
  // (made with the Effects view, further down: called through)
  drawEffectShape: () => drawEffectShape(), effectNow: (root, r) => effectNow(root, r), effectsShown: () => effectsShown(),
  effectValuesEditable: root => effectValuesEditable(root), setEffectsShown: on => setEffectsShown(on),
  setEffectValues: (root, values) => setEffectValues(root, values) });
// Prepare (prepare.js): the dialog that exports the map again, and a build or a play waiting for it.
const { needsPrepare, prepareOpened, showPrepare } = createPrepare({
  $, showPop,
  // (made further down: called through, since they are not made yet while this runs)
  banner: (message, actions, options) => banner(message, actions, options), mapLabel: id => mapLabel(id),
  projectsAvailable: () => projectsAvailable() });

// Projects: the edits saved, reopened and recovered (first-editor plan E1; project.js, research/editor-contracts.md).
// The scene holds the state; a project records it against the map as exported, and replays it onto the map.
// (The project open, `project`: editor_state.js.)
// Drafts for recovery belong to the page session that keeps them (review finding 3; projects.py): this page's id,
// made as it loads, names its own draft, and the page deletes only that one, or a draft it showed the user and the
// user restored or discarded (the drafts' state: editor_state.js).
const SESSION = uuid();
const sourceKey = o => targetKey({ package: o.sourcePackage, level: o.layer, actor: o.actor });
// Projects edit a full map's original layout: not a patch preview.
const projectsAvailable = () => !builderMode && Boolean(data) && data.scope === 'map' && !data.preview;
// The edits on screen, as a project records them: overrides of original actors and added actors, sorted.
function editState() {
  if (!eventMemo) return editStateNow();
  return eventMemo.state ??= editStateNow();
}
const dirty = () => builderMode ? !builder.loading && builderKey() !== builder.savedKey : Boolean(project) && stateKey(editState()) !== project.savedKey;
const unsavedDocument = () => builderMode || project ? dirty() : Boolean(changes().total || savedBuildings().length || groups.size || stage || areaBindings.size
  || cleared || landingZones || projectMissions || projectSpawnRules);
function saveState() { return builderMode ? !builder.doc?.revision ? 'not saved' : dirty() ? 'unsaved' : 'saved' : !project ? 'not saved' : dirty() ? 'unsaved' : 'saved'; }
// Back to the map as exported, with no history: before a project's state is applied.
function clearEdits() {
  const all = [...roots.values()];
  removeRoots(all.filter(r => r.userData.source.added));
  const moved = all.filter(r => r.userData.edit && !r.userData.source.added);
  gizmo.applyMatrices(moved, moved.map(r => baseMatrix(r)));
  for (const r of all) {
    r.userData.deleted = false; r.userData.flags = null; r.userData.breaksFurther = false;
    if (r.userData.blasts) { r.userData.blasts = null; drawBroken(r); }
  }
  setGroups(new Map()); setLiveCache(null);
  clearLightEdits();
  clearEffectEdits();
  setCleared(false); setClearKeepsOutside(false); setLandingZones(null); setMergedBuildings(null); setProjectMissions(null);
  setProjectPicture(null);
  setProjectSpawnRules(null); syncSpawnRule();
  setMissionMoves(new Map());
  setStage(null);
  setBuildings([]);
  clearedChanged();
}
// Recent projects: when this browser last opened or saved each, beside when it was saved anywhere.
const RECENT = 'workshop.recentProjects';
function recentTimes() { try { return JSON.parse(recall(RECENT)) ?? {}; } catch { return {}; } }
function touchRecent(id) {
  const times = { ...recentTimes(), [id]: new Date().toISOString() };
  remember(RECENT, JSON.stringify(Object.fromEntries(Object.entries(times).sort((a, b) => b[1].localeCompare(a[1])).slice(0, 20))));
}
function projectNote(message) { text($('diagnostics'), 'div', message, 'note'); $('issueCount').textContent = String(Number($('issueCount').textContent || 0) + 1); }
// The scene to and from a document (document_state.js): the edits on screen as a project records them, and a
// project's state put on the map.
const { editStateNow, applyState } = createDocumentState({
  actorPose, addLightRoots, addRoots, addedLightOf, addedObject, applyLightRecord, buildRoots, builder, clearEdits,
  cloneGroups, editChanged, gizmo, lightState, liveMembers, loadForeignTemplates, memberOf, movedMatrix, plural,
  projectNote, sceneChanged, short, sourceKey, templateFor,
  // (made with the map grid, further down: called through, since they are not made yet while this runs)
  ownSize: () => ownSize(), setStage: next => setStage(next),
  // (made with the cover blocks, further down: called through, since they are not made yet while this runs)
  coverOf: entity => coverOf(entity), coverVersion: (version, type) => coverVersion(version, type),
  // (made with the Effects view, further down: called through, since they are not made yet while this runs)
  addEffectRoots: list => addEffectRoots(list), addedEffectOf: entity => addedEffectOf(entity),
  applyEffectRecord: record => applyEffectRecord(record), effectState: (overrides, added) => effectState(overrides, added),
  // (made with the Spawns view, further down: called through, since they are not made yet while this runs)
  baseSpawnOf: actor => baseSpawnOf(actor), missionKey: (stream, actor) => missionKey(stream, actor),
  missionOverrides: () => missionOverrides(), setMissionMoves: next => setMissionMoves(next),
  spawnCopyRecords: () => spawnCopyRecords(), streamObjects: stream => streamObjects(stream),
  syncSpawnRule: () => syncSpawnRule(),
  // (made with the Landing zones and Buildings views, further down: called through, since they are not made yet while
  // this runs)
  clearedChanged: () => clearedChanged(), savedBuildings: () => savedBuildings(),
  setBuildings: next => setBuildings(next),
  // (made with Break and Repair, further down: called through, since they are not made yet while this runs)
  drawBroken: root => drawBroken(root), mapBreakable: o => mapBreakable(o) });
// The document session (document_session.js): opening, saving and leaving a project, its drafts kept for recovery
// and offered back, and the banner under the header.
const { banner, discardAndGo, discardDraft, draftWords, dropAdopted, ensureSavedFor, goTo, keepRecovery, loadProject,
        openProject, projectChanged, saveProject } = createDocumentSession({
  $, SESSION, applyState, builder, camera, controls, dirty, documentWrites, editChanged, editState, flashHint, gizmo,
  loadingState, openingProgress, plural, projectNote, projectsAvailable, saveState, showFileDialog, text, touchRecent,
  unsavedDocument,
  // (made with the map grid, further down: called through, since it is not made yet while this runs)
  ownSize: () => ownSize(),
  // (made with the Spawns view, further down: called through, since they are not made yet while this runs)
  bombHelperFix: moves => bombHelperFix(moves), setMissionMoves: next => setMissionMoves(next),
  // (made with the prefab builder just below, which is given the session's banner and drafts: called through)
  builderDocument: () => builderDocument(), builderTitle: () => builderTitle(), problemsPaint: () => problemsPaint(),
  refreshBuilder: () => refreshBuilder(), saveBuilder: options => saveBuilder(options),
  // (made with Build and Play just below, which is given the session's banner and save: called through)
  followBuild: (status, id) => followBuild(status, id), renderPlayItems: () => renderPlayItems(),
  setLastBuild: (id, status) => setLastBuild(id, status) });
// The prefab builder's session (builder_session.js): the prefab's document opened, kept and saved, its size line and
// ground, Align to grid, the missing pieces looked for by recipe, and the Problems check.
const { applyPrefabDocument, builderBounds, builderDocument, builderKey, builderPage, builderRecords, builderTitle,
        openPrefabDocument, physicalBox, problemsPaint, recoverPrefabSources, refreshBuilder,
        saveBuilder } = createBuilderSession({
  $, SESSION, actorPose, addRoots, addedObject, applyState, banner, boxOf, buildRoot, controls, dirty, discardAndGo, discardDraft,
  documentWrites, draftWords, dropAdopted, editChanged, editState, flashHint, gizmo, gridOrigin, isStream,
  libraryTemplate, lightPose, loadingState, movedMatrix, openingProgress, plural, projectChanged, recipeOf, removeRoots,
  rootName, sceneChanged,
  selectActors, short, showFileDialog, templateFor, text, world,
  // (made with the selection, further down: called through, since it is not made yet while this runs)
  gridNow: root => gridNow(root),
  // (made with the camera, further down: called through, since it is not made yet while this runs)
  frame: root => frame(root),
  // (made with the Buildings view and the clipboard, further down: called through, since they are not made yet while
  // this runs)
  snapshot: (selection, own) => snapshot(selection, own), volumeBox: root => volumeBox(root),
  // (made with prefabs saved and placed just below, which is given the builder's records and save: called through)
  prefabRecords: options => prefabRecords(options), showPrefabDialog: whole => showPrefabDialog(whole) });
// Prefabs saved and placed (prefab_place.js): the Save as prefab dialog, the save, and a prefab of the Add panel's
// Prefabs tab placed as a paste is.
const { choosePrefab, drawPrefabPictures, prefabClip, prefabPlacementProblem, prefabRecords, savePrefab,
        showPrefabDialog } = createPrefabPlace({
  $, BUSY_PIECES, PL, actorPose, assetUrl, banner, builderRecords, busy, busyPaint, busyStart, copyable, effectTemplate,
  flashHint, fromOf, ghostEdges, ghostLine, gltfLoader, isForeignTarget, isStream, libraryTemplate, lightPose,
  lightsBlocked, madeShape, memberOf, movedMatrix, nextFrame, physicalBox, plural, readEffectRecords,
  readLibraryRecords, recipeLight, recordId, rootName, saveBuilder, selectionGroup, short, templateFor, text, track,
  withStorableCone,
  // (made with the selection, further down: called through, since it is not made yet while this runs)
  gridNow: root => gridNow(root),
  // (made with the cover blocks, the Effects view and the clipboard, further down: called through, since they are not
  // made yet while this runs)
  boxMatrix: b => boxMatrix(b), coverOf: entity => coverOf(entity),
  coverVersion: (version, type) => coverVersion(version, type), effectViewOnly: (o, cap) => effectViewOnly(o, cap),
  groupTree: (copied, chainOf) => groupTree(copied, chainOf), linkOf: e => linkOf(e), mapChain: key => mapChain(key),
  matrixBox: matrix => matrixBox(matrix), previewGroup: (parts, override, frame) => previewGroup(parts, override, frame),
  snapshot: (selection, own) => snapshot(selection, own), startPlacing: (clip, entry) => startPlacing(clip, entry),
  stopPlacing: () => stopPlacing() });
// The map browser's wiring (map_menu.js): a map's name, the list brought up to the server's, the browser made as the
// page opens, and the Map menu's button and Change map.
const { makeMapBrowser, mapLabel, refreshMapList, showMapBrowser } = createMapMenu({
  $, goTo, modalOpen, projectsAvailable, showPop,
  // (made further down: called through, since it is not made yet while this runs)
  stopPlacing: () => stopPlacing() });
// Build and Play in game (build_play.js): Build's panel and the window that follows a build, Play in game with its
// dialog and the Game menu's Installs, the header's Build and Play buttons, the test squad's line, the prefab
// builder's Test in game and the build queue's chip.
const { followBuild, followQueueForProject, landHere, openBuild, openPrefabTest, playInGame, prefabTest, refreshInstalls,
        refreshSquadLine, renderPlayItems, renderQueueChip, setLastBuild } = createBuildPlay({
  $, bakeNote, banner, builder, builderDocument, builderRecords, dirty, dragHint, flashHint, gizmo, mapLabel,
  needsPrepare, plural, projectsAvailable, saveProject, selectActors, short, showFileDialog, showPop, showPrepare, text,
  // (made with Clear map, further down: called through, since they are not made yet while this runs)
  headerMissions: () => headerMissions(), zonesNow: () => zonesNow(),
  // (made with the Spawns and Landing zones views, further down: called through, since they are not made yet while
  // this runs)
  setZones: (next, words) => setZones(next, words), showSpawn: (actor, stream) => showSpawn(actor, stream) });
async function renderProjectMenu() {
  const info = $('projectInfo');
  info.replaceChildren();
  if (builderMode) {
    text(info, 'strong', builder.doc?.name ?? 'New prefab');
    text(info, 'div', builder.doc?.revision ? `Revision ${builder.doc.revision}${dirty() ? ' · unsaved changes' : ''}` : 'Save to add this prefab to the library.');
    for (const id of ['projectSave', 'projectSaveAs']) $(id).disabled = false;
    return;
  }
  if (project) {
    text(info, 'strong', project.doc.name);
    text(info, 'div', `Revision ${project.revision} · saved ${savedWhen(project.doc.savedAt)}${dirty() ? ' · unsaved changes' : ''}`);
    text(info, 'div', `Builds as ${project.doc.output?.shipAs ?? '(no map name)'}`).title = 'The map\'s name in the game (its package and records), fixed when the project was first saved: Save as under a new name makes a new project that builds under a name of its own';
    const pkg = lastBuild?.package;
    if (lastBuild?.state === 'running') text(info, 'div', `Building revision ${lastBuild.job.revision}…`);
    else if (pkg) {
      const last = text(info, 'div', `Last built: revision ${pkg.revision} · ${savedWhen(pkg.builtAt)}${pkg.quick ? ' · lighting not baked' : ''}`);
      last.title = pkg.quick ? `${pkg.folder}\nBuilt without baking the lighting: its lighting isn't right in the game (pathing and cover are). Build with Bake the lighting ticked for the proper lighting` : pkg.folder;
    }
  } else if (projectsAvailable()) text(info, 'div', 'No project open: edits are a trial until you save them.');
  else text(info, 'div', 'This is a patch preview: projects edit a map\'s original layout. Open the map from the map browser (M) to save one; Load opens a project on its map.');
  for (const id of ['projectSave', 'projectSaveAs']) $(id).disabled = !projectsAvailable();
  $('projectClose').hidden = !project;
  renderPlayItems();
  // Recent: the three last opened or saved here (or else saved anywhere), the open one aside.
  const list = $('projectRecent');
  try {
    const { projects } = await projectApi.list(), times = recentTimes();
    const when = p => [times[p.id] ?? '', p.savedAt ?? ''].sort().at(-1);
    const recent = projects.filter(p => !p.error && p.id !== project?.doc.id).sort((a, b) => when(b).localeCompare(when(a))).slice(0, 3);
    list.replaceChildren();
    for (const p of recent) {
      const button = text(list, 'button', '', 'projectitem');
      button.type = 'button'; button.dataset.id = p.id;
      text(button, 'strong', p.name ?? p.id);
      text(button, 'small', `${mapLabel(p.map)} · revision ${p.revision} · ${savedWhen(p.savedAt)}${p.recovery ? ' · unsaved changes kept' : ''}`);
      button.title = `Open ${p.name}`;
      button.onclick = () => { showPop(null); loadProject(p); };
    }
    if (!recent.length) text(list, 'div', projects.some(p => p.id === project?.doc.id) ? 'No other projects yet.' : 'No projects yet.', 'empty');
  } catch (e) { list.replaceChildren(`Projects could not be listed: ${e.message}`); }
}
// The game install and the editor's checks (setup.js): a first run asks for the install before anything else.
const setupDialog = createSetupDialog({
  els: { root: $('setupDialog'), form: $('setupForm'), title: $('setupTitle'), intro: $('setupIntro'), found: $('setupFound'),
         folder: $('setupFolder'), browse: $('setupBrowse'), ok: $('setupOk'), close: $('setupClose'), checks: $('setupChecks'),
         message: $('setupMessage'), version: $('setupVersion') },
  // the server lists the new install's maps: open the page afresh on them
  onChosen: () => setTimeout(() => location.reload(), 600) });
// The pieces and lights an actor name stands for (a compile report's entity or target, a prefab test's actor),
// selected and framed. False when none is in the view.
function selectActors(names) {
  const want = new Set(names.flatMap(n => [n, short(n)]));
  const ids = [...roots.values(), ...lightRoots.values()]
    .filter(r => !r.userData.deleted && (want.has(r.userData.source.actor) || want.has(short(r.userData.source.actor))))
    .map(r => r.userData.source.id);
  if (!ids.length) { flashHint(`${short(names[0])} is not in the view`); return false; }
  gizmo.setSelection(ids, ids[0]); editChanged(); frame(allRoots.get(ids[0]));
  return true;
}
const fileDialog = createProjectDialog({
  els: { root: $('fileDialog'), form: $('fileForm'), title: $('fileTitle'), folder: $('fileFolder'), head: $('fileHead'),
         list: $('fileList'), show: $('fileShow'), name: $('fileName'), ok: $('fileOk'), cancel: $('fileCancel'),
         close: $('fileClose'), confirm: $('fileConfirm'), message: $('fileMessage'), output: $('fileOutput') },
  api: projectApi, mapLabel, onLoad: loadProject,
  onSave: ({ name, target, output }) => saveProject(!target ? { name, output } : target.id === project?.doc.id ? { rename: name } : { name, replace: target }),
});
// The build queue (build_queue.js, tools/viewer/buildqueue.py): one controller for the page asks the server about it,
// for the project manager and for the chip in the top bar, which says where the queue is (and its results, until
// Clear or the next Build) and opens the manager. A row of the open project's that starts or ends refreshes its
// build state (its package), even when the server has gone on to the next row. (The chip and that row:
// build_play.js's renderQueueChip and followQueueForProject.)
const queueCall = (method, url, body) => call(method, url, body, { init: { cache: 'no-store' } });
const buildQueue = createQueueController({
  get: () => queueCall('GET', '/manager/queue.json'),
  post: (action, body) => queueCall('POST', action === 'add' ? '/manager/queue' : `/manager/queue/${action}`, body),
  onChange: (state, info) => { renderQueueChip(state, info); projectManager?.queueChanged(state, info); followQueueForProject(state, info); },
});
$('queueChip').onclick = () => showProjectManager();
window.addEventListener('focus', () => buildQueue.refresh());
// The project manager (manager.js): every project and its last build, to install or zip several at once, or to build.
const projectManager = createProjectManager({
  els: { root: $('managerDialog'), form: $('managerForm'), close: $('managerClose'), search: $('managerSearch'), show: $('managerShow'),
         sort: $('managerSort'), all: $('managerAll'), shownLabel: $('managerShown'), list: $('managerList'), count: $('managerCount'),
         pickNone: $('managerPickNone'), allModes: $('managerAllModes'), picked: $('managerPicked'), message: $('managerMessage'),
         pack: $('managerPack'), projectFiles: $('managerProjectFiles'), packChoice: $('managerPackChoice'), packName: $('managerPackName'),
         packNameRow: $('managerPackNameRow'), packAuthor: $('managerPackAuthor'), packInfo: $('managerPackInfo'), packForget: $('managerPackForget'), install: $('managerInstall'), where: $('managerWhere'), build: $('managerBuild'),
         queueBox: $('managerQueue'), queueTitle: $('managerQueueTitle'), queueClock: $('managerQueueClock'),
         queueStep: $('managerQueueStep'), queueStage: $('managerQueueStage'), queueBar: $('managerQueueBar'),
         queueNote: $('managerQueueNote'), queueFailures: $('managerQueueFailures'), queueLive: $('managerQueueLive'),
         queueStop: $('managerQueueStop'), queueResume: $('managerQueueResume'), queueClear: $('managerQueueClear'),
         queueReset: $('managerQueueReset') },
  mapLabel, onOpen: loadProject, onChanged: () => refreshInstalls(),
  reveal: path => projectApi.reveal(path),
  queue: buildQueue, ensureSaved: ensureSavedFor,
});
buildQueue.start();
// The Game maps window (gamemaps.js): what the game install's map records are now, and undoing the editor's changes.
const gameMaps = createGameMaps({
  els: { root: $('gameMapsDialog'), form: $('gameMapsForm'), close: $('gameMapsClose'), search: $('gameMapsSearch'), show: $('gameMapsShow'),
         group: $('gameMapsGroup'), column: $('gameMapsCol'), list: $('gameMapsList'), count: $('gameMapsCount'), offShown: $('gameMapsOff'), onShown: $('gameMapsOn'),
         message: $('gameMapsMessage'), undoAll: $('gameMapsUndoAll'), done: $('gameMapsDone'), where: $('gameMapsWhere') },
  onChanged: () => refreshInstalls(),
});
function showGameMaps() {
  if (modalOpen()) return;
  showPop(null);
  if (placing) stopPlacing();
  gameMaps.show();
}
// The Cache everything window (precache.js): every piece of the game's maps, and every map, read ahead of use.
const precache = createPrecache({
  els: { root: $('cacheModal'), close: $('cacheClose'), pieces: $('cachePieces'), maps: $('cacheMaps'),
         piecesNote: $('cachePiecesNote'), mapsNote: $('cacheMapsNote'), space: $('cacheSpace'), bar: $('cacheBar'),
         barText: $('cacheBarText'), failures: $('cacheFailures'), status: $('cacheStatus'), cancel: $('cacheCancel'),
         done: $('cacheDone'), start: $('cacheStart') },
  onMapsDone: () => refreshMapList(),
});
function showPrecache() {
  if (modalOpen()) return;
  showPop(null);
  if (placing) stopPlacing();
  precache.show();
}
function showProjectManager() {
  if (modalOpen()) return;
  showPop(null);
  if (placing) stopPlacing();
  projectManager.show();
}
function showFileDialog(mode, waitForSave = false) {
  if (builderMode && mode === 'save') return showPrefabDialog(true);
  if (fileDialog.open || (mode === 'save' && !projectsAvailable())) return;
  showPop(null);
  if (placing) stopPlacing();
  return fileDialog.show(mode, { mapId: activeMapId, current: project?.doc.id ?? null, name: mode === 'save' ? project?.doc.name ?? '' : '', waitForSave });
}

// (the last pointer position over the view, for paste, pointer: editor_state.js)
// The building floors a piece is listed on (floor_listings.js): the project's buildings' and the map's own,
// as the Build lists them, and the key of the pieces' edits.
const { editedKey, listingsNow, projectListings } = createFloorListings({
  boxOf, movedBox, originalOf, short, vertexBox,
  // (made further down: called through, since they are not made yet while this runs)
  allBuildings: () => allBuildings(), mapEdits: () => mapEdits(), mapIdOf: b => mapIdOf(b) });
// How far along a line (origin, unit dir) the mouse's ray passes closest: the handle's drag
function alongLine(clientX, clientY, origin, dir) {
  const ray = rayAt(clientX, clientY).ray, w = origin.clone().sub(ray.origin);
  const b = dir.dot(ray.direction), c = ray.direction.dot(ray.direction), d = dir.dot(w), e = ray.direction.dot(w);
  const den = c - b * b;
  return Math.abs(den) < 1e-9 ? null : (b * e - c * d) / den;
}
// The Map grid's handles (map_grid.js, made just below) take the press first.
renderer.domElement.addEventListener('pointerdown', e => {
  if (!startGridDrag(e)) return;
  pointerStart = null; e.stopImmediatePropagation(); e.preventDefault();
}, { capture: true });
renderer.domElement.addEventListener('pointermove', e => {
  if (gridDrag && e.pointerId === gridDrag.pointerId) { moveGridDrag(e); e.stopImmediatePropagation(); return; }
  if (gridTool && !e.buttons) renderer.domElement.style.cursor = gridHit(e.clientX, e.clientY) !== null ? 'grab' : '';
}, { capture: true });
renderer.domElement.addEventListener('pointerup', e => {
  if (!gridDrag || e.pointerId !== gridDrag.pointerId) return;
  e.stopImmediatePropagation(); endGridDrag(true);
}, { capture: true });
renderer.domElement.addEventListener('pointercancel', () => endGridDrag(false));
// The play area, the map's size as the project sets it and the rail's Map grid (map_grid.js): the play area
// drawn, the grid of a size drawn with its new area, and the Map grid's handles, drags and panel (its pointer
// listeners just above call the drags).
const { drawPlayArea, endGridDrag, gridHandleAt, gridHandles, gridHit, moveGridDrag, ownSize, playArea, setGridTool,
        setPlayArea, setStage, startGridDrag, storeysNow } = createMapGrid({
  $, alongLine, boxOf, controls, flashHint, gizmo, projectChanged, rayAt, renderer, showPop, world,
  // (made further down: called through, since they are not made yet while this runs)
  groundWords: levels => groundWords(levels), isMadeSlab: o => isMadeSlab(o),
  refreshGroundGrid: force => refreshGroundGrid(force), sizeNotes: (dims, zoneList) => sizeNotes(dims, zoneList) });

// Take from the view (LWR map packs plan, 4.5): the 3D view as it is now, on a canvas of its own. The renderer keeps no
// drawing buffer, so a frame is drawn here and copied at once (as pieces.paintThumbs copies its pictures), with the
// editor's helpers hidden for that frame: everything in the world but the map's pieces, its lights and its effects'
// likenesses (the grids, the gizmos, the handles, the markers, the play area, the selection's outline), and the pieces
// the game never draws (cover blocks and invisible floors). The next frame draws them again. (Clear map's module,
// which makes the Map picture dialog, is given it: it reads the Effects view's likeness layer, made further down.)
function grabView() {
  const keep = new Set([content, hemisphere, sun, sun.target, likenessLayer]), hidden = [];
  const hide = object => { if (object.visible) { object.visible = false; hidden.push(object); } };
  for (const child of world.children) if (!keep.has(child) && !child.isLight) hide(child);
  for (const root of roots.values()) if (root.userData.source.added?.template?.kind === COVER_KIND) hide(root);
  try {
    renderer.render(world, camera);
    const source = renderer.domElement;
    if (!source.width || !source.height) return null;
    const canvas = document.createElement('canvas');
    canvas.width = source.width; canvas.height = source.height;
    canvas.getContext('2d').drawImage(source, 0, 0);
    return canvas;
  } catch { return null; }
  finally { for (const object of hidden) object.visible = true; }
}
// Clear map, the missions, the ground grid and the map picture (clear_map.js): the landing zones as the project
// has them and the landing's pieces, the ground's height, the Clear map window and the clear, the Missions
// panel and the header's Mission picker, the Map picture dialog, and the ground grid.
const { chooseMission, clearMap, clearPlan, floorStays, groundGrid, groundHeight, groundWords, headerMission,
        headerMissions, isLanding, liveFloorIndex, mapPicture, missionName, missionsPanel, outsideBox, pointOutside,
        readLandingLines, refreshGroundGrid, refreshMissionPicker, showClearMap, showMissions, sizeNotes,
        startMissionPicker, zonesNow } = createClearMap({
  $, addLightRoots, addRoots, banner, cloneGroups, editedKey, flashHint, fromOf, gizmo, grabView, isStream,
  lightViewOnly, ownSize, plural, projectChanged, projectsAvailable, refreshInstalls, refreshLightVisibility,
  removeLightRoots, removeRoots, sceneChanged, setStage, short, showPop, world,
  // (made further down: called through, since they are not made yet while this runs)
  allBuildings: () => allBuildings(), clearedChanged: () => clearedChanged(), cutaway: () => cutaway(),
  explicitZones: () => explicitZones(), liveVolumes: () => liveVolumes(),
  missionFloorLost: o => missionFloorLost(o), missionReached: o => missionReached(o),
  placeMissionGizmo: () => placeMissionGizmo(), refreshLandingZones: () => refreshLandingZones(),
  refreshSpawnMarkers: () => refreshSpawnMarkers(), setMissionMoves: next => setMissionMoves(next),
  spawnFamilyBuilds: () => spawnFamilyBuilds(), spawnsAvailable: () => spawnsAvailable(),
  zoneSoldiers: (z, st) => zoneSoldiers(z, st), zoneState: () => zoneState() });

// The landing zones' layer, shown as View options' Landing zones says (the Landing zones view: zones_wiring.js,
// made below; the Spawns view, made just below, shows the zones too).
const LANDING_SHOWN = 'workshop.landingZones';
const landingLayer = new THREE.Group(); world.add(landingLayer);
landingLayer.visible = recall(LANDING_SHOWN) !== '0';
// The Spawns view and the mission moves (spawns_wiring.js): the markers, the view, the picked one's panel and
// gizmo, the project's moves and edits of spawn points and mission objects, and the spawn rule.
const { baseSpawnOf, bombHelperFix, cancelMissionGizmo, copySpawn, deleteSpawn, editBaseSpawn, editedCopies,
        editedSpawns, editSpawnCopy, loadSpawnRules, missionFloorLost, missionGizmo, missionGizmoWanted, missionKey,
        missionOverrides, missionProxy, missionReached, moveMissionGroup, NORMAL_SPAWNS, pickSpawnMarker,
        placeMissionGizmo, placeSpawn, refreshSpawnMarkers, resetBaseSpawn, scaleSpawnMarkers, setMissionMoves,
        setNormalSpawns, setPickedSpawn, setSpawnRule, setSpawnsShown, showSpawn, spawnAddEntries, spawnAt, spawnBoxNow,
        spawnClick, spawnCopyRecords, spawnDeleted, spawnEntry, spawnFamilyBuilds, spawnLayer, spawnMovable, spawnPanel,
        spawnsAvailable, spawnsShown, startSpawnPlacing, stopSpawnPlacing, streamObjects, syncSpawnFilters,
        syncSpawnRule, TURNED_KINDS } = createSpawnsWiring({
  $, camera, controls, flashHint, floorStays, gizmo, groundHeight, headerMission, headerMissions, isStream,
  landingLayer, lightButton, movedMatrix, pick, plural, projectsAvailable, rayAt, renderer, restingHint,
  setLightsShown, short, text, tileCorner, world,
  // (made further down: called through, since they are not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep),
  gameToView: p => gameToView(p), groundAt: (x, y, fromZ) => groundAt(x, y, fromZ),
  numberField: (parent, label, value, options) => numberField(parent, label, value, options),
  pickZone: id => pickZone(id), setEffectsShown: on => setEffectsShown(on), setVolumesShown: on => setVolumesShown(on),
  setZonesShown: on => setZonesShown(on), stopPickBox: () => stopPickBox(),
  zoneHit: (clientX, clientY) => zoneHit(clientX, clientY), zoneState: () => zoneState() });

// The Effects view (effects_wiring.js): the map's effects, sounds and lens flares as roots, the view, the likeness,
// the panel with the Wave preview and the values, and the project's records of effects and sounds.
const { addedEffect, addedEffectOf, addEffectRoots, applyEffectRecord, buildEffects, clearEffectEdits, drawEffectShape,
        drawLikenessPane, effectAt, effectEdited, effectFollows, effectLayer, effectNow, effectPicture,
        effectShapes, effectSource, effectsShown, effectState, effectTip, effectValuesEditable, effectViewOnly,
        frameEffect, ghostLikeness, ghostLikenesses, hoverLikeness, likenesses, likenessLayer, likenessPane,
        numberField, pickEffect, pickEffectAt, playWave, refreshEffects, removeEffectRoots,
        setEffectsShown, setEffectStays, setEffectValues, setLikeness, setNormalEffects, stepGhostLikenesses,
        stepLikenesses, stopWave } = createEffectsWiring({
  $, actorPose, assetUrl, baseMatrix, camera, controls, effectTemplate, flashHint, gizmo, gltfLoader, isForeignTarget,
  isStream, lightButton, ownerRoot, plural, pointOutside, renderer, sceneChanged, setLightsShown,
  setPickedSpawn, setSpawnsShown, short, text, texture, track, viewport, world,
  // (made further down: called through, since they are not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep),
  carried: (point, from, to) => carried(point, from, to), setVolumesShown: on => setVolumesShown(on),
  setZonesShown: on => setZonesShown(on), stopPickBox: () => stopPickBox(), zoneState: () => zoneState() });
// A game point (x, y, z) as a point of the view, whose basis is x, up, y (the Spawns and Landing zones views and the
// test hooks)
const gameToView = p => new THREE.Vector3(p[0], p[2], p[1]);
// The Landing zones view (zones_wiring.js): the zones drawn, the view, a zone picked with its gizmo and panel, the
// zones changed and added, and what follows a change of the cleared mark.
const { cancelZoneGizmo, carried, clearedChanged, copyZone, deleteZone, explicitZones, movedLandingActors, pickZone,
        placeZone, placeZoneGizmo, refreshLandingZones, setZoneGizmoMode, setZones, setZonesShown, startZonePlacing,
        stopZonePlacing, turnZone, zoneEntries, zoneGizmo, zoneGizmoHelper, zoneGizmoWanted, zoneHit, zoneProxy,
        zoneSoldiers, zoneState } = createZonesWiring({
  $, banner, camera, controls, editChanged, flashHint, floorStays, gameToView, gizmo, groundHeight, headerMission,
  isLanding, landHere, LANDING_SHOWN, landingLayer, lightButton, ownSize, plural, projectChanged, projectsAvailable,
  rayAt, refreshGroundGrid, refreshLightVisibility, refreshMissionPicker, renderer, restingHint,
  setEffectsShown, setLightsShown, setSpawnsShown, tileCorner, world, zonesNow,
  // (made further down: called through, since they are not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep),
  cutaway: () => cutaway(), setVolumesShown: on => setVolumesShown(on), stopPickBox: () => stopPickBox() });
// The Buildings view and box select (buildings_wiring.js): the project's buildings as boxes and the map's own, the
// view, its handles, drags and panel, the Normal button's Floor boxes, and box select.
const { addVolumes, allBuildings, buildingsFromVolumes, copyVolumes, deleteVolumes, drawCursorRings, endPickDrag,
        endVolumeDrag, FACES, handlePoint, hoverVolumeHandle, liveVolumes, makeVolume, mapEdits, mapIdOf,
        mapRestoreChange, movePickDrag, moveVolumeDrag, newBuilding, newBuildingId, ownVolumeLayer, pasteVolumes,
        PICK_SLACK, pickBoxEdge, pickMoveNear, pickMovePoint, pickOwn, pickVolumeEdge, recordVolumes, refreshPickBox,
        refreshVolumes, restoreMapBuildings, savedBuildings, setBoxesShown, setBuildings, setOwnPicked, setPickTool,
        setVolumeBox, setVolumesShown, setVolumeTool, spawnVolumeHandle, startPickDrag, startVolumeDrag, stopPickBox,
        takePickBox, updateVolumeHandles, viewPoint, volumeBox, volumeClick, volumeHandleNear, volumeHint,
        volumePanel } = createBuildingsWiring({
  $, boxOf, builderBounds, camera, chosenStorey, editBaseSpawn, editChanged, editedCopies, editedKey, editedSpawns,
  editSpawnCopy, effectsShown, effectViewOnly, flashHint, gizmo, HANDLE_PICK, isStream, lightViewOnly, missionGizmo,
  pick, plural, projectListings, projector, projectsAvailable, rayAt, refreshSpawnMarkers, renderer, restingHint,
  selectionWords, setEffectsShown, setZonesShown, short, showPop, spawnBoxNow, spawnEntry, spawnMovable,
  spawnsShown, storeysNow, syncLights, text, volumeLayer, world,
  // (made with the selection, just below: called through, since it is not made yet while this runs)
  select: (id, add, keep) => select(id, add, keep),
  // (made with Select all of a kind and the clipboard, below: called through, since they are not made yet while this
  // runs)
  copySelection: cut => copySelection(cut), kindButton: () => kindButton(),
  // (made with Delete and Reset, below: called through, since it is not made yet while this runs)
  deleteSelection: quiet => deleteSelection(quiet),
  // (made with the cutaway, below: called through, since it is not made yet while this runs)
  floorOptions: () => floorOptions() });
// The selection (selection.js): select and the piece panel it fills, a cover piece's too, and the selected piece's
// marks (its highlight, its ladder's ends, its grid chip); after the Buildings view, the last factory whose functions
// it calls (nothing of it runs as the page loads).
const { gridNow, ladderNow, refreshGrid, refreshHighlight, select } = createSelection({
  $, actorPose, allBuildings, AREA_SHOWN, areaOwner, boxOf, copyable, copyText, editChanged, field, flagContract,
  flagSource, foreignCost, foreignNote, gizmo, gridOrigin, groupChip, highlight, isLanding, isStream, ladderMarks,
  listingsNow, missionName, ownSize, pickEffect, plural, RECIPE_NOTE, recipeOf, rootName,
  setEffectsShown, setLightsShown, setVolumesShown, setZonesShown, short, text, tileCorner });
// Select all of a kind (select_kind.js): every drawn piece or effect of a picked one's kind, the button and the
// selection made; after the Buildings view, whose box select's slack it reads.
const { kindButton, selectKind } = createSelectKind({
  $, boxOf, effectsShown, effectViewOnly, flagKey, flashHint, gizmo, isStream, PICK_SLACK, plural, select, short,
  stopPickBox });
// Cover blocks and invisible floors (cover_wiring.js): a cover piece's recipe, template and the Add panel's
// Invisible kind, the ground under an invisible floor, the piece panel's cover section, and the handles on a
// picked cover piece and their drags.
const { askLineCollision, collisionMesh, commitCover, coverEntries, coverFacesNow, coverHandleNear, coverHandlePoint,
        coverOf, coverPanel, coverRecipe, coverVersion, endCoverDrag, fitFloor, FLOOR_CLEARANCE, groundAt,
        handleCover, hoverCoverHandle, moveCoverDrag, setCover, startCoverDrag,
        updateCoverHandles } = createCoverWiring({
  $, alongLine, camera, editChanged, gizmo, gridOrigin, HANDLE_PICK, materialCache, pickables, PL, projector, renderer,
  restingHint, sceneChanged, select, showPop, track, volumeHint, world });
// Copy, paste and placing (clipboard.js): a clip of the selection, a paste, the preview placed with a click,
// the Add panel shown and an entry of it placed, and a copy dragged off with Shift; after the cover blocks,
// whose floor's clearance it reads, and the Buildings view, whose own buildings' layer it reads.
const { boxMatrix, chooseEntry, chooseLibraryEntry, copyDragBegin, copyDragEnd, copySelection, dropTarget, entryParts,
        groupTree, keepRecipe, LIBRARY_SCOPES, linkOf, mapChain, matrixBox, moveGhost, paste, pasteSnapshot,
        pieceRecipes, placeAt, placeMove, previewGroup, setLibraryScope, showPieces, snapshot, startPlacing,
        stopPlacing } = createClipboard({
  $, actorPose, addedEffect, addedLight, addedObject, addEffectRoots, addLightRoots, addRoots, askLineCollision,
  assemblyOf, banner, boundsOf, buildRoots, busy, BUSY_PIECES, busyStart, chosenStorey, cloneGroup, cloneGroups,
  copyVolumes, coverEntries, effectFollows, effectTemplate, effectViewOnly, flashHint, FLOOR_CLEARANCE,
  floorSupportOf, fromOf, ghostEdges, ghostLikeness, ghostLine, gizmo, gridOrigin, groundAt, groundHeight, groupChain,
  hoverLikeness, isForeignTarget, libraryTemplate, lightClip, lightEntries, lightViewOnly, liveFloorIndex, loaded,
  madeShape, makeVolume, materialCache, materialKey, memberOf, memberRecord, newBuildingId, nextFrame, ownerRoot,
  ownVolumeLayer, partsOf, pasteVolumes, pick, plural, prefabPlacementProblem, rayAt, recipeOf, removeEffectRoots,
  removeLightRoots, removeRoots, restingHint, sceneChanged, selectionWords, setLightsShown, setNormalLights,
  setVolumeBox, short, spawnAddEntries, startSpawnPlacing, startZonePlacing, stopSpawnPlacing, stopZonePlacing, text,
  tileCorner, unscaled, volumeBox, world, zoneEntries,
  // (made further down: called through, since they are not made yet while this runs)
  deleteSelection: quiet => deleteSelection(quiet), stopWallDrawing: () => stopWallDrawing() });
// The made pieces (made_handles.js and the four modules below, made in their code's order: ARCHITECTURE.md, "The
// page"). A made piece: what it is, its look's donor, its state and its changes (each one undo step), and its
// handles and drags; the modules below are given its functions.
const { cancelPointDrag, changeWall, endWallDrag, handleWall, hoverWallHandle, isMade, isMadeGround, isMadeSlab,
        isMadeWall, lookWall, madeRoot, madeWallRoot, moveWallDrag, placePointGizmo, pointGizmo, refreshJoins,
        releaseRockPoint, rockCorners, setWall, startWallDrag, updateWallHandles, wallHandleNear, wallHandlePoint,
        wallHandlesNow, wallLookOf, wallPiecesWords, wallState, wallTemplate } = createMadeHandles({
  actorPose, alongLine, assetUrl, camera, controls, editChanged, flashHint, gizmo, gltfLoader, HANDLE_PICK,
  libraryTemplate, movedMatrix, partsOf, pickables, plural, projector, rayAt, refreshHighlight, renderer, restingHint,
  sceneChanged, select, short, showPop, track, volumeHint, world,
  // (made further down: called through, since they are not made yet while this runs)
  groundPanel: root => groundPanel(root), slabPanel: root => slabPanel(root), startWallDraw: e => startWallDraw(e),
  wallPanel: root => wallPanel(root) });
// The made pieces' looks (made_looks_wiring.js): the look each tool draws in, the look picker's samples and choice,
// the eyedropper, a made piece's look changed and its Look row.
const { closeLookPicker, lookPickAt, lookRow, openLookPicker, prepareSample, setMadeLook, startLookPick, stopLookPick,
        storedLook } = createMadeLooksWiring({
  $, assetUrl, boundsOf, changeGroups, flashHint, fromOf, gizmo, gltfLoader, isMadeGround, isMadeSlab, isMadeWall,
  isPlain, madeRequest, madeRoot, madeShape, material, materialCache, materialKey, memberOf, memberRecord, movedMatrix,
  pasteSnapshot, pick, plainLook, plural, previewGroup, renderer, short, showPieces, stopPlacing, track, wallState,
  wallTemplate,
  // (made further down: called through, since they are not made yet while this runs)
  deleteNow: (quiet, only) => deleteNow(quiet, only),
  startWallDrawing: (look, options) => startWallDrawing(look, options), stopWallDrawing: () => stopWallDrawing() });
// The made pieces' drawing (made_drawing.js): the Build menu, and a wall, room, floor, roof or ground shape drawn.
const { BUILD_TOOLS, endWallDraw, moveWallDraw, startBuild, startWallDraw, startWallDrawing, stopWallDrawing, wallGhost,
        wallHint } = createMadeDrawing({
  $, addVolumes, askLineCollision, busyStart, camera, flashHint, fromOf, gizmo, gridOrigin, groundAt, groundHeight,
  isMadeWall, lockAsGroup, lookWall, madeRequest, movedMatrix, newBuilding, pasteSnapshot, pick, plainLook, plural,
  rayAt, renderer, restingHint, showPieces, stopPlacing, stopSpawnPlacing, stopZonePlacing, text, wallTemplate,
  world });
// The piece panel's sections of a made piece (made_panel.js): the Wall, Floor, Ground and Room sections, with the
// openings and holes, and what their buttons do.
const { addWallOpening, deleteWallOpening, groundPanel, roomOfSelection, slabPanel,
        wallPanel } = createMadePanel({
  $, boxOf, changeWall, flashHint, gizmo, handleWall, isMadeGround, isMadeSlab, isMadeWall, isPlain, liveKeys,
  liveMembers, lookRow, madeRoot, madeWallRoot, openLookPicker, originalOf, plainLook, plural, selectionGroup,
  setMadeLook, setWall, short, wallLookOf, wallPiecesWords, wallState,
  // (made further down: called through, since it is not made yet while this runs)
  breakRow: (kind, g, keeps) => breakRow(kind, g, keeps) });
// Break and Repair (made_breaking.js): blasts set off on a made wall, floor or roof, or on one of the map's own
// fracturing pieces, the Break rows and tool, and a broken piece drawn.
const { breakAt, breakRow, drawBroken, mapBreakable, startBreak, stopBreak } = createMadeBreaking({
  $, changeWall, flashHint, gizmo, isMadeSlab, isMadeWall, madeRoot, pick, plural, renderer, select, stopLookPick,
  stopPlacing, stopWallDrawing, world });
// Delete, Reset piece and Reset all (delete_reset.js): a large step under the busy mark, Delete, Reset piece and
// Reset all, each one undo step; made after the factories whose functions they call (nothing of them runs as
// the page loads).
const { deleteNow, deleteSelection, resetAll, resetSelected, undoStep } = createDeleteReset({
  addEffectRoots, addLightRoots, addRoots, baseMatrix, busy, BUSY_PIECES, clearedChanged, cloneGroups, copyable,
  deleteVolumes, drawBroken, effectViewOnly, flashHint, gizmo, isStream, liveVolumes, mapEdits, mapRestoreChange,
  nextFrame, plural, refreshLandingZones, refreshLightVisibility, refreshMissionPicker, removeEffectRoots,
  removeLightRoots, removeRoots, sceneChanged, selectedBoxes, selectionWords, setLightValues, setMissionMoves, setStage,
  syncSpawnRule, valuesEdited });
$('playAreaToggle').onchange = e => { setPlayArea(e.target.checked); e.target.blur(); };
// The cutaway, the tile grid and the Floor tiles overlay (cutaway.js): which pieces are drawn and how each is cut,
// the tile grid round the selection, the saved floor tiles overlay, and the Floor picker's buttons.
const { cutaway, drawFloorTiles, floorOptions, floorTileSelect, floorTip, sceneViewOptions,
        updateTileGrid } = createCutaway({
  $, allBuildings, cutMaterials, editedKey, flashHint, gizmo, grid, helperMaterial, isStream, listingsNow,
  movedLandingActors, plural, rayAt, refreshPickBox, segButton, select, short, text, touchShadows, viewport, world });
async function open() {
  stopPickBox();
  setBoxesShownValue(false); setNormalLightsValue(false); setLightsOn(false); setLightsShownValue(false); setZonesOn(false);
  setEffectsOn(false); setPickedEffect(null); setNormalEffectsValue(false); effectLayer.visible = false; setEffectsDirty(true); stopWave();
  setSpawnsOn(false); setPickedSpawnValue(null); setSpawnZonePick(null); setNormalSpawnsValue(recall(NORMAL_SPAWNS) === '1'); setSpawnRulesData(null);
  const parameters=new URLSearchParams(location.search);
  loadingState('Opening the map list…');
  const mapResponse=await fetch('/maps.json');
  if(!mapResponse.ok)throw Error('Could not load the base map list. Restart the viewer server after updating it.');
  setMapCatalogue(await mapResponse.json());
  // A first run: no game install set and nothing exported yet. Ask for the install before anything else.
  const setup = await setupApi.status(false).catch(() => null);
  if (setup) $('helpVersion').textContent = `${setup.name} ${setup.version} (preview)`;
  if (setup && !setup.game.folder && !mapCatalogue.maps.some(map => map.ready)) {
    loadingState('Choose your game install to start.');
    $('status').textContent = 'No game install';
    $('mapTitle').textContent = 'None';
    setupDialog.show({ firstRun: true });
    return new Promise(() => {});
  }
  setActiveMapId(builderMode ? null : parameters.get('map') || mapCatalogue.defaultMap);
  const activeMap=mapCatalogue.maps.find(map=>map.id===activeMapId);
  makeMapBrowser(activeMap, parameters);
  if (builderMode) {
    setData(emptyPrefabScene());
    await startScene({ parameters, familiesAsked: fetch('/families.json').then(r => r.json()), mapName: 'Prefab' });
    return;
  }
  $('mapTitle').textContent=activeMap?.label ?? 'None';
  $('mapButton').title=activeMap ? `Base map: ${activeMap.label} (${activeMap.name})${activeMap.checked ? ', checked in the game' : ''}. Choose another (M)` : 'Choose a base map (M)';
  if(!activeMap || !activeMap.ready) {
    // A map not listed, or listed and not exported yet: the browser opens on it and prepares it (export on first open).
    loadingState(activeMap ? `Preparing ${activeMap.label}: the first open of a map takes about half a minute.` : 'Choose a base map.');
    $('status').textContent = activeMap ? 'Preparing the map' : 'No map';
    mapBrowser.show(activeMap ? activeMapId : null, activeMap ? { prepare: true }
      : { message: activeMapId ? `No map called ${activeMapId} is listed. Choose one.`
        : 'Choose a base map to start. A map opens in about half a minute the first time, while the editor prepares it.' });
    return new Promise(() => {});
  }
  setCachePrefix('/cache/'+encodeURIComponent(activeMapId)+'/');
  const requestedScene = parameters.get('scene') || 'scene.json';
  if (!/^(scene|preview-\d+)\.json$/.test(requestedScene)) throw Error('Invalid scene selection');
  // The bar: the layout file's download is the first tenth, building the pieces (their meshes and textures
  // downloading meanwhile) the rest.
  const mapName = activeMap.label;
  loadingState(`Opening ${mapName}: reading its layout…`, 0);
  const familiesAsked = fetch(`/maps/${encodeURIComponent(activeMapId)}/families.json`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  setData(await fetchJson(cachePrefix+requestedScene, share => loadingState(`Opening ${mapName}: reading its layout…`, 0.1 * share)));
  await startScene({ parameters, familiesAsked, mapName });
}
// Both maps and the prefab workspace start the same editor on a scene. Each part of the scene is started by the
// module that owns it (scene_start.js: the page's own parts), in the order the page always started them.
async function startScene({ parameters, familiesAsked, mapName }) {
  setMergedBuildings(null);
  // No layout menu any more (the user's choice, 7 November): a patch preview (Bar's EXP-07 and EXP-08 layouts)
  // opens only from its address, ?scene=preview-<n>.json.
  showSceneTitle($);
  // Configure light data before the first lit material compiles.
  setLighting(createMapLighting({ world, sun, hemisphere, scene: data, maxTextureSize:renderer.capabilities.maxTextureSize }));
  showSceneMenus($, projectsAvailable);
  setOwnGrid(null);
  readLandingLines();
  drawPlayArea();
  lightingModes();
  // What the original layout's missions stream into the map (export 13), shown for reference and never edited.
  const streamObjects = data.preview ? [] : Object.values(data.streams || {}).flatMap(s => s.objects);
  chooseMission(parameters.get('mission') ?? '0');
  if (parameters.get('project') && parameters.get('mission')?.startsWith('kind:')) setAskedPick(parameters.get('mission'));
  await buildPieces(streamObjects, mapName);
  const streamLights = data.preview ? [] : Object.values(data.streams || {}).flatMap(s => s.lights || []);
  // A patch preview's layout is not the map's: its pieces keep their classes' families, without assemblies.
  const familyTable = await familiesAsked;
  if (!familyTable) console.warn('No families from the server: restart the viewer server after updating it');
  useMapFamilies(familyTable && (data.preview ? { ...familyTable, assemblies: [] } : familyTable));
  // the map's own buildings that can be edited, as boxes (a project's records replace them when it opens)
  setBuildings([]);
  if (data.scope === 'map' && !data.preview) buildLights(streamLights);
  buildEffects();
  lightButton();
  startMissionPicker();
  sceneViewOptions(streamObjects);
  placeObjects(); floorOptions(); frame();
  applyLighting = applyMapLighting;
  applyLighting();
  $('loading').hidden = true;
  // the ground grid and the landing zones, now that the pieces are on the map (Clear map plan, sections 3 and 4), and
  // the mission's objects (mission types plan, C2)
  refreshGroundGrid(); refreshLandingZones(); refreshSpawnMarkers(); loadSpawnRules();
  showImportNotes($, text, short, plural);
  showLinked($);
  void refreshInstalls();     // the header's Play button goes by them
  if (!projectsAvailable()) $('projectButton').title = 'Project: open one (Ctrl+O). Saving needs the map\'s original layout: open the map from the map browser (M)';
  prepareOpened(familyTable, mapCatalogue);
  if (builderMode) {
    builderPage();
    setLibraryScope('all');
    await openPrefabDocument(prefabParameter);
    void prefabTest.reconnect();
  } else if (parameters.get('project')) await openProject(parameters.get('project'));
  window.viewer = createTestApi({
    $, addVolumes, addWallOpening, allBuildings, applyPrefabDocument, applyState, bombHelperFix, boxOf, BUILD_TOOLS,
    builderDocument, builderRecords, buildingsFromVolumes, camera, changes, choosePrefab, chosenStorey, clearMap,
    clearPlan, closeLookPicker, controls, copySpawn, copyVolumes, coverFacesNow, coverHandlePoint, coverRecipe,
    deleteSpawn, deleteVolumes, dirty, dropTarget, editBaseSpawn, editSpawnCopy, editState, effectNow, effectShapes,
    effectViewOnly, FACES, fileDialog, floorData, frame, gameToView, ghostLikenesses, gizmo, goTo, grid, gridHandleAt,
    gridHandles, gridNow, groundAt, groundGrid, groundHeight, handleCover, handlePoint, handleWall, headerMissions,
    hemisphere, highlight, isPlain, keepRecovery, ladderMarks, ladderNow, landingLayer, libraryTemplate, lightPanel,
    lightRecords, lightShapes, likenesses, likenessPane, listingsNow, liveKeys, loaded, madeRoot, mapEdits, mapPicture,
    memberOf, missionGizmo, missionProxy, missionsPanel, movedLandingActors, moveMissionGroup, newBuilding,
    openLookPicker, openPrefabDocument, outsideBox, ownVolumeLayer, pasteSnapshot, pasteVolumes, pick, pickables,
    pickBoxEdge, pickEffect, pickLight, pickMovePoint, pickVolumeEdge, pickZone, placeMove, placeSpawn, plainLook,
    playArea, playWave, pointGizmo, prefabClip, prefabPlacementProblem, prefabRecords, projector, recipeOf,
    recordVolumes, refreshEffects, refreshPickBox, refreshSpawnMarkers, renderer, resetBaseSpawn, restoreMapBuildings,
    rockCorners, roomOfSelection, saveBuilder, savedBuildings, savePrefab, saveProject, select, SESSION, setBinding,
    setBoxesShown, setCover, setEffectsShown, setEffectStays, setGridTool, setLevelSnap, setLibraryScope,
    setLightsShown, setLikeness, setMadeLook, setNormalEffects, setNormalLights, setNormalSpawns, setNormalView,
    setPickedSpawn, setPickTool, setSnapMode, setSolo, setSpawnRule, setSpawnsShown, setVolumeBox, setVolumesShown,
    setVolumeTool, setZones, setZonesShown, showClearMap, showMissions, showPieces, showPrepare, showSpawn, snapshot,
    spawnAddEntries, spawnAt, spawnBoxNow, spawnDeleted, spawnEntry, spawnLayer, spawnVolumeHandle, startBuild,
    startLookPick, startSpawnPlacing, startWallDrawing, stopWallDrawing, stopWave, storedLook, streamObjects, sun,
    syncSpawnFilters, takePickBox, updateTileGrid, viewPoint, volumeBox, wallHandlePoint, wallHandlesNow, wallState,
    world, zoneGizmo, zoneGizmoHelper, zoneHit, zoneProxy, zonesNow });
}

$('statsToggle').checked = recall('workshop.stats') === '1';
$('statsLine').hidden = !$('statsToggle').checked;
$('statsToggle').onchange = e => { $('statsLine').hidden = !e.target.checked; remember('workshop.stats', e.target.checked ? '1' : '0'); };
$('sourceDetails').open = recall('workshop.sourceDetails') === '1';
// The piece panel's folding sections (Group, Align, Flags, Place) keep how they were left; a section's info button
// shows or hides its how-to text (the .how notes), which is out of sight until asked for.
for (const fold of document.querySelectorAll('details[data-fold]')) {
  const key = `workshop.fold.${fold.dataset.fold}`, kept = recall(key);
  if (kept) fold.open = kept === '1';
  fold.addEventListener('toggle', () => remember(key, fold.open ? '1' : '0'));
}
for (const button of document.querySelectorAll('.howbutton')) {
  button.onclick = e => {
    e.preventDefault(); e.stopPropagation();
    const box = button.closest('.lightbox, .fold, .panel'), on = box.classList.toggle('showhow');
    button.setAttribute('aria-expanded', String(on));
    if (on && box.tagName === 'DETAILS') box.open = true;
  };
}
$('sourceDetails').ontoggle = e => remember('workshop.sourceDetails', e.target.open ? '1' : '0');
// Typed pose: a changed field moves the selection there (one undo step); Escape puts the field back.
poseInputs.forEach((input, i) => {
  input.addEventListener('change', () => {
    const pose = gizmo.pose(), value = Number(input.value);
    if (!pose || input.value.trim() === '' || !Number.isFinite(value)) { editChanged(); return; }
    if (i < 3) { const location = [...pose.location]; location[i] = value; gizmo.setPose(location, null); }
    else { const rotation = [...pose.rotation]; rotation[i - 3] = value; gizmo.setPose(null, rotation); }
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') input.blur();
    else if (e.key === 'Escape') { input.blur(); editChanged(); }
  });
});
$('mission').onchange = e => {
  chooseMission(e.target.value);
  const parameters = new URLSearchParams(location.search);
  if (missionPickValue !== '0') parameters.set('mission', missionPickValue); else parameters.delete('mission');
  history.replaceState(null, '', `${location.pathname}?${parameters}`);
  // a streamed piece that goes out of view leaves the selection
  if (isStream(allRoots.get(selected)?.userData.source) && !streamSet.has(allRoots.get(selected).userData.source.stream)) select(null);
  refreshLightVisibility();
  refreshSpawnMarkers(); placeMissionGizmo();     // (a marker of the mission before goes, with its gizmo)
  setEffectsDirty(true);     // (the Effects view shows the streams of the mission picked)
  cutaway();
};
segmented($('floor'), () => { cutaway(); setGhostDirty(true); restingHint(); });
$('hideHelpers').onchange = () => cutaway();
segmented($('scenery'), () => {cutaway();frame();refreshLightVisibility();setEffectsDirty(true);});
$('frame').onclick = () => frame();
$('selected').onclick = () => selected && frame(allRoots.get(selected));
$('grid').onchange = e => { grid.visible = e.target.checked; setTileKey(null); };
let applyLighting = () => {};
segmented($('lighting'), () => applyLighting());
// Update every base and cutaway material, not only those currently assigned, so
// changing the floor cut afterwards keeps the chosen wireframe state.
$('wire').onchange = e => {
  for (const mat of new Set([...pickables.map(p => p.userData.baseMaterial), ...cutMaterials.values()])) mat.wireframe = e.target.checked;
};
$('exposure').oninput = e => { renderer.toneMappingExposure = Number(e.target.value); };
let pointerStart;
// The Buildings view's drags (a box's face handle, the New box tool) take the press first.
// A cover piece's handles likewise (cover-block-handles-plan.md).
renderer.domElement.addEventListener('pointerdown', e => {
  if (!startVolumeDrag(e) && !startCoverDrag(e) && !startWallDrag(e) && !startPickDrag(e)) return;
  pointerStart = null; e.stopImmediatePropagation(); e.preventDefault();
}, { capture: true });
renderer.domElement.addEventListener('pointermove', e => {
  if (volumeDrag) { if (e.pointerId === volumeDrag.pointerId) moveVolumeDrag(e); e.stopImmediatePropagation(); return; }
  if (coverDrag) { if (e.pointerId === coverDrag.pointerId) moveCoverDrag(e); e.stopImmediatePropagation(); return; }
  if (wallDrag) { if (e.pointerId === wallDrag.pointerId) moveWallDrag(e); e.stopImmediatePropagation(); return; }
  if (wallDrawing?.start) { if (e.pointerId === wallDrawing.pointerId) moveWallDraw(e); e.stopImmediatePropagation(); return; }
  if (pickDrag) { if (e.pointerId === pickDrag.pointerId) movePickDrag(e); e.stopImmediatePropagation(); return; }
  if ((volumesOn || pickBox || spawnVolumeHandle()) && !gizmo.controls.dragging && e.buttons === 0)
    hoverVolumeHandle(volumeHandleNear(e.clientX, e.clientY) ?? (pickBox && pickMoveNear(e.clientX, e.clientY) ? 'move' : null));
  else if (!gizmo.controls.dragging && e.buttons === 0) { hoverCoverHandle(coverHandleNear(e.clientX, e.clientY)); hoverWallHandle(wallHandleNear(e.clientX, e.clientY)); }
}, { capture: true });
renderer.domElement.addEventListener('pointerup', e => {
  if (pickDrag && e.pointerId === pickDrag.pointerId) { e.stopImmediatePropagation(); endPickDrag(true); return; }
  if (coverDrag && e.pointerId === coverDrag.pointerId) { e.stopImmediatePropagation(); endCoverDrag(true); return; }
  if (wallDrag && e.pointerId === wallDrag.pointerId) { e.stopImmediatePropagation(); endWallDrag(true); return; }
  if (wallDrawing?.start && e.pointerId === wallDrawing.pointerId) { e.stopImmediatePropagation(); endWallDraw(e.shiftKey); return; }
  if (!volumeDrag || e.pointerId !== volumeDrag.pointerId) return;
  e.stopImmediatePropagation(); endVolumeDrag(true);
}, { capture: true });
renderer.domElement.addEventListener('pointercancel', () => {
  endVolumeDrag(false); endCoverDrag(false); endWallDrag(false); endPickDrag(false);
  if (wallDrawing?.start) { wallDrawing.start = null; wallDrawing.pointerId = null; wallGhost.visible = false; wallHint(); }
});
// A light's drag handle under the press takes it, ahead of the gizmo, the camera and picking (capture listeners run
// before the controls' own on the canvas).
renderer.domElement.addEventListener('pointerdown', e => {
  if (!startLightDrag(e)) return;
  pointerStart = null; e.stopImmediatePropagation(); e.preventDefault();
}, { capture: true });
renderer.domElement.addEventListener('pointermove', e => {
  if (lightDrag) { if (e.pointerId === lightDrag.pointerId) moveLightDrag(e); return; }
  if (!gizmo.controls.dragging && e.buttons === 0) hoverHandle(handlesNear(e.clientX, e.clientY)[0]?.h.key ?? null);
}, { capture: true });
renderer.domElement.addEventListener('pointerup', e => {
  if (!lightDrag || e.pointerId !== lightDrag.pointerId) return;
  e.stopImmediatePropagation(); endLightDrag(true);
}, { capture: true });
renderer.domElement.addEventListener('pointercancel', () => endLightDrag(false));
// A press on a gizmo handle never also picks the piece behind it.
renderer.domElement.addEventListener('pointerdown', e => {
  pointerStart = gizmo.busy() || (zoneGizmo.enabled && (zoneGizmo.dragging || zoneGizmo.axis !== null))
    || (pointGizmo.enabled && (pointGizmo.dragging || pointGizmo.axis !== null))
    || (missionGizmo.enabled && (missionGizmo.dragging || missionGizmo.axis !== null)) ? null : [e.clientX,e.clientY];
});
renderer.domElement.addEventListener('pointerup', e => {
  if (!pointerStart || Math.hypot(e.clientX-pointerStart[0], e.clientY-pointerStart[1]) > 4) return;
  // While placing (a paste, or from the piece list), a click places the piece instead of picking one.
  if (placing) { if (e.button === 0) placeAt([e.clientX, e.clientY], e.shiftKey); return; }
  // the Buildings view: only its boxes are picked
  if (volumesOn) { if (e.button === 0) volumeClick(e); return; }
  if (assigning) { const target = pick(e.clientX, e.clientY); if (target) assignOwner(target); else flashHint('Click the glowing piece'); return; }
  if (zonePlacing) { if (e.button === 0) placeZone(e.clientX, e.clientY); return; }
  if (spawnPlacing) { if (e.button === 0) placeSpawn(e.clientX, e.clientY); return; }
  if (breaking) { if (e.button === 0) breakAt(e.clientX, e.clientY); return; }
  if (lookPicking) { if (e.button === 0) lookPickAt(e.clientX, e.clientY); return; }
  // the Landing zones view: only zones are picked; a click beside them lets the picked one go
  if (zonesOn) { if (e.button === 0) { const z = zoneHit(e.clientX, e.clientY); pickZone(z ? z.id : null); } return; }
  // the Effects view: only its markers are picked; a click beside them lets the picked one go
  if (effectsOn) { if (e.button === 0) pickEffectAt(e.clientX, e.clientY, e.ctrlKey || e.shiftKey || e.metaKey); return; }
  // the Spawns view: only its markers (and, to describe them, landing zones) are picked, never a piece
  if (spawnsOn) { if (e.button === 0) spawnClick(e); return; }
  // with the Normal button's Effects switch, a marker is picked ahead of the light or piece behind it
  const fx = effectsShown() && !lightsOn ? effectAt(e.clientX, e.clientY) : null;
  if (fx) { select(fx.userData.source.id, e.ctrlKey || e.shiftKey || e.metaKey); return; }
  // a light's marker is picked ahead of the piece behind it
  const light = pickLight(e.clientX, e.clientY);
  if (light) { select(light.userData.source.id, e.ctrlKey || e.shiftKey || e.metaKey); return; }
  // the Lights view: only lights are picked
  if (lightsOn) return;
  // with the Normal button's Spawn points switch, a marker ahead of the piece behind it; a click elsewhere lets the
  // picked one go
  const spawnHit = spawnsShown() ? pickSpawnMarker(e.clientX, e.clientY) : null;
  if (spawnHit) { setPickedSpawn(spawnHit); return; }
  if (pickedSpawn) setPickedSpawn(null);
  // the Normal button's Floor boxes: a box's edge picks its building
  const edge = pickBoxEdge(e.clientX, e.clientY);
  if (edge?.id) { select(edge.id, e.ctrlKey || e.shiftKey || e.metaKey); return; }
  if (edge?.own) { pickOwn(edge.own, e.ctrlKey || e.shiftKey || e.metaKey); return; }
  const hit = pick(e.clientX, e.clientY);
  // a landing zone ahead of what stands on it; a landing piece (the frame, the Skyranger) picks its zone
  // landing zones are picked in the Landing zones view only (the user, 13 November 2026: "not editable in normal
  // mode"); a landing piece is a piece here, its zone moved in that view
  if (hit && isLanding(roots.get(hit.object.userData.objectId)?.userData.source ?? {}))
    flashHint('A piece of the landing: its zone is moved in the Landing zones view (Shift+Z)');
  if (floorTileSelect(e, hit)) return;
  // Ctrl or Shift adds a piece to the selection (or takes it out again).
  if (hit) select(hit.object.userData.objectId, e.ctrlKey || e.shiftKey || e.metaKey);
});
renderer.domElement.addEventListener('pointermove', e => { setPointer([e.clientX, e.clientY]); setGhostDirty(true); setTipDirty(true); });
renderer.domElement.addEventListener('pointerleave', () => { setPointer(null); setGhostDirty(true); setTipDirty(true); });
controls.addEventListener('change', () => { setGhostDirty(true); setTipDirty(true); });
renderer.domElement.addEventListener('dblclick', () => (effectsOn ? frameEffect() : selected && !gizmo.busy() && frame(allRoots.get(selected))));
// Snap and linked pieces are toggle buttons: .on and aria-pressed carry the state.
function toggleButton(button, onChange) {
  button.onclick = () => {
    const on = !button.classList.contains('on');
    button.classList.toggle('on', on); button.setAttribute('aria-pressed', on);
    onChange(on);
  };
}
$('editLevels').onclick = () => setLevelSnap(!levelSnap);
levelButton();
setPieces(createPieceBrowser({
  els: { panel: $('library'), list: $('libList'), filter: $('libFilter'), kind: $('libKind'), where: $('libWhere'),
         sort: $('libSort'), foot: $('libFoot') },
  renderer, preview: entry => previewGroup(entryParts(entry), null, entry.frame), onChoose: chooseEntry,
}));
setLibrary(createLibraryBrowser({
  els: { box: $('libAll'), scan: $('libScan'), filter: $('libAllFilter'), kind: $('libAllKind'), home: $('libAllHome'),
         sort: $('libAllSort'), placeable: $('libAllPlaceable'), elsewhere: $('libAllElsewhere'),
         favourites: $('libAllFavourites'), list: $('libAllList'), foot: $('libAllFoot') },
  mapName: () => data?.name ?? '', pixelRatio: () => renderer.getPixelRatio(), template: libraryTemplate,
  paint: (t, thumb) => pieces.paintThumbs([{ object: previewGroup(t.sources.map(source => ({ source, matrix: new THREE.Matrix4().fromArray(source.matrix) })), null, t.frame),
                                             box: t.box, thumb }]),
  recipesForScene: pieceRecipes,
  paintRecipe: (entry, thumb) => pieces.paintThumbs([{ object: previewGroup(entryParts(entry), null, entry.frame), box: entry.box, thumb }]),
  onChoose: chooseLibraryEntry, onChooseRecipe: chooseEntry, hint: flashHint, recall, remember,
  // an effect's picture and its moving preview (the likeness, stage FXV3)
  effectPicture: entry => (likenessOn ? effectPicture(entry) : null), onHover: hoverLikeness,
  paintObject: (object, box, thumb) => {
    // (an effect's picture: its sprites' least size is the picture's pixels, not the view's)
    const height = viewHeight.value;
    viewHeight.value = 96;
    try { return pieces.paintThumbs([{ object, box, thumb }]); } finally { viewHeight.value = height; }
  },
}));
setLookPicker(createLookPicker({ prepare: prepareSample, tagsOf: lookTags, recall, remember, hint: flashHint }));
setPrefabTab(createPrefabBrowser({
  els: { box: $('libPrefabs'), filter: $('prefabFilter'), list: $('prefabList'), foot: $('prefabFoot'), note: $('prefabNote'),
         file: $('prefabFile'), importButton: $('prefabImport') },
  onChoose: choosePrefab, onEdit: id => goTo({ prefab: id }), hint: flashHint,
  // whether this install has a map a prefab's pieces come from: by the library's list of maps, once it is read
  haveMap: name => (name.toLowerCase() === data?.name?.toLowerCase() ? true
    : library.ready() ? library.maps().has(name.toLowerCase()) : null),
  download: (name, doc) => {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([`${JSON.stringify(doc, null, 1)}\n`], { type: 'application/json' }));
    link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  },
}));
segmented($('libScope'), () => setLibraryScope($('libScope').value));
setLibraryScopeValue(LIBRARY_SCOPES[recall('workshop.libraryScope')] ? recall('workshop.libraryScope') : 'map');
$('libScope').value = libraryScope;
$('editAdd').onclick = () => data && showPieces(!pieces.open);
$('floorTiles').onchange = e => { drawFloorTiles(); e.target.blur(); };
$('libraryClose').onclick = () => showPieces(false);
toggleButton($('editLinked'), on => { gizmo.setLinked(on); select(selected, false, true); });
$('projectSave').onclick = () => { showPop(null); saveProject(); };
$('projectSaveAs').onclick = () => showFileDialog('save');
$('projectBuild').onclick = () => { showPop(null); openBuild(); };
$('projectPlay').onclick = () => playInGame();
$('prefabTest').onclick = openPrefabTest;
$('prefabRecover').onclick = () => { showPop(null); recoverPrefabSources(); };
$('projectMaps').onclick = showGameMaps;
$('projectLoad').onclick = () => showFileDialog('load');
if (builderMode) $('projectLoad').onclick = () => { showPop(null); mapBrowser?.show(null, { prefabGroup: true }); };
$('prefabNew').onclick = () => goTo({ prefab: 'new' });
$('projectManage').onclick = showProjectManager;
$('projectCache').onclick = showPrecache;
$('projectClose').onclick = () => { showPop(null); goTo({ project: null }); };
$('projectSetup').onclick = () => { showPop(null); setupDialog.show(); };
$('editUndo').onclick = () => undoStep();
$('editRedo').onclick = () => undoStep(true);
$('editReset').onclick = () => resetSelected();
$('editResetAll').onclick = () => resetAll();
$('flagsReset').onclick = () => resetFlags();
$('editKind').onclick = e => selectKind(e.shiftKey);
$('effectKind').onclick = e => { selectKind(e.shiftKey); e.target.blur(); };
$('editCopy').onclick = () => copySelection();
$('editDelete').onclick = () => deleteSelection();
for (const id of ['alignX', 'alignY', 'alignZ', 'alignBy']) $(id).onchange = e => { saveAlignPrefs(); e.target.blur(); };
$('alignGo').onclick = () => align();
$('alignTarget').onchange = e => { setAlignTarget(e.target.value); e.target.blur(); alignPanel(); };
$('groupMake').onclick = () => lockAsGroup();
$('groupAdd').onclick = () => addToGroup();
$('groupDissolve').onclick = () => { const { group } = selectionGroup(); if (group) ungroup(group); };
$('groupBreak').onchange = e => {
  const { group } = selectionGroup(), on = e.target.checked;
  e.target.blur();   // the shortcuts (Ctrl+G, Ctrl+C) ignore keys typed in a field
  if (!group) return;
  changeGroups(next => { next.get(group.id).breakTogether = on; },
               on ? 'The group breaks together in the game' : 'The group\'s pieces break on their own in the game');
};
gizmo.controls.addEventListener('dragging-changed', e => { dragHint(e.value); if (!e.value) editChanged(); });
// The light section's fields: a typed value commits on Enter or when the field is left (one undo step); Escape puts it back.
for (const [id, key] of [['lightBrightness', 'brightness'], ['lightRadius', 'radius'], ['lightFalloff', 'falloffExponent'],
                         ['lightInner', 'innerConeAngle'], ['lightOuter', 'outerConeAngle']])
  $(id).addEventListener('change', e => commitLightField(key, e.target));
for (const [k, id] of ['lightR', 'lightG', 'lightB'].entries())
  $(id).addEventListener('change', e => {
    const root = lightRoots.get(selected);
    if (!root) return;
    const bytes = [...root.userData.values.color]; bytes[k] = Number(e.target.value);
    commitColour(bytes);
  });
$('lightColor').addEventListener('change', e => {
  const hex = e.target.value;
  commitColour([1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)));
});
for (const id of ['lightBrightness', 'lightRadius', 'lightFalloff', 'lightInner', 'lightOuter', 'lightR', 'lightG', 'lightB'])
  $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') e.target.blur();
    else if (e.key === 'Escape') { lightPanel(); e.target.blur(); }
  });
$('lightOn').onchange = e => { changeLight({ enabled: e.target.checked }); e.target.blur(); };
// The cover section's Cover: a new cover when chosen (the size is the handles').
for (const id of ['coverHeight']) {
  $(id).addEventListener('change', commitCover);
  $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') e.target.blur();
    else if (e.key === 'Escape') { const root = roots.get(selected); if (root?.userData.source.cover) coverPanel(root); e.target.blur(); }
  });
}
$('coverFit').onclick = fitFloor;
$('lightSolo').onclick = () => setSolo(!soloOn);
$('lightAssign').onclick = () => {
  if (assigning) { setAssigning(null); lightPanel(); return; }
  setAssigning(selected); lightPanel(); flashHint('Click the piece this light glows from · Esc cancels');
};
$('lightKeep').onclick = () => { const root = lightRoots.get(selected); if (root) setBinding(root, null); };
$('lightAuto').onclick = () => { const root = lightRoots.get(selected); if (root) setBinding(root, undefined); };
$('editLights').onclick = () => data && setLightsShown(!lightsOn);
$('editZones').onclick = () => data && setZonesShown(!zonesOn);
$('editEffects').onclick = () => data && setEffectsShown(!effectsOn);
$('editSpawns').onclick = () => data && setSpawnsShown(!spawnsOn);
$('editNormal').onclick = () => data && setNormalView();
$('normalLights').onchange = e => { setNormalLights(e.target.checked); e.target.blur(); };
$('areaToggle').onchange = e => { setAreaShown(e.target.checked); remember(AREA_SHOWN, areaShown ? '1' : '0'); refreshLightVisibility(); e.target.blur(); };
$('reachToggle').onchange = e => {
  setReachShown(e.target.checked); remember(REACH_SHOWN, reachShown ? '1' : '0'); e.target.blur();
  setReachKey(''); refreshLightShapes(); lightPanel();   // drawn again with or without the outlines
};
$('skyToggle').checked = recall(SKY_SHOWN) === '1';
$('skyList').hidden = !$('skyToggle').checked;
$('skyToggle').onchange = e => { $('skyList').hidden = !e.target.checked; remember(SKY_SHOWN, e.target.checked ? '1' : '0'); e.target.blur(); };

// The camera, snap and keys (navigation.js): the framing, the camera's keys, look-drag, wheel and speeds, the gizmo's
// buttons with the pivot and snap (and the edit hub's tools refresh), and the editor's keys; made where the camera's
// keys were, the last of its runs, after every factory whose functions the keys call.
const { frame, panCamera, setSnapMode } = createNavigation({
  $, builderRecords, camera, cancelMissionGizmo, cancelPointDrag, cancelZoneGizmo, content, controls,
  copySelection, copySpawn, copyZone, deleteSelection, deleteSpawn, deleteWallOpening, deleteZone, dragHint,
  editBaseSpawn, editSpawnCopy, endCoverDrag, endGridDrag, endLightDrag, endPickDrag, endVolumeDrag, endWallDrag,
  flashHint, frameEffect, gizmo, groupShortcut, isMadeSlab, isMadeWall, lightPanel, madeRoot, mapBreakable,
  missionGizmo, modalOpen, openBuild, paste, pick, pickEffect, pickZone, playArea, projectsAvailable, rayAt,
  refreshGrid, refreshVolumes, releaseRockPoint, renderer, restingHint, saveProject, select, setEffectsShown,
  setGridTool, setLevelSnap, setLightsShown, setNormalView, setOwnPicked, setPickedSpawn, setPickTool, setPlayArea,
  setSolo, setSpawnsShown, setVolumesShown, setVolumeTool, setZoneGizmoMode, setZonesShown, showFileDialog,
  showMapBrowser, showPieces, showPop, spawnDeleted, spawnEntry, spawnMovable, startBreak, startLookPick, stopBreak,
  stopLookPick, stopPickBox, stopPlacing, stopSpawnPlacing, stopWallDrawing, stopZonePlacing, sun, takePickBox,
  TURNED_KINDS, turnZone, undoStep, volumePanel, wallGhost, wallHint, zoneGizmo,
  // (a let startScene sets: called through)
  applyLighting: () => applyLighting() });
window.addEventListener('beforeunload', e => { if (!leaving && unsavedDocument()) e.preventDefault(); });
new ResizeObserver(() => {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  renderer.setSize(w,h); camera.aspect=w/h; camera.updateProjectionMatrix();
}).observe(viewport);
let lastFrame = performance.now();
let builderRefresh = 0, builderTarget = '';
renderer.setAnimationLoop(() => {
  if (zoneGizmo.enabled !== zoneGizmoWanted() && !zoneGizmo.dragging) placeZoneGizmo();     // (a view or placing began or ended)
  if (missionGizmo.enabled !== missionGizmoWanted() && !missionGizmo.dragging) placeMissionGizmo();
  const now = performance.now(), sinceFrame = Math.min(0.05, (now - lastFrame) / 1000);
  panCamera(sinceFrame);
  lastFrame = now;
  controls.update();
  if (builderMode && now - builderRefresh > 250) {
    const at = `${Math.round(controls.target.x / TILE)},${Math.round(controls.target.z / TILE)}`;
    if (at !== builderTarget || now - builderRefresh > 2000) { builderTarget = at; builderRefresh = now; refreshBuilder(); }
  }
  scaleMarkers();
  scaleSpawnMarkers();
  updateLightHandles();
  updateVolumeHandles();
  updateCoverHandles();
  updateWallHandles();
  placePointGizmo();
  drawCursorRings();
  if (lightsDirty && !soloOn && $('lighting').value !== 'neutral' && now - lastLightSync > 120) applyLighting();
  if (placing && ghostDirty) moveGhost();
  if (effectsDirty) refreshEffects();
  stepLikenesses(sinceFrame);
  stepGhostLikenesses(sinceFrame);
  drawLikenessPane(sinceFrame);
  if (tipDirty && (effectsOn || (normalEffects && effectsShown()))) effectTip();
  else if (tipDirty && floorTileLayer) floorTip();
  updateTileGrid();
  pieces.drawThumbs();
  library.drawThumbs();
  lookPicker.drawFrame();
  drawPrefabPictures();
  if (now < shadowsUntil || now - shadowBeat > 1000) {
    renderer.shadowMap.needsUpdate = true; shadowBeat = now;
    if (shadowsUntil === Infinity && data) touchShadows();      // (every frame until a scene is open)
  }
  viewHeight.value = Math.max(1, renderer.domElement.clientHeight);     // (a sprite's least size: effects_preview.js)
  renderer.render(world,camera);
});
setInterval(() => {
  if (!$('statsLine').hidden) $('stats').textContent = `${renderer.info.render.calls} draw calls · ${renderer.info.render.triangles.toLocaleString()} triangles`;
}, 1000);
open().catch(e => { loadingState(`Could not open scene: ${e.message}`); $('status').textContent = 'Open failed'; console.error(e); });
