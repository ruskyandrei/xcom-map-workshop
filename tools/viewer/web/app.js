import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createGizmo, placedPose, actorMatrix } from './gizmo.js';
import { createPieceBrowser, pieceGrid, useFamilies } from './pieces.js';
import { api as projectApi, memberKey, stateKey, targetKey, tidyLocation, tidyRotator, uuid,
         groupKey } from './project.js';
import { createProjectDialog, savedWhen } from './project_files.js';
import { createProjectManager } from './manager.js';
import { createQueueController } from './build_queue.js';
import { createGameMaps } from './gamemaps.js';
import { createMapBrowser } from './map_browser.js';
import { createSetupDialog, setupApi } from './setup.js';
import { makeEffectMarker } from './effects_view.js';
import { viewHeight } from './effects_preview.js';
import { recordName } from './effects_rules.js';
import { createPrecache } from './precache.js';
import { createLibraryBrowser } from './library.js';
import { api as prefabApi, createPrefabBrowser } from './prefabs.js';
import { emptyPrefabScene, orderedWrites } from './prefab_document.js';
import { cloneBlasts } from './piece_records.js';
import { activeMapId, allRoots, areaBindings, areaShown, assigning, boxesShown, breaking, builder, builderMode,
         buildingMeta, cachePrefix, cleared, coverDrag, data, effectRoots, effectsDirty, effectsOn, eventMemo,
         floorTileLayer, foreignTemplates, geometryCache, ghostDirty, gridDrag, gridTool, groupIndex, groups, hintTimer,
         landingZones, lastBuild, lastLightSync, leaving, levelSnap, library, libraryScope, lightDrag, lightRadius,
         lightRoots, lightsDirty, lightsOn, lightsShown, likenessOn, lookPicker, lookPicking, missionMoves,
         missionPickValue, normalEffects, normalLights, normalSpawns, ownPicked, ownSet, pickBox, pickDrag,
         pickedEffect, pickedSpawn, pickedZone, pickTool, pieces, placing, prefabParameter, project, projectMissions,
         projectSpawnRules, reachShown, rockPoint, roots, selected, setActiveMapId, setAlignTarget, setAreaShown,
         setAskedPick, setAssigning, setBoxesShownValue, setCachePrefix, setCleared, setClearKeepsOutside, setData,
         setEffectsDirty, setEffectsOn, setEventMemo, setFamilies, setGhostDirty, setGroups, setHintTimer,
         setLandingActors, setLandingZones, setLeaving, setLibrary, setLibraryScopeValue, setLighting, setLightRadius,
         setLightsOn, setLightsShownValue, setLiveCache, setLookPicker, setLooksReady, setMergedBuildings,
         setNormalEffectsValue, setNormalLightsValue, setNormalSpawnsValue, setOwnGrid, setOwnPickedValue,
         setPickedEffect, setPickedSpawnValue, setPieces, setPointer, setPrefabTab, setProjectMissions,
         setProjectPicture, setProjectSpawnRules, setReachKey, setReachShown, setSnapModeValue, setSpawnRulesData,
         setSpawnsOn, setSpawnZonePick, setTileKey, setTipDirty, setZonesOn, snapMode, soloOn, spawnLayerReady,
         spawnPlacing, spawnsOn, spawnZonePick, stage, streamSet, tipDirty, volumeDrag, volumeRoots, volumesOn,
         volumeTool, wallDrag, wallDrawing, zonePlacing, zonesOn } from './editor_state.js';
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
import { createGroups } from './groups.js';
import { createAlign } from './align.js';
import { createLibraryTemplates } from './library_templates.js';
import { createClipboard } from './clipboard.js';
import { createMadeLooksWiring } from './made_looks_wiring.js';
import { createMadeDrawing } from './made_drawing.js';
import { createMadeHandles } from './made_handles.js';
import { createMadePanel } from './made_panel.js';
import { createMadeBreaking } from './made_breaking.js';
import { createMapGrid } from './map_grid.js';
import { createClearMap } from './clear_map.js';
import { createScenePieces } from './scene_pieces.js';
import { createCutaway } from './cutaway.js';
import { createFloorListings } from './floor_listings.js';
import { createLevelSnap } from './level_snap.js';
import { createDeleteReset } from './delete_reset.js';
import { createPrepare } from './prepare.js';
import { onHub, runHub, STOP } from './edit_hub.js';
import { createSelection } from './selection.js';
import { showImportNotes, showLinked, showSceneMenus, showSceneTitle } from './scene_start.js';
import { createTestApi } from './test_api.js';
import { anyModal, holdModals, releaseAfterChange } from './modal.js';
import { call } from './api.js';
import { recall, remember } from './storage.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createMapLighting } from './lighting.js';
import { makeMarker, paintMarker, valuesOf } from './lights_view.js';
import { visibleBounds, focusBounds } from './view_layout.js';
import { COVER_KIND } from './cover.js';
import { QUARTER, TILE } from './constants.js';
import { WALL_LOOKS, SLAB_LOOKS, slabLookOf, madeWallShape, madeSlabShape } from './walls.js';
import { DONOR_VERSION, loadLooks, lookTags } from './looks.js';
import { createLookPicker } from './look_picker.js';
import { GROUND_LOOKS, versionedGround, POINTS_VERSION, madeGroundShape } from './ground.js';

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
// Groups (research/editor-contracts.md, section 2): pieces the user keeps together, saved in the project. A group
// selects and moves as one, with linked pieces on or off; Ungroup ends it. There is no unlocking (the user, 11
// November 2026: "just leave it to group/ungroup"): every group is locked, and a project's `locked` is always true.
// breakTogether is for the game: when one of its breakable pieces is damaged or destroyed, the others are too, and
// its cover blocks go with a destroyed one (the
// compiler and the copier link them).
// A member is also a light (as a piece: its target, or {added}) or one of the project's buildings ({building}; plan
// 5.4a): they move, copy and go with the group, and take no part in breaking together.
// Groups nest (prefab plan 5.4): a member is a piece or another group ({group}); a piece is a direct member of one
// group at most, and a group of one. A piece picked selects the outermost group it is in; Ungroup ends that one, so
// it peels one level; Ctrl+G on pieces and whole groups makes a group of them, the groups kept inside.
// (groups and groupIndex, and setGroups: editor_state.js)
const parentGroup = g => groupIndex.get(groupKey(g.id));
// A group and the groups it is in, from the inside out.
function groupChain(g) { const out = []; for (let x = g; x && out.length < 64; x = parentGroup(x)) out.push(x); return out; }
// The outermost locked group among a group and the ones it is in: what a piece of it selects and moves with.
const topLocked = g => groupChain(g).filter(x => x.locked).at(-1) ?? null;
// The pieces of a group, those of the groups inside it too: their member keys.
function leafKeys(g, out = [], depth = 0) {
  for (const [k, m] of g.members) {
    if (m.group === undefined) out.push(k);
    else if (groups.has(m.group) && depth < 64) leafKeys(groups.get(m.group), out, depth + 1);
  }
  return out;
}
// A piece's member key and record: an original by package, level and actor; an added piece by its output name.
// (a light is a member as a piece is; a floor box stands for its building, which is a member whole: plan 5.4a)
const memberRecord = o => (o.isVolume ? { building: volumeRoots.get(o.id)?.userData.volume.building ?? '' }
  : o.added ? { added: o.actor } : { package: o.sourcePackage, level: o.layer, actor: o.actor });
