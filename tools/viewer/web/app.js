import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { createGizmo, placedPose, actorMatrix, recipeMove } from './gizmo.js';
import { collectPieces, createPieceBrowser, destructionNote, lootNote, pieceGrid, useFamilies } from './pieces.js';
import { api as projectApi, memberKey, newDocument, sortState, sourceOf, stateKey, targetKey, tidyLocation, tidyRotator, uuid,
         validAdded, validBinding, validGroup, validOverride, validStage, tidyStage, stageMax, STAGE_LEVELS_PLAYED, STAGE_MAPS,
         validBuilding, tidyBuilding, BUILDING_FLOORS_MAX, groupKey, buildingKey, pruneGroups, validPrefabMark, mapBuildingId,
         BUILDING_SAME, validLandingZone, validSpawnRules, SCHEMA_VERSION as PROJECT_SCHEMA_VERSION } from './project.js';
import { ROLES as FLAG_ROLES, lowPiece, normalize as normalizeFlags, plan as planFlags, rawOf as flagRaw, roles as flagRoles } from './piece_flags.js';
import { ownLandings, startingZones, place as zonePlace, soldierSpots, landingUnmoved, groundOf, evacBox, ownSlots, explicitEw, turn as turnBy, yawOf, DIRECTIONS as ZONE_DIRECTIONS, GROUND as ZONE_GROUND } from './spawns.js';
import { createProjectDialog, savedWhen } from './project_files.js';
import { playApi, renderInstalls } from './play.js';
import { createSquadDialog, squadLine } from './squad.js';
import { createProjectManager } from './manager.js';
import { chipWords, createQueueController } from './build_queue.js';
import { createGameMaps } from './gamemaps.js';
import { createMapBrowser } from './map_browser.js';
import { createSetupDialog, setupApi } from './setup.js';
import { createBuildOptions, savingHelp } from './build_options.js';
import { ADDED_KINDS, addedMission, kindKey, missionNote, setParagraphs, zoneServes } from './missions.js';
import { createMissionsPanel } from './missions_panel.js';
import { FAMILIES, KINDS, NEW_VOLUME, SPAWN_COPY_KINDS, SPAWN_VALUE_KEYS, addFacingPointer, addPlace, addTemplate, baseEditWords, boxMiddle, boxWords, copyEntry,
         copyEntryOf, copyMarkerRecord, copyRecord, copyTemplateWhy, deletedEntry, editCopy, editSpawn, familyOf, identityLines, makeSpawnBox, makeSpawnMarker, paintSpawnMarker,
         recordBox, shownEntries, spawnEditable, SPAWN_MARKER_SIZE, spawnEntryOf, spawnKey, spawnMoveWords, spawnNamed, spawnOverride, spawnRecords, titleOf,
         volumePlace } from './spawns_view.js';
import { consumerWords, fromWords, useLines } from './spawn_rules.js';
import { boxShape, makeEffectMarker, nearestMarker, paintEffectMarker, reachShape } from './effects_view.js';
import { SWAP, drawable, leftOut, makeLikeness, viewHeight } from './effects_preview.js';
import { LIMITS as LIKENESS_LIMITS, parametersOf } from './effects_sim.js';
import { KIND_LABEL, VALUE_LIMITS, effectRecords, keptValues, parameterControls, parameterRows, recordChips, recordLines, recordName, savedValues,
         soundReach, survivesClear, tintOf, tintVector, valuesViewOnly, withValues } from './effects_rules.js';
import { createPrecache } from './precache.js';
import { createLibraryBrowser, SOFT } from './library.js';
import { api as prefabApi, createPrefabBrowser, newPrefab, prefabWords } from './prefabs.js';
import { emptyPrefabScene, measurePrefab, normalizePrefab, reconcilePrefab, orderedWrites, PREFAB_GRID_TOP, PREFAB_MIN_Z,
         PREFAB_MAX_Z, PREFAB_GRID_LEVELS, PREFAB_PLAYED_LEVELS, PREFAB_PLAYED_TOP, PREFAB_TILES } from './prefab_document.js';
import { createPrefabTest } from './prefab_test.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createMapLighting, withLocalLights } from './lighting.js';
import { HANDLE_COLOURS, SOLO_MAX, boxInReach, boxLines, createSolo, emissionShape, lightHandles, makeHandle, makeMarker,
         nearestValue, paintMarker, recordNow, scaleMarker, valuesOf } from './lights_view.js';
import { effectiveConeDegrees, storableCone } from './light_rules.js';
import { visibleBounds, footprintOf, tileGridAround, focusBounds, interiorPlanes, tileGridOf, floorTilesOverlay } from './view_layout.js';
import { ladderEnds, addedFloors } from './ladders.js';
import { COVER_KIND, COVER_MATERIAL, coverBox, coverFaces, coverMaterial, coverMeshId, coverMeshRecord, coverScene, coverStart,
         coverWords, floorStart, isBlocker, isFloor, lengthWords, normalCover, resizedCover, retyped, sizeWords } from './cover.js';
import { gridMove, nearestGridPose } from './poserule.js';
import { WALL, WALL_LOOKS, drawnWall, flippedWall, movedOpening, openingKind, openingParts, openingPlay, openingWords, playWords,
         raisedWall, resizedWall, reshuffled, shiftedLocation, sortedOpenings, storeysOf, toolWall, wallTop, wallWords, withOpening,
         withoutOpening, withStoreys } from './walls.js';
import { buildingWithFloor, classifyFloors, copyFloors, floorAt, floorIndex, floorStamps, floorUnder, levelHeight, ownedFloors,
         stampSignature, storeyHeight, worldBox, touchedFloors, ruleListing, floorsOf, floorsAround, sourceFloorMatch,
         buildingProblems, STOREY_HEIGHT, cursorStoreys, storeysOver, cursorMiss, CURSOR_NEAR, carriedListing, floorMapOf } from './floors.js';

const $ = id => document.getElementById(id);
const prefabParameter = new URLSearchParams(location.search).get('prefab');
const builderMode = prefabParameter !== null;
const builder = { doc: null, kept: [], envelope: null, metadata: new Map(), savedKey: '', loading: true, repairing: false };
const documentWrites = orderedWrites();
let leaving = false, navigating = false;
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
const roots = new Map(), pickables = [], texturePromises = new Map();
// The map's lights, their own roots (editor lights plan 4.6; the lights section below), and every root the gizmo moves:
// pieces and lights.
const lightRoots = new Map(), lightLayer = new THREE.Group();
world.add(lightLayer);
// The project's building boxes, their own roots too (the Buildings view, further down).
const volumeRoots = new Map(), volumeLayer = new THREE.Group();
// Box select (its section is below the Buildings view's): the tool waiting for a drag, the box, the drag, what the
// box would take, and the pieces' middles while it is up.
let pickTool = false, pickBox = null, pickDrag = null, pickHits = [], pickCentres = null;
// The three views (the user, 11 November 2026): Normal, Buildings (volumesOn) and Lights (lightsOn), one at a time.
// In the Buildings view only boxes are picked, in the Lights view only lights. In the normal view pieces are, and
// with the Normal button's two switches also lights (normalLights) and the project's floor boxes (boxesShown), a
// building whole. Both switches are off whenever a map opens.
let boxesShown = false, lightsOn = false, normalLights = false;
// the Landing zones view (the user, 13 November 2026): the zones over everything, and only they are picked
let zonesOn = false, zonesHidBefore = false;
// the Effects view (effects and sounds plan, FX1; below the mission objects): its markers, and only they are picked.
// Since FX3 each effect, sound and lens flare is a root of its own (effectRoots, an original's also by its key in
// effectIndex), moved and turned by the gizmo, copied and deleted as pieces are where its family builds; the Normal
// button's Effects switch (normalEffects) draws and picks them with pieces in the normal view. effectMarkers: the
// markers drawn now, the roots' and the copies a piece's copy carries.
let effectsOn = false, pickedEffect = null, effectsDirty = true, effectMarkers = [], normalEffects = false;
// the Spawns view (editor spawns plan, SP3; its section is below the landing zones'): only its markers are picked; the
// Normal button's switch (normalSpawns, remembered) draws and picks them with pieces
let spawnsOn = false, normalSpawns = false, spawnLayerReady = false;
const effectRoots = new Map(), effectIndex = new Map();
let wavePlayer = null;     // the Wave preview's player: { audio, wave, record (its id), state: loading, playing or failed, why }
world.add(volumeLayer);
const allRoots = { get: id => roots.get(id) ?? lightRoots.get(id) ?? volumeRoots.get(id) ?? effectRoots.get(id),
                   has: id => roots.has(id) || lightRoots.has(id) || volumeRoots.has(id) || effectRoots.has(id),
                   values: () => [...roots.values(), ...lightRoots.values(), ...volumeRoots.values(), ...effectRoots.values()][Symbol.iterator]() };
const cutMaterials = new Map();
const helperMaterial = new THREE.MeshBasicMaterial({color:0x59d5df,wireframe:true,transparent:true,opacity:0.65,depthWrite:false});
const textureLoader = new THREE.TextureLoader();
const gltfLoader = new GLTFLoader();
// Trial edits: the gizmo moves whole actors in the view only; nothing is saved or built.
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
// groups: id -> { id, locked, breakTogether, members: Map(member key -> member record) }; groupIndex: member key -> the
// group it is a direct member of (a piece's key, or a group's: groupKey(id)).
let groups = new Map(), groupIndex = new Map();
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
function setGroups(next) {
  groups = next; groupIndex = new Map();
  for (const g of groups.values()) for (const k of g.members.keys()) groupIndex.set(k, g);
}
const cloneGroup = g => ({ ...g, members: new Map(g.members) });
const cloneGroups = (from = groups) => new Map([...from].map(([id, g]) => [id, cloneGroup(g)]));
// Pieces of the packages a mission streams into the map (LWR's patches, mission objects): shown for reference, never
// edited (a project edits the map's own pieces; the Build makes nothing of theirs).
const isStream = o => o?.layer === 'stream';
// The families of pieces and the map's assemblies (families.json, tools/viewer/families.py: the compiler's own), or
// null from a server without them. assemblyIndex: an original's key (package|level|actor) to its assembly.
let families = null, assemblyIndex = new Map(), originalIndex = null;
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
  return isMadeWall(o) ? { location: [original.location[0], original.location[1], o.location[2]], rotation: original.rotation }
    : { location: original.location, rotation: original.rotation };
}
const gridOrigin = () => data?.tileGrid?.origin?.slice(0, 2) ?? null;
// The corner the game counts its tiles from (export 26's tileGrid.tiles, its world data's WorldBounds; for an older
// export a unit under the origin, as on every installed map), [x, y, z]: a point's tile (a ladder's ends, a mission
// object's, a soldier's spot, the floor under a piece placed) is counted from it, as compiler.py tile_corner has it.
// Placing (snap, the lines, the grid rule) keeps the origin, the level volume's corner, where the maps' pieces stand.
const tileCorner = () => data?.tileGrid?.tiles ?? data?.tileGrid?.origin?.map(v => v - 1) ?? null;
// The map's size as the project sets it (project.js validStage): { grid: [nx, ny], ground } or null for the map's own
// (setStage, further down, draws it).
let stage = null;
// A cleared map (Clear map plan, section 6): the Build takes out what the editor never showed; the map's size may then
// be set as on the blank map, smaller too. The landing zones as the project sets them (project.js validLandingZone):
// null while the project keeps the map's own landings and the install's lines (zonesNow gives those); the install's
// lines for the map (GET landing-lines.json) and its kind come with the map.
let cleared = false, landingZones = null, landingLines = { kind: null, lines: [] };
// The clear kept the scenery outside the play area (the Clear map window's tick): the Build's clear_level then leaves
// the lights, smoke, stains and glints placed out there, and so does the view
let clearKeepsOutside = false;
// The missions the project is for (mission types plan, D1): null, every mission of the base map; else the list of
// {record: i} and {kind, ship?} entries the Build writes records for (the Missions panel, Clear map's question)
let projectMissions = null;
// the project's spawn rules (spawns plan, SP8): null, or { dropIns: 'placed' } (a malformed one is carried as saved)
let projectSpawnRules = null;
// The buildings drawn as boxes and edited (project.js validBuilding; setBuildings, further down, draws them): the
// project's, made from nothing by the Build, and the map's own that can be edited, each as the project's are (map
// buildings plan, section 1). allBuildings is what the floors code reads: the map's as exported where unchanged (their
// saved listings), the project's and the changed ones of the map by their boxes.
let buildings = [], buildingsVersion = 0, mergedBuildings = null;
const PROJECT_BUILDING = 'project:';
function allBuildings() {
  if (!mergedBuildings) {
    const edits = mapEdits();
    mergedBuildings = [...(data?.buildings ?? []).filter(b => !edits.exportIds.has(b.id) && !(cleared && !mapEditable(b))),
      ...buildings.filter(b => !buildingMeta.get(b.id)?.map || edits.changed.has(b.id))
        .map(b => ({ id: PROJECT_BUILDING + b.id, name: b.name || 'Building', project: b, floors: floorsOf(b), map: buildingMeta.get(b.id)?.map ?? null }))];
  }
  return mergedBuildings;
}
// The map's own buildings (export 21): one that can be edited is drawn and edited as the project's are, under the id
// made from its actor; a van's (it goes with the van), one with a floor that has no floor volume, a patch's, and every
// one of an older export, a preview or the prefab builder stays fixed, drawn grey to be read.
const mapEditable = b => data?.scope === 'map' && !data.preview && !builderMode && data.exporterVersion >= 21 && Boolean(b.actor)
  && !b.van && /^\d+$/.test(String(b.id)) && (b.floors ?? []).length > 0
  && b.floors.every(f => (f.volumes ?? []).length > 0 && (f.boxes ?? []).length === f.volumes.length);
const mapIdOf = b => mapBuildingId(b.level ?? 'PersistentLevel', b.actor);
const mapTarget = b => ({ package: data.name, level: 'base', actor: b.name });
const mapKind = b => (b.isUfo ? 'ufo' : 'building');
// a map building's floors as the map has them, as a record's: boxes and the floor volume each is
const mapFloors = b => b.floors.map(f => ({ boxes: f.boxes.map(x => [...x.min, ...x.max]), volumes: f.volumes.map(short) }));
// Whether a live record of a map building differs from the map's: its name, kind or a floor (every box within
// BUILDING_SAME of its own volume's, each volume once: the compiler's rule).
function mapChanged(b) {
  const e = buildingMeta.get(b.id)?.map;
  if (!e) return true;
  if ((b.name || '') !== short(e.actor) || (b.kind ?? 'building') !== mapKind(e) || b.floors.length !== e.floors.length) return true;
  const own = mapFloors(e);
  return b.floors.some((f, k) => {
    const boxes = new Map(own[k].volumes.map((v, n) => [v, own[k].boxes[n]]));
    return f.volumes.length !== boxes.size || new Set(f.volumes).size !== f.volumes.length
      || f.volumes.some((v, n) => !boxes.has(v) || boxes.get(v).some((x, j) => Math.abs(x - f.boxes[n][j]) > BUILDING_SAME));
  });
}
// Which map buildings the project changed (by their boxes, name or kind) and deleted (no box left), worked out once
// for each state of the buildings: changed, gone (ids), exportIds (the export's ids of both).
let mapEditsCache = null;
function mapEdits() {
  if (mapEditsCache?.version === buildingsVersion) return mapEditsCache;
  const live = new Map(buildings.map(b => [b.id, b])), changed = new Set(), gone = new Set(), exportIds = new Set();
  for (const [id, m] of buildingMeta) if (m.map) {
    const b = live.get(id);
    if (!b) { gone.add(id); exportIds.add(m.map.id); }
    else if (mapChanged(b)) { changed.add(id); exportIds.add(m.map.id); }
  }
  return (mapEditsCache = { version: buildingsVersion, changed, gone, exportIds });
}
// What the project saves of the buildings: its own, and the map's changed or deleted (an unchanged one is the map's).
function savedBuildings() {
  const edits = mapEdits();
  return [...buildings.filter(b => !buildingMeta.get(b.id)?.map || edits.changed.has(b.id)),
          ...[...edits.gone].map(id => ({ id, replaces: mapTarget(buildingMeta.get(id).map), deleted: true }))];
}
// Whether a box of a building is new or changed (the compiler's warnings are said for those only): a box of the
// project's own is; one of the map's is when it has no volume of the map's or stands away from its volume's box.
function freshBox(b, k, n) {
  const e = buildingMeta.get(b.id)?.map;
  if (!e) return true;
  const v = b.floors[k]?.volumes?.[n], own = mapFloors(e).flatMap(f => f.volumes.map((name, i) => [name, f.boxes[i]])).find(x => x[0] === v);
  return !own || own[1].some((x, j) => Math.abs(x - b.floors[k].boxes[n][j]) > BUILDING_SAME);
}
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
  families = table; assemblyIndex = new Map();
  const prefabOf = new Map(data.objects.filter(o => o.prefab && o.layer === 'base').map(o => [o.actor, o.prefab]));
  for (const a of table?.assemblies ?? []) {
    const tag = a.members.length > 1 ? (a.members.map(m => prefabOf.get(m)).find(Boolean) ?? short(a.pivot)) : null;
    const assembly = { ...a, tag };
    for (const m of a.members) assemblyIndex.set(targetKey({ package: table.map, level: 'base', actor: m }), assembly);
  }
  useFamilies(table, o => assemblyOf(o)?.family ?? null);
  landingActors = Array.isArray(table?.landing) ? new Set(table.landing) : null;
  gizmo.regroup();
}
let data, selected, originalPositions = false, loadErrorCount = 0, lighting;
let activeMapId, cachePrefix='/cache/', mapCatalogue=null, mapBrowser=null;
let lightRadius = 700;

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
// Settings kept per browser (stats line, source details open). Storage can be missing or blocked.
const recall = key => { try { return localStorage.getItem(key); } catch { return null; } };
const remember = (key, value) => { try { localStorage.setItem(key, value); } catch { /* not kept */ } };
// The selection's group as a chip beside its name; groupPanel keeps it up to date.
const groupChip = document.createElement('span');
groupChip.hidden = true;
// add: Ctrl/Shift-click toggles the piece in the selection. keep: only refresh the panel and highlight.
// The piece panel shows only with a selection: name and what moves with it first, source paths folded away.
function select(id, add = false, keep = false) {
  if (!keep) gizmo.select(id, add);
  id = gizmo.active;
  // a piece or a light selected from a list while the Buildings view is on: the view steps aside
  if (volumesOn && id && !volumeRoots.has(id)) setVolumesShown(false);
  // the Landing zones view picks zones only: anything selected another way (a list, a paste, a placed piece) leaves it
  if (zonesOn && id) setZonesShown(false);
  // (the Effects view picks its markers only; an effect selected another way, a paste or an undo, opens it unless the
  // normal view draws effects)
  if (effectsOn && id && !effectRoots.has(id)) setEffectsShown(false);
  else if (id && effectRoots.has(id) && !effectsOn && !normalEffects) setEffectsShown(true);
  if (lightsOn && id && !lightRoots.has(id)) setLightsShown(false);
  else if (id && lightRoots.has(id) && !lightsShown) setLightsShown(true);
  if (id) ownPicked = null;
  if (!add && !keep) ownSet.clear();
  selected = id;
  { const was = pickedEffect; pickedEffect = effectRoots.has(id) ? id : null; if (was !== pickedEffect) effectsDirty = true; }     // (one that starts off is drawn while it is picked)
  const root = roots.get(id) ?? lightRoots.get(id) ?? volumeRoots.get(id) ?? effectRoots.get(id);
  for (const button of $('objects').querySelectorAll('.piece')) button.classList.toggle('active', button.dataset.id === id);
  $('inspector').hidden = !root || Boolean(root.userData.volume);
  $('rail').classList.toggle('idle', !root);
  $('lightBox').hidden = !root?.userData.light;
  $('coverBox').hidden = !root?.userData.source?.cover;
  $('wallBox').hidden = !isMadeWall(root?.userData.source);
  if (wallFocus && wallFocus.id !== id) wallFocus = null;
  if (!root || root.userData.volume || root.userData.effect) {
    highlight.visible = false; ladderMarks.visible = false;
    if (root?.userData.effect) $('inspector').hidden = true;
    paintEffects(); effectPanel(); drawEffectShape(); editChanged(); return;
  }
  if (root.userData.light) { showLight(root); return; }
  const obj = root.userData.source, mesh = data.meshes[obj.mesh];
  refreshHighlight(root);
  const details = $('details');
  details.replaceChildren();
  if (obj.cover) { showCover(root); return; }
  if (isMadeWall(obj)) wallPanel(root);
  text(details, 'h2', short(mesh.name));
  text(details, 'div', `${obj.actorClass} · ${obj.sourcePackage || data.source.file.split(/[\\/]/).at(-1)}`, 'sub');
  const chips = text(details, 'div', '', 'chips');
  chips.append(groupChip);
  const others = gizmo.selection().filter(r => r !== root);
  if (others.length) {
    const chip = text(chips, 'span', `Moves with ${selectionWords(others, 'other ')}`, 'chip');
    chip.title = [...new Set(others.map(rootName))].join('\n');
  }
  if (obj.layer === 'inherited') text(chips, 'span', obj.hidden ? 'Inherited patch · hidden helper' : 'Inherited patch', 'chip');
  if (isStream(obj)) {
    const stream = data.streams?.[obj.stream], lwr = stream?.kind === 'lwr';
    const missions = (data.missions || []).filter(m => m.streams.includes(obj.stream)).map(missionName);
    text(chips, 'span', `${lwr ? 'LWR patch' : 'Mission stream'}${obj.hidden ? ' · hidden in game' : ''} · not editable`, 'chip warn').title =
      `From ${obj.stream}, which ${missions.length ? `the ${missions.join(', ')} mission${missions.length > 1 ? 's stream' : ' streams'}` : 'the map streams'} into the map. `
      + `It is shown for reference: a project edits the map's own pieces, and the Build leaves this package as it is.`;
  }
  if (obj.provenance) text(chips, 'span', `Patch ${obj.provenance.type}`, 'chip');
  if (obj.added) text(chips, 'span', 'Added copy', 'chip').title = `A copy of ${short(obj.added.from.actor)}`;
  // a piece of another map (library.js): the Build brings it from its home map
  if (obj.foreign) text(chips, 'span', `From ${obj.foreign.package}`, 'chip').title = foreignNote(obj);
  // export 15: the map's Kismet names the piece (the compiler's mission-linked: a warning when it is moved or deleted)
  if (obj.referencedBy?.length && !obj.added) text(chips, 'span', 'Mission script', 'chip warn').title =
    `Named by the map's Kismet (${obj.referencedBy.join('; ')}). Copied, it is an ordinary piece; moved or deleted, its `
    + 'mission script acts on the hidden original, not on the copy (the Build warns of it)';
  // F-45: LWR's landing-zone mutator spawns the landing from these (compiler.LANDING_PREFIXES)
  if (!isStream(obj) && !obj.foreign && isLanding(obj)) text(chips, 'span', obj.added ? 'Copy of a landing piece' : 'Landing zone', obj.added ? 'chip' : 'chip warn').title =
    obj.added ? 'A copy of one of the map\'s landing-zone pieces: an ordinary piece'
    : `One of the map's landing-zone pieces (${obj.archetype}): LWR's landing-zone mutator spawns the landing from it, so `
      + 'moved or deleted the dropship\'s landing breaks (F-45; the Build warns of it). Copied, it is an ordinary piece';
  gridChip = text(chips, 'span', '', 'chip');
  ladderChip = text(chips, 'span', '', 'chip');
  ladderChip.title = LADDER_NOTE;
  const helpers = families?.helpers?.[obj.actor];
  if (helpers?.length && !obj.added && obj.layer === 'base') text(chips, 'span', `Patch helper${helpers.length > 1 ? 's' : ''}`, 'chip').title =
    `${helpers.map(h => `${short(h.actor)} in ${h.stream}${h.match === 'near' ? ` (near: ${h.distance} units off, with other ends)` : ''}`).join(', ')}: `
    + 'a hidden ladder a streamed patch places with this one. Moved or deleted, the Build takes it out of the variant\'s copy of the patch, so the old place no longer climbs';
  const loot = isStream(obj) ? null : lootNote(obj);
  if (loot) text(chips, 'span', loot.label, 'chip').title = loot.title;
  flagChip(chips, root);
  // the generated area lights it glows with (export 18's associations, or the project's): they follow it
  const glowActor = obj.added ? obj.added.from.actor : obj.actor;
  const glows = obj.foreign ? (obj.foreign.areaLights?.[glowActor]?.lights ?? []).map(light => short(light.actor))
    : [...lightRoots.values()].filter(r => r.userData.source.role === 'area' && areaOwner(r.userData.source).owner?.actor === glowActor)
      .map(r => short(r.userData.source.actor));
  const unsettled = (obj.areaLights ?? []).map(id => lightRoots.get(id)).filter(r => r && !areaOwner(r.userData.source).owner
                                                                                  && areaOwner(r.userData.source).how !== 'kept');
  if (glows.length && !isStream(obj)) {
    const chip = text(chips, 'span', `Glows · ${plural(glows.length, 'light')}`, 'chip');
    chip.title = `${glows.join(', ')}: generated lights the bake made for its glow. They move, copy and go `
      + 'with it; click to see them (Area lights in View options)';
    chip.onclick = () => { areaShown = true; remember(AREA_SHOWN, '1'); setLightsShown(true); };
  }
  // the effects it carries (export 23's carriedBy; tools/bake/native_effects.py): the Build moves, copies and deletes
  // them with it. A click shows them in the Effects view.
  const effects = obj.foreign || isStream(obj) ? [] : (data?.effects ?? []).filter(e => e.carriedBy === glowActor);
  if (effects.length) {
    const chip = text(chips, 'span', effects.length === 1 ? 'Carries an effect' : `Carries ${effects.length} effects`, 'chip');
    chip.title = `${effects.map(e => `${short(e.actor)} (${String(e.template ?? 'a particle system').split('.').at(-1)})`).join(', ')}: `
      + 'a particle effect standing on it, such as a Skyranger\'s lights. The Build moves, copies and deletes it with the piece. '
      + (effects[0].id ? 'Click to see it in the Effects view (Shift+X)' : 'Prepare the map again to see it in the Effects view');
    if (effects[0].id) chip.onclick = () => { setEffectsShown(true); pickEffect(effects[0].id); };
  }
  if (unsettled.length && !obj.added && !isStream(obj)) {
    const chip = text(chips, 'span', `May glow · ${plural(unsettled.length, 'light')} to settle`, 'chip warn');
    chip.title = `${unsettled.map(r => short(r.userData.source.actor)).join(', ')}: generated lights the export couldn't tie to one piece. Before this piece `
      + 'moves, assign each its glowing piece or keep it fixed (select the light: click to show area lights)';
    chip.onclick = () => { areaShown = true; remember(AREA_SHOWN, '1'); setLightsShown(true); select(unsettled[0].userData.source.id); };
  }
  // Hidden helpers are shown for inspection only; they cannot be copied.
  $('editCopy').disabled = !copyable().length;
  const dl = $('sourceFields');
  dl.replaceChildren();
  field(dl, 'Actor', short(obj.actor));
  if (obj.added) field(dl, 'Copied from', obj.foreign ? `${short(obj.added.from.actor)} of ${obj.foreign.package}` : short(obj.added.from.actor));
  if (obj.foreign) field(dl, 'Brought in', foreignCost(obj) ?? 'By the Build, from its home map').title = foreignNote(obj);
  field(dl, 'Class', obj.actorClass);
  // what the game's damage does to it (export 17): its toughness's health
  const breakage = destructionNote(obj, data.exporterVersion);
  field(dl, 'Destructible', breakage.destructible).title = breakage.title;
  if (breakage.health) field(dl, 'Health', breakage.health).title = breakage.title;
  field(dl, 'Package', obj.sourcePackage || data.source.file.split(/[\\/]/).at(-1));
  if (obj.editorLayers?.length) field(dl, 'Source layers', obj.editorLayers.join(', '));
  if (obj.provenance) {
    field(dl, 'Patch operation', `${obj.provenance.operation} · ${obj.provenance.type}`);
    field(dl, 'Source actor', obj.provenance.sourceActor);
  }
  field(dl, 'Map location', obj.location.map(v => v.toFixed(2)).join(', '));
  field(dl, 'Mesh', mesh.name);
  if (mesh.kind === 'skeletal') field(dl, 'Pose', `Reference pose · ${mesh.bones.length} bones`);
  field(dl, 'Floors', listingsNow(root).map(f => `${short(allBuildings().find(b => b.id === f.building)?.name || f.building)} · floor ${f.floor+1}${f.cutdownFloor ? ' (cuts down)' : ''}`).join('\n') || 'None').title =
    'The building floors whose cutaway it is in. A copy, or a piece moved, joins the floor it stands in, as the Build lists it';
  const materialNames = obj.materials.map(m => data.materials[m]?.name || 'Unresolved');
  field(dl, 'Materials', materialNames.map(short).join('\n')).title = materialNames.join('\n');
  $('copyPaths').onclick = () => copyText($('copyPaths'), [`Actor: ${obj.actor}`, `Mesh: ${mesh.name}`, ...materialNames.map(m => `Material: ${m}`)].join('\n'));
  // (a made wall's mesh is made by the Build from its numbers: the page doesn't count it)
  field(dl, 'Geometry', mesh.made ? 'Made by the Build from the numbers of the wall, as the view draws it'
    : `${mesh.vertices.toLocaleString()} vertices · ${mesh.triangles.toLocaleString()} triangles`);
  const actors = [...new Set(others.filter(r => !r.userData.volume).map(r => r.userData.source.actor))].filter(a => a !== obj.actor);
  if (actors.length) field(dl, 'Moves with', actors.map(short).join('\n'));
  editChanged();
}
// Piece flags (piece flags plan; piece_flags.js): the five settings of a piece that decide how the game's tiles and
// mouse use it (Blocks walking, Gives cover, Blocks sight, Floor, Mouse picks it), edited actor by actor for the
// pieces explicitly picked (gizmo.picks, not the linked pieces the selection moves with); one actor's components
// share one setting. root.userData.flags is the request the project saves, normalized (piece_flags.normalize: only
// what the map doesn't have already, and what keeps a prop's other roles as they were); the export's pieceFlags
// (export 27) are the map's own settings, an added piece's its template's. These are the settings the game's filters
// read, not a prediction of the finished tiles.
const FLAG_WORDS = { on: 'on', off: 'off', partial: 'partly on', unknown: 'unknown', 'n/a': '' };
const flagContract = () => families?.pieceFlags ?? null;
const flagKey = o => (o.added ? `added|${o.actor}` : `orig|${sourceKey(o)}`);
const flagSentences = list => list.filter(Boolean).map(s => sentence(s).replace(/\.?$/, '.')).join(' ');
// Why a piece takes no flags at all, or null.
function flagBlock(o) {
  const c = flagContract();
  if (!c) return 'the editor\'s server is older than its page: restart it (xcom_editor.cmd restart) to set flags';
  if (o.cover) return isFloor(o.cover) ? 'an invisible floor\'s cover is its own' : 'a cover block\'s cover is its own (its Cover setting)';
  if (isStream(o)) return 'it is a piece of a streamed level, which the editor doesn\'t edit';
  if (o.hidden || o.environment) return 'it is hidden in the game';
  if (!o.pieceFlags) return c.classes[o.actorClass] ? 'its map was exported before flags: open the map again to prepare it' : `the flags are not a setting of a ${o.actorClass}`;
  return null;
}
// The actors the Flags group edits, each once with all its components: [{ key, source, roots }].
function flagTargets(ids = gizmo.picks().ids) {
  const out = new Map();
  for (const id of ids) {
    const r = roots.get(id);
    if (!r || r.userData.deleted) continue;
    const key = flagKey(r.userData.source);
    if (!out.has(key)) out.set(key, { key, source: r.userData.source, roots: [] });
  }
  if (out.size) for (const r of roots.values()) out.get(flagKey(r.userData.source))?.roots.push(r);
  return [...out.values()];
}
// One actor's flags as the project has them: its settings, its request, what the request does, and each role after it
// with its limits (a low piece's from what is drawn of it where it stands: piece_flags.js lowPiece).
function flagView(t) {
  const c = flagContract(), pf = t.source.pieceFlags, { raw, assumed } = flagRaw(pf);
  const request = t.roots[0]?.userData.flags ?? {};
  const plan = planFlags(c, t.source.actorClass, raw, request, assumed);
  const written = new Set(plan.writes.map(([k]) => k));
  const boxes = t.roots.map(r => boxOf(r)).filter(Boolean);
  const box = boxes.length ? boxes.reduce((a, b) => a.map((v, k) => (k % 2 ? Math.max(v, b[k]) : Math.min(v, b[k])))) : null;
  const roles = flagRoles(c, t.source.actorClass, { ...raw, ...Object.fromEntries(plan.writes) },
                          { collides: pf.collides, bodySetup: pf.bodySetup, assumed: assumed.filter(k => !written.has(k)),
                            low: lowPiece(c, box, tileCorner()?.[2]) });
  return { raw, assumed, request, plan, roles };
}
// The Flags chip: a piece with a setting off (or half on), or whose flags the project changes.
function flagChip(chips, root) {
  const o = root.userData.source;
  if (flagBlock(o)) return;
  const v = flagView({ key: flagKey(o), source: o, roots: [root] }), c = flagContract();
  const off = FLAG_ROLES.filter(r => ['off', 'partial'].includes(v.plan.after[r]));
  const changed = Object.keys(v.request).length > 0;
  if (!off.length && !changed) return;
  const chip = text(chips, 'span', changed ? 'Flags · changed' : 'Flags', 'chip');
  chip.title = [...FLAG_ROLES.filter(r => v.plan.after[r] !== 'n/a').map(r => `${c.labels[r]}: ${FLAG_WORDS[v.plan.after[r]]}`
    + `${r in v.request ? ' (changed)' : ''}${(v.roles[r].limits ?? []).includes('assumed') ? ' (assumed)' : ''}`),
    'How the game\'s tiles and mouse use it; set in the Flags group below'].join('\n');
}
// The Flags group: a row per role over the picked actors (mixed where they differ), what limits each, why a row is
// greyed, and how many of the pieces take it.
let flagAsk = null;      // the question open about a prop's pathing gate: { key } (the picks it was asked for)
const flagSelectionKey = () => gizmo.picks().ids.join('|');
function closeFlagAsk() { flagAsk = null; $('flagsAsk').hidden = true; $('flagsAsk').replaceChildren(); }
function flagsPanel() {
  const box = $('flagsBox');
  const all = !data || volumesOn || lightsOn || zonesOn ? [] : flagTargets();
  if (flagAsk && flagAsk.key !== flagSelectionKey()) closeFlagAsk();
  if (!all.length || all.every(t => t.source.cover)) { box.hidden = true; return; }
  box.hidden = false;
  const c = flagContract(), usable = [], blocked = new Map();
  for (const t of all) {
    const why = flagBlock(t.source);
    if (why) blocked.set(why, (blocked.get(why) ?? 0) + 1); else usable.push(t);
  }
  const views = new Map(usable.map(t => [t.key, flagView(t)]));
  const rows = $('flagsRows');
  rows.replaceChildren();
  // a limit that holds for several rows of one piece (a prop's gate) is said once, under the rows
  const one = usable.length === 1 ? views.get(usable[0].key) : null, seen = new Map();
  for (const role of FLAG_ROLES) for (const k of one?.roles[role].limits ?? []) seen.set(k, (seen.get(k) ?? 0) + 1);
  const shared = [...seen].filter(([, n]) => n > 1).map(([k]) => k);
  for (const role of FLAG_ROLES) {
    const eligible = usable.filter(t => views.get(t.key).plan.after[role] !== 'n/a');
    const states = eligible.map(t => views.get(t.key).plan.after[role]);
    const label = document.createElement('label');
    label.className = 'flagrow';
    const input = document.createElement('input');
    input.type = 'checkbox';
    label.append(input);
    const name = text(label, 'span', c?.labels[role] ?? role, 'flagname');
    const state = text(name, 'span', '', 'flagstate');
    const why = text(label, 'span', '', 'flagwhy');
    const same = states.length > 0 && states.every(x => x === states[0]);
    input.checked = states.length > 0 && states.every(x => x === 'on');
    input.indeterminate = states.length > 0 && (!same || states.some(x => x === 'partial' || x === 'unknown'));
    input.disabled = !eligible.length;
    label.classList.toggle('off', !eligible.length);
    label.classList.toggle('changed', eligible.some(t => role in views.get(t.key).request));
    state.textContent = !eligible.length ? '' : same ? FLAG_WORDS[states[0]] : 'mixed';
    if (!eligible.length) {
      why.textContent = flagSentences([usable.length ? views.get(usable[0].key).roles[role].why : [...blocked.keys()][0]]);
    } else {
      const notes = eligible.length === 1 ? (views.get(eligible[0].key).roles[role].limits ?? []).filter(k => !shared.includes(k)).map(k => c.limits[k]) : [];
      const without = usable.length - eligible.length;
      if (without) notes.push(`${eligible.length} of ${usable.length} pieces: ${plural(without, 'piece')} ${without === 1 ? 'has' : 'have'} no such setting (${[...new Set(usable.filter(t => !eligible.includes(t)).map(t => t.source.actorClass))].join(', ')})`);
      if (eligible.length > 1 && states.includes('partial')) notes.push('partly on: a prop\'s pathing gate passes it by in the sweeps, not in the occupancy step');
      why.textContent = flagSentences(notes);
    }
    input.title = `${c?.labels[role] ?? role}: click to turn it ${states.length && states.every(x => x === 'on') ? 'off' : 'on'} for ${eligible.length === 1 ? 'this piece' : `these ${eligible.length} pieces`}`;
    input.onchange = () => flagClick(role);
    rows.append(label);
  }
  $('flagsCount').textContent = all.length > 1 ? plural(usable.length, 'piece') : '';
  const lines = [...shared.map(k => c.limits[k]), ...[...blocked].map(([why, n]) => `${all.length > 1 ? `${plural(n, 'piece')}: ` : ''}${why}`)];
  if (usable.some(t => t.roots.length > 1)) lines.push('a piece of several parts (a mesh and its glass) has one setting for all of them');
  const targeted = new Set(all.flatMap(t => t.roots));
  const carried = new Set(gizmo.selection().filter(r => !r.userData.light && !r.userData.volume && !r.userData.effect && !targeted.has(r)).map(r => flagKey(r.userData.source))).size;
  if (carried) lines.push(`${plural(carried, 'piece')} that ${carried === 1 ? 'moves' : 'move'} with the selection ${carried === 1 ? 'keeps its' : 'keep their'} own flags: pick ${carried === 1 ? 'it' : 'them'} too (or Select all) to set ${carried === 1 ? 'it' : 'them'}`);
  $('flagsTargets').textContent = flagSentences(lines);
  $('flagsReset').disabled = !usable.some(t => t.roots[0]?.userData.flags);
}
// A click on a row: every picked piece that has the role turned on, or off when all of them have it on.
function flagClick(role) {
  const usable = flagTargets().filter(t => !flagBlock(t.source));
  const views = new Map(usable.map(t => [t.key, flagView(t)]));
  const eligible = usable.filter(t => views.get(t.key).plan.after[role] !== 'n/a');
  if (!eligible.length) { flagsPanel(); return; }
  applyFlags(eligible, { [role]: !eligible.every(t => views.get(t.key).plan.after[role] === 'on') });
}
// A change ({role: on}) made to these actors as one undo step, after asking where a prop's pathing gate would change a
// half-on role (`resolve`: the answer, {actor key: {role: on}}).
function applyFlags(targets, change, resolve = new Map()) {
  const c = flagContract(), next = new Map(), conflicts = new Map();
  for (const t of targets) {
    const v = flagView(t), request = { ...v.request, ...change, ...(resolve.get(t.key) ?? {}) };
    const p = planFlags(c, t.source.actorClass, v.raw, request, v.assumed);
    const open = Object.keys(p.conflicts);
    if (open.length) { conflicts.set(t.key, open); continue; }
    const n = normalizeFlags(c, t.source.actorClass, v.raw, request, v.assumed, t.source.pieceFlags.collides);
    next.set(t.key, Object.keys(n).length ? n : null);
  }
  if (conflicts.size) { askFlags(targets, change, resolve, conflicts); return; }
  closeFlagAsk();
  commitFlags(targets, next);
}
function askFlags(targets, change, resolve, conflicts) {
  const c = flagContract(), roles = [...new Set([...conflicts.values()].flat())];
  const names = roles.map(r => c.labels[r]);
  const asked = Object.entries(change).map(([r, on]) => `${c.labels[r]} ${on ? 'on' : 'off'}`).join(' and ');
  flagAsk = { key: flagSelectionKey() };
  flagsPanel();
  const box = $('flagsAsk');
  box.replaceChildren();
  text(box, 'div', `${asked} opens the pathing gate (bIgnoreForPathing) of ${conflicts.size === 1 ? 'this prop' : plural(conflicts.size, 'prop')}. `
    + `${names.join(' and ')} ${roles.length === 1 ? 'is' : 'are'} partly on there and can't stay so: set ${roles.length === 1 ? 'it' : 'them'} too.`);
  const row = text(box, 'div', '', 'row');
  for (const on of [true, false]) {
    const b = text(row, 'button', `${roles.length === 1 ? names[0] : 'Them'} ${on ? 'on' : 'off'}`);
    b.type = 'button';
    b.onclick = () => {
      const more = new Map(resolve);
      for (const [key, open] of conflicts) more.set(key, { ...(more.get(key) ?? {}), ...Object.fromEntries(open.map(r => [r, on])) });
      applyFlags(targets, change, more);
    };
  }
  const cancel = text(row, 'button', 'Cancel');
  cancel.type = 'button';
  cancel.onclick = () => { closeFlagAsk(); flagsPanel(); };
  box.hidden = false;
  row.querySelector('button')?.focus();
}
// The actors' new requests (null: none) as one undo step; nothing when none changes.
function commitFlags(targets, next) {
  const before = new Map(targets.map(t => [t.key, t.roots[0]?.userData.flags ?? null]));
  const changed = targets.filter(t => JSON.stringify(before.get(t.key)) !== JSON.stringify(next.get(t.key) ?? null));
  if (!changed.length) { flagsPanel(); return; }
  const set = values => { for (const t of changed) for (const r of t.roots) r.userData.flags = values.get(t.key) ? { ...values.get(t.key) } : null; };
  gizmo.record({ redo: () => { set(next); flagsChanged(); }, undo: () => { set(before); flagsChanged(); } });
}
function flagsChanged() { if (selected && roots.get(selected)) select(selected, false, true); }
function resetFlags() {
  const targets = flagTargets().filter(t => !flagBlock(t.source) && t.roots[0]?.userData.flags);
  closeFlagAsk();
  if (targets.length) commitFlags(targets, new Map());
}
// Select all of a kind (piece flags plan, 2.4): every drawn piece with the same mesh as a picked one, by the mesh's
// full asset path (two packages' meshes of one short name are two kinds; another map's copy of a shared asset is the
// same kind), selected in one go; with a box drawn (box select), only those whose middle is inside it, as Select
// takes them. Hidden, deleted and streamed pieces, cover blocks, lights and floor boxes are left out. Selecting is no
// edit: no undo step and nothing to save. Moving, copying and deleting still take each piece's linked pieces with it.
function kindPiece(r) {
  const o = r.userData.source;
  return !r.userData.deleted && r.visible && !r.userData.light && !r.userData.volume && !isStream(o) && !o.cover && !o.hidden
    && !o.environment && typeof data.meshes[o.mesh]?.name === 'string';
}
// An effect's, a sound's or a lens flare's kind (effects and sounds plan, FX3b; a flare since FX6b): its particle
// system, the waves it plays or its flare template; null for a sound with no wave, a flare with no template, one not
// drawn or one the editor doesn't change.
function effectKind(r) {
  const o = r.userData.source;
  if (!r.visible || r.userData.deleted || isStream(o) || !effectsShown()) return null;
  if (effectViewOnly(o, 'move') && effectViewOnly(o, 'copy') && effectViewOnly(o, 'delete')) return null;
  if (o.kind === 'effect' && o.system) return `system:${o.system}`;
  if (o.kind === 'sound' && o.waves?.length) return `waves:${[...o.waves].sort().join('+')}`;
  if (o.kind === 'flare' && o.template) return `flare:${o.template}`;
  return null;
}
// the mesh a piece counts as for Select all of a kind: a made wall as its look's (its template's)
const kindMesh = r => { const m = data.meshes[r.userData.source.mesh]; return m.look ?? m.name; };
function kindSeeds() {
  const seeds = new Map();     // full mesh path -> its short name; an effect's system or a sound's waves -> its name
  for (const id of gizmo.picks().ids) {
    const r = roots.get(id), fx = r ? null : effectRoots.get(id);
    if (r && kindPiece(r)) { const name = kindMesh(r); seeds.set(name, short(name)); }
    const kind = fx && effectKind(fx);
    if (kind) seeds.set(kind, recordName(fx.userData.source, data));
  }
  return seeds;
}
function kindMatches(seeds) {
  const box = pickBox && !pickDrag ? pickBox : null, out = [];
  const inBox = at => at.every((v, k) => v >= box[k] - PICK_SLACK && v <= box[k + 3] + PICK_SLACK);
  for (const r of roots.values()) {
    if (!kindPiece(r) || !seeds.has(kindMesh(r))) continue;
    if (box) {
      const b = boxOf(r);
      if (!b) continue;
      if (!inBox([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2])) continue;
    }
    out.push(r);
  }
  let effects = 0, flares = 0;
  for (const r of effectRoots.values()) {
    const kind = effectKind(r), e = r.matrix.elements;
    if (!kind || !seeds.has(kind) || (box && !inBox([e[12], e[14], e[13]]))) continue;
    out.push(r); effects++;
    if (r.userData.source.kind === 'flare') flares++;
  }
  return { roots: out, box: Boolean(box), effects, flares, actors: new Set(out.map(r => (r.userData.effect ? r.userData.source.id : flagKey(r.userData.source)))).size };
}
// what Select all of a kind counts, in words: pieces, or effects and sounds where only those match
const kindCount = found => (found.flares && found.flares === found.roots.length ? plural(found.actors, 'lens flare')
  : found.effects && found.effects === found.roots.length ? `${found.actors} ${found.actors === 1 ? 'effect or sound' : 'effects and sounds'}` : plural(found.actors, 'piece'));
function kindButton() {
  const button = $('editKind'), seeds = data ? kindSeeds() : new Map();
  // the effect panel's own button (a picked effect's or sound's panel stands in the piece panel's place)
  const twin = $('effectKind'), mirror = () => { twin.hidden = !seeds.size || ![...seeds.keys()].some(k => /^(system|waves|flare):/.test(k));
    twin.textContent = button.textContent; twin.title = button.title; twin.disabled = button.disabled; };
  if (!seeds.size) {
    mirror();
    button.disabled = true; button.textContent = 'Select all';
    button.title = 'Select every piece with the same mesh as the one selected, or every effect of the same particle system, every sound of the same wave, every lens flare of the same template (a light, a cover block, a hidden or streamed piece has none to match)';
    return;
  }
  const found = kindMatches(seeds), picked = new Set(gizmo.picks().ids);
  const what = seeds.size === 1 ? [...seeds.values()][0] : `of these ${seeds.size} kinds`;
  button.textContent = `Select all ${what}${found.box ? ' in box' : ''} (${found.actors})`;
  button.disabled = !found.roots.length || (found.roots.every(r => picked.has(r.userData.source.id)) && found.roots.length === picked.size);
  button.title = found.effects && found.effects === found.roots.length
    ? `Select every drawn effect of the same particle system, every sound of the same wave and every lens flare of the same template ${found.box ? 'inside the box' : 'in the map'}: ${kindCount(found)} (${[...seeds.values()].join(', ')}). Shift+click adds them to the selection.`
    : `Select every drawn piece ${seeds.size === 1 ? 'with this mesh' : 'with one of these meshes'} ${found.box ? 'whose middle is inside the box' : 'in the map'}: `
    + `${plural(found.actors, 'piece')} (${[...seeds.keys()].join(', ')}). Shift+click adds them to the selection. Hidden, deleted and streamed pieces `
    + 'are left out. The Flags group then sets them all; moving, copying and deleting still take each one\'s linked pieces with it.';
  mirror();
}
function selectKind(add = false) {
  const seeds = kindSeeds();
  if (!seeds.size) return;
  const found = kindMatches(seeds), was = gizmo.picks();
  if (!found.roots.length) { flashHint('Nothing drawn is of that kind'); return; }
  const ids = found.roots.map(r => r.userData.source.id);
  const next = add ? [...new Set([...was.ids.filter(id => allRoots.get(id)), ...ids])] : ids;
  if (found.box) stopPickBox();
  gizmo.setSelection(next, next.includes(was.active) ? was.active : next[0]);
  select(gizmo.active, false, true);
  flashHint(`${kindCount(found)} of ${seeds.size === 1 ? [...seeds.values()][0] : `${seeds.size} kinds`} selected${found.box ? ' in the box' : ''}`);
}
// A cover block's or invisible floor's panel: what it is, its size, height and cover (coverPanel), its actor and place.
function showCover(root) {
  const obj = root.userData.source, details = $('details'), c = obj.cover, floor = isFloor(c);
  text(details, 'h2', floor ? 'Invisible floor' : isBlocker(c) ? 'Blocker' : 'Cover block');
  text(details, 'div', floor ? `Invisible in the game · a floor to stand on · ${sizeWords(c.size)}`
    : `Invisible in the game · ${isBlocker(c) ? 'blocks walking, no cover' : coverWords(c)} · ${sizeWords(c.size)}, top ${lengthWords(c.heights[1])}`, 'sub');
  const chips = text(details, 'div', '', 'chips');
  chips.append(groupChip);
  const others = gizmo.selection().filter(r => r !== root);
  if (others.length) text(chips, 'span', `Moves with ${selectionWords(others, 'other ')}`, 'chip');
  text(chips, 'span', floor ? 'Added invisible floor' : isBlocker(c) ? 'Added blocker' : 'Added cover block', 'chip').title = floor
    ? 'The editor\'s own piece: a hidden plate units can stand on (EXP-32). The Build makes it on any install'
    : isBlocker(c) ? 'The editor\'s own piece: a hidden piece that blocks movement and gives no cover. The Build makes it on any '
      + 'install, plain Enemy Within included'
    : 'The editor\'s own piece, as LWR\'s patches add cover: a hidden piece that blocks movement and gives cover. The Build makes '
      + 'it on any install, plain Enemy Within included';
  gridChip = ladderChip = null;
  coverPanel(root);
  $('editCopy').disabled = !copyable().length;
  const dl = $('sourceFields');
  dl.replaceChildren();
  field(dl, 'Actor', short(obj.actor));
  field(dl, 'Class', `${obj.actorClass} (hidden)`);
  field(dl, 'Map location', placedPose(obj, root.matrix).location.map(v => v.toFixed(2)).join(', ')).title = 'Its corner, on the floor';
  $('copyPaths').onclick = () => copyText($('copyPaths'), `Actor: ${obj.actor}`);
  editChanged();
}
// The ladder's ends where the selected ladder stands now (ladders.js against the export's original floor tiles and the
// floor the project's own flat pieces are expected to give, as the compiler counts it), or null. `newFloor` says an
// end has floor only by a piece of the project.
let floorSet = null, ladderChip = null, gridChip = null;
function ladderNow(root) {
  const o = root?.userData.source;
  if (!o || o.actorClass !== 'XComLadder' || isStream(o) || !data.tileGrid || !data.tactical?.floorTiles) return null;
  floorSet ??= new Set(data.tactical.floorTiles.map(f => f.tile.join(',')));
  const boxes = [];
  for (const r of roots.values()) {
    const s = r.userData.source;
    // a cover block is no floor, bar the invisible floor, which is made to carry one (EXP-32)
    if (r.userData.deleted || isStream(s) || s.actorClass === 'XComLadder' || (s.cover && s.cover.type !== 'floor') || !(s.added || r.userData.edit)) continue;
    boxes.push(boxOf(r));
  }
  const added = addedFloors(boxes, data.tileGrid.origin, data.tileGrid.dimensions);
  const pose = placedPose(o, root.matrix);
  const ends = ladderEnds(pose.location, pose.rotation, data.meshes[o.mesh].bounds[5], tileCorner(), new Set([...floorSet, ...added]));
  ends.newFloor = ends.climbs && [ends.footTile, ends.linkedTop].some(t => !floorSet.has(t.join(',')));
  return ends;
}
const LADDER_NOTE = 'The game makes a ladder\'s climb between floors: its foot tile, and its top tile or the one below '
  + 'it, must have floor (the squares: green has floor, red has none). The map\'s own floor counts, and so does a flat '
  + 'piece this project adds with standing room over it (a deck, a slab, an invisible floor). A ladder with a red '
  + 'end is built all the same, with a warning: the game is not expected to make its climb';
function refreshLadder(root) {
  const ends = ladderNow(root);
  ladderMarks.visible = Boolean(ends) && root.visible;
  if (ladderChip) {
    ladderChip.hidden = !ends;
    if (ends) {
      ladderChip.textContent = ends.newFloor ? 'Climbs, by a floor this project adds' : ends.climbs ? 'Climbs'
        : `Won't climb: no floor at its ${ends.why.join(' or ')}`;
      ladderChip.classList.toggle('warn', !ends.climbs);
    }
  }
  if (!ends) return;
  const [ox, oy, oz] = data.tileGrid.origin;
  const tiles = [[ends.footTile, ends.footFloor], [ends.linkedTop ?? ends.topTile, Boolean(ends.linkedTop)]];
  tiles.forEach(([tile, ok], k) => {
    const mark = ladderMarks.children[k];
    mark.position.set(ox + (tile[0] + 0.5) * 96, oz + tile[2] * 64 + 3, oy + (tile[1] + 0.5) * 96);
    mark.material.color.set(ok ? 0x5ad17a : 0xe0605a);
  });
}
// A ladder, door, car, van or fracturing piece: whether it stands on the tile grid of its original (poserule.js
// gridMove, as the compiler checks it), or null for another piece. Off the grid it builds, with a warning.
function gridNow(root) {
  const o = root?.userData.source, from = o && !root.userData.light ? recipeOf(o) : null, origin = gridOrigin();
  if (!from || !origin) return null;
  const pose = actorPose(o, root.matrix);
  return gridMove(from.location, from.rotation, pose.location, pose.rotation, origin);
}
const OFF_GRID_NOTE = 'Ladders, doors, cars, vans and fracturing pieces (walls, storey floors) map what the game saves '
  + 'for their tiles exactly only moved by whole tiles (96 across) and storeys (64 up) and turned by quarter turns about '
  + 'the vertical from where the original stands. This one is off that grid: it builds where it stands, with a warning '
  + 'in the Build report. Tile snap (96 on the snap button) keeps such a piece on the grid';
function refreshGrid(root) {
  if (!gridChip) return;
  const move = isStream(root?.userData.source) ? null : gridNow(root);
  gridChip.hidden = !move || (move.valid && !gizmo.recipe);
  if (gridChip.hidden) return;
  gridChip.textContent = move.valid ? 'Recipe snap' : 'Off the grid';
  gridChip.classList.toggle('warn', !move.valid);
  gridChip.title = move.valid ? `${RECIPE_NOTE}.` : `${OFF_GRID_NOTE}. It misses ${move.why.join(', ')}.`;
}
function refreshHighlight(root) {
  // The box covers everything that moves with the selection.
  highlight.box.makeEmpty();
  for (const r of gizmo.selection().length ? gizmo.selection() : [root]) if (r.visible && !r.userData.light && !r.userData.volume) highlight.box.expandByObject(r);
  highlight.visible = root.visible && !root.userData.light;
  // Interior cuts the box to its area, but for a piece it draws whole only by the height
  if($('scenery').value==='interior') {
    const focus = focusBounds(data);
    if (root.userData.interiorWhole) { highlight.box.min.y = Math.max(highlight.box.min.y, focus.min.y); highlight.box.max.y = Math.min(highlight.box.max.y, focus.max.y); }
    else highlight.box.intersect(focus);
  }
  highlight.box.max.y=Math.min(highlight.box.max.y,root.userData.cutHeight ?? Infinity);
  highlight.visible &&= !highlight.box.isEmpty();
}
const poseInputs = ['posX','posY','posZ','rotP','rotY','rotR'].map($);
// Unsaved changes by kind. A deleted original counts as deleted only; an added piece as added only. A grid of the
// project's size (stage) and the project's own landing zones count once each.
function changes() {
  let moved = 0, added = 0, deleted = 0, lights = 0;
  const flagged = new Set();
  for (const root of roots.values()) {
    if (root.userData.source.added) added++;
    else if (root.userData.deleted) deleted++;
    else if (root.userData.edit) moved++;
    if (!root.userData.source.added && !root.userData.deleted && root.userData.flags) flagged.add(sourceKey(root.userData.source));
  }
  for (const root of lightRoots.values()) if (!isStream(root.userData.source) && root.userData.source.role !== 'area' && lightEdited(root)) lights++;
  let effects = 0;
  for (const root of effectRoots.values()) if (effectEdited(root)) effects++;
  const grid = stage ? 1 : 0, zones = landingZones ? 1 : 0;
  // the buildings the project saves: its own, and the map's it changed or deleted
  const built = data ? savedBuildings().length : 0;
  // a mission's objects moved in their streams (mission types plan, Part E), and the base spawn points edited (SP6)
  const spawns = [...missionMoves.values()].filter(m => m.stream === null || m.stream === 'copy').length, missions = missionMoves.size - spawns;
  return { moved, added, deleted, lights, effects, grid, zones, buildings: built, missions, spawns, flags: flagged.size,
           total: moved + added + deleted + lights + effects + areaBindings.size + grid + zones + built + missions + spawns + flagged.size };
}
// After any trial edit, undo or selection: the highlight, the pose fields, the tool states and the edit status.
// Undo, redo and the "not saved" chip appear only once something has changed.
// One edit event builds the document's state once (plan "faster editor", P2): while editChanged runs, editState,
// builderDocument and builderKey give what they worked out first, where each was built again by every reader (the
// save state, the title, the size line, the recovery timer: six times an event in the builder).
let eventMemo = null;
function editChanged() {
  touchShadows();
  if (eventMemo) return editChangedNow();
  eventMemo = {};
  try { return editChangedNow(); } finally { eventMemo = null; }
}
function editChangedNow() {
  effectsDirty = true;     // (the Effects view's markers follow the pieces that carry them)
  // A command (undo of a paste, a delete) can change the selection under us: follow the gizmo.
  if (data && selected !== gizmo.active) { select(gizmo.active, false, true); return; }
  // the Buildings view: the project's buildings follow the boxes; a box is never turned
  if (data) {
    if (volumesOn && gizmo.mode === 'rotate') { gizmo.setMode('translate'); return; }
    syncVolumes(); refreshVolumes(); volumePanel();
  }
  // pieces moved, deleted or brought back: the cutaway follows once a drag ends
  if (data && !gizmo.controls.dragging && editedKey() !== cutKey) { cutaway(); if (selected) return; }   // (cutaway's select ran this)
  if (selected && roots.get(selected)) { refreshHighlight(roots.get(selected)); refreshLadder(roots.get(selected)); refreshGrid(roots.get(selected)); }
  if (selected && isFloor(roots.get(selected)?.userData.source.cover) && !gizmo.controls.dragging) floorNote(roots.get(selected));
  const pose = gizmo.pose(), count = changes();
  if (pose) [...pose.location, ...pose.rotation].forEach((v, i) => {
    if (document.activeElement !== poseInputs[i]) poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2);
  });
  // while a handle is held, only what is seen to move is kept up: the pieces, the highlight, the pose fields, the
  // grid chip. The status, the save state, the panels, the size line and the warnings wait for the drag's end, which
  // runs this again in full (the gizmo's dragging-changed).
  if (gizmo.controls.dragging) { if (lightsShown) lightsChanged(); return; }
  // a streamed piece, or a view-only light, is shown, not edited: its place, read only
  const pickedRoot = allRoots.get(selected), pickedSource = pickedRoot?.userData.source;
  const fixedPick = isStream(pickedSource) || Boolean(pickedRoot?.userData.light && lightViewOnly(pickedSource));
  if (fixedPick && !pose) {
    const at = pickedRoot.userData.light ? lightPose(pickedRoot) : pickedSource;
    [...at.location, ...at.rotation.map(r => r * 360 / 65536)].forEach((v, i) => { poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2); });
  }
  poseInputs.forEach((input, i) => { input.disabled = fixedPick || (i >= 3 && pickedRoot?.userData.light && pickedSource.kind === 'point'); });
  $('editDelete').disabled = fixedPick;
  // (in the builder every piece is the prefab's own, so only whether it is saved is said)
  $('editCount').hidden = builderMode ? !count.total && !builder.doc?.revision : !count.total;
  $('editCount').textContent = builderMode ? saveState() : [count.moved && `${count.moved} moved`, count.added && `${count.added} added`,
    count.deleted && `${count.deleted} deleted`, count.lights && plural(count.lights, 'light edit'),
    count.effects && plural(count.effects, 'effect or sound edit'),
    count.grid && `grid ${data.tileGrid.dimensions[0]} × ${data.tileGrid.dimensions[1]}${cleared ? ` × ${data.tileGrid.dimensions[2]}` : ''}`,
    count.zones && 'landing zones changed', count.buildings && plural(count.buildings, 'building'),
    count.missions && `${plural(count.missions, 'mission object')} moved`, count.spawns && plural(count.spawns, 'spawn point edit'), count.flags && `${plural(count.flags, 'piece')} with flags changed`,
    saveState()].filter(Boolean).join(' · ');
  $('editCount').classList.toggle('warn', saveState() !== 'saved');
  $('editUndo').hidden = $('editRedo').hidden = !(count.total || gizmo.canUndo() || gizmo.canRedo());
  $('editUndo').disabled = !gizmo.canUndo(); $('editRedo').disabled = !gizmo.canRedo();
  $('editReset').disabled = !gizmo.selection().some(r => r.userData.edit || (r.userData.light && valuesEdited(r)) || (r.userData.effect && r.userData.values));
  $('editResetAll').hidden = builderMode || (!count.total && !groups.size && !cleared);
  flagsPanel(); kindButton();
  // (a building's box is in no group and is not aligned)
  if (volumeRoots.has(selected)) { $('groupBox').hidden = true; $('alignBox').hidden = true; targetHelper.visible = false; }
  else { groupPanel(); alignPanel(); }
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
  projectChanged();
  lightsChanged();
  warnLights();
}
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
// Many pieces made (buildRoot each), a few at a time, giving way by time and counting for the busy mark.
async function buildRoots(objs, step = null) {
  const built = [], rest = breather();
  for (let k = 0; k < objs.length; k += BUILD_CHUNK) {
    built.push(...await Promise.all(objs.slice(k, k + BUILD_CHUNK).map(buildRoot)));
    step?.(built.length, objs.length);
    await rest();
  }
  return built;
}
// A short notice in the same place (copied, deleted, nothing to paste); it goes after a moment.
let hintTimer;
function flashHint(message) {
  if (gizmo.controls.dragging) return;
  const hint = $('dragHint');
  hint.replaceChildren(message); hint.hidden = false;
  clearTimeout(hintTimer);
  hintTimer = setTimeout(restingHint, 2500);
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

// Adding and deleting pieces. Like moves, these are trial edits: drawn only, not saved or built.
// A copy is a new piece built from its source's mesh and materials, with its own id, actor name and pivot.
let clipboard = null, copySerial = 0;
const newId = () => `added:${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
let snapMode = 'off';   // 'off', 'fine' (24 units, 15 degrees) or 'tile' (whole tiles, 90 degrees)
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
}// The selection's pieces that can be copied or deleted: hidden helpers shown for inspection are left out.
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
           entries: list.map(r => ({ source: r.userData.source, matrix: r.matrix.clone(),
                                     ...(r.userData.light ? { values: { ...r.userData.values } } : {}),
                                     ...(r.userData.effect && r.userData.values ? { values: structuredClone(r.userData.values) } : {}),
                                     ...(r.userData.flags ? { flags: { ...r.userData.flags } } : {}) })),
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
function sceneChanged() { touchShadows(); liveCache = null; effectsDirty = true; cutaway(); catalogue(); refreshGroundGrid(false); }
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
// A fracturing wall the Build makes from numbers (custom geometry plan, section 0): drawn from its own mesh, which the
// server builds from the numbers as the Build does (generated.py), on its template's materials by slot (the made mesh's
// sections are slots 0 to 5 in order). Its numbers are its tile edges; its solid stops endInset short of each
// (tools/bake/frac_wall.py RECIPE). Numbers the server can't draw (generated.py's limits) leave the template's mesh.
const FRAC_WALL = { endInset: 8, halfY: 12, bottom: -16, top: 384, slots: 6, minLength: 40, maxLength: 3072 };
// A made wall's mesh bounds (the mesh form's [centre, half sizes, radius]): its solid, its section's height (one storey's
// top 192: frac_wall.shaped) and thickness.
function madeBounds(wall) {
  const top = wall.storeys === 1 ? 192 : FRAC_WALL.top;
  const a = wall.x0 + FRAC_WALL.endInset, b = wall.x1 - FRAC_WALL.endInset, hx = (b - a) / 2, hz = (top - FRAC_WALL.bottom) / 2;
  return [(a + b) / 2, 0, FRAC_WALL.bottom + hz, hx, FRAC_WALL.halfY, hz, Math.hypot(hx, FRAC_WALL.halfY, hz)];
}
// A made wall's numbers in the one spelling its mesh's key and request use (generated.py wall_numbers: two storeys left out).
const madeWallNumbers = w => ({ x0: w.x0, x1: w.x1, openings: (w.openings ?? []).map(o => ({ x0: o.x0, x1: o.x1, z0: o.z0, z1: o.z1 })),
                                seed: w.seed ?? 1, ...(w.storeys === 1 ? { storeys: 1 } : {}) });
function madeShape(template, generated) {
  const w = generated?.kind === 'fracWall' ? generated.wall : null;
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!w || !finite(w.x0) || !finite(w.x1) || w.x1 - w.x0 < FRAC_WALL.minLength || w.x1 - w.x0 > FRAC_WALL.maxLength
    || !Number.isInteger(w.seed ?? 1) || !(w.openings ?? []).every(o => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o?.[k]))
      && w.x0 <= o.x0 && o.x0 < o.x1 && o.x1 <= w.x1 && o.z0 < o.z1) || ![undefined, 1, 2].includes(w.storeys)) return {};
  const wall = madeWallNumbers(w);
  const key = `made:fracwall:${JSON.stringify(wall)}`;
  if (!data.meshes[key]) {
    // (`look`: the template's mesh, which Select all of a kind counts it as)
    data.meshes[key] = { name: `${data.meshes[template.mesh]?.name ?? 'a wall'}, made from numbers`, kind: 'static', made: true,
      look: data.meshes[template.mesh]?.name ?? null,
      url: `/generated/fracwall.glb?${new URLSearchParams({ wall: JSON.stringify(wall) })}`,
      sections: Array.from({ length: FRAC_WALL.slots }, (_, slot) => ({ slot, count: 1 })), bounds: madeBounds(wall) };
  }
  const slots = (data.meshes[template.mesh]?.sections ?? []).filter(s => s.count).map(s => s.slot);
  const bySlot = new Map(slots.map((slot, i) => [slot, template.materials[i]]));
  return { mesh: key, materials: Array.from({ length: FRAC_WALL.slots }, (_, slot) => bySlot.get(slot) ?? template.materials[0]) };
}
// An added piece: a copy of one source component, as its own actor (output name, entity id, prefab and partner).
function addedObject(template, placed, { actor, entity, prefab, partner, location, rotation, tinted, flags = null, generated = null }) {
  return { ...template, ...madeShape(template, generated), id: newId(), actor, layer: 'added', hidden: false, environment: false, hiddenBy: null, provenance: null,
    // its piece flags as made (piece flags plan): a paste's are its original's request, a project's its record's; the
    // template's settings (pieceFlags) stay its baseline
    initialFlags: flags ? { ...flags } : null,
    // `floors` stays its original's listings (its template's, a copy's included) and `cutout` its original's: the
    // copy's own listings follow where it stands (listingsNow), as the Build lists it.
    floors: originalOf(template)?.floors ?? template.floors ?? [], prefab, partner, matrix: placed.toArray(), location, rotation,
    // `generated`: a fracturing wall the Build makes from numbers on this piece's materials (custom geometry plan,
    // section 0), kept as the project has it; the view draws the template's own mesh
    added: { from: fromOf(template), entity, tinted, ...(generated ? { generated } : {}),
             ...(template.cover ? { template: { kind: COVER_KIND, version: coverVersion(template.added?.template?.version, template.cover.type) } } : {}) } };
}
// Cover blocks (cover.js): invisible pieces that give cover, made by the Build from a recipe (compiler.COVER_RECIPES,
// served in families.json). A block is a piece like any other here, drawn from a box the page makes itself (its
// synthetic mesh and material in data.meshes and data.materials, and in the caches as if loaded), at its corner.
const coverRecipe = () => families?.coverRecipes ?? null;
// The recipe version a block is saved with: its own while that version makes its type (a blocker needs version 2), else
// the latest. A later version only adds types, so a block built by either is the same.
const coverVersion = (version, type) => {
  const r = coverRecipe();
  return version != null && r?.types?.[version]?.includes(type) ? version : r?.latest;
};
// A record this page can make (cover.js, in units), as compiler.cover_shape reads one: up to the recipe's tiles across,
// and a block's heights at most the tallest whole-tile block's apart.
const validCoverValues = c => {
  const r = coverRecipe();
  if (!r || !c || !Object.hasOwn(r.heights, c.type) || !Array.isArray(c.size) || c.size.length !== 2) return false;
  const across = r.maxTiles * 96, flat = r.flat?.includes(c.type);
  if (!c.size.every(v => Number.isFinite(v) && v > 0 && v <= across)) return false;
  if (flat) return Object.keys(c).length === 2;
  const span = r.heights.high[1] - r.heights.high[0] + r.heightStep * (r.maxHeight - 1), h = c.heights;
  return Object.keys(c).length === 3 && Array.isArray(h) && h.length === 2 && h.every(v => Number.isFinite(v) && Math.abs(v) <= across)
    && h[1] - h[0] > 0 && h[1] - h[0] <= span;
};
function ensureCover(c) {
  const recipe = coverRecipe(), mesh = coverMeshId(c), material = `${COVER_MATERIAL}:${c.type}`;
  data.meshes[mesh] ??= coverMeshRecord(c, recipe);
  data.materials[material] ??= { name: isFloor(c) ? 'Invisible floor (hidden in the game)'
    : isBlocker(c) ? 'Blocker, no cover (hidden in the game)' : `Cover block, ${c.type} cover (hidden in the game)` };
  track(geometryCache, mesh, () => Promise.resolve(coverScene(c, recipe)));
  track(materialCache, `${material}:null`, () => Promise.resolve(coverMaterial(c.type)));
  return { mesh, materials: [material] };
}
// A cover block's template, as a placed piece of the map would be: its corner at `location`.
function coverSource(c, location, rotation) {
  const { mesh, materials } = ensureCover(c);
  const pkg = data.source.file.split(/[\\/]/).at(-1), actor = `${PL}${isFloor(c) ? 'InvisibleFloor' : 'CoverBlock'}`;
  return { id: `cover-template:${mesh}`, actor, component: `${actor}.StaticMeshComponent_0`, sourcePackage: pkg, layer: COVER_KIND,
           actorClass: 'XComLevelActor', componentClass: 'StaticMeshComponent', archetype: 'None', mesh, materials,
           location: [...location], rotation: [...rotation], scale: [1, 1, 1], matrix: actorMatrix(location, rotation).toArray(),
           tint: [1, 1, 1, 1], hidden: false, environment: false, hiddenBy: null, floors: [], prefab: null, partner: null,
           referencedBy: [], breaks: [], destruction: null, cutout: false, areaLights: [], editorLayers: [], provenance: null,
           cover: { ...c } };
}
// The Add panel's Invisible kind: a Cover block (coverStart: one tile of high cover) and an Invisible floor (floorStart:
// one tile), sized with their handles once placed and their cover set in the piece panel (the user's call: no row per
// size). The corner stands on a tile corner, so tile snap keeps it on the grid.
const INVISIBLE_KIND = 'Invisible';
function coverEntries() {
  const recipe = coverRecipe();
  if (!recipe || !data || data.preview) return [];
  const [ox, oy] = gridOrigin() ?? [0, 0], z = data.tileGrid?.origin?.[2] ?? 0;
  const entry = (c, key, id, name, words, title) => {
    const source = coverSource(c, [ox, oy, z], [0, 0, 0]);
    const [lo, hi] = coverBox(c, recipe);
    const box = new THREE.Box3(new THREE.Vector3(lo[0], lo[2], lo[1]), new THREE.Vector3(hi[0], hi[2], hi[1]));
    const size = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]];
    return { key, id, name, mesh: name, pkg: 'invisible in the game', kind: INVISIBLE_KIND, role: 'interior', sources: [source],
             pivotIndex: 0, count: 0, materials: [], milestone: 1, frame: actorMatrix(source.location, source.rotation).invert(),
             box, size, extent: Math.hypot(...size), cover: c, text: words, title };
  };
  const block = coverStart(recipe), floor = floorStart();
  return [
    entry(block, 'cover', 'cover-block', 'Cover block', 'cover block invisible hidden high low cover tall blocker walking none wall',
          'An invisible block, as LWR\'s patches place them: hidden in the game, it blocks movement and gives units beside it high '
          + 'or low cover (units see over low cover), or with Cover set to None no cover at all (units see past it). Placed by its '
          + 'first tile under the cursor as one tile of high cover; drag its handles to size it (with the snap setting\'s steps, '
          + `up to ${recipe.maxTiles} tiles across) and set its cover in the piece panel. The Build makes it on any install`),
    entry(floor, 'floor-plate', 'invisible-floor', 'Invisible floor', 'invisible floor hidden plate walkway walkable',
          'An invisible floor units can stand on: a thin plate hidden in the game, its top at the height it is placed at '
          + '(EXP-32). Placed by its first tile under the cursor; drag its handles to size it, its height with the Z arrow. '
          + 'The Build makes it on any install')];
}
// A saved cover block's template at its pose, or null for one this page can't make (an unknown recipe version or size).
function coverOf(entity) {
  const recipe = coverRecipe(), c = normalCover(entity.cover, recipe);
  if (!recipe?.versions.includes(entity.template.version) || !validCoverValues(c)) return null;
  // as a copy of the Add panel's template (fromOf: the same package, level and actor), made by the saved version
  const source = coverSource(c, entity.location, entity.rotation);
  return { ...source, added: { from: { package: source.sourcePackage, level: COVER_KIND, actor: source.actor },
                               template: { ...entity.template } } };
}
// Invisible floors and the ground (EXP-32): the game looks for a tile's floor along one line straight down through the
// tile's centre and takes the first standable surface it meets, so a floor plate is the tile's floor (and a flat one,
// on a ramp) only where its top is over the ground at the tile's centre. That line meets a piece's collision, which
// for most pieces is a set of convex hulls standing over the drawn surface wherever it dips (up to 5 units on the
// farm's ramp, where a floor 1 unit over the drawn ramp wasn't found: run 2), so the ground here is the collision's.
// FLOOR_CLEARANCE is how far over it a floor from the Add panel, or Fit to ground, puts it (1.1 over the hulls was
// found in run 2).
const FLOOR_CLEARANCE = 1;
const groundRay = new THREE.Raycaster();
// The game's collision for line checks by mesh (collision.json, tools/viewer/collision.py), asked for once, when a
// floor first needs the ground: mesh id -> { simple: false } (its triangles: the drawn mesh stands for them) or
// { simple: true, solids } (its convex hulls and boxes, each a mesh in the piece's mesh frame with its centre; none:
// the game's line passes through it). Until it comes, and for a mesh it doesn't cover (streamed patches'), the drawn
// mesh stands in.
let lineCollision = null, lineCollisionAsked = false, lineCollisionFailed = false;
const collisionMaterial = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
function collisionMesh(c) {
  if (!c) return undefined;
  if (!c.simple) return { simple: false };
  const solids = (c.elements ?? []).map(t => {
    const at = new Float32Array(t.length);
    for (let i = 0; i < t.length; i += 3) { at[i] = t[i]; at[i + 1] = t[i + 2]; at[i + 2] = t[i + 1]; }   // game axes to the page's
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(at, 3));
    geometry.computeBoundingSphere(); geometry.computeBoundingBox();
    const mesh = new THREE.Mesh(geometry, collisionMaterial);
    mesh.matrixAutoUpdate = false;
    return { mesh, centre: geometry.boundingBox.getCenter(new THREE.Vector3()) };
  });
  return { simple: true, solids };
}
// A hit's face normal in the world, turned to point out of the solid (whatever the triangle's winding).
const groundNormal = new THREE.Vector3(), groundCentre = new THREE.Vector3(), groundUp = new THREE.Raycaster();
function outwardY(hit, solid) {
  groundNormal.copy(hit.face.normal).transformDirection(solid.mesh.matrixWorld);
  groundCentre.copy(solid.centre).applyMatrix4(solid.mesh.matrixWorld);
  return groundNormal.dot(groundCentre.sub(hit.point).negate()) < 0 ? -groundNormal.y : groundNormal.y;
}
// Where the floor line meets one solid, as the game's floor trace takes it: a top it enters through looking up more
// than 0.7 (a steeper face is no floor, and the line goes on through); a line that starts inside the solid leaves it
// through a face looking down first, and the solid's top over it is the ground there (it stands over the line's
// start: the floor is inside it). Null where it gives none.
function solidGround(solid, root) {
  solid.mesh.matrixWorld.copy(root.matrixWorld);
  const first = groundRay.intersectObject(solid.mesh, false)[0];
  if (!first) return null;
  const up = outwardY(first, solid);
  if (up > 0.7) return first.point.y;
  if (up >= 0) return null;
  groundUp.set(new THREE.Vector3(first.point.x, first.point.y + 1e5, first.point.z), new THREE.Vector3(0, -1, 0));
  const top = groundUp.intersectObject(solid.mesh, false)[0];
  return top && outwardY(top, solid) > 0.7 ? top.point.y : null;
}
function askLineCollision() {
  if (lineCollisionAsked) return;
  lineCollisionAsked = true;
  if (builderMode) { lineCollision ??= new Map(); return; }
  const map = activeMapId;
  fetch(`/maps/${encodeURIComponent(map)}/collision.json`).then(r => (r.ok ? r.json() : null)).catch(() => null).then(reply => {
    if (map !== activeMapId) return;
    lineCollision ??= new Map();
    lineCollisionFailed = !reply?.meshes;
    for (const [id, c] of Object.entries(reply?.meshes ?? {})) lineCollision.set(id, collisionMesh(c));
    const root = selected && roots.get(selected);
    if (root && isFloor(root.userData.source.cover)) floorNote(root);
  });
}
// Each piece's box (drawn mesh, a little wider, as its hulls may be), kept while it doesn't move.
const groundBoxes = new WeakMap();
function groundBox(root) {
  let kept = groundBoxes.get(root);
  if (!kept || !kept.at.equals(root.matrixWorld)) {
    kept = { box: new THREE.Box3().setFromObject(root).expandByScalar(8), at: root.matrixWorld.clone() };
    groundBoxes.set(root, kept);
  }
  return kept.box;
}
/** The height (game z) of the map's surface straight below (x, y) from `fromZ`: the highest ground the line meets on a
 *  visible piece, by its collision where that has come (solidGround: a solid the line starts in gives its top), by the
 *  drawn mesh until then; the editor's own hidden pieces skipped; null where there is none. */
function groundAt(x, y, fromZ) {
  askLineCollision();
  groundRay.set(new THREE.Vector3(x, fromZ, y), new THREE.Vector3(0, -1, 0));
  let top = null;
  const higher = z => { if (z != null && (top == null || z > top)) top = z; };
  for (const root of roots.values()) {
    const source = root.userData.source;
    if (!root.visible || source.cover || !root.userData.parts?.length || !groundRay.ray.intersectsBox(groundBox(root))) continue;
    const c = lineCollision?.get(source.mesh);
    if (c?.simple) for (const solid of c.solids) higher(solidGround(solid, root));
    else higher(groundRay.intersectObjects(root.userData.parts, false)[0]?.point.y);
  }
  return top;
}
// A cover piece's footprint against the map's tiles, as the game's tile rebuild reads it (research/native/cover-build.md,
// sections 2 to 5; cover-block-handles-plan.md, section 1; EXP-59 to play). `at(u, v)` is a point of the piece's own
// frame (its corner's floor, game axes) in the world, `local(x, y)` a world point across in its frame.
function coverFrame(root) {
  root.updateMatrixWorld(true);
  const toLocal = root.matrixWorld.clone().invert();
  const at = (u, v, w = 0) => { const p = new THREE.Vector3(u, w, v).applyMatrix4(root.matrixWorld); return [p.x, p.z, p.y]; };
  const local = (x, y, z) => { const p = new THREE.Vector3(x, z, y).applyMatrix4(toLocal); return [p.x, p.z, p.y]; };
  return { at, local };
}
// The game's numbers (cover-build.md): a tile is occupied when its box, 48 each way across and 28 to 92 over its level's
// bottom, meets a piece at least 4 units through every way (or 384 across); fully occupied, with no floor to stand on,
// when the middle 40 x 40 from 60 to 92 meets it too. Crossing to a neighbour is blocked by a sweep from 64 over the
// floor to the neighbour's centre; cover by a sweep from the middle, 44 to 60 over the floor, meeting the piece within 88
// of the middle, looked for only toward an occupied neighbour or from a partly occupied tile.
// Sight is walked between the tiles one level above the floor (eye height: line-of-sight.md, section 2.3), whose own
// blocking sweep runs from their centre, EYE_SWEEP over the floor level's bottom, and stops only at a piece that
// blocks sight (a high block; low cover and blockers let units see past).
const TILE_BOX = [48, 28, 92], TILE_MIDDLE = [20, 60, 92], WALL_SWEEP = 64, COVER_SWEEP = [44, 60], COVER_REACH = 88;
const EYE_SWEEP = 96;
/** A cover piece against the tiles round it: { tiles: [{ centre, occupied, full, carried }] (the tiles it reaches),
 *  thin, walls (the lines between neighbouring tiles' centres it blocks), looked (the ways tiles look for cover toward
 *  or from it), covered (the tiles that get cover from it), seen (the lines between tiles' centres it crosses at eye
 *  height, eye over its floor),
 *  sweep (false when it misses the height cover is looked for at), top (its floor's height) }. */
function coverTiles(root) {
  const c = root.userData.source.cover, [ox, oy] = gridOrigin() ?? [0, 0], oz = data?.tileGrid?.origin?.[2] ?? 0;
  const { at, local } = coverFrame(root);
  const corners = [[0, 0], [c.size[0], 0], [c.size[0], c.size[1]], [0, c.size[1]]].map(([u, v]) => at(u, v));
  const xs = corners.map(p => p[0]), ys = corners.map(p => p[1]), z = corners[0][2];
  const [h0, h1] = c.heights ?? coverBox(c, coverRecipe()).map(p => p[2]);
  const inside = (x, y) => { const [u, v] = local(x, y, z); return u >= -1e-6 && v >= -1e-6 && u <= c.size[0] + 1e-6 && v <= c.size[1] + 1e-6; };
  // the footprint's own axes in the world, for an exact test against a tile's square (separating axes)
  const axes = [corners[1], corners[3]].map((q, k) => [(q[0] - corners[0][0]) / c.size[k], (q[1] - corners[0][1]) / c.size[k]]);
  const meets = (cx, cy, half) => {
    if (Math.max(...xs) <= cx - half + 1e-6 || Math.min(...xs) >= cx + half - 1e-6
        || Math.max(...ys) <= cy - half + 1e-6 || Math.min(...ys) >= cy + half - 1e-6) return false;
    return axes.every(([dx, dy], k) => {
      const m = (cx - corners[0][0]) * dx + (cy - corners[0][1]) * dy, r = half * (Math.abs(dx) + Math.abs(dy));
      return m + r > 1e-6 && m - r < c.size[k] - 1e-6;
    });
  };
  // does the footprint cross the line from p to q (across)? (clipped to it in its own frame)
  const crosses = (p, q) => {
    const a = local(p[0], p[1], z), b = local(q[0], q[1], z);
    let t0 = 0, t1 = 1;
    for (let k = 0; k < 2; k++) {
      const d = b[k] - a[k];
      for (const [pk, qk] of [[-d, a[k]], [d, c.size[k] - a[k]]]) {
        if (Math.abs(pk) < 1e-9) { if (qk < 1e-6) return false; continue; }
        if (pk < 0) t0 = Math.max(t0, qk / pk); else t1 = Math.min(t1, qk / pk);
      }
    }
    return t1 - t0 > 1e-6;
  };
  // heights against its floor's level (the level its location stands in)
  const bottom = oz + 64 * Math.floor((z - oz) / 64 + 1e-6), lo = z + h0, hi = z + h1;
  const spans = (a, b) => hi > bottom + a + 1e-6 && lo < bottom + b - 1e-6;
  const thin = Math.min(c.size[0], c.size[1], h1 - h0) < 4 && Math.max(c.size[0], c.size[1]) < 384;
  const tx0 = Math.floor((Math.min(...xs) - ox) / 96) - 1, tx1 = Math.ceil((Math.max(...xs) - ox) / 96);
  const ty0 = Math.floor((Math.min(...ys) - oy) / 96) - 1, ty1 = Math.ceil((Math.max(...ys) - oy) / 96);
  const centre = (tx, ty) => [ox + tx * 96 + 48, oy + ty * 96 + 48];
  const tile = new Map(), key = (tx, ty) => `${tx},${ty}`;
  for (let tx = tx0; tx <= tx1; tx++) {
    for (let ty = ty0; ty <= ty1; ty++) {
      const [cx, cy] = centre(tx, ty);
      if (!meets(cx, cy, 47.5)) continue;
      const occupied = !thin && spans(TILE_BOX[1], TILE_BOX[2]);
      tile.set(key(tx, ty), { centre: [cx, cy], occupied, full: occupied && meets(cx, cy, TILE_MIDDLE[0]) && spans(TILE_MIDDLE[1], TILE_MIDDLE[2]),
                              carried: inside(cx, cy) });
    }
  }
  const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  let walls = 0, looked = 0, seen = 0;
  const covered = new Set(), wallUp = h0 < WALL_SWEEP && h1 > WALL_SWEEP, eyeUp = spans(EYE_SWEEP, EYE_SWEEP);
  const sweep = h1 > COVER_SWEEP[0] && h0 < COVER_SWEEP[1];
  for (let tx = tx0; tx <= tx1; tx++) {
    for (let ty = ty0; ty <= ty1; ty++) {
      const here = tile.get(key(tx, ty)), [cx, cy] = centre(tx, ty);
      for (const [dx, dy] of DIRS) {
        const next = tile.get(key(tx + dx, ty + dy));
        // a wall: counted once, from the tile on its low side, between two tiles a unit can stand in
        if ((dx > 0 || dy > 0) && wallUp && !here?.full && !next?.full && crosses([cx, cy], centre(tx + dx, ty + dy))) walls++;
        if ((dx > 0 || dy > 0) && eyeUp && crosses([cx, cy], centre(tx + dx, ty + dy))) seen++;
        // cover this way: looked for toward an occupied neighbour, or every way from a partly occupied tile
        if (here?.full || !sweep || !(next?.occupied || (here?.occupied && !here.full))) continue;
        looked++;
        if (crosses([cx, cy], [cx + dx * (COVER_REACH + 1), cy + dy * (COVER_REACH + 1)])) covered.add(key(tx, ty));
      }
    }
  }
  return { tiles: [...tile.values()], thin, walls, looked, covered: covered.size, seen, eye: bottom + EYE_SWEEP - z, sweep, top: z };
}
/** An invisible floor's tiles' centres on its top, [x, y, z] game units each: the map's tiles whose centre it covers,
 *  where the game looks for a tile's floor (one line straight down through the centre). */
function floorCentres(root) {
  const { tiles, top } = coverTiles(root);
  return tiles.filter(t => t.carried).map(t => [...t.centre, top]);
}
// What the game will do with a block, in words (coverTiles' model; EXP-59 to play): where units can stand, the tile
// edges it walls off, and the cover it gives.
function coverGameWords(root, g = coverTiles(root)) {
  const c = root.userData.source.cover, [h0, h1] = c.heights;
  const count = (n, one, many) => (n === 1 ? one : many.replace('#', n));
  const occupied = g.tiles.filter(t => t.occupied).length, full = g.tiles.filter(t => t.full).length;
  const stand = g.thin ? 'Under 4 units through: the game counts it as filling no tile, so units can stand all round it.'
    : full ? `Units can't stand in the ${count(full, 'tile', '# tiles')} whose middle it fills.`
    : occupied ? `It fills no tile's middle, so units can stand in the ${count(occupied, 'tile', 'tiles')} it reaches into.`
    : 'It reaches no tile of the map.';
  const walls = g.walls ? `It stops units crossing ${count(g.walls, 'the tile edge', 'the # tile edges')} it stands across, as a wall does.`
    : (occupied && !full) || g.thin ? 'It stands across no line between tile centres 64 over the floor, so units walk past it.' : '';
  const cover = isBlocker(c) ? 'Units beside it get no cover from it.'
    : h1 <= COVER_SWEEP[0] ? `Its top is under ${COVER_SWEEP[0]} over the floor, below where the game looks for cover (${COVER_SWEEP[0]} to ${COVER_SWEEP[1]}): it gives none.`
    : h0 >= COVER_SWEEP[1] ? `Its bottom is over ${COVER_SWEEP[1]} above the floor, above where the game looks for cover (${COVER_SWEEP[0]} to ${COVER_SWEEP[1]}): it gives none.`
    : g.covered ? `Units in ${count(g.covered, 'the tile', 'the # tiles')} beside it get ${c.type} cover from it.`
    : g.looked ? 'It stands off the lines the game looks for cover along, so it gives none.'
    : 'No tile looks for cover toward it, since it fills none: it gives none.';
  return ['Hidden in the game.', stand, walls, cover].filter(Boolean).join(' ');
}
// Its line of sight, in one sentence: a blocker and low cover are seen through or over; a high block stops sight where
// it stands across the line between tiles at eye height (a unit beside it still leans round a short wall's ends).
function coverSightWords(root, g = coverTiles(root)) {
  const c = root.userData.source.cover;
  if (isBlocker(c)) return 'Sight: units see and shoot through it.';
  if (c.type === 'low') return 'Sight: units see and shoot over it, as over any low cover.';
  return g.seen ? 'Sight: it blocks line of sight as a wall does, though a unit beside it can lean round its ends.'
    : `Sight: it doesn't stand across eye height (${Math.round(g.eye)} over its floor), so units see and shoot past it.`;
}
/** How far an invisible floor's top stands over the ground at each of its tiles' centres (null where none is under). */
const floorClearances = root => floorCentres(root).map(([x, y, z]) => { const g = groundAt(x, y, z + 96); return g == null ? null : z - g; });
const units = v => `${Math.round(v * 10) / 10} unit${Math.abs(Math.round(v * 10) / 10) === 1 ? '' : 's'}`;
// The floor section's note: its size, and where its top stands over the ground at its tiles' centres.
function floorNote(root) {
  const c = root.userData.source.cover, carried = floorCentres(root).length, gaps = floorClearances(root).filter(v => v != null);
  const under = gaps.filter(v => v < 0).length, one = carried === 1;
  const [lo, hi] = coverBox(c, coverRecipe());
  let ground = carried ? 'No ground under it.' : 'It covers no tile\'s centre, where the game looks for a floor: it carries no tile.';
  if (under) ground = `Below the ground at the centre of ${one ? 'its tile' : `${under} of its ${carried} tiles`}: the game finds `
    + 'the ground there, not this floor. Fit to ground lifts it.';
  else if (gaps.length) {
    const least = Math.min(...gaps), most = Math.max(...gaps);
    ground = `Its top is ${one || Math.abs(most - least) < 0.05 ? units(least) : `${units(least)} to ${units(most)}`} over the ground at `
      + `${one ? 'its tile\'s centre' : 'its tiles\' centres'}, where the game looks for a floor.`;
  }
  if (gaps.length) ground += !lineCollision ? ' (Reading the ground\'s collision…)'
    : lineCollisionFailed ? ' (Measured from the drawn ground: the game\'s collision couldn\'t be read, and it can stand a few units higher.)'
    : ' (The ground\'s collision, as the game sees it.)';
  $('coverSize').textContent = `${sizeWords(c.size)} across, ${hi[2] - lo[2]} thin; it carries ${carried === 1 ? 'one tile' : `${carried} tiles`} `
    + '(the ones whose centre it covers).';
  $('coverNote').textContent = `Hidden in the game: units can stand on it. ${ground}`;
  $('coverFit').disabled = !gaps.length;
}
// Fit to ground: the selected floor raised or lowered so its top stands FLOOR_CLEARANCE over the ground at the tile
// centre where the ground is highest; one undo step.
function fitFloor() {
  const root = roots.get(selected), pose = gizmo.pose();
  if (!root || !isFloor(root.userData.source.cover) || !pose) return;
  const gaps = floorClearances(root).filter(v => v != null);
  if (!gaps.length) return;
  const shift = FLOOR_CLEARANCE - Math.min(...gaps);
  if (Math.abs(shift) < 0.01) { floorNote(root); return; }
  gizmo.setPose([pose.location[0], pose.location[1], pose.location[2] + shift], null);
}
// The piece panel's cover section: its cover, its size in words (the handles set it) and what the game will do with it.
function coverPanel(root) {
  const c = root.userData.source.cover, focused = document.activeElement, recipe = coverRecipe(), floor = isFloor(c);
  $('coverHead').textContent = floor ? 'Invisible floor' : isBlocker(c) ? 'Blocker' : 'Cover block';
  $('coverHeight').querySelector('option[value="block"]').hidden = !recipe?.heights?.block;
  if (!floor && focused !== $('coverHeight')) $('coverHeight').value = c.type;
  $('coverTypeRow').hidden = floor;
  $('coverFitRow').hidden = !floor;
  if (floor) { $('coverSight').textContent = ''; floorNote(root); return; }
  const [h0, h1] = c.heights, below = h0 < 0 ? `${lengthWords(-h0)} below its floor` : h0 > 0 ? `${lengthWords(h0)} over its floor` : 'its floor';
  $('coverSize').textContent = `${sizeWords(c.size)} across, from ${below} to ${lengthWords(h1)} ${h1 < 0 ? 'below' : 'above'} it.`;
  const g = coverTiles(root);
  $('coverSight').textContent = coverSightWords(root, g);
  $('coverNote').textContent = coverGameWords(root, g);
}
// A record and a render matrix put on a cover piece, its box drawn anew (no undo step: setCover and the handles' drags
// make one).
function applyCover(root, c, matrix = null) {
  const o = root.userData.source, { mesh, materials } = ensureCover(c);
  Object.assign(o, { cover: { ...c }, mesh, materials });
  const base = coverScene(c, coverRecipe()), material = coverMaterial(c.type);
  const old = new Set(root.userData.parts);
  root.clear();
  const parts = [];
  for (const child of base.scene.children) {
    root.add(child);
    if (!child.isMesh) continue;
    Object.assign(child.userData, { baseMaterial: material, objectId: o.id });
    child.material = material; child.castShadow = false; child.receiveShadow = false;
    parts.push(child);
  }
  root.userData.parts = parts;
  pickables.splice(0, pickables.length, ...pickables.filter(p => !old.has(p)), ...parts);
  if (matrix) gizmo.applyMatrices([root], [matrix]);
  root.updateMatrixWorld(true);
  sceneChanged();
}
// A new size, cover or corner for a block (`matrix`: its render matrix after, when its corner moves): one undo step.
function setCover(root, next, matrix = null, before = { cover: { ...root.userData.source.cover }, matrix: root.matrix.clone() }) {
  const o = root.userData.source;
  const same = JSON.stringify(next) === JSON.stringify(before.cover) && (!matrix || matrix.equals(before.matrix));
  if (!validCoverValues(next) || same) { applyCover(root, before.cover, before.matrix); coverPanel(root); return; }
  gizmo.record({ redo: () => { applyCover(root, next, matrix ?? before.matrix); select(o.id, false, true); },
                 undo: () => { applyCover(root, before.cover, before.matrix); select(o.id, false, true); } });
}
function commitCover() {
  const root = roots.get(selected);
  if (!root?.userData.source.cover || isFloor(root.userData.source.cover)) return;
  setCover(root, retyped(root.userData.source.cover, coverRecipe(), $('coverHeight').value));
}
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
async function pasteSnapshot(clip, delta, step = null) {
  const serial = copySerial + 1;   // the paste's own number, for its prefab groups
  const copies = new Map(), unitOf = e => e.unit ?? e.source.actor, keyOf = e => e.key ?? memberOf(e.source);
  const lightEntries = clip.entries.filter(e => e.source.isLight), effectEntries = clip.entries.filter(e => e.source.isEffect);
  clip = { ...clip, entries: clip.entries.filter(e => !e.source.isLight && !e.source.isEffect) };
  for (const e of clip.entries)
    if (!copies.has(unitOf(e))) copies.set(unitOf(e), { name: `${fromOf(e.source).actor}_copy${++copySerial}`, entity: uuid() });
  const tags = new Map(), tagged = new Set();
  const linkTag = e => {
    const was = linkOf(e);
    if (!was) return null;
    if (!tags.has(was)) {
      const tag = was.replace(/^copy\d+:/, '');
      tags.set(was, `copy${tagged.has(tag) ? ++copySerial : serial}:${tag}`);
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
      twins.set(v.building, { id: newBuildingId(), meta: { name, kind: meta.kind ?? 'building' } });
    }
    const root = makeVolume([0, 0, 0, 96, 96, 64], twins.get(v.building).id, v.floor);
    root.matrix.copy(delta.clone().multiply(v.matrix));
    setVolumeBox(root, volumeBox(root));
    root.userData.deleted = true;
    return root;
  });
  const objs = clip.entries.map(e => {
    const { source, matrix } = e, placed = delta.clone().multiply(matrix), copy = copies.get(unitOf(e));
    return addedObject(source, placed, { actor: copy.name, entity: copy.entity, ...actorPose(source, placed),
      prefab: linkTag(e),
      partner: copies.get(e.partner !== undefined ? e.partner : source.partner)?.name ?? null,
      tinted: e.tinted ?? Boolean(source.provenance?.type === 'spawn' || source.added?.tinted), flags: e.flags ?? null,
      generated: source.added?.generated ?? null });
  });
  // A copied group stays a group, and so do the groups it is in and the ones inside it (groupTree), each with its
  // options as the original has them. A prefab's clip brings its own groups.
  // (each copied member's key, and its copy's record: pieces, lights and buildings)
  const copied = [...clip.entries.map(e => [keyOf(e), { added: copies.get(unitOf(e)).name }]),
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
  // (giving way by time, so that the busy mark keeps turning through a large paste and a small one never waits)
  const built = await buildRoots(objs, step);
  const before = gizmo.picks(), ids = [...objs.map(o => o.id), ...lights.map(r => r.userData.source.id),
                                       ...effects.map(r => r.userData.source.id),
                                       ...(boxesShown ? boxes.map(r => r.userData.source.id) : [])];
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
      if (newGroups.length) { const next = cloneGroups(); for (const g of newGroups) next.delete(g.id); setGroups(next); }
      gizmo.setSelection(before.ids, before.active); sceneChanged();
    },
  });
  return built;
}
function copySelection(cut = false) {
  if (volumesOn) { copyVolumes(cut); return; }
  const clip = snapshot();
  if (!clip) {
    // (a view-only effect is picked but no selection takes it in: the picked one says why)
    const fx = gizmo.selection().find(r => r.userData.effect) ?? effectRoots.get(pickedEffect);
    flashHint(fx ? `It isn't copied: ${effectViewOnly(fx.userData.source, 'copy') ?? 'it is deleted'}` : 'Select a piece, light or floor box to copy');
    return;
  }
  clipboard = clip;
  const made = new Set(clip.volumes.map(v => v.building)).size;
  if (cut) deleteSelection(true);
  flashHint(`${cut ? 'Cut' : 'Copied'} ${clip.words}${made ? ` and ${plural(made, 'building')}` : ''} · Ctrl+V to place a copy`);
}
// Where a paste or placement puts the pivot piece: the point under the screen point `at` (on a piece, or else
// level with where it was copied from), in game units, or null. Fine snap rounds it to 24 units across the floor.
// Tile snap moves it whole tiles from where the piece stands in the map, so a piece aligned to the tiles stays so.
// With Level snap on, a floor piece's height snaps by levels: the height it has in the map, moved by whole levels
// (64 units) to the saved floor under that point (floors.js levelHeight), so it never stacks on the floor it is
// dropped on; with a floor chosen in the Floor picker, to that floor's height in the building there (chosenStorey).
function dropTarget(clip, at) {
  if (!at) return null;
  let point = pick(...at)?.point;
  // over nothing: on the ground grid's plane on a map (Clear map plan, section 3), else level with where it was copied
  const plane = !builderMode && data?.scope === 'map' && !data.preview && data.tileGrid?.origin ? groundHeight() : clip.pivot[2];
  if (!point) point = rayAt(...at).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -plane), new THREE.Vector3());
  if (!point) return null;
  let [x, y, z] = [point.x, point.z, point.y];
  const [px, py] = clip.pivot;
  // a prefab with a building or a piece that keeps the pose rule goes by whole tiles and levels, whatever the snap:
  // its pivot is a tile corner at ground level
  if (clip.gridLocked) return [px + Math.round((x - px) / 96) * 96, py + Math.round((y - py) / 96) * 96, clip.pivot[2] + Math.round((z - clip.pivot[2]) / 64) * 64];
  if (snapMode === 'fine') [x, y] = [Math.round(x / 24) * 24, Math.round(y / 24) * 24];
  else if (snapMode === 'tile') [x, y] = [px + Math.round((x - px) / 96) * 96, py + Math.round((y - py) / 96) * 96];
  if (clip.floor != null && levelSnap)
    z = levelHeight(clip.pivot[2], clip.floor, chosenStorey(x, y)?.z ?? floorUnder(liveFloorIndex(), { ...tileGridOf(data), origin: tileCorner() ?? tileGridOf(data).origin }, [x, y, z]).z);
  // a light from the Add panel: at its template's height above what is under the cursor
  if (clip.lightHeight != null) z += clip.lightHeight;
  // an invisible floor from the Add panel: its top just over the ground at the centre of the tile under its pivot (its
  // first tile's), where the game looks for that tile's floor and the panel measures (floorCentres), whatever the snap:
  // with snap off the pivot stands anywhere in that tile, and the ground there can be a kerb's height off
  if (clip.groundFloor) {
    const o = gridOrigin(), at = o ? [0, 1].map(k => o[k] + 96 * Math.floor(([x, y][k] - o[k]) / 96) + 48) : [x, y];
    const g = groundAt(at[0], at[1], z + 96); if (g != null) z = g + FLOOR_CLEARANCE;
  }
  return [x, y, z];
}
// The move (viewer space) that takes the clip's pivot to a game location, turned by quarter turns about the pivot
// (R while placing). Game (x, y, z up) is viewer (x, z, y).
const moveTo = (clip, [x, y, z], turns = 0) => new THREE.Matrix4().makeTranslation(x, z, y)
  .multiply(actorMatrix([0, 0, 0], [0, turns * 16384, 0]))
  .multiply(new THREE.Matrix4().makeTranslation(-clip.pivot[0], -clip.pivot[2], -clip.pivot[1]));
// A move (viewer space) of pieces ({ source, matrix } each), kept under tile snap to the pose rule of the first of them
// that is a ladder, door, car, van or fracturing piece (the recipe snap, as the gizmo keeps it); any other move as it is.
function keepRecipe(move, parts) {
  const origin = gridOrigin();
  if (!origin || snapMode !== 'tile') return move;
  for (const { source, matrix } of parts) {
    const from = recipeOf(source);
    if (!from) continue;
    const actor = matrix.clone().multiply(new THREE.Matrix4().fromArray(source.matrix).invert())
      .multiply(actorMatrix(source.location, source.rotation));
    return recipeMove(move, actor, from, origin);
  }
  return move;
}
// The move that places a clip: moveTo, kept to the pivot piece's pose rule if it has one, else the first piece's.
const placeMove = (clip, target, turns) => keepRecipe(moveTo(clip, target, turns), [clip.entries[clip.pivotIndex], ...clip.entries].filter(Boolean));
// Paste (Ctrl+V) places what was copied: a preview follows the cursor until a click puts it down. While placing,
// Ctrl+V puts it down under the cursor, as a click does.
function paste() {
  if (placing) { if (pointer) placeAt(pointer, false); return; }
  if (volumesOn) { pasteVolumes(); return; }
  if (!clipboard) { flashHint('Nothing copied yet: select a piece and press Ctrl+C'); return; }
  // a large copy's preview takes a moment to make: the busy mark meanwhile
  if (clipboard.entries.length >= BUSY_PIECES) {
    const clip = clipboard;
    busy(`Getting ${plural(clip.entries.length, 'piece')} ready to place…`, () => { startPlacing(clip); return nextFrame(); }, { now: true });
    return;
  }
  startPlacing(clipboard);
}

// Placing, for paste and the piece list: a see-through preview of the clip follows the cursor, a click places a
// copy there (Shift+click keeps placing), Escape stops. The gizmo is held meanwhile, so a click never grabs a handle.
let pieces, placing = null, ghostDirty = false;   // placing: { clip, entry (from the piece list, or null), ghost }
// The preview is drawn twice: plainly where it is in view, faintly where walls or roofs hide it.
const ghostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.45, depthWrite: false });
const ghostHidden = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.15, depthWrite: false, depthTest: false });
// Pieces of other maps (library.js, tools/viewer/library.py). A piece's record, read on first use, joins the page's
// tables: its meshes, materials and textures under their own keys (lib-<map>-…, with the folder they are served
// from), and its components as templates a copy is made of, as the map's own pieces are. A template names its home
// map (`foreign`), and so does every copy of it; an added record's `from` is the piece in that map.
const libraryRecords = new Map(), foreignTemplates = new Map();
const assetUrl = url => (url.startsWith('/') ? url : cachePrefix + url);
const isForeignTarget = t => typeof t?.package === 'string' && t.level === 'base' && Boolean(data?.name) && t.package.toLowerCase() !== data.name.toLowerCase();
// Many pieces' records read in a few requests (a prefab's or a project's opening), kept for libraryTemplate, which
// then asks the server for none of them. step(done, total) as the chunks arrive. A piece the server could not give
// is left for libraryTemplate's own request, which says why.
const RECORD_CHUNK = 100, fetchedRecords = new Map();
const recordId = source => `${source.package}|${short(source.actor)}`.toLowerCase();
async function readLibraryRecords(sources, step = null) {
  const want = [...new Map(sources.map(s => [recordId(s), s])).entries()].filter(([id]) => !libraryRecords.has(id) && !fetchedRecords.has(id));
  for (let k = 0; k < want.length; k += RECORD_CHUNK) {
    const chunk = want.slice(k, k + RECORD_CHUNK);
    step?.(k, want.length);
    try {
      const answer = await prefabApi.records(chunk.map(([, s]) => ({ package: s.package, level: 'base', actor: short(s.actor) })));
      answer.pieces.forEach((p, i) => { if (p.record) fetchedRecords.set(chunk[i][0], p.record); });
    } catch { break; }
  }
  if (want.length) step?.(want.length, want.length);
  return want.length;
}
function libraryTemplate(source) {
  const id = recordId(source);
  if (!libraryRecords.has(id)) {
    const promise = (async () => {
      let record = fetchedRecords.get(id);
      fetchedRecords.delete(id);
      if (!record) {
        const response = await fetch(`/library/piece.json?${new URLSearchParams({ package: source.package, level: 'base', actor: short(source.actor) })}`);
        record = await response.json().catch(() => ({}));
        if (!response.ok) throw Error(record.error ?? `the piece could not be read (${response.status})`);
      }
      for (const [k, m] of Object.entries(record.meshes)) data.meshes[k] ??= { ...m, url: record.base + m.url };
      for (const [k, m] of Object.entries(record.materials)) data.materials[k] ??= m;
      for (const [k, t] of Object.entries(record.textures)) data.textures[k] ??= { ...t, url: record.base + t.url };
      lineCollision ??= new Map();
      for (const [k, c] of Object.entries(record.collision ?? {})) lineCollision.set(k, collisionMesh(c));
      const foreign = { package: record.source.package, key: record.key, buildings: record.buildings ?? [], areaLights: record.areaLights ?? {} };
      if (record.source.sha256) donorHashes.set(record.source.package.toLowerCase(), record.source.sha256);
      // where the piece stands on its home map's tile grid, said on this map's (the compiler does the same): the
      // pose rule's snap then works as for one of the map's own pieces
      const here = data.tileGrid?.origin, shift = record.grid && here?.length === 3 ? here.map((v, k) => v - record.grid[k]) : [0, 0, 0];
      const rebased = o => {
        const matrix = [...o.matrix];
        matrix[12] += shift[0]; matrix[13] += shift[2]; matrix[14] += shift[1];
        return { ...o, matrix, location: o.location.map((v, k) => v + shift[k]) };
      };
      const sources = record.objects.map(o => {
        const source = { ...rebased(o), layer: 'base', floorLocation: o.location, referencedBy: [], foreign };
        const lights = (foreign.areaLights[o.actor]?.lights ?? []).filter(l => l.component === o.component);
        if (!lights.length) return source;
        const inverse = actorMatrix(o.location, o.rotation).invert();
        const foreignAreaLights = lights.map(light => {
          const source = lightSource(light);
          const relative = inverse.clone().multiply(new THREE.Matrix4().fromArray(source.matrix));
          return { root: { userData: { source, values: valuesOf(source) } }, relative };
        });
        return { ...source, foreignAreaLights };
      });
      for (const s of sources) foreignTemplates.set(`${targetKey(fromOf(s))}|${s.component}`, s);
      // an assembly (a car's body, glass and parts; a door's leaf and frame) comes whole: its parts are placed, moved
      // and copied as one, by the link tag an assembly of the map's own has (useMapFamilies)
      if (record.assembly) {
        const a = record.assembly;
        const assembly = { ...a, tag: a.members.length > 1 ? (record.objects.map(o => o.prefab).find(Boolean) ?? short(a.pivot)) : null };
        for (const m of a.members) foreignAssemblies.set(targetKey({ package: record.source.package, level: 'base', actor: m }), assembly);
      }
      // its meshes and materials loaded, as a placed piece's are (the preview and the thumbnail draw from the caches)
      await Promise.all(sources.map(buildRoot));
      const radius = s => data.meshes[s.mesh].bounds?.[6] ?? 0;
      const pivot = sources.find(s => s.actor === record.assembly?.pivot) ?? sources.reduce((a, b) => (radius(b) > radius(a) ? b : a));
      const frame = actorMatrix(pivot.location, pivot.rotation).invert();
      return { sources, pivotIndex: sources.indexOf(pivot), frame, box: boundsOf(sources, frame), record };
    })();
    promise.catch(() => libraryRecords.delete(id));
    libraryRecords.set(id, promise);
  }
  return libraryRecords.get(id);
}
// An effect, ambient sound or lens flare of another map (effects and sounds plan, stage FX4; a flare since FX6b): its
// template read from its map
// (/library/effect.json: export 28's record, its particle system or waves), kept for the placing and the project's
// copies (foreignEffects, by its target), its system and waves joined to the map's (the panel, the box, the Wave
// preview read them by their ids, which name the donor). Gives the record as an effect root's source.
const effectTemplates = new Map(), foreignEffects = new Map(), fetchedEffects = new Map();
function effectTemplate(source) {
  const id = recordId(source);
  if (!effectTemplates.has(id)) {
    const promise = (async () => {
      let t = fetchedEffects.get(id);
      fetchedEffects.delete(id);
      if (!t) {
        const response = await fetch(`/library/effect.json?${new URLSearchParams({ package: source.package, level: 'base', actor: short(source.actor) })}`);
        t = await response.json().catch(() => ({}));
        if (!response.ok) throw Error(t.error ?? `it could not be read (${response.status})`);
      }
      data.effectSystems ??= {}; data.soundWaves ??= {};
      for (const [k, v] of Object.entries(t.systems ?? {})) data.effectSystems[k] ??= v;
      for (const [k, v] of Object.entries(t.waves ?? {})) data.soundWaves[k] ??= v;
      // what its likeness is drawn from (export 29): the donor's textures, meshes and materials, by their own keys
      if (t.draw) {
        for (const [k, m] of Object.entries(t.draw.meshes ?? {})) data.meshes[k] ??= { ...m, url: t.draw.base + m.url };
        for (const [k, m] of Object.entries(t.draw.materials ?? {})) data.materials[k] ??= m;
        for (const [k, x] of Object.entries(t.draw.textures ?? {})) data.textures[k] ??= { ...x, url: t.draw.base + x.url };
      }
      if (t.source.sha256) donorHashes.set(t.source.package.toLowerCase(), t.source.sha256);
      const out = effectSource({ ...t.record, foreign: { package: t.source.package, key: t.key } });
      foreignEffects.set(targetKey({ package: out.sourcePackage, level: 'base', actor: out.actor }), out);
      return out;
    })();
    promise.catch(() => effectTemplates.delete(id));
    effectTemplates.set(id, promise);
  }
  return effectTemplates.get(id);
}
// Many effects' templates in a few requests (a project's opening), kept for effectTemplate
async function readEffectRecords(sources) {
  for (let k = 0; k < sources.length; k += RECORD_CHUNK) {
    const chunk = sources.slice(k, k + RECORD_CHUNK);
    try {
      const response = await fetch('/library/effects.json', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources: chunk.map(s => ({ package: s.package, level: 'base', actor: short(s.actor) })) }) });
      if (!response.ok) break;
      const answer = await response.json();
      answer.effects.forEach((r, i) => { if (r.record) fetchedEffects.set(recordId(chunk[i]), r.record); });
    } catch { break; }
  }
}
// The templates of the foreign pieces, effects and sounds some added records name, read before the records are
// applied. Gives what could not be had, as sentences.
async function loadForeignTemplates(added, progress = null) {
  const wanted = new Map(), effects = new Map(), failed = [];
  for (const e of added) if (!e.template && isForeignTarget(e.from)) (e.kind ? effects : wanted).set(targetKey(e.from), e.from);
  const list = [...wanted.values()], effectList = [...effects.values()];
  if (list.length > 1) await readLibraryRecords(list, (done, total) => progress?.('reading', done, total));
  if (effectList.length > 1) await readEffectRecords(effectList);
  let made = 0;
  await Promise.all([...list.map(from => libraryTemplate(from)
    .catch(error => failed.push(`${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`))
    .finally(() => progress?.('loading', ++made, list.length))),
    ...effectList.map(from => effectTemplate(from)
      .catch(error => failed.push(`${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`)))]);
  return failed;
}
const foreignCount = () => new Set([...roots.values()].map(r => r.userData.source).filter(o => o.added && o.foreign).map(o => o.actor)).size;
const kilobytes = bytes => (bytes >= 1 << 20 ? `${(bytes / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
function foreignCost(obj) {
  const entry = library?.entry(obj.foreign.key);
  return entry?.closure ? `By the Build, from ${obj.foreign.package}: up to ${kilobytes(entry.closure.bytes)} more in the map` : null;
}
const foreignNote = obj => `A piece of ${obj.foreign.package}, not of this map. The Build copies it into the map with the meshes, materials and `
  + 'textures it needs. A build with Bake the lighting lights it for where it stands (EXP-38); without, it keeps the '
  + 'light it has in its home map, so it can look too dark or too bright here.';
// What Build's panel says of a project with pieces of other maps: what baking does for them.
const bakeNote = () => (foreignCount() ? `${plural(foreignCount(), 'piece')} from other maps: baked, ${foreignCount() === 1 ? 'it is' : 'they are'} lit for `
  + `where ${foreignCount() === 1 ? 'it stands' : 'they stand'}; unbaked, ${foreignCount() === 1 ? 'it keeps' : 'they keep'} the light of the map ${foreignCount() === 1 ? 'it comes' : 'they come'} from.` : null);
let library = null, libraryScope = 'map', chooseToken = 0;
const LIBRARY_SCOPES = { map: 'libFilter', all: 'libAllFilter', prefabs: 'prefabFilter' };
function setLibraryScope(scope) {
  if (builderMode && scope === 'map') scope = 'all';
  libraryScope = LIBRARY_SCOPES[scope] ? scope : 'map';
  remember('workshop.libraryScope', libraryScope);
  $('libScope').value = libraryScope;
  $('libMap').hidden = libraryScope !== 'map';
  library.show(pieces.open && libraryScope === 'all');
  prefabTab.show(pieces.open && libraryScope === 'prefabs');
  if (libraryScope !== 'all') hoverLikeness(null);
  if (placing?.entry) stopPlacing();
  if (pieces.open) $(LIBRARY_SCOPES[libraryScope]).focus({ preventScroll: true });
}
// An entry of All maps: its piece read (exported by the server the first time), then placed as a copy is.
async function chooseLibraryEntry(entry) {
  const token = ++chooseToken;
  if (!entry) { stopPlacing(); return; }
  if (entry.effect) { chooseLibraryEffect(entry, token); return; }
  let template;
  if (!isForeignTarget({ ...entry.source, level: 'base' })) {
    // the map's own piece: a copy of it, as from This map
    const sources = partsOf(targetKey({ package: data.name, level: 'base', actor: `TheWorld.PersistentLevel.${entry.source.actor}` }));
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
  clipboard = { entries: sources.map(source => ({ source, matrix: new THREE.Matrix4().fromArray(source.matrix) })),
                pivot: [...sources[pivotIndex].location], pivotIndex, name: entry.name, libraryEntry: entry };
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
  clipboard = { entries: [{ source, matrix: new THREE.Matrix4().fromArray(source.matrix) }], pivot: [...source.location], pivotIndex: 0,
                name: entry.name, libraryEntry: entry };
  startPlacing(clipboard, entry);
}
function showPieces(on) {
  $('libMap').hidden = libraryScope !== 'map';
  library.show(on && libraryScope === 'all');
  prefabTab.show(on && libraryScope === 'prefabs');
  // floor pieces are marked (the Kind menu's Floors, and a search for "floor" finds them)
  pieces.show(on, () => collectPieces({ roots, data,
    groups: gizmo.linkedGroups([...roots.values()].filter(r => !r.userData.source.added)),
    frameOf: s => actorMatrix(s.location, s.rotation).invert(), boundsOf })
    .map(e => (floorSupportOf(e.sources) != null ? Object.assign(e, { floor: true, text: `${e.text} floor` }) : e))
    .concat(pieceRecipes()));
  if (!on && placing?.entry) stopPlacing();
  if (!on) stopWallDrawing();
  // the hover pane goes with the panel or its All maps tab (closed with the pointer still on a row, it stayed)
  if (!on || libraryScope !== 'all') hoverLikeness(null);
  $('editAdd').classList.toggle('on', on); $('editAdd').setAttribute('aria-pressed', on);
}
// The parts of a piece-list entry where the map has them.
const entryParts = entry => entry.sources.map(source => ({ source, matrix: new THREE.Matrix4().fromArray(source.matrix) }));
// Choosing an entry puts it on the clipboard and places it; choosing it again (null) stops.
function chooseEntry(entry) {
  chooseToken++;
  if (!entry) { stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopWallDrawing(); return; }
  if (entry.wallLook) { startWallDrawing(entry.wallLook); return; }     // a look of the Walls kind: drawn by dragging
  stopWallDrawing();
  if (entry.zone) { stopPlacing(); stopSpawnPlacing(); startZonePlacing(); return; }      // the Landing zones kind
  if (entry.spawnAdd) { stopPlacing(); stopZonePlacing(); startSpawnPlacing(entry.spawnAdd); return; }      // Spawn points
  if (entry.light) {    // the Lights kind's Point Light and Spot Light
    const clip = lightClip(entry.light);
    if (!clip) return;
    if (!lightsShown) { if (volumesOn) setLightsShown(true); else setNormalLights(true); }
    clipboard = clip;
    startPlacing(clip, entry);
    return;
  }
  // a cover block is placed by its first tile: the centre of the tile at its corner goes under the cursor
  const at = entry.sources[entry.pivotIndex].location;
  clipboard = { entries: entryParts(entry), pivot: entry.cover ? [at[0] + 48, at[1] + 48, at[2]] : [...at],
                pivotIndex: entry.pivotIndex, name: entry.name, groundFloor: isFloor(entry.cover) };
  if (clipboard.groundFloor) askLineCollision();     // the ground's collision on its way before the floor goes down
  startPlacing(clipboard, entry);
}
const ghostEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1));
const ghostLine = new THREE.LineBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.7, depthTest: false });
function startPlacing(clip, entry = null) {
  stopPlacing(); stopWallDrawing();
  // a floor piece snaps by levels (dropTarget): its saved floor's height over its pivot
  clip.floor = clip.prefab || clip.entries.some(e => e.source.isLight || e.source.isEffect) ? null : floorSupportOf(clip.entries.map(e => e.source));
  const ghost = new THREE.Group(), here = new THREE.Matrix4();
  ghost.add(previewGroup(clip.entries, ghostHidden, here), previewGroup(clip.entries, ghostMaterial, here));
  // the floor boxes that come with it (a building copied, a prefab's), as outlines
  for (const v of clip.volumes ?? []) {
    const line = new THREE.LineSegments(ghostEdges, ghostLine);
    line.matrix.copy(v.matrix); line.matrixAutoUpdate = false; line.raycast = () => {};
    ghost.add(line);
  }
  ghost.visible = false; ghost.matrixAutoUpdate = false; world.add(ghost);
  placing = { clip, entry, ghost, turns: 0 }; ghostDirty = true;
  gizmo.hold(true); pieces.setChosen(entry); library.setChosen(entry); prefabTab.setChosen(entry); restingHint();
}
function stopPlacing() {
  if (!placing) return;
  world.remove(placing.ghost);
  placing.ghost.traverse(part => part.isSkinnedMesh && part.skeleton.dispose());
  placing = null; gizmo.hold(false); pieces.setChosen(null); library.setChosen(null); prefabTab.setChosen(null);
  clearTimeout(hintTimer); restingHint();
}
// The preview sits where a click would place the piece; it hides when the cursor is off the view.
function moveGhost() {
  ghostDirty = false;
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
  if (clip.entries.length >= BUSY_PIECES)
    await busy(`Placing ${clip.prefab ? clip.name : 'the copy'}: pieces made`, step => pasteSnapshot(clip, delta, step), { total: clip.entries.length, now: true });
  else await pasteSnapshot(clip, delta);
  if (clip.libraryEntry) library.used(clip.libraryEntry);     // it heads the recently used pieces
  if (problem) banner(problem, [['Undo', () => gizmo.undo()]]);
  if (!keep) flashHint(`Placed ${clip.name} · Ctrl+V places another`);
}
// Shift held as a move handle is taken (an axis or a plane): the drag moves a copy along it (the gizmo's copyDrag).
// The selection itself is what moves under the cursor, with the snaps of any drag, and a drawn-only stand-in keeps
// its place; on release the selection is back where it was and the copy is pasted where it was dragged to, as any
// paste is (one undo step, the copy selected). Escape, or a drag that went nowhere, makes no copy.
// Not in the Buildings view, where boxes are copied on their own (copyVolumes): there Shift is a plain move.
function copyDragBegin() {
  if (volumesOn || placing) return null;
  const clip = snapshot();
  if (!clip) return null;
  const stand = new THREE.Group(), here = new THREE.Matrix4();
  stand.add(previewGroup(clip.entries, null, here));
  for (const v of clip.volumes) {
    const line = new THREE.LineSegments(ghostEdges, ghostLine);
    line.matrix.copy(v.matrix); line.matrixAutoUpdate = false; line.raycast = () => {};
    stand.add(line);
  }
  stand.matrixAutoUpdate = false; world.add(stand);
  const hint = $('dragHint');
  hint.hidden = false;
  hint.replaceChildren(`Moving a copy of ${clip.name} · `);
  text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
  return { clip, stand };
}
async function copyDragEnd({ clip, stand }, delta) {
  try {
    if (delta && clip.entries.length >= BUSY_PIECES)
      await busy('Placing the copy: pieces made', step => pasteSnapshot(clip, delta, step), { total: clip.entries.length, now: true });
    else if (delta) await pasteSnapshot(clip, delta);
  } finally {
    // (the stand-in goes once the copy's original is drawn in its place again)
    world.remove(stand);
    stand.traverse(part => part.isSkinnedMesh && part.skeleton.dispose());
  }
  if (delta) flashHint(`Copied ${clip.name}`);
}
function prefabPlacementProblem(clip, delta) {
  if (!builderMode && clip.bounds && data.tileGrid) {
    const b = clip.bounds, box = new THREE.Box3(new THREE.Vector3(b[0], b[2], b[1]), new THREE.Vector3(b[3], b[5], b[4])).applyMatrix4(delta);
    const low = [box.min.x, box.min.z, box.min.y], high = [box.max.x, box.max.z, box.max.y], g = data.tileGrid;
    const over = [0, 1, 2].map(k => Math.max(0, g.origin[k] - low[k], high[k] - (g.origin[k] + g.dimensions[k] * g.size[k])));
    if (over.some(v => v > 0.5)) {
      const words = [over[0] > 0.5 && `${Math.ceil(over[0] / g.size[0])} tile${Math.ceil(over[0] / g.size[0]) === 1 ? '' : 's'} along X`,
                     over[1] > 0.5 && `${Math.ceil(over[1] / g.size[1])} tile${Math.ceil(over[1] / g.size[1]) === 1 ? '' : 's'} along Y`,
                     over[2] > 0.5 && `${Math.ceil(over[2] / g.size[2])} level${Math.ceil(over[2] / g.size[2]) === 1 ? '' : 's'} in height`].filter(Boolean);
      return `${clip.name} reaches ${words.join(' and ')} outside this map's tile grid. Out there the map has no tiles: `
        + 'nothing can be stood on or give cover. Move it in, or make the map larger with Map grid.';
    }
  }
  return null;
}
// ---- Prefabs (prefab plan 5.6 and 5.7; prefabs.js, tools/viewer/prefabs.py). A prefab is what a paste makes, saved:
// added records in a space of its own (the tile grid: the origin a tile corner at ground level), with the groups and
// buildings among them. Saving a selection writes those records; placing reads them into a clip and pastes it, as one
// group marked with the prefab (a stamp: nothing ties it to the file afterwards).
let prefabTab = null;
const donorHashes = new Map();      // a map's package, lower case -> its SHA-256, as its pieces' records give it
const gridBase = () => (data?.tileGrid?.origin?.length === 3 ? data.tileGrid.origin : [0, 0, 0]);
// The selection as a prefab's records: { tiles, pieces, groups, buildings, donors, left (what won't go into it, as
// sentences), offGrid (the pieces that keep the pose rule and stand off the grid), counts, clip, box }, or null with
// nothing to save.
function prefabRecords({ complete = false } = {}) {
  if (complete) return builderRecords();
  const clip = snapshot();
  if (!clip) return null;
  const grid = gridBase(), low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  const grow = b => { for (let k = 0; k < 3; k++) { low[k] = Math.min(low[k], b[k]); high[k] = Math.max(high[k], b[k + 3]); } };
  const offGrid = [];
  for (const r of copyable()) {
    // (an effect, a sound or a lens flare is where it stands: a sound's reach is no part of the footprint)
    if (r.userData.effect) { const p = actorPose(r.userData.source, r.matrix).location; grow([...p, ...p]); continue; }
    if (r.userData.light) { const p = lightPose(r).location; grow([...p, ...p]); continue; }
    const b = physicalBox(r);
    if (b) grow(b);
    const move = isStream(r.userData.source) ? null : gridNow(r);
    if (move && !move.valid && !offGrid.includes(rootName(r))) offGrid.push(rootName(r));
  }
  for (const v of clip.volumes) grow(matrixBox(v.matrix));
  if (!Number.isFinite(low[0])) return null;
  // Height 0 is the map's grid bottom (prefab plan 5.6b): every tile level keeps its number, so what stood on the
  // map's bottom level stands on the builder's drawn grid, and what lies under the grid goes below 0. Builder ground
  // stays zero.
  const down = (v, o, step) => o + Math.floor((v - o + 0.5) / step) * step;
  const origin = [down(low[0], grid[0], 96), down(low[1], grid[1], 96), grid[2]];
  const tiles = [0, 1].map(k => Math.max(1, Math.ceil((high[k] - origin[k]) / 96 - 1e-4)));
  const shift = new THREE.Matrix4().makeTranslation(-origin[0], -origin[2], -origin[1]);
  const pieces = [], left = [], donors = new Map(), names = new Map(), copied = [];
  let n = 0;
  const units = new Map();
  for (const e of clip.entries) {
    if (e.source.isLight) continue;
    if (e.source.isEffect) continue;        // (below, with the lights)
    if (!units.has(e.source.actor)) units.set(e.source.actor, []);
    units.get(e.source.actor).push(e);
  }
  const tags = new Map();
  const donor = from => {
    const hash = from.package.toLowerCase() === data.name.toLowerCase() ? data.source?.sha256 : donorHashes.get(from.package.toLowerCase());
    donors.set(from.package.toLowerCase(), { package: from.package, ...(/^[0-9a-f]{64}$/.test(hash ?? '') ? { sha256: hash } : {}) });
  };
  for (const [actor, list] of units) {
    const s = list[0].source, placed = shift.clone().multiply(list[0].matrix), from = fromOf(s);
    if (s.cover) {
      const name = `${from.actor}_copy${++n}`;
      names.set(actor, name); copied.push([memberOf(s), { added: name }]);
      pieces.push({ actor: name, template: { kind: COVER_KIND, version: coverVersion(s.added?.template?.version, s.cover.type) }, cover: { ...s.cover }, ...actorPose(s, placed) });
      continue;
    }
    if (from.level !== 'base') { left.push(`${short(data.meshes[s.mesh].name)}: a piece of a level the mission streams in, not of a map`); continue; }
    const name = `${from.actor}_copy${++n}`, was = linkOf(list[0]);
    names.set(actor, name); copied.push([memberOf(s), { added: name }]);
    if (was && !tags.has(was)) tags.set(was, `copy${tags.size + 1}:${was.replace(/^copy\d+:/, '')}`);
    const entry = s.foreign?.key ? library?.entry(s.foreign.key) : null;
    pieces.push({ actor: name, from: { package: from.package, level: from.level, actor: from.actor }, components: list.map(e => e.source.component).sort(),
                  ...actorPose(s, placed), prefab: was ? tags.get(was) : null, partner: s.partner ?? null,
                  ...(s.provenance?.type === 'spawn' || s.added?.tinted ? { tinted: true } : {}),
                  ...(entry ? { recipe: { key: entry.key, name: entry.name } } : {}),
                  ...(list[0].flags ? { flags: { ...list[0].flags } } : {}) });
    donor(from);
  }
  // (a partner is named by its name in the prefab; one left out is no partner)
  for (const p of pieces) if (p.from) p.partner = names.get(p.partner) ?? null;
  // its effects and sounds (effects and sounds plan, stage FX6a) and its lens flares (FX6b): each a copy of its
  // original, with the values set on it (a flare has none). One its piece carries isn't in the clip: the piece's
  // copy brings it (snapshot)
  let effects = 0, sounds = 0, flares = 0;
  for (const e of clip.entries) {
    if (!e.source.isEffect) continue;
    const s = e.source, kind = s.kind, from = fromOf(s), what = kind === 'sound' ? 'a sound' : kind === 'flare' ? 'a lens flare' : 'an effect';
    if (from.level !== 'base') { left.push(`${recordName(s, data)}: ${what} of a level the mission streams in, not of a map`); continue; }
    const name = `${from.actor}_copy${++n}`, values = kind === 'flare' ? null : savedValues(e.values);
    copied.push([memberOf(s), { added: name }]);
    pieces.push({ actor: name, kind, from: { package: from.package, level: from.level, actor: from.actor },
                  ...actorPose(s, shift.clone().multiply(e.matrix)), ...(values ? { [kind]: values } : {}) });
    donor(from);
    if (kind === 'sound') sounds++; else if (kind === 'flare') flares++; else effects++;
  }
  let lights = 0;
  for (const e of clip.entries) {
    if (!e.source.isLight) continue;
    const kind = e.source.kind, recipe = families?.lightRecipes?.[kind];
    if (!recipe) { left.push(`${short(e.source.actor)}: a ${kind} light, which the editor can't make in another map yet`); continue; }
    const pose = actorPose(e.source, shift.clone().multiply(e.matrix));
    if (kind === 'point') pose.rotation = [0, 0, 0];
    const name = `${PL}${kind === 'point' ? 'PointLight' : 'SpotLight'}_copy${++n}`;
    copied.push([memberOf(e.source), { added: name }]); lights++;
    const value = k => { const v = e.values?.[k] ?? recipe.values[k]; return Array.isArray(v) ? [...v] : v; };
    // (a made light holds only cones in the editor's ranges: a map's stored 100 or 580 goes in as the 89.99 it lights as)
    pieces.push({ actor: name, template: { kind, version: recipe.latest }, light: withStorableCone(Object.fromEntries(Object.keys(recipe.values).map(k => [k, value(k)]))), ...pose });
  }
  // its buildings: the project's and the map's own selected with the pieces, each a building of the prefab
  const by = new Map();
  for (const v of clip.volumes) {
    if (!by.has(v.building)) by.set(v.building, []);
    by.get(v.building).push({ floor: v.floor, box: matrixBox(shift.clone().multiply(v.matrix)) });
  }
  const buildings = [...by].map(([was, list]) => {
    const numbers = [...new Set(list.map(x => x.floor))].sort((a, b) => a - b).slice(0, BUILDING_FLOORS_MAX), id = uuid();
    copied.push([buildingKey(was), { building: id }]);
    return tidyBuilding({ id, name: clip.buildingMeta[was]?.name ?? '', kind: clip.buildingMeta[was]?.kind ?? 'building',
                          floors: numbers.map(f => ({ boxes: list.filter(x => x.floor === f).map(x => x.box) })) });
  });
  const groups = [...groupTree(copied, mapChain).values()].map(g => ({ id: g.id, breakTogether: g.breakTogether === true, members: [...g.members.values()] }));
  const normalized = normalizePrefab({ pieces, groups, buildings }, [['Selection', [...low, ...high].map((v, k) => v - origin[k % 3])]]);
  return { ...normalized, groups, donors: [...donors.values()].sort((a, b) => a.package.localeCompare(b.package)), left, offGrid, clip,
    counts: { pieces: pieces.length - lights - effects - sounds - flares, lights, effects, sounds, flares, buildings: buildings.length, tiles: normalized.tiles },
           box: new THREE.Box3(new THREE.Vector3(low[0], low[2], low[1]), new THREE.Vector3(high[0], high[2], high[1])) };
}
// A prefab as a clip to place in this map: its records put on the map's tile grid (the prefab's origin on the grid's
// corner; the placing moves it from there), each piece from its template, read from its home map when it is another
// map's. `left`: what can't be had here, as sentences.
async function prefabClip(doc, step = null) {
  const base = gridBase(), here = v => v.map((x, k) => x + base[k]), left = [];
  const records = doc.pieces.map(p => ({ ...p, location: here(p.location) }));
  const foreign = [...new Map(records.filter(p => !p.template && !p.kind && isForeignTarget(p.from)).map(p => [targetKey(p.from), p.from])).values()];
  // (its effects and sounds of other maps: their templates, as a project's copies read them)
  const foreignFx = [...new Map(records.filter(p => p.kind && !p.template && isForeignTarget(p.from)).map(p => [targetKey(p.from), p.from])).values()];
  const unread = foreign.filter(f => !libraryRecords.has(`${f.package}|${short(f.actor)}`.toLowerCase()));
  // the first use reads each piece from the game's maps: all of them asked for at once, so each map is opened once
  if (unread.length > 1) await readLibraryRecords(unread, (done, total) => step?.(done, total, `Opening ${doc.name}: pieces read`));
  const failed = new Map();
  let loaded = 0;
  await Promise.all(foreign.map(from => libraryTemplate(from).finally(() => step?.(++loaded, foreign.length, `Opening ${doc.name}: pieces loaded`)).then(t => {
    const entry = library?.entry(t.record.key);
    // (what the library only holds back is placed: library.js SOFT; what can't be brought is left)
    if (entry && !entry.placeable && !SOFT.includes(entry.blocked)) failed.set(targetKey(from), `${entry.name} of ${from.package} can't be brought into another map yet (${entry.reason})`);
  }, error => { failed.set(targetKey(from), `${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`); })));
  const unreadFx = foreignFx.filter(f => !effectTemplates.has(recordId(f)));
  if (unreadFx.length > 1) await readEffectRecords(unreadFx);
  await Promise.all(foreignFx.map(from => effectTemplate(from).then(t => {
    const entry = t.foreign?.key ? library?.entry(t.foreign.key) : null;
    if (entry && !entry.placeable && !SOFT.includes(entry.blocked)) failed.set(targetKey(from), `${entry.name} of ${from.package} can't be brought into another map yet (${entry.reason})`);
  }, error => { failed.set(targetKey(from), `${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`); })));
  const entries = [];
  for (const p of records) {
    const key = memberKey({ added: p.actor });
    if (p.kind && !p.template) {
      const failure = failed.get(targetKey(p.from));
      if (failure) { left.push(failure); continue; }
      const source = isForeignTarget(p.from) ? foreignEffects.get(targetKey(p.from)) : effectIndex.get(targetKey(p.from))?.userData.source;
      const what = p.kind === 'sound' ? 'sound' : p.kind === 'flare' ? 'lens flare' : 'effect';
      if (!source || source.kind !== p.kind) { left.push(`${short(p.from.actor)} of ${p.from.package}: this export of the map has no such ${what}`); continue; }
      const why = effectViewOnly(source, 'copy');
      if (why) { left.push(`${recordName(source, data)}: the ${what} isn't copied (${why})`); continue; }
      // its values are placed where their family builds (families.json); the prefab keeps them either way
      const values = p.kind !== 'flare' && families?.families?.[`${p.kind}-values`]?.builds ? keptValues(p[p.kind]) : null;
      entries.push({ source, matrix: movedMatrix(source, p.location, p.rotation), ...(values ? { values } : {}), unit: p.actor, key });
      continue;
    }
    if (p.template?.kind === COVER_KIND) {
      const source = coverOf(p);
      if (!source) { left.push(`${short(p.actor)}: a cover block of a recipe this editor doesn't make`); continue; }
      entries.push({ source, matrix: new THREE.Matrix4().fromArray(source.matrix), unit: p.actor, key, link: null, partner: null });
    } else if (p.template) {
      const made = lightsBlocked() ? null : recipeLight(p.template, p.light, p.location, p.rotation);
      if (!made) { left.push(`${short(p.actor)}: a ${p.template.kind} light${lightsBlocked() ? ` (${lightsBlocked()})` : ', which this editor can\'t make yet'}`); continue; }
      entries.push({ source: made.source, matrix: new THREE.Matrix4().fromArray(made.source.matrix), values: made.values, unit: p.actor, key });
    } else {
      const failure = failed.get(targetKey(p.from));
      if (failure) { left.push(failure); continue; }
      const sources = p.components.map(c => templateFor(p.from, c));
      if (sources.some(s => !s)) { left.push(`${short(p.from.actor)} of ${p.from.package} is not in this export of the map`); continue; }
      for (const source of sources)
        entries.push({ source, matrix: movedMatrix(source, p.location, p.rotation), unit: p.actor, key, link: p.prefab ?? null, partner: p.partner ?? null,
                       tinted: Boolean(p.tinted), ...(p.flags ? { flags: { ...p.flags } } : {}) });
    }
  }
  const volumes = [], meta = {};
  for (const b of (doc.buildings ?? []).filter(validBuilding)) {
    meta[b.id] = { name: b.name ?? '', kind: b.kind ?? 'building' };
    b.floors.forEach((floor, k) => { for (const box of floor.boxes) volumes.push({ matrix: boxMatrix(box.map((v, i) => v + base[i % 3])), building: b.id, floor: k }); });
  }
  const tiles = doc.floor?.tiles ?? [1, 1], mark = { id: doc.id, name: doc.name, revision: doc.revision ?? 0 };
  return { entries, volumes, buildingMeta: meta, left, name: doc.name, prefab: mark, wrap: mark, pivotIndex: 0,
           groups: (doc.groups ?? []).map(g => ({ id: g.id, breakTogether: g.breakTogether === true, members: g.members.map(memberKey) })),
           // held by the middle of its footprint, on a tile corner
           pivot: [base[0] + Math.round(tiles[0] / 2) * 96, base[1] + Math.round(tiles[1] / 2) * 96, base[2]],
           gridLocked: volumes.length > 0 || entries.some(e => !e.source.isLight && !e.source.isEffect && pieceGrid(e.source)) };
}
function canRecoverPrefabSources(doc, missing) {
  const actors = new Set(missing);
  return doc.pieces.some(p => p.from && p.recipe && actors.has(p.actor));
}
// A prefab of the Prefabs tab: read, then placed as a paste is.
async function choosePrefab(p) {
  const token = ++chooseToken;
  if (!p) { stopPlacing(); return null; }
  flashHint(`Reading ${p.name}…`);
  return busy(`Opening the prefab ${p.name}…`, step => placePrefab(p, token, step));
}
async function placePrefab(p, token, step = null) {
  let clip, recovered = 0;
  try {
    let doc = await prefabApi.load(p.id), size = await prefabApi.size(doc);
    if (canRecoverPrefabSources(doc, size.unknown)) {
      const match = await prefabApi.recoverSources(doc).catch(() => null);
      if (match?.repaired.length) {
        doc = match.document;
        recovered = match.repaired.length;
        size = await prefabApi.size(doc);
      }
    }
    if (!size.supported) throw Error(size.errors.join('; ') + '. Open Edit to repair it.');
    clip = await prefabClip({ ...doc, floor: { tiles: size.tiles } }, step);
    clip.bounds = size.bounds.map((v, k) => v + gridBase()[k % 3]);
  }
  catch (error) { if (token === chooseToken) flashHint(`${p.name} could not be placed: ${error.message}`); return null; }
  if (token !== chooseToken) return null;
  if (clip.left.length) {
    banner(`${p.name}: ${plural(clip.left.length, 'piece')} could not be placed. ${clip.left[0]}`);
  }
  if (!clip.entries.length && !clip.volumes.length) {
    if (!clip.left.length) flashHint(`There is nothing to place in ${p.name}.`);
    return clip;
  }
  clipboard = clip;
  if (clip.entries.length >= BUSY_PIECES) await nextFrame();
  startPlacing(clip, { prefab: p, key: `prefab:${p.id}` });
  flashHint(`${p.name}${recovered ? ` · recovered ${plural(recovered, 'piece')} by recipe` : ''} · click to place it${clip.gridLocked ? ' (by whole tiles)' : ''} · R turns it`);
  return clip;
}
// A saved prefab's picture: drawn from the selection it was saved from, in a frame (drawPrefabPictures), and kept by
// the server.
const prefabPictures = [];
function drawPrefabPictures() {
  const job = prefabPictures.shift();
  if (!job) return;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 96;
  const object = previewGroup(job.entries, null, new THREE.Matrix4());
  for (const v of job.volumes ?? []) {
    const line = new THREE.LineSegments(ghostEdges, ghostLine); line.matrix.copy(v.matrix); line.matrixAutoUpdate = false; object.add(line);
  }
  if (!pieces.paintThumbs([{ object, box: job.box, thumb: canvas }])) return;
  canvas.toBlob(blob => blob && prefabApi.putPicture(job.id, blob).then(() => prefabTab.refresh()).catch(() => {}), 'image/png');
}
// Save the selection as a prefab under a name: a new one, or over the prefab `replace` (its summary) as its next
// revision. Gives { id, name, revision }, null when `going()` turned false before the save was sent, or throws.
// The server keeps a copy of every piece of a prefab in the library, and the first save of a map's pieces exports
// each one (about 0.2 s a piece: three minutes for 800), so they are exported first, a few at a time, with
// step(done, total) after each batch; the save itself then reads them back at once.
const PREFAB_EXPORT_CHUNK = 20;
async function savePrefab(name, records = prefabRecords(), replace = null, { step = null, going = () => true } = {}) {
  if (!records || (!records.pieces.length && !records.buildings.length)) throw Error('Nothing selected can go into a prefab');
  if (records.size && !records.size.supported) throw Error(records.size.errors.join('; '));
  const sources = [...new Map(records.pieces.filter(p => p.from && !p.kind).map(p => {
    const source = { package: p.from.package, level: 'base', actor: short(p.from.actor) };
    return [recordId(source), source];
  })).values()];
  for (let k = 0; k < sources.length; k += PREFAB_EXPORT_CHUNK) {
    if (!going()) return null;
    step?.(k, sources.length);
    // (a piece that can't be had is the save's to judge: it counts it unknown; a failed request leaves the rest to it)
    try { await prefabApi.warm(sources.slice(k, k + PREFAB_EXPORT_CHUNK)); } catch { break; }
  }
  if (!going()) return null;
  step?.(sources.length, sources.length);
  const id = replace?.id ?? uuid();
  const doc = newPrefab(id, name, records);
  const saved = await prefabApi.save(id, replace ? { ...doc, created: (await prefabApi.load(id)).created } : doc, replace?.revision ?? 0);
  prefabPictures.push({ id, entries: records.clip.entries, volumes: records.clip.volumes, box: records.box });
  prefabTab.refresh();
  return { id, name, revision: saved.revision };
}
const prefabDialog = { root: $('prefabDialog'), records: null, replace: null, builder: false, resolve: null, confirmed: null };
function showPrefabDialog(whole = false) {
  whole = whole === true;
  if (!data) return;
  const records = prefabRecords({ complete: whole });
  if (!records || (!records.pieces.length && !records.buildings.length)) {
    flashHint('Select what should be the prefab first (Box select, T, takes a whole building)');
    return;
  }
  prefabDialog.records = records; prefabDialog.replace = null;
  prefabDialog.builder = whole; prefabDialog.confirmed = null;
  const maps = records.donors.map(d => d.package);
  $('prefabWhat').textContent = `${prefabWords(records.counts)}${records.groups.length ? ` · ${plural(records.groups.length, 'group')}` : ''}`
    + `${maps.length ? ` · pieces of ${maps.join(', ')}` : ''}. It is saved to the Add panel's Prefabs tab, to place in any map as one thing. `
    + 'The file holds references and places only, so it can be passed on.';
  const list = (id, title, lines) => {
    const box = $(id);
    box.hidden = !lines.length;
    box.replaceChildren();
    if (!lines.length) return;
    text(box, 'b', title);
    for (const line of lines.slice(0, 40)) text(box, 'div', line);
    if (lines.length > 40) text(box, 'div', `… and ${lines.length - 40} more`);
  };
  list('prefabLeft', `Left out of the prefab (${records.left.length})`, records.left);
  list('prefabOff', `Off the grid (${records.offGrid.length}): ladders, doors, cars, vans and fracturing pieces build exactly only on whole tiles and quarter turns from where their originals stand`, records.offGrid);
  // a name to start: the prefab the selection was placed from, else its one building's, else the pivot piece's
  const held = selectionGroup(), one = records.buildings.length === 1 ? records.buildings[0].name : '';
  $('prefabName').value = whole ? (builder.doc.revision ? `${builder.doc.name} copy` : '') : (held.kind === 'whole' && held.group.prefab?.name) || one || records.clip.name.replace(/ and \d+ other pieces?$/, '');
  prefabNameCheck();
  prefabDialog.root.hidden = false;
  prefabTab.refresh().then(prefabNameCheck);
  setTimeout(() => $('prefabName').select(), 0);
  return new Promise(resolve => { prefabDialog.resolve = resolve; });
}
function prefabNameCheck() {
  const name = $('prefabName').value.trim(), here = name ? prefabTab.byName(name) : null;
  prefabDialog.replace = here;
  const self = prefabDialog.builder && here?.id === builder.doc.id;
  $('prefabOk').disabled = !name || self;
  $('prefabOk').textContent = here ? 'Replace' : 'Save';
  $('prefabStatus').textContent = here ? `The library has “${here.name}” (revision ${here.revision}): Replace saves over it. What is placed in maps stays as it is.` : '';
  if (self) $('prefabStatus').textContent = 'Use Save to update the prefab being edited, or choose another name for Save as.';
}
function hidePrefabDialog(saved = false) { prefabDialog.root.hidden = true; prefabDialog.records = null; prefabDialog.resolve?.(saved === true); prefabDialog.resolve = null; }
$('prefabName').oninput = () => { prefabDialog.confirmed = null; prefabNameCheck(); };
$('prefabForm').onsubmit = async e => {
  e.preventDefault();
  const name = $('prefabName').value.trim(), { records, replace } = prefabDialog;
  if (!name || !records) return;
  if (prefabDialog.builder && replace?.id === builder.doc.id) { prefabNameCheck(); return; }
  if (prefabDialog.builder && replace && prefabDialog.confirmed !== `${replace.id}:${replace.revision}`) {
    prefabDialog.confirmed = `${replace.id}:${replace.revision}`;
    $('prefabStatus').textContent = `Replace “${replace.name}” with these contents? The prefab being edited stays unchanged. Click Confirm replacement to continue.`;
    $('prefabOk').textContent = 'Confirm replacement'; return;
  }
  $('prefabOk').disabled = true; $('prefabStatus').textContent = 'Saving…';
  try {
    if (prefabDialog.builder) {
      const saved = await saveBuilder({ name, replace });
      if (saved) hidePrefabDialog(true);
      else { hidePrefabDialog(false); }
      return;
    }
    // Closing the dialog while the pieces are exported stops there; once the save is sent it finishes and says so.
    const open = () => prefabDialog.records === records;
    const step = (done, total) => {
      if (open() && total >= PREFAB_EXPORT_CHUNK)
        $('prefabStatus').textContent = done < total ? `Saving: copying the pieces to the library, ${done} of ${total} (the first save of a map's pieces takes a while)…` : 'Saving…';
    };
    const saved = await savePrefab(name, records, replace, { step, going: open });
    if (!saved) return;
    if (open()) hidePrefabDialog(true);
    flashHint(`Saved the prefab ${saved.name}${replace ? ` (revision ${saved.revision})` : ''} · it is in the Add panel's Prefabs tab`);
  } catch (error) {
    if (prefabDialog.records !== records) { flashHint(`The prefab ${name} was not saved: ${error.message}`); return; }
    $('prefabOk').disabled = false; $('prefabStatus').textContent = `Not saved: ${error.message}`;
  }
};
$('prefabClose').onclick = $('prefabCancel').onclick = hidePrefabDialog;
prefabDialog.root.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { e.preventDefault(); hidePrefabDialog(); } });
$('selectionPrefab').onclick = $('prefabSave').onclick = $('volumePrefab').onclick = showPrefabDialog;
// Delete: an added piece goes; an original is hidden (and returns with undo or Reset all).
// A step that touches many pieces (BUSY_PIECES or more) puts the busy mark up first, so the page says what it is
// doing instead of standing still (plan "faster editor", L3); a small one runs at once.
function heavy(message, count, work) {
  if (count < BUSY_PIECES) return work();
  return busy(message, async () => { work(); await nextFrame(); }, { now: true });
}
// Undo and redo: a large step (a paste or a delete of many pieces says its size) under the busy mark.
function undoStep(redo = false) {
  const size = (redo ? gizmo.peekRedo() : gizmo.peekUndo())?.size ?? 0;
  heavy(`${redo ? 'Redoing' : 'Undoing'} a step of ${plural(size, 'piece')}…`, size, () => (redo ? gizmo.redo() : gizmo.undo()));
}
function deleteSelection(quiet = false) {
  if (volumesOn) { deleteVolumes(); return; }
  const count = copyable().length;
  heavy(`Deleting ${plural(count, 'piece')}…`, count, () => deleteNow(quiet));
}
function deleteNow(quiet = false) {
  const targets = copyable(), boxes = selectedBoxes();
  if (!targets.length && !boxes.length) {
    const fx = effectRoots.get(pickedEffect);
    if (ownSet.size) flashHint('The map\'s own building is not deleted: its boxes are the map\'s');
    else if (fx) flashHint(`It isn't deleted: ${effectViewOnly(fx.userData.source, 'delete') ?? 'it is deleted'}`);
    return;
  }
  const pieces = targets.filter(r => !r.userData.light && !r.userData.effect), lights = targets.filter(r => r.userData.light);
  const added = pieces.filter(r => r.userData.source.added), originals = pieces.filter(r => !r.userData.source.added);
  const addedLights = lights.filter(r => r.userData.source.added), originalLights = lights.filter(r => !r.userData.source.added);
  // effects and sounds (effects and sounds plan, FX3): those the export lets an edit delete
  const effects = targets.filter(r => r.userData.effect && !effectViewOnly(r.userData.source, 'delete'));
  const addedEffects = effects.filter(r => r.userData.source.added), originalEffects = effects.filter(r => !r.userData.source.added);
  const kept = targets.filter(r => r.userData.effect && effectViewOnly(r.userData.source, 'delete'));
  if (kept.length && kept.length === targets.length && !boxes.length) { flashHint(`It isn't deleted: ${effectViewOnly(kept[0].userData.source, 'delete')}`); return; }
  const before = gizmo.picks();
  gizmo.record({
    size: targets.length,
    redo: () => {
      removeRoots(added); removeLightRoots(addedLights); removeEffectRoots(addedEffects);
      for (const r of [...originals, ...originalLights, ...originalEffects, ...boxes]) r.userData.deleted = true;
      refreshLightVisibility(); lightsDirty = true; gizmo.setSelection([]); sceneChanged();
    },
    undo: () => {
      addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects);
      for (const r of [...originals, ...originalLights, ...originalEffects, ...boxes]) r.userData.deleted = false;
      refreshLightVisibility(); lightsDirty = true; gizmo.setSelection(before.ids, before.active); sceneChanged();
    },
  });
  const what = selectionWords([...targets, ...boxes]);
  if (!quiet) flashHint(`Deleted ${what} · Ctrl+Z brings ${targets.length + boxes.length === 1 ? 'it' : 'them'} back${ownSet.size ? ' · the map\'s own building stays' : ''}`);
}
// Reset piece: the selection back where the map has it; a light's values too. One undo step.
function resetSelected() {
  const selection = gizmo.selection(), lights = selection.filter(r => r.userData.light && valuesEdited(r));
  // an effect kept where it stands (follow none): back to following its piece (effects and sounds plan, Part C)
  const stays = selection.filter(r => r.userData.effect && r.userData.stays);
  // an effect's or sound's values (stage FX5): back to the map's
  const valued = selection.filter(r => r.userData.effect && r.userData.values), fxValues = valued.map(r => r.userData.values);
  if (!lights.length && !stays.length && !valued.length) { gizmo.resetSelection(); return; }
  const moved = selection.filter(r => r.userData.edit), before = moved.map(r => r.matrix.clone()), home = moved.map(r => baseMatrix(r));
  const values = lights.map(r => ({ ...r.userData.values }));
  gizmo.record({
    redo: () => { gizmo.applyMatrices(moved, home); for (const r of lights) setLightValues(r, r.userData.baseValues); for (const r of stays) r.userData.stays = false; for (const r of valued) r.userData.values = null; sceneChanged(); },
    undo: () => { gizmo.applyMatrices(moved, before); lights.forEach((r, k) => setLightValues(r, values[k])); for (const r of stays) r.userData.stays = true; valued.forEach((r, k) => { r.userData.values = fxValues[k]; }); sceneChanged(); },
  });
}

// The landing zone's pieces (compiler.LANDING_PREFIXES, F-45): from the server's families, else by their archetype.
const LANDING_PREFIXES = ['dgn_dropshipsoldierspawn.', 'veh_lv1skyranger_mod.prefabs.'];
let landingActors = null;
const isLanding = o => !o.foreign && (landingActors ? landingActors.has(fromOf(o).actor)
  : LANDING_PREFIXES.some(p => String(o.archetype ?? '').toLowerCase().startsWith(p)));

// Floor pieces (floors.js has the rules): the pieces that carry the map's saved floor tiles, flat, and not a
// decoration lying on another floor piece (a rug, a plate). The piece list offers them as Floors; placing one keeps
// the height it has in the map, moved by whole levels to the saved floor under the cursor, and across it moves freely
// or by Snap. Worked out on first use (a map is one page).
let floorInfo = null;
function floorData() {
  if (!floorInfo) {
    const tiles = data.preview ? [] : data.tactical?.floorTiles ?? [];
    const actors = new Map();
    for (const o of data.objects) {
      if (o.layer !== 'base' || o.hidden || o.environment) continue;
      if (!actors.has(o.actor)) actors.set(o.actor, { actor: o.actor, parts: [], location: o.location });
      actors.get(o.actor).parts.push(o);
    }
    const floors = ownedFloors(tiles);
    const kinds = classifyFloors([...floors.keys()].filter(a => actors.has(a)).map(a => ({ actor: a, box: worldBox(actors.get(a).parts, data.meshes) })));
    floorInfo = { kinds, stamps: floorStamps([...actors.values()], kinds, floors), index: floorIndex(tiles) };
  }
  return floorInfo;
}
// Level snap (L, the tool strip's button under Snap; on unless turned off, and remembered): floor pieces keep to whole
// levels when placed and when moved with the gizmo. Off, they are placed and moved as any piece is.
const LEVEL_SNAP = 'workshop.levelSnap';
let levelSnap = recall(LEVEL_SNAP) !== '0';
function setLevelSnap(on) {
  levelSnap = Boolean(on); remember(LEVEL_SNAP, levelSnap ? '1' : '0'); ghostDirty = true;
  levelButton(); restingHint();
}
function levelButton() {
  const button = $('editLevels');
  button.classList.toggle('on', levelSnap); button.setAttribute('aria-pressed', levelSnap);
  button.title = levelSnap
    ? 'Level snap on (L): floor pieces keep to whole levels (64 units up). Placed, one takes its height in the map moved to '
      + 'the level under the cursor, or to the floor chosen in the Floor picker; moved up or down, it steps by whole levels. '
      + 'Click to turn it off'
    : 'Level snap off (L): floor pieces are placed and moved as any piece is. Click to turn it on';
}
// The floor chosen in the Floor picker under a point: { z (its walking height, floors.js storeyHeight), building, floor }
// of the building whose floor stands there, else the nearest with that floor; null with All.
const storeyHeights = new Map();
function chosenStorey(x, y) {
  const value = $('floor').value;
  const every = allBuildings();
  if (!value || value === 'all' || !every.length) return null;
  const k = Number(value) - 1, b = buildingWithFloor(every, k, x, y);
  if (b < 0) return null;
  const key = `${every[b].id}:${k}:${buildingsVersion}`;
  if (!storeyHeights.has(key)) storeyHeights.set(key, storeyHeight(every[b].floors[k], data.preview ? [] : data.tactical?.floorTiles));
  const z = storeyHeights.get(key);
  return z == null ? null : { z, building: b, floor: k };
}
// A floor piece's saved floor height over its pivot, or null for any other piece (several components, a car's part).
function floorSupportOf(sources) {
  if (!data || sources.length !== 1 || sources[0].partner) return null;
  return floorData().stamps.get(stampSignature(sources))?.support ?? null;
}

// Reset all: the map as exported. Added pieces go, deleted ones return, moved ones go home, groups end, and the grid,
// the landing zones and the clear mark are the map's own again; one undo step.
function resetAll() {
  const all = [...roots.values()], lights = [...lightRoots.values()];
  const added = all.filter(r => r.userData.source.added), deleted = [...all, ...lights].filter(r => r.userData.deleted);
  const flagged = all.filter(r => !r.userData.source.added && r.userData.flags), flagsBefore = flagged.map(r => r.userData.flags);
  const moved = [...all, ...lights].filter(r => r.userData.edit && !r.userData.source.added);
  const addedLights = lights.filter(r => r.userData.source.added), changed = lights.filter(r => !r.userData.source.added && valuesEdited(r));
  // effects and sounds: copies go, deleted ones return, moved ones go home, kept ones follow their piece again
  const fx = [...effectRoots.values()].filter(r => !isStream(r.userData.source));
  const addedEffects = fx.filter(r => r.userData.source.added), stays = fx.filter(r => r.userData.stays);
  const valued = fx.filter(r => !r.userData.source.added && r.userData.values), fxValues = valued.map(r => r.userData.values);
  deleted.push(...fx.filter(r => r.userData.deleted && !r.userData.source.added));
  moved.push(...fx.filter(r => r.userData.edit && !r.userData.source.added));
  // the map's own buildings changed or deleted come back as the map has them too
  const edits = mapEdits(), restore = mapRestoreChange([...edits.changed, ...edits.gone]);
  // the project's own buildings go: their boxes, which the buildings are made from
  const ownBoxes = liveVolumes().filter(r => !buildingMeta.get(r.userData.volume.building)?.map);
  if (!added.length && !deleted.length && !moved.length && !flagged.length && !groups.size && !addedLights.length && !changed.length && !areaBindings.size && !restore.count
      && !addedEffects.length && !stays.length && !valued.length
      && !ownBoxes.length && !stage && !landingZones && !cleared && !projectMissions && !missionMoves.size && !projectSpawnRules) return;
  const before = moved.map(r => r.matrix.clone()), home = moved.map(r => baseMatrix(r)), picks = gizmo.picks();
  // the map's own grid, landing zones and no clear mark
  const map = { stage, zones: landingZones ? landingZones.map(z => ({ ...z })) : null, cleared, keeps: clearKeepsOutside,
                missions: projectMissions ? projectMissions.map(e => ({ ...e })) : null, moves: new Map(missionMoves),
                rules: projectSpawnRules };
  const mapState = m => {
    cleared = m.cleared; clearKeepsOutside = m.keeps; landingZones = m.zones ? m.zones.map(z => ({ ...z })) : null;
    projectMissions = m.missions ? m.missions.map(e => ({ ...e })) : null;
    setMissionMoves(new Map(m.moves ?? []));
    projectSpawnRules = m.rules ?? null; syncSpawnRule();
    mergedBuildings = null; pickedZone = null; setStage(m.stage); clearedChanged(); refreshLandingZones(); refreshMissionPicker();
  };
  const groupsBefore = cloneGroups(), valuesBefore = changed.map(r => ({ ...r.userData.values })), bindingsBefore = new Map(areaBindings);
  gizmo.record({
    redo: () => {
      for (const r of flagged) r.userData.flags = null;
      removeRoots(added); removeLightRoots(addedLights); removeEffectRoots(addedEffects); for (const r of stays) r.userData.stays = false;
      for (const r of valued) r.userData.values = null;
      for (const r of deleted) r.userData.deleted = false; gizmo.applyMatrices(moved, home);
      for (const r of changed) setLightValues(r, r.userData.baseValues);
      restore.redo();
      for (const r of ownBoxes) r.userData.deleted = true;
      mapState({ stage: null, zones: null, cleared: false, keeps: false, missions: null, rules: null });
      areaBindings = new Map(); setGroups(new Map()); refreshLightVisibility(); lightsDirty = true; sceneChanged();
    },
    undo: () => {
      flagged.forEach((r, k) => { r.userData.flags = flagsBefore[k]; });
      addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects); for (const r of stays) r.userData.stays = true;
      valued.forEach((r, k) => { r.userData.values = fxValues[k]; });
      for (const r of deleted) r.userData.deleted = true; gizmo.applyMatrices(moved, before);
      changed.forEach((r, k) => setLightValues(r, valuesBefore[k]));
      restore.undo();
      for (const r of ownBoxes) r.userData.deleted = false;
      mapState(map);
      areaBindings = new Map(bindingsBefore); setGroups(cloneGroups(groupsBefore)); refreshLightVisibility(); lightsDirty = true;
      gizmo.setSelection(picks.ids, picks.active); sceneChanged();
    },
  });
}
// Groups' pieces on the map now (deleted ones left out): member key -> its roots. Remade after any change of pieces.
let liveCache = null;
function liveMembers() {
  if (!liveCache) {
    liveCache = new Map();
    const live = r => {
      const k = memberOf(r.userData.source);
      if (!liveCache.has(k)) liveCache.set(k, []);
      liveCache.get(k).push(r);
    };
    for (const r of roots.values()) if (!r.userData.deleted) live(r);
    // lights, and the project's buildings by their boxes (a building's key holds all of them)
    for (const r of lightRoots.values()) if (!r.userData.deleted && !r.userData.derivedGone) live(r);
    for (const r of volumeRoots.values()) if (!r.userData.deleted) live(r);
    for (const r of effectRoots.values()) if (!r.userData.deleted && !r.userData.derivedGone && !isStream(r.userData.source)) live(r);
  }
  return liveCache;
}
// A group's pieces on the map, those of the groups inside it too; and its own (the ones it holds itself).
const liveKeys = g => leafKeys(g).filter(k => liveMembers().has(k));
const ownKeys = g => [...g.members].filter(([k, m]) => m.group === undefined && liveMembers().has(k)).map(([k]) => k);
// The group of a piece, if two or more of its pieces are on the map (a delete can leave one; undo brings it back).
const liveGroup = key => { const g = groupIndex.get(key); return g && liveKeys(g).length >= 2 ? g : undefined; };
// Pieces that can break in the game: destructible props (collectibles build as such). Breaking together is over a
// group's own pieces: the groups inside it have the option for themselves.
const BREAKABLE = new Set(['XComDestructibleActor', 'XComCollectible']);
const breakableCount = g => ownKeys(g).filter(k => BREAKABLE.has(liveMembers().get(k)[0].userData.source.actorClass)).length;
// Its cover blocks (high or low, not invisible floors): in a group that breaks together the Build makes each as a
// hidden prop, which goes when a breakable piece of the group is destroyed. One breakable piece is enough with a block.
const breakBlockCount = g => ownKeys(g).filter(k => { const c = liveMembers().get(k)[0].userData.source.cover; return c && !isFloor(c); }).length;
// Its made walls (custom geometry plan, M3 item 4): in a group that breaks together each lists the group's props and
// cover blocks in the parts of it they stand by (the Build's frac_walls.group_columns), so they go when that part breaks.
// With a made wall one prop or cover block is enough.
const breakWallCount = g => ownKeys(g).filter(k => liveMembers().get(k)[0].userData.source.added?.generated?.kind === 'fracWall').length;
// The selected pieces as units: each piece stands for the outermost group all of whose pieces are selected
// (groupKey(id)), or for itself (its member key).
function selectionUnits(keys) {
  const units = new Set(), whole = new Map(), isWhole = g => {
    if (!whole.has(g.id)) whole.set(g.id, liveKeys(g).every(k => keys.has(k)));
    return whole.get(g.id);
  };
  for (const k of keys) {
    let unit = k;
    for (const g of groupChain(groupIndex.get(k))) { if (!isWhole(g)) break; unit = groupKey(g.id); }
    units.add(unit);
  }
  return units;
}
// What the selection is to the groups: { kind, group, units }. 'whole': one group, all of its pieces on the map and
// nothing else (the outermost such); 'part': some of one group's pieces or inner groups only (an unlocked group: the
// innermost group that holds them all; `units` says how many pieces and whole groups they are); 'new': two or more
// pieces or whole groups that no one group holds; null: nothing to do.
function selectionGroup() {
  const keys = new Set(groupables().map(r => memberOf(r.userData.source)));
  if (!keys.size) return { kind: null };
  const units = selectionUnits(keys);
  if (units.size === 1 && [...units][0].startsWith('group|')) return { kind: 'whole', group: groups.get([...units][0].slice(6)), units: 1 };
  let common = null;
  for (const k of keys) {
    const chain = groupChain(groupIndex.get(k));
    common = common ? common.filter(g => chain.includes(g)) : chain;
    if (!common.length) break;
  }
  if (common?.length) return { kind: 'part', group: common[0], units: units.size };
  return { kind: units.size >= 2 ? 'new' : null, count: units.size, groups: [...units].filter(u => u.startsWith('group|')).length };
}
// The group section of the piece panel, the group chip and the colour of the selection box (gold for a group).
function groupPanel() {
  const box = $('groupBox'), { kind, group: g, count, groups: wholeGroups } = selectionGroup();
  box.hidden = !kind;
  groupChip.hidden = !g;
  highlight.material.color.set(g && kind === 'whole' ? 0xe8bd5c : 0x96e5d7);
  if (!kind) return;
  const n = g ? liveKeys(g).length : count;
  box.classList.toggle('locked', Boolean(g));
  $('groupMake').hidden = kind !== 'new';
  $('groupDissolve').hidden = $('groupBreakRow').hidden = !g;
  if (!g) {
    $('groupTitle').textContent = 'Not grouped';
    $('groupText').textContent = wholeGroups
      ? `Group these ${n} (${plural(wholeGroups, 'group')}${n > wholeGroups ? ` and ${plural(n - wholeGroups, 'piece')}` : ''}) to select and move them as one. The groups stay as they are inside the new one.`
      : `Group these ${n} pieces to select and move them as one, and to give them group options.`;
    $('groupNote').hidden = true;
    return;
  }
  groupChip.className = 'chip group';
  groupChip.textContent = `Group of ${n}`;
  groupChip.title = 'Its pieces select and move as one (Ctrl+Shift+G ungroups it)';
  const inner = [...g.members.values()].filter(m => m.group !== undefined && groups.has(m.group)).length;
  $('groupTitle').textContent = `${g.prefab ? `Prefab · ${g.prefab.name}` : 'Group'} · ${keyWords(liveKeys(g))}${inner ? `, ${plural(inner, 'group')} inside` : ''}`;
  $('groupText').textContent = (g.prefab ? `Placed from the prefab ${g.prefab.name} (revision ${g.prefab.revision}): a copy of its own, which changes to the prefab don't reach. ` : '')
    + (inner
    ? 'Everything in it selects and moves as one, whether linked pieces are on or off. Ungroup it to get the groups inside it back on their own.'
    : 'Its pieces select and move as one, whether linked pieces are on or off. Ungroup it to move one on its own.');
  $('groupBreak').checked = g.breakTogether;
  const breakable = breakableCount(g), blocks = breakBlockCount(g), walls = breakWallCount(g);
  const can = breakable >= 2 || (breakable >= 1 && blocks >= 1) || (walls >= 1 && breakable + blocks >= 1);
  $('groupBreakRow').classList.toggle('off', !can && !g.breakTogether);
  $('groupBreak').disabled = !can && !g.breakTogether;
  const note = $('groupNote');
  const own = ownKeys(g).length, stay = own - breakable - blocks - (can ? walls : 0);
  note.hidden = !(!can || (g.breakTogether && (stay > 0 || blocks || walls || inner)));
  note.textContent = !can
    ? `Breaking together needs two breakable pieces (props) of the group's own, or one and a cover block or a made wall: this group has ${breakable}${blocks ? ` and ${plural(blocks, 'cover block')}` : ''}${walls ? ` and ${plural(walls, 'made wall')}` : ''}. The map's walls and scenery move with a group but don't break with it${inner ? ', and the groups inside it have the option for themselves' : ''}.`
    : [walls ? `Its props and cover blocks go when the part of ${walls === 1 ? 'its made wall' : 'a made wall of it'} they stand by breaks.` : '',
       blocks ? `${blocks === 1 ? 'Its cover block goes' : `Its ${blocks} cover blocks go`} when a breakable piece of the group is destroyed${walls ? ' or the wall behind it breaks' : ''}; nothing else destroys ${blocks === 1 ? 'it' : 'them'}.` : '',
       stay > 0 ? `${plural(stay, 'piece')} of the group ${stay === 1 ? 'is' : 'are'} not breakable and stay${stay === 1 ? 's' : ''} standing.` : '',
       inner ? 'The groups inside it break by their own option.' : ''].filter(Boolean).join(' ');
}
// A change to the groups as one undo step; the panel and the selection follow.
function changeGroups(edit, message) {
  const before = cloneGroups(), after = cloneGroups();
  edit(after);
  gizmo.record({ redo: () => setGroups(cloneGroups(after)), undo: () => setGroups(cloneGroups(before)) });
  select(gizmo.active, false, true);
  if (message) flashHint(message);
}
// Lock as group (Ctrl+G): the selected pieces and whole groups become one locked group, the groups kept as they
// are inside it. Pieces picked out of a group leave it (a group left with fewer than two members ends), and the new
// group breaks together if one of those did. When one group held them all, the new group is made inside it.
function lockAsGroup() {
  const records = new Map(groupables().map(r => [memberOf(r.userData.source), memberRecord(r.userData.source)]));
  const units = selectionUnits(new Set(records.keys()));
  if (units.size < 2) { flashHint('Select two or more pieces or groups to group them'); return; }
  const from = [...units].map(u => groupIndex.get(u)), id = uuid();
  // one group holds them all (some of its pieces or inner groups): the new group is made inside it
  // (only some of a group's pieces can be selected when the rest can't be, a streamed patch's say)
  const held = selectionGroup(), within = held.kind === 'part' ? held.group : null;
  const breakTogether = [...units].some((u, k) => !u.startsWith('group|') && from[k]?.breakTogether);
  const inner = [...units].filter(u => u.startsWith('group|')).length;
  changeGroups(next => {
    const members = new Map();
    [...units].forEach((u, k) => {
      if (from[k]) next.get(from[k].id).members.delete(u);
      members.set(u, records.get(u) ?? { group: u.slice(6) });
    });
    next.set(id, { id, locked: true, breakTogether, members });
    if (within) next.get(within.id).members.set(groupKey(id), { group: id });
    pruneGroups(next);
  }, `Grouped ${inner ? `${plural(inner, 'group')}${units.size > inner ? ` and ${plural(units.size - inner, 'piece')}` : ''}` : plural(units.size, 'piece')}`
     + `${within ? ' inside its group' : ''} · they select and move as one`);
}
// Ungroup: the group ends; its pieces and the groups inside it stay, in the group it was in if it was in one.
function ungroup(g) {
  const inner = [...g.members.values()].some(m => m.group !== undefined);
  changeGroups(next => {
    const gone = next.get(g.id), outer = [...next.values()].find(o => o.members.has(groupKey(g.id)));
    next.delete(g.id);
    if (outer) { outer.members.delete(groupKey(g.id)); for (const [k, m] of gone.members) outer.members.set(k, m); }
    pruneGroups(next);
  }, inner ? 'Ungrouped · the groups inside it stay groups' : 'Ungrouped · the pieces are separate again');
}
// Ctrl+G groups the selection; Ctrl+Shift+G ungroups the selected group.
function groupShortcut(dissolve) {
  const { kind, group: g } = selectionGroup();
  if (dissolve) { if (g) ungroup(g); else flashHint('Select a group to ungroup it'); return; }
  if (kind === 'new') lockAsGroup();
  else if (g) flashHint('Already a group · Ctrl+Shift+G ungroups it');
  else flashHint('Select two or more pieces or groups to group them');
}

// Align (the piece panel, with two or more pieces or groups selected): lines the others up with one of them, the
// target, along the chosen game axes, any of X, Y and Z: their boxes' centres, low edges or high edges meet. The
// target is the last one picked (the one the gizmo sits on) unless another is chosen in the panel; a white box marks
// it in the view. What moves as one stays together: a locked group, and with linked pieces on, linked pieces. Only
// moves, never turns; one undo step.
const AXES = { x: 'x', y: 'z', z: 'y' };   // game axis -> the viewer's
const ALIGN = 'workshop.align';
const targetHelper = new THREE.Box3Helper(new THREE.Box3(), 0xffffff);
targetHelper.visible = false; world.add(targetHelper);
let alignTarget = null;   // the id of a piece of the chosen target, or null for the last one picked
function alignPrefs() {
  try { const p = JSON.parse(recall(ALIGN)); if (p && Array.isArray(p.axes)) return p; } catch { /* the defaults */ }
  return { axes: ['x'], by: 'centre' };
}
function alignUnits() {
  const units = gizmo.units(copyablePieces()), holding = id => units.find(u => u.some(r => r.userData.source.id === id));
  const last = holding(gizmo.active) ?? units.at(-1);
  return { units, last, ref: holding(alignTarget) ?? last };
}
const unitBox = u => { const b = new THREE.Box3(); for (const r of u) b.expandByObject(r); return b; };
const unitName = u => {
  const g = liveGroup(memberOf(u[0].userData.source)), name = short(data.meshes[u[0].userData.source.mesh].name);
  return g && u.every(r => groupIndex.get(memberOf(r.userData.source)) === g) ? `the group of ${name}` : name;
};
// A target's label: its name and where its box's centre is (game X and Y), so two alike are told apart.
function unitLabel(u, last) {
  const c = unitBox(u).getCenter(new THREE.Vector3()), name = unitName(u);
  return `${name[0].toUpperCase()}${name.slice(1)} · X ${Math.round(c.x)}, Y ${Math.round(c.z)}${u === last ? ' (last picked)' : ''}`;
}
function alignPanel() {
  const box = $('alignBox'), { units, last, ref } = alignUnits();
  box.hidden = units.length < 2;
  targetHelper.visible = !box.hidden;
  if (box.hidden) { alignTarget = null; return; }   // a chosen target lasts while two or more stay selected
  targetHelper.box.copy(unitBox(ref));
  const prefs = alignPrefs();
  for (const a of ['x', 'y', 'z']) $(`align${a.toUpperCase()}`).checked = prefs.axes.includes(a);
  $('alignBy').value = prefs.by;
  $('alignGo').disabled = !prefs.axes.length;
  // The target list: one entry per piece or group selected, the target chosen.
  const select = $('alignTarget'), options = units.map(u => [u[0].userData.source.id, unitLabel(u, last)]);
  if (select.dataset.key !== JSON.stringify(options)) {
    select.replaceChildren(...options.map(([value, label]) => Object.assign(document.createElement('option'), { value, textContent: label })));
    select.dataset.key = JSON.stringify(options);
  }
  select.value = ref[0].userData.source.id;
  $('alignText').textContent = `Moves ${units.length === 2 ? 'the other one' : `the other ${units.length - 1}`} to line up with the target`
    + ' (the white box in the view). X and Y are across the floor, Z is up.';
}
function saveAlignPrefs() {
  const axes = ['x', 'y', 'z'].filter(a => $(`align${a.toUpperCase()}`).checked);
  remember(ALIGN, JSON.stringify({ axes, by: $('alignBy').value }));
  $('alignGo').disabled = !axes.length;
}
function align() {
  const { axes, by } = alignPrefs(), { units, ref } = alignUnits();
  if (units.length < 2 || !axes.length) return;
  const at = (b, k) => (by === 'min' ? b.min[k] : by === 'max' ? b.max[k] : (b.min[k] + b.max[k]) / 2);
  const goal = unitBox(ref), targets = [], before = [], after = [];
  for (const u of units) {
    if (u === ref) continue;
    const b = unitBox(u), d = new THREE.Vector3();
    for (const a of axes) d[AXES[a]] = at(goal, AXES[a]) - at(b, AXES[a]);
    if (d.lengthSq() < 1e-8) continue;
    // under tile snap, a ladder, door, car or van lines up as near as its pose rule lets it
    const move = keepRecipe(new THREE.Matrix4().makeTranslation(d.x, d.y, d.z), u.map(r => ({ source: r.userData.source, matrix: r.matrix })));
    for (const r of u) { targets.push(r); before.push(r.matrix.clone()); after.push(move.clone().multiply(r.matrix)); }
  }
  const what = `${axes.map(a => a.toUpperCase()).join(', ')} (${by === 'centre' ? 'centres' : by === 'min' ? 'low edges' : 'high edges'})`;
  if (!targets.length) { flashHint(`Already aligned on ${what}`); return; }
  gizmo.record({ redo: () => gizmo.applyMatrices(targets, after), undo: () => gizmo.applyMatrices(targets, before) });
  flashHint(`Aligned ${plural(units.length - 1, 'piece')} with ${unitName(ref)} on ${what} · Ctrl+Z undoes it`);
}

// Lights (private/plans/done/editor-lights-plan.md, 4.6). Each light with a place (point and spot lights: placed, generated area,
// toggleable, a streamed level's) is a root of its own in lightRoots: a marker, picked on screen ahead of the piece
// behind it, moved and turned by the gizmo with pieces (allRoots), and changed in the panel's light section. A root
// keeps its values in the package's terms (plan 9.1) now (`values`) and as exported or placed (`baseValues`).
// Generated area lights are never edited: they follow their glowing piece (deriveAreaLights), which the export's
// matcher found or the project binds (areaBindings). Lights never join a group; a lamp and its light can still be
// selected together and moved in one move.
const AREA_SHOWN = 'workshop.areaLights', SKY_SHOWN = 'workshop.sunSky', REACH_SHOWN = 'workshop.lightReach';
const PL = 'TheWorld.PersistentLevel.';
let lightsShown = false, areaShown = recall(AREA_SHOWN) === '1';
let reachShown = recall(REACH_SHOWN) === '1';   // the selected light's reach outlined (View options; off at first)
let soloOn = false, lightsDirty = true, lastLightSync = 0, assigning = null, warnedLights = false;
let fixedLights = [], derivedCopies = [], ownerIndex = null, paintedLights = new Set();
let handleDefs = [], handleHover = null, lightDrag = null;   // the selected light's drag handles (below commitColour)
// area light actor path -> its glowing piece as the project sets it ({ target, component }), or null: kept fixed
let areaBindings = new Map();
const lightIndex = new Map();     // an original light's key (package|level|actor) -> its root
const derivedMarks = new THREE.Group(); world.add(derivedMarks);
const lightShapes = new THREE.Group(); world.add(lightShapes);
const solo = createSolo(world);
const LIGHT_LIMITS = { brightness: [0, 100], radius: [1, 16384], falloffExponent: [0.1, 64], innerConeAngle: [0, 89], outerConeAngle: [0, 89.99] };
const LIGHT_LABELS = { brightness: 'Brightness', radius: 'Radius', falloffExponent: 'Falloff', innerConeAngle: 'The inner cone',
                       outerConeAngle: 'The outer cone' };
const REACH_WARN = 300;
const isLightRoot = r => Boolean(r?.userData.light);
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
  paintLight(root); lightsDirty = true;
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
  lightsOn = on;
  syncLights();
  if (on) flashHint('Lights view: only lights are selected · Shift+L leaves it');
}
// The Normal button's Lights switch: the lights drawn and picked with pieces in the normal view.
function setNormalLights(on) {
  normalLights = Boolean(on) && Boolean(data);
  syncLights();
}
// The normal view: out of the Buildings view, the Lights view, the Landing zones view and the Effects view.
function setNormalView() {
  if (volumesOn) setVolumesShown(false);
  if (lightsOn) setLightsShown(false);
  if (zonesOn) setZonesShown(false);
  if (effectsOn) setEffectsShown(false);
  if (spawnsOn) setSpawnsShown(false);
}
// The Landing zones view (Shift+Z): the zones shown and drawn over everything (under a floor, inside a piece), and a
// click picks a zone or lets the picked one go, never a piece or a light. The zones' layer is put back as it was after.
function setZonesShown(on) {
  on = Boolean(on) && Boolean(data) && data.scope === 'map' && !data.preview && !builderMode;
  if (on === zonesOn) return;
  if (on) {
    if (spawnsOn) setSpawnsShown(false);      // (first: it puts the zones' layer back as it was)
    if (volumesOn) setVolumesShown(false);
    if (lightsOn) setLightsShown(false);
    if (effectsOn) setEffectsShown(false);
    stopPickBox(); select(null);
    zonesHidBefore = !landingLayer.visible;
    landingLayer.visible = true;
  } else {
    pickedZone = null;
    stopZonePlacing();      // a zone asked for from the Add panel and not placed yet goes with its view
    if (zonesHidBefore) landingLayer.visible = false;
  }
  zonesOn = on;
  refreshLandingZones(); lightButton();
  if (on) flashHint('Landing zones view: only landing zones are selected · Shift+Z leaves it');
}
// After a view or a switch changed: whether lights are drawn, what stays selected, the buttons.
function syncLights() {
  lightsShown = lightsOn || (normalLights && !volumesOn);
  if (volumesOn || lightsOn || !boxesShown) { ownSet.clear(); if (!volumesOn) ownPicked = null; }
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
  derivedCopies = [];
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
  lightsDirty = true;
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
  assigning = null; $('lightAssign').classList.remove('on');
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
  soloOn = Boolean(on) && soloRoots().length > 0;
  if (on && !soloOn) flashHint('Select a light to solo it');
  updateSolo();
}
function updateSolo() {
  const targets = soloOn ? soloRoots() : [];
  if (soloOn && !targets.length) soloOn = false;
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
let shapeKey = '', reachKey = '', reachLines = null, reachNow = null;
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
    reachKey = key; reachNow = null;
    if (root && root.visible && !dragging) {
      reachNow = lightReach(root);
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
const HANDLE_PICK = 10;
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
// Screen positions (client pixels) for points in the view, or null behind the camera.
function projector() {
  const rect = renderer.domElement.getBoundingClientRect(), p = new THREE.Vector3();
  return v => {
    p.copy(v).project(camera);
    if (p.z < -1 || p.z > 1) return null;
    return [rect.left + (p.x + 1) / 2 * rect.width, rect.top + (1 - p.y) / 2 * rect.height];
  };
}
// Each frame: the handles where the selected light's shapes are (they lean to the camera's right).
function updateLightHandles() {
  const root = lightDrag?.root ?? handleRoot();
  handleDefs = !root ? [] : root.userData.effect ? effectHandles(root, lightDrag?.side ?? cameraSide())
    : lightHandles(root.userData.source.kind, root.userData.values, root.matrix, lightDrag?.side ?? cameraSide());
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
  lightDrag = { root, before: root.userData.effect ? structuredClone(root.userData.values ?? {}) : { ...root.userData.values },
                side: cameraSide(), start: [e.clientX, e.clientY], pointerId: e.pointerId,
                near, handle, offset: handle ? [handle.s[0] - e.clientX, handle.s[1] - e.clientY] : null };
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
  lightDrag = null;
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
    ({ source, values } = recipeLight({ kind, version: families.lightRecipes[kind].latest }, null, [0, 0, 0], kind === 'spot' ? [-16384, 0, 0] : [0, 0, 0]));
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
// The piece list's Landing zones kind: one entry, placed with a click (the one way to add a zone)
function zoneEntries() {
  if (!data || data.scope !== 'map' || data.preview || builderMode) return [];
  const count = zonesNow().length;
  return [{ key: 'zone', id: 'zone-new', zone: true, name: 'Landing zone', kind: 'Landing zones', pkg: 'where the squad lands',
            detail: 'Placed on a tile, facing north; moved and turned with its gizmo', count, builds: true,
            title: 'A new landing zone: click the tile it is to stand on. It starts as a copy of the first zone\'s kind, facing north, and is used by Long War (tick Plain EW in its panel for plain Enemy Within)',
            sources: [], pivotIndex: 0, materials: [], milestone: 1, role: null, size: [0, 0, 0], extent: 0, mesh: '',
            text: 'landing zone lz drop zone skyranger squad start spawn evac' }];
}
// The piece list's Spawn points kind (the user, 18 November 2026: new spawns from the Add panel too): a Pod and a Meld
// point, each placed with a click as a copy of the map's first plain pod or first Meld point (SP7's copies: the Build
// clones the template, a pod with a pod index of its own), where the spawn family builds
function spawnAddEntries() {
  if (!spawnsAvailable() || !spawnFamilyBuilds()) return [];
  const out = [];
  for (const kind of SPAWN_COPY_KINDS) {
    const template = addTemplate(data.spawns, kind);
    if (!template) continue;
    const name = KINDS[kind].label, of = short(template.actor), volume = kind === 'noSpawn';
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
const pieceRecipes = () => [...lightEntries(), ...coverEntries(), ...wallEntries(), ...zoneEntries(), ...spawnAddEntries()];
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
  actor ??= `${recipe ? `${PL}${recipe.kind === 'point' ? 'PointLight' : 'SpotLight'}` : from.actor}_copy${++copySerial}`;
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
      if (o.added.template) added.set(o.actor, { id: o.added.entity, actor: o.actor, template: { ...o.added.template }, ...pose, light: { ...root.userData.values } });
      else {
        const light = changedValues(root.userData.values, o.added.templateValues);
        added.set(o.actor, { id: o.added.entity, actor: o.actor, from: o.added.from, components: [o.added.component], ...pose,
                             ...(Object.keys(light).length ? { light } : {}) });
      }
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
  areaBindings = new Map();
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
  const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
  if (serial > copySerial) copySerial = serial;
  let source, values;
  if (entity.template) {
    const made = recipeLight(entity.template, entity.light, entity.location, entity.rotation, entity.actor);
    if (!made) return null;
    ({ source, values } = made);
  } else {
    const template = lightIndex.get(targetKey(entity.from))?.userData.source;
    if (!template || entity.components?.[0] !== template.component) return null;
    source = template; values = { ...valuesOf(template), ...(entity.light ?? {}) };
  }
  const root = addedLight(source, actorMatrix(entity.location, entity.rotation), values, entity.actor);
  const o = root.userData.source;
  Object.assign(o, { location: entity.location, rotation: entity.rotation });
  o.added.entity = entity.id;
  return root;
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
// Prepare: an export older than what lights and builds need (families.json's exportProblem) exported again (POST
// /maps/<id>/export with prepare), then the page reopened. A dialog in the middle of the window asks: when the map
// opens, before a build or a play of a project, and from a build that failed for want of it (its Prepare the map
// button, which starts it at once). Later leaves a banner with the same offer. 'update': the map's export is older
// than this editor's exporter, so it is prepared again at once when it opens (an update's drawing fixes, export 19).
let exportProblem = null, preparing = false;
const prepareWhy = {
  open: 'is older than what editing lights and building need',
  build: 'is older than a build needs, so the project can\'t be built yet',
  failed: 'is older than the build needs, which is why it stopped',
};
function showPrepare(why = 'open', start = false) {
  const els = { root: $('prepareModal'), title: $('prepareTitle'), note: $('prepareNote'), bar: $('prepareBar'), status: $('prepareStatus'),
                ok: $('prepareOk'), later: $('prepareLater'), close: $('prepareClose') };
  const label = mapLabel(activeMapId);
  const hide = () => { els.root.hidden = true; };
  const update = why === 'update';
  const later = () => {
    if (preparing) return;
    hide();
    if (update) banner(`Map schema updated: ${label} wasn't re-exported, so some pieces may draw wrong.`,
                       [['Re-export', () => showPrepare('update')]]);
    else banner(`${label}'s copy in the editor is older than what editing lights and building need. Prepare it again (about half a minute; projects and edits are kept).`,
                [['Prepare now', () => showPrepare('open')]]);
  };
  const progress = fraction => {
    els.bar.hidden = false;
    els.bar.className = `buildbar${fraction == null ? ' indeterminate' : ''}`;
    els.bar.firstElementChild.style.width = `${(100 * (fraction ?? 0.3)).toFixed(1)}%`;
  };
  async function run() {
    if (preparing) return;
    preparing = true;
    els.ok.disabled = true; els.ok.textContent = update ? 'Re-exporting…' : 'Preparing…'; els.later.hidden = els.close.hidden = true;
    const reading = update ? 'Re-exporting' : 'Reading the map from the game again';
    els.status.textContent = `${reading}: about half a minute…`;
    progress(null);
    const at = `/maps/${encodeURIComponent(activeMapId)}/export`;
    try {
      const started = await fetch(at, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prepare: true }) });
      if (!started.ok) throw Error((await started.json().catch(() => ({}))).error || `the server said ${started.status}`);
      for (;;) {
        await new Promise(done => setTimeout(done, 1500));
        const s = await (await fetch(`${at}.json`)).json();
        if (s.state === 'failed') throw Error(s.error || 'the export failed');
        if (s.state === 'ready') { els.status.textContent = update ? 'Re-exported: opening it…' : 'Prepared: opening it again…'; progress(1); location.reload(); return; }
        if (s.progress) { progress(s.progress.fraction); els.status.textContent = `${reading}: ${Math.round(s.progress.fraction * 100)}%…`; }
      }
    } catch (e) {
      preparing = false;
      els.bar.hidden = true;
      els.status.textContent = `${label} could not be ${update ? 're-exported' : 'prepared'}: ${e.message}`;
      els.ok.disabled = false; els.ok.textContent = 'Try again'; els.later.hidden = els.close.hidden = false;
    }
  }
  els.title.textContent = update ? label : `${label} needs preparing again`;
  els.note.textContent = update
    ? 'Map schema updated. Re-exporting.'
    : `The editor's copy of ${label} ${prepareWhy[why] ?? prepareWhy.open}. Preparing reads the map from the game again, which takes about half a minute, and opens it afresh. Your projects are kept, and so are edits not saved yet.`;
  els.ok.textContent = update ? 'Re-export' : 'Prepare now'; els.ok.disabled = false;
  els.later.hidden = els.close.hidden = false;
  els.bar.hidden = true; els.status.textContent = '';
  els.ok.onclick = run; els.later.onclick = els.close.onclick = later;
  els.root.onkeydown = e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); later(); } };
  els.root.hidden = false;
  showPop(null);
  if (start) run(); else setTimeout(() => els.ok.focus(), 0);
}
// A build or a play of a project waits for the map to be prepared: true when the dialog was shown instead.
function needsPrepare() {
  if (!exportProblem) return false;
  showPrepare('build');
  return true;
}

// The prefab builder uses the same roots, history and tools, with a complete document
// instead of a delta against a map. Missing pieces remain members of that document.
const physicalBoxes = new WeakMap();
function physicalBox(root) {
  if (root.userData.light) { const p = lightPose(root).location; return [...p, ...p]; }
  if (root.userData.volume) return volumeBox(root);
  if (root.userData.effect) return null;
  const key = root.matrix.elements.join(',') + ':' + root.userData.source.mesh;
  if (physicalBoxes.get(root)?.key === key) return physicalBoxes.get(root).box;
  const b = boxOf(root, true), box = b ? [b[0], b[2], b[4], b[1], b[3], b[5]] : null;
  physicalBoxes.set(root, { key, box }); return box;
}
const PIECE_FIELDS = new Set(['actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner', 'tinted', 'recipe', 'template', 'light', 'cover', 'id', 'flags',
                              'kind', 'effect', 'sound']);
function builderDocument() {
  if (!eventMemo) return builderDocumentNow();
  return eventMemo.document ??= builderDocumentNow();
}
function builderDocumentNow() {
  const state = editState(), known = state.added.map(({ id, ...p }) => {
    const original = builder.metadata.get(p.actor);
    // (a field of a newer editor's, which this one doesn't know, is carried as the file had it: prefabs.py `carried`)
    const carried = original ? Object.fromEntries(Object.entries(original).filter(([k]) => !PIECE_FIELDS.has(k))) : {};
    return { ...carried, ...p, ...(p.from && original?.recipe && !p.recipe ? { recipe: original.recipe } : {}) };
  });
  const pieces = [...known, ...builder.kept].sort((a, b) => a.actor.localeCompare(b.actor));
  const reconciled = reconcilePrefab(pieces, state.buildings, [...groups.values()].map(g => ({ ...g, members: [...g.members.values()] })));
  const donors = new Map((builder.doc?.donors ?? []).map(d => [d.package.toLowerCase(), d]));
  for (const p of pieces) if (p.from && !donors.has(p.from.package.toLowerCase())) {
    const sha256 = donorHashes.get(p.from.package.toLowerCase());
    donors.set(p.from.package.toLowerCase(), { package: p.from.package, ...(sha256 ? { sha256 } : {}) });
  }
  const used = new Set(pieces.filter(p => p.from).map(p => p.from.package.toLowerCase()));
  return { ...builder.doc, pieces: reconciled.pieces, groups: reconciled.groups, buildings: state.buildings,
    donors: [...donors].filter(([key]) => used.has(key)).map(([, d]) => d).sort((a, b) => a.package.localeCompare(b.package)) };
}
function builderKey() {
  if (eventMemo?.key) return eventMemo.key;
  const { pieces, groups, buildings, donors } = builderDocument();
  const key = JSON.stringify({ pieces, groups, buildings, donors, envelope: builder.envelope });
  if (eventMemo) eventMemo.key = key;
  return key;
}
function builderBounds() {
  const boxes = [...allRoots.values()].filter(r => !r.userData.deleted).map(r => [rootName(r), physicalBox(r)]).filter(([, b]) => b);
  for (const p of builder.kept) if (['point', 'spot'].includes(p.template?.kind) || (p.kind && !p.template)) boxes.push([p.actor, [...p.location, ...p.location]]);
  // (an effect, a sound or a lens flare is where it stands)
  for (const r of effectRoots.values()) {
    if (r.userData.deleted || !r.userData.source.added) continue;
    const p = actorPose(r.userData.source, r.matrix).location;
    boxes.push([short(r.userData.source.actor), [...p, ...p]]);
  }
  return boxes;
}
function builderRecords() {
  const doc = builderDocument(), clip = snapshot([...allRoots.values()], new Set()) ?? { entries: [], volumes: [], name: doc.name };
  const records = normalizePrefab(doc, builderBounds(), { envelope: builder.envelope, unknown: builder.kept.filter(p => !p.kind || p.template).map(p => p.actor) });
  const lights = records.pieces.filter(p => ['point', 'spot'].includes(p.template?.kind)).length;
  const [effects, sounds, flares] = ['effect', 'sound', 'flare'].map(kind => records.pieces.filter(p => !p.template && p.kind === kind).length);
  const b = records.size.bounds;
  return { ...records, clip, left: [], offGrid: [...roots.values()].filter(r => gridNow(r)?.valid === false).map(rootName),
    counts: { pieces: records.pieces.length - lights - effects - sounds - flares, lights, effects, sounds, flares, buildings: records.buildings.length, tiles: records.tiles },
    box: new THREE.Box3(new THREE.Vector3(b[0], b[2], b[1]), new THREE.Vector3(b[3], b[5], b[4])) };
}
// Align to grid (the builder's warning, prefab plan 5.6b): the pieces keeping the pose rule (doors, ladders, cars, vans,
// fracturing pieces) that stand off their grid, and the one smallest shift of the whole prefab that puts every such
// piece on it: each off piece's nearest whole tile and level (poserule.js nearestGridPose), the least of those that
// suits them all. { off: [{ root, name }], delta, pivot (a root id) } or, with no such shift, turned (pieces a shift
// can't help: turned off quarter turns, or pitched) or clash (no one shift suits them all).
function gridAlignment() {
  const origin = gridOrigin(), ruled = [];
  if (!origin) return { off: [] };
  for (const [id, r] of roots) {
    if (r.userData.deleted || isStream(r.userData.source) || r.userData.light) continue;
    const from = recipeOf(r.userData.source);
    if (!from) continue;
    const pose = actorPose(r.userData.source, r.matrix);
    ruled.push({ id, r, from, pose, move: gridMove(from.location, from.rotation, pose.location, pose.rotation, origin) });
  }
  const off = ruled.filter(p => !p.move.valid);
  const named = [...new Map(off.map(p => [rootName(p.r), { root: p.r, id: p.id, name: rootName(p.r) }])).values()];
  if (!off.length) return { off: [] };
  const turned = named.filter(n => off.some(p => p.r === n.root && p.move.why.some(w => w === 'pitch or roll' || w === 'quarter turns')));
  if (turned.length) return { off: named, turned };
  const suits = d => ruled.every(p => gridMove(p.from.location, p.from.rotation, p.pose.location.map((v, k) => v + d[k]), p.pose.rotation, origin).valid);
  const best = off.map(p => ({ p, delta: nearestGridPose(p.from.location, p.from.rotation, p.pose.location, p.pose.rotation, origin)
    .location.map((v, k) => Number((v - p.pose.location[k]).toFixed(4))) }))
    .sort((a, b) => Math.hypot(...a.delta) - Math.hypot(...b.delta)).find(c => suits(c.delta));
  return best ? { off: named, delta: best.delta, pivot: best.p.id } : { off: named, clash: true };
}
// The shift made: everything of the prefab (pieces, lights, floor boxes) moved as one, one undo step; the selection
// is given back.
function alignToGrid() {
  const plan = gridAlignment();
  if (!plan.delta || builder.kept.length || gizmo.controls.dragging) return false;
  const before = gizmo.picks();
  const ids = [roots, lightRoots, volumeRoots].flatMap(m => [...m].filter(([, r]) => !r.userData.deleted).map(([id]) => id));
  gizmo.setSelection(ids, plan.pivot);
  const pose = gizmo.pose();
  if (pose) gizmo.setPose(pose.location.map((v, k) => v + plan.delta[k]), null);
  gizmo.setSelection(before.ids.filter(id => allRoots.has(id)), before.active);
  editChanged();
  flashHint(`Moved the prefab ${shiftWords(plan.delta)}: every door, ladder and fracturing piece is on the grid`);
  return Boolean(pose);
}
const shiftWords = d => [['east', 'west'], ['south', 'north'], ['up', 'down']]
  .map(([plus, minus], k) => Math.abs(d[k]) > 0.005 ? `${Math.abs(Number(d[k].toFixed(2)))} ${d[k] > 0 ? plus : minus}` : '')
  .filter(Boolean).join(', ') || 'nowhere';
// The warning over the size: what stands off the grid, Show (select those pieces) and Align to grid.
function gridWarning() {
  const plan = gridAlignment(), box = $('gridWarning');
  box.hidden = !plan.off.length;
  if (box.hidden) return;
  const names = plan.off.map(n => n.name);
  $('gridWarningText').textContent = `${plural(names.length, 'piece')} off the tile grid: ${names.slice(0, 3).join(', ')}`
    + `${names.length > 3 ? ' …' : ''}`;
  const why = builder.kept.length ? 'Some pieces could not be read: align once they can, so they move too.'
    : plan.turned ? `${plan.turned.map(n => n.name).join(', ')} ${plan.turned.length === 1 ? 'is' : 'are'} turned off quarter turns or tilted: turn ${plan.turned.length === 1 ? 'it' : 'them'} first (Show selects ${plan.turned.length === 1 ? 'it' : 'them'}).`
    : plan.clash ? 'No single shift puts them all on the grid: move them apart from each other first (Show selects them).'
    : `Align to grid moves the whole prefab ${shiftWords(plan.delta)}, the nearest place where they all are.`;
  box.title = 'Doors, ladders, cars, vans and fracturing pieces keep to the tile grid: whole tiles (96) and levels (64) from '
    + 'where their originals stand. Off it they build where they stand, and the Build and Test in game say so. ' + why;
  $('gridAlign').disabled = !plan.delta || builder.kept.length > 0;
  $('gridAlign').title = plan.delta && !builder.kept.length ? `Moves everything ${shiftWords(plan.delta)} as one: one undo step` : why;
}
$('gridAlign').onclick = () => { alignToGrid(); };
$('gridShow').onclick = () => {
  const plan = gridAlignment(), ids = (plan.turned ?? plan.off).map(n => n.id);
  if (!ids.length) return;
  gizmo.setSelection(ids, ids[0]); editChanged(); frame(roots.get(ids[0]));
};
const builderGround = new THREE.Group(); world.add(builderGround);
let builderGroundKey = '';
function refreshBuilder() {
  if (!builderMode || builder.loading || !data) return;
  const records = builderRecords(), { size } = records, b = size.bounds;
  $('prefabRecover').hidden = !records.pieces.some(p => p.from && !p.kind);
  $('prefabRecover').disabled = builder.repairing;
  $('builderSize').textContent = `${size.tiles[0]} × ${size.tiles[1]} tiles · height ${b[2].toFixed(0)}–${b[5].toFixed(0)}, grid 0–${PREFAB_GRID_TOP}`
    + (size.warnings.length ? ' · larger than a map holds' : size.unknown.length ? ' · size unverified: missing pieces kept'
      : size.outside.length ? ' · sticks out of the grid' : '');
  $('builderSize').title = [...size.warnings.map(w => `${w}. It is saved and placed all the same.`),
    `A map is at most ${PREFAB_TILES} by ${PREFAB_TILES} tiles; the tile grid is 0 to ${PREFAB_GRID_TOP} units high (${PREFAB_GRID_LEVELS} levels), `
    + `and anything may stick out to ${PREFAB_MIN_Z} under it and ${PREFAB_MAX_Z} over it, roofs and floor boxes `
    + 'included. Out of the grid there are no tiles: nothing can be stood on there or give cover.',
    size.outside.length ? `Out of the grid: ${size.outside.slice(0, 8).join(', ')}${size.outside.length > 8 ? ' …' : ''}.` : ''].filter(Boolean).join('\n');
  $('builderSize').classList.toggle('warn', size.warnings.length > 0 || !size.verified);
  gridWarning();
  const lo = [0, 1].map(k => Math.floor((Math.min(-576, b[k], controls.target[k ? 'z' : 'x'] - 576) - 192) / 96) * 96);
  const hi = [0, 1].map(k => Math.ceil((Math.max(576, b[k + 3], controls.target[k ? 'z' : 'x'] + 576) + 192) / 96) * 96);
  const key = [...lo, ...hi, ...size.origin, ...size.tiles, size.warnings.length].join(',');
  if (key === builderGroundKey) return;
  builderGroundKey = key;
  for (const child of [...builderGround.children]) { child.geometry.dispose(); child.material.dispose(); builderGround.remove(child); }
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(hi[0] - lo[0], hi[1] - lo[1]).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0x778c91, transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide }));
  plane.position.set((hi[0] + lo[0]) / 2, -0.2, (hi[1] + lo[1]) / 2); builderGround.add(plane);
  const lines = [], line = (x, y, X, Y) => lines.push(x, 0, y, X, 0, Y);
  // Bound drawing cost even when repairing a very large legacy prefab.
  const step = Math.max(96, Math.ceil(Math.max(hi[0] - lo[0], hi[1] - lo[1]) / (256 * 96)) * 96);
  for (let x = lo[0]; x <= hi[0]; x += step) line(x, lo[1], x, hi[1]);
  for (let y = lo[1]; y <= hi[1]; y += step) line(lo[0], y, hi[0], y);
  builderGround.add(new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(lines, 3)),
    new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.14 })));
  const [x, y] = size.origin, [nx, ny] = size.tiles;
  const outline = [x, 0.4, y, x + nx * 96, 0.4, y, x + nx * 96, 0.4, y + ny * 96, x, 0.4, y + ny * 96, x, 0.4, y];
  builderGround.add(new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(outline, 3)),
    new THREE.LineBasicMaterial({ color: size.warnings.length ? 0xef9979 : 0x82d5ce })));
  for (const child of builderGround.children) child.raycast = () => {};
}
async function applyPrefabDocument(doc, { envelope = null, nextSerial = 0 } = {}, progress = null) {
  builder.loading = true;
  builder.metadata = new Map(doc.pieces.map(p => [p.actor, structuredClone(p)]));
  for (const d of doc.donors ?? []) if (d.sha256) donorHashes.set(d.package.toLowerCase(), d.sha256);
  // Reserve names and link serials even when none of their pieces can be displayed.
  for (const p of doc.pieces) for (const s of [/_copy(\d+)$/.exec(p.actor)?.[1], /^copy(\d+):/.exec(p.prefab ?? '')?.[1]]) nextSerial = Math.max(nextSerial, Number(s) || 0);
  builder.kept = doc.pieces;
  const carried = await applyState({ overrides: [], added: doc.pieces.map(p => ({ ...p, id: p.actor })), groups: doc.groups ?? [], buildings: doc.buildings ?? [], nextSerial }, progress);
  builder.kept = carried.added.map(({ id, ...p }) => p);
  builder.envelope = builder.kept.length ? envelope ?? [0, 0, 0, doc.floor.tiles[0] * 96, doc.floor.tiles[1] * 96, 0] : null;
  builder.loading = false;
  refreshBuilder(); editChanged();
}
async function openPrefabDocument(id) {
  // the loading overlay while a saved prefab is read and its pieces made (those of other maps are read from them)
  if (id !== 'new') { $('loading').hidden = false; loadingState('Opening the prefab…'); }
  try {
    builder.doc = id === 'new' ? newPrefab(uuid(), 'Untitled prefab', { tiles: [1, 1], pieces: [], groups: [], buildings: [], donors: [] }) : await prefabApi.load(id);
    if (id !== 'new') loadingState(`Opening ${builder.doc.name}: reading its ${plural(builder.doc.pieces.length, 'piece')}…`, 0);
    await applyPrefabDocument(builder.doc, {}, openingProgress(builder.doc.name));
  } finally { $('loading').hidden = true; }
  builder.savedKey = builderKey();
  Object.assign(problems, { result: null, error: null, key: null, open: false });
  builderTitle(); frame(); editChanged();     // (the status was drawn while loading, before the saved state was known)
  if (id === 'new') return;
  checkPrefab();
  const recovery = await prefabApi.recovery(id).catch(() => null);
  const missing = builder.kept.length;
  if (recovery?.document) banner(`Unsaved changes to ${builder.doc.name} from ${savedWhen(recovery.savedAt)} were kept.` +
    (missing ? ` The saved version has ${plural(missing, 'missing piece')}. Choose which version to open before looking for sources.` : ''), [
    ['Restore them', async () => {
      builder.doc.donors = recovery.document.donors;
      await applyPrefabDocument(recovery.document, recovery);
      recoveryKept = true; projectChanged();
      await recoverOpenedPrefabSources();
    }],
    ['Discard them', async () => { await clearDocumentRecovery(); await recoverOpenedPrefabSources(); }],
  ]);
  else await recoverOpenedPrefabSources();
}

function prefabSourceNotice(repaired, unresolved = [], error = '') {
  const missing = new Map(builder.kept.map(p => [p.actor, p.from && !p.recipe ? 'No recipe was saved.' : 'Could not load its source.']));
  for (const p of unresolved) missing.set(p.actor, p.reason);
  const messages = [];
  if (repaired) messages.push(`Recovered ${plural(repaired, 'piece')} by recipe. Save to keep the new sources.`);
  if (error) messages.push(`Could not look up prefab sources: ${error}`);
  if (missing.size) {
    const names = [...missing].slice(0, 3).map(([actor, reason]) => `${short(actor)}: ${reason}`);
    messages.push(`${plural(missing.size, 'piece')} still missing. ${names.join(' ')}${missing.size > names.length ? ` And ${missing.size - names.length} more.` : ''}`);
  }
  banner(messages.join(' ') || 'All prefab sources are available.');
}

async function recoverOpenedPrefabSources() {
  if (!builder.kept.length) return;
  if (builder.kept.some(p => p.from && p.recipe)) await recoverPrefabSources();
  else prefabSourceNotice(0);
}

async function recoverPrefabSources() {
  if (!builderMode || builder.loading || builder.repairing || saving || gizmo.controls.dragging) return;
  const before = builderKey(), doc = builderDocument();
  builder.repairing = $('prefabRecover').disabled = true;
  flashHint('Looking for the missing pieces in the map catalogue…');
  try {
    const result = await prefabApi.recoverSources(doc);
    const repaired = new Set(result.repaired);
    if (!repaired.size) {
      prefabSourceNotice(0, result.unresolved);
      return;
    }
    const replacements = result.document.pieces.filter(p => repaired.has(p.actor));
    const hashes = new Map(result.document.donors.map(d => [d.package.toLowerCase(), d.sha256]));
    const made = await Promise.all(replacements.flatMap(p => p.components.map(async component => {
      const { record } = await libraryTemplate(p.from);
      if (record.source.sha256 !== hashes.get(p.from.package.toLowerCase()))
        throw Error('The game package changed while this prefab was open. Reopen the prefab and try again.');
      const source = templateFor(p.from, component);
      if (!source) throw Error(`Could not load ${short(p.actor)} from ${p.from.package}.`);
      return buildRoot(addedObject(source, movedMatrix(source, p.location, p.rotation), { ...p, entity: p.actor }));
    })));
    if (before !== builderKey() || saving || gizmo.controls.dragging) throw Error('The prefab changed during the search. Try again.');
    const old = [...roots.values()].filter(r => repaired.has(r.userData.source.actor));
    const picks = gizmo.picks(), removed = new Set(old.map(r => r.userData.source.id));
    const kept = builder.kept, envelope = builder.envelope, metadata = builder.metadata, donors = builder.doc.donors;
    const remaining = kept.filter(p => !repaired.has(p.actor));
    const updated = new Map(metadata);
    for (const p of replacements) updated.set(p.actor, p);
    gizmo.record({
      redo() {
        removeRoots(old); addRoots(made);
        Object.assign(builder, { kept: remaining, envelope: remaining.length ? envelope : null, metadata: updated });
        builder.doc.donors = result.document.donors;
        gizmo.setSelection(picks.ids.filter(id => !removed.has(id)), removed.has(picks.active) ? null : picks.active);
        sceneChanged();
      },
      undo() {
        removeRoots(made); addRoots(old);
        Object.assign(builder, { kept, envelope, metadata });
        builder.doc.donors = donors;
        gizmo.setSelection(picks.ids, picks.active);
        sceneChanged();
      },
    });
    prefabSourceNotice(repaired.size, result.unresolved);
  } catch (error) {
    prefabSourceNotice(0, [], error.message);
  } finally {
    builder.repairing = false;
    refreshBuilder();
  }
}

function builderTitle() {
  $('projectTitle').textContent = builder.doc?.name ?? 'Untitled prefab';
  $('mapTitle').textContent = builder.doc?.name ?? 'New prefab';
  document.title = `${builder.doc?.name ?? 'New prefab'} · Prefab · XCOM Map Workshop`;
  $('projectButton').classList.toggle('unsaved', dirty());
}
async function saveBuilder({ name = null, replace = null } = {}) {
  if (saving || builder.loading || gizmo.controls.dragging) return false;
  if (!name && !builder.doc.revision) return showPrefabDialog(true);
  saving = true; clearTimeout(recoveryTimer);
  try {
    await documentWrites.wait();
    const records = prefabRecords({ complete: true }), before = builderKey(), previous = builder.doc.id;
    if (!records.pieces.length && !records.buildings.length) throw Error('The prefab is empty. Add a piece, light or floor box first.');
    if (!records.size.supported) throw Error(records.size.errors.join('; '));
    const target = name ? replace : builder.doc, id = target?.id ?? uuid();
    const doc = newPrefab(id, name ?? builder.doc.name, records);
    if (target?.created) doc.created = target.created;
    else if (replace) doc.created = (await prefabApi.load(id)).created;
    const result = await prefabApi.save(id, doc, target?.revision ?? 0);
    if (previous !== id) await prefabApi.dropRecovery(previous);
    const withRecipes = list => list.map(p => result.recipes?.[p.actor] ? { ...p, recipe: result.recipes[p.actor] } : p);
    const baseline = JSON.parse(before);
    baseline.pieces = withRecipes(baseline.pieces);
    builder.doc = { ...doc, pieces: withRecipes(doc.pieces), revision: result.revision, created: result.created, savedAt: result.savedAt };
    builder.savedKey = JSON.stringify(baseline); recoveryKept = false;
    setTimeout(checkPrefab, 0);
    builder.metadata = new Map(withRecipes(records.pieces).map(p => [p.actor, structuredClone(p)]));
    history.replaceState(null, '', `?prefab=${encodeURIComponent(id)}`);
    prefabPictures.push({ id, entries: records.clip.entries, volumes: records.clip.volumes, box: records.box });
    prefabTab.refresh(); builderTitle();
    flashHint(`Saved ${doc.name} · revision ${result.revision}${!result.size?.verified ? ' · size unverified: missing pieces kept' : ''}`);
    return true;
  } catch (error) {
    if (error.status === 409 && Number.isInteger(error.detail?.revision) && !name) banner(`${builder.doc.name} was saved elsewhere (revision ${error.detail.revision}).`, [
      ['Overwrite it with this', () => { builder.doc.revision = error.detail.revision; saveBuilder(); }],
      ['Open the saved one', () => discardAndGo({ prefab: builder.doc.id })],
    ]);
    else banner(`Not saved: ${error.message}`);
    return false;
  } finally { saving = false; projectChanged(); }
}
async function clearDocumentRecovery() {
  clearTimeout(recoveryTimer);
  const id = builderMode ? builder.doc?.id : project?.doc.id, api = builderMode ? prefabApi : projectApi;
  await documentWrites.run(async () => { if (id) await api.dropRecovery(id); });
  recoveryKept = false;
}
async function discardAndGo(change) {
  await clearDocumentRecovery(); leaving = true; navigate(change);
}
function askLeave() {
  return new Promise(resolve => {
    const modal = $('leaveDialog'); modal.hidden = false;
    $('leaveName').textContent = `Save changes to ${builderMode ? builder.doc.name : project?.doc.name ?? 'this map'} before opening something else?`;
    const done = value => { modal.hidden = true; resolve(value); };
    $('leaveSave').onclick = () => done('save'); $('leaveDiscard').onclick = () => done('discard'); $('leaveCancel').onclick = () => done('cancel');
    modal.onkeydown = e => { e.stopPropagation(); if (e.key === 'Escape') done('cancel'); };
    $('leaveCancel').focus();
  });
}
// Projects: the edits saved, reopened and recovered (first-editor plan E1; project.js, research/editor-contracts.md).
// The scene holds the state; a project records it against the map as exported, and replays it onto the map.
let project = null;   // { doc, revision, carried: {overrides, added} kept as they were, savedKey }
let templates = null, recoveryTimer = null, recoveryKept = false, saving = false;
const sourceKey = o => targetKey({ package: o.sourcePackage, level: o.layer, actor: o.actor });
// Projects edit a full map's original layout: not a piece study or a patch preview.
const projectsAvailable = () => !builderMode && Boolean(data) && data.scope === 'map' && !data.preview;
// The edits on screen, as a project records them: overrides of original actors and added actors, sorted.
function editState() {
  if (!eventMemo) return editStateNow();
  return eventMemo.state ??= editStateNow();
}
function editStateNow() {
  const overrides = new Map(), added = new Map();
  for (const root of roots.values()) {
    const o = root.userData.source;
    if (o.added && o.cover) {      // a cover block: its recipe (a version that makes its type), size and cover, at its corner
      added.set(o.actor, { id: o.added.entity, actor: o.actor,
                           template: { ...o.added.template, version: coverVersion(o.added.template.version, o.cover.type) }, cover: { ...o.cover },
                           ...actorPose(o, root.matrix) });
    } else if (o.added) {
      let entity = added.get(o.actor);
      if (!entity) {
        entity = { id: o.added.entity, actor: o.actor, from: o.added.from, components: [], ...actorPose(o, root.matrix),
                   prefab: o.prefab ?? null, partner: o.partner ?? null };
        if (o.added.tinted) entity.tinted = true;
        if (o.added.generated) entity.generated = o.added.generated;
        if (root.userData.flags) entity.flags = { ...root.userData.flags };
        if (builderMode && builder.metadata.get(o.actor)?.recipe) entity.recipe = builder.metadata.get(o.actor).recipe;
        else if (builderMode && !builder.metadata.has(o.actor) && o.foreign?.key)
          entity.recipe = { key: o.foreign.key, name: library?.entry(o.foreign.key)?.name ?? short(data.meshes[o.mesh].name) };
        added.set(o.actor, entity);
      }
      entity.components.push(o.component);
    } else if ((root.userData.deleted || root.userData.edit || root.userData.flags) && !overrides.has(sourceKey(o))) {
      // (flags alone: an override with no pose, the piece where the map has it; a deleted piece has no flags)
      const target = { package: o.sourcePackage, level: o.layer, actor: o.actor };
      overrides.set(sourceKey(o), root.userData.deleted ? { target, deleted: true }
        : { target, ...(root.userData.edit ? actorPose(o, root.matrix) : {}), ...(root.userData.flags ? { flags: { ...root.userData.flags } } : {}) });
    }
  }
  for (const entity of added.values()) entity.components?.sort();
  const areaLightBindings = lightState(overrides, added);
  effectState(overrides, added);
  // A group keeps the pieces still on the map and the groups inside it; one left with fewer than two members isn't
  // saved (its last member takes its place in the group it was in).
  const saved = cloneGroups();
  for (const g of saved.values()) for (const [k, m] of [...g.members]) if (m.group === undefined && !liveMembers().has(k)
    && !(builderMode && builder.kept.some(p => memberKey({ added: p.actor }) === k))) g.members.delete(k);
  const kept = [...pruneGroups(saved).values()].map(g => ({ id: g.id, locked: g.locked, breakTogether: g.breakTogether, members: [...g.members.values()],
                                                             ...(g.prefab ? { prefab: g.prefab } : {}) }));
  return sortState({ overrides: [...overrides.values(), ...missionOverrides()], added: [...added.values(), ...spawnCopyRecords()], groups: kept, areaLightBindings, stage,
                    buildings: savedBuildings(), cleared, landingZones, clearKeepsOutside, missions: projectMissions,
                    spawnRules: projectSpawnRules });
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
  for (const r of all) { r.userData.deleted = false; r.userData.flags = null; }
  setGroups(new Map()); liveCache = null;
  clearLightEdits();
  clearEffectEdits();
  cleared = false; clearKeepsOutside = false; landingZones = null; mergedBuildings = null; projectMissions = null;
  projectSpawnRules = null; syncSpawnRule();
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
// Put a project state on the map: originals moved or deleted, copies added. Records naming pieces this export does
// not have are returned, to be kept and saved back unchanged; nothing is matched by short name.
const foreignNoted = new Set();
async function applyState(state, progress = null) {
  // pieces of other maps: their templates read first (a map the install lacks leaves its records carried)
  for (const message of await loadForeignTemplates(state.added, progress))
    if (!foreignNoted.has(message)) { foreignNoted.add(message); projectNote(`${message}: its copies are kept and saved back unchanged.`); }
  clearEdits();
  cleared = state.cleared === true; clearKeepsOutside = cleared && state.clearKeepsOutside === true; mergedBuildings = null;
  landingZones = Array.isArray(state.landingZones) ? state.landingZones.map(z => ({ ...z })) : null;
  projectMissions = Array.isArray(state.missions) ? state.missions.map(e => ({ ...e })) : null;
  projectSpawnRules = state.spawnRules ?? null; syncSpawnRule();
  setStage(validStage(state.stage, ownSize()?.dims) ? state.stage : null);
  clearedChanged();
  // (a record for a map building this export can't edit is kept and saved back unchanged)
  const unknownBuildings = setBuildings((state.buildings ?? []).filter(validBuilding));
  const actors = new Map(), carried = { overrides: [], added: [], groups: [], areaLightBindings: [], buildings: unknownBuildings };
  for (const r of roots.values()) {
    const key = sourceKey(r.userData.source);
    if (!actors.has(key)) actors.set(key, []);
    actors.get(key).push(r);
  }
  const streamMoves = new Map();
  for (const record of state.overrides) {
    if (record.target?.level === 'stream') {
      // a mission object moved in its stream (Part E): one of this export's, else carried unchanged
      const o = streamObjects(record.target.package).find(x => x.actor === record.target.actor);
      if (o && !record.deleted && Array.isArray(record.location) && Array.isArray(record.rotation))
        streamMoves.set(missionKey(record.target.package, o.actor), { stream: record.target.package, actor: o.actor,
                                                                      location: [...record.location], rotation: [...record.rotation] });
      else carried.overrides.push(record);
      continue;
    }
    // a base pod, Meld point or drop-in point moved, turned or given values (SP6); one the page doesn't take is
    // carried unchanged (below: no piece has its actor)
    if (record.target?.level === 'base' && String(record.target.package).toLowerCase() === String(data.name).toLowerCase()) {
      const o = baseSpawnOf(record.target.actor), entry = o ? spawnEntryOf(o, record) : null;
      if (entry) { streamMoves.set(missionKey(null, o.actor), entry); continue; }
    }
    if (applyLightRecord(record)) continue;
    if (applyEffectRecord(record)) continue;
    const list = actors.get(targetKey(record.target));
    if (!list) { carried.overrides.push(record); continue; }
    if (record.deleted) { for (const r of list) if (!r.userData.source.hidden && !r.userData.source.environment) r.userData.deleted = true; }
    else {
      if (record.location !== undefined) gizmo.applyMatrices(list, list.map(r => movedMatrix(r.userData.source, record.location, record.rotation)));
      if (record.flags) for (const r of list) r.userData.flags = { ...record.flags };
    }
  }
  const objs = [], lights = [], effects = [];
  for (const entity of state.added) {
    if (SPAWN_COPY_KINDS.includes(entity.kind)) {
      // a copy of one of the map's pods, Meld points or no-spawn volumes (SP7), or a new volume (no `from`); one the page
      // doesn't take is carried unchanged
      const from = entity.from, o = from?.level === 'base' && String(from.package).toLowerCase() === String(data.name).toLowerCase() ? baseSpawnOf(from.actor)
        : from === undefined && entity.kind === 'noSpawn' ? NEW_VOLUME : null;
      const entry = o ? copyEntryOf(o, entity) : null;
      if (entry) {
        streamMoves.set(spawnKey('copy', entry.actor), entry);
        const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
        if (serial > copySerial) copySerial = serial;
      } else carried.added.push(entity);
      continue;
    }
    if (entity.kind) {      // an effect, a sound or a flare copied (effects and sounds plan, Part C)
      const root = addedEffectOf(entity);
      if (root) effects.push(root); else carried.added.push(entity);
      continue;
    }
    if (entity.template?.kind === COVER_KIND) {
      const source = coverOf(entity);
      if (!source) { carried.added.push(entity); continue; }
      const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
      if (serial > copySerial) copySerial = serial;
      objs.push(addedObject(source, new THREE.Matrix4().fromArray(source.matrix), { actor: entity.actor, entity: entity.id,
        prefab: null, partner: null, location: entity.location, rotation: entity.rotation, tinted: false }));
      continue;
    }
    if (entity.template || lightIndex.has(targetKey(entity.from))) {
      const light = addedLightOf(entity);
      if (light) lights.push(light); else carried.added.push(entity);
      continue;
    }
    // Output names already used, applied or not, are never handed out again.
    const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
    if (serial > copySerial) copySerial = serial;
    const sources = entity.components.map(c => templateFor(entity.from, c));
    if (sources.some(t => !t)) { carried.added.push(entity); continue; }
    for (const source of sources) {
      objs.push(addedObject(source, movedMatrix(source, entity.location, entity.rotation), { actor: entity.actor, entity: entity.id,
        prefab: entity.prefab ?? null, partner: entity.partner ?? null, location: entity.location, rotation: entity.rotation,
        tinted: Boolean(entity.tinted), flags: entity.flags ?? null, generated: entity.generated ?? null }));
    }
  }
  addRoots(await buildRoots(objs, progress && ((done, total) => progress('making', done, total))));
  addLightRoots(lights);
  addEffectRoots(effects);
  setMissionMoves(streamMoves);
  // Area lights' glowing pieces as the project sets them; one naming a light this export lacks is carried.
  for (const b of state.areaLightBindings ?? []) {
    const root = lightIndex.get(targetKey(b.target));
    if (root?.userData.source.role === 'area') areaBindings.set(root.userData.source.actor, b.owner); else carried.areaLightBindings.push(b);
  }
  // Groups whose pieces are all here; one naming a piece this export (or this state) lacks is carried unchanged.
  const applied = new Set([...actors.keys()].map(k => `orig|${k}`));
  if (builderMode) for (const p of builder.kept) applied.add(memberKey({ added: p.actor }));
  for (const o of objs) applied.add(memberKey({ added: o.actor }));
  // (lights and the project's buildings are members too)
  for (const r of [...lightRoots.values(), ...volumeRoots.values(), ...effectRoots.values()]) applied.add(memberOf(r.userData.source));
  // (a group that names a group not applied goes with it; so does one in two groups, or in itself)
  const next = new Map(), wanted = state.groups ?? [];
  let fit = wanted.filter(g => g.members.every(m => m.group !== undefined || applied.has(memberKey(m))));
  for (let before = -1; before !== fit.length;) {
    before = fit.length;
    const ids = new Set(fit.map(g => g.id)), holders = new Map();
    for (const g of fit) for (const m of g.members) if (m.group !== undefined) holders.set(m.group, (holders.get(m.group) ?? 0) + 1);
    const loops = g => { for (let x = g, n = 0; x; n++) { if (n > 64) return true; x = fit.find(p => p.members.some(m => m.group === x.id)); } return false; };
    fit = fit.filter(g => g.members.every(m => m.group === undefined || (ids.has(m.group) && m.group !== g.id)) && (holders.get(g.id) ?? 0) <= 1 && !loops(g));
  }
  for (const g of wanted) {
    if (!fit.includes(g)) { carried.groups.push(g); continue; }
    // (a group saved unlocked, before 11 November 2026, is a group as any other now)
    next.set(g.id, { id: g.id, locked: true, breakTogether: g.breakTogether === true,
                     ...(validPrefabMark(g.prefab) ? { prefab: { ...g.prefab } } : {}),
                     members: new Map(g.members.map(m => [memberKey(m), m])) });
  }
  setGroups(next);
  copySerial = Math.max(copySerial, Number.isInteger(state.nextSerial) ? state.nextSerial : 0);
  gizmo.setSelection([]); gizmo.clearHistory(); sceneChanged(); editChanged();
  return carried;
}
// A message under the header with its actions (recovered edits, a save conflict, a project that cannot open).
// timeout (ms): a passing message closes itself after that long (Play in game's "Starting XCOM …"); hovering it
// keeps it open, and × still closes it sooner. Without one it stays until dismissed.
let bannerTimer = null;
function banner(message, actions = [], { timeout = 0 } = {}) {
  const el = $('projectBanner');
  clearTimeout(bannerTimer);
  el.onmouseenter = el.onmouseleave = null;
  // a message with line breaks: one paragraph each
  if (typeof message === 'string' && message.includes('\n')) {
    const body = document.createElement('div'); body.className = 'bannertext';
    setParagraphs(body, message);
    el.replaceChildren(body);
  } else el.replaceChildren(message);
  for (const [label, run] of actions) {
    const button = text(el, 'button', label);
    button.type = 'button';
    button.onclick = () => { el.hidden = true; run(); };
  }
  const close = text(el, 'button', '×', 'close');
  Object.assign(close, { type: 'button', title: 'Dismiss' });
  close.onclick = () => { el.hidden = true; };
  el.hidden = false;
  if (timeout) {
    const arm = () => { clearTimeout(bannerTimer); bannerTimer = setTimeout(() => { el.hidden = true; }, timeout); };
    el.onmouseenter = () => clearTimeout(bannerTimer);
    el.onmouseleave = arm;
    arm();
  }
}
// Recent projects: when this browser last opened or saved each, beside when it was saved anywhere.
const RECENT = 'workshop.recentProjects';
function recentTimes() { try { return JSON.parse(recall(RECENT)) ?? {}; } catch { return {}; } }
function touchRecent(id) {
  const times = { ...recentTimes(), [id]: new Date().toISOString() };
  remember(RECENT, JSON.stringify(Object.fromEntries(Object.entries(times).sort((a, b) => b[1].localeCompare(a[1])).slice(0, 20))));
}
function projectNote(message) { text($('diagnostics'), 'div', message, 'note'); $('issueCount').textContent = String(Number($('issueCount').textContent || 0) + 1); }
function navigate(change) {
  const parameters = new URLSearchParams(location.search);
  if ('prefab' in change) for (const key of ['map', 'project', 'scene', 'mission']) parameters.delete(key);
  else if ('map' in change || 'project' in change) parameters.delete('prefab');
  for (const [key, value] of Object.entries(change)) { if (value == null) parameters.delete(key); else parameters.set(key, value); }
  location.search = parameters.toString();
}
async function goTo(change) {
  if (navigating || saving) return false;
  navigating = true;
  try {
    if (unsavedDocument()) {
      const decision = await askLeave();
      if (decision === 'cancel') return false;
      if (decision === 'save') {
        const saved = builderMode ? await saveBuilder() : project ? await saveProject() : await showFileDialog('save', true);
        if (!saved || (builderMode ? dirty() : !project || dirty())) return false;
      }
    }
    await discardAndGo(change); return true;
  } catch (error) { banner(`Could not leave: ${error.message}`); return false; }
  finally { navigating = false; }
}
async function openProject(id) {
  if (!projectsAvailable()) { banner('Projects edit a map\'s original layout, so this layout opened without the project.'); return; }
  let doc;
  try { doc = await projectApi.load(id); }
  catch (e) { banner(`The project could not be opened: ${e.message}`); return; }
  if (doc.source?.map !== activeMapId) { goTo({ map: doc.source?.map, scene: null, project: id }); return new Promise(() => {}); }
  $('loading').hidden = false; loadingState(`Opening ${doc.name}…`, 0);
  const docGroups = Array.isArray(doc.groups) ? doc.groups : [];
  const docBindings = Array.isArray(doc.areaLightBindings) ? doc.areaLightBindings : [];
  const malformed = { overrides: doc.overrides.filter(r => !validOverride(r)), added: doc.added.filter(e => !validAdded(e)),
                      groups: docGroups.filter(g => !validGroup(g)), areaLightBindings: docBindings.filter(b => !validBinding(b)) };
  const carried = await applyState({ overrides: doc.overrides.filter(validOverride), added: doc.added.filter(validAdded),
                                     groups: docGroups.filter(validGroup), areaLightBindings: docBindings.filter(validBinding),
                                     stage: doc.stage, buildings: Array.isArray(doc.buildings) ? doc.buildings : [],
                                     cleared: doc.cleared === true, clearKeepsOutside: doc.clearKeepsOutside === true,
                                     landingZones: Array.isArray(doc.landingZones) ? doc.landingZones : null,
                                     missions: Array.isArray(doc.missions) ? doc.missions : null,
                                     spawnRules: doc.spawnRules ?? null,
                                     nextSerial: doc.nextSerial }, openingProgress(doc.name));
  // a building this page can't read is kept and saved back unchanged, and so is one of the map's it can't edit
  carried.buildings = [...(carried.buildings ?? []), ...(Array.isArray(doc.buildings) ? doc.buildings : []).filter(b => !validBuilding(b))];
  carried.overrides.push(...malformed.overrides); carried.added.push(...malformed.added); carried.groups.push(...malformed.groups);
  carried.areaLightBindings.push(...malformed.areaLightBindings);
  project = { doc, revision: doc.revision, carried, savedKey: stateKey(editState()) };
  // a bomb moved before export 33 left its helper point behind (F-124; decision D6): the helper gets the move now, and
  // the project shows as changed until it is saved
  const helped = bombHelperFix();
  if (helped) {
    setMissionMoves(helped);
    banner('The bomb\'s helper point now moves with it: Long War\'s bomb mutator finds the bomb again and places it where it finds places, the project\'s place being where it plays when it finds none. Save the project to keep it.');
  }
  askedPick = null;     // (the address's added kind is picked by now, if the project adds it)
  touchRecent(id);
  // its last package, and a build still running (opened again, or the page reloaded mid-build): follow it
  projectApi.buildStatus(id).then(s => { lastBuild = s; if (s.state === 'running') followBuild(s); }, () => {});
  $('loading').hidden = true;
  const kept = carried.overrides.length + carried.added.length + carried.groups.length + carried.areaLightBindings.length
    + carried.buildings.filter(validBuilding).length;
  if (kept) projectNote(`${doc.name}: ${plural(kept, 'edit')} name pieces this export does not have; they are kept and saved back unchanged.`);
  if (doc.source.sha256 !== data.source.sha256) {
    projectNote(`${doc.name} was made on another ${doc.source.package} (SHA-256 ${doc.source.sha256.slice(0, 12)}…, this one ${data.source.sha256.slice(0, 12)}…).`);
    banner(`${doc.name} was made on a different ${doc.source.package}. Its edits are shown where their pieces match; check them before building.`);
  }
  if (doc.view?.camera?.length === 3 && doc.view.target?.length === 3) {
    camera.position.fromArray(doc.view.camera); controls.target.fromArray(doc.view.target); controls.update();
  }
  const recovery = await projectApi.recovery(id).catch(() => null);
  if (recovery && Array.isArray(recovery.overrides) && Array.isArray(recovery.added)) {
    const state = { overrides: recovery.overrides.filter(validOverride), added: recovery.added.filter(validAdded),
                    groups: (Array.isArray(recovery.groups) ? recovery.groups : []).filter(validGroup),
                    areaLightBindings: (Array.isArray(recovery.areaLightBindings) ? recovery.areaLightBindings : []).filter(validBinding),
                    stage: validStage(recovery.stage, ownSize()?.dims) ? recovery.stage : null,
                    buildings: (Array.isArray(recovery.buildings) ? recovery.buildings : []).filter(validBuilding),
                    cleared: recovery.cleared === true, clearKeepsOutside: recovery.clearKeepsOutside === true,
                    landingZones: Array.isArray(recovery.landingZones) ? recovery.landingZones : null,
                    missions: Array.isArray(recovery.missions) ? recovery.missions : null,
                    spawnRules: recovery.spawnRules ?? null,
                    nextSerial: recovery.nextSerial };
    if (stateKey(sortState(state)) !== project.savedKey) {
      const when = new Date(recovery.savedAt).toLocaleString();
      const since = recovery.baseRevision !== project.revision ? ` (based on revision ${recovery.baseRevision}; the project is now at ${project.revision})` : '';
      banner(`Unsaved changes to ${doc.name} from ${when} were kept${since}.`, [
        ['Restore them', async () => { await applyState(state); recoveryKept = true; projectChanged(); }],
        ['Discard them', () => { clearDocumentRecovery().catch(error => banner(`Recovery could not be cleared: ${error.message}`)); }],
      ]);
    }
  }
  editChanged();
}
// The project's own state in the header, and its unsaved state kept on the server against a lost tab.
function projectChanged() {
  if (builderMode) {
    if (builder.loading) return;
    builderTitle(); refreshBuilder(); problemsPaint(); clearTimeout(recoveryTimer);
    // (the status says saved or unsaved: a save changes it with no edit)
    if (builder.doc?.revision) { $('editCount').hidden = false; $('editCount').textContent = saveState(); $('editCount').classList.toggle('warn', saveState() !== 'saved'); }
    if (!navigating && !saving) recoveryTimer = setTimeout(keepRecovery, 1000);
    return;
  }
  $('projectTitle').textContent = project ? project.doc.name : 'None';
  if (!project) return;
  $('projectButton').classList.toggle('unsaved', dirty());
  clearTimeout(recoveryTimer);
  recoveryTimer = setTimeout(keepRecovery, 1000);
}
async function keepRecovery() {
  if (builderMode) {
    if (!builder.doc?.revision || builder.loading || saving || navigating) return;
    if (gizmo.controls.dragging) { recoveryTimer = setTimeout(keepRecovery, 1000); return; }
    const id = builder.doc.id, state = { baseRevision: builder.doc.revision, document: builderDocument(), envelope: builder.envelope, nextSerial: copySerial };
    const changed = dirty();
    if (!changed && !recoveryKept) return;
    try {
      await documentWrites.run(() => changed ? prefabApi.keepRecovery(id, state) : prefabApi.dropRecovery(id));
      recoveryKept = changed;
    } catch (error) { if (error.status !== 409) banner(`Unsaved prefab changes could not be kept for recovery: ${error.message}`); }
    return;
  }
  if (!project || saving || navigating) return;
  // A drag in progress is never kept half done.
  if (gizmo.controls.dragging) { recoveryTimer = setTimeout(keepRecovery, 1000); return; }
  const state = editState();
  try {
    if (stateKey(state) !== project.savedKey) {
      const id = project.doc.id, snapshot = { baseRevision: project.revision, nextSerial: copySerial, ...state };
      await documentWrites.run(() => projectApi.keepRecovery(id, snapshot));
      recoveryKept = true;
    } else if (recoveryKept) { const id = project.doc.id; await documentWrites.run(() => projectApi.dropRecovery(id)); recoveryKept = false; }
  } catch (e) { console.warn('Unsaved changes could not be kept for recovery', e); }
}
// Save (Ctrl+S): the open project's next revision; without one, the Save dialog asks for a name first.
// The Save dialog calls it with { name, output } for a new project from what is on screen, with the map name it showed
// (the server's: output names plan); { name, replace } to put what is on screen into that saved project, which keeps
// its id and map name; or { rename } for the open project's next revision under that name (the dialog matches names
// regardless of case), its map name kept. A new project's save that the server refuses because its map name was
// taken meanwhile throws, so the dialog can show the name it would get now; other failures say so in a banner.
async function saveProject({ name = null, replace = null, rename = null, output = null } = {}) {
  if (builderMode) return saveBuilder({ name, replace });
  if (!projectsAvailable() || saving || gizmo.controls.dragging) return false;
  if (!project && !name) { showFileDialog('save'); return false; }
  saving = true;
  clearTimeout(recoveryTimer); await documentWrites.wait();
  const state = editState(), carried = project?.carried ?? { overrides: [], added: [], groups: [], areaLightBindings: [] };
  const previous = project?.doc.id, fresh = Boolean(name) && !replace;
  // What is on screen was made against the open project's map, or else this export. A project of this very package
  // opened on a newer export is bound to it on saving: what is on screen is that export's, and the Build compiles
  // against the export the project names (compiler.find_export), so a newer export's data (export 23's effects) reaches
  // it.
  const source = project ? { ...project.doc.source } : sourceOf(activeMapId, data);
  if (project && source.sha256 === data?.source?.sha256 && Number(data.exporterVersion) > Number(source.exporterVersion ?? 0))
    source.exporterVersion = data.exporterVersion;
  let base = project?.doc, expected = project?.revision;
  try {
    if (replace) {
      const target = await projectApi.load(replace.id);
      if (target.source?.map !== activeMapId) throw new Error(`${target.name} is a project of another map.`);
      base = { ...target, name, source }; expected = target.revision;
    } else if (fresh) {
      if (!output) throw new Error('the map name is still being worked out; save again in a moment');
      base = { ...newDocument(name, activeMapId, data, output), source }; expected = 0;
    }
    else if (rename && project) base = { ...project.doc, name: rename };
    const document = { ...base, schemaVersion: PROJECT_SCHEMA_VERSION, ...sortState({ overrides: [...state.overrides, ...carried.overrides], added: [...state.added, ...carried.added],
                                               groups: [...state.groups, ...carried.groups],
                                               areaLightBindings: [...state.areaLightBindings, ...(carried.areaLightBindings ?? [])],
                                               stage: state.stage, buildings: [...(state.buildings ?? []), ...(carried.buildings ?? [])],
                                               cleared: state.cleared, clearKeepsOutside: state.clearKeepsOutside,
                                               landingZones: state.landingZones, missions: state.missions, spawnRules: state.spawnRules }),
                       nextSerial: copySerial, view: { camera: camera.position.toArray(), target: controls.target.toArray() } };
    if (project && !replace && !fresh) document.source = source;     // a newer export of the same package binds it
    if (!document.stage) delete document.stage;     // the map's own size is said by saying nothing
    if (!document.buildings.length) delete document.buildings;
    if (!document.cleared) delete document.cleared;
    if (!document.clearKeepsOutside) delete document.clearKeepsOutside;
    if (document.landingZones == null) delete document.landingZones;     // the map's own landings and lines
    if (document.missions == null) delete document.missions;     // every mission of the base map
    delete document.revision; delete document.savedAt;
    if (fresh) delete document.created;
    const result = await projectApi.save(document.id, document, expected);
    // Saved under another project: the changes kept for recovery of the one open before are in it now.
    if (previous && previous !== document.id && recoveryKept) projectApi.dropRecovery(previous).catch(() => {});
    project = { doc: { ...document, ...result }, revision: result.revision, carried, savedKey: stateKey(state) };
    recoveryKept = false;
    touchRecent(document.id);
    const parameters = new URLSearchParams(location.search);
    parameters.set('map', activeMapId); parameters.delete('scene'); parameters.set('project', document.id);
    history.replaceState(null, '', `?${parameters}`);
    flashHint(`Saved ${document.name} · revision ${result.revision}`);
    return true;
  } catch (e) {
    // the map name shown was taken meanwhile: the dialog shows the one it would get now, and nothing is lost
    if (fresh && e.status === 409 && e.detail?.proposal) throw e;
    if (e.status === 409 && Number.isInteger(e.detail?.revision) && !name && !replace) {
      banner(`${project.doc.name} was saved elsewhere since you opened it (revision ${e.detail.revision}).`, [
        ['Overwrite it with this', () => { project.revision = e.detail.revision; saveProject(); }],
        ['Open the saved one', () => discardAndGo({ map: activeMapId, project: project.doc.id, scene: null })],
      ]);
    } else banner(`Not saved: ${e.message}`);
    return false;
  } finally { saving = false; editChanged(); }
}
// Build (Ctrl+B, Project menu): a panel first asks whether to bake the lighting (build_options.js; off by default),
// then the open project is saved if it has unsaved changes (Save itself never builds) and the server builds the saved
// revision (tools/viewer/builds.py runs tools/editor/build.py, with --quick when not baking): the variant package in the
// builds folder. Nothing is installed. While it runs, a window covers the editor, since the build takes
// the saved revision and nothing should change under it. The window shows:
// - the steps with their times, and the step running with its progress (relight.py counts the pieces it relights);
// - the log's latest lines;
// - the time so far against the project's last build, which gives the bar its estimate.
// When the build ends, the window shows the package or why it failed, and closes with Close or Esc.
let buildTimer = null, buildTicker = null, lastBuild = null, buildView = null;
const BUILD_ROWS = [['snapshot', 'Read the project and its base map'], ['compile', 'Compile the edit'],
                    ['patch', 'Build and cook the patch in UDK'], ['transplant', 'Bring the pieces from other maps'], ['light', 'Make the edit in the map and bake its lighting'],
                    ['package', 'Write the variant folder']];
const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const secondsBetween = (a, b) => Math.max(0, ((b ? new Date(b).getTime() : Date.now()) - new Date(a).getTime()) / 1000);
const sentence = s => s.charAt(0).toUpperCase() + s.slice(1);
// Whether Build can start now: false (with a hint) without a saved project or while a build runs.
function canBuild() {
  if (!projectsAvailable() || saving) return false;
  if (!project) { flashHint('Name and save the project first: Build makes a package of a saved project'); showFileDialog('save'); return false; }
  if (lastBuild?.state === 'running') { flashHint('The build is still running'); return false; }
  return true;
}
// Build's panel: whether to bake the lighting, then buildProject.
function openBuild() {
  if (buildOptions.open || !canBuild() || needsPrepare()) return;
  buildOptions.show({
    title: `Build ${project.doc.name}`,
    note: `${dirty() ? 'What is on screen, saved first as a new revision' : `Revision ${project.revision}, as saved`}, into its variant package in the builds folder (${project.doc.output?.shipAs}). It replaces the last package and installs nothing.`,
    times: lastBuild?.package?.times ?? {}, bakeNote: bakeNote(),
    ok: 'Build', onBuild: ({ quick }) => buildProject(quick),
  });
}
// quick: the edit made in the map without baking its lighting (build.py --quick): seconds, not minutes.
async function buildProject(quick = false) {
  if (!canBuild()) return;
  if (dirty() && !(await saveProject())) return;
  try {
    const status = await projectApi.build(project.doc.id, quick);
    // Play in game asked for this very build: its attempt, so no other build of the project (the queue's) plays
    if (playAfterBuild && !playAfterBuild.attempt && status.job?.project === playAfterBuild.project) playAfterBuild.attempt = status.job.attempt;
    followBuild(status);
  }
  catch (e) { banner(`Not built: ${e.message}`); }
}
// Each status from the server (every 2 s while the build runs). A build that ended before this page saw it running
// opens no window: its package shows in the Project menu. A build of the build queue's (job.origin 'queue') opens no
// window either: the editor stays usable, and the chip and the project manager follow it.
function followBuild(status) {
  clearTimeout(buildTimer);
  lastBuild = status;
  const job = status.job;
  if (!project || !job) return;
  if (job.origin === 'queue' && buildView?.attempt !== job.attempt) { renderPlayItems(); return; }
  if (buildView?.attempt !== (job.attempt ?? job.startedAt)) {
    if (status.state !== 'running') return;
    // the estimate: how long the project's last build of the same kind (full or quick) took
    const times = status.package?.times;
    buildView = { attempt: job.attempt ?? job.startedAt, started: job.startedAt, estimate: (job.quick ? times?.quick : times?.full) || null,
                  failures: 0, fullLog: false, thenInstall: Boolean(job.attempt) && playAfterBuild?.attempt === job.attempt, install: null };
    $('buildPlaySaving').checked = false;           // the window's Enable saving: off for each build
    openBuildWindow();
  }
  Object.assign(buildView, { status, failures: 0 });
  if (status.state === 'failed' && !buildView.ended) buildView.fullLog = true;
  buildView.ended = status.state !== 'running';
  // Play in game asked for this build: play it once built (this attempt alone).
  if (buildView.ended && job.attempt && playAfterBuild?.attempt === job.attempt) {
    playAfterBuild = null;
    if (status.state === 'built') playBuilt(job.project);
  }
  renderBuild();
  if (!buildView.ended) buildTimer = setTimeout(pollBuild, 2000);
  else {
    clearInterval(buildTicker); $('buildClose').focus();
    // the window's Play in game goes by the installs as they are now
    if (status.state === 'built') refreshInstalls().then(() => { if (!$('buildModal').hidden) renderBuild(); });
  }
}
function pollBuild() {
  if (!project) return;
  projectApi.buildStatus(project.doc.id).then(followBuild, () => {
    buildView.failures++;
    renderBuild();
    buildTimer = setTimeout(pollBuild, 5000);
  });
}
function openBuildWindow() {
  const el = $('buildModal');
  el.hidden = false;
  document.activeElement?.blur?.();
  el.focus();
  gizmo.cancel(); dragHint(false);
  clearInterval(buildTicker);
  buildTicker = setInterval(() => { if (buildView && !buildView.ended) renderBuild(); }, 1000);
}
// Closed while the build still runs (only when the server stopped answering): keep asking, and open it again if the
// server answers with the build still running.
function closeBuildWindow() {
  clearInterval(buildTicker); clearTimeout(buildTimer);
  $('buildModal').hidden = true;
  if (buildView && !buildView.ended) { buildView.attempt = null; buildTimer = setTimeout(pollBuild, 5000); }
}
const copyCount = n => n === 1 ? '1 copy' : `${n} copies`;
// A step's line under its name: what it made once done, or what it is doing while it runs.
// The Build's light counts (build.py light_counts): placed lights moved, changed, added and deleted, and the glow
// lights following their pieces.
function lightWords(l) {
  if (!l) return '';
  const placed = [l.moved && `${l.moved} moved`, l.changed && `${l.changed} changed`,
                  l.added && `${l.added} added${l.recipeSpots ? ` (${l.recipeSpots} from the recipe)` : ''}`, l.deleted && `${l.deleted} deleted`];
  const glow = l.area ? (l.area.moved || 0) + (l.area.copied || 0) + (l.area.deleted || 0) : 0;
  return [placed.some(Boolean) && `lights ${placed.filter(Boolean).join(', ')}`,
          glow && `${plural(glow, 'glow light')} following ${plural(l.area.pieces?.length ?? 0, 'piece')}`].filter(Boolean).join('; ');
}
// the writer's record of pieces' flags (build.py flag_record): the pieces written and read back, any it refused
function flagWords(f) {
  if (!f) return '';
  const pieces = (f.inPlace ?? 0) + (f.onCopies ?? 0) - (f.refused?.length ?? 0);
  return [`flags written on ${plural(pieces, 'piece')}`, f.regions && `${plural(f.regions, 'tile region')} worked out again`,
          f.refused?.length && `not written on ${f.refused.join(', ')}`].filter(Boolean).join(', ');
}
function buildStepDetail(key, stage, job, running) {
  if (key === 'compile' && stage) {
    const say = (parts, where) => (parts = parts.filter(Boolean)).length ? `${parts.join(' and ')} ${where}` : '';
    return [say([stage.nativeCopies && copyCount(stage.nativeCopies), stage.hides && plural(stage.hides, 'hidden piece')], 'made in the map'),
            say([stage.copierCopies && copyCount(stage.copierCopies), stage.patchHides && plural(stage.patchHides, 'hidden piece')], 'for the patch'),
            lightWords(stage.lights), stage.pieceFlags && `${plural(stage.pieceFlags, 'piece')} with flags changed in place`,
            stage.leftOut ? `${plural(stage.leftOut, 'piece')} left out (listed below)` : '']
      .filter(Boolean).join('; ');
  }
  if (key === 'patch' && stage?.bytes) return `${Math.round(stage.bytes / 1024)} KB cooked`;
  if (key === 'transplant' && stage) {
    // pieces, and effects and sounds (effects and sounds plan, FX4) and lens flares (FX6b: counted among the
    // effects, and of their own), each donor's actors staged once
    const sum = k => stage.donors.reduce((n, d) => n + (d[k] ?? 0), 0), pieces = sum('pieces'), flares = sum('flares'), effects = sum('effects') - flares;
    const what = [pieces && plural(pieces, 'piece'), effects && `${effects} ${effects === 1 ? 'effect or sound' : 'effects and sounds'}`,
                  flares && plural(flares, 'lens flare')]
      .filter(Boolean).join(' and ') || plural(stage.foreignPieces, 'piece');
    return `${what} from ${stage.donors.map(d => d.map).join(', ')}: ${kilobytes(sum('bytes'))} more in the map`;
  }
  if (key === 'light' && stage?.baked === false)    // a quick build's: the edit made, nothing relit
    return [stage.nativeCopies && `${copyCount(stage.nativeCopies)} made`, stage.hidden && `${stage.hidden} taken out`,
            stage.lights && 'light edits made', flagWords(stage.pieceFlags), 'lighting not baked'].filter(Boolean).join(', ');
  // a build whose light edits change no texel (a light added switched off) keeps the map's lighting
  if (key === 'light' && stage?.lightingUnchanged) return ['lighting unchanged: no texel to relight', flagWords(stage.pieceFlags)].filter(Boolean).join('; ');
  if (key === 'light' && stage) return [`${plural(stage.written, 'piece')} relit`, `${stage.unchanged} unchanged`,
                                        stage.hidden && `${stage.hidden} taken out`, flagWords(stage.pieceFlags)].filter(Boolean).join(', ');
  if (!running) return '';
  const p = job.progress;
  if (p) return sentence(p.total ? `${p.what}: ${p.done} of ${p.total}` : `${p.what}…`);
  return job.running ? `${sentence(job.running)}…` : '';
}
function renderBuild() {
  const { status, estimate, failures } = buildView, job = status.job;
  const running = status.state === 'running', built = status.state === 'built';
  const elapsed = secondsBetween(job.startedAt, job.finishedAt);
  $('buildIcon').className = `buildicon ${running ? 'spin' : status.state}`;
  const cancelled = status.state === 'cancelled';
  // a quick build (the edit without its lighting baked) says so in its title, and once built, what that means
  const quick = Boolean(job.quick), kind = quick ? ' (lighting not baked)' : '';
  // Play in game, once built: the package installed and the game started on it, from the window (playFinished)
  const install = buildView.install, playable = built && Boolean(status.package) && !playStatus?.unavailable;
  $('buildTitle').textContent = running ? `Building ${job.name}${kind}` : built ? `Built ${job.name}${kind}` : cancelled ? `${job.name}: build cancelled` : `${job.name} didn't build`;
  $('buildClock').textContent = clock(elapsed);
  $('buildNote').textContent = failures >= 3
    ? 'The viewer\'s server isn\'t answering (was it restarted?). The build may still be running; trying again every 5 s.'
    : running ? `Revision ${job.revision}, as saved${quick ? ', its lighting not baked' : ''}${buildView.thenInstall ? '; played in the game once built' : ''}. The editor waits until the build ends.`
    : built ? `Revision ${job.revision}, in ${clock(elapsed)}.${quick ? ' Its lighting is not baked: in the game the edit\'s lighting is wrong, while pathing, cover and line of sight are as a full build makes them. Build with Bake the lighting ticked for the proper lighting.' : ''}${buildView.thenInstall || install ? ''
      : playable ? ' Nothing is installed yet: Play in game installs it and starts the game in a battle on it.' : ' Nothing is installed: the package\'s README says how.'}`
    : `Revision ${job.revision}, stopped after ${clock(elapsed)}.`;
  // the steps: done with their times, the one running with its progress. The patch's shows only once the compile
  // leaves the patch something, which no project the compiler accepts does today: its edit is made in the map itself.
  const stages = Object.fromEntries((job.stages || []).map(s => [s.stage, s]));
  const compiled = stages.compile;
  const patchMade = Boolean(stages.patch ? !stages.patch.skipped : compiled?.copierCopies || compiled?.patchHides);
  const list = $('buildSteps');
  list.replaceChildren();
  let from = job.startedAt, reached = false;
  for (const [key, label] of BUILD_ROWS) {
    const end = key === 'package' ? (built ? job.finishedAt : null) : stages[key]?.at;
    if (key === 'patch' && !patchMade) { if (end) from = end; continue; }
    if (key === 'transplant' && !(stages.transplant || compiled?.foreignCopies)) continue;
    const state = end ? 'done' : reached ? 'todo' : running ? 'now' : built ? 'done' : 'failed';
    if (state === 'now' || state === 'failed') reached = true;
    const li = text(list, 'li', '', state);
    text(li, 'span', '', 'stepmark');
    const what = text(li, 'span', key === 'light' && quick ? 'Make the edit in the map (lighting not baked)' : label, 'what');
    const detail = buildStepDetail(key, stages[key], job, state === 'now');
    if (detail) text(what, 'small', detail);
    if (state === 'now' && job.progress?.total) {
      const bar = text(what, 'span', '', 'stepbar');
      text(bar, 'span').style.width = `${(100 * job.progress.done / job.progress.total).toFixed(1)}%`;
    }
    text(li, 'span', ['done', 'now', 'failed'].includes(state) ? clock(secondsBetween(from, end ?? job.finishedAt)) : '', 'time');
    if (end) from = end;
  }
  // the pieces the compiler left out (plan "sturdier prefabs", R4): the build goes on without them; a row selects
  // its piece
  // (with those the Build itself could not make: its `leftout` stage, build.py drop_untried)
  const gone = [...(compiled?.leftOutPieces ?? []), ...(stages.leftout?.pieces ?? [])], goneList = $('buildLeftOut');
  goneList.hidden = !gone.length;
  goneList.replaceChildren();
  if (gone.length) {
    text(goneList, 'li', `${plural((compiled.leftOut ?? 0) + (stages.leftout?.count ?? 0) || gone.length, 'piece')} left out of this build: ${gone.length === 1 ? 'it' : 'they'} can't be built. The rest ${running ? 'is being built' : built ? 'is built' : 'was being built'}.`, 'head');
    for (const row of gone.slice(0, 50)) {
      const li = text(goneList, 'li', row.message, row.actor ? 'pick' : '');
      if (row.actor) { li.title = `Select ${short(row.actor)}`; li.onclick = () => selectActors([row.actor]); }
    }
    if ((compiled.leftOut ?? gone.length) > 50) text(goneList, 'li', `… and ${(compiled.leftOut ?? gone.length) - 50} more (the build's compile-report.json has them all)`);
  }
  // what the edit does to the missions the variant keeps (the compiler's mission warnings, mission types plan C3), by
  // mission: warnings only, the build goes on
  const warned = compiled?.missionWarnings ?? [], missionList = $('buildMissions');
  missionList.hidden = !warned.length;
  missionList.replaceChildren();
  if (warned.length) {
    const count = compiled.missionWarningCount ?? warned.length, byMission = new Map();
    for (const row of warned) { if (!byMission.has(row.mission)) byMission.set(row.mission, []); byMission.get(row.mission).push(row); }
    text(missionList, 'li', `${plural(count, 'mission warning')}: what the edit does to ${byMission.size === 1 ? 'a mission' : `${byMission.size} missions`} the variant keeps. The build goes on; move the piece, or drop the mission from the project.`, 'head');
    for (const [mission, rows] of byMission) {
      text(missionList, 'li', mission ?? 'A mission', 'mission');
      for (const row of rows) {
        const li = text(missionList, 'li', row.message.replace(/^[^:]*: /, ''), row.actor ? 'pick' : '');
        if (row.actor) { li.title = `Show ${short(row.actor)} (its marker, the Normal button's Spawn points and objectives)`; li.onclick = () => showSpawn(row.actor, row.stream ?? null); }
      }
    }
    if (count > warned.length) text(missionList, 'li', `… and ${count - warned.length} more (the build's compile-report.json has them all)`);
  }
  // the bar: the time so far against the last build's, or a moving bar when there is none to go by
  const bar = $('buildBar'), barText = $('buildBarText');
  bar.className = `buildbar ${status.state}${running && !estimate ? ' indeterminate' : ''}`;
  const share = running ? (estimate ? Math.min(elapsed / estimate, 0.97) : 0.3) : built ? 1 : Math.min(elapsed / (estimate || elapsed || 1), 1);
  bar.firstElementChild.style.width = `${(100 * share).toFixed(1)}%`;
  const last = quick ? 'the last unbaked build' : 'the last baked build';
  barText.textContent = !running ? '' : !estimate ? `This project hasn't had ${quick ? 'an unbaked' : 'a baked'} build before, so there is no time to go by.`
    : elapsed < estimate ? `About ${clock(estimate - elapsed)} left, going by ${last} (${clock(estimate)}).`
    : `Taking longer than ${last} (${clock(estimate)}).`;
  // the log: its latest lines, or all the server keeps (the last 40)
  const lines = (job.lines || []).filter(l => !/^\w+: \{/.test(l) && !l.trimStart().startsWith('$ ')).map(l => l.trim()).filter(Boolean);
  // (written only when it changes; the full log follows its end unless it was scrolled up to read)
  const log = $('buildLog'), shown = (buildView.fullLog ? job.lines || [] : lines.slice(-4)).join('\n') || '…';
  const wasFull = log.classList.contains('full'), atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 4;
  if (log.textContent !== shown) log.textContent = shown;
  log.classList.toggle('full', buildView.fullLog);
  if (buildView.fullLog && (atEnd || !wasFull)) log.scrollTop = log.scrollHeight;
  $('buildLogToggle').textContent = buildView.fullLog ? 'Latest lines only' : 'Show the log';
  // the result
  const result = $('buildResult'), pkg = status.package;
  // the compiler found no export new enough (compiler.py: "... prepare the map ..."): Prepare the map does it from here
  const wantsPrepare = status.state === 'failed' && /\bno export of\b.*\bprepare the map\b|\bre-export it\b/s.test(job.error ?? '');
  result.replaceChildren();
  result.hidden = running;
  result.classList.toggle('error', status.state === 'failed');
  if (built && pkg) {
    pathLink(result, pkg.folder);
    text(result, 'small', pkg.files.join(' · '));
  } else if (status.state === 'failed' || cancelled) {
    if (wantsPrepare) text(result, 'div', `The editor's copy of ${mapLabel(activeMapId)} is older than this build needs. Prepare the map again, then build.`, 'remedy');
    text(result, 'div', job.error ?? 'See the log.');
  }
  if (buildView.reportPath) pathLink(result, buildView.reportPath, 'Bug report saved (its path is copied): ');
  else if (buildView.report) text(result, 'div', buildView.report, 'path');
  if (install) setParagraphs(text(result, 'div', '', `install ${install.state}`), install.state === 'running' ? 'Installing it and starting the game…' : install.message);
  const play = $('buildPlay'), cantPlay = playBlocked(playStatus);
  play.hidden = !playable;
  play.disabled = install?.state === 'running' || Boolean(cantPlay);
  // Enable saving beside it: off unless ticked, fixed on for a mission that needs it (the header's)
  const savingRow = $('buildPlaySavingRow'), saving = $('buildPlaySaving'), forced = savingFor(missionPickValue);
  savingRow.hidden = !playable;
  if (forced) saving.checked = true;
  else if (saving.dataset.forced) saving.checked = false;   // fixed on for the mission before: off again
  saving.dataset.forced = forced ? '1' : '';
  saving.disabled = Boolean(forced) || play.disabled;
  savingRow.title = forced ?? savingHelp(playStatus?.saveKey ?? 'F5');
  play.title = cantPlay ? `Not now: ${cantPlay}`
    : `Install this build in ${playStatus?.install?.sameAsLwr === false ? 'the install under Installs' : 'the game install'} under its own name and start the game in a battle on it: no campaign to start, and nothing of the game's own is changed`;
  $('buildCopy').hidden = !(built && pkg);
  $('buildPrepare').hidden = !wantsPrepare;
  $('buildClose').classList.toggle('primary', !wantsPrepare);
  $('buildCancel').hidden = !running || failures >= 3;
  $('buildReport').hidden = running;
  $('buildClose').hidden = running && failures < 3;
}
// A path of the builds folder as a link: a click shows it in Windows Explorer (builds.py reveal); before: words ahead.
function pathLink(parent, path, before = '') {
  const line = text(parent, 'div', before);
  const link = text(line, 'a', path, 'path');
  link.href = '#';
  link.title = 'Show in Windows Explorer';
  link.onclick = async e => {
    e.preventDefault();
    try { await projectApi.reveal(path); }
    catch (error) { link.title = `Not shown: ${error.message}`; link.classList.add('failed'); }
  };
  return link;
}
$('buildLogToggle').onclick = () => { buildView.fullLog = !buildView.fullLog; renderBuild(); };
$('buildCopy').onclick = () => {
  navigator.clipboard?.writeText(buildView.status.package.folder).then(() => { $('buildCopy').textContent = 'Copied'; },
    () => { $('buildCopy').textContent = 'Copy failed'; });
  setTimeout(() => { $('buildCopy').textContent = 'Copy the folder path'; }, 1500);
};
$('buildClose').onclick = closeBuildWindow;
// Play in game from a finished build's window: that build installed and the game started on it (playBuilt), the
// outcome shown in the window. It asks the server first, as the Project menu's Play in game does (XCOM may be open).
async function playFinished() {
  const id = buildView.status.job.project;
  playZone = null;                                  // the window's own Play: no landing zone of a Land here
  playMission = missionPickValue;                   // and the header's mission
  playSaving = $('buildPlaySaving').checked;        // and its own Enable saving
  buildView.install = { state: 'running' };
  renderBuild();
  let why;
  try { playStatus = await playApi.status(); why = playBlocked(playStatus); }
  catch (e) { why = e.message; }
  if (why) { buildView.install = { state: 'failed', message: `Not started: ${why}.` }; renderBuild(); return; }
  playBuilt(id);
}
$('buildPlay').onclick = playFinished;
$('buildPrepare').onclick = () => { closeBuildWindow(); showPrepare('failed', true); };
// Cancel stops the build and its tools (builds.py); the package swaps in only at the end, so the last good one stays.
$('buildCancel').onclick = async () => {
  $('buildCancel').disabled = true;
  try { followBuild(await projectApi.cancelBuild(buildView.status.job.project, buildView.status.job.attempt)); }
  catch (e) { buildView.report = `Not cancelled: ${e.message}`; buildView.reportPath = null; renderBuild(); }
  finally { $('buildCancel').disabled = false; }
};
// A bug report: the project, the build's logs and manifest zipped in the builds folder (builds.py report).
$('buildReport').onclick = async () => {
  $('buildReport').disabled = true;
  try {
    const r = await projectApi.report(buildView.status.job.project);
    buildView.report = null; buildView.reportPath = r.zip;
    navigator.clipboard?.writeText(r.zip).catch(() => {});
  } catch (e) { buildView.report = `No bug report: ${e.message}`; buildView.reportPath = null; }
  finally { $('buildReport').disabled = false; renderBuild(); }
};
// While the build window is open the editor takes no keys (Ctrl shortcuts included); the window's buttons keep theirs,
// and Esc closes it once the build has ended.
window.addEventListener('keydown', e => {
  if ($('buildModal').hidden) return;
  e.stopImmediatePropagation();
  if (e.key === 'Escape' && !$('buildClose').hidden) { e.preventDefault(); closeBuildWindow(); }
  else if ((e.ctrlKey || e.metaKey) && !['c', 'r'].includes(e.key.toLowerCase())) e.preventDefault();
}, true);
const mapLabel = id => mapCatalogue?.maps.find(m => m.id === id)?.label ?? id ?? '';
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
  $('projectBuild').disabled = !projectsAvailable() || !project || lastBuild?.state === 'running';
  $('projectClose').hidden = !project;
  // the installs as last known (an install or reset here answers with them), then asked again
  if (playStatus) renderInstalls($('installInfo'), playStatus, mapLabel);
  renderPlayItems();
  refreshInstalls();
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
// Play in game and Remove from game (play.js, tools/viewer/play.py): the game started straight in a battle on the open
// map, in the game install the settings name (the install setting, else the game install the editor reads). With a
// project open it plays the project's build, building first when the last build isn't of what is on screen; with a map
// alone, the original map (no edits). The menu's Installs section says what the editor works with.
// playAfterBuild: { project, attempt } once Build and play has asked for a build (its attempt once the server took it)
let playStatus = null, playAfterBuild = null;
// Land here (Clear map plan, section 4): the landing zone, by id, the next play of the project lands at, else null
let playZone = null;
// The mission the next play is (mission types plan, A4): one of playMissions()'s values, chosen in the play dialog
let playMission = null;
// Whether the next play has saving on (play.py): the game starts at its main menu and a key there opens the battle
let playSaving = false;
// Why a play of the mission (a playMissions() value) has saving on whatever is chosen (Long War's EXALT missions:
// the server's table of kinds), or null
function savingFor(value) {
  const m = headerMissions().find(x => x.value === String(value));
  return playStatus?.missionKinds?.[kindKey(m?.mission)]?.saving ?? null;
}
// the Build panel's saving row for a play (build_options.js show's `saving`)
const savingOption = mission => ({ key: playStatus?.saveKey ?? 'F5', mission, forcedFor: savingFor });
// The missions a play can be, as the play dialog lists them: the map's records (the export's `missions`, the
// header's Mission picker), each with its kind's line from the server's table.
function playMissions() {
  return headerMissions().map(m => ({ value: m.value, label: m.label }));
}
function playMissionNote(value) {
  const m = headerMissions().find(x => x.value === String(value));
  if (m?.entry) {
    return [ADDED_KINDS[m.entry.kind]?.needs,
      ...missionNote(playStatus?.missionKinds, m.mission).split('\n').slice(1)].filter(Boolean).join('\n');
  }
  return missionNote(playStatus?.missionKinds, m?.mission);
}
// a play's mission as the server takes it: a record's index, or an added kind
const missionRequest = value => (String(value).startsWith('kind:') ? String(value).slice(5) : Number(value) || 0);
// The header's picker follows the mission played, so the streams on screen are that mission's.
function followPlayedMission(value) {
  const v = String(value);
  if (v === missionPickValue || !headerMissions().some(m => m.value === v)) return;
  $('mission').value = v;
  $('mission').onchange({ target: $('mission') });
}
const builtAsShown = () => Boolean(project) && !dirty() && lastBuild?.package?.revision === project.revision;
async function refreshInstalls() {
  try { playStatus = await playApi.status(); }
  catch (e) { playStatus = { error: e.message, unavailable: e.status === 404 }; }
  renderInstalls($('installInfo'), playStatus, mapLabel);
  renderPlayItems();
}
// Why the game can't be played now, going by the server's play status (null: it can, or it isn't known yet).
const playBlocked = s => !s ? null : s.error ?? (!s.install?.ready ? s.install?.why ?? 'asking the server' : s.launch && !s.launch.how ? s.launch.why : null);
function renderPlayItems() {
  const s = playStatus, play = $('projectPlay'), maps = $('projectMaps');
  play.hidden = maps.hidden = Boolean(s?.unavailable);
  const ready = Boolean(s?.install?.ready), why = s?.install?.why ?? s?.error;
  const cantStart = ready && s?.launch && !s.launch.how ? s.launch.why : null;
  const where = s?.install?.sameAsLwr ? 'the game install' : 'the install under Installs';
  play.disabled = !projectsAvailable() || !ready || Boolean(cantStart) || lastBuild?.state === 'running';
  play.title = !projectsAvailable() ? 'Play in game starts the game on a map\'s original layout or a project on it: open the map from the map browser (M)'
    : !ready ? `Not now: ${why ?? 'asking the server'}`
    : cantStart ? `Not possible: ${cantStart}`
    : project ? `Start the game in a battle on ${project.doc.name}, in ${where}: no campaign to start, and nothing of the game's own is changed. Build's panel asks first whether to bake the lighting${builtAsShown()
        ? `, or to play its last build as it is (revision ${project.revision}, lighting ${lastBuild.package.quick ? 'not baked' : 'baked'})` : ''}`
    : `Start the game in a battle on the original ${mapLabel(activeMapId)} (no project open, so no edits), in ${where}: no campaign to start, and nothing is installed (but a copy of the map's record where the game comments its records out: the tutorial's map)`;
  maps.title = `The map records of ${where} as the game reads them now: which are in rotation, which a project's build replaces or adds to, and each one switched off or on. It undoes what the editor changed${s?.game?.anything ? ' (there is something of the editor\'s in the game now)' : ''}`;
}
// The "Starting XCOM" message: what is played, what to do at the main menu when saving is on, and anything the play
// goes without or should know, one short paragraph each.
function playedMessage(r) {
  const p = r.played;
  const what = (p.kind === 'project' ? `${p.project?.name}, revision ${p.project?.revision}${p.quick ? ' (lighting not baked)' : ''}`
    : `${mapLabel(p.map)} (original map)`) + (p.mission?.label ? `, ${p.mission.label}` : '');
  return [
    p.how === 'dry' ? `Starting XCOM is left out here (serve --dry-play): ${what}.` : `Starting XCOM: ${what}.`,
    p.how === 'steam' ? 'Pick Enemy Within if the game\'s launcher asks.' : null,
    p.saving ? `At the main menu, press ${p.saving.key} to start the battle.` : null,
    p.squad ? `Squad: ${p.squad.name}, ${p.squad.count} unit${p.squad.count === 1 ? '' : 's'}${p.squad.warnings?.length
      ? ` (${p.squad.warnings.length} warning${p.squad.warnings.length === 1 ? '' : 's'}: Test squad setup lists them)` : ''}.` : null,
    ...(p.mission?.missing ?? []),
    p.introBack ? 'The first mission an earlier version of the editor installed is the game\'s own again.' : null,
    p.note,
  ].filter(Boolean).join('\n');
}
async function playInGame(zoned) {
  if (zoned !== true) playZone = null;
  showPop(null);
  if (!projectsAvailable() || saving) return;
  if (lastBuild?.state === 'running') { flashHint('The build is still running'); return; }
  try { playStatus = await playApi.status(); }
  catch (e) { banner(`Not started: ${e.message}`); return; }
  if (!playStatus.install.ready) { banner(`Not started: ${playStatus.install.why}.`, [['Try again', playAgain]]); return; }
  if (playStatus.launch && !playStatus.launch.how) { banner(`Not started: ${playStatus.launch.why}.`); return; }
  const missions = playMissions();
  if (!project) {
    // a map alone: the play dialog, for which of its missions and whether saving is on
    if (buildOptions.open) return;
    const only = missions.length < 2 ? missions[0]?.value ?? '0' : null;
    buildOptions.show({
      title: `Play ${mapLabel(activeMapId)} in the game`, build: false, ok: 'Play',
      note: `Plays the original map (no edits) in ${playStatus.install.sameAsLwr ? 'the game install' : 'the install under Installs'}.`,
      missions, mission: missionPickValue, missionNote: playMissionNote, saving: savingOption(only ?? missionPickValue),
      squad: squadLine(playStatus.squad),
      onBuild: ({ mission, saving }) => {
        const chosen = mission ?? only ?? 0;
        followPlayedMission(chosen);
        sendPlay({ map: activeMapId, mission: missionRequest(chosen), saving }, mapLabel(activeMapId));
      },
    });
    return;
  }
  if (needsPrepare()) return;
  // A project opens Build's panel (build_options.js): build it, baked or not, and play it once built; or, when its
  // last build is of what is on screen, play that as it is (then the default).
  if (buildOptions.open) return;
  const where = playStatus.install.sameAsLwr ? 'the game install' : 'the install under Installs';
  const current = builtAsShown() ? lastBuild.package : null;
  const what = dirty() ? 'What is on screen, saved first as a new revision,' : `Revision ${project.revision}`;
  const zoneAt = playZone ? zonesNow().findIndex(z => z.id === playZone) : -1;
  buildOptions.show({
    title: `Play ${project.doc.name} in the game${zoneAt >= 0 ? `, landing at zone ${zoneAt + 1}` : ''}`,
    note: `${what} installed in ${where} under its own name, and the game started in a battle on it. ${current
      ? `Its last build (lighting ${current.quick ? 'not baked' : 'baked'}) can be played as it is, or it can be built again first.`
      : 'It is built first and played when the build ends.'}`,
    times: lastBuild?.package?.times ?? {}, bakeNote: bakeNote(),
    missions, mission: missionPickValue, missionNote: playMissionNote, saving: savingOption(missionPickValue),
    squad: squadLine(playStatus.squad),
    ok: 'Build and play', onBuild: ({ quick, mission, saving }) => playChosen(quick ? 'quick' : 'full', mission, saving),
    last: current ? 'Play last build' : null, onLast: ({ mission, saving }) => playChosen('last', mission, saving),
  });
}
async function playChosen(kind, mission = null, saving = false) {
  if (!project || lastBuild?.state === 'running') return;
  playMission = mission === null || mission === undefined ? missionPickValue : String(mission);
  playSaving = Boolean(saving);
  followPlayedMission(playMission);
  if (kind === 'last') { if (builtAsShown()) sendPlay(withZone({ project: project.doc.id }), project.doc.name); return; }
  // save and build it, and play it when that build ends (followBuild)
  playAfterBuild = { project: project.doc.id, attempt: null };
  await buildProject(kind === 'quick');
  // the build didn't start (not saved, or refused: the build queue holds the slot): no later build plays
  if (!playAfterBuild?.attempt) playAfterBuild = null;
}
async function sendPlay(request, label) {
  flashHint(`Starting the game on ${label}…`);
  try { const r = await playApi.start(request); playStatus = r; banner(playedMessage(r), [], playedFor(r)); }
  catch (e) { banner(e.message, [['Try again', playAgain]]); }
}
// how long the "Starting XCOM …" message stays: a play with saving on keeps it until dismissed (it says the key)
const playedFor = r => (r?.played?.saving ? {} : { timeout: PLAYED_FOR });
const playAgain = () => playInGame(playZone !== null);
const withZone = request => ({ ...request, ...(playZone ? { zone: playZone } : {}), mission: missionRequest(playMission ?? missionPickValue),
                               saving: playSaving });
// Land here: Play in game for the project, the squad landing at the picked zone (under LWR that zone's line alone is
// installed; a zone that is one of the map's own landings opens on its spawn group). The build must carry the zone's
// id, so a project still on the map's own lines takes them in first (one undo step), which makes it a change to build.
function landHere() {
  if (!pickedZone || !project) return;
  if (!landingZones) setZones(zonesNow(), 'Took the map\'s landing zones into the project');
  playZone = pickedZone;
  playInGame(true);
}
const PLAYED_FOR = 12000;     // ms the "Starting XCOM …" message stays (a failure stays until dismissed)
// After a build Play in game asked for: the outcome shows in the build window, or in a banner once it's closed.
async function playBuilt(id) {
  buildView.install = { state: 'running' };
  try {
    const r = await playApi.start(withZone({ project: id }));
    playStatus = r;
    buildView.install = { state: 'done', message: playedMessage(r), saving: Boolean(r.played?.saving) };
  }
  catch (e) { buildView.install = { state: 'failed', message: e.message }; }
  if (!$('buildModal').hidden) renderBuild();
  else if (buildView.install.state === 'failed') banner(buildView.install.message, [['Try again', playAgain]]);
  else banner(buildView.install.message, [], buildView.install.saving ? {} : { timeout: PLAYED_FOR });
}
// Opening another project reloads the page on its map (the browser asks first if there are unsaved changes).
function loadProject(p) { if (p.id !== project?.doc.id) goTo({ map: p.map, scene: null, project: p.id }); }
// The game install and the editor's checks (setup.js): a first run asks for the install before anything else.
const setupDialog = createSetupDialog({
  els: { root: $('setupDialog'), form: $('setupForm'), title: $('setupTitle'), intro: $('setupIntro'), found: $('setupFound'),
         folder: $('setupFolder'), browse: $('setupBrowse'), ok: $('setupOk'), close: $('setupClose'), checks: $('setupChecks'),
         message: $('setupMessage'), version: $('setupVersion') },
  // the server lists the new install's maps: open the page afresh on them
  onChosen: () => setTimeout(() => location.reload(), 600) });
// Build's panel: whether to bake the lighting, for Build (openBuild) and Play in game (playInGame).
const buildOptions = createBuildOptions({
  els: { root: $('buildOptions'), form: $('buildForm'), title: $('buildOptionsTitle'), note: $('buildOptionsNote'),
         bake: $('buildBake'), bakeRow: $('buildBakeRow'), bakeNote: $('buildBakeNote'), estimate: $('buildEstimate'), ok: $('buildOptionsOk'), last: $('buildOptionsLast'),
         missionRow: $('buildMissionRow'), mission: $('buildMission'), missionNote: $('buildMissionNote'),
         mapBakeHelp: $('buildMapBakeHelp'), testBakeHelp: $('buildTestBakeHelp'),
         savingRow: $('buildSavingRow'), saving: $('buildSaving'), savingHelp: $('buildSavingHelp'),
         squadRow: $('buildSquadRow'), squad: $('buildSquad'),
         close: $('buildOptionsClose'), cancel: $('buildOptionsCancel') },
  onSquad: () => squadDialog.show() });
// Test squad setup (squad.js; Settings menu, and the play dialog's squad line): the one squad every play lands with.
// A save refreshes the play status, so the squad line of an open play dialog and the Settings menu follow it.
const squadDialog = createSquadDialog({
  els: { root: $('squadDialog'), form: $('squadForm'), title: $('squadTitle'), intro: $('squadIntro'), problem: $('squadProblem'),
         name: $('squadName'), units: $('squadUnits'), add: $('squadAdd'), copy: $('squadCopy'), remove: $('squadRemove'),
         up: $('squadUp'), down: $('squadDown'), count: $('squadCount'), unit: $('squadUnit'), issues: $('squadIssues'),
         wide: $('squadWide'), status: $('squadStatus'), exportButton: $('squadExport'), importButton: $('squadImport'),
         importFile: $('squadImportFile'), reset: $('squadReset'), cancel: $('squadCancel'), save: $('squadSave'),
         close: $('squadClose') },
  onSaved: () => refreshSquadLine(true),
});
async function refreshSquadLine(saved = false) {
  try { playStatus = await playApi.status(); }
  catch (e) { if (saved) flashHint(`Saved; the play status could not be read: ${e.message}`); return; }
  const line = squadLine(playStatus.squad);
  if (buildOptions.open) buildOptions.setSquad(line);
  const menu = $('settingsSquadLine');
  menu.textContent = line ? line.text : 'The squad is not known: this server starts no game.';
  menu.title = line?.title ?? '';
  menu.classList.toggle('warn', Boolean(line?.warn));
  if (saved && !buildOptions.open) flashHint('Saved the test squad: the next Play in game lands with it');
}
$('settingsSquad').onclick = () => { showPop(null); squadDialog.show(); };
const prefabTest = createPrefabTest({
  els: { root: $('prefabTestModal'), icon: $('prefabTestIcon'), title: $('prefabTestTitle'), note: $('prefabTestNote'),
         bar: $('prefabTestBar'), status: $('prefabTestStatus'), issues: $('prefabTestIssues'), details: $('prefabTestDetails'),
         log: $('prefabTestLog'), close: $('prefabTestClose'), cancel: $('prefabTestCancel'), launch: $('prefabTestLaunch') },
  uuid, onPick: actor => selectActors([actor]),
});
// The builder's Problems check (plan "sturdier prefabs", R5): what a test of the prefab as it stands would say,
// asked of the server without building anything (POST /prefab-tests/check: the test's prepare step). The chip under
// the size line counts the pieces that would be left out and the warnings; it opens the list, where a row selects
// and frames its piece. Checked when a prefab is opened and saved, and on demand; after an edit the chip says the
// list is from before it.
const problems = { result: null, key: null, running: false, error: null, open: false };
async function checkPrefab() {
  if (!builderMode || builder.loading || problems.running) return;
  const doc = builderDocument(), key = builderKey();
  if (!doc.pieces.length && !doc.buildings.length) { Object.assign(problems, { result: null, error: null, key }); problemsPaint(); return; }
  problems.running = true; problemsPaint();
  try {
    const response = await fetch('/prefab-tests/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ snapshot: doc }) });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(value.error ?? `the server said ${response.status}`);
    Object.assign(problems, { result: value, error: null, key });
  } catch (error) { Object.assign(problems, { result: null, error: error.message, key }); }
  finally { problems.running = false; problemsPaint(); }
}
function problemsPaint(stale = Boolean(problems.result) && builderMode && !builder.loading && problems.key !== builderKey()) {
  const box = $('builderProblems'), chip = $('problemsChip'), list = $('problemsList'), r = problems.result;
  box.hidden = !builderMode || builder.loading;
  if (box.hidden) return;
  const issues = r?.issues ?? [], gone = r?.leftOut ?? 0, warnings = issues.length - gone;
  chip.textContent = problems.running ? 'Checking…' : problems.error ? 'Not checked' : !r ? 'Check for problems'
    : !r.ready ? 'Not checked yet' : r.refused ? 'Can\'t be tested'
    : (gone || warnings ? [gone && `${gone} left out`, warnings && plural(warnings, 'warning')].filter(Boolean).join(' · ') : 'No problems')
      + (stale ? ' (before the last edit)' : '');
  chip.classList.toggle('warn', Boolean(gone || r?.refused || problems.error));
  chip.title = problems.error ? `The check could not be run: ${problems.error}. Click to try again.`
    : !r ? 'What Test in game would say of this prefab, without building it: the pieces it would leave out and its warnings'
    : !r.ready ? r.message : `${r.refused ? `${r.refused} ` : ''}Click to ${problems.open ? 'close' : 'open'} the list${stale ? '; it is from before the last edit: Check again in the list brings it up to date' : ''}.`;
  list.hidden = !problems.open || !r?.ready;
  list.replaceChildren();
  if (list.hidden) return;
  const again = text(list, 'li', '', 'again'), button = text(again, 'button', problems.running ? 'Checking…' : 'Check again');
  button.type = 'button'; button.disabled = problems.running; button.onclick = () => checkPrefab();
  if (r.stage) text(again, 'small', ` test stage ${r.stage[0]} × ${r.stage[1]} tiles, ${r.stage[2]} levels`);
  if (r.refused) text(list, 'li', r.refused, 'leftout');
  for (const issue of issues.slice(0, 200)) {
    const li = text(list, 'li', issue.actor && !issue.leftOut ? `${short(issue.actor)} · ${issue.message}` : issue.message, issue.leftOut ? 'leftout' : '');
    if (issue.actor) { li.classList.add('pick'); li.title = `Select ${short(issue.actor)}`; li.onclick = () => selectActors([issue.actor]); }
  }
  if (issues.length > 200) text(list, 'li', `… and ${issues.length - 200} more`);
  if (!issues.length && !r.refused) text(list, 'li', 'Nothing would be left out, and the compiler has no warning.');
}
$('problemsChip').onclick = () => {
  if (!problems.result?.ready || problems.error) { checkPrefab(); return; }
  problems.open = !problems.open; problemsPaint();
};
// How many levels the test's stage gets (prefab_stage.py stage_levels): what the prefab needs, 18 at least, 30 at most.
const testStageLevels = bounds => Math.min(PREFAB_GRID_LEVELS, Math.max(PREFAB_PLAYED_LEVELS, Math.ceil((bounds[5] - 0.5) / 64)));
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
async function openPrefabTest() {
  showPop(null);
  if (!builderMode || builder.loading || buildOptions.open || prefabTest.showExisting()) return;
  let target;
  try {
    const status = await playApi.status();
    const blocked = playBlocked(status);
    if (blocked) { banner(blocked, [['Try again', openPrefabTest]]); return; }
    target = status.install.folder;
    playStatus = status;
  } catch (e) { banner(e.message, [['Try again', openPrefabTest]]); return; }
  if (buildOptions.open || prefabTest.showExisting()) return;
  const { size } = builderRecords(), [x, y] = size.tiles;
  const label = builder.doc.revision ? builder.doc.name : 'Unsaved prefab';
  const revision = dirty() ? 'Unsaved changes included.' : builder.doc.revision ? `Revision ${builder.doc.revision}.` : '';
  buildOptions.show({
    title: builder.doc.revision ? `Test ${label} in game` : 'Test unsaved prefab in game',
    note: [`${x} × ${y} tiles, height ${size.bounds[2].toFixed(1)}–${size.bounds[5].toFixed(1)}, on a stage ${testStageLevels(size.bounds)} levels high`
      + '.',
      Math.max(x, y) > PREFAB_TILES ? `It is too large for the ${PREFAB_TILES} by ${PREFAB_TILES} tile stage: the test will say so.` : '',
      revision, `Game install ${target}`].filter(Boolean).join(' '),
    ok: 'Build and test', bake: false, prefabTest: true, saving: { key: playStatus?.saveKey ?? 'F5' },
    squad: squadLine(playStatus?.squad),
    onBuild: ({ quick, saving }) => prefabTest.start(builderDocument(), quick, dirty() || !builder.doc.revision, saving),
  });
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
// build state (its package), even when the server has gone on to the next row.
async function queueCall(method, url, body) {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                                      body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store' });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(value.error || `The server said ${response.status}`), { status: response.status, body: value });
  return value;
}
const buildQueue = createQueueController({
  get: () => queueCall('GET', '/manager/queue.json'),
  post: (action, body) => queueCall('POST', action === 'add' ? '/manager/queue' : `/manager/queue/${action}`, body),
  onChange: (state, info) => { renderQueueChip(state, info); projectManager?.queueChanged(state, info); followQueueForProject(state, info); },
});
function renderQueueChip(state, info) {
  const chip = $('queueChip'), words = chipWords(state);
  chip.hidden = !words;
  if (!words) return;
  chip.textContent = words.text + (info?.offline ? ' (not answering)' : '');
  chip.classList.toggle('warn', words.warn);
  chip.title = `The build queue: ${words.text}. Click to open the project manager and follow it`;
}
function followQueueForProject(state, info) {
  if (!project || builderMode) return;
  const id = project.doc.id, mine = state?.items?.find(i => i.project === id);
  const building = Boolean(mine && (mine.state === 'starting' || mine.state === 'building'));
  const shown = lastBuild?.state === 'running' && lastBuild.job?.origin === 'queue';
  if (building !== shown || info?.ended?.some(i => i.project === id))
    projectApi.buildStatus(id).then(s => { if (project?.doc.id === id) { lastBuild = s; renderPlayItems(); } }, () => {});
}
$('queueChip').onclick = () => showProjectManager();
window.addEventListener('focus', () => buildQueue.refresh());
// Build in the manager saves the open project first when it is ticked and has unsaved changes, as the editor's own
// Build does; a save that fails or is refused queues nothing, and neither does a project switched meanwhile.
async function ensureSavedFor(ids) {
  if (builderMode || !project || !ids.includes(project.doc.id) || !dirty()) return true;
  const id = project.doc.id;
  const saved = await saveProject();
  return Boolean(saved) && project?.doc.id === id && !dirty();
}
// The project manager (manager.js): every project and its last build, to install or zip several at once, or to build.
const projectManager = createProjectManager({
  els: { root: $('managerDialog'), form: $('managerForm'), close: $('managerClose'), search: $('managerSearch'), show: $('managerShow'),
         sort: $('managerSort'), all: $('managerAll'), shownLabel: $('managerShown'), list: $('managerList'), count: $('managerCount'),
         pickNone: $('managerPickNone'), allModes: $('managerAllModes'), picked: $('managerPicked'), message: $('managerMessage'),
         pack: $('managerPack'), projectFiles: $('managerProjectFiles'), install: $('managerInstall'), where: $('managerWhere'), build: $('managerBuild'),
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
  if (gameMaps.open || projectManager.open || fileDialog.open || mapBrowser?.open || setupDialog.open || buildOptions.open || !$('buildModal').hidden) return;
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
  if (precache.open || gameMaps.open || projectManager.open || fileDialog.open || mapBrowser?.open || setupDialog.open || buildOptions.open || !$('buildModal').hidden) return;
  showPop(null);
  if (placing) stopPlacing();
  precache.show();
}
function showProjectManager() {
  if (gameMaps.open || projectManager.open || fileDialog.open || mapBrowser?.open || setupDialog.open || buildOptions.open || !$('buildModal').hidden) return;
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

// Picking: the first visible, unclipped piece under a screen point, or null.
function rayAt(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2((clientX-rect.left)/rect.width*2-1, -(clientY-rect.top)/rect.height*2+1), camera);
  return ray;
}
function pick(clientX, clientY) {
  return rayAt(clientX, clientY).intersectObjects(pickables).find(h => {
    const root = roots.get(h.object.userData.objectId);
    return root?.visible && (root.userData.clippingPlanes || []).every(plane => plane.distanceToPoint(h.point) >= -0.01);
  }) ?? null;
}
let pointer = null;   // the last pointer position over the view, for paste
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
    lightRadius=Math.max(700,size.length()*0.55);sun.target.position.copy(center);
    Object.assign(sun.shadow.camera,{left:-lightRadius,right:lightRadius,top:lightRadius,bottom:-lightRadius,near:1,far:lightRadius*6});
    sun.shadow.camera.updateProjectionMatrix();applyLighting();
  }
}
async function texture(id, color = true, sampling = {channel:0,scale:[1,1]}) {
  if (!id || !data.textures[id]) return null;
  const key = `${id}:${color}:${JSON.stringify(sampling)}`;
  if (!texturePromises.has(key)) texturePromises.set(key, (async () => {
    const tex = await textureLoader.loadAsync(assetUrl(data.textures[id].url));
    tex.colorSpace = color && data.textures[id].srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    // UE UVs and extracted PNGs both use a top-left origin. Preserve that
    // convention, as glTF does; flipping the upload mirrors every atlas in V.
    tex.flipY = false;
    tex.channel = sampling.channel;
    tex.repeat.set(...sampling.scale);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    return tex;
  })());
  return texturePromises.get(key);
}
async function material(id,overrideTint=null) {
  const info = data.materials[id];
  if (!info) return withLocalLights(new THREE.MeshPhongMaterial({color: 0xbc628f, side: THREE.DoubleSide}));
  // A fractured mesh's inside faces, which the game draws only where a fragment has broken off (export 14)
  if (info.render?.family === 'hidden') return new THREE.MeshBasicMaterial({visible: false});
  if (info.render?.constantColor) {
    const Type=info.render.unlit || info.render.family === 'fogged-civilian' ? THREE.MeshBasicMaterial : THREE.MeshPhongMaterial;
    return withLocalLights(new Type({
      color:new THREE.Color(...info.render.constantColor),side:info.twoSided ? THREE.DoubleSide : THREE.FrontSide,
      transparent:info.blend === 'BLEND_Translucent',depthWrite:info.blend !== 'BLEND_Translucent',
    }));
  }
  if (info.blend === 'BLEND_Modulate') return new THREE.MeshBasicMaterial({
    color:0xa8b9c2,transparent:true,opacity:0.35,depthWrite:false,blending:THREE.MultiplyBlending,premultipliedAlpha:true,
    side: info.twoSided ? THREE.DoubleSide : THREE.FrontSide,
  });
  const glass = ['BLEND_Translucent', 'BLEND_Additive'].includes(info.blend);
  const masked = ['diffuse-alpha','packed-alpha'].includes(info.render?.opacitySource);
  const diffuse = await texture(info.diffuse,true,info.render?.uv);
  const alpha = await texture(info.opacity,false,info.render?.opacityUv);
  const emission = await texture(info.emissive,false,info.render?.emissiveUv);
  const energy = info.render?.family === 'alien-energy';
  const glow = energy ? (info.vectors.DoorColor || [0.4,0.8,3,1]) : (info.vectors.EmsColor_EmsValue || [0,0,0,0]);
  const tint = overrideTint || info.vectors.TintColor || [1, 1, 1];
  const spec = info.vectors.SpcColor_SpcGloss || [0.2, 0.2, 0.2, 12];
  const mat = new THREE.MeshPhongMaterial({
    color: energy ? new THREE.Color(...glow.slice(0,3)) : glass ? 0x7597a2 : diffuse ? new THREE.Color(...tint.slice(0,3)) : 0x9c6b93,
    map: energy ? emission : diffuse, alphaMap:alpha,
    emissive: new THREE.Color(...(emission || energy ? glow.slice(0,3) : [0,0,0])),
    emissiveMap: emission, emissiveIntensity: energy ? 1 : Math.max(0,glow[3] || 0),
    specular: new THREE.Color(...spec.slice(0,3).map(v => Math.min(0.45,Math.max(0,v*0.1)))), shininess: Math.max(1, spec[3] || 12),
    transparent: glass, opacity: glass ? 0.32 : 1, depthWrite: !glass,
    alphaTest: masked ? (info.alphaTest ?? 0.4) : 0, side: info.twoSided || glass ? THREE.DoubleSide : THREE.FrontSide,
  });
  // Packed UE normals need family-specific decoding. Retain them in the manifest
  // rather than silently treating the DXT alpha channel as an ordinary RGB map.
  return withLocalLights(mat);
}
// Meshes and materials load once and are shared by every piece that uses them, copies included.
const geometryCache = new Map(), materialCache = new Map();
// Spawned preview pieces (and copies of them) carry their own tint.
function materialKey(obj, id) {
  const tint = obj.provenance?.type === 'spawn' || obj.added?.tinted ? obj.tint : null;
  return [`${id}:${JSON.stringify(tint)}`, tint];
}
// The no-op catch only stops an early failure being reported as unhandled before its piece is reached.
// Once loaded, a value can also be had at once with loaded(), for drawing in the middle of a frame.
const settled = new WeakMap();
function track(map, key, start) {
  if (!map.has(key)) { const promise = start(); promise.then(v => settled.set(promise, v), () => {}); map.set(key, promise); }
}
const loaded = (map, key) => settled.get(map.get(key));
// A drawn-only copy of some pieces (the placing preview, a piece-list thumbnail) from the loaded meshes and
// materials, or `override` for every part. It is never picked. parts: { source, matrix }; `frame` moves them all.
function previewGroup(parts, override, frame) {
  const group = new THREE.Group();
  for (const { source, matrix, values } of parts) {
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
    const gltf = loaded(geometryCache, source.mesh);
    if (!gltf) continue;
    const root = data.meshes[source.mesh].kind === 'skeletal' ? cloneSkeleton(gltf.scene) : gltf.scene.clone(true);
    let i = 0;
    root.traverse(part => {
      if (!part.isMesh) return;
      part.material = override ?? loaded(materialCache, materialKey(source, source.materials[i])[0]) ?? ghostMaterial;
      part.raycast = () => {}; i++;
    });
    root.matrix.multiplyMatrices(frame, matrix); root.matrixAutoUpdate = false;
    group.add(root);
  }
  return group;
}
// The box round some pieces' meshes, in `frame` (for a piece-list entry: its pivot actor's own frame).
function boundsOf(sources, frame) {
  const box = new THREE.Box3(), part = new THREE.Box3(), m = new THREE.Matrix4();
  for (const source of sources) {
    const gltf = loaded(geometryCache, source.mesh);
    if (!gltf) continue;
    const placed = frame.clone().multiply(new THREE.Matrix4().fromArray(source.matrix));
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(mesh => {
      if (!mesh.isMesh) return;
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      box.union(part.copy(mesh.geometry.boundingBox).applyMatrix4(m.multiplyMatrices(placed, mesh.matrixWorld)));
    });
  }
  return box;
}
// One piece's render root, built from its mesh file. Copies are built this way too: cloning a placed root
// would also deep-copy its userData through JSON, materials and textures included.
async function buildRoot(obj) {
  track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[obj.mesh].url)));
  const base = await geometryCache.get(obj.mesh);
  const root = data.meshes[obj.mesh].kind === 'skeletal' ? cloneSkeleton(base.scene) : base.scene.clone(true);
  root.userData.source = obj; root.visible = !obj.hidden && !obj.environment;
  root.userData.flags = obj.initialFlags ? { ...obj.initialFlags } : null;     // its piece flags as the project sets them
  const parts = []; root.traverse(child => { if (child.isMesh) parts.push(child); });
  for (let i=0; i<parts.length; ++i) {
    const [key, tint] = materialKey(obj, obj.materials[i]);
    track(materialCache, key, () => material(obj.materials[i], tint));
    parts[i].material = await materialCache.get(key);
    parts[i].userData.baseMaterial = parts[i].material;
    parts[i].castShadow = !parts[i].material.transparent;
    parts[i].receiveShadow = true;
    parts[i].userData.objectId = obj.id;
  }
  root.userData.parts = parts;
  root.matrix.fromArray(obj.matrix); root.matrixAutoUpdate = false; root.matrixWorldNeedsUpdate = true;
  return root;
}
function addRoots(list) {
  liveCache = null;
  for (const root of list) {
    roots.set(root.userData.source.id, root); content.add(root); pickables.push(...root.userData.parts);
  }
}
// Removed roots keep their geometry: an undo puts the same objects back.
function removeRoots(list) {
  const parts = new Set(list.flatMap(root => root.userData.parts));
  liveCache = null;
  for (const root of list) { roots.delete(root.userData.source.id); content.remove(root); }
  pickables.splice(0, pickables.length, ...pickables.filter(p => !parts.has(p)));
}
// The piece's unedited matrix: as exported (for a copy, where it was placed), or at its study position in sample mode.
function baseMatrix(root) {
  const obj = root.userData.source, matrix = new THREE.Matrix4().fromArray(obj.matrix);
  if (data.scope === 'sample' && !originalPositions && !obj.added) {
    const carLocation = data.objects.find(o => short(o.actor) === 'XComDestructibleActor_20')?.location || [0,0,0];
    const name = short(obj.actor);
    const anchor = name === 'XComLevelActor_242' ? [0,0,0] : name === 'XComDecoFracLevelActor_9' ? [-230,0,0] : [150,1,0];
    const source = name === 'XComFracLevelActor_10' ? carLocation : obj.location;
    matrix.elements[12] += anchor[0] - source[0];
    matrix.elements[13] += anchor[1] - source[2];
    matrix.elements[14] += anchor[2] - source[1];
  }
  return matrix;
}
function placeObjects() {
  for (const root of roots.values()) {
    root.matrix.copy(baseMatrix(root)); root.matrixAutoUpdate = false;
    if (root.userData.edit) root.matrix.premultiply(root.userData.edit);
    root.matrixWorldNeedsUpdate = true;
  }
  content.updateMatrixWorld(true);
  if (selected) select(selected, false, true);
}
// Search results: only while the search box has focus and holds text. Pieces hidden in the current view are left out.
const MAX_RESULTS = 60;
let resultIndex = -1;
function catalogue() {
  const search = $('search'), list = $('objects');
  const filter = search.value.trim().toLowerCase();
  list.replaceChildren(); resultIndex = -1;
  list.hidden = !filter || document.activeElement !== search;
  if (!filter || !data) return;
  const matches = [];
  for (const [id, root] of roots) {
    const obj = root.userData.source, name = data.meshes[obj.mesh].name;
    if (isStream(obj) && !streamSet.has(obj.stream)) continue;
    if (obj.environment || obj.hidden && !((obj.layer === 'inherited' || isStream(obj)) && obj.hiddenBy == null && !$('hideHelpers').checked)) continue;
    if (root.userData.tacticalExcluded || root.userData.deleted) continue;
    if (`${name} ${obj.actor}`.toLowerCase().includes(filter)) matches.push([id, obj, name]);
  }
  for (const [id, obj, name] of matches.slice(0, MAX_RESULTS)) {
    const button = text(list, 'button', '', 'piece');
    Object.assign(button, { type: 'button', title: `${name}\n${obj.actor}` });
    button.dataset.id = id; button.setAttribute('role', 'option');
    button.classList.toggle('active', id === selected);
    const label = text(button, 'span', '');
    text(label, 'strong', short(name)); text(label, 'small', short(obj.actor));
    const others = gizmo.linkedCount(id), group = liveGroup(memberOf(obj));
    if (group) text(button, 'span', 'group', 'tag group').title = `In a group of ${plural(liveKeys(group).length, 'piece')}`;
    if (isStream(obj)) text(button, 'span', data.streams?.[obj.stream]?.kind === 'lwr' ? 'LWR patch' : 'mission', 'tag').title = `From ${obj.stream}: not editable`;
    else if (obj.hidden) text(button, 'span', 'hidden helper', 'tag');
    else if (obj.cover) text(button, 'span', isFloor(obj.cover) ? 'invisible floor' : isBlocker(obj.cover) ? 'blocker' : 'cover block', 'tag').title = isFloor(obj.cover)
      ? 'An invisible floor units can stand on' : isBlocker(obj.cover) ? 'An invisible block units can\'t walk into, with no cover' : 'An invisible block that gives cover';
    else if (obj.added) text(button, 'span', others ? `added · +${others}` : 'added', 'tag').title = `A copy of ${short(obj.added.from.actor)}`;
    else if (others) text(button, 'span', `+${others} linked`, 'tag').title = `Moves with ${plural(others, 'other piece')}`;
    button.onclick = e => choose(id, e.ctrlKey || e.shiftKey || e.metaKey);
  }
  text(list, 'div', matches.length
    ? `${matches.length} ${matches.length === 1 ? 'match' : 'matches'}${matches.length > MAX_RESULTS ? `, first ${MAX_RESULTS} shown` : ''} · ↑↓ to choose · Enter selects and frames · Esc clears`
    : 'No visible piece matches', 'resultsfoot');
  highlightResult(0);
}
function highlightResult(index) {
  const items = [...$('objects').querySelectorAll('.piece')];
  if (!items.length) return;
  resultIndex = (index + items.length) % items.length;
  items.forEach((b, i) => b.classList.toggle('hl', i === resultIndex));
  items[resultIndex].scrollIntoView({ block: 'nearest' });
}
// Picking a result selects the piece and frames it; Ctrl/Shift adds it to the selection and keeps the list open.
function choose(id, add) {
  select(id, add);
  if (add) { catalogue(); return; }
  if (roots.get(id)) frame(roots.get(id));
  $('search').blur();
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
// Building-floor listings as the Build gives them (floors.js copyFloors, the Build's native_copy.copy_floors, which
// pass the same cases): an original where the map has it keeps its own; a copy, or an original moved, joins the floor
// it now stands in, by the box of its original's mesh vertices carried to where it stands (floorAt). Exports before
// 15 have no floor volumes: their copies are listed nowhere, as before.
let originalParts = null;
const vertexBoxes = new Map(), vertex = new THREE.Vector3();
// The export's own components of an original actor, by its key (package|level|actor).
function partsOf(key) {
  if (!originalParts) {
    originalParts = new Map();
    for (const x of data.objects) { const k = targetKey(fromOf(x)); if (!originalParts.has(k)) originalParts.set(k, []); originalParts.get(k).push(x); }
  }
  return originalParts.get(key) ?? [];
}
// The export's own piece an added piece was copied from (one of its components), or the piece itself.
const originalOf = o => (o.added ? partsOf(targetKey(o.added.from))[0] ?? null : o);
// An original actor's box [x0, x1, y0, y1, z0, z1] of its meshes' vertices where the map has it (the Build's piece_box).
function vertexBox(original) {
  const key = targetKey(fromOf(original));
  if (vertexBoxes.has(key)) return vertexBoxes.get(key);
  const box = [Infinity, -Infinity, Infinity, -Infinity, Infinity, -Infinity], m = new THREE.Matrix4();
  for (const part of partsOf(key).length ? partsOf(key) : [original]) {
    const gltf = loaded(geometryCache, part.mesh);
    if (!gltf) return null;
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(mesh => {
      if (!mesh.isMesh) return;
      m.fromArray(part.matrix).multiply(mesh.matrixWorld);
      const position = mesh.geometry.attributes.position;
      for (let i = 0; i < position.count; i++) {
        vertex.fromBufferAttribute(position, i).applyMatrix4(m);
        const g = [vertex.x, vertex.z, vertex.y];
        for (let k = 0; k < 3; k++) { box[2 * k] = Math.min(box[2 * k], g[k]); box[2 * k + 1] = Math.max(box[2 * k + 1], g[k]); }
      }
    });
  }
  vertexBoxes.set(key, box);
  return box;
}
// A box carried as a piece is carried from one actor pose to another (the Build's moved_box): its turned corners' box.
function movedBox(box, before, after) {
  const m = actorMatrix(after.location, after.rotation).multiply(actorMatrix(before.location, before.rotation).invert());
  const out = [Infinity, -Infinity, Infinity, -Infinity, Infinity, -Infinity];
  for (const x of box.slice(0, 2)) for (const y of box.slice(2, 4)) for (const z of box.slice(4, 6)) {
    vertex.set(x, z, y).applyMatrix4(m);
    const g = [vertex.x, vertex.z, vertex.y];
    for (let k = 0; k < 3; k++) { out[2 * k] = Math.min(out[2 * k], g[k]); out[2 * k + 1] = Math.max(out[2 * k + 1], g[k]); }
  }
  return out;
}
// A piece's world box [x0, x1, y0, y1, z0, z1] in game axes from what is drawn of it, vertex by vertex when `precise`.
const drawnBox = new THREE.Box3();
function boxOf(root, precise = false) {
  root.updateMatrixWorld(true);
  drawnBox.setFromObject(root, precise);
  return drawnBox.isEmpty() ? null : [drawnBox.min.x, drawnBox.max.x, drawnBox.min.z, drawnBox.max.z, drawnBox.min.y, drawnBox.max.y];
}
// The classes a building floor lists (the Build's buildings.LISTED): a StaticMeshActor never hides.
const LISTED_CLASSES = new Set(['XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComFracLevelActor', 'XComDecoFracLevelActor',
                                'XComInteractiveLevelActor', 'XComLadder', 'XComCollectible', 'KAsset']);
// Where the project's buildings list a piece, by the game editor's rule as the Build applies it (floors.js
// touchedFloors and ruleListing; tools/bake/buildings.py): from the box of what is drawn of it where it stands.
function projectListings(root) {
  const o = root.userData.source;
  if (!allBuildings().some(b => b.project) || o.cover || o.hidden || !LISTED_CLASSES.has(o.actorClass)) return [];
  const key = `${buildingsVersion}|${root.matrix.elements.join(',')}`;
  if (root.userData.ownListingsKey === key) return root.userData.ownListings;
  const out = [], rough = boxOf(root)?.slice();
  const template = o.added && (o.foreign ? foreignTemplates.get(`${targetKey(o.added.from)}|${o.component}`) : originalOf(o));
  const sourceBuildings = template && (template.foreign?.buildings ?? data.buildings);
  const before = template && { location: template.floorLocation ?? template.location, rotation: template.rotation };
  const pose = before && placedPose(o, root.matrix);
  const authored = new Set();
  // The rule's answer for a box against floors, as [[floor, cutdownFloor]]. A piece that collides with nothing is on
  // none: the game lists what touches a floor volume, and only a piece that collides touches one (F-87; `collides`
  // false in exports that carry it, the Build's native_copy.collides).
  const collides = o.collides !== false;
  const rule = (at, floors) => (collides ? ruleListing(touchedFloors(at, floors), Boolean(o.cutout)).map(l => [l.floor, l.cutdownFloor]) : []);
  if (rough) {
    let box = null;
    for (const b of allBuildings()) {
      if (!b.project) continue;
      if (b.map) {
        // one of the map's own, changed (map buildings plan, section 3): what the map saved where the rule's answer
        // did not change, with the old boxes at the piece's old pose against the new boxes at its new pose
        const original = o.foreign ? null : originalOf(o);
        const saved = (original?.floors ?? []).filter(l => l.building === b.map.id).map(l => [l.floor, l.cutdownFloor]);
        if (!saved.length && !touchedFloors(rough, b.floors, -Infinity).length) continue;
        box ??= boxOf(root, true)?.slice();
        if (!box) break;
        const old = !original ? null : !o.added && !root.userData.edit ? box : vertexBox(original);
        const fmap = floorMapOf(b.map.floors.map(f => f.volumes.map(short)), b.project.floors.map(f => f.volumes));
        const oldRule = old ? rule(old, b.map.floors) : [];
        const newRule = old || !original ? rule(box, b.floors) : [];
        for (const [floor, cut] of carriedListing(saved, oldRule, newRule, fmap).entries) out.push({ building: b.id, floor, cutdownFloor: cut });
        continue;
      }
      // a building that comes from the piece's own map: what the map saved (its hand-made inclusion and exclusion
      // lists among it) where the rule gives the same with the map's boxes as with the building's, which may have been
      // edited since (the Build's buildings.members with the compiler's carry)
      const match = sourceBuildings && sourceFloorMatch(sourceBuildings, b.floors, before, pose);
      if (match) {
        authored.add(b.project.id);
        const saved = (template.floors ?? []).filter(l => l.building === match.building.id).map(l => [l.floor, l.cutdownFloor]);
        box ??= boxOf(root, true)?.slice();
        const [oldRule, newRule] = box ? [rule(box, match.moved), rule(box, b.floors)] : [[], []];
        for (const [floor, cut] of carriedListing(saved, oldRule, newRule, match.floorMap).entries) out.push({ building: b.id, floor, cutdownFloor: cut });
        continue;
      }
      if (!touchedFloors(rough, b.floors, -Infinity).length) continue;
      box ??= boxOf(root, true)?.slice();
      if (!box) break;
      for (const [floor, cut] of rule(box, b.floors)) out.push({ building: b.id, floor, cutdownFloor: cut });
    }
  }
  root.userData.authoredFloors = authored;
  root.userData.ownListingsKey = key; root.userData.ownListings = out;
  return out;
}
const listingsNow = root => (allBuildings().some(b => b.project) ? [...mapListings(root), ...projectListings(root)] : mapListings(root));
// Where the map's own buildings that are not changed list a piece: its saved listings, or a copy's moved to the floor
// it stands in (copyFloors, as the Build's edit_floor_caches). A changed or deleted one lists nothing here: its
// listing is projectListings', and a copy standing in a changed one is left to it (its floor found by its new boxes).
function mapListings(root) {
  const o = root.userData.source, edits = mapEdits(), keep = l => !edits.exportIds.has(l.building);
  if (!o.added && !root.userData.edit) return edits.exportIds.size ? (o.floors || []).filter(keep) : o.floors || [];
  const original = originalOf(o), listings = original?.floors ?? [];
  if (!listings.length || !(data.exporterVersion >= 15) || !data.buildings?.length) return [];
  const key = `${root.matrix.elements.join(',')}|${buildingsVersion}`;
  if (root.userData.listingsKey === key) return root.userData.listings;
  const exported = data.buildings, index = new Map(exported.map((b, i) => [b.id, i]));
  const before = vertexBox(original);
  if (!before) return [];
  const live = new Map(buildings.map(b => [b.id, b]));
  const now = exported.map(b => {
    if (!edits.exportIds.has(b.id)) return b;
    const record = live.get(mapIdOf(b));
    return { ...b, floors: record ? floorsOf(record) : [] };
  });
  const from = { location: original.location, rotation: original.rotation }, pose = placedPose(o, root.matrix);
  const here = floorAt(exported, before), there = floorAt(now, movedBox(before, from, pose));
  const result = there && edits.exportIds.has(exported[there.building].id) ? []
    : copyFloors(listings.filter(l => index.has(l.building) && keep(l)).map(l => ({ ...l, building: index.get(l.building) })),
                 here, there, b => exported[b].floors.length).map(l => ({ ...l, building: exported[l.building].id }));
  root.userData.listingsKey = key; root.userData.listings = result;
  return result;
}
// After an edit ends (a drag let go, an undo): copies and moved pieces may stand in other floors now, and the Floor
// tiles overlay hatches moved and deleted pieces' tiles. The cutaway follows when what it depends on changed.
let cutKey = '';
function editedKey() {
  let key = '';
  for (const r of roots.values()) if (r.userData.edit || r.userData.deleted) key += `${r.userData.source.id}:${r.userData.deleted ? 'x' : r.matrix.elements.join(',')}|`;
  return key;
}
// The play area: the map's level volume (playableBounds), the box the game's tile grid fills, which units can't leave.
// Drawn light: its edges as lines and its four sides as faint see-through walls, from the lowest tile level up to the
// top of the highest, never picked and never cut by Interior or the floor cutaway. View options' Play area, or B,
// turns it off and on (remembered in the browser).
const PLAY_AREA_SHOWN = 'workshop.playArea', PLAY_AREA_COLOR = 0xffb347;
const playArea = new THREE.Group(); world.add(playArea);
playArea.visible = recall(PLAY_AREA_SHOWN) !== '0';
const playAreaMaterials = {
  line: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.75, depthWrite: false }),
  // the same edges faintly through whatever stands in front, so Full's tall buildings don't hide it
  through: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.22, depthWrite: false, depthTest: false }),
  wall: new THREE.MeshBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }),
  none: new THREE.MeshBasicMaterial({ visible: false }),
};
function drawPlayArea() {
  for (const child of [...playArea.children]) { child.geometry.dispose(); playArea.remove(child); }
  const bounds = data?.scope === 'map' && data.playableBounds;
  $('playAreaRow').hidden = !bounds;
  if (!bounds) return;
  const min = new THREE.Vector3(...bounds.min), max = new THREE.Vector3(...bounds.max);
  const size = new THREE.Vector3().subVectors(max, min), centre = new THREE.Vector3().addVectors(min, max).multiplyScalar(0.5);
  const box = new THREE.BoxGeometry(size.x, size.y, size.z);
  const edgeGeometry = new THREE.EdgesGeometry(box);
  const edges = new THREE.LineSegments(edgeGeometry, playAreaMaterials.line);
  const through = new THREE.LineSegments(edgeGeometry.clone(), playAreaMaterials.through);
  // a box's faces in order +x, -x, +y, -y, +z, -z: the sides only, no lid or floor
  const walls = new THREE.Mesh(box, [playAreaMaterials.wall, playAreaMaterials.wall, playAreaMaterials.none, playAreaMaterials.none, playAreaMaterials.wall, playAreaMaterials.wall]);
  for (const part of [edges, through, walls]) { part.position.copy(centre); part.renderOrder = 2; playArea.add(part); }
  edges.name = 'playAreaEdges'; walls.name = 'playAreaWalls';
}
function setPlayArea(on) {
  playArea.visible = Boolean(on); $('playAreaToggle').checked = playArea.visible;
  remember(PLAY_AREA_SHOWN, playArea.visible ? '1' : '0');
}
$('playAreaToggle').checked = playArea.visible;
// The map's size as the project sets it (Project menu, Map size…; prefab plan 5.11). The Build makes the map's tile
// grid that many tiles from its own corner, so it grows along +X and +Y. Here the scene's grid and play area take the
// size, so everything that reads them (the play area's box, the tile grid, Interior) follows, and the new area is
// drawn as a faint sheet at the grid's bottom: green where the Build is to lay the map's ground, grey where the
// project lays its own.
const stageArea = new THREE.Group(); world.add(stageArea);
const stageMaterials = {
  ground: new THREE.MeshBasicMaterial({ color: 0x5f8a3a, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }),
  bare: new THREE.MeshBasicMaterial({ color: 0x8a97a0, transparent: true, opacity: 0.2, side: THREE.DoubleSide, depthWrite: false }),
  line: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.45, depthWrite: false }),
};
let ownGrid = null;     // the map's own: { dims, max } as exported, kept before the first change
function ownSize() {
  if (!ownGrid && !builderMode && data?.scope === 'map' && !data.preview && data.tileGrid?.dimensions && data.tileGrid.origin && data.playableBounds)
    ownGrid = { dims: [...data.tileGrid.dimensions], max: [...data.playableBounds.max] };
  return ownGrid;
}
// Whether the map's size can be set: on any whole map (13 November), growing only while it is as it is, and any way, in
// any of the three, once it is cleared (Clear map plan, section 6). On the bare map a new map starts from
// (project.js STAGE_MAPS) the Build lays its ground over the new area.
const bareMap = () => STAGE_MAPS.includes(activeMapId);
const sizeEditable = () => Boolean(ownSize());
// The grid a stage asks for, as [nx, ny, nz], when this map can take it; else null (the map's own size)
function stageDims(next, own = ownSize()) {
  if (!own || !next || !validStage(next, own.dims)) return null;
  const want = [next.grid[0], next.grid[1], next.grid[2] ?? own.dims[2]];
  // a map as it is only grows (the user, 13 November: the blank map's rule for every map); a cleared map any way
  if (!cleared && (want[0] < own.dims[0] || want[1] < own.dims[1] || want[2] < own.dims[2])) return null;
  return want.some((v, k) => v !== own.dims[k]) ? want : null;
}
// The grid drawn at `dims` (the play area's box and everything that reads the scene's grid), without changing the
// project: the Clear map dialog's numbers while they are typed, and setStage
function showGrid(dims) {
  const own = ownSize();
  if (!own) return;
  const [nx, ny, nz] = dims ?? own.dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [96, 96, 64];
  data.tileGrid.dimensions[0] = nx; data.tileGrid.dimensions[1] = ny; data.tileGrid.dimensions[2] = nz;
  data.playableBounds.max[0] = dims ? ox + nx * sx : own.max[0];
  data.playableBounds.max[2] = dims ? oy + ny * sy : own.max[2];
  data.playableBounds.max[1] = dims ? oz + nz * sz : own.max[1];
  drawPlayArea(); refreshGroundGrid();
  placeGridHandles(); if (gridTool && !gridDrag) gridPanel();
}
function setStage(next) {
  const own = ownSize();
  for (const child of [...stageArea.children]) { child.geometry.dispose(); stageArea.remove(child); }
  const dims = stageDims(next, own);
  // a size this map can't take (smaller than the map's own, not cleared) is kept as the project has it, not drawn
  stage = dims ? tidyStage(next) : (next && validStage(next, own?.dims) && !cleared ? tidyStage(next) : null);
  if (!own) return;
  showGrid(dims);
  // a map grown as it is: the new area as a faint sheet, green where the Build lays the map's ground (where it is laid
  // as planes), grey where the project asked for none
  if (!dims || cleared) return;
  const [nx, ny] = dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [96, 96];
  const x1 = ox + own.dims[0] * sx, x2 = ox + nx * sx, y1 = oy + own.dims[1] * sy, y2 = oy + ny * sy;
  for (const [ax, ay, bx, by] of [[x1, oy, x2, y2], [ox, y1, x1, y2]]) {
    if (bx - ax < 1 || by - ay < 1) continue;
    const sheet = new THREE.Mesh(new THREE.PlaneGeometry(bx - ax, by - ay), stage.ground === false ? stageMaterials.bare : stageMaterials.ground);
    sheet.rotation.x = -Math.PI / 2; sheet.position.set((ax + bx) / 2, oz + 0.5, (ay + by) / 2);
    sheet.renderOrder = 1; sheet.name = 'stageGround'; stageArea.add(sheet);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(sheet.geometry), stageMaterials.line);
    edge.rotation.copy(sheet.rotation); edge.position.copy(sheet.position); stageArea.add(edge);
  }
}
// ---------------------------------------------------------------- Map grid (the user, 13 November)
// The rail's Map grid: the play area's box with a handle on each side the grid can move: its far X and Y sides and its
// top. The corner and the bottom never move (the Build grows and shrinks the grid there). A handle drags along its
// axis by whole tiles (96 across) or levels (64 up), and each drag is one undo step. A map as it is, the blank map
// included, only grows, across and up; a cleared map also shrinks and gets lower. The panel reads out
// the size and the notes (sizeNotes: zones outside, no room for LWR's pods, the ground above the grid).
let gridTool = false, gridDrag = null, gridForcedPlay = false;
const gridHandles = new THREE.Group(); world.add(gridHandles); gridHandles.visible = false;
// game axis -> the view's (x, up, y basis): 0 is view x, 1 (game y) view z, 2 (up) view y
const GRID_AXES = [{ axis: 0, view: [1, 0, 0], color: 0xff5a5a }, { axis: 1, view: [0, 0, 1], color: 0x4a9cff }, { axis: 2, view: [0, 1, 0], color: 0x5ad17a }];
const gridHandleMaterials = new Map(GRID_AXES.map(a => [a.axis, new THREE.MeshBasicMaterial({ color: a.color, depthTest: false, transparent: true, opacity: 0.95 })]));
const gridHandleLine = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, depthTest: false });
// What the grid can be here: the axes with a handle and each one's bounds, in tiles and levels
function gridRule() {
  const own = ownSize();
  if (!own) return null;
  // a map as it is grows across and up (the user, 13 November: up too); a cleared map any way. Up to 256 tiles and 30
  // levels, or the map's own where more (stageMax)
  return { axes: [0, 1, 2], min: cleared ? [1, 1, 1] : [...own.dims], max: stageMax(own.dims) };
}
// The cursor's floors on the grid as the project has it (floors.js cursorStoreys; the Build's shell.py)
const storeysNow = () => cursorStoreys(data, { cleared, own: ownSize()?.dims ?? null });
// The stage a grid of `dims` asks for (null: the map's own)
function stageFor(dims) {
  const own = ownSize();
  if (dims.every((v, k) => v === own.dims[k])) return null;
  if (cleared) return { grid: [...dims] };
  return { grid: dims[2] === own.dims[2] ? [dims[0], dims[1]] : [...dims], ...(stage?.ground === false ? { ground: false } : {}) };
}
// Where a handle stands (the view's basis): the middle of its side of the play area's box
function gridHandleAt(axis) {
  const b = data.playableBounds, mid = [0, 1, 2].map(k => (b.min[k] + b.max[k]) / 2);
  return axis === 0 ? new THREE.Vector3(b.max[0], mid[1], mid[2]) : axis === 1 ? new THREE.Vector3(mid[0], mid[1], b.max[2])
    : new THREE.Vector3(mid[0], b.max[1], mid[2]);
}
function placeGridHandles() {
  for (const c of [...gridHandles.children]) { c.traverse(o => o.geometry?.dispose()); gridHandles.remove(c); }
  const rule = gridTool && data?.playableBounds ? gridRule() : null;
  gridHandles.visible = Boolean(rule);
  if (!rule) return;
  const b = data.playableBounds, span = Math.max(b.max[0] - b.min[0], b.max[2] - b.min[2]), size = Math.max(90, span * 0.032);
  for (const a of GRID_AXES.filter(g => rule.axes.includes(g.axis))) {
    const at = gridHandleAt(a.axis), dir = new THREE.Vector3(...a.view), handle = new THREE.Group();
    const cone = new THREE.Mesh(new THREE.ConeGeometry(size * 0.45, size * 1.2, 20), gridHandleMaterials.get(a.axis));
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir); cone.position.copy(dir.clone().multiplyScalar(size * 1.6));
    const grip = new THREE.Mesh(new THREE.SphereGeometry(size * 0.42, 18, 12), gridHandleMaterials.get(a.axis));
    const stem = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), dir.clone().multiplyScalar(size * 1.1)]), gridHandleLine);
    for (const part of [cone, grip, stem]) { part.renderOrder = 12; part.userData.gridAxis = a.axis; handle.add(part); }
    stem.raycast = () => {};
    handle.position.copy(at);
    gridHandles.add(handle);
  }
}
function gridHit(clientX, clientY) {
  if (!gridHandles.visible) return null;
  const hit = rayAt(clientX, clientY).intersectObjects(gridHandles.children, true).find(h => h.object.userData.gridAxis !== undefined);
  return hit ? hit.object.userData.gridAxis : null;
}
// How far along a line (origin, unit dir) the mouse's ray passes closest: the handle's drag
function alongLine(clientX, clientY, origin, dir) {
  const ray = rayAt(clientX, clientY).ray, w = origin.clone().sub(ray.origin);
  const b = dir.dot(ray.direction), c = ray.direction.dot(ray.direction), d = dir.dot(w), e = ray.direction.dot(w);
  const den = c - b * b;
  return Math.abs(den) < 1e-9 ? null : (b * e - c * d) / den;
}
function gridPanel(dims = [...data.tileGrid.dimensions]) {
  const panel = $('gridPanel');
  panel.hidden = !gridTool;
  if (!gridTool) return;
  const own = ownSize(), rule = gridRule();
  if (!own || !rule) { $('gridSize').textContent = 'This view has no map grid to change.'; $('gridHow').textContent = ''; $('gridGroundRow').hidden = true; $('gridNotes').hidden = true; return; }
  const [nx, ny, nz] = dims, same = dims.every((v, k) => v === own.dims[k]);
  $('gridSize').textContent = `${nx} × ${ny} tiles, ${nz} level${nz === 1 ? '' : 's'}${same ? ': the map\'s own' : ` (the map's own: ${own.dims[0]} × ${own.dims[1]} × ${own.dims[2]})`}.`;
  $('gridHow').textContent = cleared
    ? 'Drag a handle: red moves the far X side, blue the far Y side and green the top, by whole tiles and levels, larger or smaller. The corner and the bottom stay where they are.'
    : 'Drag a handle to make the map larger: red along X and blue along Y by whole tiles, green higher by whole levels. It can\'t be smaller or lower than the map\'s own: clear the map for that.';
  const grows = !cleared && (nx > own.dims[0] || ny > own.dims[1]);
  $('gridGroundRow').hidden = cleared;
  $('gridGround').checked = stage?.ground !== false; $('gridGround').disabled = !grows;
  $('gridOwn').disabled = !stage;
  const notes = sizeNotes(dims);
  if (cleared) notes.push(groundWords(nz));
  if (!cleared && !bareMap() && grows) notes.push('The Build lays more of the map\'s ground over the new area only where the map\'s ground is laid as planes (Bar\'s is), and makes the map\'s own low scenery there (its ground and pavements) walkable; elsewhere lay floors.');
  if (!cleared && nz > own.dims[2]) notes.push('The cursor reaches the new levels by storeys the Build adds over the whole grid, above the map\'s own.');
  $('gridNotes').hidden = !notes.length; $('gridNotes').textContent = notes.join(' ');
}
function setGridTool(on) {
  gridTool = Boolean(on) && Boolean(data) && data.scope === 'map' && !data.preview && !builderMode;
  $('editGrid').classList.toggle('on', gridTool); $('editGrid').setAttribute('aria-pressed', String(gridTool));
  // the play area is shown while the handles are, and put back as it was after
  if (gridTool && !playArea.visible) { playArea.visible = true; gridForcedPlay = true; }
  else if (!gridTool && gridForcedPlay) { playArea.visible = false; gridForcedPlay = false; }
  placeGridHandles(); gridPanel();
  if (gridTool) flashHint(cleared ? 'Drag the play area\'s handles to resize the grid' : 'Drag the play area\'s handles to make the grid larger or higher');
}
// One undo step for a new size
function commitStage(next, words) {
  const before = stage;
  if (JSON.stringify(before ?? null) === JSON.stringify(next ?? null)) { setStage(stage); return; }
  gizmo.record({ redo: () => { setStage(next); projectChanged(); }, undo: () => { setStage(before); projectChanged(); } });
  if (words) flashHint(`${words} · Ctrl+Z undoes`);
}
function startGridDrag(e) {
  if (!gridTool || e.button !== 0) return false;
  const axis = gridHit(e.clientX, e.clientY);
  if (axis === null) return false;
  const origin = gridHandleAt(axis), dir = new THREE.Vector3(...GRID_AXES[axis].view), t0 = alongLine(e.clientX, e.clientY, origin, dir);
  if (t0 === null) return false;
  gridDrag = { axis, origin, dir, t0, from: [...data.tileGrid.dimensions], dims: [...data.tileGrid.dimensions], pointerId: e.pointerId };
  controls.enabled = false; renderer.domElement.style.cursor = 'grabbing';
  return true;
}
function moveGridDrag(e) {
  const d = gridDrag, t = alongLine(e.clientX, e.clientY, d.origin, d.dir);
  if (t === null) return;
  const step = (data.tileGrid.size ?? [96, 96, 64])[d.axis], rule = gridRule();
  const n = Math.min(rule.max[d.axis], Math.max(rule.min[d.axis], d.from[d.axis] + Math.round((t - d.t0) / step)));
  if (n === d.dims[d.axis]) return;
  d.dims[d.axis] = n;
  showGrid(d.dims); gridPanel(d.dims);
}
function endGridDrag(keep) {
  const d = gridDrag;
  gridDrag = null; controls.enabled = true; renderer.domElement.style.cursor = '';
  if (!d) return;
  if (keep && d.dims.some((v, k) => v !== d.from[k])) commitStage(stageFor(d.dims), `The map grid is ${d.dims[0]} × ${d.dims[1]} × ${d.dims[2]}`);
  else setStage(stage);
}
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
$('editGrid').onclick = () => setGridTool(!gridTool);
$('projectSize').onclick = () => { showPop(null); setGridTool(true); };
$('gridDone').onclick = () => setGridTool(false);
$('gridOwn').onclick = () => commitStage(null, 'The map grid is the map\'s own');
$('gridGround').onchange = e => {
  if (!stage) return;
  const { ground, ...rest } = stage;
  commitStage(e.target.checked ? rest : { ...rest, ground: false }, e.target.checked ? 'The Build lays ground over the new area' : 'The new area gets no ground');
};

// ---------------------------------------------------------------- Clear map (private/plans/done/clear-map-plan.md)
// The landing zones as the project has them: its own list, or the map's own landings joined with the install's lines
// (spawns.js startingZones; ids stable for a map, so an unchanged list is saved as nothing)
let startingCache = null;
function zonesNow() {
  if (landingZones) return landingZones.filter(validLandingZone);
  if (!startingCache && data) startingCache = startingZones(ownLandings(data), landingLines.lines ?? [], (() => { let n = 0; return () => `start-${++n}`; })());
  return startingCache ?? [];
}
// The ground's height (section 3): the commonest ground of the landing zones, else the map's own landing's, else the
// commonest lowest saved floor; and its level in the grid
function groundHeight() {
  const counts = new Map();
  for (const z of zonesNow()) { const g = Math.round(groundOf(z)); counts.set(g, (counts.get(g) ?? 0) + 1); }
  if (!counts.size) for (const o of ownLandings(data ?? {})) { const g = Math.round(groundOf(o.zone)); counts.set(g, (counts.get(g) ?? 0) + 1); }
  if (!counts.size) {
    const lowest = new Map();
    for (const f of data?.tactical?.floorTiles ?? []) { const k = `${f.tile[0]},${f.tile[1]}`; if (!lowest.has(k) || f.location[2] < lowest.get(k)) lowest.set(k, f.location[2]); }
    for (const z of lowest.values()) { const g = Math.round(z); counts.set(g, (counts.get(g) ?? 0) + 1); }
  }
  if (!counts.size) return data?.tileGrid?.origin?.[2] ?? 0;
  return [...counts].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
}
const LEVEL_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six'];
function groundWords(levels) {
  const oz = data.tileGrid.origin[2], sz = data.tileGrid.size?.[2] ?? 64, ground = groundHeight();
  const under = Math.max(0, Math.floor((ground - oz + 2) / sz));
  if (under >= levels) return `The ground is at ${Math.round(ground)}, above the grid's top: the grid needs ${under + 1} levels or more.`;
  return `The ground is at level ${under + 1} of ${levels}: ${under ? `${LEVEL_WORDS[under] ?? under} level${under === 1 ? '' : 's'} of the grid ${under === 1 ? 'is' : 'are'}` : 'no level of the grid is'} under it.`;
}
// The notes under a size, none of which blocks (warn, don't block): zones outside the grid, no room for LWR's pods
// (F-90), the ground above the grid
function sizeNotes([nx, ny, nz], zoneList = null) {
  const notes = [], [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [96, 96, 64];
  const box = [ox, oy, oz, ox + nx * sx, oy + ny * sy, oz + nz * sz];
  const zones = zoneList ?? zonesNow();
  const inside = p => p[0] >= box[0] && p[0] <= box[3] && p[1] >= box[1] && p[1] <= box[4] && p[2] >= box[2] && p[2] <= box[5];
  const st = zoneState(), outside = zones.filter(z => !zoneSoldiers(z, st).every(s => inside(s.location)));
  if (outside.length) notes.push(`${outside.length} of ${plural(zones.length, 'landing zone')} ${outside.length === 1 ? 'is' : 'are'} outside the new grid.`);
  const far = zones.some(z => {
    const pts = zoneSoldiers(z, st).map(s => s.location), mx = pts.reduce((a, p) => a + p[0], 0) / pts.length, my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
    return Math.max(...[box[0], box[3]].flatMap(x => [box[1], box[4]].map(y => Math.hypot(x - mx, y - my)))) < 29 * sx;
  });
  if (far) notes.push('No part of the grid is 29 tiles from a landing zone: LWR places no pods or Meld there for a squad landing at it.');
  if (Math.floor((groundHeight() - oz + 2) / sz) >= nz) notes.push('The ground is above the grid.');
  return notes;
}
// The play area a clear that keeps the scenery outside goes by, across, in game units [x0, y0, x1, y1]: the map's level
// volume as exported and the grid of `dims` tiles together (the compiler's outside_box)
function outsideBox(dims = data.tileGrid.dimensions) {
  const own = ownSize(), b = data.playableBounds, [ox, oy] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [96, 96, 64];
  return [Math.min(b.min[0], ox), Math.min(b.min[2], oy), Math.max(own?.max[0] ?? b.max[0], ox + dims[0] * sx),
          Math.max(own?.max[2] ?? b.max[2], oy + dims[1] * sy)];
}
let outsideCache = null;
// Whether a place (game x, y) is outside the play area of the clear the project made
function pointOutside(x, y) {
  if (!clearKeepsOutside || !data?.playableBounds) return false;
  const key = data.tileGrid.dimensions.join(',');
  if (outsideCache?.key !== key) outsideCache = { key, box: outsideBox() };
  const [x0, y0, x1, y1] = outsideCache.box;
  return x < x0 || x > x1 || y < y0 || y > y1;
}
// What a clear takes and keeps, from the pieces and lights on the map now. `keepOutside`: the grid size (tiles, levels)
// the clear gives, to leave the scenery wholly outside the play area (outsideBox): a piece whose every part's box is
// outside it, and a light placed outside it.
function clearPlan(keepOutside = null) {
  const originals = [], added = [], landing = new Set(), script = new Map(), actors = new Set(), addedActors = new Set();
  const area = keepOutside ? outsideBox(keepOutside) : null, boxes = new Map(), outside = new Set();
  const out = (x, y) => area && (x < area[0] || x > area[2] || y < area[1] || y > area[3]);
  for (const r of roots.values()) {
    const o = r.userData.source;
    if (o.added) { added.push(r); addedActors.add(o.actor); continue; }
    if (isStream(o) || o.hidden || o.environment || r.userData.deleted) continue;
    if (isLanding(o)) { landing.add(o.actor); continue; }
    if (area) { const b = new THREE.Box3().setFromObject(r); if (!b.isEmpty()) (boxes.get(o.actor) ?? boxes.set(o.actor, []).get(o.actor)).push(b); }
    originals.push(r);
  }
  // across, an actor wholly outside the play area: every part's box beyond the same side or another
  if (area) for (const [actor, bs] of boxes)
    if (bs.every(b => b.max.x < area[0] || b.min.x > area[2] || b.max.z < area[1] || b.min.z > area[3])) outside.add(actor);
  for (let k = originals.length - 1; k >= 0; k--) if (outside.has(originals[k].userData.source.actor)) originals.splice(k, 1);
  for (const r of originals) {
    const o = r.userData.source;
    actors.add(o.actor);
    if (o.referencedBy?.length) script.set(o.actor, o.referencedBy);
  }
  const originalLights = [], addedLights = [], kept = [];
  let lightCount = 0, lightsOutside = 0;
  for (const r of lightRoots.values()) {
    const o = r.userData.source;
    if (isStream(o)) continue;
    if (o.added) { addedLights.push(r); lightCount++; continue; }
    if (o.kind === 'directional' || o.kind === 'sky' || o.role === 'dominant' || o.role === 'sky') { kept.push(o); continue; }
    if (r.userData.deleted) continue;
    const e = r.matrix.elements;       // (a light's place is its root's own matrix, in the view's basis)
    if (out(e[12], e[14])) { lightsOutside++; continue; }
    lightCount++;
    // the lights the editor edits are deleted here; area lights go with their pieces; the view-only ones the Build
    // takes out (clear_level), and a cleared map draws none of them
    if (!lightViewOnly(o) && o.role !== 'area') originalLights.push(r);
  }
  return { originals, added, originalLights, addedLights, pieces: actors.size + addedActors.size, lights: lightCount,
           landing: landing.size, script: [...script], kept, boxes: liveVolumes(), outside: outside.size, lightsOutside };
}
// What a clear does to the spawn points (the user, 18 November 2026: "clear should also clear all of these"): the map's
// pods, Meld points and drop-in points are deleted (their moves and values go), but for one something names (the Build
// would keep it and warn: it stays, with its edit); the project's copies of them go. No-spawn volumes (the map's and
// the project's) and the mission streams' objects stay as they are. { after (the edits after the clear), deleted,
// named (the records), copies (how many go), volumes (how many stay) }.
function clearedSpawns() {
  const after = new Map(missionMoves), deleted = [], named = [];
  if (!spawnsAvailable() || !spawnFamilyBuilds()) return { after, deleted, named, copies: 0, volumes: 0 };
  let copies = 0, volumes = 0;
  for (const [k, m] of missionMoves) {
    if (m.stream !== 'copy') continue;
    if (m.copy.kind === 'noSpawn') volumes++; else { after.delete(k); copies++; }
  }
  for (const o of data?.spawns ?? []) {
    const k = spawnKey(null, o.actor);
    if (o.landing || missionMoves.get(k)?.deleted || !spawnEditable(o)) continue;
    if (o.kind === 'noSpawn') { volumes++; continue; }
    if (spawnNamed(o)) { named.push(o); continue; }
    after.set(k, deletedEntry(o)); deleted.push(o);
  }
  return { after, deleted, named, copies, volumes };
}
// What a clear does to the effects, sounds and lens flares standing now (effects_rules.js survivesClear, the Build's
// clear_level): { effects (and flares) and sounds that go, landing: the landing's that stay (the Skyranger's lights,
// dust and sound) }. `keepOutside`: the grid size of a clear that keeps the scenery outside the play area.
function clearedEffects(keepOutside = null) {
  const area = keepOutside ? outsideBox(keepOutside) : null;
  const outside = (x, y) => Boolean(area) && (x < area[0] || x > area[2] || y < area[1] || y > area[3]);
  let effects = 0, sounds = 0, landing = 0;
  for (const root of effectRoots.values()) {
    const o = root.userData.source;
    if (o.added || isStream(o) || root.userData.deleted || root.userData.derivedGone) continue;
    const ctx = { carrierMoved: root.userData.carrierMoved, moved: Boolean(root.userData.edit) };
    if (!survivesClear(o, { ...ctx, cleared, outside: pointOutside })) continue;      // (an earlier clear's)
    if (survivesClear(o, { ...ctx, cleared: true, outside })) { if (o.landingActor) landing++; }
    else if (o.kind === 'sound') sounds++;
    else effects++;
  }
  return { effects, sounds, landing };
}
const clearDialog = { root: $('clearMap'), keep: $('clearMapKeepOutside') };
const CLEAR_KEEP_OUTSIDE = 'workshop.clearKeepOutside';
clearDialog.keep.checked = recall(CLEAR_KEEP_OUTSIDE) === '1';
// The window's counts and notes, at the grid's size now (a clear keeps it; the rail's Map grid changes it)
function clearSize() {
  const v = [...data.tileGrid.dimensions], notes = [];
  if (landingLines.kind === 'ew') notes.push('Plain Enemy Within puts the aliens at the map\'s pods and Meld points, and the clear deletes them: place new ones on your floors with the Add panel\'s Spawn points.');
  $('clearMapWarn').hidden = !notes.length; $('clearMapWarn').textContent = notes.join(' ');
  clearWords(v);
  return v;
}
function showClearMap() {
  showPop(null);
  if (!projectsAvailable() || !ownSize()) { banner('Clear map is for a whole map, not a piece study, a preview or the prefab builder.'); return; }
  clearSize();
  clearDialog.root.hidden = false;
  setTimeout(() => $('clearMapOk').focus(), 0);
}
// The window's counts, for the size `v` (the play area a clear keeping the scenery outside goes by follows it)
function clearWords(v) {
  const plan = clearPlan(clearDialog.keep.checked ? v : null), zones = zonesNow(), kept = clearKeptZone();
  // (the sun or moon and the sky light have no marker: the export's list says whether the map has them)
  const placeless = (data.lights ?? []).filter(l => l.layer === 'base');
  const sky = placeless.some(l => l.role === 'sky' || l.kind === 'sky'), sun = placeless.some(l => l.kind === 'directional');
  const scenery = clearDialog.keep.checked ? `, ${plural(plan.outside, 'piece')} and ${plural(plan.lightsOutside, 'light')} outside the play area` : '';
  const sp = clearedSpawns(), points = sp.deleted.length + sp.copies, fx = clearedEffects(clearDialog.keep.checked ? v : null);
  const and = list => (list.length > 1 ? `${list.slice(0, -1).join(', ')} and ${list.at(-1)}` : list[0]);
  const gone = [plural(plan.pieces, 'piece'), plural(plan.lights, 'light'), points && `${plural(points, 'spawn point')} (pods, Meld points and drop-in points)`,
                fx.effects && plural(fx.effects, 'effect'), fx.sounds && plural(fx.sounds, 'ambient sound')].filter(Boolean);
  $('clearMapPlan').textContent = `Removes ${and(gone)}. `
    + `Keeps the landing's ${plural(plan.landing, 'piece')}${fx.landing ? ` and its ${fx.landing === 1 ? 'effect' : `${fx.landing} effects and sounds`}` : ''}, `
    + `${kept ? `one landing zone (${zones.findIndex(z => z.id === kept.id) === 0 ? 'the first' : `zone ${zones.findIndex(z => z.id === kept.id) + 1}`}, the map's own landing${zones.length > 1 ? `; the other ${zones.length - 1} go` : ''})` : 'no landing zone'}`
    + `${scenery}${sp.volumes ? `, the ${plural(sp.volumes, 'no-spawn volume')}` : ''}${sun ? ', the sun' : ''}${sky ? ' and the sky light' : ''}.`
    + (sp.named.length ? ` ${plural(sp.named.length, 'spawn point')} the map's script names ${sp.named.length === 1 ? 'stays' : 'stay'} (${sp.named.slice(0, 4).map(o => short(o.actor)).join(', ')}${sp.named.length > 4 ? ` and ${sp.named.length - 4} more` : ''}).` : '');
  // the kinds a record alone gives the map, and the base map's missions that bring objects in their streams
  const brought = (data.missions ?? []).filter(m => (m.streams ?? []).some(s => data.streams?.[s]?.missionObjects?.length));
  const words = { Abduction: 'an abduction', TerrorSite: 'a terror site', 'Special/Bomb': 'a bomb mission', Crash: 'a UFO mission (with a UFO placed)' };
  const added = Object.keys(words).filter(k => !(k === 'Special/Bomb' && (!lwrInstall() || baseHas(k))) && !brought.some(m => kindKey(m) === k)).map(k => words[k]);
  const listed = list => (list.length > 1 ? `${list.slice(0, -1).join(', ')} or ${list.at(-1)}` : list[0]);
  $('clearMapMissions').hidden = false;
  $('clearMapMissions').textContent = `Then it asks what the cleared map is for: ${listed(added)}`
    + (brought.length ? `; or the base map's ${listed(missionLabels(brought))}, ${brought.length === 1 ? 'its' : 'their'} objects standing where the original map has them until moved.` : '.');
  const named = plan.script;
  $('clearMapScript').hidden = !named.length;
  $('clearMapScript').textContent = named.length ? `${plural(named.length, 'piece')} the mission's script shows or hides go${named.length === 1 ? 'es' : ''} too: `
    + named.map(([actor, by]) => `${short(actor)} (${by.join('; ')})`).join(', ') + '.' : '';
}
function hideClearMap() { clearDialog.root.hidden = true; }
clearDialog.keep.onchange = () => { remember(CLEAR_KEEP_OUTSIDE, clearDialog.keep.checked ? '1' : '0'); clearSize(); };
$('clearMapForm').onsubmit = e => { e.preventDefault(); clearDialog.root.hidden = true; clearMap(null, clearDialog.keep.checked); };
$('clearMapClose').onclick = $('clearMapCancel').onclick = hideClearMap;
clearDialog.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hideClearMap(); } });
$('projectClear').onclick = showClearMap;
// The clear (section 1), one undo step: the added pieces and lights go, the originals and the editable lights are
// marked deleted but for the landing's, the sun and the sky light; the project's buildings (and the map's that can be
// edited) are deleted, its groups and area-light bindings go; the size and the cleared mark are set.
// The one landing zone a clear keeps (the user, 13 November: "just leave 1 LZ"): plain EW's first, the map's own
// first landing (else the first zone), used by both games
function clearKeptZone() {
  const zones = data ? explicitZones() : [], z = zones.find(v => v.ew) ?? zones[0];
  if (!z) return null;
  const { lwr, ew, ...rest } = z;
  return { ...rest, ...(ownLandings(data).length ? { ew: true } : {}) };
}
function clearMap(size, keepOutside = false) {
  const own = ownSize(), plan = clearPlan(keepOutside ? (size ?? [...data.tileGrid.dimensions]) : null), keepsBefore = clearKeepsOutside;
  const kept = clearKeptZone(), zonesBefore = landingZones ? landingZones.map(z => ({ ...z })) : null;
  // a size given (the tests, scripts) is the clear's; none keeps the grid as it is now
  const next = size ? (size.some((v, k) => v !== own.dims[k]) ? { grid: [...size] } : null)
    : (stage ? { grid: [...data.tileGrid.dimensions] } : null);
  const picks = gizmo.picks(), groupsBefore = cloneGroups(), bindingsBefore = new Map(areaBindings), stageBefore = stage, clearedBefore = cleared;
  // what a cleared map is for (mission types plan, D2): the header's mission when it is an abduction, a terror site or
  // a bomb (a record of the map's, or a kind the project adds), else an abduction; the Missions panel asks once the
  // clear is made
  const missionsBefore = projectMissions ? projectMissions.map(e => ({ ...e })) : null, missionsCleared = clearedMissions();
  // (the map's pods, Meld points and drop-in points deleted, the project's copies of them gone: clearedSpawns)
  const spawnsBefore = new Map(missionMoves), spawnsAfter = clearedSpawns().after;
  const started = performance.now();
  gizmo.record({
    redo: () => {
      removeRoots(plan.added); removeLightRoots(plan.addedLights);
      setMissionMoves(new Map(spawnsAfter));
      for (const r of [...plan.originals, ...plan.originalLights, ...plan.boxes]) r.userData.deleted = true;
      areaBindings = new Map(); setGroups(new Map());
      cleared = true; clearKeepsOutside = keepOutside; mergedBuildings = null; setStage(next); clearedChanged();
      projectMissions = missionsCleared.map(e => ({ ...e })); refreshMissionPicker();
      if (kept) { landingZones = [{ ...kept }]; pickedZone = null; refreshLandingZones(); }
      refreshLightVisibility(); lightsDirty = true; gizmo.setSelection([]); sceneChanged();
    },
    undo: () => {
      addRoots(plan.added); addLightRoots(plan.addedLights);
      setMissionMoves(new Map(spawnsBefore));
      for (const r of [...plan.originals, ...plan.originalLights, ...plan.boxes]) r.userData.deleted = false;
      areaBindings = new Map(bindingsBefore); setGroups(cloneGroups(groupsBefore));
      cleared = clearedBefore; clearKeepsOutside = keepsBefore; mergedBuildings = null; setStage(stageBefore); clearedChanged();
      projectMissions = missionsBefore ? missionsBefore.map(e => ({ ...e })) : null; refreshMissionPicker();
      if (kept) { landingZones = zonesBefore ? zonesBefore.map(z => ({ ...z })) : null; pickedZone = null; refreshLandingZones(); }
      refreshLightVisibility(); lightsDirty = true; gizmo.setSelection(picks.ids, picks.active); sceneChanged();
    },
  });
  lastClearMs = Math.round(performance.now() - started);
  flashHint('Cleared · Ctrl+Z brings it back');
  if (!size) setTimeout(() => showMissions(true), 0);      // (a scripted clear, with its size, asks nothing)
}
// The Missions panel (missions_panel.js; mission types plan, D2): the base map's missions and the kinds a record alone
// gives the map, ticked as the project has them; OK sets them, one undo step.
const missionsPanel = createMissionsPanel({
  els: { root: $('missionsDialog'), form: $('missionsForm'), title: $('missionsTitle'), note: $('missionsNote'), list: $('missionsList'),
         warn: $('missionsWarn'), ok: $('missionsOk'), close: $('missionsClose'), cancel: $('missionsCancel') } });
const lwrInstall = () => landingLines?.kind !== 'ew';
// whether a UFO building stands on the map: one of the project's, or one of the map's own that stays
const hasUfoBuilding = () => allBuildings().some(b => (b.project ? (b.project.kind ?? 'building') === 'ufo' : b.isUfo));
const baseHas = kind => (data?.missions ?? []).some(m => kindKey(m) === kind);
// A cleared map's missions: the header's when it is one of the first three kinds (its own record, else added), else
// the base map's abduction record, else an added abduction.
function clearedMissions() {
  const picked = (data?.missions ?? [])[missionIndex], key = picked ? kindKey(picked) : null;
  const addedPick = missionPickValue.startsWith('kind:') ? missionPickValue.slice(5) : null;
  if (['Abduction', 'TerrorSite', 'Special/Bomb'].includes(addedPick) && (addedPick !== 'Special/Bomb' || lwrInstall())) return [{ kind: addedPick }];
  // (the base map's bomb is its own record, its objects standing where the original map has them until moved)
  if (picked && ['Abduction', 'TerrorSite', 'Special/Bomb'].includes(key)) return [{ record: missionIndex }];
  const abduction = (data?.missions ?? []).findIndex(m => kindKey(m) === 'Abduction');
  return abduction >= 0 ? [{ record: abduction }] : [{ kind: 'Abduction' }];
}
async function showMissions(asked = false) {
  showPop(null);
  if (!projectsAvailable() || !data || data.preview) return;
  if (!playStatus) await refreshInstalls();     // what is known of each kind played (the Project menu asks it too)
  const missions = data.missions ?? [], labels = missionLabels(missions), kinds = playStatus?.missionKinds ?? {};
  const listed = Array.isArray(projectMissions) ? projectMissions : missions.map((_, i) => ({ record: i }));
  const has = entry => listed.some(e => (entry.record !== undefined ? e.record === entry.record : e.kind === entry.kind));
  const rows = missions.map((m, i) => {
    const objects = (m.streams ?? []).flatMap(s => data.streams?.[s]?.missionObjects ?? []);
    const lost = objects.filter(o => missionReached(o) && missionFloorLost(o)).length;
    return { entry: { record: i }, label: labels[i], checked: has({ record: i }), words: kinds[kindKey(m)]?.words ? `${kinds[kindKey(m)].words}.` : '',
             detail: [objects.length ? `${plural(objects.length, 'object')} in its stream${cleared ? ', standing where the original map has them' : ''}.` : '',
                      lost ? `${plural(lost, 'object')} of the map's floor taken from under ${lost === 1 ? 'it' : 'them'} (the Build warns).` : ''].filter(Boolean).join(' ') };
  });
  for (const [kind, k] of Object.entries(ADDED_KINDS)) {
    if (baseHas(kind) && !listed.some(e => e.kind === kind)) continue;     // the base map's own record is the row for it
    const entry = listed.find(e => e.kind === kind) ?? { kind, ...(k.ufo ? { ship: 'eShip_UFOSmallScout' } : {}) };
    rows.push({ entry, label: `${k.label} (added)`, checked: has({ kind }), words: '', detail: k.needs, ufo: k.ufo,
                disabled: k.lwr && !lwrInstall() ? 'Long War only: plain Enemy Within would play the bomb where Slaughterhouse has it.'
                  : k.ufo && !hasUfoBuilding() ? 'Place a UFO prefab first: the mission needs a UFO building on the map.' : null });
  }
  missionsPanel.show({
    title: asked ? 'What is this map for?' : `Missions${project ? ` of ${project.doc.name}` : ''}`,
    note: asked ? 'The cleared map is played as the missions ticked here; the Build writes a record for each. The Missions item in the Project menu changes them later.'
      : 'The Build writes a record for each mission ticked, and Play in game plays one of them. An added kind is made from the base map\'s abduction record.',
    rows, onOk: entries => setMissions(entries),
  });
}
// The project's missions set, one undo step: every base record and nothing added on a map that isn't cleared is the
// default (null: saved as nothing).
function setMissions(entries) {
  const all = (data.missions ?? []).length, records = entries.filter(e => Number.isInteger(e.record));
  const next = !cleared && records.length === all && entries.length === all ? null : entries.map(e => ({ ...e }));
  const before = projectMissions ? projectMissions.map(e => ({ ...e })) : null;
  if (JSON.stringify(next) === JSON.stringify(before)) return;
  gizmo.record({
    redo: () => { projectMissions = next ? next.map(e => ({ ...e })) : null; refreshMissionPicker(); projectChanged(); },
    undo: () => { projectMissions = before ? before.map(e => ({ ...e })) : null; refreshMissionPicker(); projectChanged(); },
  });
}
$('projectMissions').onclick = () => showMissions(false);
let lastClearMs = null;

// The ground grid (Clear map plan, section 3): a faint grid on the ground's plane (groundHeight: the landing zones'),
// over the map's tile grid and no further, drawn only where the map has no floor: a tile is left out where a saved
// floor at or under the ground is carried by a piece still where the map has it. So on a map as it is it shows only
// over holes, and on a cleared one everywhere. Drawn with the depth test 2 units under the ground, so a floor piece
// laid at ground level covers it; never picked. View options' Ground grid, on by default and remembered.
const GROUND_GRID = 'workshop.groundGrid';
const groundGrid = new THREE.Group(); world.add(groundGrid);
groundGrid.visible = recall(GROUND_GRID) !== '0';
const groundGridMaterials = {
  sheet: new THREE.MeshBasicMaterial({ color: 0x778c91, transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide }),
  line: new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.14, depthWrite: false }),
  outline: new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.35, depthWrite: false }),
};
// The pieces still where the map has them (not deleted, not moved): their saved floor tiles count
function floorStays(actor) {
  const list = floorRootsByActor().get(actor);
  return Boolean(list) && list.every(r => !r.userData.deleted && !r.userData.edit);
}
let floorRootsCache = null, floorRootsKey = null;
function floorRootsByActor() {
  if (!floorRootsCache || floorRootsKey !== roots.size) {
    floorRootsCache = new Map(); floorRootsKey = roots.size;
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (o.added || o.layer !== 'base') continue;
      if (!floorRootsCache.has(o.actor)) floorRootsCache.set(o.actor, []);
      floorRootsCache.get(o.actor).push(r);
    }
  }
  return floorRootsCache;
}
// The saved floor index (floors.js floorIndex) of the tiles whose piece is still where the map has it: what Level snap
// goes by, so a deleted piece's floor no longer guides placement
let liveFloorCache = null;
function liveFloorIndex() {
  const key = editedKey();
  if (!liveFloorCache || liveFloorCache.key !== key) {
    const tiles = data.preview ? [] : (data.tactical?.floorTiles ?? []).filter(f => floorStays(f.actor));
    liveFloorCache = { key, index: floorIndex(tiles) };
  }
  return liveFloorCache.index;
}
let groundGridKey = null;
function refreshGroundGrid(force = true) {
  if (!data || builderMode || data.scope !== 'map' || data.preview || !data.tileGrid?.origin || !data.tileGrid.dimensions) {
    for (const child of [...groundGrid.children]) { child.geometry.dispose(); groundGrid.remove(child); }
    return;
  }
  const ground = groundHeight(), key = `${roots.size}|${editedKey()}|${data.tileGrid.dimensions.join(',')}|${ground}|${cleared}`;
  if (!force && key === groundGridKey) return;
  groundGridKey = key;
  for (const child of [...groundGrid.children]) { child.geometry.dispose(); groundGrid.remove(child); }
  const [ox, oy] = data.tileGrid.origin, [nx, ny] = data.tileGrid.dimensions, [sx, sy, sz] = data.tileGrid.size ?? [96, 96, 64];
  const covered = new Set();
  for (const f of data.tactical?.floorTiles ?? []) {
    if (f.location[2] <= ground + sz / 2 && floorStays(f.actor)) covered.add(`${f.tile[0]},${f.tile[1]}`);
  }
  const y = ground - 2, sheet = [], lines = [], edge = new Set();
  const segment = (x0, z0, x1, z1) => { const k = `${x0},${z0},${x1},${z1}`; if (!edge.has(k)) { edge.add(k); lines.push(x0, y, z0, x1, y, z1); } };
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
    if (covered.has(`${i},${j}`)) continue;
    const x0 = ox + i * sx, x1 = x0 + sx, z0 = oy + j * sy, z1 = z0 + sy;
    sheet.push(x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z0, x1, y, z1, x0, y, z1);
    segment(x0, z0, x1, z0); segment(x0, z1, x1, z1); segment(x0, z0, x0, z1); segment(x1, z0, x1, z1);
  }
  if (sheet.length) {
    const mesh = new THREE.Mesh(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(sheet, 3)), groundGridMaterials.sheet);
    mesh.raycast = () => {}; mesh.name = 'groundGridSheet'; groundGrid.add(mesh);
    const grid = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(lines, 3)), groundGridMaterials.line);
    grid.raycast = () => {}; grid.name = 'groundGridLines'; groundGrid.add(grid);
  }
  // the grid's outline at the ground's height, so the gap under it to the play area's bottom is seen
  const X = ox + nx * sx, Z = oy + ny * sy;
  const outline = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(
    [ox, y, oy, X, y, oy, X, y, oy, X, y, Z, X, y, Z, ox, y, Z, ox, y, Z, ox, y, oy], 3)), groundGridMaterials.outline);
  outline.raycast = () => {}; outline.name = 'groundGridOutline'; groundGrid.add(outline);
  groundGrid.userData = { ground, bare: sheet.length / 18 };
}
function setGroundGrid(on) {
  groundGrid.visible = Boolean(on); $('groundGridToggle').checked = groundGrid.visible;
  remember(GROUND_GRID, groundGrid.visible ? '1' : '0');
}
$('groundGridToggle').checked = groundGrid.visible;
$('groundGridToggle').onchange = e => { setGroundGrid(e.target.checked); e.target.blur(); };

// ---------------------------------------------------------------- landing zones (Clear map plan, section 4)
// Each zone drawn as its footprint: the evac zone's box (faint), the six soldier points as dots, an arrow the way the
// squad faces, its number, and for a zone that is one of the map's own landings the grounded Skyranger's outline. A
// click picks one (ahead of the pieces under it); dragged, it moves by whole tiles; the panel turns it, raises it,
// orders, copies and deletes it. Every change is one undo step, and the first one makes the project's own list.
const LANDING_SHOWN = 'workshop.landingZones';
const landingLayer = new THREE.Group(); world.add(landingLayer);
landingLayer.visible = recall(LANDING_SHOWN) !== '0';
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
  try { localStorage.removeItem('workshop.missionObjects'); } catch { /* not kept */ }
}
normalSpawns = recall(NORMAL_SPAWNS) === '1';
const spawnLayer = new THREE.Group(); world.add(spawnLayer);
spawnLayer.visible = false;
spawnLayerReady = true;
let spawnFilters = (() => { try { return JSON.parse(recall(SPAWN_FILTERS) || '{}') || {}; } catch { return {}; } })();
let pickedSpawn = null;            // the picked marker's key (spawns_view.js spawnKey)
let spawnZonePick = null;          // a landing zone picked in the Spawns view, described only (decision D3)
let spawnLandingBefore = true;     // whether the landing zones showed before the Spawns view showed them
let spawnRulesData = null;         // what the install does with spawn points (spawn-rules.json), read as a map opens
let spawnEntriesNow = [];          // spawnRecords' entries for the mission the header shows
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
let missionMoves = new Map(), missionDragView = null;
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
  missionMoves = next; missionDragView = null;
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
function copySpawn(key) {
  const e = spawnEntry(key);
  const o = e?.layer === 'copy' ? copyTemplateOf(missionMoves.get(key)) : e?.layer === 'base' ? e.record : null;
  if (!o || copyTemplateWhy(o) || missionMoves.get(key)?.deleted) return null;
  const at = spawnAt(e), now = missionMoves.get(key);
  const actor = copyName(o), k = spawnKey('copy', actor), box = o.kind === 'noSpawn' ? spawnBoxNow(e) : null;
  const entry = copyEntry(o, { id: uuid(), actor, location: [at[0] + 96, at[1], at[2]], box: box && [box[0] + 96, box[1], box[2], box[3] + 96, box[4], box[5]],
                               rotation: now?.rotation ?? (o.rotation ?? [0, 0, 0]).map(v => Math.round(v)), spawn: now?.spawn ?? {} });
  const before = new Map(missionMoves), after = new Map(missionMoves).set(k, entry);
  gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
  setPickedSpawn(k);
  flashHint(`Copied ${short(e.record.actor)} a tile east · drag its arrows to place it`);
  return k;
}
// a copy's template: the base record it copies, or NEW_VOLUME for a no-spawn volume made fresh (no `from`)
const copyTemplateOf = m => (m?.stream !== 'copy' ? null : m.copy.from ? baseSpawnOf(m.copy.from) : m.copy.kind === 'noSpawn' ? NEW_VOLUME : null);
// a new copy's name: its template's with a serial (a fresh volume's after the class)
const copyName = o => `${o.actor ?? `TheWorld.PersistentLevel.${o.actorClass}`}_copy${++copySerial}`;
// a no-spawn volume's box now (the drag's, the project's, else the map's): [x0, y0, z0, x1, y1, z1]
const spawnBoxNow = e => missionMoveOf(e.stream, e.record.actor)?.box ?? recordBox(e.record);
// A new pod or Meld point from the Add panel (its Spawn points kind): the Spawns view is shown with the kind's family,
// and the next click places a copy of the kind's template (spawns_view.js addTemplate) on the tile under it
let spawnPlacing = null;
function startSpawnPlacing(kind) {
  const template = addTemplate(data?.spawns, kind);
  if (!template || !spawnFamilyBuilds()) return;
  setSpawnsShown(true);
  const family = KINDS[kind].family;
  if (spawnFilters[family] === false) {
    spawnFilters = { ...spawnFilters, [family]: true }; remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); syncSpawnFilters(); refreshSpawnMarkers();
  }
  // (the picked point goes, so its arrows are never under the click)
  if (pickedSpawn) setPickedSpawn(null);
  spawnPlacing = kind; renderer.domElement.style.cursor = 'crosshair';
  placeMissionGizmo();
  flashHint(`Click the tile the new ${KINDS[kind].label.toLowerCase()} is to stand ${kind === 'noSpawn' ? 'over' : 'on'} · Esc cancels`);
}
function stopSpawnPlacing() {
  if (!spawnPlacing) return;
  spawnPlacing = null; renderer.domElement.style.cursor = ''; pieces.setChosen?.(null); restingHint();
  placeMissionGizmo();
}
// One undo step: the copy placed where the click falls (on a piece, else on the ground grid's plane), on the tile under
// it by whole tiles from its template, at the template's height above its own floor; then picked
function placeSpawn(clientX, clientY) {
  const kind = spawnPlacing, template = addTemplate(data?.spawns, kind);
  stopSpawnPlacing();
  if (!template) return null;
  const hit = pick(clientX, clientY)?.point
    ?? rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundHeight()), new THREE.Vector3());
  if (!hit) return null;
  const actor = copyName(template), k = spawnKey('copy', actor);
  let entry;
  if (kind === 'noSpawn') {
    // a volume: its box over whole tiles round the click, its bottom on the level of the surface under it
    const grid = { origin: data?.tileGrid?.origin ?? [0, 0, 0], size: data?.tileGrid?.size ?? [96, 96, 64] };
    const box = volumePlace(template, [hit.x, hit.z, hit.y], groundAt(hit.x, hit.z, hit.y + 64), grid);
    entry = copyEntry(template, { id: uuid(), actor, box, spawn: {} });
  } else {
    const [tx, ty, tz] = template.location;
    const place0 = addPlace(template, [hit.x, hit.z, hit.y], null, null);
    const at = addPlace(template, [hit.x, hit.z, hit.y], groundAt(place0[0], place0[1], hit.y + 64), groundAt(tx, ty, tz + 64));
    entry = copyEntry(template, { id: uuid(), actor, location: at, rotation: (template.rotation ?? [0, 0, 0]).map(v => Math.round(v)), spawn: {} });
  }
  const before = new Map(missionMoves), after = new Map(missionMoves).set(k, entry);
  gizmo.record({ redo: () => setMissionMoves(after), undo: () => setMissionMoves(before) });
  setPickedSpawn(k);
  flashHint(kind === 'noSpawn' ? `Added a no-spawn volume${template.fresh ? '' : `, a copy of ${short(template.actor)}`} · its arrows move it, its white handles stretch a side`
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
// turn for it, nor for any other point (the user, 18 November 2026: only where it changes the game)
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
  spawnEntriesNow = spawnsAvailable() ? [...spawnRecords(data, streamSet, spawnDonor()), ...copyEntries()] : [];
  // (a deleted base point shows only with the flyout's Deleted points switch on)
  const shown = shownEntries(spawnEntriesNow, spawnFilters, spawnDeleted);
  if (pickedSpawn && !shown.some(e => e.key === pickedSpawn)) pickedSpawn = null;      // another mission's, or a family hidden
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
  const line = (head, value) => { const p = document.createElement('p'); if (head) text(p, 'strong', `${head}: `); p.append(value); info.append(p); };
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
  // (a base pod or Meld point: the Build counts the places left, compiler.spawn_places, spawns plan SP5; one the
  // project moved, at its new place)
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
    const levels = Math.abs(Math.round(d[2] / 64));
    line('', `Moved ${Math.round(Math.hypot(d[0], d[1]) / 96)} tiles across${levels ? ` and ${levels} ${levels === 1 ? 'level' : 'levels'} ${d[2] > 0 ? 'up' : 'down'}` : ''} from where ${e.layer === 'donor' ? 'its stream' : 'the original map'} has it${n > 1 ? ', with its group' : ''}: the Build moves ${n > 1 ? 'them' : 'it'} in the variant's copy of ${e.stream}.`);
  }
  if (movable) {
    // a stream's copy replaces it in every record that streams it (keyed by the source package): name them all
    const using = streamMissions(e.stream);
    if (using.length > 1) line('', `The Build moves it for every mission of the variant that streams ${e.stream}: ${using.join(', ')}.`);
  }
  if (movable && projectsAvailable() && spawnMovable(e)) line('', `Drag the arrows to move it${n > 1 ? ` with its group (${n} parts)` : ''} by whole tiles and levels; Ctrl+Z undoes.`);
  if (['base', 'copy'].includes(e.layer) && projectsAvailable() && spawnMovable(e)) {
    const below = [TURNED_KINDS.includes(o.kind) && 'turn it', SPAWN_VALUE_KEYS[o.kind].length && (volume ? 'set what it keeps out' : 'set its values')].filter(Boolean);
    line('', `Drag the arrows to move it by whole tiles and levels${volume ? ', its white handles to stretch a side to the tile lines and levels (Alt: steps of 8)' : ''}${below.length ? `; ${below.join(' and ')} below` : ''}; Ctrl+Z undoes.`);
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
    for (const [label, turn, title] of [['Turn left', -16384, 'A quarter turn to the left ([)'], ['Turn right', 16384, 'A quarter turn to the right (])']]) {
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
// of it away (compiler.mission_objects' rule, on the saved tiles only).
function missionFloorLost(o) {
  const grid = data?.tileGrid, tiles = data?.tactical?.floorTiles;
  if (!grid?.origin || !tiles?.length) return false;
  const [ox, oy, oz] = tileCorner(), [sx, sy, sz] = grid.size ?? [96, 96, 64];
  const tx = Math.floor((o.location[0] - ox) / sx), ty = Math.floor((o.location[1] - oy) / sy), tz = Math.floor((o.location[2] - oz) / sz);
  const under = tiles.filter(f => f.tile[0] === tx && f.tile[1] === ty && (f.tile[2] === tz || f.tile[2] === tz - 1));
  return under.length > 0 && under.every(f => f.actor && !floorStays(f.actor));
}
function setPickedSpawn(key) {
  if (key && selected) select(null);
  pickedSpawn = key ?? null; spawnZonePick = null;
  refreshSpawnMarkers(); placeMissionGizmo();
}
// A stream object's group moves by its arrows (a donor's too, an added bomb's: stage SP4), and so does a base pod, Meld
// point or drop-in point where the spawn family builds (SP6)
const spawnMovable = e => Boolean(e) && (e.layer === 'stream' || e.layer === 'donor'
  || (e.layer === 'base' && spawnEditable(e.record) && spawnFamilyBuilds() && !spawnDeleted(e))
  || (e.layer === 'copy' && spawnFamilyBuilds()));
// The picked stream object's gizmo: arrows on its marker that move its group by whole tiles across and whole levels
// (64 units) up, as a landing zone's do. Escape during a drag puts it back.
const missionProxy = new THREE.Object3D(); world.add(missionProxy);
const missionGizmo = new TransformControls(camera, renderer.domElement);
missionGizmo.attach(missionProxy); missionGizmo.enabled = false; missionGizmo.setMode('translate');
const missionGizmoHelper = missionGizmo.getHelper(); missionGizmoHelper.visible = false; world.add(missionGizmoHelper);
let missionDrag = null;
const missionGizmoWanted = () => Boolean(spawnMovable(spawnEntry(pickedSpawn)) && spawnsShown() && projectsAvailable() && !placing
  && !spawnPlacing && !volumesOn && !lightsOn && !zonesOn && !effectsOn);
function placeMissionGizmo() {
  const e = missionGizmoWanted() ? spawnEntry(pickedSpawn) : null;
  missionGizmo.enabled = missionGizmoHelper.visible = Boolean(e);
  if (!e || missionGizmo.dragging) return;
  missionProxy.position.copy(gameToView(spawnAt(e)));
  missionProxy.quaternion.identity(); missionProxy.updateMatrixWorld(true);
}
missionGizmo.addEventListener('dragging-changed', e => { controls.enabled = !e.value; });
missionGizmo.addEventListener('mouseDown', () => {
  const e = spawnEntry(pickedSpawn);
  missionDrag = spawnMovable(e) ? { stream: e.stream, actor: e.record.actor, at: missionProxy.position.clone(), delta: [0, 0, 0], key: '' } : null;
});
missionGizmo.addEventListener('objectChange', () => {
  const d = missionDrag;
  if (!d || d.cancelled) return;
  const p = missionProxy.position, dx = Math.round((p.x - d.at.x) / 96) * 96, dz = Math.round((p.z - d.at.z) / 96) * 96,
        dy = Math.round((p.y - d.at.y) / 64) * 64;
  p.set(d.at.x + dx, d.at.y + dy, d.at.z + dz);
  d.delta = [dx, dz, dy];                 // the view's basis is x, up, y
  const key = d.delta.join(',');
  if (key !== d.key) {
    d.key = key;
    missionDragView = movedMissions(d.stream, d.actor, d.delta);
    placeStreamRoots(); refreshSpawnMarkers();
  }
});
missionGizmo.addEventListener('mouseUp', () => {
  const d = missionDrag;
  missionDrag = null; missionDragView = null;
  if (d && !d.cancelled && moveMissionGroup(d.stream, d.actor, d.delta)) return;
  placeStreamRoots(); refreshSpawnMarkers();
  setTimeout(placeMissionGizmo, 0);       // (the controls end their drag after this event)
});
function cancelMissionGizmo() {
  if (!missionDrag) return;
  missionDrag.cancelled = true; missionDragView = null; placeStreamRoots(); refreshSpawnMarkers();
}
// the marker nearest the click within a few pixels, as a light's is picked: its key, or null
function pickSpawnMarker(clientX, clientY) {
  if (!spawnLayer.visible || !spawnLayer.children.length) return null;
  const rect = renderer.domElement.getBoundingClientRect(), p = new THREE.Vector3();
  let best = null, bestD = 18;          // (about the halo's size on screen)
  for (const marker of spawnLayer.children) {
    if (!marker.userData.spawn) continue;       // (a volume's box: its marker is picked)
    marker.updateWorldMatrix(true, false);
    p.setFromMatrixPosition(marker.matrixWorld).project(camera);
    if (p.z > 1 || p.z < -1) continue;
    const d = Math.hypot(rect.left + (p.x + 1) / 2 * rect.width - clientX, rect.top + (1 - p.y) / 2 * rect.height - clientY);
    if (d < bestD) { bestD = d; best = marker.userData.spawn; }
  }
  return best;
}
// A click in the Spawns view: a marker, else a landing zone to describe, else the picked one let go
function spawnClick(e) {
  const key = pickSpawnMarker(e.clientX, e.clientY);
  if (key) { setPickedSpawn(key); return; }
  const z = zoneHit(e.clientX, e.clientY);
  setPickedSpawn(null);
  spawnZonePick = z ? z.id : null;
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
    spawnFilters = { ...spawnFilters, [family]: true }; remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); syncSpawnFilters();
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
    spawnZonePick = null;
    stopSpawnPlacing();     // a spawn point asked for from the Add panel and not placed yet goes with its view
    if (!spawnLandingBefore) landingLayer.visible = false;
  }
  spawnsOn = on;
  refreshSpawnMarkers(); lightButton(); placeMissionGizmo();
  if (on) {
    const shown = shownEntries(spawnEntriesNow, spawnFilters), n = kinds => shown.filter(e => kinds.includes(e.record.kind)).length;
    flashHint(`Spawns view: ${plural(n(['pod']), 'pod')}, ${plural(n(['meld']), 'Meld point')}, ${plural(n(['dropIn']), 'drop-in point')}`
      + `${n(['bomb', 'powerNode', 'capturePoint', 'radar', 'use']) ? `, ${plural(n(['bomb', 'powerNode', 'capturePoint', 'radar', 'use']), 'objective')}` : ''} · click one to see what it is · Shift+U leaves it`);
  }
}
// The Normal button's switch: the markers drawn and picked with pieces in the normal view (remembered)
function setNormalSpawns(on) {
  normalSpawns = Boolean(on);
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
  box.onchange = e => { spawnFilters = { ...spawnFilters, [f.id]: e.target.checked }; remember(SPAWN_FILTERS, JSON.stringify(spawnFilters)); refreshSpawnMarkers(); placeMissionGizmo(); e.target.blur(); };
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
  const put = v => { projectSpawnRules = v; syncSpawnRule(); spawnPanel(); };
  gizmo.record({ redo: () => put(next), undo: () => put(before) });
  flashHint(next ? 'Scripted drop-ins land where placed: the Build excludes the variant from Long War\'s drop-in mutator' : 'Scripted drop-ins as the install plays them');
}
$('dropInsPlaced').onchange = e => setSpawnRule(e.target.checked ? { dropIns: 'placed' } : null);
function loadSpawnRules() {
  spawnRulesData = null;
  if (!spawnsAvailable()) return;
  const id = activeMapId;
  fetch(`/maps/${encodeURIComponent(id)}/spawn-rules.json`).then(r => (r.ok ? r.json() : null)).then(rules => {
    if (id === activeMapId) { spawnRulesData = rules; spawnPanel(); syncSpawnRule(); }
  }).catch(() => {});
}

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
  effectsDirty = true; liveCache = null;
}
function removeEffectRoots(list) {
  for (const root of list) { effectRoots.delete(root.userData.source.id); effectLayer.remove(root); }
  effectsDirty = true; liveCache = null;
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
  effectsDirty = false; pickCentres = null;
  if (!effectsAvailable()) { effectMarkers = []; effectLayer.visible = false; refreshLikenesses(); return; }
  deriveEffects();
  const shown = effectsShown();
  effectLayer.visible = shown;
  // Interior shows what stands in the play area (view basis, as playableBounds)
  const play = $('scenery').value === 'interior' ? data.playableBounds : null;
  const at = new THREE.Vector3(), inAnyPlay = v => !play || [0, 1, 2].every(k => v.getComponent(k) >= play.min[k] - 48 && v.getComponent(k) <= play.max[k] + 48);
  effectMarkers = [];
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
let likenessOn = recall('workshop.likeness') !== '0', likenessThin = 1, likenessCount = 0;
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
  if (!likenesses.size) { likenessCount = 0; return; }
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
  likenessCount = count;
  // towards the budget, a little a frame, so nothing pops
  const want = count > LIKENESS_LIMITS.view ? likenessThin * LIKENESS_LIMITS.view / count : Math.min(1, likenessThin * 1.05);
  likenessThin = Math.max(0.02, likenessThin + (want - likenessThin) * 0.2);
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
    const text = $('likenessText');
    text.replaceChildren();
    text.append(entry.name);
    const out = leftOut(made.system), small = document.createElement('small');
    small.textContent = [`${entry.group} · the square is one tile`, out.ignored.length ? 'drawn roughly' : null].filter(Boolean).join(' · ');
    text.append(small);
    for (const line of tip.split('\n').filter(Boolean)) { const more = document.createElement('small'); more.textContent = line; text.append(more); }
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
  likenessOn = Boolean(on);
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
  wavePlayer = null;
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
  const audio = new Audio(), player = wavePlayer = { audio, wave, record: record.id, state: 'loading', why: null };
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
  const clock = t => (Number.isFinite(t) ? `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}` : '');
  for (const el of $('effectWaves').querySelectorAll('[data-wave]')) {
    const p = wavePlayer?.wave === el.dataset.wave && wavePlayer.record === pickedEffect ? wavePlayer : null;
    if (el.tagName === 'BUTTON') {
      if (el.disabled) continue;
      el.textContent = p && p.state !== 'failed' ? 'Stop' : 'Play';
      el.classList.toggle('on', Boolean(p && p.state !== 'failed'));
    } else {
      el.textContent = !p ? '' : p.state === 'loading' ? 'loading…' : p.state === 'failed' ? (p.why ? `Not played: ${p.why}` : 'Not played…')
        : `${clock(p.audio.currentTime)} / ${clock(p.audio.duration)}`;
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
      added.set(o.actor, { id: o.added.entity, actor: o.actor, kind: o.added.kind, from: { ...o.added.from }, ...actorPose(o, root.matrix),
                           ...(values ? { [o.added.kind]: values } : {}) });
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
  effectsDirty = true;
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
  actor ??= `${from.actor}_copy${++copySerial}`;
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
  // the map's own, or one of another map (its template read first: loadForeignTemplates)
  const template = effectIndex.get(targetKey(entity.from ?? {}))?.userData.source ?? foreignEffects.get(targetKey(entity.from ?? {}));
  if (!template || template.kind !== entity.kind || !Array.isArray(entity.location) || !Array.isArray(entity.rotation)) return null;
  const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
  if (serial > copySerial) copySerial = serial;
  const root = addedEffect(template, actorMatrix(entity.location, entity.rotation), entity.actor, entity.id, keptValues(entity[entity.kind]));
  Object.assign(root.userData.source, { location: [...entity.location], rotation: [...entity.rotation] });
  return root;
}
// The name of the marker under the pointer (the floor tiles' tip)
function effectTip() {
  tipDirty = false;
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
  effectsOn = on;
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
  normalEffects = Boolean(on) && effectsAvailable();
  if (!normalEffects && !effectsOn && gizmo.picks().ids.some(id => effectRoots.has(id))) select(null);
  effectsDirty = true; lightButton();
}
$('effectStay').onclick = e => { const root = effectRoots.get(pickedEffect); if (root) setEffectStays(root, !root.userData.stays); e.target.blur(); };
$('normalEffects').onchange = e => { setNormalEffects(e.target.checked); e.target.blur(); };
for (const kind of ['effect', 'sound', 'flare']) {
  const box = $(`effectShow-${kind}`);
  box.checked = effectFilters[kind] !== false;
  box.onchange = e => { effectFilters[kind] = e.target.checked; remember(EFFECT_FILTERS, JSON.stringify(effectFilters)); effectsDirty = true; e.target.blur(); };
}
const ZONE_OWN = 0x4aa3ff, ZONE_LWR = 0xffb347, ZONE_PICKED = 0xffffff;
let pickedZone = null, zonePlacing = false;
// While the zone gizmo is dragged: { id, change } drawn in place of the zone (zoneState)
let zoneDragView = null;
const zoneMaterial = (color, opacity, through = false) => (through
  ? new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false, depthTest: false })
  : new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide }));
const gameToView = p => new THREE.Vector3(p[0], p[2], p[1]);
// The zones and which are the map's own landings: { zones, own (the map's own landings), slots (zone index -> own index) }
function zoneState() {
  const zones = zonesNow().map(z => (zoneDragView?.change && z.id === zoneDragView.id ? { ...z, ...zoneDragView.change } : z)), own = data ? ownLandings(data) : [], slots = new Map(ownSlots(zones, own.length).map((z, k) => [z, k]));
  return { zones, own, slots };
}
// The floor's top under a point at a zone's ground: the map's floor tile there on the ground's level, by its saved
// height (the tutorial's road is 18 over its level's start, so marks at the ground itself sink under it), else null
let floorTopIndex = null;
function floorTop(x, y, ground) {
  const grid = data?.tileGrid;
  if (!grid?.origin || !data.tactical?.floorTiles) return null;
  if (floorTopIndex?.data !== data) {
    const tops = new Map();
    for (const f of data.tactical.floorTiles) tops.set(f.tile.join(','), Math.max(tops.get(f.tile.join(',')) ?? -Infinity, f.location[2]));
    floorTopIndex = { data, tops };
  }
  // the spot's tile as the game counts it; its ground's level takes a ground up to a unit under a level's start (the
  // maps' floors are a unit over the game's corner: 2 over the origin, as before)
  const [ox, oy, oz] = tileCorner(), [sx, sy, sz] = grid.size ?? [96, 96, 64];
  const key = [Math.floor((x - ox) / sx), Math.floor((y - oy) / sy), Math.floor((ground + 1 - oz) / sz)].join(',');
  const top = floorTopIndex.tops.get(key);
  return top !== undefined && top >= ground - 8 && top <= ground + sz ? top : null;
}
// Where the squad stands for a zone (spawns.js soldierSpots): a landing with no frame (the tutorial's) keeps its own
// points while its zone stays where the map has it
function zoneSoldiers(z, st = zoneState()) {
  const k = st.zones.findIndex(x => x.id === z.id);
  return soldierSpots(z, k >= 0 && st.slots.has(k) ? st.own[st.slots.get(k)] : null);
}
function zoneLabel(text, color) {
  const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 64;
  const c = canvas.getContext('2d');
  c.fillStyle = `#${color.toString(16).padStart(6, '0')}`; c.beginPath(); c.arc(32, 32, 28, 0, Math.PI * 2); c.fill();
  c.fillStyle = '#10161a'; c.font = 'bold 34px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, 32, 34);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true }));
  sprite.scale.set(70, 70, 1); sprite.renderOrder = 9; sprite.raycast = () => {};
  return sprite;
}
// The rigid move from one of the map's own landings to its zone: a point of the landing (the Skyranger) carried along
function carried(point, from, to) {
  const d = yawOf(to.direction) - yawOf(from.direction), v = turnBy([point[0] - from.location[0], point[1] - from.location[1], 0], d);
  return [to.location[0] + v[0], to.location[1] + v[1], point[2] + (to.location[2] - from.location[2])];
}
function refreshLandingZones() {
  for (const child of [...landingLayer.children]) {
    child.traverse(o => { o.geometry?.dispose(); if (o.material?.map) o.material.map.dispose(); });
    landingLayer.remove(child);
  }
  const on = data && !builderMode && data.scope === 'map' && !data.preview;
  $('landingRow').hidden = !on;
  placeZoneGizmo();
  if (!on) { $('landingPanel').hidden = true; return; }
  const st = zoneState(), { zones, own, slots } = st;
  zones.forEach((z, k) => {
    const group = new THREE.Group(), soldiers = zoneSoldiers(z, st), ground = groundOf(z), picked = z.id === pickedZone;
    // the marks lie on the floor under each soldier point, so a floor over the level's start doesn't hide them
    const tops = soldiers.map(s => floorTop(s.location[0], s.location[1], ground) ?? ground), lift = Math.max(...tops);
    const color = picked ? ZONE_PICKED : slots.has(k) ? ZONE_OWN : ZONE_LWR;
    group.userData.zoneId = z.id;
    const b = evacBox(z);
    // the evac zone's footprint on the ground (picked by it) and its box faintly
    const foot = new THREE.Mesh(new THREE.PlaneGeometry(b[3] - b[0], b[4] - b[1]).rotateX(-Math.PI / 2), zoneMaterial(color, picked ? 0.32 : 0.18));
    foot.position.set((b[0] + b[3]) / 2, lift + 3, (b[1] + b[4]) / 2); foot.userData.zoneId = z.id; foot.renderOrder = 3;
    group.add(foot);
    const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(b[3] - b[0], b[5] - b[2], b[4] - b[1])), zoneMaterial(color, 0.45, true));
    box.position.set((b[0] + b[3]) / 2, (b[2] + b[5]) / 2, (b[1] + b[4]) / 2); box.raycast = () => {}; group.add(box);
    // the six soldier points, where the squad stands
    soldiers.forEach((s, n) => {
      const dot = new THREE.Mesh(new THREE.CircleGeometry(22, 20).rotateX(-Math.PI / 2), zoneMaterial(color, 0.85));
      dot.position.copy(gameToView([s.location[0], s.location[1], tops[n] + 4])); dot.renderOrder = 4; dot.userData.zoneId = z.id; group.add(dot);
    });
    // an arrow the way the squad faces (the soldier points' facing)
    const mid = soldiers.reduce((a, s) => [a[0] + s.location[0] / soldiers.length, a[1] + s.location[1] / soldiers.length], [0, 0]);
    const f = turnBy([1, 0, 0], soldiers[0].yaw), tip = [mid[0] + f[0] * 260, mid[1] + f[1] * 260], side = [-f[1] * 50, f[0] * 50];
    const arrow = [mid[0], mid[1], tip[0], tip[1], tip[0], tip[1], tip[0] - f[0] * 70 + side[0], tip[1] - f[1] * 70 + side[1], tip[0], tip[1],
                   tip[0] - f[0] * 70 - side[0], tip[1] - f[1] * 70 - side[1]];
    const pts = []; for (let i = 0; i < arrow.length; i += 2) pts.push(arrow[i], lift + 6, arrow[i + 1]);
    const line = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)), zoneMaterial(color, 0.9, true));
    line.raycast = () => {}; group.add(line);
    const label = zoneLabel(String(k + 1), color); label.position.copy(gameToView([mid[0], mid[1], lift + 140])); group.add(label);
    // the number is drawn over everything and picks its zone wherever the zone is (under a floor, inside a piece)
    delete label.raycast; label.userData.zoneId = z.id; label.userData.zoneBadge = true;
    // one of the map's own landings: the grounded Skyranger, carried with it
    const o = slots.has(k) ? own[slots.get(k)] : null, mesh = o?.landing?.skyranger?.actors?.find(a => a.role === 'mesh');
    if (mesh) {
      const c = carried(mesh.location, o.zone, z), yaw = mesh.rotation[1] + yawOf(z.direction) - yawOf(o.zone.direction);
      const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(900, 300, 700)), zoneMaterial(color, 0.3, true));
      outline.position.copy(gameToView([c[0], c[1], c[2] + 150])); outline.rotation.y = -yaw * Math.PI / 32768; outline.raycast = () => {};
      group.add(outline);
    }
    // the Landing zones view: drawn over everything
    if (zonesOn) group.traverse(o => { if (o.material) { o.material.depthTest = false; o.renderOrder = Math.max(o.renderOrder, 8); } });
    landingLayer.add(group);
  });
  landingPanel();
}
// The map's own landing pieces (the frame, the Skyranger) whose zone has moved from where the map has them (as the
// Build reckons it: spawns.js landingUnmoved, so a zone a unit off its frame keeps them): the zone draws them, the
// pieces are not shown
function movedLandingActors() {
  const { zones, own, slots } = zoneState(), out = new Set();
  for (const [k, j] of slots) {
    const o = own[j], z = zones[k];
    if (landingUnmoved(z, o)) continue;
    if (o.frame) out.add(o.frame);
    for (const a of o.landing?.skyranger?.actors ?? []) out.add(a.path);
    if (!o.landing) {     // an older export: the Skyranger nearest the frame
      const sky = [...roots.values()].map(r => r.userData.source).filter(s => isLanding(s) && /skyranger/i.test(s.archetype ?? ''))
        .sort((a, b) => Math.hypot(a.location[0] - o.zone.location[0], a.location[1] - o.zone.location[1])
                      - Math.hypot(b.location[0] - o.zone.location[0], b.location[1] - o.zone.location[1]))[0];
      if (sky) out.add(sky.actor);
    }
  }
  return out;
}
// A change of the zones as one undo step; the project's own list from the first change on
function setZones(next, words) {
  const before = landingZones ? landingZones.map(z => ({ ...z })) : null, after = next.map(z => ({ ...z }));
  gizmo.record({
    redo: () => { landingZones = after.map(z => ({ ...z })); zonesChanged(); },
    undo: () => { landingZones = before ? before.map(z => ({ ...z })) : null; zonesChanged(); },
  });
  if (words) flashHint(`${words} · Ctrl+Z undoes`);
}
function zonesChanged() {
  if (pickedZone && !zonesNow().some(z => z.id === pickedZone)) pickedZone = null;
  effectsDirty = true;     // (the landing's effects and sound follow a moved zone)
  refreshLandingZones(); refreshGroundGrid(); cutaway(); projectChanged(); editChanged();
}
// The zones with plain EW's marks written out (`ew: true`): a list saved before the mark goes by order (ownSlots),
// and any change keeps the zones plain EW played
function explicitZones() {
  const zones = zonesNow().map(z => ({ ...z }));
  if (!explicitEw(zones)) for (const k of ownSlots(zones, data ? ownLandings(data).length : 0)) zones[k].ew = true;
  return zones;
}
function changeZone(id, change, words) {
  const zones = explicitZones(), k = zones.findIndex(z => z.id === id);
  if (k < 0) return;
  const next = change(zones, k);
  if (next) setZones(next, words);
}
function pickZone(id) {
  if (id && !zonesOn) setZonesShown(true);     // a zone is picked and edited in the Landing zones view only
  pickedZone = id;
  if (id && selected) select(null);
  refreshLandingZones();
}
// The picked zone's gizmo (the user, 13 November: a gizmo in place of the panel's buttons). Its handle stands on the
// drop zone's frame (StartLoc), on the ground. It moves the zone by whole tiles across and whole levels (64 units) up,
// and turns it by quarter turns about the vertical: the only steps a zone takes (an LZArray line faces one of four
// ways). G shows the arrows, R the ring; each drag is one undo step, Escape during one puts it back.
const zoneProxy = new THREE.Object3D(); world.add(zoneProxy);
const zoneGizmo = new TransformControls(camera, renderer.domElement);
zoneGizmo.attach(zoneProxy); zoneGizmo.enabled = false; zoneGizmo.setRotationSnap(Math.PI / 2);
const zoneGizmoHelper = zoneGizmo.getHelper(); zoneGizmoHelper.visible = false; world.add(zoneGizmoHelper);
let zoneGizmoMode = 'translate', zoneGizmoDrag = null;
const zoneGizmoWanted = () => Boolean(pickedZone && zonesOn && landingLayer.visible && !placing && !volumesOn && !lightsOn);
function placeZoneGizmo() {
  const z = zoneGizmoWanted() ? zonesNow().find(v => v.id === pickedZone) : null;
  zoneGizmo.enabled = zoneGizmoHelper.visible = Boolean(z);
  if (!z || zoneGizmo.dragging) return;
  zoneProxy.position.copy(gameToView([z.location[0], z.location[1], groundOf(z)]));
  zoneProxy.quaternion.identity(); zoneProxy.updateMatrixWorld(true);
  zoneGizmo.setMode(zoneGizmoMode);
  zoneGizmo.showX = zoneGizmo.showZ = zoneGizmoMode !== 'rotate';
}
function setZoneGizmoMode(mode) {
  zoneGizmoMode = mode; placeZoneGizmo();
  flashHint(mode === 'rotate' ? 'Turn the landing zone by quarter turns (G moves it)' : 'Move the landing zone by whole tiles and levels (R turns it)');
}
zoneGizmo.addEventListener('dragging-changed', e => { controls.enabled = !e.value; });
zoneGizmo.addEventListener('mouseDown', () => {
  const z = zonesNow().find(v => v.id === pickedZone);
  zoneGizmoDrag = z ? { id: z.id, from: z, at: zoneProxy.position.clone(), change: null, key: '' } : null;
});
zoneGizmo.addEventListener('objectChange', () => {
  const d = zoneGizmoDrag;
  if (!d || d.cancelled) return;
  if (zoneGizmo.mode === 'translate') {
    const p = zoneProxy.position, dx = Math.round((p.x - d.at.x) / 96) * 96, dz = Math.round((p.z - d.at.z) / 96) * 96,
          dy = Math.round((p.y - d.at.y) / 64) * 64;
    p.set(d.at.x + dx, d.at.y + dy, d.at.z + dz);
    // the zone's ground lands on a level of the grid: a zone saved off the levels (the tutorial's, fitted before the
    // ground was snapped: 16 under the grid) comes onto one with its first move
    const l = d.from.location, oz = data.tileGrid?.origin?.[2] ?? 0, ground = l[2] - ZONE_GROUND + dy;
    const level = Math.round(oz + Math.round((ground - oz) / 64) * 64) + ZONE_GROUND;
    const z = data.tileGrid && Math.abs(level - (l[2] + dy)) >= 1 ? level : l[2] + dy;
    d.change = dx || dy || dz ? { location: [l[0] + dx, l[1] + dz, z] } : null;
  } else {
    // a turn about the view's up is the opposite turn of the game's yaw (the view's basis is x, up, y)
    const q = Math.round(2 * Math.atan2(zoneProxy.quaternion.y, zoneProxy.quaternion.w) / (Math.PI / 2));
    zoneProxy.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), q * Math.PI / 2);
    const turns = ((-q % 4) + 4) % 4;
    d.change = turns ? { direction: ZONE_DIRECTIONS[(ZONE_DIRECTIONS.indexOf(d.from.direction) + turns) % 4] } : null;
  }
  const key = JSON.stringify(d.change);
  if (key !== d.key) { d.key = key; zoneDragView = { id: d.id, change: d.change }; refreshLandingZones(); }
});
zoneGizmo.addEventListener('mouseUp', () => {
  const d = zoneGizmoDrag;
  zoneGizmoDrag = null; zoneDragView = null;
  if (d?.change && !d.cancelled)
    changeZone(d.id, (zones, k) => { zones[k] = { ...zones[k], ...d.change }; return zones; }, d.change.direction ? 'Turned the landing zone' : 'Moved the landing zone');
  else refreshLandingZones();
  setTimeout(placeZoneGizmo, 0);       // (the controls end their drag after this event)
});
function cancelZoneGizmo() {
  if (!zoneGizmoDrag) return;
  zoneGizmoDrag.cancelled = true; zoneDragView = null; refreshLandingZones();
}
function zoneHit(clientX, clientY) {
  if (!landingLayer.visible || !landingLayer.children.length) return null;
  const hits = rayAt(clientX, clientY).intersectObjects(landingLayer.children, true).filter(h => h.object.userData.zoneId);
  // a zone's number badge first: it is drawn over everything, so a click on it is meant for its zone
  const hit = hits.find(h => h.object.userData.zoneBadge) ?? hits[0];
  return hit ? { id: hit.object.userData.zoneId, distance: hit.distance, point: hit.point, badge: Boolean(hit.object.userData.zoneBadge) } : null;
}
// The panel for the picked zone: its number, whether it is one of the map's own landings, its kind and mission, notes
function landingPanel() {
  const panel = $('landingPanel'), { zones, own, slots } = zoneState(), k = zones.findIndex(z => z.id === pickedZone);
  panel.hidden = k < 0 || volumesOn;
  if (k < 0) return;
  const z = zones[k];
  $('landingTitle').textContent = `Landing zone ${k + 1} of ${zones.length}`;
  const group = own[slots.get(k)]?.group;
  $('landingInfo').textContent = [slots.has(k) && own.length > 1 ? `Plain EW lands here in place of the map's own landing ${slots.get(k) + 1}${/^Group/.test(group ?? '') ? ` (${group})` : ''}.` : '',
    z.missionType || z.councilType ? `Kept for ${[z.missionType, z.councilType].filter(Boolean).join(', ')}.` : '',
    `Facing ${z.direction}; ground at ${Math.round(groundOf(z))}.`].filter(Boolean).join(' ');
  $('landingKind').value = ['normal', 'inside'].includes(z.kind) ? z.kind : 'normal';
  $('landingKind').disabled = !['normal', 'inside'].includes(z.kind ?? 'normal');
  $('landingLwr').checked = z.lwr !== false;
  $('landingEw').checked = slots.has(k);
  $('landingEw').disabled = !own.length;
  $('landingEw').parentElement.title = own.length ? `Plain Enemy Within lands here: one of the map's own landings is moved to this zone in the package. This map has ${plural(own.length, 'landing')} of its own, so up to ${own.length} zone${own.length === 1 ? '' : 's'} can be marked`
    : 'This map has no landing of its own that the editor can read, so plain Enemy Within plays none of these zones';
  $('landingPlay').hidden = !project || !projectsAvailable();
  const mission = headerMission(), serves = zoneServes(z, mission);
  $('landingPlay').disabled = !serves;
  $('landingPlay').title = serves ? 'Play in game, the squad landing at this zone' + (mission ? ` (${mission.label}, the mission the header shows)` : '')
    : `This zone is kept for another mission than the one the header shows (${mission?.label}): pick that mission in the header to land here`;
  const notes = zoneNotes(z, k, { zones, own, slots });
  $('landingNotes').hidden = !notes.length; $('landingNotes').textContent = notes.join(' ');
}
// Notes while editing, none of which blocks: outside the grid, a soldier point over no floor, a piece on one, played
// under LWR only, played nowhere
function zoneNotes(z, k, { zones, own, slots }) {
  const notes = [], grid = data.tileGrid, [ox, oy, oz] = grid.origin, [nx, ny, nz] = grid.dimensions, [sx, sy, sz] = grid.size ?? [96, 96, 64];
  const soldiers = zoneSoldiers(z, { zones, own, slots }), ground = groundOf(z);
  if (soldiers.some(s => s.location[0] < ox || s.location[0] > ox + nx * sx || s.location[1] < oy || s.location[1] > oy + ny * sy
                             || ground < oz - 1 || ground > oz + nz * sz)) notes.push('It is outside the tile grid: its soldiers would stand where there are no tiles.');
  // the floor tiles of the ground's level (the compiler's check_zones: the level of the ground plus 2)
  const level = Math.floor((ground + 2 - oz) / sz);
  const floor = new Set((data.tactical?.floorTiles ?? []).filter(f => floorStays(f.actor) && f.tile[2] === level).map(f => `${f.tile[0]},${f.tile[1]}`));
  const flat = [...roots.values()].filter(r => r.userData.source.added && !r.userData.deleted).map(r => new THREE.Box3().setFromObject(r))
    .filter(b => b.max.y - b.min.y <= 40 && Math.abs(b.max.y - ground) <= 20);
  const tall = [...roots.values()].filter(r => r.userData.source.added && !r.userData.deleted).map(r => new THREE.Box3().setFromObject(r))
    .filter(b => b.max.y - b.min.y > 40 && b.min.y < ground + 150 && b.max.y > ground + 8);
  // on a map grown as it is, the map's own low scenery past its far sides: the Build makes it walkable (F-100; the
  // compiler's scenery_floor), and the map's saved floor tiles stop at its own grid
  const ownDims = ownSize()?.dims, ox1 = ownDims ? ox + ownDims[0] * sx : Infinity, oy1 = ownDims ? oy + ownDims[1] * sy : Infinity;
  const scenery = stage?.grid && !cleared ? [...roots.values()]
    .filter(r => !r.userData.source.added && !r.userData.deleted && r.userData.source.actorClass === 'XComLevelActor')
    .map(r => new THREE.Box3().setFromObject(r))
    .filter(b => b.max.y - b.min.y <= 32 && b.min.y >= oz - sz / 4 && b.max.y <= oz + nz * sz && (b.max.x > ox1 || b.max.z > oy1) && Math.abs(b.max.y - ground) <= 20) : [];
  flat.push(...scenery);
  const bare = [], blocked = [];
  soldiers.forEach((s, n) => {
    const [x, y] = s.location, key = `${Math.floor((x - ox) / sx)},${Math.floor((y - oy) / sy)}`;
    if (!floor.has(key) && !flat.some(b => x >= b.min.x && x <= b.max.x && y >= b.min.z && y <= b.max.z)) bare.push(n + 1);
    if (tall.some(b => x >= b.min.x && x <= b.max.x && y >= b.min.z && y <= b.max.z)) blocked.push(n + 1);
  });
  if (bare.length) notes.push(`Soldier point${bare.length === 1 ? '' : 's'} ${bare.join(', ')} ${bare.length === 1 ? 'is' : 'are'} over no floor: lay floor there.`);
  if (blocked.length) notes.push(`A piece stands on soldier point${blocked.length === 1 ? '' : 's'} ${blocked.join(', ')}.`);
  if (!slots.has(k) && z.lwr === false) notes.push('Neither Long War nor plain EW uses it: it is never played.');
  if (slots.has(k) && slots.size < own.length) notes.push(`Plain EW also lands at ${plural(own.length - slots.size, 'more of the map\'s own landing')}, where the map has ${own.length - slots.size === 1 ? 'it' : 'them'}: mark ${own.length - slots.size === 1 ? 'another zone' : 'more zones'} Plain EW to move ${own.length - slots.size === 1 ? 'it' : 'them'}.`);
  return notes;
}
$('landingToggle').checked = landingLayer.visible;
$('landingToggle').onchange = e => { landingLayer.visible = e.target.checked; remember(LANDING_SHOWN, e.target.checked ? '1' : '0'); if (!e.target.checked) pickZone(null); e.target.blur(); };
const zoneTurn = (k, dir) => (zones => { zones[k] = { ...zones[k], direction: ZONE_DIRECTIONS[(ZONE_DIRECTIONS.indexOf(zones[k].direction) + dir + 4) % 4] }; return zones; });
$('landingPlay').onclick = landHere;
const turnZone = dir => changeZone(pickedZone, (zones, k) => zoneTurn(k, dir)(zones), 'Turned the landing zone');
// A copy is played by Long War; plain EW keeps the zones it had
function copyZone() {
  const id = uuid();
  changeZone(pickedZone, (zones, k) => {
    const l = zones[k].location, { lwr, ew, ...rest } = zones[k];
    zones.push({ ...rest, id, location: [l[0] + 192, l[1], l[2]] });
    return zones;
  }, 'Copied the landing zone');
  pickZone(id);
}
// Deleting the only zone marked Plain EW marks the first zone left, so plain EW always has one
function deleteZone() {
  let moved = false;
  changeZone(pickedZone, (zones, k) => {
    const [gone] = zones.splice(k, 1);
    if (gone.ew && zones.length && !zones.some(z => z.ew)) { zones[0] = { ...zones[0], ew: true }; moved = true; }
    return zones;
  }, 'Deleted the landing zone');
  if (moved) flashHint('Deleted the landing zone · zone 1 is now plain EW\'s · Ctrl+Z undoes');
  pickZone(null);
}
$('landingCopy').onclick = copyZone;
$('landingDelete').onclick = deleteZone;
$('landingKind').onchange = e => changeZone(pickedZone, (zones, k) => { zones[k] = { ...zones[k], kind: e.target.value }; return zones; }, 'Changed the landing zone\'s kind');
$('landingLwr').onchange = e => changeZone(pickedZone, (zones, k) => {
  const { lwr, ...rest } = zones[k]; zones[k] = e.target.checked ? rest : { ...rest, lwr: false }; return zones;
}, e.target.checked ? 'Long War lands at the zone' : 'Long War no longer lands at the zone');
// Plain EW: at least one zone, and no more than the map has landings of its own (the user, 13 November)
$('landingEw').onchange = e => {
  const zones = explicitZones(), k = zones.findIndex(z => z.id === pickedZone), own = data ? ownLandings(data).length : 0;
  const marked = zones.filter(z => z.ew).length;
  if (k < 0) return;
  if (e.target.checked && marked >= own) {
    e.target.checked = false;
    banner(`This map has ${plural(own, 'landing')} of its own, so plain EW can land at ${own === 1 ? 'one zone' : `${own} zones`}: uncheck Plain EW on ${own === 1 ? 'the other zone' : 'another zone'} first.`, [], { timeout: 8000 });
    return;
  }
  if (!e.target.checked && zones[k].ew && marked <= 1) {
    e.target.checked = true;
    banner('Plain EW needs a landing zone: check Plain EW on another zone first.', [], { timeout: 8000 });
    return;
  }
  changeZone(pickedZone, (list, j) => {
    const { ew, ...rest } = list[j]; list[j] = e.target.checked ? { ...rest, ew: true } : rest;
    // the list keeps saying which zones plain EW plays when the last mark of an old list's order goes
    if (!list.some(z => z.ew)) list[j] = { ...rest, ew: true };
    return list;
  }, e.target.checked ? 'Plain EW lands at the zone' : 'Plain EW no longer lands at the zone');
};
// Add a landing zone (the piece list's Landing zones kind): the zones are shown, and the next click on the view places
// one on the tile under it, at the ground grid's height
function startZonePlacing() {
  setZonesShown(true);
  if (!landingLayer.visible) { landingLayer.visible = true; $('landingToggle').checked = true; remember(LANDING_SHOWN, '1'); refreshLandingZones(); }
  zonePlacing = true; renderer.domElement.style.cursor = 'crosshair';
  flashHint('Click the tile the new landing zone is to stand on · Esc cancels');
}
function stopZonePlacing() {
  if (!zonePlacing) return;
  zonePlacing = false; renderer.domElement.style.cursor = ''; pieces.setChosen?.(null); restingHint();
}
function placeZone(clientX, clientY) {
  zonePlacing = false; renderer.domElement.style.cursor = ''; pieces.setChosen?.(null);
  const ground = groundHeight(), at = rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -ground), new THREE.Vector3());
  if (!at) return;
  const [ox, oy] = data.tileGrid.origin, first = zonesNow()[0];
  // a zone's StartLoc sits a unit off a tile's corner, as LWR's lines do (Bar's first: 719, -1681)
  const x = ox + Math.round((at.x - ox) / 96) * 96 - 1, y = oy + Math.round((at.z - oy) / 96) * 96 - 1, id = uuid();
  const zones = explicitZones(), ew = !zones.some(z => z.ew) && ownLandings(data).length > 0;
  setZones([...zones, { id, location: [x, y, ground + 64], direction: 'north', kind: first?.kind === 'inside' ? 'inside' : 'normal', ...(ew ? { ew: true } : {}) }], 'Added a landing zone');
  pickZone(id);
}
// After the cleared mark changes: the menu, the streamed patches' pieces and the view-only lights (a cleared map
// draws none: the Build takes them out), the ground grid
function clearedChanged() {
  if (!data) return;
  $('projectSize').hidden = !projectsAvailable();
  $('projectClear').hidden = !projectsAvailable();
  $('projectMissions').hidden = !projectsAvailable();
  mergedBuildings = null;
  refreshMissionPicker();     // a project's missions, or none
  refreshLightVisibility();
  effectsDirty = true;
  if (!builderMode) cutaway();
  refreshGroundGrid(); refreshLandingZones();
}
// The Buildings view (prefab plan 5.3a): the project's buildings as boxes in the view, one for each box of each floor,
// made, stretched and moved there. A box is a root as a piece or a light is (volumeRoots; the gizmo moves it, by whole
// tiles and levels), drawn see-through in its floor's colour; the map's own floor volumes show in grey, never picked.
// While the view is on (the tool strip's button, Shift+B) only boxes are picked: no piece or light can be selected or
// moved by accident. `buildings`, what the project saves and the Floor buttons, the cutaway and the pieces' Floors
// lines read, is written from the boxes after every edit (syncVolumes).
const FLOOR_COLOURS = [0x4aa3ff, 0xffb347, 0x5ad17a, 0xe06cff, 0xff6b6b, 0x4ad1c8, 0xd1c84a, 0xb0b8c0];
const volumeMaterials = FLOOR_COLOURS.map(color => ({
  fill: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false }),
  picked: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.26, side: THREE.DoubleSide, depthWrite: false }),
  // while it is drawn or stretched: the same see-through box, a little whiter
  drag: new THREE.MeshBasicMaterial({ color: new THREE.Color(color).lerp(new THREE.Color(0xffffff), 0.45), transparent: true, opacity: 0.3,
                                      side: THREE.DoubleSide, depthWrite: false }),
  line: new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9, depthWrite: false }),
  through: new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3, depthWrite: false, depthTest: false }) }));
const ownVolumeMaterials = {
  fill: new THREE.MeshBasicMaterial({ color: 0x9aa7b0, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false }),
  picked: new THREE.MeshBasicMaterial({ color: 0xc8d4dc, transparent: true, opacity: 0.24, side: THREE.DoubleSide, depthWrite: false }),
  line: new THREE.LineBasicMaterial({ color: 0x9aa7b0, transparent: true, opacity: 0.45, depthWrite: false }) };
const ownVolumeLayer = new THREE.Group(); world.add(ownVolumeLayer);
const buildingMeta = new Map();     // building id -> { name, kind }
let volumesOn = false, volumeSerial = 0, volumesKey = '[]', volumeTool = null, volumeDrag = null, volumeHover = null;
let volumeClip = null, lastBuilding = null, aroundIds = [];
let ownPicked = null;       // one of the map's own boxes, picked to read: its fill mesh (never moved or changed)
// The map's own buildings selected with pieces in the normal view (the Normal button's Floor boxes): a copy of the
// selection then gets a building of the project with the same boxes. They are never moved, turned or deleted: the
// Build leaves the map's own volumes as they are (the user, 11 November 2026, after copying the Bar).
const ownSet = new Set();
const volumeGrid = () => (data?.tileGrid?.origin && data.tileGrid.dimensions
  ? { origin: data.tileGrid.origin, dimensions: data.tileGrid.dimensions, size: data.tileGrid.size ?? [96, 96, 64], unbounded: builderMode,
      ...(builderMode ? { heights: [PREFAB_MIN_Z, PREFAB_MAX_Z] } : {}) } : null);
const newBuildingId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
const boxCount = n => `${n} ${n === 1 ? 'box' : 'boxes'}`;
const liveVolumes = () => [...volumeRoots.values()].filter(r => !r.userData.deleted);
// (in the normal view a building is picked whole: every box that moves with the selection)
const pickedVolumes = () => (volumesOn ? gizmo.picks().ids.map(id => volumeRoots.get(id)).filter(r => r && !r.userData.deleted)
  : gizmo.selection().filter(r => r.userData.volume && !r.userData.deleted));
// A box's place, [x0, y0, z0, x1, y1, z1] in game units. Its root's matrix is the whole box: a unit cube moved to its
// middle, scaled to its size and, after a turn with pieces in the normal view, turned by quarter turns; so the
// gizmo's moves, turns and undo carry all of it. The box is what that cube covers along the axes.
function volumeBox(root) {
  const e = root.matrix.elements, r = v => Number(v.toFixed(3)) + 0;
  const half = row => (Math.abs(e[row]) + Math.abs(e[4 + row]) + Math.abs(e[8 + row])) / 2;
  const hx = half(0), hz = half(1), hy = half(2);
  return [r(e[12] - hx), r(e[14] - hy), r(e[13] - hz), r(e[12] + hx), r(e[14] + hy), r(e[13] + hz)];
}
function setVolumeBox(root, box) {
  const v = root.userData.volume, size = [box[3] - box[0], box[4] - box[1], box[5] - box[2]];
  const centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2];
  root.matrix.makeScale(size[0], size[2], size[1]).setPosition(centre[0], centre[2], centre[1]); root.matrixWorldNeedsUpdate = true;
  // its unedited pose is where it is put: the gizmo's moves count from here
  Object.assign(root.userData.source, { matrix: root.matrix.toArray(), location: centre, rotation: [0, 0, 0] });
  root.userData.edit = null;
  v.size = size;
  if (!root.children.length) {
    const geometry = new THREE.BoxGeometry(1, 1, 1), edges = new THREE.EdgesGeometry(geometry);
    const fill = new THREE.Mesh(geometry), line = new THREE.LineSegments(edges), through = new THREE.LineSegments(edges.clone());
    fill.userData.volumeId = root.userData.source.id; line.raycast = through.raycast = () => {};
    for (const part of [fill, line, through]) { part.renderOrder = 2; root.add(part); }
    root.userData.fill = fill; root.userData.lines = [line, through];
  }
  // drawn a unit short of its faces, so two boxes that touch don't flicker
  for (const part of root.children) part.scale.set(1 - 1 / Math.max(2, size[0]), 1 - 1 / Math.max(2, size[2]), 1 - 1 / Math.max(2, size[1]));
  paintVolume(root);
}
// A box's colours: its floor's, fuller when selected, whiter while it is drawn or stretched.
function paintVolume(root, picked = pickedVolumes().includes(root)) {
  const m = volumeMaterials[root.userData.volume.effective % volumeMaterials.length];
  root.userData.fill.material = volumeDrag?.root === root ? m.drag : picked ? m.picked : m.fill;
  root.userData.lines[0].material = m.line; root.userData.lines[1].material = m.through;
}
// (`origin`: the map's floor volume a box of one of the map's buildings is, null for a new box; it holds only while
// the box is in that building, its `home`)
function makeVolume(box, building, floor, origin = null) {
  const id = `volume:${++volumeSerial}`, root = new THREE.Group();
  root.matrixAutoUpdate = false;
  root.userData = { volume: { building, floor, size: [0, 0, 0], effective: floor, origin, home: building }, deleted: false, edit: null,
                    source: { id, isVolume: true, sourcePackage: '', layer: 'volume', actor: id, hidden: false } };
  volumeRoots.set(id, root); volumeLayer.add(root);
  setVolumeBox(root, box);
  return root;
}
// The project's buildings as the boxes say them: a building's floors are its boxes' floor numbers in order (a number
// no box has is no floor: the ones above it count down), and each box's floor as counted (volume.effective).
function buildingsFromVolumes() {
  const by = new Map();
  for (const root of liveVolumes()) { const b = root.userData.volume.building; if (!by.has(b)) by.set(b, []); by.get(b).push(root); }
  const out = [];
  for (const [id, list] of by) {
    const numbers = [...new Set(list.map(r => r.userData.volume.floor))].sort((a, b) => a - b).slice(0, BUILDING_FLOORS_MAX);
    for (const r of list) r.userData.volume.effective = Math.max(0, Math.min(numbers.length - 1, numbers.indexOf(r.userData.volume.floor)));
    const meta = buildingMeta.get(id) ?? { name: '', kind: 'building' };
    const floorRoots = numbers.map((n, k) => list.filter(r => r.userData.volume.effective === k));
    // one of the map's: `replaces` its building volume, each box with the floor volume it is (tidyBuilding sorts them)
    out.push(tidyBuilding({ id, name: meta.name, kind: meta.kind, ...(meta.map ? { replaces: mapTarget(meta.map) } : {}),
      floors: floorRoots.map(rs => (meta.map
        ? { boxes: rs.map(volumeBox), volumes: rs.map(r => (r.userData.volume.home === id ? r.userData.volume.origin : null)) }
        : { boxes: rs.map(volumeBox).sort((a, b) => a.join().localeCompare(b.join())) })) }));
  }
  return out.sort((a, b) => a.id.localeCompare(b.id));
}
// After an edit of the boxes (a move let go, an undo, a new box): the project's buildings follow, and with them the
// Floor buttons, the cutaway and the pieces' Floors lines.
function syncVolumes() {
  if (!data || gizmo.controls.dragging || volumeDrag) return;
  const next = buildingsFromVolumes(), key = JSON.stringify(next);
  if (key === volumesKey) return;
  volumesKey = key; buildings = next; buildingsVersion++; mergedBuildings = null;
  liveCache = null;     // a group's buildings are counted by their boxes
  floorOptions();       // the Floor buttons, then the cutaway
}
// The project's buildings put in the view (a project opened, or the edits cleared): every box made anew. The history
// is the caller's to forget, as for added pieces.
// The map's own buildings that can be edited come with them, each as the project's record has it (changed or
// deleted), else as the map has it. Returns the records of map buildings this export can't edit (a van's, one it
// lacks, a second record for one): the caller carries them unchanged.
function setBuildings(next) {
  for (const root of volumeRoots.values()) { for (const child of root.children) child.geometry.dispose(); volumeLayer.remove(root); }
  volumeRoots.clear(); buildingMeta.clear(); lastBuilding = null;
  const editable = new Map((data?.buildings ?? []).filter(mapEditable).map(b => [targetKey(mapTarget(b)), b]));
  const records = new Map(), unknown = [];
  for (const b of next.filter(validBuilding)) {
    if (b.replaces) {
      const key = targetKey(b.replaces);
      if (editable.has(key) && !records.has(key)) records.set(key, b); else unknown.push(b);
      continue;
    }
    const tidy = tidyBuilding(b);
    buildingMeta.set(tidy.id, { name: tidy.name, kind: tidy.kind });
    tidy.floors.forEach((floor, k) => { for (const box of floor.boxes) makeVolume(box, tidy.id, k); });
  }
  for (const [key, e] of editable) {
    const record = records.get(key), id = mapIdOf(e);
    buildingMeta.set(id, { name: record?.name || short(e.actor), kind: record && !record.deleted ? record.kind ?? 'building' : mapKind(e), map: e });
    const floors = record?.deleted ? [] : record ? tidyBuilding(record).floors : mapFloors(e);
    floors.forEach((floor, k) => floor.boxes.forEach((box, n) => makeVolume(box, id, k, floor.volumes?.[n] ?? null)));
  }
  buildings = buildingsFromVolumes(); volumesKey = JSON.stringify(buildings);
  buildingsVersion++; mergedBuildings = null;
  if (data) drawOwnVolumes();
  refreshVolumes();
  if (data) floorOptions();
  return unknown;
}
// What is drawn of the boxes: only with the view on, each in its floor's colour, the selected ones fuller.
function refreshVolumes() {
  const picked = new Set(pickedVolumes());
  for (const root of volumeRoots.values()) {
    root.visible = (volumesOn || (boxesShown && !lightsOn)) && !root.userData.deleted;
    paintVolume(root, picked.has(root));
  }
  const ownShown = volumesOn || (boxesShown && !lightsOn);
  if (ownShown && !ownVolumeLayer.children.length && data?.buildings?.some(b => !mapEditable(b))) drawOwnVolumes();
  ownVolumeLayer.visible = ownShown;
  for (const part of ownVolumeLayer.children) if (part.userData.own)
    part.material = part === ownPicked || ownSet.has(part.userData.own.building) ? ownVolumeMaterials.picked : ownVolumeMaterials.fill;
}
function drawOwnVolumes() {
  for (const child of [...ownVolumeLayer.children]) { child.geometry.dispose(); ownVolumeLayer.remove(child); }
  ownPicked = null;
  for (const b of (data?.buildings ?? []).filter(b => !mapEditable(b))) (b.floors ?? []).forEach((floor, k) => (floor.boxes ?? []).forEach(({ min, max }, n) => {
    const geometry = new THREE.BoxGeometry(max[0] - min[0], max[2] - min[2], max[1] - min[1]);
    const fill = new THREE.Mesh(geometry, ownVolumeMaterials.fill), line = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), ownVolumeMaterials.line);
    // picked to be read, never changed: the building, the floor and the floor volume it is
    fill.userData.own = { building: b, floor: k, box: [...min, ...max],
                          volume: (floor.volumes ?? []).length === (floor.boxes ?? []).length ? floor.volumes[n] : null };
    line.raycast = () => {};
    for (const part of [fill, line]) { part.position.set((min[0] + max[0]) / 2, (min[2] + max[2]) / 2, (min[1] + max[1]) / 2); part.renderOrder = 1; ownVolumeLayer.add(part); }
  }));
}
function setOwnPicked(mesh) {
  if (mesh === ownPicked) return;
  ownPicked = mesh;
  refreshVolumes(); volumePanel();
}
function setVolumesShown(on) {
  const next = Boolean(on) && data?.scope === 'map' && !data.preview;
  if (next === volumesOn) return;
  if (next) {
    if (zonesOn) setZonesShown(false);
    if (effectsOn) setEffectsShown(false);
    // the pieces selected on the way in: "Boxes around them" makes a building of them
    aroundIds = gizmo.selection().filter(r => roots.has(r.userData.source.id) && !r.userData.source.cover && !r.userData.deleted).map(r => r.userData.source.id);
    stopPickBox();
    select(null);
    lightsOn = false;
    volumesOn = true;
    if (gizmo.mode === 'rotate') gizmo.setMode('translate');
    if (!ownVolumeLayer.children.length) drawOwnVolumes();
  } else {
    setVolumeTool(null);
    volumesOn = false; aroundIds = []; ownPicked = null;
    if (volumeRoots.has(gizmo.active)) select(null);
  }
  syncLights();
  refreshVolumes(); volumePanel(); restingHint();
}
// ---- changes, each one undo step. A box is never thrown away while the history may name it: deleting hides it.
const volumeState = root => ({ box: volumeBox(root), building: root.userData.volume.building, floor: root.userData.volume.floor, deleted: root.userData.deleted });
function putVolumeState(root, s) {
  setVolumeBox(root, s.box); root.userData.volume.building = s.building; root.userData.volume.floor = s.floor; root.userData.deleted = s.deleted;
}
// change(): alters boxes (`targets`) and building names and kinds; recorded with what they were before.
function recordVolumes(targets, change, selection = null) {
  const before = targets.map(volumeState), metaBefore = new Map([...buildingMeta].map(([k, v]) => [k, { ...v }])), picksBefore = gizmo.picks();
  change();
  const after = targets.map(volumeState), metaAfter = new Map([...buildingMeta].map(([k, v]) => [k, { ...v }]));
  const put = (states, meta, picks) => {
    targets.forEach((root, i) => putVolumeState(root, states[i]));
    buildingMeta.clear(); for (const [k, v] of meta) buildingMeta.set(k, { ...v });
    if (picks) gizmo.setSelection(picks.ids.filter(id => !volumeRoots.get(id)?.userData.deleted), picks.active);
  };
  gizmo.record({ redo: () => put(after, metaAfter, selection ?? picksBefore), undo: () => put(before, metaBefore, picksBefore) });
}
// The floor a new box at height z0 is in a building: the floor whose boxes start there, else one for each floor that
// starts lower.
function floorFor(building, z0) {
  const starts = new Map();
  for (const r of liveVolumes()) if (r.userData.volume.building === building) {
    const f = r.userData.volume.floor, z = volumeBox(r)[2];
    starts.set(f, Math.min(starts.get(f) ?? Infinity, z));
  }
  for (const [f, z] of starts) if (Math.abs(z - z0) <= 8) return f;
  const below = [...starts].filter(([, z]) => z < z0).map(([f]) => f);
  return Math.min(BUILDING_FLOORS_MAX - 1, below.length ? Math.max(...below) + 1 : 0);
}
function newBuilding() {
  const id = newBuildingId();
  let n = 1;
  const names = new Set([...buildingMeta.values()].map(m => m.name));
  while (names.has(`Building ${n}`)) n++;
  buildingMeta.set(id, { name: `Building ${n}`, kind: 'building' });
  return id;
}
// The building a new box joins: the one of the box selected (or made) last, while it still has a box.
function buildingForNew() {
  const live = new Set(liveVolumes().map(r => r.userData.volume.building));
  const from = volumeRoots.get(selected)?.userData.volume.building ?? lastBuilding;
  return live.has(from) ? from : null;
}
function addVolumes(boxes, building = null) {
  const id = building ?? buildingForNew() ?? newBuilding();
  const made = boxes.map(({ box, floor }) => { const root = makeVolume(box, id, floor ?? floorFor(id, box[2])); root.userData.deleted = true; return root; });
  const meta = { ...buildingMeta.get(id) };
  gizmo.record({ redo: () => { for (const r of made) r.userData.deleted = false; if (!buildingMeta.has(id)) buildingMeta.set(id, { ...meta });
                               gizmo.setSelection(made.map(r => r.userData.source.id)); },
                 undo: () => { for (const r of made) r.userData.deleted = true; gizmo.setSelection([]); } });
  lastBuilding = id;
  return made;
}
function deleteVolumes() {
  const targets = pickedVolumes();
  if (!targets.length) return;
  recordVolumes(targets, () => { for (const r of targets) r.userData.deleted = true; }, { ids: [], active: null });
  flashHint(`${boxCount(targets.length)} deleted · Ctrl+Z brings ${targets.length === 1 ? 'it' : 'them'} back`);
}
function copyVolumes(cut = false) {
  const targets = pickedVolumes();
  if (!targets.length) return;
  volumeClip = targets.map(r => ({ box: volumeBox(r), building: r.userData.volume.building, floor: r.userData.volume.floor }));
  if (cut) deleteVolumes();
  flashHint(`${boxCount(targets.length)} ${cut ? 'cut' : 'copied'} · Ctrl+V puts ${targets.length === 1 ? 'a copy' : 'copies'} on top, as the next floor`);
}
// Paste: each copied box again on top of where it was copied from, as the floor above it in its building (a building
// that is gone gets the boxes as a new one). Moved from there with the gizmo.
function pasteVolumes() {
  if (!volumeClip?.length) { flashHint('Nothing copied yet: select a box and press Ctrl+C'); return; }
  const live = new Set(liveVolumes().map(r => r.userData.volume.building)), grid = volumeGrid();
  const top = grid && !builderMode ? grid.origin[2] + grid.dimensions[2] * grid.size[2] : Infinity;
  const byBuilding = new Map();
  for (const c of volumeClip) { if (!byBuilding.has(c.building)) byBuilding.set(c.building, []); byBuilding.get(c.building).push(c); }
  const made = [];
  for (const [building, clips] of byBuilding) {
    const rise = Math.max(...clips.map(c => c.box[5])) - Math.min(...clips.map(c => c.box[2]));
    const fits = Math.max(...clips.map(c => c.box[5])) + rise <= top + 0.5 && live.has(building);
    made.push(...addVolumes(clips.map(c => ({ box: fits ? [c.box[0], c.box[1], c.box[2] + rise, c.box[3], c.box[4], c.box[5] + rise] : [...c.box],
                                              floor: fits ? Math.min(BUILDING_FLOORS_MAX - 1, c.floor + 1) : c.floor })),
                            live.has(building) ? building : newBuilding()));
  }
  gizmo.setSelection(made.map(r => r.userData.source.id));
  flashHint(`${boxCount(made.length)} pasted`);
}
// A box for each floor of a building around the pieces that were selected when the view was turned on.
function volumesAround() {
  const grid = volumeGrid(), boxes = aroundIds.map(id => roots.get(id)).filter(r => r && !r.userData.deleted).map(r => boxOf(r, true)?.slice()).filter(Boolean);
  const floors = grid && floorsAround(boxes, grid);
  if (!floors) { flashHint('Select the building\'s pieces first, then turn this view on'); return; }
  const id = newBuilding();
  addVolumes(floors.map((f, k) => ({ box: f.boxes[0], floor: k })), id);
}
// ---- the selected box's six face handles: a drag stretches that face, to tile lines and levels (Alt: 8 units)
const FACES = [['x0', 0, -1], ['x1', 0, 1], ['y0', 1, -1], ['y1', 1, 1], ['z0', 2, -1], ['z1', 2, 1]];
const FACE_WORDS = { x0: 'West side', x1: 'East side', y0: 'South side', y1: 'North side', z0: 'Bottom', z1: 'Top' };
const volumeHandleLayer = new THREE.Group(); world.add(volumeHandleLayer);
const volumeHandles = new Map(FACES.map(([key]) => {
  const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
  mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material; volumeHandleLayer.add(mesh);
  return [key, mesh];
}));
const volumeStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(36), 3)),
                                           new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
volumeStems.renderOrder = 8; volumeStems.raycast = () => {}; volumeStems.frustumCulled = false; volumeHandleLayer.add(volumeStems);
const handleVolume = () => { const r = volumeRoots.get(selected); return volumesOn && r && !r.userData.deleted && !placing && pickedVolumes().length === 1 ? r : null; };
// the picked no-spawn volume whose handles show: one the project moves (spawnMovable), its markers shown, nothing placed
const spawnVolumeHandle = () => {
  const e = spawnEntry(pickedSpawn);
  return e?.record.kind === 'noSpawn' && spawnMovable(e) && spawnsShown() && projectsAvailable() && !placing && !spawnPlacing && !volumesOn
    && !lightsOn && !zonesOn && !effectsOn && !missionGizmo.dragging && spawnBoxNow(e) ? e : null;
};
// the box the six handles are on: the selected building's box, a picked no-spawn volume's, or in the normal view the
// select box
const handleBox = () => {
  const r = handleVolume();
  if (r) return volumeBox(r);
  const e = spawnVolumeHandle();
  if (e) return spawnBoxNow(e);
  return pickBox && !volumesOn && !placing && pickDrag?.kind !== 'new' ? pickBox : null;
};
// game point -> the view's
const viewPoint = ([x, y, z]) => new THREE.Vector3(x, z, y);
function facePoint(box, key) {
  const [, axis, side] = FACES.find(f => f[0] === key), p = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2];
  p[axis] = side < 0 ? box[axis] : box[axis + 3];
  return p;
}
// Where a face's handle is drawn: out from the face along its axis, clear of the gizmo's arrows, which reach about
// an eighth of the camera's distance from the box's middle whatever the box's size.
function handlePoint(box, key) {
  const [, axis, side] = FACES.find(f => f[0] === key), p = facePoint(box, key);
  const centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2], d = camera.position.distanceTo(viewPoint(centre));
  p[axis] = centre[axis] + side * Math.max((box[axis + 3] - box[axis]) / 2 + d * 0.035, d * 0.2);
  return p;
}
function updateVolumeHandles() {
  const box = volumeDrag?.kind === 'face' ? volumeBox(volumeDrag.root) : volumeDrag?.kind === 'spawn' ? volumeDrag.box : handleBox();
  volumeHandleLayer.visible = Boolean(box) && !gizmo.controls.dragging && !missionGizmo.dragging;
  pickBoxParts.move.visible = volumeHandleLayer.visible && Boolean(pickBox) && !volumesOn;
  if (!volumeHandleLayer.visible) { if (volumeHover) hoverVolumeHandle(null); return; }
  const lit = volumeDrag?.key ?? pickDrag?.key ?? (pickDrag?.kind === 'move' ? 'move' : volumeHover), stems = volumeStems.geometry.attributes.position;
  if (pickBoxParts.move.visible) {
    pickBoxParts.move.position.copy(viewPoint(pickMovePoint()));
    pickBoxParts.moveMaterial.color.setHex(lit === 'move' ? 0xffe27a : 0x96e5d7);
    scaleMarker(pickBoxParts.move, camera, pickBoxParts.move.position);
  }
  let n = 0;
  for (const [key, mesh] of volumeHandles) {
    mesh.position.copy(viewPoint(handlePoint(box, key)));
    mesh.userData.material.color.setHex(key === lit ? 0xffe27a : 0xffffff);
    scaleMarker(mesh, camera, mesh.position);
    const from = viewPoint(facePoint(box, key));
    stems.setXYZ(n++, from.x, from.y, from.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z);
  }
  stems.needsUpdate = true;
}
function volumeHandleNear(x, y) {
  const box = handleBox();
  if (!box) return null;
  const project = projector();
  return FACES.map(([key]) => { const s = project(viewPoint(handlePoint(box, key))); return s && { key, d: Math.hypot(s[0] - x, s[1] - y) }; })
    .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.key ?? null;
}
function hoverVolumeHandle(key) {
  if (key === volumeHover) return;
  volumeHover = key;
  renderer.domElement.style.cursor = key ? 'grab' : volumeTool || pickTool ? 'crosshair' : '';
  renderer.domElement.title = !key ? '' : key === 'move' ? 'Drag to move the box over the ground'
    : volumesOn ? `${FACE_WORDS[key]}: drag to stretch the box (to tile lines and levels; Alt for steps of 8)`
      : spawnVolumeHandle() ? `${FACE_WORDS[key]}: drag to stretch the no-spawn volume (to tile lines and levels; Alt for steps of 8)` : `${FACE_WORDS[key]}: drag to stretch the box`;
}
// Where the pointer's ray comes nearest a line through `origin` along game axis `axis`: the coordinate on that axis.
function alongAxis(clientX, clientY, origin, axis) {
  const ray = rayAt(clientX, clientY).ray, o = viewPoint(origin), d = viewPoint([axis === 0 ? 1 : 0, axis === 1 ? 1 : 0, axis === 2 ? 1 : 0]);
  const w = o.clone().sub(ray.origin), b = d.dot(ray.direction), e = d.dot(w), f = ray.direction.dot(w), den = 1 - b * b;
  if (Math.abs(den) < 1e-6) return null;
  return origin[axis] + (b * f - e) / den;
}
// The cursor's floors in the Buildings view (floors.js cursorStoreys): around each of the project's boxes, and the
// map's own box being read, a yellow line at each height where a cursor floor starts over it, with the floor's
// number at a corner for the selected ones. A box's bottom should sit on one (the panel says when it doesn't), and
// a face dragged up or down goes to one when it is near.
const cursorRingLayer = new THREE.Group();
cursorRingLayer.renderOrder = 3; world.add(cursorRingLayer);
const ringMaterials = { near: new THREE.LineBasicMaterial({ color: 0xffd84a, depthTest: false, transparent: true, opacity: 0.95 }),
                        far: new THREE.LineBasicMaterial({ color: 0xffd84a, depthTest: false, transparent: true, opacity: 0.3 }) };
const ringLabels = new Map();
function ringLabel(label) {
  if (!ringLabels.has(label)) {
    const canvas = Object.assign(document.createElement('canvas'), { width: 128, height: 64 }), c = canvas.getContext('2d');
    c.fillStyle = 'rgba(20, 24, 30, 0.85)'; c.beginPath(); c.roundRect(2, 2, 124, 60, 12); c.fill();
    c.strokeStyle = '#ffd84a'; c.lineWidth = 3; c.stroke();
    c.fillStyle = '#ffd84a'; c.font = '600 30px system-ui, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(label, 64, 34);
    ringLabels.set(label, new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true }));
  }
  return ringLabels.get(label);
}
let cursorRingKey = '';
function drawCursorRings() {
  const storeys = volumesOn && data ? storeysNow() : null, items = [];
  if (storeys?.length) {
    const picked = new Set(pickedVolumes());
    for (const root of volumeRoots.values()) if (root.visible) items.push([volumeBox(root).map(v => Math.round(v)), picked.has(root) || volumeDrag?.root === root]);
    if (ownPicked) items.push([ownPicked.userData.own.box.map(v => Math.round(v)), true]);
  }
  const key = JSON.stringify(items);
  if (key === cursorRingKey) return;
  cursorRingKey = key;
  for (const child of [...cursorRingLayer.children]) { child.geometry?.dispose(); cursorRingLayer.remove(child); }
  const seen = new Set();
  for (const [box, near] of items.sort((a, b) => b[1] - a[1])) {
    const out = 14, x0 = box[0] - out, x1 = box[3] + out, y0 = box[1] - out, y1 = box[4] + out;
    for (const s of storeysOver(storeys, box)) {
      const at = `${x0},${y0},${x1},${y1},${Math.round(s.z)}`;
      if (seen.has(at)) continue;
      seen.add(at);
      const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
        [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => viewPoint([x, y, s.z]))), near ? ringMaterials.near : ringMaterials.far);
      ring.raycast = () => {}; ring.renderOrder = 3; cursorRingLayer.add(ring);
      if (!near) continue;
      const label = new THREE.Sprite(ringLabel(`${s.floor} · ${Math.round(s.z)}`));
      label.position.copy(viewPoint([x0, y0, s.z + 14])); label.scale.set(76, 38, 1); label.renderOrder = 4; label.raycast = () => {};
      cursorRingLayer.add(label);
    }
  }
}
// What the panel says of the cursor's floors over a box.
function cursorLine(over, made) {
  if (!over.length) return 'No cursor volume of the map is over it: the cursor has no floors here.';
  const heights = over.map(s => Math.round(s.z)), list = heights.length > 1 ? `${heights.slice(0, -1).join(', ')} and ${heights.at(-1)}` : `${heights[0]}`;
  return `The cursor's ${plural(over.length, 'floor')} here ${over.length === 1 ? 'starts' : 'start'} at ${list} (the yellow lines)`
    + `${made ? ': the map has no cursor volumes of its own, and the Build gives it these' : ''}.`;
}
function snapTo(value, axis, fine, box = null) {
  const grid = volumeGrid();
  if (fine || !grid) return Math.round(value / 8) * 8;
  if (axis === 2 && box) {
    // a cursor floor's start near by wins over the level (a map's may be off the levels: the Bar's second is at 210)
    const near = storeysOver(storeysNow(), box).map(s => s.z).sort((a, b) => Math.abs(a - value) - Math.abs(b - value))[0];
    if (near != null && Math.abs(near - value) <= CURSOR_NEAR) return near;
  }
  return grid.origin[axis] + Math.round((value - grid.origin[axis]) / grid.size[axis]) * grid.size[axis];
}
function volumeHint(message) {
  const hint = $('dragHint');
  clearTimeout(hintTimer);
  hint.hidden = false; hint.replaceChildren(`${message} · `);
  text(hint, 'kbd', 'Esc'); hint.append(' cancels');
}
const tilesOf = box => { const g = volumeGrid(), s = g?.size ?? [96, 96, 64]; return [(box[3] - box[0]) / s[0], (box[4] - box[1]) / s[1]].map(v => Number(v.toFixed(2)) + 0); };
// ---- the pointer in the view while it is on: a face handle stretches, the New box tool draws a footprint
function startVolumeDrag(e) {
  // a picked no-spawn volume's face handle (the Spawns view, or the Normal button's spawn switch): stretches its box
  const sv = !volumesOn && e.button === 0 && !volumeDrag && !gizmo.controls.dragging ? spawnVolumeHandle() : null, sk = sv && volumeHandleNear(e.clientX, e.clientY);
  if (sk) {
    const before = spawnBoxNow(sv), [, axis] = FACES.find(f => f[0] === sk);
    volumeDrag = { kind: 'spawn', key: sk, entry: sv.key, stream: sv.stream, actor: sv.record.actor, before, box: before, pointerId: e.pointerId,
                   from: alongAxis(e.clientX, e.clientY, facePoint(before, sk), axis) };
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  if (!volumesOn || placing || e.button !== 0 || volumeDrag || gizmo.controls.dragging) return false;
  const key = volumeHandleNear(e.clientX, e.clientY);
  if (key) {
    const root = handleVolume(), before = volumeBox(root), [, axis] = FACES.find(f => f[0] === key);
    // the handle stands off its face: the drag moves the face by as much as the pointer moves along the axis
    volumeDrag = { kind: 'face', root, key, before, pointerId: e.pointerId, from: alongAxis(e.clientX, e.clientY, facePoint(before, key), axis) };
    paintVolume(root);
  } else if (gizmo.busy()) return false;
  else if (volumeTool === 'new') {
    const grid = volumeGrid(), hit = pick(e.clientX, e.clientY)?.point;
    if (!grid) return false;
    // the level under the cursor: what is drawn there, to the nearest level; else the grid's lowest
    const level = hit ? grid.origin[2] + Math.round((hit.y - grid.origin[2]) / grid.size[2]) * grid.size[2] : grid.origin[2];
    // with a floor chosen in the Floor buttons, that floor's height in the building there
    const storey = hit ? chosenStorey(hit.x, hit.z) : null, z0 = builderMode ? (storey ? storey.z : level) : Math.max(grid.origin[2], storey ? storey.z : level);
    const at = rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -z0), new THREE.Vector3());
    if (!at) return false;
    const tile = [0, 1].map(k => { const n = Math.floor(((k ? at.z : at.x) - grid.origin[k]) / grid.size[k]); return builderMode ? n : Math.max(0, Math.min(grid.dimensions[k] - 1, n)); });
    const building = buildingForNew() ?? newBuilding();
    const root = makeVolume(tileBox(grid, tile, tile, z0), building, floorFor(building, z0));
    volumeDrag = { kind: 'new', root, grid, tile, z0, building, pointerId: e.pointerId };
    refreshVolumes();
  } else return false;
  showPop(null);
  renderer.domElement.setPointerCapture(e.pointerId);
  renderer.domElement.style.cursor = 'grabbing';
  return true;
}
const tileBox = (grid, a, b, z0) => [grid.origin[0] + Math.min(a[0], b[0]) * grid.size[0], grid.origin[1] + Math.min(a[1], b[1]) * grid.size[1], z0,
                                    grid.origin[0] + (Math.max(a[0], b[0]) + 1) * grid.size[0], grid.origin[1] + (Math.max(a[1], b[1]) + 1) * grid.size[1],
                                    grid.unbounded ? z0 + STOREY_HEIGHT : Math.min(z0 + STOREY_HEIGHT, Math.max(z0 + grid.size[2], grid.origin[2] + grid.dimensions[2] * grid.size[2]))];
function moveVolumeDrag(e) {
  const d = volumeDrag;
  if (d.kind === 'spawn') {
    // a no-spawn volume's side to the tile lines and levels (Alt: steps of 8), at least a quarter tile from the other;
    // drawn live (missionDragView), one undo step at the release
    const [, axis, side] = FACES.find(f => f[0] === d.key);
    const at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
    if (at == null || d.from == null) return;
    const least = axis === 2 ? 16 : 24, box = [...d.before];
    let value = snapTo((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from, axis, e.altKey);
    if (side < 0) { value = Math.min(value, d.before[axis + 3] - least); box[axis] = value; }
    else { value = Math.max(value, d.before[axis] + least); box[axis + 3] = value; }
    if (box.every((v, k) => v === d.box[k])) return;
    d.box = box;
    missionDragView = d.stream === 'copy' ? editedCopies(d.actor, { box }) : editedSpawns(d.actor, { box });
    refreshSpawnMarkers();
    volumeHint(`${FACE_WORDS[d.key]} at ${Math.round(value)}: ${boxWords(box)}`);
    return;
  }
  if (d.kind === 'face') {
    const [, axis, side] = FACES.find(f => f[0] === d.key);
    const at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
    if (at == null || d.from == null) return;
    const least = axis === 2 ? 16 : 24, box = [...d.before];
    let value = snapTo((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from, axis, e.altKey, d.before);
    if (side < 0) { value = Math.min(value, d.before[axis + 3] - least); box[axis] = value; }
    else { value = Math.max(value, d.before[axis] + least); box[axis + 3] = value; }
    setVolumeBox(d.root, box);
    const [tx, ty] = tilesOf(box);
    volumeHint(`${FACE_WORDS[d.key]} at ${Math.round(value)}: ${tx} by ${ty} tiles, ${Math.round(box[5] - box[2])} high`);
    volumePanel();
  } else {
    const at = rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -d.z0), new THREE.Vector3());
    if (!at) return;
    const tile = [0, 1].map(k => { const n = Math.floor(((k ? at.z : at.x) - d.grid.origin[k]) / d.grid.size[k]); return builderMode ? n : Math.max(0, Math.min(d.grid.dimensions[k] - 1, n)); });
    const box = tileBox(d.grid, d.tile, tile, d.z0);
    setVolumeBox(d.root, box);
    const [tx, ty] = tilesOf(box);
    volumeHint(`New box: ${tx} by ${ty} tiles at height ${Math.round(d.z0)}`);
  }
}
function endVolumeDrag(keep) {
  const d = volumeDrag;
  if (!d) return false;
  volumeDrag = null;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
  renderer.domElement.style.cursor = volumeTool ? 'crosshair' : '';
  if (d.kind === 'spawn') {
    missionDragView = null;
    const changed = d.box.some((v, k) => Math.abs(v - d.before[k]) > 1e-6), hint = `No-spawn volume ${boxWords(d.box)}`;
    if (!(keep && changed && (d.stream === 'copy' ? editSpawnCopy(d.actor, { box: d.box }, hint) : editBaseSpawn(d.actor, { box: d.box }, hint)))) {
      refreshSpawnMarkers(); restingHint();
    }
    return true;
  }
  if (d.kind === 'face') {
    const after = volumeBox(d.root);
    setVolumeBox(d.root, d.before);
    if (keep && after.some((v, k) => Math.abs(v - d.before[k]) > 1e-6)) recordVolumes([d.root], () => setVolumeBox(d.root, after));
  } else {
    const box = volumeBox(d.root), floor = d.root.userData.volume.floor;
    // the preview goes; the box is made as one undo step
    for (const child of d.root.children) child.geometry.dispose();
    volumeLayer.remove(d.root); volumeRoots.delete(d.root.userData.source.id);
    if (keep) { addVolumes([{ box, floor }], d.building); setVolumeTool(null); }
    else if (!liveVolumes().some(r => r.userData.volume.building === d.building)) buildingMeta.delete(d.building);
  }
  restingHint(); editChanged();
  return true;
}
// ---- a cover block's or invisible floor's handles (private/plans/done/cover-block-handles-plan.md, decisions 2 and 3):
// with one selected, a white handle off each face along the piece's own axes (four sides, and a block's top and
// bottom), drawn and picked as a building box's are. A drag moves that face by the snap setting's steps
// (cover.js resizedCover): a low side's drag moves the corner too, so the opposite side stays; Esc puts it back, and
// the drag is one undo step.
const COVER_FACE_WORDS = { '-x': 'Side −X', '+x': 'Side +X', '-y': 'Side −Y', '+y': 'Side +Y', '-z': 'Bottom', '+z': 'Top' };
const SNAP_STEPS = { off: 'steps of 1 unit', fine: 'steps of 24', tile: 'whole tiles' };
const coverHandleLayer = new THREE.Group(); world.add(coverHandleLayer);
const coverHandles = new Map(Object.keys(COVER_FACE_WORDS).map(key => {
  const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
  mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material; coverHandleLayer.add(mesh);
  return [key, mesh];
}));
const coverStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(36), 3)),
                                          new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
coverStems.renderOrder = 8; coverStems.raycast = () => {}; coverStems.frustumCulled = false; coverHandleLayer.add(coverStems);
let coverDrag = null, coverHover = null;
// The cover piece the handles are on: the one piece picked, shown, in the Normal view, nothing being placed.
function handleCover() {
  const root = roots.get(selected);
  if (!root?.userData.source.cover || root.userData.deleted || !root.visible || placing || volumesOn || lightsOn || zonesOn
      || gizmo.picks().ids.length !== 1) return null;
  return root;
}
// Its faces now, in the view: each { face: [key, axis, side], at (the face's middle), dir (out along the axis), centre,
// half (the box's half size along it) }.
function coverFacesNow(root) {
  const c = root.userData.source.cover, [lo, hi] = coverBox(c, coverRecipe());
  root.updateMatrixWorld(true);
  const toView = ([x, y, z]) => new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
  const middle = [0, 1, 2].map(k => (lo[k] + hi[k]) / 2), centre = toView(middle);
  return coverFaces(c).map(face => {
    const [, axis, side] = face, p = [...middle];
    p[axis] = side < 0 ? lo[axis] : hi[axis];
    const at = toView(p), out = [...p];
    out[axis] += side;
    return { face, at, dir: toView(out).sub(at).normalize(), centre, half: (hi[axis] - lo[axis]) / 2 };
  });
}
// Where a handle is drawn: out from its face, clear of the gizmo's arrows (as a building box's, handlePoint).
function coverHandlePoint(f) {
  const d = camera.position.distanceTo(f.centre);
  return f.centre.clone().addScaledVector(f.dir, Math.max(f.half + d * 0.035, d * 0.2));
}
function updateCoverHandles() {
  const root = coverDrag?.root ?? handleCover();
  coverHandleLayer.visible = Boolean(root) && !gizmo.controls.dragging;
  if (!coverHandleLayer.visible) { if (coverHover) hoverCoverHandle(null); return; }
  const faces = new Map(coverFacesNow(root).map(f => [f.face[0], f])), lit = coverDrag?.face[0] ?? coverHover;
  const stems = coverStems.geometry.attributes.position;
  let n = 0;
  for (const [key, mesh] of coverHandles) {
    const f = faces.get(key);
    mesh.visible = Boolean(f);
    if (!f) continue;
    mesh.position.copy(coverHandlePoint(f));
    mesh.userData.material.color.setHex(key === lit ? 0xffe27a : 0xffffff);
    scaleMarker(mesh, camera, mesh.position);
    stems.setXYZ(n++, f.at.x, f.at.y, f.at.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z);
  }
  for (; n < 12; n++) stems.setXYZ(n, 0, 0, 0);
  stems.needsUpdate = true;
}
function coverHandleNear(x, y) {
  const root = handleCover();
  if (!root || gizmo.controls.dragging) return null;
  const project = projector();
  return coverFacesNow(root).map(f => { const s = project(coverHandlePoint(f)); return s && { f, d: Math.hypot(s[0] - x, s[1] - y) }; })
    .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.f ?? null;
}
function hoverCoverHandle(f) {
  const key = f?.face?.[0] ?? f ?? null;
  if (key === coverHover) return;
  coverHover = key;
  renderer.domElement.style.cursor = key ? 'grab' : '';
  renderer.domElement.title = key ? `${COVER_FACE_WORDS[key]}: drag to size it (${SNAP_STEPS[snapMode]}, as the snap setting)` : '';
}
function startCoverDrag(e) {
  if (e.button !== 0 || coverDrag || volumeDrag || gizmo.controls.dragging) return false;
  const f = coverHandleNear(e.clientX, e.clientY);
  if (!f) return false;
  const root = handleCover(), from = alongLine(e.clientX, e.clientY, f.at, f.dir);
  if (from == null) return false;
  coverDrag = { root, face: f.face, at: f.at, dir: f.dir, from, pointerId: e.pointerId,
                before: { cover: { ...root.userData.source.cover }, matrix: root.matrix.clone() }, after: null };
  showPop(null);
  renderer.domElement.setPointerCapture(e.pointerId);
  renderer.domElement.style.cursor = 'grabbing';
  return true;
}
function moveCoverDrag(e) {
  const d = coverDrag, t = alongLine(e.clientX, e.clientY, d.at, d.dir);
  if (t == null) return;
  const { cover, shift } = resizedCover(d.before.cover, coverRecipe(), d.face, t - d.from, snapMode);
  // a low side moved: the corner moves along the piece's own axis (dir points out of that side, so back along it)
  const matrix = d.before.matrix.clone();
  if (shift) matrix.premultiply(new THREE.Matrix4().makeTranslation(...d.dir.clone().multiplyScalar(-shift).toArray()));
  d.after = { cover, matrix };
  applyCover(d.root, cover, matrix);
  coverPanel(d.root);
  const [h0, h1] = cover.heights ?? [];
  volumeHint(`${COVER_FACE_WORDS[d.face[0]]}: ${sizeWords(cover.size)}${cover.heights ? `, from ${Math.round(h0 * 100) / 100} to ${Math.round(h1 * 100) / 100}` : ''} (${SNAP_STEPS[snapMode]})`);
}
function endCoverDrag(keep) {
  const d = coverDrag;
  if (!d) return false;
  coverDrag = null;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
  renderer.domElement.style.cursor = '';
  if (keep && d.after) setCover(d.root, d.after.cover, d.after.matrix, d.before);
  else { applyCover(d.root, d.before.cover, d.before.matrix); coverPanel(d.root); }
  restingHint(); editChanged();
  return true;
}
// ---- made walls (custom geometry plan, stage M1; walls.js is the pure part). A look's entry in the Add panel draws a
// wall: press on the ground at one end, drag along a tile line, release (Shift keeps drawing, Esc stops). The wall is
// an added copy of the look's donor (a fracturing wall of the game's, this map's own or brought from its map) that
// carries the numbers the Build makes its mesh from. A picked made wall has white handles at its ends (whole tiles)
// and blue ones on each opening (its middle slides it, its sides, its top, a window's sill; sides in whole tiles, with
// Alt in steps of 8); the piece panel's Wall section adds, lists and removes openings, flips it and reshuffles its
// break pattern. Each change is one undo step; the view draws the wall as the Build makes it (generated.py), the last
// drawing kept until the next arrives.
const isMadeWall = o => o?.added?.generated?.kind === 'fracWall';
const madeWallRoot = id => { const r = roots.get(id); return r && isMadeWall(r.userData.source) ? r : null; };
const wallLookOf = o => WALL_LOOKS.find(l => short(o.added?.from?.actor ?? '') === l.actor && (o.added?.from?.package ?? '').toLowerCase() === l.package.toLowerCase()) ?? null;
// The look's donor as a template: this map's own piece, or the piece read from its home map (libraryTemplate).
async function wallTemplate(look) {
  const actor = `TheWorld.PersistentLevel.${look.actor}`;
  if (data.name?.toLowerCase() === look.package.toLowerCase()) {
    const parts = partsOf(targetKey({ package: data.name, level: 'base', actor }));
    if (!parts.length) throw Error(`${look.actor} is not in this export of the map`);
    return parts[0];
  }
  const t = await libraryTemplate({ package: look.package, actor });
  return t.sources.find(s => short(s.actor) === look.actor) ?? t.sources[t.pivotIndex];
}
// The Add panel's Walls kind: one entry for each look, a recipe in both scopes.
const WALLS_KIND = 'Walls';
function wallEntries() {
  if (!data || data.preview || builderMode) return [];
  return WALL_LOOKS.map(look => ({ key: `wall:${look.id}`, id: `wall-${look.id}`, name: look.name, mesh: look.name, kind: WALLS_KIND,
    pkg: `from ${look.package}`, role: 'interior', sources: [], pivotIndex: 0, count: 0, materials: [], milestone: 1,
    wallLook: look, size: [96, 24, WALL.top - WALL.bottom], detail: 'Drawn by dragging; any length, doorways and windows',
    text: `wall walls ${look.name} ${look.package} ${look.words} fracturing breaks doorway window`.toLowerCase(),
    title: `${look.name}: ${look.words}. Press on the ground at one end, drag along a tile line and let go: the wall runs from tile `
      + `edge to tile edge, up to ${WALL.maxTiles} tiles. It breaks as the game's walls do (it is made like ${look.package}'s own). `
      + 'Add doorways and windows in the piece panel; its handles lengthen it and move them. The Build makes it on any install'
      + `${look.lwrOnly ? ' of Long War Rebalance' : ', plain Enemy Within included'}` }));
}
let wallDrawing = null;    // { look, template (once read), start, floor, pointerId, last }
const wallGhostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.4, depthWrite: false });
const wallGhost = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), wallGhostMaterial);
wallGhost.visible = false; wallGhost.matrixAutoUpdate = false; wallGhost.raycast = () => {}; wallGhost.renderOrder = 7; world.add(wallGhost);
async function startWallDrawing(look) {
  stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopWallDrawing();
  const drawing = wallDrawing = { look, template: null, start: null };
  renderer.domElement.style.cursor = 'crosshair';
  pieces.setChosen(wallEntries().find(e => e.wallLook === look) ?? null);
  const done = busyStart(`Reading ${look.name}…`);
  try {
    const template = await wallTemplate(look);
    if (wallDrawing !== drawing) return;
    drawing.template = template;
    askLineCollision();
    wallHint();
  } catch (error) {
    if (wallDrawing === drawing) { stopWallDrawing(); flashHint(`${look.name} can't be drawn: ${error.message}`); }
  } finally { done(); }
}
function wallHint(words = null) {
  clearTimeout(hintTimer);
  const hint = $('dragHint');
  hint.hidden = false;
  hint.replaceChildren(words ?? `Drawing a ${wallDrawing.look.name}: press on the ground at one end, drag along a tile line, let go · Shift keeps drawing · `);
  text(hint, 'kbd', 'Esc'); hint.append(' stops');
}
function stopWallDrawing() {
  if (!wallDrawing) return;
  if (wallDrawing.pointerId != null) try { renderer.domElement.releasePointerCapture(wallDrawing.pointerId); } catch { /* released */ }
  wallDrawing = null; wallGhost.visible = false; renderer.domElement.style.cursor = '';
  pieces.setChosen(null); library.setChosen(null); restingHint();
}
// The point of the ground (or a piece) under the pointer, in game units; and the floor under it.
function wallGround(clientX, clientY) {
  const hit = pick(clientX, clientY)?.point
    ?? rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundHeight()), new THREE.Vector3());
  return hit ? [hit.x, hit.z, hit.y] : null;
}
function drawnNow(d, at) {
  return drawnWall(d.start.slice(0, 2), at.slice(0, 2), { origin: gridOrigin() ?? [0, 0], template: d.template, floor: d.floor, seed: d.seed });
}
// The ghost: the wall's solid at the pose drawn (its box in the donor mesh's frame, at the copy's place).
function showWallGhost(template, w) {
  const a = WALL.endInset, b = w.wall.x1 - WALL.endInset;
  wallGhost.matrix.copy(movedMatrix(template, w.location, w.rotation))
    .multiply(new THREE.Matrix4().makeTranslation((a + b) / 2, (WALL.top + WALL.bottom) / 2, 0))
    .multiply(new THREE.Matrix4().makeScale(b - a, WALL.top - WALL.bottom, 2 * WALL.half));
  wallGhost.matrixWorldNeedsUpdate = true; wallGhost.visible = true;
}
function startWallDraw(e) {
  const d = wallDrawing;
  if (!d?.template || e.button !== 0 || d.start) return false;
  const at = wallGround(e.clientX, e.clientY);
  if (!at) return false;
  d.start = at; d.floor = groundAt(at[0], at[1], at[2] + 8) ?? at[2]; d.pointerId = e.pointerId;
  d.seed = 1 + Math.floor(Math.random() * 999999);
  d.last = drawnNow(d, at);
  renderer.domElement.setPointerCapture(e.pointerId);
  showWallGhost(d.template, d.last);
  wallHint(`${plural(d.last.tiles, 'tile')} · let go to make it · `);
  return true;
}
function moveWallDraw(e) {
  const d = wallDrawing, at = wallGround(e.clientX, e.clientY);
  if (!at) return;
  // the far end along the line the drag runs on, at the start's floor (a point on a piece behind is taken at its
  // place on the ground plane through the start)
  const ray = rayAt(e.clientX, e.clientY).ray, plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -d.start[2]);
  const flat = ray.intersectPlane(plane, new THREE.Vector3());
  d.last = drawnNow(d, flat ? [flat.x, flat.z, flat.y] : at);
  showWallGhost(d.template, d.last);
  wallHint(`${plural(d.last.tiles, 'tile')}${d.last.tiles === WALL.maxTiles ? ' (the longest)' : ''} · let go to make it · `);
}
async function endWallDraw(keep) {
  const d = wallDrawing;
  if (!d?.start) return;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
  const made = d.last, template = d.template, look = d.look;
  d.start = null; d.pointerId = null; wallGhost.visible = false;
  if (!keep) stopWallDrawing(); else wallHint();
  const generated = { kind: 'fracWall', version: 1, wall: made.wall };
  const source = { ...template, added: { from: fromOf(template), generated } };
  await pasteSnapshot({ entries: [{ source, matrix: movedMatrix(template, made.location, made.rotation) }], pivotIndex: 0, name: look.name },
                      new THREE.Matrix4());
  flashHint(`Made a ${look.name}, ${plural(made.tiles, 'tile')} long · its white handles lengthen it; Add doorway and Add window are in the piece panel`);
}
// ---- the wall as it is now, and changing it
const wallState = root => ({ generated: structuredClone(root.userData.source.added.generated), ...actorPose(root.userData.source, root.matrix) });
// The mesh record for a made wall's numbers (as madeShape makes it), its key.
function madeWallMesh(o, wall) {
  const key = `made:fracwall:${JSON.stringify(madeWallNumbers(wall))}`;
  if (!data.meshes[key]) {
    const was = data.meshes[o.mesh];
    data.meshes[key] = { ...was, url: `/generated/fracwall.glb?${new URLSearchParams({ wall: key.slice('made:fracwall:'.length) })}`,
      bounds: madeBounds(wall) };
  }
  return key;
}
// A state put on the wall's piece: its numbers, its pose, its mesh drawn anew once loaded (no undo step).
async function applyWall(root, state) {
  const o = root.userData.source;
  o.added = { ...o.added, generated: structuredClone(state.generated) };
  const key = madeWallMesh(o, state.generated.wall);
  o.mesh = key;
  gizmo.applyMatrices([root], [movedMatrix(o, state.location, state.rotation)]);
  root.updateMatrixWorld(true);
  const token = root.userData.wallToken = (root.userData.wallToken ?? 0) + 1;
  track(geometryCache, key, () => gltfLoader.loadAsync(assetUrl(data.meshes[key].url)));
  let base;
  try { base = await geometryCache.get(key); } catch { geometryCache.delete(key); return; }
  if (root.userData.wallToken !== token) return;
  const old = root.userData.parts, materials = old.map(p => p.userData.baseMaterial);
  const fresh = base.scene.clone(true), parts = [];
  fresh.traverse(child => { if (child.isMesh) parts.push(child); });
  parts.forEach((part, i) => {
    part.material = materials[i] ?? materials[0];
    Object.assign(part.userData, { baseMaterial: part.material, objectId: o.id });
    part.castShadow = !part.material.transparent; part.receiveShadow = true;
  });
  root.clear();
  for (const child of [...fresh.children]) root.add(child);
  root.userData.parts = parts;
  const gone = new Set(old);
  pickables.splice(0, pickables.length, ...pickables.filter(p => !gone.has(p)), ...(roots.get(o.id) === root ? parts : []));
  root.updateMatrixWorld(true);
  sceneChanged();
  if (selected === o.id) { refreshHighlight(root); wallPanel(root); }
}
// One undo step from `before` to `after` (states), the piece picked again each way.
function setWall(root, after, before) {
  const id = root.userData.source.id;
  if (JSON.stringify(after) === JSON.stringify(before)) { applyWall(root, before); return; }
  gizmo.record({ redo: () => { applyWall(root, after); select(id, false, true); },
                 undo: () => { applyWall(root, before); select(id, false, true); } });
}
function changeWall(change) {
  const root = madeWallRoot(selected);
  if (!root) return;
  const before = wallState(root), after = change(before);
  if (after) setWall(root, after, before);
}
// ---- the handles
const wallHandleLayer = new THREE.Group(); world.add(wallHandleLayer);
const wallHandleMeshes = [];
const wallStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(18), 3)),
                                         new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
wallStems.renderOrder = 8; wallStems.raycast = () => {}; wallStems.frustumCulled = false; wallHandleLayer.add(wallStems);
let wallDrag = null, wallHover = null, wallFocus = null;   // wallFocus: { id, index }: the opening whose handle was last touched
const WALL_PART_WORDS = { middle: 'Opening: drag to slide it along the wall', x0: 'Opening\'s side', x1: 'Opening\'s side',
                          z1: 'Opening\'s top', z0: 'Window\'s sill' };
function handleWall() {
  const root = madeWallRoot(selected);
  if (!root || root.userData.deleted || !root.visible || placing || wallDrawing || volumesOn || lightsOn || zonesOn || effectsOn || spawnsOn
      || gizmo.picks().ids.length !== 1 || !toolWall(root.userData.source.added.generated.wall)) return null;
  return root;
}
// The handles of the wall now: each { key, kind ('end' | 'opening'), part, index, at (on the wall), dir (the drag's
// axis, out of an end), out (whether it stands off the wall, out from `at`) } in the view.
function wallHandlesNow(root) {
  const w = root.userData.source.added.generated.wall;
  root.updateMatrixWorld(true);
  const toView = (x, y, z) => new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
  const axis = (x, y, z) => toView(x, y, z).sub(toView(0, 0, 0)).normalize();
  // the openings' handles on the face toward the camera
  const toCamera = camera.position.clone().sub(toView(w.x1 / 2, 0, 184));
  const side = toCamera.dot(axis(0, 1, 0)) >= 0 ? WALL.half + 1 : -WALL.half - 1;
  const mid = (wallTop(w) + WALL.bottom) / 2, out = [];
  out.push({ key: 'end:x0', kind: 'end', part: 'x0', at: toView(0, 0, mid), dir: axis(-1, 0, 0) });
  out.push({ key: 'end:x1', kind: 'end', part: 'x1', at: toView(w.x1, 0, mid), dir: axis(1, 0, 0) });
  // the top: up or down a storey (M2)
  out.push({ key: 'end:top', kind: 'end', part: 'top', at: toView(w.x1 / 2, 0, wallTop(w)), dir: axis(0, 0, 1) });
  sortedOpenings(w.openings ?? []).forEach((o, index) => {
    const cx = (o.x0 + o.x1) / 2, bottom = Math.max(0, o.z0), cz = (bottom + o.z1) / 2;
    const at = { middle: [cx, cz], x0: [o.x0, cz], x1: [o.x1, cz], z1: [cx, o.z1], z0: [cx, o.z0] };
    for (const part of openingParts(o))
      out.push({ key: `open:${index}:${part}`, kind: 'opening', part, index, at: toView(at[part][0], side, at[part][1]),
                 dir: part === 'z0' || part === 'z1' ? axis(0, 0, 1) : axis(1, 0, 0) });
  });
  return out;
}
const wallHandlePoint = h => (h.kind === 'end' ? h.at.clone().addScaledVector(h.dir, camera.position.distanceTo(h.at) * 0.06) : h.at);
function updateWallHandles() {
  const root = wallDrag?.root ?? handleWall();
  wallHandleLayer.visible = Boolean(root) && !gizmo.controls.dragging;
  if (!wallHandleLayer.visible) { if (wallHover) hoverWallHandle(null); return; }
  const handles = wallHandlesNow(root), lit = wallDrag?.key ?? wallHover;
  while (wallHandleMeshes.length < handles.length) {
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
    mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material;
    wallHandleLayer.add(mesh); wallHandleMeshes.push(mesh);
  }
  const stems = wallStems.geometry.attributes.position;
  let n = 0;
  wallHandleMeshes.forEach((mesh, i) => {
    const h = handles[i];
    mesh.visible = Boolean(h);
    if (!h) return;
    mesh.position.copy(wallHandlePoint(h));
    const focused = h.kind === 'opening' && wallFocus?.id === root.userData.source.id && wallFocus.index === h.index;
    mesh.userData.material.color.setHex(h.key === lit ? 0xffe27a : h.kind === 'end' ? 0xffffff : focused ? 0x9fdcff : 0x4aa8ff);
    scaleMarker(mesh, camera, mesh.position);
    if (h.kind === 'opening') mesh.scale.multiplyScalar(0.8);
    if (h.kind === 'end' && n < 6) { stems.setXYZ(n++, h.at.x, h.at.y, h.at.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z); }
  });
  for (; n < 6; n++) stems.setXYZ(n, 0, 0, 0);
  stems.needsUpdate = true;
}
function wallHandleNear(x, y) {
  const root = handleWall();
  if (!root || gizmo.controls.dragging) return null;
  const project = projector();
  return wallHandlesNow(root).map(h => { const s = project(wallHandlePoint(h)); return s && { h, d: Math.hypot(s[0] - x, s[1] - y) }; })
    .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.h ?? null;
}
function hoverWallHandle(h) {
  const key = h?.key ?? null;
  if (key === wallHover) return;
  wallHover = key;
  renderer.domElement.style.cursor = key ? 'grab' : wallDrawing ? 'crosshair' : '';
  renderer.domElement.title = !h ? '' : h.part === 'top' ? `The wall's top: drag ${storeysOf(handleWall()?.userData.source.added.generated.wall) === 1 ? 'up to make it two storeys' : 'down to make it one storey'}`
    : h.kind === 'end' ? 'The wall\'s end: drag to lengthen or shorten it by whole tiles'
    : `${WALL_PART_WORDS[h.part]}${h.part === 'x0' || h.part === 'x1' || h.part === 'middle' ? ' (whole tiles; Alt: steps of 8)' : ' (steps of 8)'}`;
}
function startWallDrag(e) {
  if (wallDrawing) return startWallDraw(e);
  if (e.button !== 0 || wallDrag || coverDrag || volumeDrag || gizmo.controls.dragging) return false;
  const h = wallHandleNear(e.clientX, e.clientY);
  if (!h) return false;
  const root = handleWall(), from = alongLine(e.clientX, e.clientY, h.at, h.dir);
  if (from == null) return false;
  wallDrag = { root, key: h.key, handle: h, from, pointerId: e.pointerId, before: wallState(root), after: null, shown: null };
  if (h.kind === 'opening') { wallFocus = { id: root.userData.source.id, index: h.index }; wallPanel(root); }
  showPop(null);
  renderer.domElement.setPointerCapture(e.pointerId);
  renderer.domElement.style.cursor = 'grabbing';
  return true;
}
function moveWallDrag(e) {
  const d = wallDrag, t = alongLine(e.clientX, e.clientY, d.handle.at, d.handle.dir);
  if (t == null) return;
  const delta = t - d.from, b = d.before, w = b.generated.wall, h = d.handle;
  let wall = w, location = b.location, words;
  if (h.part === 'top') {
    const r = raisedWall(w, delta);
    wall = r.wall;
    words = `${wallWords(wall)}${r.cut ? ` · ${plural(r.cut, 'opening')} brought under the top` : ''}${r.removed ? ` · ${plural(r.removed, 'opening')} in the upper storey will go` : ''}`;
  } else if (h.kind === 'end') {
    // (out of the start end is back along the wall)
    const r = resizedWall(w, h.part, h.part === 'x0' ? -delta : delta);
    wall = r.wall; location = shiftedLocation(b.location, b.rotation, r.shift);
    words = `${wallWords(wall)}${r.removed ? ` · ${plural(r.removed, 'opening')} past the end will go` : ''}`;
  } else {
    wall = movedOpening(w, h.index, h.part, delta, { fine: e.altKey });
    words = openingWords(sortedOpenings(wall.openings)[h.index]);
  }
  const key = JSON.stringify([wall, location]);
  if (key === d.shown) return;
  d.shown = key;
  d.after = { generated: { ...b.generated, wall }, location, rotation: b.rotation };
  applyWall(d.root, d.after);
  volumeHint(words);
}
function endWallDrag(keep) {
  const d = wallDrag;
  if (!d) return false;
  wallDrag = null;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
  renderer.domElement.style.cursor = '';
  if (keep && d.after) setWall(d.root, d.after, d.before);
  else applyWall(d.root, d.before);
  restingHint(); editChanged();
  return true;
}
// ---- the piece panel's Wall section
function wallPanel(root) {
  const o = root.userData.source, g = o.added.generated, w = g.wall, look = wallLookOf(o), tool = toolWall(w);
  $('wallHead').textContent = `Wall · ${look?.name ?? short(data.meshes[originalOf(o)?.mesh]?.name ?? 'made from numbers')}`;
  $('wallSize').textContent = tool ? `${wallWords(w)}. Its white handles lengthen or shorten it by whole tiles; the one on top makes it ${storeysOf(w) === 1 ? 'two storeys' : 'one storey'}.`
    : `${Math.round(w.x1 - w.x0)} long: numbers this tool doesn't draw (made elsewhere), so it has no handles here; the Build makes it as it is.`;
  const list = $('wallOpenings'), openings = sortedOpenings(w.openings ?? []);
  const doors = doorBoxes(root);
  list.replaceChildren(...openings.map((p, index) => {
    const row = document.createElement('div');
    row.className = 'wallopening';
    row.classList.toggle('on', wallFocus?.id === o.id && wallFocus.index === index);
    const play = openingPlay(w, p), door = openingKind(p) === 'doorway' && doors.some(b => boxesMeet(openingWorldBox(root, p), b, 8));
    const words = playWords(w, p, { door });
    const warn = !play.tiles || (openingKind(p) === 'doorway' ? !play.walk || !door : play.walk || play.cover === 'none' || !play.sight);
    row.append(Object.assign(document.createElement('strong'), { textContent: openingWords(p) }),
               Object.assign(document.createElement('small'), { textContent: words, className: warn ? 'warn' : '' }));
    const remove = Object.assign(document.createElement('button'), { type: 'button', textContent: 'Remove', title: 'Take this opening out of the wall' });
    remove.disabled = !tool;
    remove.onclick = () => { wallFocus = null; changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } })); };
    row.append(remove);
    row.onmouseenter = () => { wallFocus = { id: o.id, index }; };
    return row;
  }));
  const free = tool && withOpening(w, 'window');
  $('wallDoor').disabled = $('wallWindow').disabled = !free;
  $('wallFlip').disabled = $('wallShuffle').disabled = $('wallStoreys').disabled = !tool;
  $('wallStoreys').textContent = storeysOf(w) === 1 ? 'Two storeys' : 'One storey';
  $('wallStoreys').title = storeysOf(w) === 1 ? 'Make the wall two storeys tall (400)' : 'Make the wall one storey tall (208): openings in its upper storey go';
  $('wallNote').textContent = `Made from numbers on ${look ? `${look.package}'s` : 'its donor\'s'} materials: it breaks as the game's walls do, `
    + 'a fragment at a time. Doorways, windows and holes are walked, seen and shot through by the lines between tiles\' centres. '
    + 'A blast doesn\'t spread from it to the walls beside it, nor from them to it.';
}
// The boxes of the doors drawn now (copies, and the map's own where they stand), game units [x0, x1, y0, y1, z0, z1].
function doorBoxes(except) {
  const out = [];
  for (const r of roots.values()) {
    if (r === except || r.userData.deleted || !r.visible || r.userData.source.actorClass !== 'XComInteractiveLevelActor') continue;
    const b = boxOf(r);
    if (b) out.push(b);
  }
  return out;
}
function openingWorldBox(root, p) {
  root.updateMatrixWorld(true);
  const pts = [];
  for (const x of [p.x0, p.x1]) for (const y of [-WALL.half, WALL.half]) for (const z of [p.z0, p.z1]) {
    const v = new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
    pts.push([v.x, v.z, v.y]);
  }
  return [0, 1, 2].flatMap(k => [Math.min(...pts.map(q => q[k])), Math.max(...pts.map(q => q[k]))]);
}
// (as the compiler's overlaps_by: across at all, along and up by more than `least`)
function boxesMeet(a, b, least) {
  const along = a[1] - a[0] >= a[3] - a[2] ? 0 : 1, over = [0, 1, 2].map(k => Math.min(a[2 * k + 1], b[2 * k + 1]) - Math.max(a[2 * k], b[2 * k]));
  return over[along] > least && over[2] > least && over[1 - along] > 0;
}
$('wallDoor').onclick = () => addWallOpening('doorway');
$('wallWindow').onclick = () => addWallOpening('window');
function addWallOpening(kind) {
  const root = madeWallRoot(selected);
  if (!root) return;
  const r = withOpening(root.userData.source.added.generated.wall, kind);
  if (!r) { flashHint('Every tile of the wall has an opening'); return; }
  wallFocus = { id: root.userData.source.id, index: r.index };
  changeWall(s => ({ ...s, generated: { ...s.generated, wall: r.wall } }));
  flashHint(`Added a ${kind} · its blue handles move and size it`);
}
$('wallFlip').onclick = () => changeWall(s => {
  const f = flippedWall(s.generated.wall, s.location, s.rotation);
  return { generated: { ...s.generated, wall: f.wall }, location: f.location, rotation: f.rotation };
});
$('wallShuffle').onclick = () => changeWall(s => ({ ...s, generated: { ...s.generated, wall: reshuffled(s.generated.wall) } }));
$('wallStoreys').onclick = () => changeWall(s => ({ ...s, generated: { ...s.generated,
  wall: withStoreys(s.generated.wall, storeysOf(s.generated.wall) === 1 ? 2 : 1).wall } }));
// Delete with an opening's handle last touched takes that opening out (the wall stays): true when it did.
function deleteWallOpening() {
  const root = madeWallRoot(selected);
  if (!root || wallFocus?.id !== root.userData.source.id || !handleWall()) return false;
  const index = wallFocus.index;
  if (index >= (root.userData.source.added.generated.wall.openings ?? []).length) return false;
  wallFocus = null;
  changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } }));
  flashHint('Removed the opening · Ctrl+Z puts it back');
  return true;
}
function setVolumeTool(tool) {
  volumeTool = volumesOn ? tool : null;
  renderer.domElement.style.cursor = volumeTool ? 'crosshair' : '';
  $('volumeNew').classList.toggle('on', volumeTool === 'new');
  if (volumeTool === 'new') { clearTimeout(hintTimer); const hint = $('dragHint'); hint.hidden = false; hint.replaceChildren('New box: drag over the tiles it is to cover · '); text(hint, 'kbd', 'Esc'); hint.append(' cancels'); }
  else restingHint();
}
// A click in the view while it is on: the box under it, never a piece or a light.
function volumeClick(e) {
  if (volumeTool) return;
  const add = e.ctrlKey || e.shiftKey || e.metaKey;
  const hit = rayAt(e.clientX, e.clientY).intersectObjects([...[...volumeRoots.values()].filter(r => r.visible).map(r => r.userData.fill),
                                                            ...ownVolumeLayer.children.filter(c => c.userData.own)])[0];
  if (hit?.object.userData.volumeId) { ownPicked = null; select(hit.object.userData.volumeId, add); }
  // one of the map's own: shown in the panel, read only
  else if (hit) { if (selected) select(null); setOwnPicked(hit.object); }
  else if (!add) { if (selected) select(null); setOwnPicked(null); }
}
// ---- the panel: what the view is for and its tools, and the selected boxes' building and floor
const volumeUi = { root: $('volumePanel'), picked: $('volumePicked'), title: $('volumeTitle'), bottom: $('volumeBottom'), top: $('volumeTop'),
                   building: $('volumeBuilding'), name: $('volumeName'), kind: $('volumeKind'), floor: $('volumeFloor'), note: $('volumeNote'), warn: $('volumeWarn') };
let volumeCountKey = '', volumeCountText = '';
// How many pieces the boxes list, and of them how many cut down (worked out when nothing is being dragged).
function volumeCounts(targets) {
  const key = `${buildingsVersion}|${editedKey()}|${targets.map(r => r.userData.source.id).join()}`;
  if (key === volumeCountKey) return volumeCountText;
  const boxes = targets.map(r => { const b = volumeBox(r); return { boxes: [{ min: b.slice(0, 3), max: b.slice(3, 6) }] }; });
  let listed = 0, cut = 0;
  for (const root of roots.values()) {
    const o = root.userData.source;
    if (root.userData.deleted || o.cover || o.hidden || !LISTED_CLASSES.has(o.actorClass)) continue;
    const rough = boxOf(root);
    if (!rough || !touchedFloors(rough, boxes).length) continue;
    listed++;
    if (o.cutout && projectListings(root).some(l => l.cutdownFloor)) cut++;
  }
  volumeCountKey = key;
  volumeCountText = `${plural(listed, 'piece')} of the map ${listed === 1 ? 'stands' : 'stand'} in ${targets.length === 1 ? 'it' : 'them'}${cut ? `, ${cut} cutting down` : ''}.`;
  return volumeCountText;
}
function volumePanel() {
  // in the normal view: only for a building selected there, without the view's own tools
  const shown = volumesOn || (volumeRoots.has(selected) && pickedVolumes().length > 0) || (Boolean(ownPicked) && !selected);
  volumeUi.root.hidden = !shown;
  if (!shown) return;
  for (const part of [$('volumeIntro'), $('volumeOwn'), $('volumeNew').parentElement]) part.style.display = volumesOn ? '' : 'none';
  $('volumeHead').replaceChildren(volumesOn ? 'Buildings view ' : 'Building ');
  text($('volumeHead'), 'span', volumesOn ? 'pieces are locked' : 'picked whole');
  const targets = pickedVolumes(), one = targets.length === 1 ? targets[0] : null, grid = volumeGrid();
  const live = liveVolumes().length, ownCount = (data?.buildings ?? []).filter(b => !mapEditable(b) && b.floors?.length).length;
  $('volumeIntro').textContent = live ? `${boxCount(live)} in ${plural(buildings.length, 'building')}. Click a box to select it; the gizmo moves it, the white dots stretch it.`
    : 'A building is boxes laid over its floors: the game hides the pieces in the upper boxes when a soldier is inside, and cuts the walls down. Draw one with New box.';
  $('volumeOwn').textContent = ownCount ? `${ownCount === 1 ? 'One building of the map stays' : `${ownCount} buildings of the map stay`} as the map has `
    + `${ownCount === 1 ? 'it' : 'them'}, in grey: a van's goes with its van${data.exporterVersion >= 21 ? '' : ' (this export predates editing the map\'s buildings: prepare the map again)'}. `
    + 'Click a grey box to read it.' : '';
  mapChangesList();
  $('volumeAround').hidden = !aroundIds.length;
  $('volumeAround').textContent = `Boxes around the ${aroundIds.length === 1 ? 'piece' : `${aroundIds.length} pieces`} selected`;
  const own = ownPicked?.userData.own, readOnly = !targets.length && Boolean(own);
  volumeUi.picked.hidden = !targets.length && !own;
  for (const input of [volumeUi.bottom, volumeUi.top, volumeUi.building, volumeUi.name, volumeUi.kind, volumeUi.floor]) input.disabled = readOnly;
  $('volumeCopy').hidden = $('volumeDelete').hidden = readOnly; volumeUi.kind.parentElement.hidden = readOnly;
  $('volumeRestore').hidden = true;
  $('volumePrefab').hidden = readOnly;      // floor boxes alone are saveable too
  volumeUi.name.parentElement.firstChild.textContent = readOnly ? 'Floor volume' : 'Name';
  if (readOnly) {
    // one of the map's own boxes: what the map saves of it
    const b = own.box, g = grid?.size ?? [96, 96, 64], t = k => Number(((b[k + 3] - b[k]) / g[k]).toFixed(2)) + 0;
    const floor = own.building.floors[own.floor], members = floor.members ?? [], cut = members.filter(m => m.cutdownFloor).length;
    volumeUi.title.textContent = `The map's box · ${t(0)} by ${t(1)} tiles, ${Math.round(b[5] - b[2])} high`;
    volumeUi.bottom.value = Math.round(b[2] * 100) / 100; volumeUi.top.value = Math.round(b[5] * 100) / 100;
    volumeUi.building.replaceChildren(Object.assign(document.createElement('option'), { value: '', textContent: short(own.building.name) }));
    volumeUi.floor.value = own.floor + 1; volumeUi.name.value = own.volume ? short(own.volume) : '';
    volumeUi.note.textContent = `Floor ${own.floor + 1} of ${own.building.floors.length} of the map's own ${short(own.building.name)}`
      + `${floor.boxes.length > 1 ? `, one of this floor's ${floor.boxes.length} boxes` : ''}. The map lists ${plural(members.length, 'piece')} on this floor`
      + `${cut ? `, ${cut} cutting down` : ''}. It is shown to be read: ${own.building.van ? 'a van\'s own building goes with its van' : 'this building stays as the map has it'}.`
      + `${volumesOn ? '' : ' Selected with its pieces and copied (Ctrl+C, Ctrl+V), the copy gets a building of your own with the same boxes; this one stays where it is.'}`
      + `${storeysNow() ? ` ${cursorLine(storeysOver(storeysNow(), b), false)}` : ''}`;
    volumeUi.warn.hidden = true;
    return;
  }
  if (!targets.length) return;
  const boxes = targets.map(volumeBox), same = get => { const values = new Set(targets.map(get)); return values.size === 1 ? [...values][0] : null; };
  const [tx, ty] = one ? tilesOf(boxes[0]) : [0, 0];
  volumeUi.title.textContent = one ? `Box · ${tx} by ${ty} tiles, ${Math.round(boxes[0][5] - boxes[0][2])} high` : `${targets.length} boxes`;
  const whole = !volumesOn;
  const active = document.activeElement, put = (input, value) => { if (active !== input) input.value = value ?? ''; };
  put(volumeUi.bottom, one ? Math.round(boxes[0][2] * 100) / 100 : ''); put(volumeUi.top, one ? Math.round(boxes[0][5] * 100) / 100 : '');
  volumeUi.bottom.disabled = volumeUi.top.disabled = !one || whole;
  volumeUi.building.disabled = volumeUi.floor.disabled = whole;
  const building = same(r => r.userData.volume.building), meta = building ? buildingMeta.get(building) : null;
  const options = [...buildingMeta].filter(([id]) => liveVolumes().some(r => r.userData.volume.building === id))
    .map(([id, m], i) => Object.assign(document.createElement('option'), { value: id, textContent: m.name || `Building ${i + 1}` }));
  if (!building) options.unshift(Object.assign(document.createElement('option'), { value: '', textContent: 'Several', disabled: true }));
  options.push(Object.assign(document.createElement('option'), { value: 'new', textContent: 'New building' }));
  if (active !== volumeUi.building) { volumeUi.building.replaceChildren(...options); volumeUi.building.value = building ?? ''; }
  put(volumeUi.name, meta?.name ?? ''); volumeUi.name.disabled = volumeUi.kind.disabled = !meta;
  if (active !== volumeUi.kind) volumeUi.kind.value = meta?.kind ?? 'building';
  const floor = same(r => r.userData.volume.floor);
  put(volumeUi.floor, floor == null ? '' : floor + 1);
  const dragging = gizmo.controls.dragging || volumeDrag;
  const notes = whole ? ['Here the building is picked whole, to move, turn, copy or delete with its pieces. Its boxes are stretched and set to floors in the Buildings view (Shift+B).'] : [];
  const counted = same(r => r.userData.volume.effective);
  if (floor != null && counted != null && counted !== floor) notes.push(`Counted as floor ${counted + 1}: its building has no box on a floor below.`);
  if (meta?.map) {
    // one of the map's own buildings: whether the project changed it, and its notched volumes
    const changed = mapEdits().changed.has(building);
    notes.push(`One of the map's own buildings (${short(meta.map.actor)}): ${changed ? 'changed, so the Build edits it in place' : 'as the map has it'}.`);
    $('volumeRestore').hidden = !changed;
    const plain = new Map(meta.map.floors.flatMap(f => f.volumes.map((v, n) => [short(v), f.plain?.[n] !== false])));
    const notched = targets.filter(r => r.userData.volume.origin && r.userData.volume.home === building && plain.get(r.userData.volume.origin) === false);
    if (notched.length) notes.push(`${one ? 'This box is' : `${plural(notched.length, 'box')} of these are`} a notched floor volume of the map's, drawn by its outer box: `
      + 'moved, it keeps its notches; stretched, the Build puts a plain box in its place, the notches filled.');
  }
  if (!dragging) notes.push(volumeCounts(targets));
  const storeys = storeysNow(), misses = [];
  if (storeys && one) notes.push(cursorLine(storeysOver(storeys, boxes[0]), storeys.some(s => s.made)));
  if (storeys && !dragging) for (const box of boxes) {
    const over = storeysOver(storeys, box);
    if (cursorMiss(box, over)) misses.push(`${one ? 'This box' : 'A box'} starts at ${Math.round(box[2])}, away from where the cursor's floors start here `
      + `(${over.map(s => Math.round(s.z)).join(', ')}): the mouse wheel would not stop at this storey. Start it within ${CURSOR_NEAR} units of one.`);
  }
  volumeUi.note.textContent = notes.join(' ');
  const problems = new Set();
  if (!dragging && grid) for (const b of buildings) {
    if (!targets.some(r => r.userData.volume.building === b.id)) continue;
    const authored = [...roots.values()].some(r => {
      if (r.userData.deleted || !r.userData.source.added) return false;
      projectListings(r);
      return r.userData.authoredFloors?.has(b.id);
    });
    const others = allBuildings().filter(x => x.project !== b && x.id !== PROJECT_BUILDING + b.id && !(buildingMeta.get(b.id)?.map && x.id === buildingMeta.get(b.id).map.id));
    for (const p of buildingProblems(b, grid, others, authored, (k, n) => freshBox(b, k, n))) problems.add(`${b.name || 'the building'}: ${p}`);
  }
  const said = [problems.size ? `This may behave oddly in the game (the Build builds it and warns): ${[...problems].join('; ')}.` : '', ...new Set(misses)].filter(Boolean);
  volumeUi.warn.hidden = !said.length;
  volumeUi.warn.textContent = said.join(' ');
}
function typedHeight(input, index) {
  const root = pickedVolumes().length === 1 ? pickedVolumes()[0] : null, value = Number(input.value);
  if (!root || input.value === '' || !Number.isFinite(value)) { volumePanel(); return; }
  const box = volumeBox(root);
  box[index] = value;
  if (box[5] - box[2] < 16) { flashHint('A box is at least 16 units high'); input.value = volumeBox(root)[index]; return; }
  recordVolumes([root], () => setVolumeBox(root, box));
}
// (a field lets go once its change is made, so the keys work in the view again)
volumeUi.bottom.onchange = () => { typedHeight(volumeUi.bottom, 2); volumeUi.bottom.blur(); };
volumeUi.top.onchange = () => { typedHeight(volumeUi.top, 5); volumeUi.top.blur(); };
volumeUi.building.onchange = () => {
  const targets = pickedVolumes(), value = volumeUi.building.value;
  if (!targets.length || !value) return;
  recordVolumes(targets, () => {
    const id = value === 'new' ? newBuilding() : value;
    for (const r of targets) r.userData.volume.building = id;
    lastBuilding = id;
  });
  volumeUi.building.blur();
};
const editMeta = change => {
  const id = pickedVolumes()[0]?.userData.volume.building;
  if (id && buildingMeta.has(id)) recordVolumes([], () => Object.assign(buildingMeta.get(id), change));
};
volumeUi.name.onchange = () => { editMeta({ name: volumeUi.name.value.trim().slice(0, 60) }); volumeUi.name.blur(); };
volumeUi.kind.onchange = () => { editMeta({ kind: volumeUi.kind.value }); volumeUi.kind.blur(); };
volumeUi.floor.onchange = () => {
  const targets = pickedVolumes(), n = Number(volumeUi.floor.value);
  if (!targets.length || !Number.isInteger(n) || n < 1 || n > BUILDING_FLOORS_MAX) { volumePanel(); return; }
  recordVolumes(targets, () => { for (const r of targets) r.userData.volume.floor = n - 1; });
  volumeUi.floor.blur();
};
// Restore the map's (map buildings plan, section 1): a changed or deleted building of the map back as the map has
// it, its boxes made again from the export and its record gone, as one undo step. (A deleted one has no box left to
// click: the Buildings view lists the changed and deleted ones, mapChangesList.)
function mapRestoreChange(ids) {
  const targets = liveVolumes().filter(r => ids.includes(r.userData.volume.building)), made = [];
  for (const id of ids) {
    const e = buildingMeta.get(id)?.map;
    if (e) mapFloors(e).forEach((f, k) => f.boxes.forEach((box, n) => { const r = makeVolume(box, id, k, f.volumes[n]); r.userData.deleted = true; made.push(r); }));
  }
  const before = ids.map(id => ({ ...buildingMeta.get(id) }));
  const after = before.map(m => ({ ...m, name: short(m.map.actor), kind: mapKind(m.map) }));
  const put = (gone, back, metas) => { for (const r of gone) r.userData.deleted = true; for (const r of back) r.userData.deleted = false;
                                       ids.forEach((id, k) => buildingMeta.set(id, { ...metas[k] })); };
  return { redo: () => put(targets, made, after), undo: () => put(made, targets, before), count: ids.length };
}
function restoreMapBuildings(ids) {
  ids = ids.filter(id => buildingMeta.get(id)?.map);
  if (!ids.length) return;
  const change = mapRestoreChange(ids), picks = gizmo.picks();
  gizmo.record({ redo: () => { change.redo(); gizmo.setSelection([]); },
                 undo: () => { change.undo(); gizmo.setSelection(picks.ids.filter(id => volumeRoots.get(id) ? !volumeRoots.get(id).userData.deleted : allRoots.has(id)), picks.active); } });
  flashHint(`${ids.length === 1 ? short(buildingMeta.get(ids[0]).map.actor) : plural(ids.length, 'building')} as the map has ${ids.length === 1 ? 'it' : 'them'} · Ctrl+Z undoes it`);
}
$('volumeRestore').onclick = () => { const b = pickedVolumes()[0]?.userData.volume.building; if (b) restoreMapBuildings([b]); };
// The Buildings view's list of the map's buildings the project changed or deleted, each with Restore.
let mapChangesKey = '';
function mapChangesList() {
  const edits = mapEdits(), list = $('volumeChanged');
  const ids = volumesOn ? [...edits.changed, ...edits.gone].sort() : [];
  const key = ids.map(id => `${id}:${edits.gone.has(id)}`).join();
  if (key === mapChangesKey) return;
  mapChangesKey = key;
  list.hidden = !ids.length;
  list.replaceChildren();
  if (!ids.length) return;
  text(list, 'div', 'The map\'s buildings this project changes:', 'lightnote');
  for (const id of ids) {
    const row = text(list, 'div', '', 'row');
    text(row, 'span', `${short(buildingMeta.get(id).map.actor)} · ${edits.gone.has(id) ? 'deleted' : 'changed'}`);
    const button = text(row, 'button', 'Restore the map\'s');
    button.type = 'button';
    button.title = 'Back as the map has it: its boxes made again, its name and kind the map\'s (Ctrl+Z undoes it)';
    button.onclick = () => restoreMapBuildings([id]);
  }
}
$('volumeNew').onclick = () => setVolumeTool(volumeTool === 'new' ? null : 'new');
$('volumeAround').onclick = volumesAround;
$('volumeCopy').onclick = () => (volumesOn ? copyVolumes() : copySelection());
$('volumeDelete').onclick = () => (volumesOn ? deleteVolumes() : deleteSelection());
// The Normal button's Floor boxes switch: the project's boxes drawn in the normal view. A click on a box's edge, or the select
// box, then takes its whole building with whatever else is picked; it moves by whole tiles and turns by quarter turns,
// is copied with its pieces as a new building, and deleted. Stretching a box and its floor stay the Buildings view's.
function setBoxesShown(on) {
  boxesShown = Boolean(on) && data?.scope === 'map' && !data.preview;
  syncLights(); volumePanel();
}
$('boxesToggle').onchange = e => { setBoxesShown(e.target.checked); e.target.blur(); };
// The box whose edge is under a screen point, in the normal view (a box's sides are see-through: the pieces inside
// are picked through them).
function pickBoxEdge(x, y) {
  if (!boxesShown || volumesOn || lightsOn) return null;
  const project = projector();
  let best = null;
  const near = (b, hit) => {
    const corner = ([i, j, k]) => project(viewPoint([b[i * 3], b[1 + j * 3], b[2 + k * 3]]));
    for (const [lo, hi] of BOX_EDGES) {
      const p = corner(lo), q = corner(hi);
      if (!p || !q) continue;
      const dx = q[0] - p[0], dy = q[1] - p[1], length = dx * dx + dy * dy;
      const t = length ? Math.max(0, Math.min(1, ((x - p[0]) * dx + (y - p[1]) * dy) / length)) : 0;
      const d = Math.hypot(p[0] + t * dx - x, p[1] + t * dy - y);
      if (d <= 6 && (!best || d < best.d)) best = { d, ...hit };
    }
  };
  // the project's boxes first: one of the map's is taken only where it is nearer
  for (const root of volumeRoots.values()) if (root.visible) near(volumeBox(root), { id: root.userData.source.id });
  for (const mesh of ownVolumeLayer.children) if (mesh.userData.own) near(mesh.userData.own.box, { own: mesh });
  return best;
}
const pickVolumeEdge = (x, y) => pickBoxEdge(x, y)?.id ?? null;
// One of the map's own buildings picked in the normal view: with Ctrl or Shift, added to what is selected (or taken
// out again); alone, shown to be read.
function pickOwn(mesh, add) {
  const building = mesh.userData.own.building;
  if (!add) select(null);
  if (add && ownSet.has(building)) ownSet.delete(building); else ownSet.add(building);
  ownPicked = ownSet.has(building) && !selected ? mesh : null;
  refreshVolumes(); volumePanel();
  if (ownSet.has(building)) flashHint(`${short(building.name)}, a building of the map: copied with its pieces, the copy gets a building of your own`);
}
$('volumeDone').onclick = () => setVolumesShown(false);
$('editBuildings').onclick = () => data && setVolumesShown(!volumesOn);
// Box select (the user, 11 November 2026: "a better way of selecting many items at once"): in the normal view a box
// is drawn over the ground (the tool strip's button, T), stretched by the six face handles a building's box has and
// moved by the dot in its middle. Select (Enter) takes every piece whose middle is inside, with its group and linked
// pieces whole as a click takes them; Shift+Enter adds them to the selection. Only what is drawn is taken (a floor
// hidden by the Floor buttons is not), and never a streamed patch's piece. The box is the tool's alone: it is not
// saved, and no undo step.
const PICK_SLACK = 4;      // a wall on the box's side counts as inside
const PICK_DROP = 32;      // the box starts this far under the level it is drawn on: the floor under a house comes too
const pickBoxLayer = new THREE.Group(); pickBoxLayer.visible = false; world.add(pickBoxLayer);
const pickBoxParts = (() => {
  const fill = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }));
  const line = new THREE.LineSegments(new THREE.EdgesGeometry(fill.geometry), new THREE.LineBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.95, depthWrite: false }));
  const through = new THREE.LineSegments(line.geometry, new THREE.LineBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.35, depthWrite: false, depthTest: false }));
  // what Select would take: each piece's box in white
  const hits = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.8, depthTest: false }));
  const moveMaterial = new THREE.MeshBasicMaterial({ color: 0x96e5d7, depthTest: false, transparent: true });
  const move = new THREE.Mesh(new THREE.SphereGeometry(0.7, 16, 12), moveMaterial);
  for (const part of [fill, line, through, hits, move]) { part.raycast = () => {}; part.renderOrder = 7; part.frustumCulled = false; pickBoxLayer.add(part); }
  move.renderOrder = 9;
  return { fill, line, through, hits, move, moveMaterial };
})();
// the twelve edges of a box, as pairs of corners (each a 0 or 1 for x, y and z)
const BOX_EDGES = [];
for (let axis = 0; axis < 3; axis++) for (let u = 0; u < 2; u++) for (let v = 0; v < 2; v++) {
  const lo = [0, 0, 0], hi = [0, 0, 0], [p, q] = [0, 1, 2].filter(k => k !== axis);
  lo[p] = hi[p] = u; lo[q] = hi[q] = v; hi[axis] = 1;
  BOX_EDGES.push([lo, hi]);
}
// The pieces Select can take, each with its drawn box and that box's middle (worked out once for a drag).
function pickCandidates() {
  if (!pickCentres) {
    pickCentres = [];
    for (const root of lightsOn || effectsOn ? [] : roots.values()) {
      const o = root.userData.source;
      if (root.userData.deleted || !root.visible || isStream(o)) continue;
      const b = boxOf(root);
      if (b) pickCentres.push({ id: o.id, box: b.slice(), at: [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2] });
    }
    // with the lights shown, the lights that can be edited; with View options' Floor boxes, the project's boxes
    if (lightsShown) for (const root of lightRoots.values()) {
      const o = root.userData.source, e = root.matrix.elements;
      if (!root.visible || root.userData.deleted || isStream(o) || lightViewOnly(o)) continue;
      pickCentres.push({ id: o.id, kind: 'light', at: [e[12], e[14], e[13]], box: [e[12] - 14, e[12] + 14, e[14] - 14, e[14] + 14, e[13] - 14, e[13] + 14] });
    }
    // with the markers drawn (the Effects view, where only they are taken, or the Normal button's switch), the
    // effects, sounds and flares the editor changes (effects and sounds plan, FX3b)
    if (effectsShown() && !lightsOn) for (const root of effectRoots.values()) {
      const o = root.userData.source, e = root.matrix.elements;
      if (!root.visible || root.userData.deleted || isStream(o)) continue;
      if (effectViewOnly(o, 'move') && effectViewOnly(o, 'copy') && effectViewOnly(o, 'delete')) continue;
      pickCentres.push({ id: o.id, kind: o.kind, at: [e[12], e[14], e[13]], box: [e[12] - 14, e[12] + 14, e[14] - 14, e[14] + 14, e[13] - 14, e[13] + 14] });
    }
    if (boxesShown && !lightsOn && !effectsOn) for (const root of volumeRoots.values()) {
      if (!root.visible) continue;
      const b = volumeBox(root);
      pickCentres.push({ id: root.userData.source.id, kind: 'box', at: [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], box: [b[0], b[3], b[1], b[4], b[2], b[5]] });
    }
    // and the map's own boxes: taken to be copied
    if (boxesShown && !lightsOn && !effectsOn) ownVolumeLayer.children.filter(c => c.userData.own).forEach((mesh, n) => {
      const b = mesh.userData.own.box;
      pickCentres.push({ id: `own:${n}`, kind: 'own', mesh, at: [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], box: [b[0], b[3], b[1], b[4], b[2], b[5]] });
    });
  }
  return pickCentres;
}
// The box and what it would take, drawn again; `recount` after anything that may have moved or hidden a piece.
function refreshPickBox(recount = false) {
  if (recount) pickCentres = null;
  const b = pickBox, parts = pickBoxParts, button = $('editBox');
  pickBoxLayer.visible = Boolean(b);
  $('boxBar').hidden = !b;
  button.classList.toggle('on', pickTool || Boolean(b)); button.setAttribute('aria-pressed', pickTool || Boolean(b));
  if (!pickDrag) kindButton();      // Select all of a kind narrows to a box drawn
  if (!b) { pickHits = []; return; }
  for (const part of [parts.fill, parts.line, parts.through]) {
    part.position.set((b[0] + b[3]) / 2, (b[2] + b[5]) / 2, (b[1] + b[4]) / 2);
    part.scale.set(Math.max(1, b[3] - b[0]), Math.max(1, b[5] - b[2]), Math.max(1, b[4] - b[1]));
  }
  pickHits = pickCandidates().filter(c => c.at.every((v, k) => v >= b[k] - PICK_SLACK && v <= b[k + 3] + PICK_SLACK));
  const points = new Float32Array(pickHits.length * 72);
  let n = 0;
  for (const { box } of pickHits) for (const edge of BOX_EDGES) for (const [i, j, k] of edge) {
    points[n++] = box[i]; points[n++] = box[4 + k]; points[n++] = box[2 + j];
  }
  parts.hits.geometry.dispose();
  parts.hits.geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(points, 3));
  $('boxBarText').textContent = pickHits.length ? `${pickWords()} inside` : lightsOn ? 'No light inside' : effectsOn ? 'No effect or sound inside' : 'No piece inside';
  $('boxTake').disabled = $('boxAdd').disabled = !pickHits.length;
}
// what the box holds, in words: pieces, lights and floor boxes
function pickWords() {
  const of = kind => pickHits.filter(c => c.kind === kind).length;
  const lights = of('light'), boxes = of('box') + of('own'), effects = of('effect'), sounds = of('sound'), flares = of('flare');
  const n = pickHits.length - lights - boxes - effects - sounds - flares;
  const parts = [n && plural(n, 'piece'), lights && plural(lights, 'light'), boxes && `${boxes} floor ${boxes === 1 ? 'box' : 'boxes'}`,
                 effects && plural(effects, 'effect'), sounds && plural(sounds, 'sound'), flares && plural(flares, 'lens flare')].filter(Boolean);
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0];
}
const pickMovePoint = () => [(pickBox[0] + pickBox[3]) / 2, (pickBox[1] + pickBox[4]) / 2, (pickBox[2] + pickBox[5]) / 2];
function pickMoveNear(x, y) {
  if (!pickBox || volumesOn || placing) return false;
  const s = projector()(viewPoint(pickMovePoint()));
  return Boolean(s) && Math.hypot(s[0] - x, s[1] - y) <= HANDLE_PICK + 4;
}
// where the pointer's ray meets the level at height z (a point of the view: x, the height, y)
const levelPoint = (e, z) => rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -z), new THREE.Vector3());
function setPickTool(on) {
  if (on && (!data || placing)) return;
  if (on && volumesOn) setVolumesShown(false);
  if (on && zonesOn) setZonesShown(false);     // box select takes pieces, which the Landing zones view doesn't
  // (the Effects view stays: there the box takes its markers only, as the Lights view's takes lights)
  pickTool = Boolean(on);
  if (!pickTool) { pickBox = null; pickDrag = null; }
  renderer.domElement.style.cursor = pickTool ? 'crosshair' : '';
  refreshPickBox(true); restingHint();
}
const stopPickBox = () => { if (pickTool || pickBox) setPickTool(false); };
function startPickDrag(e) {
  if (volumesOn || placing || e.button !== 0 || pickDrag || gizmo.controls.dragging || !(pickTool || pickBox)) return false;
  const key = pickBox ? volumeHandleNear(e.clientX, e.clientY) : null;
  if (key) {
    const [, axis] = FACES.find(f => f[0] === key);
    pickDrag = { kind: 'face', key, before: [...pickBox], pointerId: e.pointerId, from: alongAxis(e.clientX, e.clientY, facePoint(pickBox, key), axis) };
  } else if (pickMoveNear(e.clientX, e.clientY)) {
    const level = pickMovePoint()[2], at = levelPoint(e, level);
    if (!at) return false;
    pickDrag = { kind: 'move', before: [...pickBox], pointerId: e.pointerId, from: [at.x, at.z], level };
  } else if (gizmo.busy() || !pickTool) return false;
  else {
    // drawn on what is under the pointer (else the grid's lowest level), from a little under it up to the grid's top
    const grid = volumeGrid(), hit = pick(e.clientX, e.clientY)?.point;
    const work = builderMode ? builderBounds().map(([, box]) => box) : [];
    const level = Math.min(hit ? hit.y : grid ? grid.origin[2] : 0, ...work.map(b => b[2])), at = levelPoint(e, level);
    if (!at) return false;
    const top = Math.max(level + STOREY_HEIGHT, grid ? grid.origin[2] + grid.dimensions[2] * grid.size[2] : level + 4 * STOREY_HEIGHT, ...work.map(b => b[5]));
    pickDrag = { kind: 'new', before: pickBox, pointerId: e.pointerId, from: [at.x, at.z], level, top };
    pickBox = [at.x, at.z, level - PICK_DROP, at.x, at.z, top].map(Math.round);
  }
  showPop(null);
  renderer.domElement.setPointerCapture(e.pointerId);
  renderer.domElement.style.cursor = 'grabbing';
  refreshPickBox(true);
  return true;
}
function movePickDrag(e) {
  const d = pickDrag;
  if (d.kind === 'face') {
    const [, axis, side] = FACES.find(f => f[0] === d.key), at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
    if (at == null || d.from == null) return;
    const box = [...d.before], value = Math.round((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from);
    if (side < 0) box[axis] = Math.min(value, d.before[axis + 3] - 8); else box[axis + 3] = Math.max(value, d.before[axis] + 8);
    pickBox = box;
  } else {
    const at = levelPoint(e, d.level);
    if (!at) return;
    if (d.kind === 'move') {
      const dx = Math.round(at.x - d.from[0]), dy = Math.round(at.z - d.from[1]);
      pickBox = [d.before[0] + dx, d.before[1] + dy, d.before[2], d.before[3] + dx, d.before[4] + dy, d.before[5]];
    } else pickBox = [Math.min(d.from[0], at.x), Math.min(d.from[1], at.z), d.level - PICK_DROP, Math.max(d.from[0], at.x), Math.max(d.from[1], at.z), d.top].map(Math.round);
  }
  refreshPickBox();
  volumeHint(`Box select: ${pickHits.length ? `${pickWords()} inside` : effectsOn ? 'no effect or sound inside' : 'no piece inside'}`);
}
function endPickDrag(keep) {
  const d = pickDrag;
  if (!d) return false;
  pickDrag = null;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
  if (!keep) pickBox = d.before && [...d.before];
  else if (d.kind === 'new') {
    // a press without a drag draws nothing: the tool waits for one
    if (pickBox[3] - pickBox[0] < 8 || pickBox[4] - pickBox[1] < 8) pickBox = d.before && [...d.before];
    else pickTool = false;
  }
  renderer.domElement.style.cursor = pickTool ? 'crosshair' : '';
  refreshPickBox(true); restingHint();
  return true;
}
// Select: the pieces inside become the selection (`add`: join it), and the box goes.
function takePickBox(add = false) {
  if (!pickBox) return;
  refreshPickBox(true);
  const owns = pickHits.filter(c => c.kind === 'own'), ids = pickHits.filter(c => c.kind !== 'own').map(c => c.id), was = gizmo.picks();
  if (!ids.length && !owns.length) { flashHint(lightsOn ? 'No light is inside the box' : effectsOn ? 'No effect or sound is inside the box' : 'No piece has its middle inside the box'); return; }
  const before = add ? was.ids.filter(id => allRoots.get(id)) : [];
  stopPickBox();
  // a piece holds the pivot when there is one
  gizmo.setSelection([...new Set([...before, ...ids])], before.includes(was.active) ? was.active : ids.find(id => roots.has(id)) ?? ids[0]);
  if (!add) ownSet.clear();
  for (const c of owns) ownSet.add(c.mesh.userData.own.building);
  ownPicked = !gizmo.active && owns.length ? owns[0].mesh : null;
  select(gizmo.active, false, true);
  flashHint(`${[gizmo.selection().length && selectionWords(gizmo.selection()), ownSet.size && `${plural(ownSet.size, 'building')} of the map`].filter(Boolean).join(' and ')} selected`);
}
$('editBox').onclick = () => setPickTool(!(pickTool || pickBox));
$('boxTake').onclick = () => takePickBox(false);
$('boxAdd').onclick = () => takePickBox(true);
$('boxAgain').onclick = () => setPickTool(true);
$('boxCancel').onclick = stopPickBox;
$('playAreaToggle').onchange = e => { setPlayArea(e.target.checked); e.target.blur(); };
const WHOLE_OVERHANG = 4 * 96;    // four tiles
function cutaway() {
  touchShadows();
  cutKey = editedKey();
  // The floor cut applies to every building at once (the user's choice, 7 November: no building list).
  const requested = $('floor').value ?? 'all', chosen = 'all';
  const interior=$('scenery').value==='interior';
  const allFloors = $('floor').querySelector('[data-value=all]');
  if (allFloors) allFloors.title = interior ? 'All interior floors' : 'All floors · roof closed';
  const scenePlanes=interior ? interiorPlanes(data) : [];
  // Interior draws a piece that reaches into its area whole across the map (only the height cut stays), unless it
  // reaches more than WHOLE_OVERHANG past the area's sides: big ground and long walls stay cut there, so the outside
  // doesn't come back with them. (interiorPlanes: x min/max, then the height's two, then z min/max.)
  const focus=interior ? focusBounds(data) : null, heightPlanes=scenePlanes.slice(2, 4);
  const actors=new Map();
  const movedLanding = landingZones && !builderMode ? movedLandingActors() : null;
  for (const root of roots.values()) {
    const obj = root.userData.source;
    // a streamed package's pieces show with the chosen mission's streams
    const shownStream = !isStream(obj) || streamSet.has(obj.stream);
    const helper = (obj.layer === 'inherited' || isStream(obj)) && shownStream && obj.hidden && obj.hiddenBy == null && !$('hideHelpers').checked;
    root.visible = (!obj.hidden || helper) && !obj.environment && !root.userData.deleted && shownStream
      && !(cleared && isStream(obj) && data.streams?.[obj.stream]?.kind === 'lwr') && !(movedLanding?.has(obj.actor));
    // Pieces the user added always count as part of the playable scene, whatever their source's layer.
    root.userData.tacticalExcluded=interior && !obj.provenance && !obj.added && ['backdrop','roof','helper'].includes(obj.sceneryRole);
    root.visible &&= !root.userData.tacticalExcluded;
    let height = Infinity;
    if (requested !== 'all') {
      const idx = Number(requested)-1;
      const groups = new Map();
      for (const entry of listingsNow(root)) {
        if (chosen !== 'all' && entry.building !== chosen) continue;
        const old = groups.get(entry.building);
        // The game's floor pass runs top to bottom: the lowest cache entry wins.
        if (!old || entry.floor < old.floor) groups.set(entry.building,entry);
      }
      if (groups.size) {
        const entries = [...groups.values()];
        root.visible &&= entries.some(f => f.floor <= idx);
        for (const f of entries) {
          if (obj.cutout && f.floor <= idx && f.cutdownFloor > idx) {
            const building = allBuildings().find(b => b.id === f.building);
            const top = building?.floors[idx]?.top;
            if (top != null) height = Math.min(height,top);
          }
        }
      }
    }
    root.userData.cutHeight = height;
    let whole = false;
    if (focus && root.visible) {
      const box = new THREE.Box3().setFromObject(root);
      whole = !box.isEmpty() && box.intersectsBox(focus)
        && Math.max(focus.min.x - box.min.x, box.max.x - focus.max.x, focus.min.z - box.min.z, box.max.z - focus.max.z) <= WHOLE_OVERHANG;
    }
    root.userData.interiorWhole = whole;
    const planes=whole ? [...heightPlanes] : [...scenePlanes];
    if(Number.isFinite(height))planes.push(new THREE.Plane(new THREE.Vector3(0,-1,0),height));
    root.userData.clippingPlanes=planes;
    const actor=actors.get(obj.actor) || {visible:false,ceiling:-Infinity};
    actor.visible ||= root.visible;if(root.visible)actor.ceiling=Math.max(actor.ceiling,height);
    actors.set(obj.actor,actor);
    root.traverse(part => {
      if (!part.isMesh || !part.userData.baseMaterial) return;
      const base = part.userData.baseMaterial;
      if (helper) {part.material=helperMaterial;part.castShadow=false;}
      else if (planes.length) {
        const key = `${base.uuid}:${height}:${interior}:${whole}`;
        if (!cutMaterials.has(key)) {
          const mat = withLocalLights(base.clone());
          mat.clippingPlanes = planes;
          mat.clipShadows = true; cutMaterials.set(key,mat);
        }
        part.material = cutMaterials.get(key);
      } else part.material = base;
    });
  }
  // The tile grid follows the saved floors whose actors are shown: draw it again; and the Floor tiles overlay.
  floorActors=actors;tileKey=null;
  drawFloorTiles();
  if (selected) select(selected, false, true);
  const count=[...roots.values()].filter(r=>r.visible).length;
  $('status').textContent=`${count} visible pieces · ${data.counts.meshes} meshes · ${data.counts.textures} textures${loadErrorCount ? ` · ${loadErrorCount} display errors` : ''}`;
  if (pickBox && !pickDrag) refreshPickBox(true);
}
// The tile grid (first-editor plan, section 2): only the tiles around the selection, or around the piece being placed,
// with the tiles its bounds cover filled (view_layout.js tileGridAround). It is drawn again whenever what it follows
// moves or turns, or the cutaway changes.
let floorActors = null, tileKey = '';
function tileTargets() {
  if (!$('grid').checked || !data) return [];
  if (placing) return placing.ghost.visible ? [placing.ghost.children[1]] : [];
  return gizmo.selection().filter(root => root.visible && !root.userData.light && !root.userData.volume && !root.userData.effect);
}
function updateTileGrid() {
  const targets = tileTargets();
  // Children too: the footprint is read from each mesh's own world matrix.
  for (const t of targets) t.updateWorldMatrix(true, true);
  const key = targets.map(t => t.uuid + ':' + t.matrixWorld.elements.map(v => v.toFixed(2)).join(',')).join('|');
  if (key === tileKey) return;
  tileKey = key;
  for (const child of [...grid.children]) {
    grid.remove(child);
    child.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
  }
  const note = $('tileNote'), foot = targets.length ? footprintOf(targets, data) : null;
  note.hidden = !foot;
  if (!foot) return;
  const local = tileGridAround(foot, data, floorActors);
  grid.add(local);
  const { tiles, edges, level, gap, floating } = local.userData;
  note.textContent = `${plural(tiles.length, 'tile')}${edges.length ? ` + ${edges.length} at the edge` : ''} · level ${level}`
    + (floating ? ` · ${Math.round(gap)} above the floor: may give no cover` : '');
  note.classList.toggle('floating', floating);
}
// The Floor tiles overlay (View options; view_layout.js floorTilesOverlay): the map's saved floor tiles, coloured by the
// piece that carries each (one colour per kind of piece: copies of one piece share it), hatched grey where
// that piece was moved or deleted since. The tiles of pieces hidden or cut away in the view are left out. Hovering a
// tile names its piece; a click selects it. Drawn again with the cutaway.
let floorTileLayer = null, tileOwners = null, tipDirty = false;
function signatureColor(signature) {
  let h = 2166136261;
  for (let i = 0; i < signature.length; i++) { h ^= signature.charCodeAt(i); h = Math.imul(h, 16777619); }
  return new THREE.Color().setHSL(((h >>> 0) % 360) / 360, 0.62, 0.56).getHex();
}
function drawFloorTiles() {
  if (floorTileLayer) {
    world.remove(floorTileLayer);
    floorTileLayer.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
    floorTileLayer = null;
  }
  $('floorTip').hidden = true;
  if (!data || !$('floorTiles').checked) return;
  const owners = new Map();     // an original's actor -> { roots, sources, gone, color }
  for (const r of roots.values()) {
    const o = r.userData.source;
    if (o.added || o.layer !== 'base') continue;
    if (!owners.has(o.actor)) owners.set(o.actor, { roots: [], sources: [] });
    owners.get(o.actor).roots.push(r); owners.get(o.actor).sources.push(o);
  }
  for (const s of owners.values()) {
    s.gone = s.roots.some(r => r.userData.deleted || r.userData.edit);
    s.color = signatureColor(stampSignature(s.sources));
  }
  tileOwners = owners;
  floorTileLayer = floorTilesOverlay(data, {
    shown: f => { const s = owners.get(f.actor), a = floorActors?.get(f.actor);
      if (cleared && s?.gone) return false;     // a cleared map: the gone pieces' tiles are left out, not hatched
      return !s || s.gone || !a || (a.visible && f.location[2] <= a.ceiling + 1); },
    colorOf: a => owners.get(a)?.color ?? 0x82d5ce, gone: a => Boolean(owners.get(a)?.gone) });
  world.add(floorTileLayer);
}
function floorTileHit(clientX, clientY) {
  const mesh = floorTileLayer?.getObjectByName('floorTiles');
  const hit = mesh && rayAt(clientX, clientY).intersectObject(mesh)[0];
  return hit ? { tile: floorTileLayer.userData.tiles[Math.floor(hit.faceIndex / 2)], distance: hit.distance } : null;
}
function floorTip() {
  tipDirty = false;
  const tip = $('floorTip'), hit = pointer && !gizmo.controls.dragging ? floorTileHit(...pointer) : null;
  tip.hidden = !hit;
  if (!hit) return;
  const f = hit.tile, s = tileOwners?.get(f.actor), mesh = s ? data.meshes[s.sources[0].mesh]?.name : null;
  tip.replaceChildren();
  text(tip, 'strong', short(mesh ?? f.actor));
  text(tip, 'small', `${short(f.actor)} · tile ${f.tile[0]}, ${f.tile[1]} · level ${f.tile[2]}`);
  if (s?.gone) text(tip, 'small', s.roots.some(r => r.userData.deleted) ? 'deleted since: the Build\'s rebuild checks this tile again'
                                                                          : 'moved since: the Build\'s rebuild checks this tile again');
  const rect = viewport.getBoundingClientRect();
  tip.style.left = `${pointer[0] - rect.left}px`; tip.style.top = `${pointer[1] - rect.top}px`;
}
// A click on a saved floor tile selects its piece, unless another piece stands nearer in front of it.
function floorTileSelect(e, hit) {
  const tile = floorTileLayer && floorTileHit(e.clientX, e.clientY);
  if (!tile || (hit && hit.distance < tile.distance - 1)) return false;
  const s = tileOwners?.get(tile.tile.actor), live = s?.roots.filter(r => !r.userData.deleted) ?? [];
  if (live.length) { select((live.find(r => r.visible) ?? live[0]).userData.source.id, e.ctrlKey || e.shiftKey || e.metaKey); return true; }
  if (s) { flashHint(`${short(tile.tile.actor)}, which carries that tile, is deleted: Ctrl+Z or Reset all brings it back`); return true; }
  return false;
}
// Floor buttons up to the tallest building's floors. The chosen floor stays if there still is one.
function floorOptions() {
  const previous = $('floor').value;
  const count = Math.max(0,...allBuildings().map(b => b.floors.length));
  $('floorGroup').hidden = !count;
  const buttons = [segButton('all', 'All', 'All floors · roof closed')];
  for (let i=1;i<=count;i++) buttons.push(segButton(String(i), String(i), i === 1 ? 'Up to the ground floor' : `Up to floor ${i}`));
  $('floor').replaceChildren(...buttons);
  $('floor').value = buttons.some(b => b.dataset.value === previous) ? previous : 'all';
  cutaway();
}
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
// The map's missions (an export's `missions`: its DefaultMaps.ini records) and the one whose streamed packages show.
// missionPickValue is the picker's value: a record's index ('0', '1', ...), or 'kind:<kind>' for a kind the project
// adds (mission types plan, D2), which streams nothing; missionIndex is the record's index, -1 for an added kind.
let missionIndex = 0, missionPickValue = '0', streamSet = new Set();
// an added kind the address asks for (?mission=kind:...), picked once the project that adds it is open
let askedPick = null;
// The missions the header's picker lists: the map's records, or the project's missions when it names them (its
// records kept, then the kinds it adds).
function headerMissions() {
  const missions = data?.preview ? [] : data?.missions ?? [];
  const labels = missionLabels(missions);
  const all = missions.map((m, i) => ({ value: String(i), index: i, label: labels[i], mission: m }));
  if (!Array.isArray(projectMissions)) return all;
  const kept = new Set(projectMissions.filter(e => Number.isInteger(e.record)).map(e => e.record));
  return [...all.filter(m => kept.has(m.index)),
          ...projectMissions.filter(e => ADDED_KINDS[e.kind]).map(e => ({ value: `kind:${e.kind}`, index: -1,
                                                                          label: `${ADDED_KINDS[e.kind].label} (added)`, mission: addedMission(e.kind), entry: e }))];
}
// the mission the header shows: a record of the map, or a kind the project adds
const headerMission = () => (missionIndex >= 0 ? (data?.missions ?? [])[missionIndex] : headerMissions().find(m => m.value === missionPickValue)?.mission);
// The picker's options again (the project's missions changed, or a project opened), keeping the choice when it is
// still listed.
function refreshMissionPicker() {
  if (!data) return;
  const list = headerMissions(), before = missionPickValue;
  if (askedPick && list.some(m => m.value === askedPick)) { chooseMission(askedPick); askedPick = null; }
  $('missionPick').hidden = list.length < 2;
  $('mission').replaceChildren(...list.map(m => new Option(m.label, m.value)));
  if (!list.some(m => m.value === missionPickValue)) chooseMission(list[0]?.value ?? '0');
  $('mission').value = missionPickValue;
  if (missionPickValue !== before) { refreshLightVisibility(); refreshSpawnMarkers(); placeMissionGizmo(); cutaway(); catalogue(); }
}
const missionName = m => m.label;
function missionLabels(missions) {
  const count = {};
  for (const m of missions) count[m.label] = (count[m.label] || 0) + 1;
  // two records of one kind (a landed transport and a landed terror ship): their display names tell them apart
  return missions.map(m => count[m.label] > 1 ? `${m.label} (${m.display.match(/\(([^)]*)\)/)?.[1]?.trim() || m.display})` : m.label);
}
function chooseMission(value) {
  const missions = data?.preview ? [] : data?.missions ?? [];
  const v = String(value ?? '0');
  if (v.startsWith('kind:')) { missionPickValue = v; missionIndex = -1; streamSet = new Set(); return; }
  const index = Number(v);
  missionIndex = Number.isInteger(index) && missions[index] ? index : 0;
  missionPickValue = String(missionIndex);
  streamSet = new Set(missions[missionIndex]?.streams ?? []);
}
async function open() {
  stopPickBox();
  boxesShown = false; normalLights = false; lightsOn = false; lightsShown = false; zonesOn = false;
  effectsOn = false; pickedEffect = null; normalEffects = false; effectLayer.visible = false; effectsDirty = true; stopWave();
  spawnsOn = false; pickedSpawn = null; spawnZonePick = null; normalSpawns = recall(NORMAL_SPAWNS) === '1'; spawnRulesData = null;
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
  activeMapId=builderMode ? null : parameters.get('map') || mapCatalogue.defaultMap;
  const activeMap=mapCatalogue.maps.find(map=>map.id===activeMapId);
  mapBrowser=createMapBrowser({ els: { root: $('mapDialog'), form: $('mapForm'), search: $('mapSearch'), prepared: $('mapPrepared'),
    groups: $('mapGroups'), list: $('mapList'), count: $('mapCount'), message: $('mapMessage'), bar: $('mapBar'), ok: $('mapOk'),
    // On a patch preview the open map counts as not open: choosing it opens its original layout.
    cancel: $('mapCancel'), close: $('mapClose') }, maps: mapCatalogue.maps,
    current: activeMap?.ready && !parameters.get('scene') ? activeMapId : null,
    // The map asked for but not prepared yet opens as asked (its project too) once it is ready.
    prefabs: async () => (await prefabApi.list()).prefabs, onPrefab: id => goTo({ prefab: id }),
    onOpen: id => { mapBrowser.close(); goTo({ map: id, scene: null, project: null, mission: null }); } });
  if (builderMode) {
    data = emptyPrefabScene();
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
  cachePrefix='/cache/'+encodeURIComponent(activeMapId)+'/';
  const requestedScene = parameters.get('scene') || 'scene.json';
  if (!/^(scene|preview-\d+)\.json$/.test(requestedScene)) throw Error('Invalid scene selection');
  // The bar: the layout file's download is the first tenth, building the pieces (their meshes and textures
  // downloading meanwhile) the rest.
  const mapName = activeMap.label;
  loadingState(`Opening ${mapName}: reading its layout…`, 0);
  const familiesAsked = fetch(`/maps/${encodeURIComponent(activeMapId)}/families.json`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  data = await fetchJson(cachePrefix+requestedScene, share => loadingState(`Opening ${mapName}: reading its layout…`, 0.1 * share));
  await startScene({ parameters, familiesAsked, mapName });
}
// Both maps and the prefab workspace start the same editor on a scene.
async function startScene({ parameters, familiesAsked, mapName }) {
  mergedBuildings = null;
  // No layout menu any more (the user's choice, 7 November): a patch preview (Bar's EXP-07 and EXP-08 layouts)
  // opens only from its address, ?scene=preview-<n>.json.
  originalPositions = data.scope !== 'sample';
  $('layout').hidden = data.scope !== 'sample';
  document.title = `${data.name} · XCOM Map Workshop`;
  $('previewChip').hidden = !data.preview;
  // Configure light data before the first lit material compiles.
  lighting = createMapLighting({ world, sun, hemisphere, scene: data, maxTextureSize:renderer.capabilities.maxTextureSize });
  $('scenery').value=data.preview ? 'full' : data.tactical?.recommendedView || 'full';
  $('sceneryGroup').hidden=!data.playableBounds || data.scope!=='map';
  $('projectSize').hidden = !projectsAvailable();     // Map grid: any whole map
  $('projectClear').hidden = !projectsAvailable();
  $('projectMissions').hidden = !projectsAvailable();
  ownGrid = null; startingCache = null; landingLines = { kind: null, lines: [] };
  // the install's landing lines for the map (Clear map plan, section 4): the starting list of landing zones
  if (data.scope === 'map' && !data.preview && !builderMode && activeMapId)
    fetch(`/maps/${encodeURIComponent(activeMapId)}/landing-lines.json`).then(r => (r.ok ? r.json() : null)).catch(() => null)
      .then(v => { if (v && Array.isArray(v.lines)) { landingLines = v; startingCache = null; refreshGroundGrid(); refreshLandingZones(); } });
  drawPlayArea();
  for (const button of $('lighting').querySelectorAll('button')) button.disabled = button.dataset.value !== 'neutral' && !lighting.available;
  // Neutral light by default: our map lighting is an approximation (the user's choice, 7 November).
  $('lighting').value = 'neutral';
  // What the original layout's missions stream into the map (export 13), shown for reference and never edited.
  const streamObjects = data.preview ? [] : Object.values(data.streams || {}).flatMap(s => s.objects);
  chooseMission(parameters.get('mission') ?? '0');
  if (parameters.get('project') && parameters.get('mission')?.startsWith('kind:')) askedPick = parameters.get('mission');
  // Request every mesh and material up front so downloads overlap; pieces are
  // still assembled in scene order below.
  const everything = [...data.objects, ...streamObjects];
  for (const obj of everything) {
    track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(cachePrefix+data.meshes[obj.mesh].url));
    for (const id of obj.materials) { const [key, tint] = materialKey(obj, id); track(materialCache, key, () => material(id, tint)); }
  }
  let built = 0;
  for (const obj of everything) {
    try { addRoots([await buildRoot(obj)]); }
    catch (e) { console.error(obj.actor, e); loadErrorCount++; }
    built++;
    if (built % 8 === 0 || built === everything.length)
      loadingState(`Opening ${mapName}: building its pieces…`, 0.1 + 0.9 * built / everything.length,
                   `${built} of ${everything.length} pieces · meshes and textures load as they are needed`);
  }
  if (!roots.size && !builderMode) throw Error('No meshes could be displayed. See import notes and browser console.');
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
  // The mission picker: shown when the map's missions stream different packages (Police Station's data recovery
  // streams its radar arrays, its abduction and terror missions don't).
  const missions = headerMissions();
  $('missionPick').hidden = missions.length < 2;
  $('mission').replaceChildren(...missions.map(m => new Option(m.label, m.value)));
  $('mission').value = missionPickValue;
  $('mission').title = 'Which mission\'s streamed packages to show: LWR\'s patches and the mission\'s own objects, for reference';
  $('floorGroup').hidden = !allBuildings().length;
  // Patch helpers: pieces a patch places hidden in game (LWR's blockers and cover, ladders' collision), hidden here
  // too by default; unticking Hide patch helpers draws them as a wireframe.
  const streamHelpers = streamObjects.some(o => o.hidden);
  $('helpersRow').hidden = !(data.inheritedPatches?.length || streamHelpers);
  $('composition').textContent = [...(data.inheritedPatches || []).map(p=>{
    const removed=data.objects.filter(o=>o.layer==='inherited' && o.sourcePackage===p.name && o.hiddenBy!=null).length;
    return `${p.name} · ${p.components} source helpers${removed ? ` (${removed} removed by layout)` : ''} · ${p.records.filter(r=>r.actorClass==='XComRebuildWorldDataVolume').length} rebuild volumes`;
  }), ...(data.preview ? [] : Object.entries(data.streams || {}).map(([name, s]) =>
    `${name} · ${s.error ? `not shown: ${s.error}` : `${s.objects.length} pieces (${s.hiddenComponents} hidden in game), ${s.rebuildVolumes} rebuild volumes`}`))].join(' / ');
  placeObjects(); floorOptions(); catalogue(); frame();
  applyLighting = () => {
    // the lights as edited (lightRecords), when they changed since
    if (lightsDirty && data.scope === 'map' && !data.preview) {
      lighting.setLights(lightRecords()); lightsDirty = false; lastLightSync = performance.now();
    }
    if (soloOn) { lighting.dim(sun.target.position, lightRadius); return; }
    const result = lighting.apply($('lighting').value, sun.target.position, lightRadius);
    $('lightCount').textContent = $('lighting').value === 'neutral' ? '' : `${result.local} local lights`;
  };
  applyLighting();
  $('loading').hidden = true;
  // the ground grid and the landing zones, now that the pieces are on the map (Clear map plan, sections 3 and 4), and
  // the mission's objects (mission types plan, C2)
  refreshGroundGrid(); refreshLandingZones(); refreshSpawnMarkers(); loadSpawnRules();
  // Import notes: a count on the header button; the list opens from it. Preview notes count as warnings.
  const issues = data.preview ? [...data.preview.notes,...data.diagnostics.filter(d => !data.preview.notes.some(n => n.source === d.source && n.message === d.message))] : data.diagnostics;
  $('issueCount').textContent = issues.length + loadErrorCount || '';
  $('issueCount').classList.toggle('warn', Boolean(data.preview?.notes.length || loadErrorCount));
  for (const issue of issues) {
    const item = text($('diagnostics'), 'div', '', 'note');
    text(item, 'strong', short(issue.source)); text(item, 'div', issue.message);
  }
  if (loadErrorCount) text($('diagnostics'), 'div', `${plural(loadErrorCount, 'piece')} could not be displayed; the browser console has the errors.`, 'note');
  // Exports before version 12 carry no prefab/partner links: say so instead of silently moving one actor.
  const hasLinks = builderMode || data.objects.some(o => 'prefab' in o);
  $('editLinked').disabled = !hasLinks;
  if (!hasLinks) {
    $('editLinked').classList.remove('on');
    $('editLinked').title = 'Linked pieces need a re-export: this export has no prefab/partner links. Re-export the map (export version 12) and restart the viewer server.';
  }
  if (!projectsAvailable()) $('projectButton').title = 'Project: load one (Ctrl+O). Saving needs the map\'s original layout: open the map from the map browser (M)';
  // An export older than what lights and Builds need (export 18 and its glowing pieces): prepare it again.
  // An export older than the server's exporter (the catalogue's outdated: an update since the map was prepared) is
  // prepared again at once, so the update's fixes reach it (its dialog says so; a failure leaves the offer in a banner).
  exportProblem = projectsAvailable() ? familyTable?.exportProblem ?? null : null;
  const outdated = Boolean(mapCatalogue?.maps?.find(m => m.id === activeMapId)?.outdated) && data.scope === 'map' && !data.preview;
  // once a session per map: should it come back still outdated, the dialog waits for a click rather than looping
  const tried = `workshop.updated.${activeMapId}`;
  let again = false;
  try { again = sessionStorage.getItem(tried) === '1'; sessionStorage.setItem(tried, outdated ? '1' : '0'); } catch { /* no session storage: start */ }
  if (outdated) showPrepare('update', !again);
  else if (exportProblem) showPrepare('open');
  if (builderMode) {
    document.body.classList.add('prefab-builder');
    $('builderSize').hidden = false;
    $('prefabTest').hidden = false;
    $('projectButton').querySelector('small').textContent = 'Prefab';
    $('projectMenu').querySelector('h3').textContent = 'Prefab';
    $('projectButton').title = 'Prefab: Save, Open and Test in game';
    $('mapButton').querySelector('small').textContent = 'Prefab';
    $('mapButton').title = 'Open a map or prefab (M)';
    $('projectLoad').querySelector('span').textContent = 'Open…';
    const loadProjectButton = text($('projectLoad').parentElement, 'button', 'Load project…');
    loadProjectButton.type = 'button'; loadProjectButton.onclick = () => showFileDialog('load');
    setLibraryScope('all');
    await openPrefabDocument(prefabParameter);
    void prefabTest.reconnect();
  } else if (parameters.get('project')) await openProject(parameters.get('project'));
  window.viewer = {data, mapId:activeMapId, gizmo, renderer, world, camera, controls, roots, select, frame, lighting, sun, hemisphere, grid,
    // the selected cover piece's handles on the screen ({ key: [x, y] }, none when they don't show), and a record put on a
    // cover piece as one undo step (for scripts: the guide's shots, the checks)
    // (each [x, y, x', y']: the handle, and where a point `tiles` tiles further out along its face's axis is, in below 0)
    coverHandles: (tiles = 1) => { const r = handleCover(), project = projector();
      return r ? Object.fromEntries(coverFacesNow(r).map(f => { const p = coverHandlePoint(f);
        return [f.face[0], [...project(p), ...project(p.clone().addScaledVector(f.dir, 96 * tiles))]]; })) : {}; },
    setCover: (id, cover) => { const r = roots.get(id); if (r?.userData.source.cover) setCover(r, normalCover(cover, coverRecipe())); },
    // made walls (custom geometry plan, M1): the Walls entries, drawing, a game point on the screen, the picked wall's
    // handles on the screen ({ key: [x, y, x', y'] }: the handle and a point `units` along its drag axis), its state
    wallEntries, startWallDrawing, stopWallDrawing,
    wallDrawing: () => wallDrawing && { look: wallDrawing.look.id, ready: Boolean(wallDrawing.template), drawing: Boolean(wallDrawing.start),
                                        last: wallDrawing.last ? { ...wallDrawing.last } : null },
    screenOf: ([x, y, z]) => projector()(new THREE.Vector3(x, z, y)),
    wallHandles: (units = 96) => { const r = handleWall(), project = projector();
      return r ? Object.fromEntries(wallHandlesNow(r).map(h => { const p = wallHandlePoint(h);
        return [h.key, [...project(p), ...project(p.clone().addScaledVector(h.dir, units))]]; })) : {}; },
    wallState: id => { const r = madeWallRoot(id); return r ? wallState(r) : null; },
    // the map's surface below a point (game x, y, from z down), as the wall tool and the Add panel find the floor
    groundAt: (x, y, fromZ = 4096) => groundAt(x, y, fromZ),
    wallMeshReady: id => { const r = madeWallRoot(id); return Boolean(r && loaded(geometryCache, r.userData.source.mesh)); },
    addWallOpening, wallPanelText: () => $('wallBox').hidden ? null : $('wallBox').innerText,
    streamPieces: streamObjects.length, mission: () => missionIndex, missionPick: () => missionPickValue, headerMissions,
    missionMoves: () => [...missionMoves.values()], moveMissionGroup,
    // (a base spawn point: turned, given values, back as the map has it; SP6)
    editBaseSpawn, resetBaseSpawn, spawnEditShown: () => !$('spawnEdit').hidden, copySpawn, deleteSpawn, editSpawnCopy,
    spawnAddEntries, startSpawnPlacing, placeSpawn, spawnPlacing: () => spawnPlacing,
    // where a game point is drawn in the view's canvas (client pixels), for clicks at a tile
    clientAt: ([x, y, z]) => { const p = gameToView([x, y, z]).project(camera), r = renderer.domElement.getBoundingClientRect();
                               return [r.left + (p.x + 1) / 2 * r.width, r.top + (1 - p.y) / 2 * r.height]; },
    // (the mission objects' hooks before the Spawns view: a stream object picked by its stream and actor)
    setPickedMission: o => setPickedSpawn(o ? spawnKey(o.stream, o.actor) : null),
    pickedMission: () => { const e = spawnEntry(pickedSpawn); return e && e.layer !== 'base' ? { stream: e.stream, actor: e.record.actor } : null; },
    missionGizmo: () => ({ enabled: missionGizmo.enabled, at: [missionProxy.position.x, missionProxy.position.z, missionProxy.position.y] }),
    missions: () => projectMissions, showMissions, missionsPanel,
    tileGrid: () => { updateTileGrid(); return grid.children[0]?.userData ?? null; },
    pick, changes, pickables, pieces, showPieces, library, setLibraryScope, libraryTemplate, setSnapMode, families: () => families, playArea,
    // prefabs (prefab plan stage P), for the browser smoke test
    prefabs: prefabTab, prefabApi, prefabRecords, savePrefab, choosePrefab, prefabClip,
    builderMode, builderDocument, builderRecords, saveBuilder, openPrefabDocument, applyPrefabDocument, goTo, keepRecovery,
    pasteSnapshot, snapshot, dirty, copySerial: () => copySerial,
    placementProblem: at => {
      if (!placing) return 'No placement';
      const target = dropTarget(placing.clip, at);
      return target ? prefabPlacementProblem(placing.clip, placeMove(placing.clip, target, placing.turns)) : 'No target';
    },
    gridNow: id => gridNow(roots.get(id)),
    groupList: () => [...groups.values()].map(g => ({ id: g.id, prefab: g.prefab ?? null, members: [...g.members.keys()] })),
    // lights (editor lights plan 4.6), for the browser smoke test
    lightRoots, lightsShown: () => lightsShown, setLightsShown, lightRecords, pickLight, lightPanel, setSolo, soloOn: () => soloOn,
    lightReach: () => reachNow, areaBindings: () => new Map(areaBindings), setBinding, lightShapes, derivedCopies: () => derivedCopies,
    // the selected light's drag handles: each one's value and screen point, and the light's
    lightHandles: () => { const project = projector();
      return handleDefs.map(h => ({ key: h.key, value: h.value, screen: project(h.at(h.value)), origin: project(h.origin) })); },
    lightDragging: () => Boolean(lightDrag),
    levelSnap: () => levelSnap, setLevelSnap, chosenStorey: (x, y) => chosenStorey(x, y),
    // the ground under a point as invisible floors read it (the game's collision once it has come)
    groundAt: (x, y, fromZ) => groundAt(x, y, fromZ), collisionRead: () => (lineCollision ? !lineCollisionFailed : null),
    recipeOf: id => recipeOf(roots.get(id)?.userData.source),
    ladderEnds: id => ladderNow(roots.get(id)), ladderMarks,
    placing: () => placing && { name: placing.clip.name, fromList: Boolean(placing.entry), ghost: placing.ghost, turns: placing.turns, floor: placing.clip.floor },
    editState, projectState: () => stateKey(editState()), saveProject, fileDialog, highlight,
    // Clear map, the ground grid and landing zones (Clear map plan), for the browser smoke test
    clearPlan: keep => { const p = clearPlan(keep ?? null); return { pieces: p.pieces, lights: p.lights, landing: p.landing, script: p.script, deletable: p.originals.length,
                                                       editableLights: p.originalLights.length, boxes: p.boxes.length, outside: p.outside, lightsOutside: p.lightsOutside }; },
    outsideBox: dims => outsideBox(dims),
    ownLandingCount: () => (data ? ownLandings(data).length : 0),
    gridTool: () => ({ on: gridTool, handles: gridHandles.visible ? gridHandles.children.map(h => h.children[0].userData.gridAxis) : [],
                       dims: [...data.tileGrid.dimensions] }),
    setGridTool, gridHandleAt: axis => { const v = gridHandleAt(axis); return [v.x, v.z, v.y]; },
    zoneGizmo: () => ({ enabled: zoneGizmo.enabled, shown: zoneGizmoHelper.visible, axis: zoneGizmo.axis, mode: zoneGizmo.mode,
                        dragging: zoneGizmo.dragging, at: [zoneProxy.position.x, zoneProxy.position.z, zoneProxy.position.y] }),
    clearMap, showClearMap, cleared: () => cleared, clearKeepsOutside: () => clearKeepsOutside, stage: () => stage, zones: () => zonesNow(), landingLines: () => landingLines,
    groundGrid: () => ({ shown: groundGrid.visible, ...groundGrid.userData, ground: groundHeight() }), pickZone, pickedZone: () => pickedZone,
    lastClearMs: () => lastClearMs, landingLayer, setZones, setZonesShown, zonesOn: () => zonesOn,
    // the Spawns view (spawns plan, SP3): the entries drawn now, with where each marker stands and its screen point
    spawnLayer, spawnsOn: () => spawnsOn, setSpawnsShown, normalSpawns: () => normalSpawns, setNormalSpawns, showSpawn,
    pickedSpawn: () => pickedSpawn, pickSpawn: key => setPickedSpawn(key), spawnRules: () => spawnRulesData, bombHelperFix,
    projectSpawnRules: () => projectSpawnRules, setSpawnRule,
    spawns: () => { const project = projector(), shown = new Set(spawnLayer.children.map(m => m.userData.spawn));
      return spawnEntriesNow.map(e => ({ key: e.key, layer: e.layer, stream: e.stream, kind: e.record.kind, role: e.record.role ?? null,
        group: e.record.group ?? null, actor: e.record.actor, marked: shown.has(e.key), at: spawnAt(e), screen: project(gameToView(spawnAt(e))),
        deleted: spawnDeleted(e), box: e.record.kind === 'noSpawn' ? spawnBoxNow(e) : null })); },
    // a no-spawn volume's face handles (the Buildings view's six): where each is on screen, null when none show
    spawnVolumeHandles: () => { const e = spawnVolumeHandle(), b = e && spawnBoxNow(e), project = projector();
      return b ? Object.fromEntries(FACES.map(([key]) => [key, project(viewPoint(handlePoint(b, key)))])) : null; },
    spawnEdits: () => [...missionMoves.values()].map(m => structuredClone(m)),
    spawnPanelText: () => ($('spawnPanel').hidden ? null : { title: $('spawnTitle').textContent, info: $('spawnInfo').textContent }),
    setSpawnFilter: (family, on) => { spawnFilters = { ...spawnFilters, [family]: on }; syncSpawnFilters(); refreshSpawnMarkers(); },
    // the Effects view (effects and sounds plan, FX1): each marker's record id, where it stands (game units), its
    // screen point and whether it is a copy the Build makes with a piece
    effectsOn: () => effectsOn, setEffectsShown, pickEffect, pickedEffect: () => pickedEffect, effectShapes,
    // the Wave preview (FX2): what plays, how far it has got and why it failed
    playWave: wave => { const r = effectRoots.get(pickedEffect)?.userData.source; if (r) playWave(r, wave); }, stopWave,
    // effects and sounds edited (FX3): each root's state, the normal view's switch, keep where it is
    likenessPane: () => ({ shown: likenessPane.shown ? likenessPane.shown.source.system : null, hidden: $('likenessPane').hidden,
      particles: likenessPane.shown?.likeness.count() ?? 0 }), ghostLikenesses: () => ghostLikenesses.filter(g => !g.idle).length,
    likenessState: () => ({ on: likenessOn, effects: likenesses.size, particles: likenessCount, thin: likenessThin,
      drawn: [...likenesses].filter(([, k]) => k.likeness.group.visible).map(([owner]) => owner.userData.source?.id ?? null) }), setLikeness,
    // one effect's likeness, emitter by emitter (effects_preview.js describe)
    likenessOf: id => { const k = likenesses.get(effectRoots.get(id)); return k ? k.likeness.describe() : null; },
    effectRoots, effectState: id => { const r = effectRoots.get(id); return r && { id, kind: r.userData.source.kind, added: Boolean(r.userData.source.added),
      deleted: r.userData.deleted, moved: Boolean(r.userData.edit), stays: r.userData.stays, gone: Boolean(r.userData.derivedGone), visible: r.visible,
      at: (v => [v.x, v.z, v.y])(new THREE.Vector3().setFromMatrixPosition(r.matrix)), viewOnly: effectViewOnly(r.userData.source, 'move'),
      // its values (FX5), as the project keeps them, and its record as edited
      values: r.userData.values ? structuredClone(r.userData.values) : null, now: effectNow(r) }; },
    setNormalEffects, normalEffects: () => normalEffects, setEffectStays: (id, on) => { const r = effectRoots.get(id); if (r) setEffectStays(r, on); },
    seekWave: t => { if (wavePlayer) wavePlayer.audio.currentTime = t; },
    wave: () => wavePlayer && { wave: wavePlayer.wave, record: wavePlayer.record, state: wavePlayer.state, why: wavePlayer.why,
                                time: wavePlayer.audio.currentTime, duration: wavePlayer.audio.duration, paused: wavePlayer.audio.paused, volume: wavePlayer.audio.volume },
    effectMarkers: () => { if (effectsDirty) refreshEffects(); const project = projector();
      return effectMarkers.map(m => ({ id: m.userData.record.id, kind: m.userData.record.kind, derived: Boolean(m.userData.derived),
                                       added: Boolean(m.userData.record.added),
                                       ...(w => ({ at: [w.x, w.z, w.y], screen: project(w) }))(m.getWorldPosition(new THREE.Vector3())) })); },
    zoneHit: (x, y) => zoneHit(x, y), movedLandingActors: () => [...movedLandingActors()],
    // for the browser smoke test: floor pieces (each carrying actor's kind, and the floor stamps' supports), the
    // screen point of a game point, building-floor listings and the overlay
    floorPieces: () => { const f = floorData(); return { kinds: Object.fromEntries(f.kinds), supports: [...f.stamps.values()].map(v => [v.actor, v.support]) }; },
    screenOf: ([x, y, z]) => { const v = new THREE.Vector3(x, z, y).project(camera), r = renderer.domElement.getBoundingClientRect();
      return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height]; },
    // box select, for the browser smoke test
    boxesShown: () => boxesShown, setBoxesShown, pickVolumeEdge,
    ownSelected: () => [...ownSet].map(b => b.name), ownEdge: (x, y) => pickBoxEdge(x, y)?.own?.userData.own.building.name ?? null,
    ownBoxes: () => ownVolumeLayer.children.filter(c => c.userData.own).map(c => ({ building: c.userData.own.building.name, floor: c.userData.own.floor, box: c.userData.own.box })),
    lightsOn: () => lightsOn, normalLights: () => normalLights, setNormalLights, setNormalView,
    pickBox: () => pickBox && [...pickBox], pickTool: () => pickTool, setPickTool, takePickBox, pickHits: () => pickHits.map(c => c.id),
    setPickBox: box => { pickBox = [...box]; pickTool = false; refreshPickBox(true); },
    pieceBox: id => (roots.get(id) ? boxOf(roots.get(id))?.slice() ?? null : null),
    pickMoveHandle: () => (pickBox ? projector()(viewPoint(pickMovePoint())) : null),
    pickFaceHandle: key => (pickBox ? projector()(viewPoint(handlePoint(pickBox, key))) : null),
    // the Buildings view, for the browser smoke test
    buildings: () => buildings, allBuildings, volumeRoots, volumesOn: () => volumesOn, setVolumesShown, volumeBox, addVolumes, newBuilding, setVolumeTool,
    volumeHandle: key => { const r = volumeRoots.get(selected); return r ? projector()(viewPoint(handlePoint(volumeBox(r), key))) : null; },
    ownPicked: () => ownPicked?.userData.own ?? null,
    // the map's own buildings made editable (map buildings plan), for the browser smoke test
    savedBuildings, restoreMapBuildings, copyVolumes, pasteVolumes, deleteVolumes, clipboard: () => clipboard, pasteSnapshot,
    mapEdits: () => { const e = mapEdits(); return { changed: [...e.changed], gone: [...e.gone] }; },
    putVolume: (id, box) => { const r = volumeRoots.get(id); recordVolumes([r], () => setVolumeBox(r, box)); },
    listingsNow: id => roots.get(id) && listingsNow(roots.get(id)), floorTiles: () => floorTileLayer && floorTileLayer.userData.tiles.length,
    project: () => project && { id: project.doc.id, name: project.doc.name, revision: project.revision, dirty: dirty(), carried: project.carried, doc: project.doc }};
}

const search = $('search');
search.addEventListener('input', catalogue);
search.addEventListener('focus', () => { search.select(); catalogue(); });
search.addEventListener('blur', () => { $('objects').hidden = true; });
search.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') highlightResult(resultIndex + (e.key === 'ArrowDown' ? 1 : -1));
  else if (e.key === 'Enter') {
    const item = $('objects').querySelectorAll('.piece')[Math.max(0, resultIndex)];
    if (item) choose(item.dataset.id, e.ctrlKey || e.shiftKey || e.metaKey);
  } else if (e.key === 'Escape') { if (search.value) { search.value = ''; catalogue(); } else search.blur(); }
  else return;
  e.preventDefault();
});
// Pressing in the list must not take focus from the search box (that would close the list before the click lands).
$('objects').addEventListener('mousedown', e => e.preventDefault());
// Header menus: one open at a time; a press elsewhere or Escape closes it.
function showPop(id) {
  for (const button of document.querySelectorAll('[data-pop]')) {
    const on = button.dataset.pop === id, pop = $(button.dataset.pop);
    pop.hidden = !on;
    button.setAttribute('aria-expanded', on);
    if (on && pop.classList.contains('left')) pop.style.left = `${button.getBoundingClientRect().left - viewport.getBoundingClientRect().left}px`;
  }
  if (id === 'projectMenu') renderProjectMenu();
  if (id === 'settingsMenu') refreshSquadLine();
}
for (const button of document.querySelectorAll('[data-pop]')) button.onclick = () => showPop($(button.dataset.pop).hidden ? button.dataset.pop : null);
document.addEventListener('pointerdown', e => { if (!e.target.closest('.pop, [data-pop]')) showPop(null); });
$('statsToggle').checked = recall('viewer.stats') === '1';
$('statsLine').hidden = !$('statsToggle').checked;
$('statsToggle').onchange = e => { $('statsLine').hidden = !e.target.checked; remember('viewer.stats', e.target.checked ? '1' : '0'); };
$('sourceDetails').open = recall('viewer.sourceDetails') === '1';
$('sourceDetails').ontoggle = e => remember('viewer.sourceDetails', e.target.open ? '1' : '0');
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
  if (!mapBrowser || mapBrowser.open || fileDialog.open || projectManager.open || gameMaps.open || setupDialog.open || buildOptions.open || !$('buildModal').hidden) return;
  showPop(null);
  if (placing) stopPlacing();
  mapBrowser.show();
}
$('mapButton').onclick = showMapBrowser;
$('mission').onchange = e => {
  chooseMission(e.target.value);
  const parameters = new URLSearchParams(location.search);
  if (missionPickValue !== '0') parameters.set('mission', missionPickValue); else parameters.delete('mission');
  history.replaceState(null, '', `${location.pathname}?${parameters}`);
  // a streamed piece that goes out of view leaves the selection
  if (isStream(allRoots.get(selected)?.userData.source) && !streamSet.has(allRoots.get(selected).userData.source.stream)) select(null);
  refreshLightVisibility();
  refreshSpawnMarkers(); placeMissionGizmo();     // (a marker of the mission before goes, with its gizmo)
  effectsDirty = true;     // (the Effects view shows the streams of the mission picked)
  cutaway(); catalogue();
};
segmented($('floor'), () => { cutaway(); ghostDirty = true; restingHint(); });
$('hideHelpers').onchange = () => {cutaway();catalogue();};
segmented($('scenery'), () => {cutaway();catalogue();frame();refreshLightVisibility();effectsDirty = true;});
$('frame').onclick = () => frame();
$('selected').onclick = () => selected && frame(allRoots.get(selected));
$('grid').onchange = e => { grid.visible = e.target.checked; tileKey = null; };
let applyLighting = () => {};
segmented($('lighting'), () => applyLighting());
// Update every base and cutaway material, not only those currently assigned, so
// changing the floor cut afterwards keeps the chosen wireframe state.
$('wire').onchange = e => {
  for (const mat of new Set([...pickables.map(p => p.userData.baseMaterial), ...cutMaterials.values()])) mat.wireframe = e.target.checked;
};
$('exposure').oninput = e => { renderer.toneMappingExposure = Number(e.target.value); };
$('layout').onclick = () => { originalPositions = !originalPositions; placeObjects(); frame(); $('layout').textContent = originalPositions ? 'Piece study' : 'Original positions'; };
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
renderer.domElement.addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; ghostDirty = true; tipDirty = true; });
renderer.domElement.addEventListener('pointerleave', () => { pointer = null; ghostDirty = true; tipDirty = true; });
controls.addEventListener('change', () => { ghostDirty = true; tipDirty = true; });
renderer.domElement.addEventListener('dblclick', () => (effectsOn ? frameEffect() : selected && !gizmo.busy() && frame(allRoots.get(selected))));
$('editMove').onclick = () => gizmo.setMode('translate');
$('editRotate').onclick = () => gizmo.setMode('rotate');
$('editOff').onclick = () => gizmo.setMode('off');
$('editSpace').onclick = () => gizmo.toggleSpace();
// The pivot (C): each piece's own origin, or the selection's centre (Discord feedback S4); remembered on this computer.
const PIVOT = 'viewer.pivot';
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
  snapMode = next; gizmo.setSnap(next); ghostDirty = true;
  snapButton(); refreshGrid(roots.get(selected));
}
$('editSnap').onclick = () => setSnapMode(SNAPS[snapMode][0]);
$('editLevels').onclick = () => setLevelSnap(!levelSnap);
levelButton();
pieces = createPieceBrowser({
  els: { panel: $('library'), list: $('libList'), filter: $('libFilter'), kind: $('libKind'), where: $('libWhere'),
         sort: $('libSort'), foot: $('libFoot') },
  renderer, preview: entry => previewGroup(entryParts(entry), null, entry.frame), onChoose: chooseEntry,
});
library = createLibraryBrowser({
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
});
prefabTab = createPrefabBrowser({
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
});
segmented($('libScope'), () => setLibraryScope($('libScope').value));
libraryScope = LIBRARY_SCOPES[recall('workshop.libraryScope')] ? recall('workshop.libraryScope') : 'map';
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
$('alignTarget').onchange = e => { alignTarget = e.target.value; e.target.blur(); alignPanel(); };
$('groupMake').onclick = () => lockAsGroup();
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
  if (assigning) { assigning = null; lightPanel(); return; }
  assigning = selected; lightPanel(); flashHint('Click the piece this light glows from · Esc cancels');
};
$('lightKeep').onclick = () => { const root = lightRoots.get(selected); if (root) setBinding(root, null); };
$('lightAuto').onclick = () => { const root = lightRoots.get(selected); if (root) setBinding(root, undefined); };
$('editLights').onclick = () => data && setLightsShown(!lightsOn);
$('editZones').onclick = () => data && setZonesShown(!zonesOn);
$('editEffects').onclick = () => data && setEffectsShown(!effectsOn);
$('editSpawns').onclick = () => data && setSpawnsShown(!spawnsOn);
$('editNormal').onclick = () => data && setNormalView();
$('normalLights').onchange = e => { setNormalLights(e.target.checked); e.target.blur(); };
$('areaToggle').onchange = e => { areaShown = e.target.checked; remember(AREA_SHOWN, areaShown ? '1' : '0'); refreshLightVisibility(); e.target.blur(); };
$('reachToggle').onchange = e => {
  reachShown = e.target.checked; remember(REACH_SHOWN, reachShown ? '1' : '0'); e.target.blur();
  reachKey = ''; refreshLightShapes(); lightPanel();   // drawn again with or without the outlines
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
const FLY_KEYS = 'viewer.flyKeys';
const panKeys = new Set();
let panFast = false, flyKeys = recall(FLY_KEYS) === '1';
// View options' camera speeds (Discord feedback S2, S3): each a factor on its default, remembered on this computer.
// Move speed scales PAN_SPEED, key turn speed TURN_SPEED, and drag turn speed OrbitControls' orbit and the look-drag
// along the view (LOOK_PER_SCREEN). A double-click on a slider puts it back to 1; letting go of one gives the keys back
// to the camera.
const CAMERA_SPEEDS = { moveSpeed: 'viewer.moveSpeed', turnSpeed: 'viewer.turnSpeed', dragSpeed: 'viewer.dragSpeed' };
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
// V select, T box select, G move, R rotate (while placing, R turns the piece), P the piece list, X world/local, C the
// pivot (origin or centre), F frame, arrow keys and
// WASD move the camera and Q and E turn it, O solos the selected lights, B shows or hides the play area, Ctrl+F find,
// Escape cancels a drag,
// stops placing, closes a menu or, when there is none of those, clears the selection,
// Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z) undo and redo, Ctrl+C / X / V copy, cut and paste pieces, Ctrl+G groups the
// selection and Ctrl+Shift+G ungroups the selected group, Delete deletes, Ctrl+S saves, Ctrl+B saves
// and builds, and Ctrl+O loads a project. Typing in a field never triggers them (Ctrl+F, S and O aside), and Ctrl+C with
// nothing selected is the browser's own copy. The Save and Load dialogs keep their own keys while open.
document.addEventListener('keydown', e => {
  const key = e.key.toLowerCase();
  if (fileDialog.open || projectManager.open || gameMaps.open || mapBrowser?.open || setupDialog.open || buildOptions.open) { if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f', 'b'].includes(key)) e.preventDefault(); return; }
  if ((e.ctrlKey || e.metaKey) && key === 'f') { e.preventDefault(); search.focus(); return; }
  if ((e.ctrlKey || e.metaKey) && key === 's') { e.preventDefault(); if (!e.repeat) saveProject(); return; }
  if ((e.ctrlKey || e.metaKey) && key === 'o') { e.preventDefault(); if (!e.repeat) showFileDialog('load'); return; }
  if ((e.ctrlKey || e.metaKey) && key === 'b') { e.preventDefault(); if (!e.repeat) openBuild(); return; }
  if (e.target.closest?.('input, select, textarea, [contenteditable]')) return;
  // while a light's handle is dragged, Escape puts it back and other keys wait
  if (lightDrag) { if (key === 'escape') endLightDrag(false); e.preventDefault(); return; }
  if (volumeDrag) { if (key === 'escape') endVolumeDrag(false); e.preventDefault(); return; }
  if (coverDrag) { if (key === 'escape') endCoverDrag(false); e.preventDefault(); return; }
  if (wallDrag) { if (key === 'escape') endWallDrag(false); e.preventDefault(); return; }
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
        const turn = key === '[' ? -16384 : 16384, hint = `Turned a quarter ${turn > 0 ? 'right' : 'left'}`;
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
    if (assigning) { assigning = null; lightPanel(); flashHint('Assigning cancelled'); }
    else if (gizmo.cancel()) dragHint(false);
    else if (placing) stopPlacing();
    else if (document.querySelector('.pop:not([hidden])')) showPop(null);
    else if (selected) select(null);
    else if (ownSet.size || (ownPicked && !volumesOn)) { ownSet.clear(); ownPicked = null; refreshVolumes(); volumePanel(); }
    else return;
  }
  else if (e.altKey) return;
  else if (PAN_KEYS[key] || TURN_KEYS[key]) { panKeys.add(key); panFast = e.shiftKey; }
  else if (key === 'p') { if (data) showPieces(!pieces.open); }
  else if (key === 'm') showMapBrowser();
  else if (key === 'r') {
    // While placing, R turns the piece a quarter turn about its pivot (Shift+R the other way); otherwise it is Rotate.
    if (!placing) { gizmo.setMode('rotate'); e.preventDefault(); return; }
    placing.turns = (placing.turns + (e.shiftKey ? 3 : 1)) % 4; ghostDirty = true;
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
    const at = `${Math.round(controls.target.x / 96)},${Math.round(controls.target.z / 96)}`;
    if (at !== builderTarget || now - builderRefresh > 2000) { builderTarget = at; builderRefresh = now; refreshBuilder(); }
  }
  scaleMarkers();
  scaleSpawnMarkers();
  updateLightHandles();
  updateVolumeHandles();
  updateCoverHandles();
  updateWallHandles();
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