const memberOf = o => memberKey(memberRecord(o));
const cloneGroup = g => ({ ...g, members: new Map(g.members) });
const cloneGroups = (from = groups) => new Map([...from].map(([id, g]) => [id, cloneGroup(g)]));
// Pieces of the packages a mission streams into the map (LWR's patches, mission objects): shown for reference, never
// edited (a project edits the map's own pieces; the Build makes nothing of theirs).
const isStream = o => o?.layer === 'stream';
// The families of pieces and the map's assemblies (families.json, tools/viewer/families.py: the compiler's own), or
// null from a server without them. assemblyIndex: an original's key (package|level|actor) to its assembly.
let assemblyIndex = new Map(), originalIndex = null;     // (the families, families: editor_state.js)
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
// foreignAssemblies: the same for the assemblies of other maps' pieces, as their records are read (libraryTemplate).
const foreignAssemblies = new Map();
const assemblyOf = o => {
  if (!o) return null;
  const key = targetKey(fromOf(o));
  return assemblyIndex.get(key) ?? foreignAssemblies.get(key) ?? null;
};
// The exported pose of the original whose pose rule a piece keeps under tile snap (a ladder, door, car, van or
// fracturing piece: the recipe snap), or null.
function recipeOf(o) {
  if (!o || o.isLight || o.isEffect || isStream(o) || !pieceGrid(o)) return null;
  if (!o.added) return { location: o.location, rotation: o.rotation };
  if (!originalIndex) {
    originalIndex = new Map();
    for (const r of roots.values()) if (!r.userData.source.added) originalIndex.set(targetKey(fromOf(r.userData.source)), r.userData.source);
  }
  const original = originalIndex.get(targetKey(o.added.from)) ?? foreignTemplates.get(`${targetKey(o.added.from)}|${o.component}`);
  if (!original) return null;
  // a made wall's height is free (its columns are made for where it stands): it moves by storeys from its own
  return isMade(o) ? { location: [original.location[0], original.location[1], o.location[2]], rotation: original.rotation }
    : { location: original.location, rotation: original.rotation };
}
const gridOrigin = () => data?.tileGrid?.origin?.slice(0, 2) ?? null;
// The corner the game counts its tiles from (export 26's tileGrid.tiles, its world data's WorldBounds; for an older
// export a unit under the origin, as on every installed map), [x, y, z]: a point's tile (a ladder's ends, a mission
// object's, a soldier's spot, the floor under a piece placed) is counted from it, as compiler.py tile_corner has it.
// Placing (snap, the lines, the grid rule) keeps the origin, the level volume's corner, where the maps' pieces stand.
const tileCorner = () => data?.tileGrid?.tiles ?? data?.tileGrid?.origin?.map(v => v - 1) ?? null;
// (The map's size as the project sets it, the cleared map, its landing zones, missions, picture and spawn rules, the
// buildings, and the install's landing lines for the map with the read a project waits for: editor_state.js.)
// The scene's pieces (scene_pieces.js): picking, textures and materials, the meshes' and materials' loads, a
// piece's root built, added and taken away, an original's parts and boxes, and a piece's box; made before
// the gizmo, which is given baseMatrix (nothing of it runs as the page loads but a few tables and vectors
// made).
const { addRoots, baseMatrix, boundsOf, boxOf, buildPieces, buildRoot, loaded, material, materialCache, materialKey,
        movedBox, originalOf, partsOf, pick, placeObjects, PLAIN_MATERIAL, rayAt, removeRoots, texture, track,
        vertexBox } = createScenePieces({
  camera, content, flashHint, fromOf, gltfLoader, gridOrigin, loadingState, pickables, renderer, textureLoader,
  texturePromises,
  // (made further down: called through, since they are not made yet while this runs)
  assetUrl: url => assetUrl(url), drawBroken: root => drawBroken(root),
  select: (id, add, keep) => select(id, add, keep) });
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
// The map's families arrived: an assembly also knows the link tag its copies' pieces share where a piece has no prefab
// of its own (pasteSnapshot): its members' prefab (Police Station's standalone light bar joins its sedan's), else its
// pivot (a door's leaf and frame share no prefab).
function useMapFamilies(table) {
  setFamilies(table); assemblyIndex = new Map();
  const prefabOf = new Map(data.objects.filter(o => o.prefab && o.layer === 'base').map(o => [o.actor, o.prefab]));
  for (const a of table?.assemblies ?? []) {
    const tag = a.members.length > 1 ? (a.members.map(m => prefabOf.get(m)).find(Boolean) ?? short(a.pivot)) : null;
    const assembly = { ...a, tag };
    for (const m of a.members) assemblyIndex.set(targetKey({ package: table.map, level: 'base', actor: m }), assembly);
  }
  useFamilies(table, o => assemblyOf(o)?.family ?? null);
  setLandingActors(Array.isArray(table?.landing) ? new Set(table.landing) : null);
  gizmo.regroup();
}
// (the Map lighting mode, lighting, and the pieces that could not be drawn, loadErrorCount: editor_state.js)
let mapCatalogue=null, mapBrowser=null;     // (cachePrefix: editor_state.js)
// (the lights' reach, lightRadius: editor_state.js)

const short = path => path.split('.').at(-1);
function text(parent, tag, value, className) {
  const el = document.createElement(tag); el.textContent = value;
  if (className) el.className = className;
  parent.append(el); return el;
}
function field(parent, name, value) {
  text(parent, 'dt', name); return text(parent, 'dd', value);
}
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
async function copyText(button, value) {
  const label = button.textContent;
  try { await navigator.clipboard.writeText(value); button.textContent = 'Copied'; }
  catch { button.textContent = 'Copy failed'; }
  setTimeout(() => { button.textContent = label; }, 1500);
}
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
onHub('edit', 'tools', () => {
  for (const [id, m] of [['editMove','translate'],['editRotate','rotate'],['editOff','off']]) $(id).classList.toggle('on', gizmo.mode === m);
  snapButton();
  const world = gizmo.space === 'world';
  $('editSpace').querySelector('use').setAttribute('href', world ? '#i-world' : '#i-local');
  $('editSpace').title = world ? "World axes: click for the piece's own axes (X)" : "The piece's own axes: click for world axes (X)";
  const centre = gizmo.pivot === 'centre';
  $('editPivot').querySelector('use').setAttribute('href', centre ? '#i-pivot-centre' : '#i-pivot-origin');
  $('editPivot').classList.toggle('on', centre);
  $('editPivot').setAttribute('aria-pressed', String(centre));
  $('editPivot').title = centre
    ? "Pivot: the selection's centre (with tile snap, the nearest tile centre or corner). Click to move and turn about each piece's own origin (C)"
    : "Pivot: each piece's own origin. Click to move and turn about the selection's centre (C)";
  $('selected').disabled = !selected;
});
// While a gizmo handle is held: one short line on what is moving and how to back out.
function dragHint(dragging) {
  const hint = $('dragHint');
  clearTimeout(hintTimer);
  if (!dragging) { restingHint(); return; }
  hint.hidden = false;
  hint.replaceChildren(`${gizmo.mode === 'rotate' ? 'Rotating' : 'Moving'} ${plural(gizmo.selection().length, 'piece')} · `
    + `${ownSet.size ? 'the map\'s own building stays where it is (copy it instead) · ' : ''}`);
  text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
}
// The busy mark for slow steps (map buildings plan, 4a): the build window's turning ring with what is being done, put
// up once a step has run for about a third of a second, so quick steps never show it. busyStart(message) returns the
// function that ends it. A long step on the page's own thread, which no timer interrupts (a paste of many pieces),
// asks for it `now`: the mark is drawn first and a frame let through (nextFrame) before the work runs.
const BUSY_AFTER = 330, BUSY_PIECES = 60, WORK_SLICE = 12, BUILD_CHUNK = 16;
const busyJobs = [];
function busyStart(message, now = false, hold = false) {
  const job = { message, shown: now, hold, done: 0, total: null };
  busyJobs.push(job);
  const timer = now ? null : setTimeout(() => { job.shown = true; busyPaint(); }, BUSY_AFTER);
  busyPaint();
  const end = () => { clearTimeout(timer); const at = busyJobs.indexOf(job); if (at >= 0) busyJobs.splice(at, 1); busyPaint(); };
  end.job = job;
  return end;
}
function busyPaint() {
  const job = busyJobs.filter(j => j.shown).at(-1);
  $('busyMark').hidden = !job;
  if (!job) return;
  const counted = job.total > 0;
  $('busyText').textContent = counted ? `${job.message} ${Math.min(job.done, job.total)} of ${job.total}` : job.message;
  $('busyBar').hidden = !counted;
  if (counted) $('busyBar').firstElementChild.style.width = `${Math.round(100 * Math.min(1, job.done / job.total))}%`;
}
// After the next frame is drawn (or a moment, where the page is in the background and draws none).
const nextFrame = () => new Promise(resolve => { requestAnimationFrame(() => setTimeout(resolve, 0)); setTimeout(resolve, 80); });
// One way to be busy (plan "sturdier prefabs, faster editor", L1): busy(message, work, { total, now }) puts the mark
// up (after a third of a second, or at once and with a frame let through when the caller knows the step is large),
// runs work(step) and takes the mark down whatever happens. step(done, total, message) moves the bar and the count
// ("212 of 458"); without a total the ring alone shows. While a mark put up at once is shown, clicks and keys meant
// for the view are ignored (busyHeld), so a second Ctrl+V does not queue behind the first; a mark that comes up late
// (a read that may be quick) holds nothing unless asked to.
async function busy(message, work, { total = null, now = false, hold = now } = {}) {
  const end = busyStart(message, now, hold), job = end.job;
  job.total = total;
  const step = (done, of = job.total, text = null) => { job.done = done; job.total = of; if (text) job.message = text; busyPaint(); };
  try {
    if (now) await nextFrame();
    return await work(step);
  } finally { end(); }
}
const busyHeld = () => busyJobs.some(j => j.hold && j.shown);
for (const type of ['keydown', 'pointerdown', 'wheel'])
  window.addEventListener(type, e => {
    if (!busyHeld()) return;
    const view = type === 'keydown' ? !e.target.closest?.('input, textarea, select, [contenteditable], dialog') : e.target.tagName === 'CANVAS';
    if (view) { e.stopImmediatePropagation(); e.preventDefault(); }
  }, { capture: true, passive: false });
// A long loop on the page's own thread gives way once it has held it for WORK_SLICE ms: `const rest = breather()`
// before the loop, `await rest()` in it. The ring keeps turning and the bar moves; a short loop never waits.
function breather(slice = WORK_SLICE) {
  let since = performance.now();
  return async () => { if (performance.now() - since < slice) return; await nextFrame(); since = performance.now(); };
}
// Many pieces made (buildRoot each), a few at a time, giving way by time and counting for the busy mark. With `failed`
// (a list), a piece that can't be drawn (its mesh, a material or a texture not had) is left out of what is given back
// and named there, { obj, error }, as the map's own load leaves one out (review finding 29); without, it throws.
async function buildRoots(objs, step = null, failed = null) {
  const built = [], rest = breather();
  for (let k = 0; k < objs.length; k += BUILD_CHUNK) {
    const chunk = objs.slice(k, k + BUILD_CHUNK);
    const made = await Promise.all(chunk.map(obj => (failed ? buildRoot(obj).catch(error => { failed.push({ obj, error }); return null; }) : buildRoot(obj))));
    built.push(...made.filter(Boolean));
    step?.(k + chunk.length, objs.length);
    await rest();
  }
  return built;
}
// A short notice in the same place (copied, deleted, nothing to paste); it goes after a moment.
// (its timer, hintTimer: editor_state.js)
function flashHint(message) {
  if (gizmo.controls.dragging) return;
  const hint = $('dragHint');
  hint.replaceChildren(message); hint.hidden = false;
  clearTimeout(hintTimer);
  setHintTimer(setTimeout(restingHint, 2500));
}
// With nothing else to say: how to place the piece being placed, or nothing.
function restingHint() {
  const hint = $('dragHint');
  if (pickTool && !placing) {
    hint.hidden = false; hint.replaceChildren('Box select: drag over the ground, around the pieces to take · ');
    text(hint, 'kbd', 'Esc'); hint.append(' cancels');
    return;
  }
  hint.hidden = !placing;
  if (!placing) return;
  const turned = placing.turns ? ` (turned ${placing.turns * 90}°)` : '';
  const storey = $('floor').value !== 'all' ? `floor ${$('floor').value}'s height (the Floor picker)` : 'the level under the cursor';
  const floor = placing.clip.floor != null && levelSnap ? ` · a floor piece: its height snaps to ${storey}` : '';
  hint.replaceChildren(`Placing ${placing.clip.name}${turned}${floor} · click to place · R turns · Shift+click places more · `);
  text(hint, 'kbd', 'Esc'); hint.append(' stops');
}

// Adding and deleting pieces. Like moves, these are edits a project keeps and the Build makes.
// A copy is a new piece built from its source's mesh and materials, with its own id, actor name and pivot.
// (the clipboard, clipboard, and the copies' serial: editor_state.js)
const newId = () => `added:${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
// (snapMode, the snap setting, 'off', 'fine' or 'tile': editor_state.js)
// Snap cycles off, fine steps, whole tiles. Under tile snap a selection with a ladder, door, car, van or fracturing piece
// takes the recipe snap (gizmo.js recipeMove, poserule.js): the Build maps what the map saves per tile exactly only for
// such a pose. Snap off or fine, such a piece moves as any piece does, and off the grid the Build warns (refreshGrid).
const SNAPS = {
  off: ['fine', '', 'Snap off. Click for steps of 24 units and 15°'],
  fine: ['tile', '24', 'Snap: steps of 24 units and 15°. Click for whole tiles'],
  tile: ['off', '96', 'Snap: whole tiles (96 across, 64 up) from where the piece stood, and 90° turns. Click to turn snap off'],
};
const RECIPE_NOTE = 'Recipe snap: under tile snap, ladders, doors, cars, vans and fracturing pieces (walls, storey floors) move by whole tiles (96 across) and storeys (64 up) and '
  + 'turn by quarter turns about the vertical, from where the original stands, so the Build maps what the map '
  + 'saves for their tiles exactly. Click to turn snap off: they then move freely';
function snapButton() {
  const button = $('editSnap'), recipe = gizmo.recipe;
  button.classList.toggle('on', snapMode !== 'off'); button.setAttribute('aria-pressed', snapMode !== 'off');
  button.title = recipe ? `${RECIPE_NOTE}.` : SNAPS[snapMode][2];
  $('snapBadge').textContent = recipe ? 'R' : SNAPS[snapMode][1];
}
// What a selected root is called in a list: a piece by its mesh, a light by its actor.
const rootName = r => (r.userData.volume ? `Floor box of ${buildingMeta.get(r.userData.volume.building)?.name || 'a building'}`
  : r.userData.light ? short(r.userData.source.actor) : r.userData.effect ? recordName(r.userData.source, data)
  : short(data.meshes[r.userData.source.mesh].name));
// "12 pieces, 2 lights and 1 building": what these roots are, by kind.
function selectionWords(list, other = '') {
  const lights = list.filter(r => r.userData.light).length, boxes = list.filter(r => r.userData.volume);
  const fx = kind => list.filter(r => r.userData.effect && r.userData.source.kind === kind).length;
  const effects = fx('effect'), sounds = fx('sound'), flares = fx('flare');
  const made = new Set(boxes.map(r => r.userData.volume.building)).size, n = list.length - lights - boxes.length - effects - sounds - flares;
  const parts = [n && plural(n, `${other}piece`), lights && plural(lights, `${n ? '' : other}light`), effects && plural(effects, 'effect'),
                 sounds && plural(sounds, 'sound'), flares && plural(flares, 'lens flare'),
                 made && plural(made, `${n || lights ? '' : other}building`)].filter(Boolean);
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? `0 ${other}pieces`;
}
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
// "3 pieces, 1 light and 1 building": a group's members (their keys), by kind.
function keyWords(keys) {
  const kind = k => { const r = liveMembers().get(k)?.[0]; return k.startsWith('building|') ? 'building' : r?.userData.light ? 'light'
    : r?.userData.effect ? (r.userData.source.kind === 'flare' ? 'lens flare' : r.userData.source.kind) : 'piece'; };
  const parts = ['piece', 'light', 'effect', 'sound', 'lens flare', 'building'].map(w => { const n = keys.filter(k => kind(k) === w).length; return n && plural(n, w); }).filter(Boolean);
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? plural(0, 'piece');
}
function sceneChanged() { touchShadows(); setLiveCache(null); setEffectsDirty(true); cutaway(); refreshGroundGrid(false); refreshJoins(); }
// An actor's pose at a render matrix: game location and rotator. A piece that was only moved keeps its source's own
// rotator exactly, so untouched native values stay as they were.
function actorPose(source, matrix) {
  const pose = placedPose(source, matrix);
  const turn = matrix.clone().multiply(new THREE.Matrix4().fromArray(source.matrix).invert()).elements;
  const same = [0, 1, 2, 4, 5, 6, 8, 9, 10].every(i => Math.abs(turn[i] - (i % 5 === 0 ? 1 : 0)) < 1e-7);
  return { location: pose.location.map(tidyLocation), rotation: same ? [...source.rotation] : pose.rotation.map(tidyRotator) };
}
// The render matrix that puts a source piece's actor at a game pose (the inverse of actorPose).
const movedMatrix = (source, location, rotation) => actorMatrix(location, rotation)
  .multiply(actorMatrix(source.location, source.rotation).invert()).multiply(new THREE.Matrix4().fromArray(source.matrix));
// A made piece's request (custom geometry plan, M4): a donor look's at its kind's DONOR_VERSION with the look in its
// numbers, a look id's (or none) at version 1 as before.
// A made piece drawn plain (custom geometry editing plan, B2, 19 November 2026): its kind's default look's numbers at
// its kind's PLAIN_VERSION, drawn in a plain material until a look is chosen in the piece panel; the Build makes it in
// that default look and says so (compiler made-no-look).
const PLAIN_VERSION = { fracWall: 4, fracSlab: 3, ground: 3 };
// (MADE_KINDS, the kinds of made piece, one piece each made from numbers: piece_records.js)
const isPlain = g => Boolean(g) && (g.version === PLAIN_VERSION[g.kind] || (g.kind === 'ground' && g.version === POINTS_VERSION && g.ground?.look === undefined));
const madeRequest = (kind, look, numbers, plain = false) => {
  const key = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' }[kind];
  // (a rock with moved points: POINTS_VERSION whatever its look, versionedGround)
  if (plain) return versionedGround({ kind, version: PLAIN_VERSION[kind], [key]: numbers });
  return versionedGround(look?.donor ? { kind, version: DONOR_VERSION[key], [key]: { ...numbers, look: { ...look.donor } } } : { kind, version: 1, [key]: numbers });
};
// The default look a plain piece of `kind` is made in: the Bar's inside wall, the Bar's floor or roof by the slab's
// role, asphalt (a look marked `plain`, which setMadeLook makes a plain request of).
function plainLook(kind, numbers = null) {
  if (kind === 'wall') return { ...WALL_LOOKS[0], plain: true };
  if (kind === 'ground') return { ...GROUND_LOOKS[0], plain: true };
  const role = slabLookOf(numbers ?? {})?.role ?? 'roof';
  return { ...(SLAB_LOOKS.find(l => l.role === role) ?? SLAB_LOOKS[0]), plain: true };
}
// A made piece's mesh and materials; a plain one's (B2) on the plain material, but for the hidden inside faces.
function madeShape(template, generated) {
  const shape = madeShapeOf(template, generated);
  return isPlain(generated) && shape.materials
    ? { ...shape, materials: shape.materials.map(m => (data.materials[m]?.render?.family === 'hidden' ? m : PLAIN_MATERIAL)) } : shape;
}
// A made piece's mesh and materials from its numbers (walls.js madeWallShape and madeSlabShape, ground.js
// madeGroundShape: the mesh record goes into the scene's meshes), or {} when the server can't draw them.
function madeShapeOf(template, generated) {
  if (generated?.kind === 'fracSlab') return madeSlabShape(template, generated.slab, generated.blasts, data.meshes);
  if (generated?.kind === 'ground') return madeGroundShape(template, generated.ground, data.meshes);
  return generated?.kind === 'fracWall' ? madeWallShape(template, generated.wall, generated.blasts, data.meshes) : {};
}
// An added piece: a copy of one source component, as its own actor (output name, entity id, prefab and partner).
// A made piece stands at scale 1 whatever its donor's (custom geometry plan, M4b: the Build sets its DrawScale and
// DrawScale3D to 1; a ground donor placed at 4 gives a look like any other): its matrix without the donor's scale.
function unscaled(matrix) {
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  matrix.decompose(p, q, s);
  return new THREE.Matrix4().compose(p, q, new THREE.Vector3(1, 1, 1));
}
function addedObject(template, placed, { actor, entity, prefab, partner, location, rotation, tinted, flags = null, generated = null, blasts = null, breaksFurther = false }) {
  if (generated && ['fracWall', 'fracSlab', 'ground'].includes(generated.kind)) placed = unscaled(placed);
  return { ...template, ...madeShape(template, generated), id: newId(), actor, layer: 'added', hidden: false, environment: false, hiddenBy: null, provenance: null,
    // its piece flags as made (piece flags plan): a paste's are its original's request, a project's its record's; the
    // template's settings (pieceFlags) stay its baseline
    initialFlags: flags ? { ...flags } : null,
    // a copy of one of the map's fracturing pieces broken (E6): its blasts, a paste's its original's
    initialBlasts: blasts?.length && !generated ? cloneBlasts(blasts) : null,
    // (and, a roof or floor the game keeps whole, asked to break further in battle: F-139)
    initialBreaksFurther: Boolean(blasts?.length && !generated && breaksFurther),
    // `floors` stays its original's listings (its template's, a copy's included) and `cutout` its original's: the
    // copy's own listings follow where it stands (listingsNow), as the Build lists it.
    floors: originalOf(template)?.floors ?? template.floors ?? [], prefab, partner, matrix: placed.toArray(), location, rotation,
    // `generated`: a fracturing wall the Build makes from numbers on this piece's materials (custom geometry plan,
    // section 0), kept as the project has it; the view draws the mesh made from its numbers (madeShapeOf)
    added: { from: fromOf(template), entity, tinted, ...(generated ? { generated } : {}),
             ...(template.cover ? { template: { kind: COVER_KIND, version: coverVersion(template.added?.template?.version, template.cover.type) } } : {}) } };
}
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
  $, cloneGroups, flashHint, gizmo, groupables, groupChain, groupChip, highlight, isStream, keyWords, leafKeys,
  memberOf, memberRecord, plural,
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
// (walls, floors, roofs and ground are drawn from the Build menu on the Add button, no longer listed here: B1)
const pieceRecipes = () => [...lightEntries(), ...coverEntries(), ...zoneEntries(), ...spawnAddEntries()];
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
let templates = null;
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
function templateFor(from, component) {
  if (!templates) {
    templates = new Map();
    for (const r of roots.values()) if (!r.userData.source.added) templates.set(`${sourceKey(r.userData.source)}|${r.userData.source.component}`, r.userData.source);
  }
  return templates.get(`${targetKey(from)}|${component}`) ?? foreignTemplates.get(`${targetKey(from)}|${component}`);
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
  loadingState, plural, projectNote, projectsAvailable, saveState, showFileDialog, text, touchRecent, unsavedDocument,
  // (made with the map grid, further down: called through, since it is not made yet while this runs)
  ownSize: () => ownSize(),
  // (made with the Spawns view, further down: called through, since they are not made yet while this runs)
  bombHelperFix: moves => bombHelperFix(moves), setMissionMoves: next => setMissionMoves(next),
  // (made with the loading overlay, further down: called through, since it is not made yet while this runs)
  openingProgress: name => openingProgress(name),
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
  documentWrites, draftWords, dropAdopted, editChanged, editState, flashHint, frame, gizmo, gridOrigin, isStream,
  libraryTemplate, lightPose, loadingState, movedMatrix, plural, projectChanged, recipeOf, removeRoots, rootName, sceneChanged,
  selectActors, short, showFileDialog, templateFor, text, world,
  // (made with the loading overlay, further down: called through, since it is not made yet while this runs)
  openingProgress: name => openingProgress(name),
  // (made with the selection, further down: called through, since it is not made yet while this runs)
  gridNow: root => gridNow(root),
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
  lightsBlocked, madeShape, memberOf, movedMatrix, nextFrame, physicalBox, plural, previewGroup, readEffectRecords,
  readLibraryRecords, recipeLight, recordId, rootName, saveBuilder, selectionGroup, short, templateFor, text, track,
  withStorableCone,
  // (made with the selection, further down: called through, since it is not made yet while this runs)
  gridNow: root => gridNow(root),
  // (made with the cover blocks, the Effects view and the clipboard, further down: called through, since they are not
  // made yet while this runs)
  boxMatrix: b => boxMatrix(b), coverOf: entity => coverOf(entity),
  coverVersion: (version, type) => coverVersion(version, type), effectViewOnly: (o, cap) => effectViewOnly(o, cap),
  groupTree: (copied, chainOf) => groupTree(copied, chainOf), linkOf: e => linkOf(e), mapChain: key => mapChain(key),
  matrixBox: matrix => matrixBox(matrix), snapshot: (selection, own) => snapshot(selection, own),
  startPlacing: (clip, entry) => startPlacing(clip, entry), stopPlacing: () => stopPlacing() });
const mapLabel = id => mapCatalogue?.maps.find(m => m.id === id)?.label ?? id ?? '';
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
// Maps were prepared outside the map browser: the list it shows is brought up to the server's, entry by entry (the
// browser keeps the array it was given).
async function refreshMapList() {
  if (!mapCatalogue) return;
  try {
    const response = await fetch('/maps.json');
    if (!response.ok) return;
    const fresh = await response.json();
    for (const map of fresh.maps) {
      const mine = mapCatalogue.maps.find(m => m.id === map.id);
      if (mine) { delete mine.outdated; Object.assign(mine, map); } else mapCatalogue.maps.push(map);
    }
  } catch { /* the list stays as it was; a reload brings it */ }
}
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
let frameNear = 2;    // the near plane the last framing set (the wheel zoom brings it in close up)
function frame(root = content) {
  const interior=$('scenery').value==='interior';
  const box = (root === 'playable' || root === content && interior) && data.playableBounds
    ? focusBounds(data)
    : root === content ? visibleBounds(roots,data?.playableBounds)
    : root?.userData?.light ? new THREE.Box3().setFromCenterAndSize(new THREE.Vector3().setFromMatrixPosition(root.matrix),
                                                                    new THREE.Vector3(1, 1, 1).multiplyScalar(Math.min(800, Math.max(200, root.userData.values.radius ?? 400))))
    : new THREE.Box3().setFromObject(root);
  if (builderMode && root === content && !builder.loading) {
    const b = builderRecords().box;
    if (!b.isEmpty()) box.union(b);
    if (box.isEmpty() || box.getSize(new THREE.Vector3()).length() < 1) box.set(new THREE.Vector3(-576, 0, -576), new THREE.Vector3(576, 192, 576));
  }
  if(interior && root!==content && root!=='playable')box.intersect(focusBounds(data));
  if(root!==content && root!=='playable')box.max.y=Math.min(box.max.y,root.userData.cutHeight ?? Infinity);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = size.length() * 0.5;
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * Math.max(1, 1 / camera.aspect) * 1.1;
  controls.target.copy(center);
  camera.position.copy(center).add((interior ? new THREE.Vector3(0.55,1.5,1.1) : new THREE.Vector3(1,1.15,1.35)).normalize().multiplyScalar(distance));
  camera.near = frameNear = Math.max(0.2, distance / 5000); camera.far = Math.max(100000, distance * 8);
  camera.updateProjectionMatrix(); controls.update();
  if(root===content || root==='playable') {
    setLightRadius(Math.max(700,size.length()*0.55));sun.target.position.copy(center);
    Object.assign(sun.shadow.camera,{left:-lightRadius,right:lightRadius,top:lightRadius,bottom:-lightRadius,near:1,far:lightRadius*6});
    sun.shadow.camera.updateProjectionMatrix();applyLighting();
  }
}
// A drawn-only copy of some pieces (the placing preview, a piece-list thumbnail) from the loaded meshes and
// materials, or `override` for every part. It is never picked. parts: { source, matrix }; `frame` moves them all.
// (Not with the scene's pieces, scene_pieces.js: it falls back on the clipboard's ghost material, made further down.)
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
// A row of buttons used like a select: .value, buttons with data-value, onChange after a click.
function segmented(el, onChange) {
  Object.defineProperty(el, 'value', {
    get: () => (el.querySelector('button.on') || el.querySelector('button'))?.dataset.value,
    set: v => { for (const b of el.querySelectorAll('button')) { b.classList.toggle('on', b.dataset.value === v); b.setAttribute('aria-pressed', b.dataset.value === v); } },
  });
  el.addEventListener('click', e => {
    const button = e.target.closest('button');
    if (!button || button.disabled || button.classList.contains('on')) return;
    el.value = button.dataset.value; onChange();
  });
}
function segButton(value, label, title) {
  const button = document.createElement('button');
  Object.assign(button, { type: 'button', textContent: label, title });
  button.dataset.value = value;
  return button;
}
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
  listingsNow, missionName, ownSize, pickEffect, plural, RECIPE_NOTE, recipeOf, rootName, selectionWords,
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
        ghostMaterial, groupTree, keepRecipe, LIBRARY_SCOPES, linkOf, mapChain, matrixBox, moveGhost, paste,
        pasteSnapshot, placeAt, placeMove, setLibraryScope, showPieces, snapshot, startPlacing,
        stopPlacing } = createClipboard({
  $, actorPose, addedEffect, addedLight, addedObject, addEffectRoots, addLightRoots, addRoots, askLineCollision,
  assemblyOf, banner, boundsOf, buildRoots, busy, BUSY_PIECES, busyStart, chosenStorey, cloneGroup, cloneGroups,
  copyVolumes, effectFollows, effectTemplate, effectViewOnly, flashHint, FLOOR_CLEARANCE, floorSupportOf, fromOf,
  ghostEdges, ghostLine, gizmo, gridOrigin, groundAt, groundHeight, groupChain, hoverLikeness, isForeignTarget,
  libraryTemplate, lightClip, lightViewOnly, liveFloorIndex, makeVolume, memberOf, memberRecord, newBuildingId,
  nextFrame, ownerRoot, ownVolumeLayer, partsOf, pasteVolumes, pick, pieceRecipes, plural, prefabPlacementProblem,
  previewGroup, rayAt, recipeOf, removeEffectRoots, removeLightRoots, removeRoots, restingHint, sceneChanged,
  selectionWords, setLightsShown, setNormalLights, setVolumeBox, short, startSpawnPlacing, startZonePlacing,
  stopSpawnPlacing, stopZonePlacing, text, tileCorner, volumeBox, world,
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
// The loading overlay: what is happening, a progress bar when the share done is known, and a detail line.
// What an opening document's steps say on the loading overlay: the pieces of other maps read (the first 40% of the
// bar), loaded with their meshes (to 70%) and the document's own pieces made (the rest).
const OPENING = { reading: [0, 0.4, 'reading'], loading: [0.4, 0.3, 'loading'], making: [0.7, 0.3, 'making'] };
const openingProgress = name => (phase, done, total) => {
  const [from, share, word] = OPENING[phase];
  loadingState(`Opening ${name}: ${word} ${done} of ${plural(total, 'piece')}…`, from + share * (total ? done / total : 1));
};
function loadingState(message, fraction = null, detail = '') {
  $('loadingText').textContent = message;
  $('loadingBar').hidden = fraction == null;
  if (fraction != null) $('loadingBar').firstElementChild.style.width = `${Math.round(100 * Math.min(1, Math.max(0, fraction)))}%`;
  $('loadingDetail').textContent = detail;
}
// A JSON file read with its progress (onProgress(share) as it arrives; the server sends its length).
async function fetchJson(url, onProgress) {
  const response = await fetch(url);
  if (!response.ok) throw Error(`Scene request failed: ${response.status}`);
  const length = Number(response.headers.get('Content-Length')) || 0;
  if (!length || !response.body) return response.json();
  const reader = response.body.getReader(), chunks = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); received += value.length;
    onProgress(received / length);
  }
  return JSON.parse(new TextDecoder().decode(await new Blob(chunks).arrayBuffer()));
}
async function open() {
  stopPickBox();
  setBoxesShownValue(false); setNormalLightsValue(false); setLightsOn(false); setLightsShownValue(false); setZonesOn(false);
  setEffectsOn(false); setPickedEffect(null); setNormalEffectsValue(false); effectLayer.visible = false; setEffectsDirty(true); stopWave();
  setSpawnsOn(false); setPickedSpawnValue(null); setSpawnZonePick(null); setNormalSpawnsValue(recall(NORMAL_SPAWNS) === '1'); setSpawnRulesData(null);
  const parameters=new URLSearchParams(location.search);
  loadingState('Opening the map list…');
  const mapResponse=await fetch('/maps.json');
  if(!mapResponse.ok)throw Error('Could not load the base map list. Restart the viewer server after updating it.');
  mapCatalogue=await mapResponse.json();
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
  // (the map the address asks for, when it isn't prepared yet: kept now, as the browser marks its entry ready)
  const askedUnprepared = !builderMode && activeMap && !activeMap.ready ? activeMapId : null;
  mapBrowser=createMapBrowser({ els: { root: $('mapDialog'), form: $('mapForm'), search: $('mapSearch'), prepared: $('mapPrepared'),
    groups: $('mapGroups'), list: $('mapList'), count: $('mapCount'), message: $('mapMessage'), bar: $('mapBar'), ok: $('mapOk'),
    // On a patch preview the open map counts as not open: choosing it opens its original layout.
    cancel: $('mapCancel'), close: $('mapClose') }, maps: mapCatalogue.maps,
    current: activeMap?.ready && !parameters.get('scene') ? activeMapId : null,
    prefabs: async () => (await prefabApi.list()).prefabs, onPrefab: id => goTo({ prefab: id }),
    // The map asked for but not prepared yet opens as asked once it is ready: the address as it was, its project,
    // mission and layout too (review finding 7; nothing is open meanwhile). Any other map chosen is a switch of map,
    // which opens it alone.
    onOpen: id => {
      mapBrowser.close();
      if (id === askedUnprepared) { setLeaving(true); location.reload(); return; }
      goTo({ map: id, scene: null, project: null, mission: null });
    } });
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

// Header menus: one open at a time; a press elsewhere or Escape closes it.
function showPop(id) {
  for (const button of document.querySelectorAll('[data-pop]')) {
    const on = button.dataset.pop === id, pop = $(button.dataset.pop);
    pop.hidden = !on;
    button.setAttribute('aria-expanded', on);
    if (on && pop.classList.contains('left')) pop.style.left = `${button.getBoundingClientRect().left - viewport.getBoundingClientRect().left}px`;
  }
  if (id === 'projectMenu') renderProjectMenu();
  if (id === 'playMenu') { refreshSquadLine(); refreshInstalls(); }
}
for (const button of document.querySelectorAll('[data-pop]')) button.onclick = () => showPop($(button.dataset.pop).hidden ? button.dataset.pop : null);
document.addEventListener('pointerdown', e => { if (!e.target.closest('.pop, [data-pop]')) showPop(null); });
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
function showMapBrowser() {
  if (!mapBrowser || modalOpen()) return;
  showPop(null);
  if (placing) stopPlacing();
  mapBrowser.show();
}
// The Map menu: Change map and the map's own things (missions, picture, grid, Clear map). Where it would hold Change
// map alone (a prefab, a patch preview), the button opens the map browser itself.
$('mapButton').onclick = () => {
  if (builderMode || !projectsAvailable()) { showMapBrowser(); return; }
  showPop($('mapMenu').hidden ? 'mapMenu' : null);
};
$('mapChange').onclick = showMapBrowser;
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
$('editMove').onclick = () => gizmo.setMode('translate');
$('editRotate').onclick = () => gizmo.setMode('rotate');
$('editOff').onclick = () => gizmo.setMode('off');
$('editSpace').onclick = () => gizmo.toggleSpace();
// The pivot (C): each piece's own origin, or the selection's centre (Discord feedback S4); remembered on this computer.
const PIVOT = 'workshop.pivot';
function togglePivot() {
  gizmo.setPivot(gizmo.pivot === 'centre' ? 'origin' : 'centre');
  remember(PIVOT, gizmo.pivot);
}
if (recall(PIVOT) === 'centre') gizmo.setPivot('centre', true);    // (the button shows it at the first editChanged)
$('editPivot').onclick = togglePivot;
// Snap and linked pieces are toggle buttons: .on and aria-pressed carry the state.
function toggleButton(button, onChange) {
  button.onclick = () => {
    const on = !button.classList.contains('on');
    button.classList.toggle('on', on); button.setAttribute('aria-pressed', on);
    onChange(on);
  };
}
function setSnapMode(next) {
  setSnapModeValue(next); gizmo.setSnap(next); setGhostDirty(true);
  snapButton(); refreshGrid(roots.get(selected));
}
$('editSnap').onclick = () => setSnapMode(SNAPS[snapMode][0]);
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

// The arrow keys and WASD move the camera while held. By default they pan across the map: Up/W and Down/S along the
// view's direction laid flat, Left/A and Right/D across it, so the camera keeps its height and angle. With View
// options' "Keys move along the view" ticked, Up/W and Down/S move forward and back the way the camera faces (climbing
// or descending with its tilt), Left/A and Right/D sideways across it. Either way the orbit target moves with the
// camera. The speed is the same on every map and at every zoom: PAN_SPEED units a second, well under what the distance
// used to give after Interior's framing on most maps (about 9,000 units away); Shift moves three times as fast.
// Q and E turn the view left and right while held, about the vertical, keeping the camera's tilt: by default the
// camera circles the point it looks at (as XCOM's own camera turns), and with "Keys move along the view" it turns where
// it stands, the point it looks at swinging round it. TURN_SPEED a second; Shift three times as fast.
const PAN_KEYS = { arrowup: 'forward', w: 'forward', arrowdown: 'back', s: 'back', arrowleft: 'left', a: 'left', arrowright: 'right', d: 'right' };
const TURN_KEYS = { q: 1, e: -1 };    // a positive turn about +Y swings forward towards the screen's left
const TURN_SPEED = THREE.MathUtils.degToRad(60);
const PAN_SPEED = 5000;    // about 52 tiles a second (7,200 at first: the user found it a little fast)
const FLY_KEYS = 'workshop.flyKeys';
const panKeys = new Set();
let panFast = false, flyKeys = recall(FLY_KEYS) === '1';
// View options' camera speeds (Discord feedback S2, S3): each a factor on its default, remembered on this computer.
// Move speed scales PAN_SPEED, key turn speed TURN_SPEED, and drag turn speed OrbitControls' orbit and the look-drag
// along the view (LOOK_PER_SCREEN). A double-click on a slider puts it back to 1; letting go of one gives the keys back
// to the camera.
const CAMERA_SPEEDS = { moveSpeed: 'workshop.moveSpeed', turnSpeed: 'workshop.turnSpeed', dragSpeed: 'workshop.dragSpeed' };
const cameraSpeed = { moveSpeed: 1, turnSpeed: 1, dragSpeed: 1 };
for (const [id, key] of Object.entries(CAMERA_SPEEDS)) {
  const input = $(id), saved = Number(recall(key));
  if (saved > 0) input.value = String(saved);    // (a range input keeps a saved value inside its own limits)
  const show = () => {
    cameraSpeed[id] = Number(input.value);
    $(`${id}Value`).textContent = `×${cameraSpeed[id].toFixed(2)}`;
    controls.rotateSpeed = cameraSpeed.dragSpeed;
  };
  show();
  input.oninput = () => { show(); remember(key, input.value); };
  input.onchange = () => input.blur();
  input.ondblclick = () => { input.value = '1'; input.oninput(); input.blur(); };
}
function turnCamera(dt) {
  const turn = [...panKeys].reduce((sum, k) => sum + (TURN_KEYS[k] ?? 0), 0);
  if (!turn) return;
  const angle = turn * TURN_SPEED * cameraSpeed.turnSpeed * (panFast ? 3 : 1) * dt, up = new THREE.Vector3(0, 1, 0);
  if (flyKeys) controls.target.sub(camera.position).applyAxisAngle(up, angle).add(camera.position);
  else camera.position.sub(controls.target).applyAxisAngle(up, angle).add(controls.target);
  camera.lookAt(controls.target);    // so this frame's move goes by the turned view
}
function panCamera(dt) {
  if (!panKeys.size) return;
  turnCamera(dt);
  const forward = new THREE.Vector3().subVectors(controls.target, camera.position);
  if (!flyKeys) {
    forward.setY(0);
    // Looking straight down, forward is the top of the screen.
    if (forward.lengthSq() < 1e-6) forward.set(0, 1, 0).applyQuaternion(camera.quaternion).setY(0);
  }
  if (forward.lengthSq() < 1e-6) return;
  forward.normalize();
  // Sideways is the screen's right, level with the ground (also looking straight down, when forward x up is nothing).
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion).setY(0);
  if (right.lengthSq() < 1e-6) return;
  right.normalize();
  const held = new Set([...panKeys].map(k => PAN_KEYS[k])), move = new THREE.Vector3();
  if (held.has('forward')) move.add(forward);
  if (held.has('back')) move.sub(forward);
  if (held.has('right')) move.add(right);
  if (held.has('left')) move.sub(right);
  if (move.lengthSq() < 1e-6) return;
  const speed = PAN_SPEED * cameraSpeed.moveSpeed * (panFast ? 3 : 1);
  move.normalize().multiplyScalar(speed * dt);
  camera.position.add(move); controls.target.add(move);
}
// Along the view, a left-drag looks round from where the camera stands instead of orbiting: the camera keeps its place
// and the point it looks at swings round it at the same distance, dragging right looking right and up looking up
// (LOOK_PER_SCREEN for a drag the view's height; the tilt stops just short of straight up or down). OrbitControls'
// own rotate is off then; its pans (right-drag, or Shift, Ctrl or Cmd with the left button) and the wheel stay. A press
// the gizmo or a light's handle takes is left to them, and a press that barely moves is still a click.
const LOOK_PER_SCREEN = Math.PI / 2;
let look = null;    // { id, x, y } while a look-drag is held
function lookBy(yaw, pitch) {
  const aim = new THREE.Spherical().setFromVector3(new THREE.Vector3().subVectors(controls.target, camera.position));
  aim.theta += yaw;
  aim.phi = THREE.MathUtils.clamp(aim.phi - pitch, 0.01, Math.PI - 0.01);
  controls.target.copy(camera.position).add(new THREE.Vector3().setFromSpherical(aim));
  camera.lookAt(controls.target);
}
renderer.domElement.addEventListener('pointerdown', e => {
  if (!flyKeys || e.button !== 0 || e.ctrlKey || e.shiftKey || e.metaKey || !controls.enabled || gizmo.busy()) return;
  look = { id: e.pointerId, x: e.clientX, y: e.clientY };
  zoomAnchor = null;
});
renderer.domElement.addEventListener('pointermove', e => {
  if (!look || e.pointerId !== look.id) return;
  if (!controls.enabled) { look = null; return; }    // the gizmo took the drag after all
  const k = LOOK_PER_SCREEN * cameraSpeed.dragSpeed / Math.max(1, renderer.domElement.clientHeight);
  lookBy(-(e.clientX - look.x) * k, -(e.clientY - look.y) * k);
  look.x = e.clientX; look.y = e.clientY;
});
for (const type of ['pointerup', 'pointercancel']) renderer.domElement.addEventListener(type, e => { if (look?.id === e.pointerId) look = null; });
function setFlyKeys(on) {
  flyKeys = Boolean(on); remember(FLY_KEYS, flyKeys ? '1' : '0');
  controls.enableRotate = !flyKeys; look = null;
}
$('flyKeys').checked = flyKeys;
controls.enableRotate = !flyKeys;
$('flyKeys').onchange = e => { setFlyKeys(e.target.checked); e.target.blur(); };
// The wheel zooms towards what is under the cursor. OrbitControls' own zoom scaled the distance to the orbit target, so
// each notch moved a share of a shrinking distance and never passed the target: on a big map, zoomed far in towards
// anything but the target, scrolling all but stopped. Here a notch moves the camera ZOOM_STEP of the way to the surface
// under the cursor (else the ground level with the target, else a point on the cursor's ray as far as the target), so
// that point stays under the cursor, and the orbit target moves onto the view's centre line at that point's depth:
// orbiting, panning and the next notch work about what is looked at. Zooming out moves away from it the same way.
// A burst of wheel events with the cursor still keeps the first one's point (a raycast once per burst).
const ZOOM_STEP = 0.18, ZOOM_BURST = 250;
let zoomAnchor = null;   // { point, x, y, time }
function zoomPoint(clientX, clientY) {
  const now = performance.now();
  if (zoomAnchor && now - zoomAnchor.time < ZOOM_BURST && Math.hypot(clientX - zoomAnchor.x, clientY - zoomAnchor.y) < 4) {
    zoomAnchor.time = now;
    return zoomAnchor.point;
  }
  const ray = rayAt(clientX, clientY).ray, reach = camera.position.distanceTo(controls.target);
  let point = data ? pick(clientX, clientY)?.point?.clone() : null;
  if (!point) {
    const ground = ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -controls.target.y), new THREE.Vector3());
    point = ground && ground.distanceTo(camera.position) < reach * 4 ? ground : ray.at(Math.max(reach, 1), new THREE.Vector3());
  }
  zoomAnchor = { point, x: clientX, y: clientY, time: now };
  return point;
}
function wheelZoom(e) {
  e.preventDefault();
  if (gizmo.controls.dragging) return;
  // pixels, lines or pages to notches (a mouse notch is about 100 pixels; a touchpad sends many small ones)
  const pixels = e.deltaY * (e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 800 : 1);
  const notches = THREE.MathUtils.clamp(pixels / 100, -3, 3);
  if (!notches) return;
  const point = zoomPoint(e.clientX, e.clientY);
  const forward = new THREE.Vector3().subVectors(controls.target, camera.position).normalize();
  // scrolled up (deltaY below 0) zooms in, as OrbitControls did: under 1 nears the point, over 1 backs away
  const factor = Math.pow(1 - ZOOM_STEP, -notches);
  const next = point.clone().addScaledVector(new THREE.Vector3().subVectors(camera.position, point), factor);
  if (next.distanceTo(point) > camera.far * 0.5) return;    // as far out as the view reaches
  camera.position.copy(next);
  const depth = Math.max(1, new THREE.Vector3().subVectors(point, camera.position).dot(forward));
  controls.target.copy(camera.position).addScaledVector(forward, depth);
  // close in, the near plane comes in too, so the surface isn't cut away; back out it returns to the framing's
  const near = THREE.MathUtils.clamp(depth / 50, 0.2, frameNear);
  if (Math.abs(near - camera.near) > 1e-3) { camera.near = near; camera.updateProjectionMatrix(); }
  controls.update();
}
controls.enableZoom = false;
controls.addEventListener('start', () => { zoomAnchor = null; });    // orbited or panned: a new burst picks again
renderer.domElement.addEventListener('wheel', wheelZoom, { passive: false });
document.addEventListener('keyup', e => {
  panKeys.delete(e.key.toLowerCase());
  panFast = e.shiftKey;
});
// Shift pressed while a move or turn key is already held speeds the camera up at once (it used to wait for the next key
// press: Discord feedback B1)
document.addEventListener('keydown', e => { if (e.key === 'Shift') panFast = true; });
window.addEventListener('blur', () => { panKeys.clear(); panFast = false; });
// The editor's keys (index.html's help panel lists them for users): V select, T box select, G move, R rotate (while
// placing, R and Shift+R turn the piece), P the Add panel, M the map browser, X world or local axes, C the pivot
// (origin or centre), F frame, L level snap, O solo the selected lights, B Break on a picked wall, floor or roof that
// breaks (else the play area), I the eyedropper while drawing; Shift+N, B, L, Z, U and X the six views (in the
// Buildings view N draws a new box); arrow keys and WASD move the camera and Q and E turn it; Escape cancels a drag,
// stops placing, drawing or a pick, closes a menu or, when there is none of those, clears the selection; Ctrl+Z /
// Ctrl+Y (or Ctrl+Shift+Z) undo and redo, Ctrl+C / X / V copy, cut and paste, Ctrl+G groups the selection and
// Ctrl+Shift+G ungroups the selected group, Delete deletes; a picked landing zone or spawn point takes Delete, Ctrl+D
// (a copy) and [ ] (a quarter turn); Ctrl+S saves, Ctrl+B builds and Ctrl+O loads a project. Typing in a field never
// triggers them (Ctrl+S, B and O aside), and Ctrl+C with nothing selected is the browser's own copy. An open dialog
// (modalOpen) keeps the keys.
document.addEventListener('keydown', e => {
  const key = e.key.toLowerCase();
  if (modalOpen()) { if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f', 'b'].includes(key)) e.preventDefault(); return; }
  if ((e.ctrlKey || e.metaKey) && key === 's') { e.preventDefault(); if (!e.repeat) saveProject(); return; }
  if ((e.ctrlKey || e.metaKey) && key === 'o') { e.preventDefault(); if (!e.repeat) showFileDialog('load'); return; }
  if ((e.ctrlKey || e.metaKey) && key === 'b') { e.preventDefault(); if (!e.repeat) openBuild(); return; }
  if (e.target.closest?.('input, select, textarea, [contenteditable]')) return;
  // while a light's handle is dragged, Escape puts it back and other keys wait
  if (lightDrag) { if (key === 'escape') endLightDrag(false); e.preventDefault(); return; }
  if (volumeDrag) { if (key === 'escape') endVolumeDrag(false); e.preventDefault(); return; }
  if (coverDrag) { if (key === 'escape') endCoverDrag(false); e.preventDefault(); return; }
  if (wallDrag) { if (key === 'escape') endWallDrag(false); e.preventDefault(); return; }
  if (rockPoint && key === 'escape') { if (!cancelPointDrag()) releaseRockPoint(); e.preventDefault(); return; }
  if (wallDrawing && key === 'escape') {
    if (wallDrawing.start) { try { renderer.domElement.releasePointerCapture(wallDrawing.pointerId); } catch { /* released */ }
      wallDrawing.start = null; wallDrawing.pointerId = null; wallGhost.visible = false; wallHint(); }
    else stopWallDrawing();
    e.preventDefault(); return;
  }
  if (pickDrag) { if (key === 'escape') endPickDrag(false); e.preventDefault(); return; }
  if (zoneGizmo.dragging) { if (key === 'escape') cancelZoneGizmo(); e.preventDefault(); return; }
  if (missionGizmo.dragging) { if (key === 'escape') cancelMissionGizmo(); e.preventDefault(); return; }
  if (gridDrag) { if (key === 'escape') endGridDrag(false); e.preventDefault(); return; }
  if (gridTool && key === 'escape' && !pickedZone && !selected && !placing) { setGridTool(false); e.preventDefault(); return; }
  if (zonePlacing && key === 'escape') { stopZonePlacing(); e.preventDefault(); return; }
  if (spawnPlacing && key === 'escape') { stopSpawnPlacing(); e.preventDefault(); return; }
  if (lookPicking && key === 'escape') { stopLookPick(); e.preventDefault(); return; }
  if (breaking && key === 'escape') { stopBreak(); e.preventDefault(); return; }
  // B: Break on the picked made wall, floor or roof, or off again (B5)
  if (key === 'b' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.repeat
      && (breaking || isMadeWall(madeRoot(selected)?.userData.source) || isMadeSlab(madeRoot(selected)?.userData.source)
          || mapBreakable(roots.get(selected)?.userData.source))) {
    if (breaking) stopBreak(); else startBreak();
    e.preventDefault(); return;
  }
  // I: the eyedropper, while a wall, slab or ground tool draws (M4c; the look picker's own I is its panel's)
  if (key === 'i' && !e.ctrlKey && !e.metaKey && !e.altKey && wallDrawing) {
    startLookPick(wallDrawing.ground ? 'ground' : wallDrawing.slab ? 'slab' : 'wall');
    e.preventDefault(); return;
  }
  // a picked landing zone: Delete, Ctrl+D copies, G and R its gizmo's arrows or ring, [ and ] turn it, Escape lets it
  // go (Ctrl+Z undoes as for anything)
  if (pickedZone && !selected && !e.altKey) {
    if (key === 'delete' && !e.ctrlKey && !e.metaKey) { deleteZone(); e.preventDefault(); return; }
    if ((e.ctrlKey || e.metaKey) && key === 'd') { copyZone(); e.preventDefault(); return; }
    if (key === '[' || key === ']') { turnZone(key === '[' ? -1 : 1); e.preventDefault(); return; }
    if ((key === 'g' || key === 'r') && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      setZoneGizmoMode(key === 'r' ? 'rotate' : 'translate'); e.preventDefault(); return;
    }
    if (key === 'escape') { pickZone(null); e.preventDefault(); return; }
  }
  // the Effects view: Escape lets the picked marker go (a drag or a placing first gives way)
  if (effectsOn && pickedEffect && key === 'escape' && !e.ctrlKey && !e.metaKey && !e.altKey && !gizmo.busy() && !placing) { pickEffect(null); e.preventDefault(); return; }
  // a picked spawn marker (or a zone the Spawns view describes): Escape lets it go
  if ((pickedSpawn || spawnZonePick) && !selected && key === 'escape' && !e.ctrlKey && !e.metaKey && !e.altKey && !gizmo.busy() && !placing) { setPickedSpawn(null); e.preventDefault(); return; }
  // a picked base pod, Meld point or drop-in point, or a copy (SP6, SP7), as a landing zone: Delete, Ctrl+D copies,
  // [ and ] turn a drop-in point a quarter
  {
    const se = pickedSpawn && !selected && !e.altKey && !placing && !gizmo.busy() ? spawnEntry(pickedSpawn) : null;
    if (se && ['base', 'copy'].includes(se.layer) && projectsAvailable() && (spawnMovable(se) || spawnDeleted(se))) {
      if (key === 'delete' && !e.ctrlKey && !e.metaKey) { deleteSpawn(pickedSpawn); e.preventDefault(); return; }
      if ((e.ctrlKey || e.metaKey) && key === 'd') { copySpawn(pickedSpawn); e.preventDefault(); return; }
      // (a drop-in point only: a pod's facing aims nothing, the user, 18 November 2026)
      if ((key === '[' || key === ']') && !e.ctrlKey && !e.metaKey && TURNED_KINDS.includes(se.record.kind) && spawnMovable(se)) {
        const turn = key === '[' ? -QUARTER : QUARTER, hint = `Turned a quarter ${turn > 0 ? 'right' : 'left'}`;
        if (se.layer === 'copy') editSpawnCopy(se.record.actor, { turn }, hint); else editBaseSpawn(se.record.actor, { turn }, hint);
        e.preventDefault(); return;
      }
    }
  }
  // the select box: Enter takes what is inside (Shift+Enter adds it to the selection), Escape puts the box away
  if ((pickTool || pickBox) && !e.ctrlKey && !e.metaKey && !e.altKey && !placing) {
    if (key === 'escape' && !gizmo.controls.dragging) { stopPickBox(); e.preventDefault(); return; }
    if (key === 'enter' && pickBox) { takePickBox(e.shiftKey); e.preventDefault(); return; }
  }
  if (volumesOn && !e.ctrlKey && !e.metaKey && !e.altKey && !placing) {
    if (key === 'escape' && volumeTool) { setVolumeTool(null); e.preventDefault(); return; }
    if (key === 'escape' && ownPicked && !selected) { setOwnPicked(null); e.preventDefault(); return; }
    if (key === 'n' && !e.shiftKey) { setVolumeTool(volumeTool === 'new' ? null : 'new'); e.preventDefault(); return; }
    if (key === 'r') { flashHint('A building\'s box is not turned'); e.preventDefault(); return; }
  }
  if (e.ctrlKey || e.metaKey) {
    if (e.altKey) return;
    if (key === 'z' && !e.shiftKey) undoStep();
    else if (key === 'y' || (key === 'z' && e.shiftKey)) undoStep(true);
    else if ((key === 'c' || key === 'x') && selected) copySelection(key === 'x');
    else if (key === 'v') paste();
    else if (key === 'g') { if (!e.repeat && !volumesOn && !lightsOn) groupShortcut(e.shiftKey); }
    else return;
  } else if (key === 'delete') { if (!selected && !ownSet.size) return; if (!deleteWallOpening()) deleteSelection(); }
  else if (key === 'escape') {
    if (assigning) { setAssigning(null); lightPanel(); flashHint('Assigning cancelled'); }
    else if (gizmo.cancel()) dragHint(false);
    else if (placing) stopPlacing();
    else if (document.querySelector('.pop:not([hidden])')) showPop(null);
    else if (selected) select(null);
    else if (ownSet.size || (ownPicked && !volumesOn)) { ownSet.clear(); setOwnPickedValue(null); refreshVolumes(); volumePanel(); }
    else return;
  }
  else if (e.altKey) return;
  else if (PAN_KEYS[key] || TURN_KEYS[key]) { panKeys.add(key); panFast = e.shiftKey; }
  else if (key === 'p') { if (data) showPieces(!pieces.open); }
  else if (key === 'm') showMapBrowser();
  else if (key === 'r') {
    // While placing, R turns the piece a quarter turn about its pivot (Shift+R the other way); otherwise it is Rotate.
    if (!placing) { gizmo.setMode('rotate'); e.preventDefault(); return; }
    placing.turns = (placing.turns + (e.shiftKey ? 3 : 1)) % 4; setGhostDirty(true);
    clearTimeout(hintTimer); restingHint();
  }
  else if (key === 'v') gizmo.setMode('off');
  else if (key === 't') { if (data && !e.repeat) setPickTool(!(pickTool || pickBox)); }
  else if (key === 'g') gizmo.setMode('translate');
  else if (key === 'x') { if (e.shiftKey) { if (data) setEffectsShown(!effectsOn); } else gizmo.toggleSpace(); }
  else if (key === 'c') togglePivot();
  else if (key === 'b') {
    if (e.shiftKey) { if (data) setVolumesShown(!volumesOn); }
    else { if (!playArea.children.length) return; setPlayArea(!playArea.visible); }
  }
  else if (key === 'l') { if (e.shiftKey) { if (data) setLightsShown(!lightsOn); } else setLevelSnap(!levelSnap); }
  else if (key === 'n') { if (!e.shiftKey || !data) return; setNormalView(); }
  else if (key === 'z') { if (!e.shiftKey || !data) return; setZonesShown(!zonesOn); }
  else if (key === 'u') { if (!e.shiftKey || !data) return; setSpawnsShown(!spawnsOn); }
  else if (key === 'o') { if (!lightRoots.has(selected)) return; setSolo(!soloOn); }
  else if (key === 'f') { if (!(effectsOn && frameEffect())) frame(selected ? allRoots.get(selected) : undefined); }
  else return;
  e.preventDefault();
});
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
