import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { createGizmo, placedPose, actorMatrix, recipeMove } from './gizmo.js';
import { collectPieces, createPieceBrowser, destructionNote, lootNote, pieceGrid, useFamilies } from './pieces.js';
import { api as projectApi, memberKey, stateKey, targetKey, tidyLocation, tidyRotator, uuid, validStage, tidyStage,
         stageMax, STAGE_MAPS, groupKey, buildingKey, pruneGroups, mapBuildingId, BUILDING_SAME, validLandingZone } from './project.js';
import { ROLES as FLAG_ROLES, lowPiece, made as madeFlags, normalize as normalizeFlags, plan as planFlags, rawOf as flagRaw, roles as flagRoles } from './piece_flags.js';
import { ownLandings, startingZones, groundOf } from './spawns.js';
import { createProjectDialog, savedWhen } from './project_files.js';
import { createProjectManager } from './manager.js';
import { createQueueController, sentence } from './build_queue.js';
import { createGameMaps } from './gamemaps.js';
import { createMapBrowser } from './map_browser.js';
import { createSetupDialog, setupApi } from './setup.js';
import { ADDED_KINDS, addedMission, kindKey } from './missions.js';
import { createMissionsPanel } from './missions_panel.js';
import { createMapPicture } from './map_picture.js';
import { deletedEntry, spawnEditable, spawnKey, spawnNamed } from './spawns_view.js';
import { makeEffectMarker } from './effects_view.js';
import { viewHeight } from './effects_preview.js';
import { recordName, survivesClear } from './effects_rules.js';
import { createPrecache } from './precache.js';
import { createLibraryBrowser } from './library.js';
import { api as prefabApi, createPrefabBrowser } from './prefabs.js';
import { emptyPrefabScene, orderedWrites } from './prefab_document.js';
import { MADE_KINDS, cloneBlasts, optionsOf, stateOfRoot } from './piece_records.js';
import { activeMapId, allRoots, areaBindings, areaShown, askedPick, assigning, boxesShown, builder, builderMode,
         buildingMeta, buildings, buildingsVersion, chooseToken, cleared, clearKeepsOutside, clipboard, copySerial,
         data, derivedCopies, donorHashes, effectMarkers, effectRoots, effectsDirty, effectsOn, effectTemplates,
         eventMemo, families, foreignEffects, geometryCache, groupIndex, groups, handleDefs, hintTimer, landingZones,
         lastBuild, lastLightSync, leaving, library, libraryRecords, lightDrag, lighting, lightRadius, lightRoots,
         lightsDirty, lightsOn, lightsShown, likenessCount, likenessOn, likenessThin, liveCache, loadErrorCount,
         mergedBuildings, missionIndex, missionMoves, missionPickValue, nextChooseToken, nextCopySerial, normalEffects,
         normalLights, normalSpawns, ownPicked, ownSet, pickBox, pickDrag, pickedEffect, pickedSpawn, pickedZone,
         pickHits, pickTool, pieces, placing, playStatus, pointer, prefabParameter, prefabTab, project, projectMissions,
         projectPicture, projectSpawnRules, reachNow, reachShown, roots, selected, setActiveMapId, setAreaBindings,
         setAreaShown, setAskedPick, setAssigning, setBoxesShownValue, setCleared, setClearKeepsOutside, setClipboard,
         setData, setEffectsDirty, setEffectsOn, setEventMemo, setFamilies, setGroups, setHintTimer, setLandingRead,
         setLandingZones, setLastLightSync, setLeaving, setLibrary, setLighting, setLightRadius, setLightsDirty,
         setLightsOn, setLightsShownValue, setLiveCache, setLoadErrorCount, setLooksReady, setMergedBuildings,
         setMissionIndex, setMissionPickValue, setNormalEffectsValue, setNormalLightsValue, setNormalSpawnsValue,
         setOwnPickedValue, setPickBoxValue, setPickedEffect, setPickedSpawnValue, setPickedZone, setPickToolValue,
         setPieces, setPlacing, setPointer, setPrefabTab, setProjectMissions, setProjectPicture, setProjectSpawnRules,
         setReachKey, setReachShown, setSelected, setSpawnFilters, setSpawnRulesData, setSpawnsOn, setSpawnZonePick,
         setStageValue, setStreamSet, setTipDirty, setZonesOn, soloOn, spawnEntriesNow, spawnFilters, spawnLayerReady,
         spawnPlacing, spawnRulesData, spawnsOn, spawnZonePick, stage, streamSet, tipDirty, volumeDrag, volumeRoots,
         volumesOn, volumeTool, wavePlayer, zonePlacing, zonesOn } from './editor_state.js';
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
import { anyModal, holdModals, releaseAfterChange } from './modal.js';
import { call } from './api.js';
import { recall, remember } from './storage.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createMapLighting, withLocalLights } from './lighting.js';
import { makeMarker, paintMarker, scaleMarker, valuesOf } from './lights_view.js';
import { visibleBounds, footprintOf, tileGridAround, focusBounds, interiorPlanes, tileGridOf, floorTilesOverlay } from './view_layout.js';
import { ladderEnds, addedFloors } from './ladders.js';
import { COVER_KIND, COVER_MATERIAL, coverBox, coverFaces, coverFrame, coverGameWords, coverSightWords, coverTiles, coverMaterial, coverMeshId, coverMeshRecord, coverScene, coverStart,
         coverWords, floorStart, isBlocker, isFloor, lengthWords, normalCover, resizedCover, retyped, sizeWords } from './cover.js';
import { gridMove } from './poserule.js';
import { LEVEL, QUARTER, TILE } from './constants.js';
import { WALL, WALL_LOOKS, OPENING as GAP, drawnWall, flippedWall, movedOpening, openingParts, openingPlay, openingWords, playWords,
         raisedWall, resizedWall, reshuffled, shiftedLocation, sortedOpenings, storeysOf, toolWall, wallTop, wallWords, withOpening,
         withoutOpening, withStoreys, wallJoins, joinWords, drawnRoom, wallSpec, storeyWords, storeysInLook, openingsInLook,
         steppedStoreys,
         SLAB_LOOKS, SLAB, slabTiles, drawnSlab, resizedSlab, withHole, withoutHole, movedHole, reshuffledSlab, holeWords, slabWords,
         toolSlab, slabLookOf, roomRoof, madeWallShape, madeSlabShape, madeBounds, madeWallNumbers, madeSlabNumbers, slabBounds,
         blastQuery } from './walls.js';
import { loadLooks, catalogued, entryForPiece, lookFromEntry, lookTags, lookKey, DONOR_VERSION } from './looks.js';
import { createLookPicker } from './look_picker.js';
import { GROUND, GROUND_LOOKS, anotherRock, drawnGround, groundBox as groundShapeBox, groundLookOf, groundWords as groundShapeWords, raisedGround,
         resizedGround, slopeOf, slopeWords, toolGround, turnedGround, versionedGround, POINTS_VERSION, movedPoint, resetRock, ROCK,
         madeGroundShape, madeGroundNumbers, groundBounds } from './ground.js';
import { buildingWithFloor, classifyFloors, copyFloors, floorAt, floorIndex, floorStamps, floorUnder, levelHeight,
         ownedFloors, stampSignature, storeyHeight, worldBox, touchedFloors, ruleListing, floorsOf, sourceFloorMatch,
         cursorStoreys, carriedListing, floorMapOf, LISTED_CLASSES } from './floors.js';

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
// (The map's size as the project sets it, the cleared map, its landing zones, missions, picture and spawn rules, and
// the buildings: editor_state.js.) The install's landing lines for the map (GET landing-lines.json) and its kind come
// with the map: 'lwr' or 'longwar' (Long War), 'ew' (plain Enemy Within), or null, a game the editor doesn't know (none
// set, or the read failed: `failed` says why), a state of its own and not Long War (review finding 31). (That read,
// which a project waits for, landingRead: editor_state.js.)
let landingLines = { kind: null, lines: [] };
// allBuildings is what the floors code reads: the map's as exported where unchanged (their saved listings), the
// project's and the changed ones of the map by their boxes (worked out once for each state of the buildings:
// mergedBuildings, editor_state.js).
const PROJECT_BUILDING = 'project:';
function allBuildings() {
  if (!mergedBuildings) {
    const edits = mapEdits();
    setMergedBuildings([...(data?.buildings ?? []).filter(b => !edits.exportIds.has(b.id) && !(cleared && !mapEditable(b))),
      ...buildings.filter(b => !buildingMeta.get(b.id)?.map || edits.changed.has(b.id))
        .map(b => ({ id: PROJECT_BUILDING + b.id, name: b.name || 'Building', project: b, floors: floorsOf(b), map: buildingMeta.get(b.id)?.map ?? null }))]);
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
  setFamilies(table); assemblyIndex = new Map();
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
// (the Map lighting mode, lighting, and the pieces that could not be drawn, loadErrorCount: editor_state.js)
let cachePrefix='/cache/', mapCatalogue=null, mapBrowser=null;
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
// a panel section's text with its how-to notes shown (the test hooks read it)
function sectionText(id) {
  const box = $(id);
  if (box.hidden) return null;
  const had = box.classList.contains('showhow');
  box.classList.add('showhow');
  const words = box.innerText;
  box.classList.toggle('showhow', had);
  return words;
}
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
  if (id) setOwnPickedValue(null);
  if (!add && !keep) ownSet.clear();
  setSelected(id);
  { const was = pickedEffect; setPickedEffect(effectRoots.has(id) ? id : null); if (was !== pickedEffect) setEffectsDirty(true); }     // (one that starts off is drawn while it is picked)
  const root = roots.get(id) ?? lightRoots.get(id) ?? volumeRoots.get(id) ?? effectRoots.get(id);
  $('inspector').hidden = !root || Boolean(root.userData.volume);
  $('rail').classList.toggle('idle', !root);
  $('lightBox').hidden = !root?.userData.light;
  $('coverBox').hidden = !root?.userData.source?.cover;
  $('wallBox').hidden = !isMadeWall(root?.userData.source);
  $('slabBox').hidden = !isMadeSlab(root?.userData.source);
  $('groundBox').hidden = !isMadeGround(root?.userData.source);
  $('pieceBreakBox').hidden = !mapBreakable(root?.userData.source);
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
  if (isMadeSlab(obj)) slabPanel(root);
  if (isMadeGround(obj)) groundPanel(root);
  if (mapBreakable(obj)) breakRow('piece', { blasts: root.userData.blasts, breaksFurther: root.userData.breaksFurther }, obj.keepsPieces);
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
    chip.onclick = () => { setAreaShown(true); remember(AREA_SHOWN, '1'); setLightsShown(true); };
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
    chip.onclick = () => { setAreaShown(true); remember(AREA_SHOWN, '1'); setLightsShown(true); select(unsettled[0].userData.source.id); };
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
// [class, flags record] a piece's flags are planned on: its own, or for a wall, floor or ground made from numbers what
// the Build makes of its donor's (piece_flags.js made: collision of its own; a ground shape on a static mesh actor is
// made a level piece that collides, the user, 19 November 2026: flags on made pieces).
function flagSource(o) {
  const kind = o.added?.generated?.kind;
  return kind && o.pieceFlags ? madeFlags(flagContract(), o.actorClass, o.pieceFlags, kind) : [o.actorClass, o.pieceFlags];
}
// One actor's flags as the project has them: its settings, its request, what the request does, and each role after it
// with its limits (a low piece's from what is drawn of it where it stands: piece_flags.js lowPiece).
function flagView(t) {
  const c = flagContract(), [cls, pf] = flagSource(t.source), { raw, assumed } = flagRaw(pf);
  const request = t.roots[0]?.userData.flags ?? {};
  const plan = planFlags(c, cls, raw, request, assumed);
  const written = new Set(plan.writes.map(([k]) => k));
  const boxes = t.roots.map(r => boxOf(r)).filter(Boolean);
  const box = boxes.length ? boxes.reduce((a, b) => a.map((v, k) => (k % 2 ? Math.max(v, b[k]) : Math.min(v, b[k])))) : null;
  const roles = flagRoles(c, cls, { ...raw, ...Object.fromEntries(plan.writes) },
                          { collides: pf.collides, bodySetup: pf.bodySetup, assumed: assumed.filter(k => !written.has(k)),
                            low: lowPiece(c, box, tileCorner()?.[2]) });
  return { cls, collides: pf.collides, raw, assumed, request, plan, roles };
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
  const rows = $('flagsRows'), whyLine = $('flagsWhy');
  rows.replaceChildren();
  const showWhy = label => { whyLine.textContent = label?.dataset.why ? `${label.dataset.name}: ${label.dataset.why}` : whyLine.dataset.rest; };
  rows.onmouseleave = () => showWhy(null);
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
    const why = { textContent: '' };
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
      if (without) notes.push(`${eligible.length} of ${usable.length} pieces: ${plural(without, 'piece')} ${without === 1 ? 'has' : 'have'} no such setting (${[...new Set(usable.filter(t => !eligible.includes(t)).map(t => views.get(t.key).cls))].join(', ')})`);
      if (eligible.length > 1 && states.includes('partial')) notes.push('partly on: a prop\'s pathing gate passes it by in the sweeps, not in the occupancy step');
      why.textContent = flagSentences(notes);
    }
    input.title = `${c?.labels[role] ?? role}: click to turn it ${states.length && states.every(x => x === 'on') ? 'off' : 'on'} for ${eligible.length === 1 ? 'this piece' : `these ${eligible.length} pieces`}`;
    input.onchange = () => flagClick(role);
    // what limits the row, or why it is greyed: said in the one line under the rows while the pointer or the focus is on it
    label.dataset.name = c?.labels[role] ?? role;
    label.dataset.why = why.textContent;
    if (why.textContent) {
      label.classList.add('haswhy');
      label.title = why.textContent;
      label.insertAdjacentHTML('beforeend', '<svg class="i whymark" aria-hidden="true"><use href="#i-info"/></svg>');
    }
    label.onmouseenter = () => showWhy(label);
    input.onfocus = () => showWhy(label);
    rows.append(label);
  }
  whyLine.dataset.rest = rows.querySelector('.haswhy') ? 'Point at a marked flag for what limits it.' : '';
  showWhy(null);
  const changedRoles = rows.querySelectorAll('.changed').length;
  $('flagsCount').textContent = [changedRoles ? `${changedRoles} changed` : usable.length ? 'as the map has them' : 'not available',
    all.length > 1 ? plural(usable.length, 'piece') : ''].filter(Boolean).join(' · ');
  $('flagsCount').classList.toggle('changed', changedRoles > 0);
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
    const p = planFlags(c, v.cls, v.raw, request, v.assumed);
    const open = Object.keys(p.conflicts);
    if (open.length) { conflicts.set(t.key, open); continue; }
    const n = normalizeFlags(c, v.cls, v.raw, request, v.assumed, v.collides);
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
  $('flagsBox').open = true;
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
    twin.textContent = kindText; twin.title = button.title; twin.disabled = button.disabled; };
  let kindText = 'Select all';
  if (!seeds.size) {
    mirror();
    button.disabled = true; $('editKindCount').textContent = '';
    button.title = 'Select every piece with the same mesh as the one selected, or every effect of the same particle system, every sound of the same wave, every lens flare of the same template (a light, a cover block, a hidden or streamed piece has none to match)';
    return;
  }
  const found = kindMatches(seeds), picked = new Set(gizmo.picks().ids);
  const what = seeds.size === 1 ? [...seeds.values()][0] : `of these ${seeds.size} kinds`;
  kindText = `Select all${found.box ? ' in box' : ''} (${found.actors})`;
  $('editKindCount').textContent = String(found.actors);
  button.disabled = !found.roots.length || (found.roots.every(r => picked.has(r.userData.source.id)) && found.roots.length === picked.size);
  button.title = found.effects && found.effects === found.roots.length
    ? `Select all ${what}: every drawn effect of the same particle system, every sound of the same wave and every lens flare of the same template ${found.box ? 'inside the box' : 'in the map'}: ${kindCount(found)} (${[...seeds.values()].join(', ')}). Shift+click adds them to the selection.`
    : `Select all ${what}: every drawn piece ${seeds.size === 1 ? 'with this mesh' : 'with one of these meshes'} ${found.box ? 'whose middle is inside the box' : 'in the map'}: `
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
// end has floor only by a piece of the project. The floor is counted as the compiler's ladder check counts it
// (compiler.py added_floors, ladder_ends; review finding 34): a piece whose flags make it no floor gives none, and the
// tiles of the map's own pieces made no floor, moved or deleted are taken out (compiler floor_now);
// one of the map's own pieces made floor where it stands gives floor; a grown grid's new levels count.
let floorSet = null, ladderChip = null, gridChip = null;
function ladderNow(root) {
  const o = root?.userData.source;
  if (!o || o.actorClass !== 'XComLadder' || isStream(o) || !data.tileGrid || !data.tactical?.floorTiles) return null;
  floorSet ??= new Set(data.tactical.floorTiles.map(f => f.tile.join(',')));
  const boxes = [], off = new Set(), gone = new Set();
  for (const r of roots.values()) {
    const s = r.userData.source;
    if (isStream(s) || s.actorClass === 'XComLadder') continue;
    if (!s.added && (r.userData.deleted || r.userData.edit)) gone.add(s.actor);
    if (r.userData.deleted) continue;
    const floor = floorPlan(r);
    if (!s.added && !r.userData.edit) {
      // the map's own piece where it stands: its flags may take its floor away, or give it floor
      if (floor?.before === 'on' && floor.after === 'off') off.add(s.actor);
      else if (floor?.after === 'on' && floor.before !== 'on') boxes.push(boxOf(r));
      continue;
    }
    // a cover block is no floor, bar the invisible floor, which is made to carry one (EXP-32); a copy whose flags make
    // it no floor (and that collides) gives none
    if ((s.cover && s.cover.type !== 'floor') || (floor?.collides && floor.after === 'off')) continue;
    boxes.push(boxOf(r));
  }
  const dims = data.tileGrid.dimensions, own = ownSize()?.dims;
  const added = addedFloors(boxes, data.tileGrid.origin, dims && [dims[0], dims[1], Math.max(dims[2], own?.[2] ?? 0)]);
  const floors = off.size || gone.size ? new Set(data.tactical.floorTiles.filter(f => !off.has(f.actor) && !gone.has(f.actor)).map(f => f.tile.join(',')))
    : floorSet;
  const pose = placedPose(o, root.matrix);
  const ends = ladderEnds(pose.location, pose.rotation, data.meshes[o.mesh].bounds[5], tileCorner(), new Set([...floors, ...added]));
  ends.newFloor = ends.climbs && [ends.footTile, ends.linkedTop].some(t => !floors.has(t.join(',')));
  return ends;
}
// A piece's Floor before and after its flags (piece_flags.js plan, as the compiler's flag_plan), with whether it
// collides, or null when it has no flags request (or they can't be planned).
function floorPlan(r) {
  const s = r.userData.source, c = flagContract();
  if (!c || !r.userData.flags || !s.pieceFlags) return null;
  const [cls, pf] = flagSource(s), { raw, assumed } = flagRaw(pf), p = planFlags(c, cls, raw, r.userData.flags, assumed);
  if (Object.keys(p.conflicts).length) return null;
  return { before: p.before.floor, after: p.after.floor, collides: s.added?.generated?.kind === 'ground' || s.pieceFlags.collides !== false };
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
    mark.position.set(ox + (tile[0] + 0.5) * TILE, oz + tile[2] * LEVEL + 3, oy + (tile[1] + 0.5) * TILE);
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
  setEffectsDirty(true);     // (the Effects view's markers follow the pieces that carry them)
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
  flagsPanel(); kindButton();
  // (a building's box is in no group and is not aligned)
  if (volumeRoots.has(selected)) { $('groupBox').hidden = true; $('alignBox').hidden = true; targetHelper.visible = false; }
  else { groupPanel(); alignPanel(); }
  roomPanel();
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
  const across = r.maxTiles * TILE, flat = r.flat?.includes(c.type);
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
  // (one map per page: the answer is always the open map's)
  fetch(`/maps/${encodeURIComponent(activeMapId)}/collision.json`).then(r => (r.ok ? r.json() : null)).catch(() => null).then(reply => {
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
// A cover piece against the tiles round it (cover.js coverTiles, the game's tile rebuild as research/native/cover-build.md
// has it): its frame in the world, the tile grid's corner and the cover recipe.
const coverTilesOf = root => coverTiles(root.userData.source.cover, coverFrame(root),
  [...(gridOrigin() ?? [0, 0]), data?.tileGrid?.origin?.[2] ?? 0], coverRecipe());
/** An invisible floor's tiles' centres on its top, [x, y, z] game units each: the map's tiles whose centre it covers,
 *  where the game looks for a tile's floor (one line straight down through the centre). */
function floorCentres(root) {
  const { tiles, top } = coverTilesOf(root);
  return tiles.filter(t => t.carried).map(t => [...t.centre, top]);
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
  const g = coverTilesOf(root);
  $('coverSight').textContent = coverSightWords(c, g);
  $('coverNote').textContent = coverGameWords(c, g);
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
      twins.set(v.building, { id: newBuildingId(), meta: { name, kind: meta.kind ?? 'building' } });
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
  setClipboard(clip);
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
  if (clip.gridLocked) return [px + Math.round((x - px) / TILE) * TILE, py + Math.round((y - py) / TILE) * TILE, clip.pivot[2] + Math.round((z - clip.pivot[2]) / LEVEL) * LEVEL];
  if (snapMode === 'fine') [x, y] = [Math.round(x / 24) * 24, Math.round(y / 24) * 24];
  else if (snapMode === 'tile') [x, y] = [px + Math.round((x - px) / TILE) * TILE, py + Math.round((y - py) / TILE) * TILE];
  if (clip.floor != null && levelSnap)
    z = levelHeight(clip.pivot[2], clip.floor, chosenStorey(x, y)?.z ?? floorUnder(liveFloorIndex(), { ...tileGridOf(data), origin: tileCorner() ?? tileGridOf(data).origin }, [x, y, z]).z);
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
let ghostDirty = false;   // (what is being placed, placing, and pieces: editor_state.js)
// The preview is drawn twice: plainly where it is in view, faintly where walls or roofs hide it.
const ghostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.45, depthWrite: false });
const ghostHidden = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.15, depthWrite: false, depthTest: false });
// Pieces of other maps (library.js, tools/viewer/library.py). A piece's record, read on first use, joins the page's
// tables: its meshes, materials and textures under their own keys (lib-<map>-…, with the folder they are served
// from), and its components as templates a copy is made of, as the map's own pieces are. A template names its home
// map (`foreign`), and so does every copy of it; an added record's `from` is the piece in that map.
const foreignTemplates = new Map();     // (the records read, libraryRecords: editor_state.js)
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
const fetchedEffects = new Map();     // (effectTemplates, foreignEffects: editor_state.js)
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
let libraryScope = 'map';     // (the All maps library, library, and chooseToken: editor_state.js)
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
  const token = nextChooseToken();
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
  nextChooseToken();
  if (!entry) { stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopWallDrawing(); return; }
  stopWallDrawing();
  if (entry.zone) { stopPlacing(); stopSpawnPlacing(); startZonePlacing(); return; }      // the Landing zones kind
  if (entry.spawnAdd) { stopPlacing(); stopZonePlacing(); startSpawnPlacing(entry.spawnAdd); return; }      // Spawn points
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
  setClipboard({ entries: entryParts(entry), pivot: entry.cover ? [at[0] + 48, at[1] + 48, at[2]] : [...at],
                pivotIndex: entry.pivotIndex, name: entry.name, groundFloor: isFloor(entry.cover) });
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
  setPlacing({ clip, entry, ghost, turns: 0 }); ghostDirty = true;
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
// (`only`: those pieces, not the selection, whose locked groups bring their whole groups: a look change's)
function deleteNow(quiet = false, only = null) {
  const targets = only ?? copyable(), boxes = only ? [] : selectedBoxes();
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
      refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection([]); sceneChanged();
    },
    undo: () => {
      addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects);
      for (const r of [...originals, ...originalLights, ...originalEffects, ...boxes]) r.userData.deleted = false;
      refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection(before.ids, before.active); sceneChanged();
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

// Reset all: the map as exported. Added pieces go, deleted ones return, moved ones go home, broken ones are mended,
// groups end, and the grid, the landing zones and the clear mark are the map's own again; one undo step.
function resetAll() {
  const all = [...roots.values()], lights = [...lightRoots.values()];
  const added = all.filter(r => r.userData.source.added), deleted = [...all, ...lights].filter(r => r.userData.deleted);
  const flagged = all.filter(r => !r.userData.source.added && r.userData.flags), flagsBefore = flagged.map(r => r.userData.flags);
  // the map's own pieces broken (Break, E6) are mended: their blasts and Breaks further in battle go (review finding 28)
  const broken = all.filter(r => !r.userData.source.added && r.userData.blasts?.length);
  const brokenBefore = broken.map(r => ({ blasts: cloneBlasts(r.userData.blasts), further: Boolean(r.userData.breaksFurther) }));
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
  if (!added.length && !deleted.length && !moved.length && !flagged.length && !broken.length && !groups.size && !addedLights.length && !changed.length && !areaBindings.size && !restore.count
      && !addedEffects.length && !stays.length && !valued.length
      && !ownBoxes.length && !stage && !landingZones && !cleared && !projectMissions && !missionMoves.size && !projectSpawnRules) return;
  const before = moved.map(r => r.matrix.clone()), home = moved.map(r => baseMatrix(r)), picks = gizmo.picks();
  // the map's own grid, landing zones and no clear mark
  const map = { stage, zones: landingZones ? landingZones.map(z => ({ ...z })) : null, cleared, keeps: clearKeepsOutside,
                missions: projectMissions ? projectMissions.map(e => ({ ...e })) : null, moves: new Map(missionMoves),
                rules: projectSpawnRules };
  const mapState = m => {
    setCleared(m.cleared); setClearKeepsOutside(m.keeps); setLandingZones(m.zones ? m.zones.map(z => ({ ...z })) : null);
    setProjectMissions(m.missions ? m.missions.map(e => ({ ...e })) : null);
    setMissionMoves(new Map(m.moves ?? []));
    setProjectSpawnRules(m.rules ?? null); syncSpawnRule();
    setMergedBuildings(null); setPickedZone(null); setStage(m.stage); clearedChanged(); refreshLandingZones(); refreshMissionPicker();
  };
  const groupsBefore = cloneGroups(), valuesBefore = changed.map(r => ({ ...r.userData.values })), bindingsBefore = new Map(areaBindings);
  gizmo.record({
    redo: () => {
      for (const r of flagged) r.userData.flags = null;
      for (const r of broken) { r.userData.blasts = null; r.userData.breaksFurther = false; drawBroken(r); }
      removeRoots(added); removeLightRoots(addedLights); removeEffectRoots(addedEffects); for (const r of stays) r.userData.stays = false;
      for (const r of valued) r.userData.values = null;
      for (const r of deleted) r.userData.deleted = false; gizmo.applyMatrices(moved, home);
      for (const r of changed) setLightValues(r, r.userData.baseValues);
      restore.redo();
      for (const r of ownBoxes) r.userData.deleted = true;
      mapState({ stage: null, zones: null, cleared: false, keeps: false, missions: null, rules: null });
      setAreaBindings(new Map()); setGroups(new Map()); refreshLightVisibility(); setLightsDirty(true); sceneChanged();
    },
    undo: () => {
      flagged.forEach((r, k) => { r.userData.flags = flagsBefore[k]; });
      broken.forEach((r, k) => { r.userData.blasts = cloneBlasts(brokenBefore[k].blasts); r.userData.breaksFurther = brokenBefore[k].further; drawBroken(r); });
      addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects); for (const r of stays) r.userData.stays = true;
      valued.forEach((r, k) => { r.userData.values = fxValues[k]; });
      for (const r of deleted) r.userData.deleted = true; gizmo.applyMatrices(moved, before);
      changed.forEach((r, k) => setLightValues(r, valuesBefore[k]));
      restore.undo();
      for (const r of ownBoxes) r.userData.deleted = false;
      mapState(map);
      setAreaBindings(new Map(bindingsBefore)); setGroups(cloneGroups(groupsBefore)); refreshLightVisibility(); setLightsDirty(true);
      gizmo.setSelection(picks.ids, picks.active); sceneChanged();
    },
  });
}
// Groups' pieces on the map now (deleted ones left out): member key -> its roots. Remade after any change of pieces.
// (that cache, liveCache: editor_state.js)
function liveMembers() {
  if (!liveCache) {
    setLiveCache(new Map());
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
const BREAK_TOGETHER_TITLE = $('groupBreakRow').title;
function groupPanel() {
  const box = $('groupBox'), { kind, group: g, count, groups: wholeGroups } = selectionGroup();
  box.hidden = !kind;
  groupChip.hidden = !g;
  highlight.material.color.set(g && kind === 'whole' ? 0xe8bd5c : 0x96e5d7);
  if (!kind) return;
  const n = g ? liveKeys(g).length : count;
  box.classList.toggle('locked', Boolean(g));
  $('groupMake').hidden = kind !== 'new';
  const adding = kind === 'new' ? groupToAddTo() : null;
  $('groupAdd').hidden = !adding;
  $('groupDissolve').hidden = $('groupBreakRow').hidden = !g;
  if (!g) {
    $('groupTitle').textContent = 'Not grouped';
    $('groupText').textContent = wholeGroups
      ? `Group these ${n} (${plural(wholeGroups, 'group')}${n > wholeGroups ? ` and ${plural(n - wholeGroups, 'piece')}` : ''}) to select and move them as one. The groups stay as they are inside the new one.`
      : `Group these ${n} pieces to select and move them as one, and to give them group options.`;
    if (adding) $('groupText').textContent += ` Add to group puts the ${keyWords(adding.loose)} in the group instead, which keeps its options.`;
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
  note.classList.toggle('how', !can);
  $('groupBreakRow').title = !can ? 'Needs two breakable pieces (props) of the group\'s own, or one and a cover block or a made wall' : BREAK_TOGETHER_TITLE;
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
// Add to group (the user, 19 November 2026): a selection of one whole group and pieces (lights, buildings) that are in
// no group puts those in that group, which keeps its options, rather than making a new group of them all. Gives
// { group, loose (their member keys), records } when the selection is so, else null.
function groupToAddTo() {
  const records = new Map(groupables().map(r => [memberOf(r.userData.source), memberRecord(r.userData.source)]));
  const units = [...selectionUnits(new Set(records.keys()))];
  const whole = units.filter(u => u.startsWith('group|')), loose = units.filter(u => !u.startsWith('group|'));
  const group = whole.length === 1 ? groups.get(whole[0].slice(6)) : null;
  return group && loose.length && loose.every(k => !groupIndex.get(k)) ? { group, loose, records } : null;
}
function addToGroup() {
  const add = groupToAddTo();
  if (!add) { flashHint('Select one group and pieces that are in no group to add them to it'); return; }
  const words = keyWords(add.loose);
  changeGroups(next => { const g = next.get(add.group.id); for (const k of add.loose) g.members.set(k, add.records.get(k)); },
    `Added ${words} to the group · ${add.loose.length === 1 ? 'it selects and moves' : 'they select and move'} with it`);
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
const { addedLight, addedLightOf, addLightRoots, applyLightRecord, areaOwner, assignOwner, buildLights, changeLight,
        clearLightEdits, commitColour, commitLightField, endLightDrag, handlesNear, hoverHandle, lightClip, lightEdited,
        lightEntries, lightPanel, lightPose, lightRecords, lightsBlocked, lightsChanged, lightShapes, lightSource,
        lightState, lightViewOnly, moveLightDrag, ownerRoot, pickLight, recipeLight, refreshLightShapes,
        refreshLightVisibility, removeLightRoots, scaleMarkers, setBinding, setLightsShown, setLightValues,
        setNormalLights, setSolo, showLight, startLightDrag, updateLightHandles, valuesEdited, warnLights,
        withStorableCone } = createLightsWiring({
  $, actorPose, baseMatrix, camera, copyable, copyText, editChanged, field, flashHint, gizmo, HANDLE_PICK, highlight,
  isStream, ladderMarks, lightLayer, pickables, PL, plural, pointOutside, projector, renderer, restingHint, select,
  short, showPop, sun, syncLights, text, world,
  // (made further down: called through, since they are not made yet while this runs)
  applyLighting: () => applyLighting(), banner: (message, actions, options) => banner(message, actions, options),
  // (made with the Spawns, Landing zones and Buildings views, further down: called through)
  setSpawnsShown: on => setSpawnsShown(on), setVolumesShown: on => setVolumesShown(on),
  setZonesShown: on => setZonesShown(on), stopPickBox: () => stopPickBox(),
  // (made with the Effects view, further down: called through)
  drawEffectShape: () => drawEffectShape(), effectNow: (root, r) => effectNow(root, r), effectsShown: () => effectsShown(),
  effectValuesEditable: root => effectValuesEditable(root), setEffectsShown: on => setEffectsShown(on),
  setEffectValues: (root, values) => setEffectValues(root, values) });
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
  cloneGroups, coverOf, coverVersion, drawBroken, editChanged, gizmo, lightState, liveMembers, loadForeignTemplates,
  mapBreakable, memberOf, movedMatrix, ownSize, plural, projectNote, savedBuildings, sceneChanged, setStage, short,
  sourceKey, templateFor,
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
  clearedChanged: () => clearedChanged(), setBuildings: next => setBuildings(next) });
// The document session (document_session.js): opening, saving and leaving a project, its drafts kept for recovery
// and offered back, and the banner under the header.
const { banner, discardAndGo, discardDraft, draftWords, dropAdopted, ensureSavedFor, goTo, keepRecovery, loadProject,
        openProject, projectChanged, saveProject } = createDocumentSession({
  $, SESSION, applyState, builder, camera, controls, dirty, documentWrites, editChanged, editState, flashHint, gizmo,
  loadingState, ownSize, plural, projectNote, projectsAvailable, saveState, showFileDialog, text, touchRecent,
  unsavedDocument,
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
const { applyPrefabDocument, builderBounds, builderDocument, builderKey, builderRecords, builderTitle, openPrefabDocument,
        physicalBox, problemsPaint, recoverPrefabSources, refreshBuilder, saveBuilder } = createBuilderSession({
  $, SESSION, actorPose, addRoots, addedObject, applyState, banner, boxOf, buildRoot, controls, dirty, discardAndGo, discardDraft,
  documentWrites, draftWords, dropAdopted, editChanged, editState, flashHint, frame, gizmo, gridNow, gridOrigin, isStream,
  libraryTemplate, lightPose, loadingState, movedMatrix, plural, projectChanged, recipeOf, removeRoots, rootName, sceneChanged,
  selectActors, short, snapshot, templateFor, text, world,
  // (made with the loading overlay, further down: called through, since it is not made yet while this runs)
  openingProgress: name => openingProgress(name),
  // (made with the Buildings view, further down: called through, since it is not made yet while this runs)
  volumeBox: root => volumeBox(root),
  // (made with prefabs saved and placed just below, which is given the builder's records and save: called through)
  prefabRecords: options => prefabRecords(options), showPrefabDialog: whole => showPrefabDialog(whole) });
// Prefabs saved and placed (prefab_place.js): the Save as prefab dialog, the save, and a prefab of the Add panel's
// Prefabs tab placed as a paste is.
const { choosePrefab, drawPrefabPictures, prefabClip, prefabPlacementProblem, prefabRecords, savePrefab,
        showPrefabDialog } = createPrefabPlace({
  $, BUSY_PIECES, PL, actorPose, assetUrl, banner, boxMatrix, builderRecords, busy, busyPaint, busyStart, copyable, coverOf,
  coverVersion, effectTemplate, flashHint, fromOf, ghostEdges, ghostLine, gltfLoader, gridNow, groupTree,
  isForeignTarget, isStream, libraryTemplate, lightPose, lightsBlocked, linkOf, madeShape, mapChain, matrixBox, memberOf,
  movedMatrix, nextFrame, physicalBox, plural, previewGroup, readEffectRecords, readLibraryRecords, recipeLight, recordId,
  rootName, saveBuilder, selectionGroup, short, snapshot, startPlacing, stopPlacing, templateFor, text, track,
  withStorableCone,
  // (made with the Effects view, further down: called through, since it is not made yet while this runs)
  effectViewOnly: (o, cap) => effectViewOnly(o, cap) });
const mapLabel = id => mapCatalogue?.maps.find(m => m.id === id)?.label ?? id ?? '';
// Build and Play in game (build_play.js): Build's panel and the window that follows a build, Play in game with its
// dialog and the Game menu's Installs, the header's Build and Play buttons, the test squad's line, the prefab
// builder's Test in game and the build queue's chip.
const { followBuild, followQueueForProject, landHere, openBuild, openPrefabTest, playInGame, prefabTest, refreshInstalls,
        refreshSquadLine, renderPlayItems, renderQueueChip, setLastBuild } = createBuildPlay({
  $, bakeNote, banner, builder, builderDocument, builderRecords, dirty, dragHint, flashHint, gizmo, headerMissions, mapLabel,
  needsPrepare, plural, projectsAvailable, saveProject, selectActors, short, showFileDialog, showPop, showPrepare, text,
  zonesNow,
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
async function texture(id, color = true, sampling = {channel:0,scale:[1,1]}) {
  if (!id || !data.textures[id]) return null;
  const key = `${id}:${color}:${JSON.stringify(sampling)}`;
  // (a texture that failed to load is asked for again by the next material that needs it: track)
  track(texturePromises, key, async () => {
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
  });
  return texturePromises.get(key);
}
// The plain material of a made piece with no look (B2): light grey, shaded by the lights, the floor's tile lines
// drawn on it (every 96 units from the tile grid's corner, both ways across the ground).
const PLAIN_MATERIAL = 'plain:made';
function plainMaterial() {
  const mat = withLocalLights(new THREE.MeshPhongMaterial({ color: 0xc3cbd0, specular: 0x161616, shininess: 8 }));
  const local = mat.onBeforeCompile, origin = gridOrigin() ?? [0, 0];
  mat.onBeforeCompile = (shader, r) => {
    local?.(shader, r);
    shader.uniforms.plainTileOrigin = { value: new THREE.Vector2(origin[0], origin[1]) };
    shader.fragmentShader = `uniform vec2 plainTileOrigin;\n${shader.fragmentShader}`.replace('#include <dithering_fragment>', `#include <dithering_fragment>
      vec2 plainTile = (vLocalWorld.xz - plainTileOrigin) / ${TILE.toFixed(1)};
      vec2 plainDist = abs(fract(plainTile + 0.5) - 0.5) * ${TILE.toFixed(1)};
      float plainWidth = max(0.6, length(fwidth(vLocalWorld.xz)) * 0.8);
      gl_FragColor.rgb *= 1.0 - 0.45 * (1.0 - smoothstep(0.0, plainWidth, min(plainDist.x, plainDist.y)));`);
  };
  mat.customProgramCacheKey = () => 'plain-made';
  return mat;
}
async function material(id,overrideTint=null) {
  if (id === PLAIN_MATERIAL) return plainMaterial();
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
const materialCache = new Map();     // (the meshes, geometryCache: editor_state.js)
// Spawned preview pieces (and copies of them) carry their own tint.
function materialKey(obj, id) {
  const tint = obj.provenance?.type === 'spawn' || obj.added?.tinted ? obj.tint : null;
  return [`${id}:${JSON.stringify(tint)}`, tint];
}
// The catch stops an early failure being reported as unhandled before its piece is reached, and drops the failed load,
// so the next piece that needs it asks again rather than failing for the page's life (review finding 29).
// Once loaded, a value can also be had at once with loaded(), for drawing in the middle of a frame.
const settled = new WeakMap();
function track(map, key, start) {
  if (map.has(key)) return;
  const promise = start();
  promise.then(v => settled.set(promise, v), () => { if (map.get(key) === promise) map.delete(key); });
  map.set(key, promise);
}
const loaded = (map, key) => settled.get(map.get(key));
// A drawn-only copy of some pieces (the placing preview, a piece-list thumbnail) from the loaded meshes and
// materials, or `override` for every part. It is never picked. parts: { source, matrix }; `frame` moves them all.
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
  let base;
  try { base = await geometryCache.get(obj.mesh); }
  catch (error) {
    // a made piece the server can't draw (a look it can't make here): its donor's own mesh, as numbers this page
    // doesn't draw are; the Build makes it all the same
    const made = data.meshes[obj.mesh];
    if (!made?.made || !made.fallback) throw error;
    if (!made.warned) { made.warned = true; flashHint(`${made.name}: the editor can't draw it in its look here, so it shows its donor; the Build makes it`); }
    obj.mesh = made.fallback.mesh; obj.materials = [...made.fallback.materials];
    track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[obj.mesh].url)));
    base = await geometryCache.get(obj.mesh);
  }
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
  root.userData.blasts = obj.initialBlasts ? cloneBlasts(obj.initialBlasts) : null;     // (E6) drawn without what they knock out
  root.userData.breaksFurther = Boolean(obj.initialBreaksFurther);
  if (root.userData.blasts) drawBroken(root);
  root.matrix.fromArray(obj.matrix); root.matrixAutoUpdate = false; root.matrixWorldNeedsUpdate = true;
  return root;
}
function addRoots(list) {
  setLiveCache(null);
  for (const root of list) {
    roots.set(root.userData.source.id, root); content.add(root); pickables.push(...root.userData.parts);
  }
}
// Removed roots keep their geometry: an undo puts the same objects back.
function removeRoots(list) {
  const parts = new Set(list.flatMap(root => root.userData.parts));
  setLiveCache(null);
  for (const root of list) { roots.delete(root.userData.source.id); content.remove(root); }
  pickables.splice(0, pickables.length, ...pickables.filter(p => !parts.has(p)));
}
// The piece's unedited matrix: as exported (for a copy, where it was placed).
function baseMatrix(root) {
  return new THREE.Matrix4().fromArray(root.userData.source.matrix);
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
// (the classes a building floor lists: floors.js LISTED_CLASSES)
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
// The map's size as the project sets it (Map menu, Map grid; prefab plan 5.11). The Build makes the map's tile
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
// The map's size can be set on any whole map (13 November), growing only while it is as it is, and any way, in any of
// the three, once it is cleared (Clear map plan, section 6). Whether this is the bare map a new map starts from
// (project.js STAGE_MAPS): the Build lays its ground over the new area.
const bareMap = () => STAGE_MAPS.includes(activeMapId);
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
  const [nx, ny, nz] = dims ?? own.dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
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
  setStageValue(dims ? tidyStage(next) : (next && validStage(next, own?.dims) && !cleared ? tidyStage(next) : null));
  if (!own) return;
  showGrid(dims);
  // a map grown as it is: the new area as a faint sheet, green where the Build lays the map's ground (where it is laid
  // as planes), grey where the project asked for none
  if (!dims || cleared) return;
  const [nx, ny] = dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [TILE, TILE];
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
// The cursor's floors on the grid as the project has it (floors.js cursorStoreys; the Build's shell.py), with the made
// floors' and roofs' own over their footprints (floors.js madeStoreys; the Build's made_cursors.py)
const madeSlabBoxes = () => [...roots.values()].filter(r => !r.userData.deleted && isMadeSlab(r.userData.source))
  .map(r => boxOf(r)).filter(Boolean).map(b => ({ box: [b[0], b[2], b[4], b[1], b[3], b[5]] }));
let storeysKept = null;
const storeysNow = () => {
  const own = ownSize()?.dims ?? null, slabs = madeSlabBoxes();
  const key = JSON.stringify([cleared, own, data?.tileGrid?.dimensions ?? null, slabs]);
  if (storeysKept?.data !== data || storeysKept.key !== key) storeysKept = { data, key, value: cursorStoreys(data, { cleared, own, slabs }) };
  return storeysKept.value;
};
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
  const step = (data.tileGrid.size ?? [TILE, TILE, LEVEL])[d.axis], rule = gridRule();
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
  const oz = data.tileGrid.origin[2], sz = data.tileGrid.size?.[2] ?? LEVEL, ground = groundHeight();
  const under = Math.max(0, Math.floor((ground - oz + 2) / sz));
  if (under >= levels) return `The ground is at ${Math.round(ground)}, above the grid's top: the grid needs ${under + 1} levels or more.`;
  return `The ground is at level ${under + 1} of ${levels}: ${under ? `${LEVEL_WORDS[under] ?? under} level${under === 1 ? '' : 's'} of the grid ${under === 1 ? 'is' : 'are'}` : 'no level of the grid is'} under it.`;
}
// The notes under a size, none of which blocks (warn, don't block): zones outside the grid, no room for LWR's pods
// (F-90), the ground above the grid
function sizeNotes([nx, ny, nz], zoneList = null) {
  const notes = [], [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
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
  const own = ownSize(), b = data.playableBounds, [ox, oy] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
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
  if (!projectsAvailable() || !ownSize()) { banner('Clear map is for a whole map, not a preview or the prefab builder.'); return; }
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
  const words = { Abduction: 'an abduction', TerrorSite: 'a terror site', 'Special/Bomb': lwrInstall() ? 'a bomb mission' : 'a bomb mission (on Long War only)', Crash: 'a UFO mission (with a UFO placed)' };
  const added = Object.keys(words).filter(k => !(k === 'Special/Bomb' && (plainEw() || baseHas(k))) && !brought.some(m => kindKey(m) === k)).map(k => words[k]);
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
      setAreaBindings(new Map()); setGroups(new Map());
      setCleared(true); setClearKeepsOutside(keepOutside); setMergedBuildings(null); setStage(next); clearedChanged();
      setProjectMissions(missionsCleared.map(e => ({ ...e }))); refreshMissionPicker();
      if (kept) { setLandingZones([{ ...kept }]); setPickedZone(null); refreshLandingZones(); }
      refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection([]); sceneChanged();
    },
    undo: () => {
      addRoots(plan.added); addLightRoots(plan.addedLights);
      setMissionMoves(new Map(spawnsBefore));
      for (const r of [...plan.originals, ...plan.originalLights, ...plan.boxes]) r.userData.deleted = false;
      setAreaBindings(new Map(bindingsBefore)); setGroups(cloneGroups(groupsBefore));
      setCleared(clearedBefore); setClearKeepsOutside(keepsBefore); setMergedBuildings(null); setStage(stageBefore); clearedChanged();
      setProjectMissions(missionsBefore ? missionsBefore.map(e => ({ ...e })) : null); refreshMissionPicker();
      if (kept) { setLandingZones(zonesBefore ? zonesBefore.map(z => ({ ...z })) : null); setPickedZone(null); refreshLandingZones(); }
      refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection(picks.ids, picks.active); sceneChanged();
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
// Which game is set (review finding 31): Long War, plain Enemy Within, or neither known, a state of its own
const lwrInstall = () => ['lwr', 'longwar'].includes(landingLines?.kind);
const plainEw = () => landingLines?.kind === 'ew';
const gameUnknownWhy = () => (landingLines?.kind ? null : landingLines?.failed
  ? `the editor couldn't read it: ${landingLines.failed}` : 'the settings name no game folder the editor recognises');
// whether a UFO building stands on the map: one of the project's, or one of the map's own that stays
const hasUfoBuilding = () => allBuildings().some(b => (b.project ? (b.project.kind ?? 'building') === 'ufo' : b.isUfo));
const baseHas = kind => (data?.missions ?? []).some(m => kindKey(m) === kind);
// A cleared map's missions: the header's when it is one of the first three kinds (its own record, else added), else
// the base map's abduction record, else an added abduction.
function clearedMissions() {
  const picked = (data?.missions ?? [])[missionIndex], key = picked ? kindKey(picked) : null;
  const addedPick = missionPickValue.startsWith('kind:') ? missionPickValue.slice(5) : null;
  if (['Abduction', 'TerrorSite', 'Special/Bomb'].includes(addedPick) && (addedPick !== 'Special/Bomb' || !plainEw())) return [{ kind: addedPick }];
  // (the base map's bomb is its own record, its objects standing where the original map has them until moved)
  if (picked && ['Abduction', 'TerrorSite', 'Special/Bomb'].includes(key)) return [{ record: missionIndex }];
  const abduction = (data?.missions ?? []).findIndex(m => kindKey(m) === 'Abduction');
  return abduction >= 0 ? [{ record: abduction }] : [{ kind: 'Abduction' }];
}
async function showMissions(asked = false) {
  showPop(null);
  if (!projectsAvailable() || !data || data.preview) return;
  if (!playStatus) await refreshInstalls();     // what is known of each kind played (the page asks at its start too)
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
    const unknown = k.lwr ? gameUnknownWhy() : null;
    rows.push({ entry, label: `${k.label} (added)`, checked: has({ kind }), words: '', ufo: k.ufo,
                detail: unknown ? `${k.needs} Which game is set isn't known (${unknown}), so the editor can't check that it is Long War.` : k.needs,
                disabled: k.lwr && plainEw() ? 'Long War only: plain Enemy Within would play the bomb where Slaughterhouse has it.'
                  : k.ufo && !hasUfoBuilding() ? 'Place a UFO prefab first: the mission needs a UFO building on the map.' : null });
  }
  missionsPanel.show({
    title: asked ? 'What is this map for?' : `Missions${project ? ` of ${project.doc.name}` : ''}`,
    note: asked ? 'The cleared map is played as the missions ticked here; the Build writes a record for each. Missions in the Map menu changes them later.'
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
    redo: () => { setProjectMissions(next ? next.map(e => ({ ...e })) : null); refreshMissionPicker(); projectChanged(); },
    undo: () => { setProjectMissions(before ? before.map(e => ({ ...e })) : null); refreshMissionPicker(); projectChanged(); },
  });
}
$('projectMissions').onclick = () => showMissions(false);
// The Map picture dialog (map_picture.js; LWR map packs plan, 4.2): the picture is kept by the server with the project
// and named in the project by its SHA-256, so the project's next save carries it (no undo step: the file is kept
// outside the edit history).
const mapPicture = createMapPicture({
  els: { root: $('mapPictureDialog'), form: $('mapPictureForm'), title: $('mapPictureTitle'), note: $('mapPictureNote'), drop: $('mapPictureDrop'),
         canvas: $('mapPictureCanvas'), empty: $('mapPictureEmpty'), file: $('mapPictureFile'), choose: $('mapPictureChoose'), take: $('mapPictureTake'),
         result: $('mapPictureResult'), resultNote: $('mapPictureResultNote'), status: $('mapPictureStatus'), use: $('mapPictureUse'),
         remove: $('mapPictureRemove'), close: $('mapPictureClose') },
  onUse: result => { setProjectPicture({ sha256: result.sha256 }); projectChanged(); flashHint('The map picture is set: save the project to keep it'); },
  onRemove: () => { setProjectPicture(null); projectChanged(); flashHint('The map picture is removed: save the project to keep it so'); },
  grabView,
});
// Take from the view (LWR map packs plan, 4.5): the 3D view as it is now, on a canvas of its own. The renderer keeps no
// drawing buffer, so a frame is drawn here and copied at once (as pieces.paintThumbs copies its pictures), with the
// editor's helpers hidden for that frame: everything in the world but the map's pieces, its lights and its effects'
// likenesses (the grids, the gizmos, the handles, the markers, the play area, the selection's outline), and the pieces
// the game never draws (cover blocks and invisible floors). The next frame draws them again.
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
$('projectPicture').onclick = () => {
  showPop(null);
  // the picture is kept with a saved project (by its id)
  if (!project) { banner('Save the project first: its map picture is kept with it.'); return; }
  mapPicture.show({ project: { id: project.doc.id, name: project.doc.name }, map: project.doc.source?.map ?? activeMapId, own: projectPicture?.sha256 ?? null });
};
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
  const [ox, oy] = data.tileGrid.origin, [nx, ny] = data.tileGrid.dimensions, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
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
  $, camera, controls, flashHint, floorStays, gizmo, groundAt, groundHeight, headerMissions, isStream, landingLayer,
  lightButton, movedMatrix, pick, plural, projectsAvailable, rayAt, renderer, restingHint, select, setLightsShown,
  short, text, tileCorner, world,
  // (made further down: called through, since they are not made yet while this runs)
  gameToView: p => gameToView(p), headerMission: () => headerMission(),
  numberField: (parent, label, value, options) => numberField(parent, label, value, options),
  pickZone: id => pickZone(id), setEffectsShown: on => setEffectsShown(on), setVolumesShown: on => setVolumesShown(on),
  setZonesShown: on => setZonesShown(on), stopPickBox: () => stopPickBox(),
  zoneHit: (clientX, clientY) => zoneHit(clientX, clientY), zoneState: () => zoneState() });

// The Effects view (effects_wiring.js): the map's effects, sounds and lens flares as roots, the view, the likeness,
// the panel with the Wave preview and the values, and the project's records of effects and sounds.
const { addedEffect, addedEffectOf, addEffectRoots, applyEffectRecord, buildEffects, clearEffectEdits, drawEffectShape,
        drawLikenessPane, effectAt, effectEdited, effectFollows, effectLayer, effectNow, effectPanel, effectPicture,
        effectShapes, effectSource, effectsShown, effectState, effectTip, effectValuesEditable, effectViewOnly,
        frameEffect, ghostLikeness, ghostLikenesses, hoverLikeness, likenesses, likenessLayer, likenessPane,
        numberField, paintEffects, pickEffect, pickEffectAt, playWave, refreshEffects, removeEffectRoots,
        setEffectsShown, setEffectStays, setEffectValues, setLikeness, setNormalEffects, stepGhostLikenesses,
        stepLikenesses, stopWave } = createEffectsWiring({
  $, actorPose, assetUrl, baseMatrix, camera, controls, effectTemplate, flashHint, gizmo, gltfLoader, isForeignTarget,
  isStream, lightButton, ownerRoot, plural, pointOutside, renderer, sceneChanged, select, setLightsShown,
  setPickedSpawn, setSpawnsShown, short, text, texture, track, viewport, world,
  // (made further down: called through, since they are not made yet while this runs)
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
  $, banner, camera, controls, cutaway, editChanged, flashHint, floorStays, gameToView, gizmo, groundHeight, isLanding,
  landHere, LANDING_SHOWN, landingLayer, lightButton, ownSize, plural, projectChanged, projectsAvailable, rayAt,
  refreshGroundGrid, refreshLightVisibility, refreshMissionPicker, renderer, restingHint, select, setEffectsShown,
  setLightsShown, setSpawnsShown, tileCorner, world, zonesNow,
  // (made further down: called through, since they are not made yet while this runs)
  headerMission: () => headerMission(), setVolumesShown: on => setVolumesShown(on), stopPickBox: () => stopPickBox() });
// The Buildings view and box select (buildings_wiring.js): the project's buildings as boxes and the map's own, the
// view, its handles, drags and panel, the Normal button's Floor boxes, and box select.
const { addVolumes, buildingsFromVolumes, copyVolumes, deleteVolumes, drawCursorRings, endPickDrag, endVolumeDrag,
        FACES, handlePoint, hoverVolumeHandle, liveVolumes, makeVolume, mapRestoreChange, movePickDrag, moveVolumeDrag,
        newBuilding, newBuildingId, ownVolumeLayer, pasteVolumes, PICK_SLACK, pickBoxEdge, pickMoveNear, pickMovePoint,
        pickOwn, pickVolumeEdge, recordVolumes, refreshPickBox, refreshVolumes, restoreMapBuildings, setBoxesShown,
        setBuildings, setOwnPicked, setPickTool, setVolumeBox, setVolumesShown, setVolumeTool, spawnVolumeHandle,
        startPickDrag, startVolumeDrag, stopPickBox, syncVolumes, takePickBox, updateVolumeHandles, viewPoint,
        volumeBox, volumeClick, volumeHandleNear, volumeHint, volumePanel } = createBuildingsWiring({
  $, allBuildings, boxOf, builderBounds, camera, chosenStorey, copySelection, deleteSelection, editBaseSpawn,
  editChanged, editedCopies, editedKey, editedSpawns, editSpawnCopy, effectsShown, effectViewOnly, flashHint,
  floorOptions, freshBox, gizmo, HANDLE_PICK, isStream, kindButton, lightViewOnly, mapEditable, mapEdits, mapFloors,
  mapIdOf, mapKind, mapTarget, missionGizmo, pick, plural, PROJECT_BUILDING, projectListings, projector,
  projectsAvailable, rayAt, refreshSpawnMarkers, renderer, restingHint, select, selectionWords, setEffectsShown,
  setZonesShown, short, showPop, spawnBoxNow, spawnEntry, spawnMovable, spawnsShown, storeysNow, syncLights, text,
  volumeLayer, world });
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
// floor and roof slabs (custom geometry plan, M5): drawn by dragging a rectangle (the floor under the start, an upper
// floor a storey over it, a roof on the tops of the made walls round it, or two storeys up); white handles on its four
// edges grow or shrink it by whole tiles, blue ones move and size its holes; the piece panel's Floor section adds and
// removes holes and reshuffles its break pattern. Shared with the walls: the drawing, the handles, the undo steps.
const isMadeSlab = o => o?.added?.generated?.kind === 'fracSlab';
const isMadeGround = o => o?.added?.generated?.kind === 'ground';
const isMade = o => isMadeWall(o) || isMadeSlab(o) || isMadeGround(o);
const madeRoot = id => { const r = roots.get(id); return r && isMade(r.userData.source) ? r : null; };
const wallLookOf = o => WALL_LOOKS.find(l => short(o.added?.from?.actor ?? '') === l.actor && (o.added?.from?.package ?? '').toLowerCase() === l.package.toLowerCase()) ?? null;
// A wall standing for a look's heights (wallSpec): a donor look's numbers carry it; a look id's are the Bar's.
const lookWall = look => (look?.donor ? { look: look.donor } : {});
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
let lookPicker = null;      // made with the piece browser (it paints)
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
let lookPicking = null;     // { kind, onChoose }
function startLookPick(kind, onChoose = null) {
  closeLookPicker(); stopWallDrawing(); stopPlacing();
  lookPicking = { kind, onChoose };
  gizmo.hold(true);
  renderer.domElement.style.cursor = 'crosshair';
  flashHint(`Click a piece in the view to draw ${LOOK_NOUNS[kind] === 'ground' ? 'ground' : `${LOOK_NOUNS[kind]}s`} in its look (this map's, a copy, or one from another map) · Esc cancels`);
}
function stopLookPick() { if (lookPicking) gizmo.hold(false); lookPicking = null; renderer.domElement.style.cursor = ''; }
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
// ---- the Build menu (custom geometry editing plan, B1, 19 November 2026): the Add button's flyout starts drawing a made
// piece at once; the find box finds the same tools by their words
// (drawn plain, B2: in its kind's default look's shape, the look chosen afterwards in the piece panel)
const BUILD_TOOLS = {
  wall: { name: 'Wall', words: 'wall walls fracturing', start: () => startWallDrawing(plainLook('wall'), { plain: true }) },
  room: { name: 'Room', words: 'room rooms walls box', start: () => startWallDrawing(plainLook('wall'), { room: true, plain: true }) },
  roomroof: { name: 'Room with a roof', words: 'room rooms roof building walls', start: () => startWallDrawing(plainLook('wall'), { room: true, roof: true, plain: true }) },
  floor: { name: 'Floor', words: 'floor floors storey slab upstairs', start: () => startWallDrawing(plainLook('slab', { look: 'floor' }), { slab: true, plain: true }) },
  roof: { name: 'Roof', words: 'roof roofs slab ceiling', start: () => startWallDrawing(plainLook('slab', { look: 'roof' }), { slab: true, plain: true }) },
  ...Object.fromEntries(['patch', 'block', 'ramp', 'rock'].map(shape => [shape, {
    name: `Ground ${shape}`, words: `ground terrain ${shape}${shape === 'rock' ? ' boulder stone' : shape === 'ramp' ? ' slope' : ' platform'}`,
    start: () => startWallDrawing(plainLook('ground'), { ground: shape, plain: true }) }])),
};
let buildTool = null;     // the Build menu's tool being drawn (its button is lit)
function startBuild(key) {
  const tool = BUILD_TOOLS[key];
  if (!tool || !data || data.preview || builderMode) return;
  if (pieces.open) showPieces(false);
  tool.start();
  markBuildTool(key);
}
function markBuildTool(key) {
  buildTool = key;
  for (const b of $('buildFlyout').querySelectorAll('button[data-build]')) b.classList.toggle('on', b.dataset.build === key);
}
for (const b of $('buildFlyout').querySelectorAll('button[data-build]')) {
  b.onclick = () => { startBuild(b.dataset.build); b.blur(); };
}
// The tops of the made walls along a rectangle's sides ([x0, x1, y0, y1], standing on about `floor`): the highest, or null.
function wallTopsRound(rect, floor) {
  let top = null;
  for (const r of roots.values()) {
    if (r.userData.deleted || !r.visible || !isMadeWall(r.userData.source)) continue;
    const b = new THREE.Box3().setFromObject(r);
    if (b.isEmpty() || b.max.x < rect[0] - 16 || b.min.x > rect[1] + 16 || b.max.z < rect[2] - 16 || b.min.z > rect[3] + 16) continue;
    if (Math.abs(b.min.y - WALL.bottom - floor) > 64) continue;
    const inside = b.min.x > rect[0] + 16 && b.max.x < rect[1] - 16 && b.min.z > rect[2] + 16 && b.max.z < rect[3] - 16;
    if (!inside) top = Math.max(top ?? -Infinity, b.max.y);
  }
  return top;
}
let wallDrawing = null;    // { look, room (a room's four walls), slab, roof (a room's roof: roofTemplate), template (once read), start, floor, pointerId, last }
const wallGhostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.4, depthWrite: false });
// (a wall's ghost, and three more for a room's other sides)
const wallGhosts = [0, 1, 2, 3, 4].map(() => {
  const ghost = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), wallGhostMaterial);
  ghost.visible = false; ghost.matrixAutoUpdate = false; ghost.raycast = () => {}; ghost.renderOrder = 7; world.add(ghost);
  return ghost;
});
const wallGhost = { set visible(on) { for (const g of wallGhosts) g.visible = on; } };
async function startWallDrawing(look, { room = false, slab = false, roof = false, ground = null, plain = false } = {}) {
  stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopWallDrawing();
  const drawing = wallDrawing = { look, room, slab, roof, ground, plain, template: null, start: null };
  renderer.domElement.style.cursor = 'crosshair';
  pieces.setChosen(null);
  const done = busyStart(`Reading ${look.name}…`);
  try {
    const template = await wallTemplate(look);
    const roofTemplate = roof ? await wallTemplate(SLAB_LOOKS[0]) : null;
    if (wallDrawing !== drawing) return;
    drawing.template = template; drawing.roofTemplate = roofTemplate;
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
  // (a plain piece is named by its kind; its look is chosen afterwards in the piece panel)
  const d = wallDrawing, of = d.plain ? '' : ` of ${d.look.name.toLowerCase()}`;
  hint.replaceChildren(words ?? (d.ground
    ? `Drawing a ${d.ground}${of}: press on the ground at one corner, drag to the other${d.ground === 'ramp' ? ' (it rises toward the end)' : ''}, let go · Shift keeps drawing · `
    : d.slab
    ? `Drawing a ${d.plain ? (d.look.role === 'roof' ? 'roof' : 'floor') : d.look.name.toLowerCase()}: press at one corner, drag to the other, let go · Shift keeps drawing · `
    : d.room
    ? `Drawing a room${d.plain ? '' : `${of}s`}${d.roof ? ' with a roof' : ''}: press on the ground at one corner, drag to the other, let go · Shift keeps drawing · `
    : `Drawing a ${d.plain ? 'wall' : d.look.name}: press on the ground at one end, drag along a tile line, let go · Shift keeps drawing · `));
  text(hint, 'kbd', 'Esc'); hint.append(' stops');
}
function stopWallDrawing() {
  if (!wallDrawing) return;
  if (wallDrawing.pointerId != null) try { renderer.domElement.releasePointerCapture(wallDrawing.pointerId); } catch { /* released */ }
  wallDrawing = null; wallGhost.visible = false; renderer.domElement.style.cursor = '';
  pieces.setChosen(null); library.setChosen(null); markBuildTool(null); restingHint();
}
// The point of the ground (or a piece) under the pointer, in game units; and the floor under it.
function wallGround(clientX, clientY) {
  const hit = pick(clientX, clientY)?.point
    ?? rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundHeight()), new THREE.Vector3());
  return hit ? [hit.x, hit.z, hit.y] : null;
}
function drawnNow(d, at) {
  const options = { origin: gridOrigin() ?? [0, 0], template: d.template, floor: d.floor, seed: d.seed };
  if (d.ground) return drawnGround(d.start.slice(0, 2), at.slice(0, 2), { ...options, z: d.floor, shape: d.ground, look: d.look });
  if (d.slab) {
    const flat = drawnSlab(d.start.slice(0, 2), at.slice(0, 2), { ...options, z: d.floor, look: d.look });
    if (d.look.role !== 'roof') return flat;
    // a roof: on the tops of the made walls round it, else two storeys over the floor
    const [x, y] = flat.location, top = wallTopsRound([x, x + flat.slab.x1, y, y + flat.slab.y1], d.floor);
    return { ...flat, location: [x, y, Math.round((top ?? d.floor + WALL.top) * 1000) / 1000] };     // (no walls: the Bar's two storeys)
  }
  if (!d.room) return drawnWall(d.start.slice(0, 2), at.slice(0, 2), options);
  const room = drawnRoom(d.start.slice(0, 2), at.slice(0, 2), { ...options, camera: [camera.position.x, camera.position.z] });
  return d.roof ? { ...room, roof: roomRoof(room, { template: d.roofTemplate, floor: d.floor, seed: d.seed + 4, top: wallTop(lookWall(d.look)) }) } : room;
}
// The ghost: the wall's solid at the pose drawn (its box in the donor mesh's frame, at the copy's place); a room's four.
function showWallGhost(template, drawn) {
  if (drawn.slab) { showSlabGhost(template, drawn, 0); for (const g of wallGhosts.slice(1)) g.visible = false; return; }
  if (drawn.ground) {
    const ghost = wallGhosts[0], b = groundShapeBox(drawn.ground);
    ghost.visible = true;
    ghost.matrix.copy(movedMatrix(template, drawn.location, drawn.rotation))
      .multiply(new THREE.Matrix4().makeTranslation((b[0] + b[1]) / 2, (b[4] + b[5]) / 2, (b[2] + b[3]) / 2))
      .multiply(new THREE.Matrix4().makeScale(b[1] - b[0], Math.max(4, b[5] - b[4]), b[3] - b[2]));
    ghost.matrixWorldNeedsUpdate = true;
    for (const g of wallGhosts.slice(1)) g.visible = false;
    return;
  }
  if (drawn.roof) { showSlabGhost(wallDrawing.roofTemplate, drawn.roof, 4); }
  else wallGhosts[4].visible = false;
  const walls = drawn.walls ?? [drawn];
  wallGhosts.forEach((ghost, k) => {
    const w = walls[k];
    ghost.visible = Boolean(w);
    if (!w) return;
    const lw = { ...w.wall, ...lookWall(wallDrawing?.look) }, spec = wallSpec(lw), top = wallTop(lw);
    const a = spec.endInset, b = w.wall.x1 - spec.endInset;
    ghost.matrix.copy(movedMatrix(template, w.location, w.rotation))
      .multiply(new THREE.Matrix4().makeTranslation((a + b) / 2, (top + spec.bottom) / 2, 0))
      .multiply(new THREE.Matrix4().makeScale(b - a, top - spec.bottom, 2 * spec.half));
    ghost.matrixWorldNeedsUpdate = true;
  });
}
// A slab's ghost (k: which ghost): its footprint between its look's heights (at least 4 thick, to be seen).
function showSlabGhost(template, drawn, k) {
  const ghost = wallGhosts[k], look = slabLookOf(drawn.slab), mid = (look.top + look.bottom) / 2;
  ghost.visible = true;
  ghost.matrix.copy(movedMatrix(template, drawn.location, drawn.rotation))
    .multiply(new THREE.Matrix4().makeTranslation(drawn.slab.x1 / 2, mid, drawn.slab.y1 / 2))
    .multiply(new THREE.Matrix4().makeScale(drawn.slab.x1, Math.max(4, look.top - look.bottom), drawn.slab.y1));
  ghost.matrixWorldNeedsUpdate = true;
}
const drawnWords = d => (d.ground ? `${d.last.tiles[0]} by ${d.last.tiles[1]} tiles${d.ground === 'ramp' ? ` · ${slopeWords(d.last.ground)}` : ''}`
  : d.slab || d.room ? `${d.last.tiles[0]} by ${d.last.tiles[1]} tiles${d.last.tiles.includes(d.slab ? SLAB.maxTiles : WALL.maxTiles) ? ' (the largest)' : ''}`
  : `${plural(d.last.tiles, 'tile')}${d.last.tiles === WALL.maxTiles ? ' (the longest)' : ''}`);
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
  wallHint(`${drawnWords(d)} · let go to make it · `);
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
  wallHint(`${drawnWords(d)} · let go to make it · `);
}
async function endWallDraw(keep) {
  const d = wallDrawing;
  if (!d?.start) return;
  try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
  const made = d.last, template = d.template, look = d.look, room = d.room, roofTemplate = d.roofTemplate, floor = d.floor, plain = d.plain;
  const chooseWords = plain ? ' · choose its look in the piece panel' : '';
  d.start = null; d.pointerId = null; wallGhost.visible = false;
  if (!keep) stopWallDrawing(); else wallHint();
  if (made.ground) {
    await pasteSnapshot({ entries: [{ source: { ...template, added: { from: fromOf(template), generated: madeRequest('ground', look, made.ground, plain) } },
                                      matrix: movedMatrix(template, made.location, made.rotation) }], pivotIndex: 0, name: look.name }, new THREE.Matrix4());
    flashHint(`Made a ${groundShapeWords(made.ground).toLowerCase()}${plain ? '' : ` of ${look.name.toLowerCase()}`} · its white handles size it${made.ground.shape === 'patch' ? '' : ', the top one raises it'}${chooseWords}`);
    return;
  }
  if (made.slab) {
    await pasteSnapshot({ entries: [{ source: { ...template, added: { from: fromOf(template), generated: madeRequest('fracSlab', look, made.slab, plain) } },
                                      matrix: movedMatrix(template, made.location, made.rotation) }], pivotIndex: 0, name: look.name }, new THREE.Matrix4());
    flashHint(`Made a ${plain ? (look.role === 'roof' ? 'roof' : 'floor') : look.name.toLowerCase()}, ${made.tiles[0]} by ${made.tiles[1]} tiles · its white handles grow it; Add hole is in the piece panel${chooseWords}`);
    return;
  }
  const entries = (made.walls ?? [made]).map(w => ({
    source: { ...template, added: { from: fromOf(template), generated: madeRequest('fracWall', look, w.wall, plain) } },
    matrix: movedMatrix(template, w.location, w.rotation) }));
  if (made.roof)
    entries.push({ source: { ...roofTemplate, added: { from: fromOf(roofTemplate), generated: madeRequest('fracSlab', SLAB_LOOKS[0], made.roof.slab, plain) } },
                   matrix: movedMatrix(roofTemplate, made.roof.location, made.roof.rotation) });
  await pasteSnapshot({ entries, pivotIndex: 0, name: room ? (plain ? 'room' : `room of ${look.name.toLowerCase()}s`) : plain ? 'wall' : look.name }, new THREE.Matrix4());
  // (a room is one locked group, its building with it when it has one: B3, D-2)
  const pasted = gizmo.picks().ids;
  if (made.roof) {
    // its building: the room's rectangle, a floor for each storey, breaking at the storeys' heights, and one over them
    // for the roof, as the game's are: URB_Bar's lists its walls on floor 0 cut down at floor 2, its upstairs floor
    // slab on floor 1 and its roof on floor 2. The game lists a piece in a floor only when its bottom is more than 20
    // under that floor's top, so a slab belongs to the floor it is the bottom of (EXP-76 run E: with the floors 16
    // higher, the floor and roof were in none and never cut away)
    const [x0, y0] = made.roof.location, x1 = x0 + made.roof.slab.x1, y1 = y0 + made.roof.slab.y1, z = floor;
    // (the look's: a wall's floors break at each of its storeys and at its top, a one-storey wall's at its top)
    const lw = lookWall(look), spec = wallSpec(lw), top = wallTop(lw);
    const breaks = [spec.bottom, ...Array.from({ length: storeysOf(lw) - 1 }, (_, k) => spec.storey * (k + 1)), top];
    const boxes = addVolumes([...breaks.slice(0, -1).map((b, k) => ({ box: [x0, y0, z + b, x1, y1, z + breaks[k + 1]], floor: k })),
                              { box: [x0, y0, z + top, x1, y1, z + top + WALL.storey], floor: breaks.length - 1 }], newBuilding());
    // (a wall the active piece, so the panel is the room's, not its building's)
    gizmo.setSelection([...pasted, ...boxes.map(r => r.userData.source.id)], pasted[0]);
    lockAsGroup();
    gizmo.joinLast(3);
    flashHint(`Made a room, ${made.tiles[0]} by ${made.tiles[1]} tiles, with a roof and a building round it: picked as one (Ungroup edits its walls one by one); the roof is cut away when the cursor is inside${chooseWords} · Ctrl+Z takes it out`);
    return;
  }
  if (room) { gizmo.setSelection(pasted, pasted[0]); lockAsGroup(); gizmo.joinLast(2); }
  flashHint(room ? `Made a room, ${made.tiles[0]} by ${made.tiles[1]} tiles: four walls joined at the corners, a doorway in the near side, picked as one (Ungroup edits its walls one by one)${chooseWords}`
    : `Made a ${plain ? 'wall' : look.name}, ${plural(made.tiles, 'tile')} long · its white handles lengthen it; Add gap is in the piece panel${chooseWords}`);
}
// ---- the wall as it is now, and changing it
const wallState = root => ({ generated: structuredClone(root.userData.source.added.generated), ...actorPose(root.userData.source, root.matrix) });
// The mesh record for a made wall's numbers (as madeShape makes it) and end styles, its key.
function madeMesh(o, generated, ends = null) {
  if (generated.kind === 'ground') {
    const numbers = madeGroundNumbers(generated.ground), key = `made:ground:${JSON.stringify(numbers)}`;
    if (!data.meshes[key])
      data.meshes[key] = { ...data.meshes[o.mesh], url: `/generated/ground.glb?${new URLSearchParams({ ground: JSON.stringify(numbers) })}`, bounds: groundBounds(numbers) };
    return key;
  }
  if (generated.kind !== 'fracSlab') return madeWallMesh(o, generated.wall, ends, generated.blasts);
  // (its blasts, B5, in its key and request)
  const numbers = madeSlabNumbers(generated.slab), broken = blastQuery(generated.blasts);
  const key = `made:fracslab:${JSON.stringify(numbers)}${broken.key}`;
  if (!data.meshes[key])
    data.meshes[key] = { ...data.meshes[o.mesh], url: `/generated/fracslab.glb?${new URLSearchParams({ slab: JSON.stringify(numbers), ...broken.query })}`, bounds: slabBounds(numbers) };
  return key;
}
function madeWallMesh(o, wall, ends = null, blasts = null) {
  const numbers = madeWallNumbers(wall, ends), broken = blastQuery(blasts);
  const key = `made:fracwall:${JSON.stringify(numbers)}${broken.key}`;
  if (!data.meshes[key]) {
    const was = data.meshes[o.mesh];
    data.meshes[key] = { ...was, url: `/generated/fracwall.glb?${new URLSearchParams({ wall: JSON.stringify(numbers), ...broken.query })}`,
      bounds: madeBounds(numbers) };
  }
  return key;
}
// ---- joined walls (custom geometry plan, M3 item 2): where made walls meet, each end's style follows (wallJoins, the
// compiler's wall_joins), worked out again after every change and never saved (the Build works it out the same way);
// a wall whose ends changed is drawn anew. root.userData.joins: its { ends, joins } now.
let joinsQueued = false;
function refreshJoins() {
  if (joinsQueued) return;
  joinsQueued = true;
  queueMicrotask(() => {
    joinsQueued = false;
    const walls = [...roots.values()].filter(r => isMadeWall(r.userData.source) && !r.userData.deleted
      && r.userData.source.added.generated.kind === 'fracWall');
    const found = wallJoins(walls.map(r => ({ key: r.userData.source.id, wall: r.userData.source.added.generated.wall,
                                              ...actorPose(r.userData.source, r.matrix) })));
    for (const r of walls) {
      const now = found[r.userData.source.id], was = r.userData.joins?.ends ?? ['free', 'free'];
      r.userData.joins = now;
      if (now.ends[0] !== was[0] || now.ends[1] !== was[1]) applyWall(r, wallState(r));
      else if (selected === r.userData.source.id && JSON.stringify(now.joins) !== JSON.stringify(r.userData.joinsShown ?? [])) wallPanel(r);
    }
  });
}
// A state put on the wall's piece: its numbers, its pose, its mesh drawn anew once loaded (no undo step).
async function applyWall(root, state) {
  state = { ...state, generated: versionedGround(state.generated) };
  const o = root.userData.source;
  o.added = { ...o.added, generated: structuredClone(state.generated) };
  const key = madeMesh(o, state.generated, root.userData.joins?.ends), was = root.userData.drawnMesh ?? o.mesh;
  o.mesh = key;
  gizmo.applyMatrices([root], [movedMatrix(o, state.location, state.rotation)]);
  root.updateMatrixWorld(true);
  const token = root.userData.wallToken = (root.userData.wallToken ?? 0) + 1;
  track(geometryCache, key, () => gltfLoader.loadAsync(assetUrl(data.meshes[key].url)));
  let base;
  try { base = await geometryCache.get(key); }
  catch (error) {
    // a mesh the server didn't make (review finding 31): the piece keeps the numbers (its panel, handles and the save
    // have them, and the Build makes them) and its drawing the shape it had, which its mesh key says too; the hint says
    // why. (track drops the failed load, so the next change asks again.)
    if (root.userData.wallToken !== token) return;
    o.mesh = was;
    flashHint(`${data.meshes[key]?.name ?? 'The piece'}: the editor couldn't draw these numbers (${error?.message ?? error}), so it shows the shape it had; the Build makes the new one`);
    return;
  }
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
  // (the made mesh it drew before leaves the cache when no piece draws it: a drag passes through many, each a whole
  // wall's; undo asks the server again, which keeps its recent answers)
  root.userData.drawnMesh = key;
  if (was && was !== key && was.startsWith('made:') && ![...roots.values()].some(r => r.userData.source.mesh === was || r.userData.drawnMesh === was))
    geometryCache.delete(was);
  const gone = new Set(old);
  pickables.splice(0, pickables.length, ...pickables.filter(p => !gone.has(p)), ...(roots.get(o.id) === root ? parts : []));
  root.updateMatrixWorld(true);
  sceneChanged();
  if (selected === o.id) { refreshHighlight(root); (isMadeGround(o) ? groundPanel : isMadeSlab(o) ? slabPanel : wallPanel)(root); }
}
// One undo step from `before` to `after` (states), the piece picked again each way.
function setWall(root, after, before) {
  const id = root.userData.source.id;
  after = { ...after, generated: versionedGround(after.generated) };
  if (JSON.stringify(after) === JSON.stringify(before)) { applyWall(root, before); return; }
  gizmo.record({ redo: () => { applyWall(root, after); select(id, false, true); },
                 undo: () => { applyWall(root, before); select(id, false, true); } });
}
function changeWall(change) {
  const root = madeRoot(selected);
  if (!root) return;
  const before = wallState(root), after = change(before);
  if (after) setWall(root, after, before);
}
// ---- the handles
const wallHandleLayer = new THREE.Group(); world.add(wallHandleLayer);
const wallHandleMeshes = [];
const wallStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(24), 3)),
                                         new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
wallStems.renderOrder = 8; wallStems.raycast = () => {}; wallStems.frustumCulled = false; wallHandleLayer.add(wallStems);
let wallDrag = null, wallHover = null, wallFocus = null;   // wallFocus: { id, index }: the opening whose handle was last touched
const WALL_PART_WORDS = { middle: 'Gap: drag to move it along the wall or up and down (down to the floor it is a doorway)', x0: 'Gap\'s side: drag it to the wall\'s end to cut the wall away to there',
                          x1: 'Gap\'s side: drag it to the wall\'s end to cut the wall away to there',
                          z1: 'Gap\'s top: drag it up to the wall\'s top to cut through it',
                          z0: 'Gap\'s bottom: drag it down to the floor to cut to the wall\'s bottom' };
// A gap's handles move by the snap setting (the user, 19 November 2026: smoothly unless the snap is on), [along the
// wall, up]; Alt: steps of GAP.fine
const OPENING_STEPS = { off: [1, 1], fine: [24, 24], tile: [TILE, 24] };
const OPENING_STEP_WORDS = { off: 'steps of 1 unit', fine: 'steps of 24', tile: 'whole tiles along the wall, steps of 24 up' };
function handleWall() {
  const root = madeRoot(selected);
  if (!root || root.userData.deleted || !root.visible || placing || wallDrawing || volumesOn || lightsOn || zonesOn || effectsOn || spawnsOn
      || gizmo.picks().ids.length !== 1) return null;
  const g = root.userData.source.added.generated;
  return (g.kind === 'ground' ? toolGround(g.ground) : g.kind === 'fracSlab' ? toolSlab(g.slab) : toolWall(g.wall)) ? root : null;
}
// A ground shape's handles: a white one out of each edge ('side') at its top's middle height, and one on top ('top': a
// block's top, a ramp's high edge) that raises it.
function groundHandlesNow(root) {
  const g = root.userData.source.added.generated.ground, b = groundShapeBox(g);
  root.updateMatrixWorld(true);
  const toView = (x, y, h) => new THREE.Vector3(x, h, y).applyMatrix4(root.matrixWorld);
  const axis = (x, y, z = 0) => toView(x, y, z).sub(toView(0, 0, 0)).normalize();
  const mid = g.shape === 'ramp' ? b[5] / 2 : b[5], cx = (b[0] + b[1]) / 2, cy = (b[2] + b[3]) / 2;
  const out = [
    { key: 'side:x0', kind: 'side', part: 'x0', at: toView(b[0], cy, g.shape === 'ramp' ? 0 : mid), dir: axis(-1, 0) },
    { key: 'side:x1', kind: 'side', part: 'x1', at: toView(b[1], cy, mid), dir: axis(1, 0) },
    { key: 'side:y0', kind: 'side', part: 'y0', at: toView(cx, b[2], mid), dir: axis(0, -1) },
    { key: 'side:y1', kind: 'side', part: 'y1', at: toView(cx, b[3], mid), dir: axis(0, 1) }];
  if (g.shape !== 'patch')
    out.push({ key: 'end:top', kind: 'end', part: 'top', at: toView(g.shape === 'ramp' ? b[1] : cx, cy, b[5]), dir: axis(0, 0, 1) });
  // a rock's corners: a blue point on each (look picker and rock points plan, R3), from the server's answer
  const c = g.shape === 'rock' && !pointGizmo.dragging ? rockCornersOf(g) : null;
  for (const index of c?.corners ?? [])
    out.push({ key: `point:${index}`, kind: 'point', part: 'point', index, at: toView(...c.points[index]), dir: null });
  return out;
}
// ---- a rock's corners (look picker and rock points plan, R2, R3): its points and which are corners, asked of the
// server (Python's seeded random isn't the page's) for each rock's numbers; a point picked takes the move gizmo
const rockCorners = new Map();      // the rock's numbers, look aside (JSON) -> { points, corners } or a promise
// A failed answer isn't kept (review finding 31): the hint says why, once, and the corners are asked for again after a
// pause (the handles are worked out often, so not straight away)
const rockCornersFailed = new Map();  // the rock's numbers -> performance.now() of its last failed answer
function rockCornersOf(g) {
  const { look: _, ...shape } = madeGroundNumbers(g), key = JSON.stringify(shape), known = rockCorners.get(key);
  if (known && !known.then) return known;
  if (!known && !(performance.now() - (rockCornersFailed.get(key) ?? -Infinity) < 4000)) {
    const asking = fetch(`/generated/ground-corners.json?${new URLSearchParams({ ground: key })}`)
      .then(async r => {
        const answer = await r.json().catch(() => null);
        if (!r.ok || !answer?.points) throw new Error(answer?.error ?? `the editor's server answered ${r.status}`);
        return answer;
      })
      .then(answer => {
        rockCorners.set(key, answer);
        rockCornersFailed.delete(key);
        if (rockCorners.size > 300) rockCorners.delete(rockCorners.keys().next().value);
      }, error => {
        if (rockCorners.get(key) === asking) rockCorners.delete(key);
        if (!rockCornersFailed.has(key))
          flashHint(`The rock's corner points couldn't be read (${error?.message ?? error}); the editor asks again in a moment`);
        rockCornersFailed.set(key, performance.now());
      });
    rockCorners.set(key, asking);
  }
  return null;
}
let rockPoint = null, pointDrag = null;     // rockPoint: { id, index }, the rock's point the gizmo stands on
let shiftHeld = false;
window.addEventListener('keydown', e => { if (e.key === 'Shift') shiftHeld = true; });
window.addEventListener('keyup', e => { if (e.key === 'Shift') shiftHeld = false; });
window.addEventListener('blur', () => { shiftHeld = false; });
const pointProxy = new THREE.Object3D(); world.add(pointProxy);
const pointGizmo = new TransformControls(camera, renderer.domElement);
pointGizmo.attach(pointProxy); pointGizmo.enabled = false; pointGizmo.setSpace('local'); pointGizmo.setMode('translate');
const pointGizmoHelper = pointGizmo.getHelper(); pointGizmoHelper.visible = false; world.add(pointGizmoHelper);
pointGizmo.addEventListener('dragging-changed', e => { controls.enabled = !e.value; });
// The picked rock's points now: its moved ones, else its seed's from the server (null until they are known).
function rockPointsOf(g) { return g.points ?? rockCornersOf(g)?.points ?? null; }
function pickRockPoint(root, index) {
  if (!rockPoint) gizmo.hold(true);
  rockPoint = { id: root.userData.source.id, index };
  placePointGizmo();
  groundPanel(root);
  flashHint(`A corner of the rock: drag its arrows to move it${index < ROCK.ring ? ' on the ground (it is of the rock\'s foot)' : ''}; Shift: steps of 8 · Esc lets it go`);
}
function releaseRockPoint() {
  if (!rockPoint) return;
  const root = roots.get(rockPoint.id);
  rockPoint = null; pointDrag = null;
  pointGizmo.enabled = pointGizmoHelper.visible = false;
  gizmo.hold(false);
  if (root && selected === root.userData.source.id && isMadeGround(root.userData.source)) groundPanel(root);
}
// Each frame: the gizmo on the picked point, or the point let go when its rock is no longer the one handled.
function placePointGizmo() {
  if (!rockPoint) return;
  const root = roots.get(rockPoint.id);
  if (!root || (handleWall() !== root && !pointDrag) || root.userData.source.added?.generated?.ground?.shape !== 'rock') { releaseRockPoint(); return; }
  if (pointGizmo.dragging) return;
  const p = rockPointsOf(root.userData.source.added.generated.ground)?.[rockPoint.index];
  pointGizmo.enabled = pointGizmoHelper.visible = Boolean(p);
  if (!p) return;
  root.updateMatrixWorld(true);
  pointProxy.position.copy(new THREE.Vector3(p[0], p[2], p[1]).applyMatrix4(root.matrixWorld));
  pointProxy.quaternion.setFromRotationMatrix(new THREE.Matrix4().extractRotation(root.matrixWorld));
  pointProxy.updateMatrixWorld(true);
  // (a point of the rock's foot moves on the ground only: no up arrow, the view's y)
  pointGizmo.showY = rockPoint.index >= ROCK.ring;
}
pointGizmo.addEventListener('mouseDown', () => {
  const root = rockPoint && roots.get(rockPoint.id);
  const points = root && rockPointsOf(root.userData.source.added.generated.ground);
  if (!points) { pointDrag = null; return; }
  root.updateMatrixWorld(true);
  pointDrag = { root, index: rockPoint.index, points, before: wallState(root), frame: root.matrixWorld.clone(),
                start: points[rockPoint.index], after: null, shown: '' };
});
pointGizmo.addEventListener('objectChange', () => {
  const d = pointDrag;
  if (!d) return;
  // the proxy's place in the rock's frame as it was when the drag began (its corner may move as the footprint grows)
  const local = pointProxy.position.clone().applyMatrix4(d.frame.clone().invert());
  let to = [local.x, local.z, local.y];
  if (shiftHeld) {
    to = to.map((v, k) => d.start[k] + Math.round((v - d.start[k]) / 8) * 8);
    pointProxy.position.copy(new THREE.Vector3(to[0], to[2], to[1]).applyMatrix4(d.frame));
  }
  const b = d.before, r = movedPoint(b.generated.ground, d.points, d.index, to);
  const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.frame))
    .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
  const location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
  const key = JSON.stringify([r.ground, location]);
  if (key === d.shown) return;
  d.shown = key;
  d.after = { generated: { ...b.generated, ground: r.ground }, location, rotation: b.rotation };
  applyWallSoon(d.root, d.after);
  const grown = r.ground.x1 !== b.generated.ground.x1 || r.ground.y1 !== b.generated.ground.y1;
  volumeHint(`Corner at ${r.ground.points[d.index].map(Math.round).join(', ')} in the rock's frame${grown ? ` · grown to ${groundShapeWords(r.ground).toLowerCase()}` : ''}`);
});
pointGizmo.addEventListener('mouseUp', () => {
  const d = pointDrag;
  pointDrag = null;
  dropQueuedWall(d?.root);
  if (d?.after && !d.cancelled) setWall(d.root, d.after, d.before);
  restingHint(); editChanged();
  setTimeout(placePointGizmo, 0);       // (the controls end their drag after this event)
});
function cancelPointDrag() {
  const d = pointDrag;
  if (!d) return false;
  d.cancelled = true; pointGizmo.reset?.();
  dropQueuedWall(d.root);
  applyWall(d.root, d.before);
  return true;
}
// A slab's handles: a white one out of the middle of each edge ('side', its part the side), at its top; on each hole a
// blue one at each side and one in its middle ('hole'; the middle slides it on the slab, `dir` null).
function slabHandlesNow(root) {
  const s = root.userData.source.added.generated.slab, look = slabLookOf(s), z = look.top + 1;
  root.updateMatrixWorld(true);
  const toView = (x, y, h) => new THREE.Vector3(x, h, y).applyMatrix4(root.matrixWorld);
  const axis = (x, y) => toView(x, y, 0).sub(toView(0, 0, 0)).normalize();
  const out = [
    { key: 'side:x0', kind: 'side', part: 'x0', at: toView(0, s.y1 / 2, z), dir: axis(-1, 0) },
    { key: 'side:x1', kind: 'side', part: 'x1', at: toView(s.x1, s.y1 / 2, z), dir: axis(1, 0) },
    { key: 'side:y0', kind: 'side', part: 'y0', at: toView(s.x1 / 2, 0, z), dir: axis(0, -1) },
    { key: 'side:y1', kind: 'side', part: 'y1', at: toView(s.x1 / 2, s.y1, z), dir: axis(0, 1) }];
  (s.holes ?? []).forEach((h, index) => {
    const cx = (h.x0 + h.x1) / 2, cy = (h.y0 + h.y1) / 2;
    out.push({ key: `hole:${index}:middle`, kind: 'hole', part: 'middle', index, at: toView(cx, cy, z), dir: null });
    for (const [part, x, y, d] of [['x0', h.x0, cy, [1, 0]], ['x1', h.x1, cy, [1, 0]], ['y0', cx, h.y0, [0, 1]], ['y1', cx, h.y1, [0, 1]]])
      out.push({ key: `hole:${index}:${part}`, kind: 'hole', part, index, at: toView(x, y, z), dir: axis(...d) });
  });
  return out;
}
// The handles of the wall now: each { key, kind ('end' | 'opening'), part, index, at (on the wall), dir (the drag's
// axis, out of an end), out (whether it stands off the wall, out from `at`) } in the view.
function wallHandlesNow(root) {
  if (isMadeGround(root.userData.source)) return groundHandlesNow(root);
  if (isMadeSlab(root.userData.source)) return slabHandlesNow(root);
  const w = root.userData.source.added.generated.wall;
  root.updateMatrixWorld(true);
  const toView = (x, y, z) => new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
  const axis = (x, y, z) => toView(x, y, z).sub(toView(0, 0, 0)).normalize();
  // the openings' handles on the face toward the camera
  const toCamera = camera.position.clone().sub(toView(w.x1 / 2, 0, 184));
  const spec = wallSpec(w), side = toCamera.dot(axis(0, 1, 0)) >= 0 ? spec.half + 1 : -spec.half - 1;
  const mid = (wallTop(w) + spec.bottom) / 2, out = [];
  out.push({ key: 'end:x0', kind: 'end', part: 'x0', at: toView(0, 0, mid), dir: axis(-1, 0, 0) });
  out.push({ key: 'end:x1', kind: 'end', part: 'x1', at: toView(w.x1, 0, mid), dir: axis(1, 0, 0) });
  // the top: up or down a storey (M2)
  out.push({ key: 'end:top', kind: 'end', part: 'top', at: toView(w.x1 / 2, 0, wallTop(w)), dir: axis(0, 0, 1) });
  sortedOpenings(w.openings ?? []).forEach((o, index) => {
    // (a gap cut to the wall's bottom has its bottom handle on the floor)
    const cx = (o.x0 + o.x1) / 2, bottom = Math.max(0, o.z0), cz = (bottom + o.z1) / 2;
    const at = { middle: [cx, cz], x0: [o.x0, cz], x1: [o.x1, cz], z1: [cx, o.z1], z0: [cx, bottom] };
    // (the middle drags in the wall's plane: `plane` its normal; the sides and ends along their axis)
    for (const part of openingParts())
      out.push({ key: `open:${index}:${part}`, kind: 'opening', part, index, at: toView(at[part][0], side, at[part][1]),
                 dir: part === 'middle' ? null : part === 'z0' || part === 'z1' ? axis(0, 0, 1) : axis(1, 0, 0),
                 plane: part === 'middle' ? axis(0, 1, 0) : null, along: part === 'middle' ? axis(1, 0, 0) : null });
  });
  return out;
}
const wallHandlePoint = h => (h.kind === 'end' || h.kind === 'side' ? h.at.clone().addScaledVector(h.dir, camera.position.distanceTo(h.at) * 0.06) : h.at);
function updateWallHandles() {
  const root = wallDrag?.root ?? handleWall();
  wallHandleLayer.visible = Boolean(root) && !gizmo.controls.dragging && !pointGizmo.dragging;
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
    const white = h.kind === 'end' || h.kind === 'side';
    const focused = !white && h.kind !== 'point' && wallFocus?.id === root.userData.source.id && wallFocus.index === h.index;
    const pickedPoint = h.kind === 'point' && rockPoint?.id === root.userData.source.id && rockPoint.index === h.index;
    mesh.userData.material.color.setHex(h.key === lit ? 0xffe27a : white || pickedPoint ? 0xffffff : focused ? 0x9fdcff : 0x4aa8ff);
    scaleMarker(mesh, camera, mesh.position);
    if (!white) mesh.scale.multiplyScalar(h.part === 'middle' ? 1 : h.kind === 'point' ? 0.7 : 0.8);
    if (white && n < 8) { stems.setXYZ(n++, h.at.x, h.at.y, h.at.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z); }
  });
  for (; n < 8; n++) stems.setXYZ(n, 0, 0, 0);
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
  renderer.domElement.title = !h ? '' : h.kind === 'point' ? 'A corner of the rock: click it, then drag its arrows to move it (Shift: steps of 8)'
    : h.part === 'top' && isMadeGround(handleWall()?.userData.source) ? 'The top: drag to raise or lower it (steps of 8)'
    : h.kind === 'side' ? 'The edge: drag to grow or shrink it by whole tiles'
    : h.kind === 'hole' ? (h.part === 'middle' ? 'Hole: drag to slide it (whole tiles)' : 'Hole\'s side: drag to size it (whole tiles)')
    : h.part === 'top' ? topHandleWords(handleWall()?.userData.source.added.generated.wall)
    : h.kind === 'end' ? 'The wall\'s end: drag to lengthen or shorten it by whole tiles'
    : `${WALL_PART_WORDS[h.part]} (${OPENING_STEP_WORDS[snapMode]}, as the snap setting; Alt: steps of ${GAP.fine})`;
}
// What the wall's top handle does: adds or takes storeys (B4), its look's storeys at a time where it can't be made
// one storey.
function topHandleWords(w) {
  const spec = wallSpec(w);
  return `The wall's top: drag up or down to add or take storeys${spec.lower ? '' : ` (${storeyWords(spec.storeys)} at a time: its look is made that tall only)`}`;
}
// What the Build makes of a wall longer or taller than the game's (B4, D-3: made_split), in words; '' for one piece.
function wallPiecesWords(w) {
  const spec = wallSpec(w), long = Math.round((w.x1 - w.x0) / TILE) > WALL.pieceTiles, tall = storeysOf(w) > spec.storeys;
  if (!long && !tall) return '';
  return ` The Build makes it as walls of at most ${WALL.pieceTiles} tiles and ${storeyWords(spec.storeys)} (its look's), `
    + `${long && tall ? 'joined end to end and stacked' : long ? 'joined end to end' : 'stacked'}: they break as one wall.`;
}
function startWallDrag(e) {
  if (wallDrawing) return startWallDraw(e);
  if (e.button !== 0 || wallDrag || coverDrag || volumeDrag || gizmo.controls.dragging) return false;
  // (a press on the point's gizmo is the gizmo's: it works out its arrow in its own press handler, after this one, so
  // it is asked here first)
  if (pointGizmo.enabled && !pointGizmo.dragging) {
    const r = renderer.domElement.getBoundingClientRect();
    pointGizmo.pointerHover({ x: (e.clientX - r.left) / r.width * 2 - 1, y: -(e.clientY - r.top) / r.height * 2 + 1, button: e.button });
  }
  if (pointGizmo.enabled && (pointGizmo.dragging || pointGizmo.axis !== null)) return false;
  const h = wallHandleNear(e.clientX, e.clientY);
  if (h?.kind === 'point') { pickRockPoint(handleWall(), h.index); return true; }
  if (rockPoint) releaseRockPoint();
  if (!h) return false;
  const root = handleWall(), from = h.dir ? alongLine(e.clientX, e.clientY, h.at, h.dir)
    : h.plane ? onPlane(e.clientX, e.clientY, h.at, h.plane) : onLevel(e.clientX, e.clientY, h.at.y);
  if (from == null) return false;
  root.updateMatrixWorld(true);
  wallDrag = { root, key: h.key, handle: h, from, pointerId: e.pointerId, before: wallState(root), after: null, shown: null,
               inverse: root.matrixWorld.clone().invert() };
  if (h.kind === 'opening') { wallFocus = { id: root.userData.source.id, index: h.index }; wallPanel(root); }
  if (h.kind === 'hole') { wallFocus = { id: root.userData.source.id, index: h.index }; slabPanel(root); }
  showPop(null);
  renderer.domElement.setPointerCapture(e.pointerId);
  renderer.domElement.style.cursor = 'grabbing';
  return true;
}
// The point where the pointer's ray meets the level at view height y (null when it runs along it).
function onLevel(clientX, clientY, y) {
  return rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -y), new THREE.Vector3());
}
// The point where the pointer's ray meets the plane through `at` square to `normal` (null when it runs along it).
function onPlane(clientX, clientY, at, normal) {
  return rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(normal, at), new THREE.Vector3());
}
// A handle's drag asks the server for one made mesh at a time, the latest state, while the numbers and pose change at
// once (so the handles follow the pointer): each answer for a long or tall wall takes a while, and asking for every
// step had piled them up behind each other (the user, 19 November 2026: the gaps lagged far behind their handles).
function applyWallSoon(root, state) {
  const o = root.userData.source;
  o.added = { ...o.added, generated: structuredClone(versionedGround(state.generated)) };
  gizmo.applyMatrices([root], [movedMatrix(o, state.location, state.rotation)]);
  root.updateMatrixWorld(true);
  const q = root.userData.applyQueue ??= { busy: false, next: null };
  q.next = state;
  if (q.busy) return;
  q.busy = true;
  (async () => {
    try { while (q.next) { const s = q.next; q.next = null; await applyWall(root, s); } } finally { q.busy = false; }
  })();
}
// The drag's queued states dropped (its last state is then applied by setWall, or the one before it put back).
function dropQueuedWall(root) { if (root?.userData.applyQueue) root.userData.applyQueue.next = null; }
function moveSlabDrag(e) {
  const d = wallDrag, h = d.handle, b = d.before, s = b.generated.slab;
  let slab = s, location = b.location, words;
  if (h.part === 'middle') {
    const at = onLevel(e.clientX, e.clientY, h.at.y);
    if (!at) return;
    // the pointer's move in the slab's own frame (its x and y), a hole slid by whole tiles each way
    const inv = new THREE.Matrix4().copy(d.root.matrixWorld).invert();
    const a = d.from.clone().applyMatrix4(inv), c = at.clone().applyMatrix4(inv);
    slab = movedHole(movedHole(s, h.index, 'x', c.x - a.x), h.index, 'y', c.z - a.z);
    words = holeWords(slab.holes[h.index]);
  } else {
    const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
    if (t == null) return;
    if (h.kind === 'side') {
      const r = resizedSlab(s, h.part, t - d.from);
      slab = r.slab;
      const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.root.matrixWorld))
        .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
      location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
      words = `${slabWords(slab)}${r.removed ? ` · ${plural(r.removed, 'hole')} past the edge will go` : ''}`;
    } else {
      slab = movedHole(s, h.index, h.part, t - d.from);
      words = holeWords(slab.holes[h.index]);
    }
  }
  const key = JSON.stringify([slab, location]);
  if (key === d.shown) return;
  d.shown = key;
  d.after = { generated: { ...b.generated, slab }, location, rotation: b.rotation };
  applyWallSoon(d.root, d.after);
  volumeHint(words);
}
function moveGroundDrag(e) {
  const d = wallDrag, h = d.handle, b = d.before, g0 = b.generated.ground;
  const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
  if (t == null) return;
  let g = g0, location = b.location;
  if (h.part === 'top') g = raisedGround(g0, t - d.from);
  else {
    const r = resizedGround(g0, h.part, t - d.from);
    g = r.ground;
    const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.root.matrixWorld))
      .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
    location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
  }
  const key = JSON.stringify([g, location]);
  if (key === d.shown) return;
  d.shown = key;
  d.after = { generated: { ...b.generated, ground: g }, location, rotation: b.rotation };
  applyWallSoon(d.root, d.after);
  volumeHint(`${groundShapeWords(g)}${g.shape === 'ramp' ? ` · ${slopeWords(g)}` : ''}`);
}
function moveWallDrag(e) {
  if (isMadeGround(wallDrag.root.userData.source)) { moveGroundDrag(e); return; }
  if (isMadeSlab(wallDrag.root.userData.source)) { moveSlabDrag(e); return; }
  const d = wallDrag, h = d.handle, b = d.before, w = b.generated.wall;
  let wall = w, location = b.location, words, delta = 0;
  if (h.plane) {
    // (the gap's middle: the pointer's move in the wall's plane, in its frame: along it and up)
    const at = onPlane(e.clientX, e.clientY, h.at, h.plane);
    if (!at) return;
    const a = d.from.clone().applyMatrix4(d.inverse), c = at.clone().applyMatrix4(d.inverse);
    const [along, up] = e.altKey ? [GAP.fine, GAP.fine] : OPENING_STEPS[snapMode];
    wall = movedOpening(w, h.index, 'middle', [c.x - a.x, c.y - a.y], { along, up });
    words = `${openingWords(sortedOpenings(wall.openings)[h.index], wall)} (${e.altKey ? `steps of ${GAP.fine}` : OPENING_STEP_WORDS[snapMode]})`;
  } else {
    const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
    if (t == null) return;
    delta = t - d.from;
  }
  if (h.plane) { /* moved above */ } else if (h.part === 'top') {
    const r = raisedWall(w, delta);
    wall = r.wall;
    words = `${wallWords(wall)}${r.cut ? ` · ${plural(r.cut, 'opening')} brought under the top` : ''}${r.removed ? ` · ${plural(r.removed, 'opening')} in the upper storey will go` : ''}`;
  } else if (h.kind === 'end') {
    // (out of the start end is back along the wall)
    const r = resizedWall(w, h.part, h.part === 'x0' ? -delta : delta);
    wall = r.wall; location = shiftedLocation(b.location, b.rotation, r.shift);
    words = `${wallWords(wall)}${r.removed ? ` · ${plural(r.removed, 'opening')} past the end will go` : ''}`;
  } else {
    const [along, up] = e.altKey ? [GAP.fine, GAP.fine] : OPENING_STEPS[snapMode];
    wall = movedOpening(w, h.index, h.part, delta, { along, up });
    words = `${openingWords(sortedOpenings(wall.openings)[h.index], wall)} (${e.altKey ? `steps of ${GAP.fine}` : OPENING_STEP_WORDS[snapMode]})`;
  }
  // (numbers the tool doesn't make, which the mesh server and the Build would refuse, aren't applied: the drag stays
  // at its last state the tool makes; review finding 32)
  if (!toolWall(wall)) return;
  const key = JSON.stringify([wall, location]);
  if (key === d.shown) return;
  d.shown = key;
  d.after = { generated: { ...b.generated, wall }, location, rotation: b.rotation };
  applyWallSoon(d.root, d.after);
  volumeHint(words);
}
function endWallDrag(keep) {
  const d = wallDrag;
  if (!d) return false;
  wallDrag = null;
  dropQueuedWall(d.root);
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
  const lookName = look?.name ?? catalogued('wall', w?.look)?.name ?? short(data.meshes[originalOf(o)?.mesh]?.name ?? 'made from numbers');
  $('wallHead').textContent = `Wall · ${isPlain(g) ? 'plain' : lookName}`;
  lookRow('wall', g, lookName, tool);
  $('wallState').textContent = tool ? wallWords(w) : `${Math.round(w.x1 - w.x0)} long, made elsewhere: no handles here`;
  $('wallSize').textContent = tool ? `${wallWords(w)}. Its white handles lengthen or shorten it by whole tiles; the one on top adds or takes storeys.${wallPiecesWords(w)}`
    : `${Math.round(w.x1 - w.x0)} long: numbers this tool doesn't draw (made elsewhere), so it has no handles here; the Build makes it as it is.`;
  root.userData.joinsShown = root.userData.joins?.joins ?? [];
  const joined = joinWords(root.userData.joinsShown);
  if (joined) $('wallSize').textContent += ` ${joined}`;
  const list = $('wallOpenings'), openings = sortedOpenings(w.openings ?? []);
  const doors = doorBoxes(root);
  list.replaceChildren(...openings.map((p, index) => {
    const row = document.createElement('div');
    row.className = 'wallopening';
    row.classList.toggle('on', wallFocus?.id === o.id && wallFocus.index === index);
    // (a gap units walk through, with no wall under it to give cover, is a doorway: it wants a door; one they walk
    // through over a wall that gives cover, or one they neither walk through nor see through, plays oddly)
    const play = openingPlay(w, p), door = play.walk && doors.some(b => boxesMeet(openingWorldBox(root, p), b, 8));
    const words = playWords(w, p, { door });
    const warn = !play.tiles || (play.walk ? play.cover !== 'none' || !door : play.cover === 'none' || !play.sight);
    row.append(Object.assign(document.createElement('strong'), { textContent: openingWords(p, w) }),
               Object.assign(document.createElement('small'), { textContent: words, className: warn ? 'warn' : '' }));
    row.title = words;
    if (warn) row.insertAdjacentHTML('beforeend', '<svg class="i warnmark" role="img" aria-label="Plays oddly"><use href="#i-warn"/></svg>');
    const remove = Object.assign(document.createElement('button'), { type: 'button', textContent: '\u00d7', title: 'Remove: take this gap out of the wall' });
    remove.setAttribute('aria-label', 'Remove this gap');
    remove.disabled = !tool;
    remove.onclick = () => { wallFocus = null; changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } })); };
    row.append(remove);
    row.onmouseenter = () => { wallFocus = { id: o.id, index }; };
    return row;
  }));
  $('wallGap').disabled = !(tool && withOpening(w, 'doorway'));
  $('wallFlip').disabled = $('wallShuffle').disabled = !tool;
  breakRow('wall', g, o.keepsPieces);
  $('wallNote').textContent = `Made from numbers on ${look ? `${look.package}'s` : 'its donor\'s'} materials: it breaks as the game's walls do, `
    + 'a fragment at a time. Doorways, windows and holes are walked, seen and shot through by the lines between tiles\' centres. '
    + 'A break passes to the walls, floors and other fracturing pieces it touches, and from them to it, as between the game\'s.';
}
// ---- Break and Repair (custom geometry editing plan, B5): blasts set off on a made wall, floor or roof, each knocking
// out the fragments within its reach as the Build does (tools/bake/made_blasts.py), saved on the piece as blasts (D-4)
// so they stay where they are when it is made longer, taller or in another look.
const MAX_BLASTS = 64;
const BREAK_ROWS = ['wall', 'slab', 'piece'];     // the panels with a Break row: made walls, made slabs, the map's pieces (E6)
let breaking = null;      // { id }: the piece Break is on
let blastTiles = 1;
blastTiles = Math.min(3, Math.max(1, Math.round(Number(recall('workshop.blastTiles')) || 1)));
const blastMarker = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16),
  new THREE.MeshBasicMaterial({ color: 0xff7a3d, transparent: true, opacity: 0.25, depthTest: false, depthWrite: false }));
blastMarker.renderOrder = 9; blastMarker.visible = false; blastMarker.raycast = () => {}; world.add(blastMarker);
// The Break row of the wall, floor or piece panel (`kind`) for the piece's request `g` (its blasts, breaksFurther):
// Breaks further in battle shows on a broken piece the game keeps whole (`keeps`: the export's keepsPieces, its
// donor's for a copy or a made piece), most roofs and floors (F-139).
function breakRow(kind, g, keeps) {
  const n = g.blasts?.length ?? 0;
  $(`${kind}Break`).classList.toggle('on', Boolean(breaking));
  $(`${kind}BlastSize`).value = String(blastTiles);
  $(`${kind}Repair`).disabled = !n;
  $(`${kind}Broken`).textContent = n ? `Broken by ${plural(n, 'blast')}` : '';
  $(`${kind}FurtherRow`).hidden = !(keeps && n);
  $(`${kind}Further`).checked = Boolean(g.breaksFurther);
}
function startBreak() {
  const root = madeRoot(selected) ?? roots.get(selected), o = root?.userData.source;
  if (!root || !(isMadeWall(o) || isMadeSlab(o) || mapBreakable(o))) {
    flashHint('Pick a wall, floor or roof to break it: a made one, or one of the map\'s fracturing pieces'); return;
  }
  stopLookPick(); stopWallDrawing(); stopPlacing();
  breaking = { id: o.id };
  gizmo.hold(true);
  renderer.domElement.style.cursor = 'crosshair';
  for (const k of BREAK_ROWS) $(`${k}Break`).classList.add('on');
  flashHint(`Click the ${isMadeSlab(o) ? 'floor' : isMadeWall(o) ? 'wall' : 'piece'} where a blast goes off: it knocks out the fragments within ${plural(blastTiles, 'tile')} · Esc stops`);
}
function stopBreak() {
  if (!breaking) return;
  breaking = null;
  gizmo.hold(false);
  renderer.domElement.style.cursor = '';
  blastMarker.visible = false;
  for (const k of BREAK_ROWS) $(`${k}Break`).classList.remove('on');
}
// Where a blast at the pointer goes off on the piece being broken: { point (the view's), at (its frame's: x, y, z) }.
function blastAt(x, y) {
  const root = breaking && roots.get(breaking.id), hit = root ? pick(x, y) : null;
  if (!hit || roots.get(hit.object.userData.objectId) !== root) return null;
  // (in its mesh's frame, the made numbers' frame: x along, y across, z up)
  hit.object.updateMatrixWorld();
  const p = hit.object.worldToLocal(hit.point.clone());
  return { point: hit.point, at: [p.x, p.z, p.y].map(v => Math.round(v * 10) / 10) };
}
function breakAt(x, y) {
  if (selected !== breaking.id) { stopBreak(); return; }
  const b = blastAt(x, y);
  if (!b) { flashHint('Click on the piece itself · Esc stops'); return; }
  const piece = roots.get(breaking.id);
  if (mapBreakable(piece?.userData.source)) {
    changeBlasts(piece, blasts => {
      if (blasts.length < MAX_BLASTS) return [...blasts, { at: b.at, radius: blastTiles * TILE }];
      flashHint(`It has the most blasts a piece takes (${MAX_BLASTS}): Repair mends it as the map has it`);
      return undefined;
    });
    return;
  }
  changeWall(s => {
    const blasts = s.generated.blasts ?? [];
    if (blasts.length >= MAX_BLASTS) { flashHint(`It has the most blasts a piece takes (${MAX_BLASTS}): Repair mends it whole`); return null; }
    return { ...s, generated: { ...s.generated, blasts: [...blasts, { at: b.at, radius: blastTiles * TILE }] } };
  });
}
renderer.domElement.addEventListener('pointermove', e => {
  if (!breaking) return;
  const b = blastAt(e.clientX, e.clientY);
  blastMarker.visible = Boolean(b);
  if (b) { blastMarker.position.copy(world.worldToLocal(b.point.clone())); blastMarker.scale.setScalar(blastTiles * TILE); }
});
for (const k of BREAK_ROWS) {
  $(`${k}Break`).onclick = () => (breaking ? stopBreak() : startBreak());
  $(`${k}BlastSize`).onchange = e => {
    blastTiles = Number(e.target.value) || 1;
    remember('workshop.blastTiles', String(blastTiles));
    for (const j of BREAK_ROWS) $(`${j}BlastSize`).value = String(blastTiles);
  };
  if (k === 'piece') {
    $('pieceRepair').onclick = () => { const r = roots.get(selected); if (mapBreakable(r?.userData.source)) changeBlasts(r, () => null); };
    $('pieceFurther').onchange = e => {
      const r = roots.get(selected);
      if (mapBreakable(r?.userData.source) && r.userData.blasts?.length) setBroken(r, { blasts: r.userData.blasts, further: e.target.checked });
    };
    continue;
  }
  $(`${k}Repair`).onclick = () => changeWall(s => {
    if (!s.generated.blasts) return null;
    const { blasts: _, breaksFurther: __, ...generated } = s.generated;
    return { ...s, generated };
  });
  $(`${k}Further`).onchange = e => changeWall(s => {
    if (!s.generated.blasts) return null;
    const { breaksFurther: _, ...generated } = s.generated;
    return { ...s, generated: e.target.checked ? { ...generated, breaksFurther: true } : generated };
  });
}
// ---- Break on the map's own fracturing pieces (custom geometry editing plan, E6, decision D-5): the same blasts on
// any of the map's fracturing pieces or a copy of one, saved on its record (an override's or added copy's `blasts`,
// in its mesh's frame). The Build paints out the fragments whose middle (that of their vertices' box) a blast
// reaches, with those the map paints out (tools/bake/made_blasts.py fragment_centres, hidden_at); the page works the
// middles out the same way from the mesh it draws and draws the piece without those fragments.
const FRACTURING_CLASSES = new Set(['XComFracLevelActor', 'XComDecoFracLevelActor']);
function mapBreakable(o) {
  return Boolean(o && !o.cover && !o.added?.generated && FRACTURING_CLASSES.has(o.actorClass)
    && data?.meshes[o.mesh]?.sections?.some(s => s.fragments?.length));
}
// A root's parts with the sections they draw: [{ section, part }] (the glb has a primitive for each section with
// triangles, in order); none when they don't match.
function sectionParts(root) {
  const parts = root.userData.parts ?? [], sections = (data.meshes[root.userData.source.mesh].sections ?? []).filter(s => s.count);
  return sections.length === parts.length ? sections.map((section, k) => ({ section, part: parts[k] })) : [];
}
// Where each fragment's triangles lie in a section's primitive: [start, count] in its indices (null: none drawn), as
// the export wrote them (its fragments' ranges, packed in order where the map paints fragments out: export.py).
function fragmentSpans(mesh, section) {
  const mask = mesh.fragmentMask;
  let packed = 0;
  return section.fragments.map(([first, triangles], i) => {
    if (!mask) return triangles ? [first - section.first, 3 * triangles] : null;
    if (!mask[i]) return null;
    const at = packed;
    packed += 3 * triangles;
    return triangles ? [at, 3 * triangles] : null;
  });
}
const fragmentMiddles = new Map();     // mesh key -> [[x, y, z] | null]: each fragment's middle in its mesh's frame
function middlesOf(root) {
  const key = root.userData.source.mesh, mesh = data.meshes[key];
  if (fragmentMiddles.has(key)) return fragmentMiddles.get(key);
  const lo = [], hi = [];
  for (const { section, part } of sectionParts(root)) {
    const g = part.userData.baseGeometry ?? part.geometry, idx = g.index.array, pos = g.attributes.position;
    fragmentSpans(mesh, section).forEach((span, i) => {
      if (!span) return;
      for (let k = span[0]; k < span[0] + span[1]; ++k) {
        const v = idx[k], p = [pos.getX(v), pos.getZ(v), pos.getY(v)];     // (the mesh's frame: z up)
        if (!lo[i]) { lo[i] = [...p]; hi[i] = [...p]; continue; }
        for (let a = 0; a < 3; ++a) { lo[i][a] = Math.min(lo[i][a], p[a]); hi[i][a] = Math.max(hi[i][a], p[a]); }
      }
    });
  }
  const n = Math.max(0, ...(mesh.sections ?? []).map(s => s.fragments?.length ?? 0));
  const out = Array.from({ length: n }, (_, i) => (lo[i] ? lo[i].map((v, a) => (v + hi[i][a]) / 2) : null));
  fragmentMiddles.set(key, out);
  return out;
}
// The fragments a root's blasts knock out (made_blasts.hidden_at), in order.
function knockedOut(root) {
  const blasts = root.userData.blasts ?? [];
  if (!blasts.length) return [];
  return middlesOf(root).flatMap((c, i) => (c && blasts.some(b => Math.hypot(c[0] - b.at[0], c[1] - b.at[1], c[2] - b.at[2]) <= b.radius) ? [i] : []));
}
// A root drawn without the fragments its blasts knock out (each part a geometry of its own then, with the mesh's
// attributes and the kept triangles), or with its mesh's own again. (The old geometry isn't disposed: it shares the
// mesh's attributes, which other pieces draw.)
function drawBroken(root) {
  const mesh = data.meshes[root.userData.source.mesh], gone = new Set(knockedOut(root));
  for (const { section, part } of sectionParts(root)) {
    const base = part.userData.baseGeometry ?? part.geometry;
    if (!gone.size) { part.geometry = base; delete part.userData.baseGeometry; continue; }
    part.userData.baseGeometry = base;
    const idx = base.index.array, kept = [];
    fragmentSpans(mesh, section).forEach((span, i) => {
      if (span && !gone.has(i)) for (let k = span[0]; k < span[0] + span[1]; ++k) kept.push(idx[k]);
    });
    const g = new THREE.BufferGeometry();
    for (const [name, attribute] of Object.entries(base.attributes)) g.setAttribute(name, attribute);
    g.setIndex(kept);
    g.boundingBox = base.boundingBox?.clone() ?? null;
    g.boundingSphere = base.boundingSphere?.clone() ?? null;
    part.geometry = g;
  }
}
// One of the map's pieces given other blasts (`change` from its blasts to the new ones; null mends it, and takes
// Breaks further in battle off with them; undefined changes nothing), as one undo step.
function changeBlasts(root, change) {
  const before = root.userData.blasts ?? null, next = change(before ? cloneBlasts(before) : []);
  if (next === undefined) return;
  const after = next?.length ? next : null;
  if (JSON.stringify(after) === JSON.stringify(before)) return;
  setBroken(root, { blasts: after, further: Boolean(after && root.userData.breaksFurther) });
}
// One of the map's pieces broken as `after` says ({ blasts, further: Breaks further in battle }), as one undo step.
function setBroken(root, after) {
  const before = { blasts: root.userData.blasts ?? null, further: Boolean(root.userData.breaksFurther) };
  const id = root.userData.source.id;
  const set = v => {
    root.userData.blasts = v.blasts ? cloneBlasts(v.blasts) : null; root.userData.breaksFurther = v.further;
    drawBroken(root); select(id, false, true);
  };
  gizmo.record({ redo: () => set(after), undo: () => set(before) });
}
// The Lower and Taller buttons of the room panel (`kind` 'room': a picked wall's own top handle does it) for the wall
// `w` (null: neither).
function storeyButtons(kind, w) {
  const down = w && steppedStoreys(w, -1), up = w && steppedStoreys(w, 1), spec = w ? wallSpec(w) : null;
  const tall = x => `${storeyWords(storeysOf(x.wall))} (${Math.round(wallTop(x.wall) - spec.bottom)} tall)`;
  $(`${kind}Shorter`).disabled = !down;
  $(`${kind}Storeys`).disabled = !up;
  $(`${kind}Shorter`).title = down ? `Lower: ${tall(down)}${down.removed ? '; openings over its top go' : ''}`
    : w ? 'As low as its look is made' : '';
  $(`${kind}Storeys`).title = up ? `Taller: ${tall(up)}${storeysOf(up.wall) > spec.storeys ? `; the Build stacks walls of its look's ${storeyWords(spec.storeys)}` : ''}`
    : w ? `As tall as a wall is drawn here (${storeyWords(WALL.maxStoreys)})` : '';
}
// ---- the piece panel's Floor section (made slabs)
function slabPanel(root) {
  const o = root.userData.source, s = o.added.generated.slab, look = slabLookOf(s), tool = toolSlab(s);
  $('slabHead').textContent = `${look?.role === 'roof' ? 'Roof' : 'Floor'} · ${isPlain(o.added.generated) ? 'plain' : look?.name ?? 'made from numbers'}`;
  lookRow('slab', o.added.generated, look?.name ?? 'made from numbers', tool);
  const cut = slabTiles(s).some(n => n > SLAB.pieceTiles)
    ? ` The Build makes it as slabs of at most ${SLAB.pieceTiles} by ${SLAB.pieceTiles} tiles side by side: they break as one.` : '';
  breakRow('slab', o.added.generated, o.keepsPieces);
  $('slabState').textContent = tool ? slabWords(s) : 'Made elsewhere: no handles here';
  $('slabSize').textContent = tool ? `${slabWords(s)}. Its white handles grow or shrink it by whole tiles.${cut}`
    : 'Numbers this tool doesn\'t draw (made elsewhere), so it has no handles here; the Build makes it as it is.';
  const holes = s.holes ?? [];
  $('slabHoles').replaceChildren(...holes.map((h, index) => {
    const row = document.createElement('div');
    row.className = 'wallopening';
    row.classList.toggle('on', wallFocus?.id === o.id && wallFocus.index === index);
    row.append(Object.assign(document.createElement('strong'), { textContent: holeWords(h) }),
               Object.assign(document.createElement('small'), { textContent: 'Open: units fall through it only as the game lets them (they don\'t); a ladder or stairs of the game\'s go in it' }));
    row.title = row.querySelector('small').textContent;
    const remove = Object.assign(document.createElement('button'), { type: 'button', textContent: '\u00d7', title: 'Remove: fill this hole' });
    remove.setAttribute('aria-label', 'Remove this hole');
    remove.disabled = !tool;
    remove.onclick = () => { wallFocus = null; changeWall(st => ({ ...st, generated: { ...st.generated, slab: withoutHole(st.generated.slab, index) } })); };
    row.append(remove);
    row.onmouseenter = () => { wallFocus = { id: o.id, index }; };
    return row;
  }));
  $('slabHole').disabled = !tool || !withHole(s);
  $('slabShuffle').disabled = !tool;
  $('slabNote').textContent = `Made from numbers on ${look ? `${look.package}'s` : 'its donor\'s'} materials: it breaks as the game's `
    + `${look?.role === 'roof' ? 'roofs do' : 'floors do'}, a piece at a time, and a break passes to the walls and pieces it touches. `
    + (look?.role === 'roof' ? 'It is cut away with its building\'s top floor when the cursor is inside, and takes no clicks.'
      : 'Units walk on it where there is standing room over it; a hole in it is no floor.');
}
$('slabHole').onclick = () => {
  const root = madeRoot(selected);
  if (!root || !isMadeSlab(root.userData.source)) return;
  const r = withHole(root.userData.source.added.generated.slab);
  if (!r) { flashHint('Every tile of it is a hole'); return; }
  wallFocus = { id: root.userData.source.id, index: r.index };
  changeWall(st => ({ ...st, generated: { ...st.generated, slab: r.slab } }));
  flashHint('Added a hole, one tile · its blue handles move and size it');
};
$('slabShuffle').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, slab: reshuffledSlab(st.generated.slab) } }));
// ---- the piece panel's Ground section (M6)
function groundPanel(root) {
  const o = root.userData.source, g = o.added.generated.ground, look = groundLookOf(g), tool = toolGround(g);
  const plain = isPlain(o.added.generated);
  $('groundHead').textContent = `Ground · ${plain ? 'plain' : look?.name ?? 'made from numbers'}`;
  lookRow('ground', o.added.generated, look?.name ?? 'made from numbers', tool);
  $('groundState').textContent = tool ? groundShapeWords(g) : 'Made elsewhere: no handles here';
  $('groundSize').textContent = tool ? `${groundShapeWords(g)}. Its white handles size it by whole tiles${g.shape === 'patch' ? '' : '; the one on top raises or lowers it'}.`
    : 'Numbers this tool doesn\'t draw (made elsewhere), so it has no handles here; the Build makes it as it is.';
  const words = slopeWords(g);
  $('groundSlope').hidden = !words;
  $('groundSlope').textContent = words ? words[0].toUpperCase() + words.slice(1) + '.' : '';
  $('groundSlope').classList.toggle('warn', slopeOf(g) > GROUND.sloped);
  $('groundTurn').hidden = g.shape !== 'ramp';
  $('groundTurn').disabled = !tool;
  $('groundAnother').hidden = $('groundResetPoints').hidden = g.shape !== 'rock';
  $('groundAnother').disabled = !tool;
  $('groundResetPoints').disabled = !tool || !g.points;
  if (g.shape === 'rock' && tool)
    $('groundSize').textContent += g.points ? ' Its corners have been moved: its blue points move them again (click one, then drag its arrows).'
      : ' Its blue points are its corners: click one, then drag its arrows to move it.';
  $('groundNote').textContent = `Made from numbers on ${look ? `${look.package}'s ${look.name.toLowerCase()}` : 'its donor\'s material'}: `
    + (g.shape === 'rock' ? 'it stands in the way and gives cover by its height, as the game\'s rocks do, and it doesn\'t break.'
      : 'units walk on it and it doesn\'t break.')
    + (g.shape === 'patch' ? ' Its top lies level with the ground it covers, its plate under it.' : '');
}
$('groundAnother').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, ground: anotherRock(st.generated.ground) } }));
$('groundResetPoints').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, ground: resetRock(st.generated.ground) } }));
$('groundTurn').onclick = () => changeWall(st => {
  const t = turnedGround(st.generated.ground, st.location, st.rotation);
  return { generated: { ...st.generated, ground: t.ground }, location: t.location, rotation: t.rotation };
});
/** A made piece in another look (M4c: a look id, or a donor look from the picker or the eyedropper): made again on that
 *  look's donor where it stands, its numbers kept (a wall's openings brought under its new face's top), in one undo
 *  step; the tool's next pieces take the look too. */
// The pieces a look change takes: the made pieces of its kind picked now; a lone wall picked takes the walls joined to
// it, end to end or at corners, so a room or a run changes whole (the user, 19 November 2026: a room's look changed
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
// ---- a room (custom geometry editing plan, B3): a drawn room is one locked group; picked whole, the panel is the
// room's, its walls' and roof's own sections hidden (Ungroup edits them one by one)
function madeLookName(root) {
  const o = root.userData.source, g = o.added.generated;
  if (isPlain(g)) return null;
  if (g.kind === 'fracWall') return wallLookOf(o)?.name ?? catalogued('wall', g.wall?.look)?.name ?? 'made from numbers';
  if (g.kind === 'fracSlab') return slabLookOf(g.slab)?.name ?? 'made from numbers';
  return groundLookOf(g.ground)?.name ?? 'made from numbers';
}
// The picked group as a room: its made walls (three or more, each joined at both ends to another of them) and the
// made slab on them (its roof), with nothing else but its building; or null.
function roomOfSelection() {
  const { kind, group: g } = selectionGroup();
  if (kind !== 'whole' || !g) return null;
  const keys = liveKeys(g), rs = keys.filter(k => !k.startsWith('building|')).map(k => liveMembers().get(k)?.[0]).filter(Boolean);
  const walls = rs.filter(r => isMadeWall(r.userData.source)), slabs = rs.filter(r => isMadeSlab(r.userData.source));
  if (walls.length < 3 || slabs.length > 1 || walls.length + slabs.length !== rs.length) return null;
  const ids = new Set(walls.map(r => r.userData.source.id));
  if (!walls.every(r => new Set((r.userData.joins?.joins ?? []).filter(j => ids.has(j.other)).map(j => j.end)).size === 2)) return null;
  return { group: g, walls, roof: slabs[0] ?? null };
}
let roomShown = null;
function roomPanel() {
  const room = roomShown = volumeRoots.has(selected) ? null : roomOfSelection();
  $('roomBox').hidden = !room;
  if (!room) return;
  $('wallBox').hidden = $('slabBox').hidden = true;
  const box = new THREE.Box3();
  for (const r of room.walls) box.expandByObject(r);
  const tiles = [Math.round((box.max.x - box.min.x) / TILE), Math.round((box.max.z - box.min.z) / TILE)];
  const w = room.walls[0].userData.source.added.generated.wall, names = new Set(room.walls.map(madeLookName));
  const tool = room.walls.every(r => toolWall(r.userData.source.added.generated.wall));
  $('roomHead').textContent = `Room · ${tiles[0]} by ${tiles[1]} tiles`;
  $('roomState').textContent = `${plural(room.walls.length, 'wall')}, ${storeyWords(storeysOf(w))}${room.roof ? ', a roof' : ''} · picked as one`;
  $('roomSize').textContent = `${plural(room.walls.length, 'wall')}, ${storeyWords(storeysOf(w))}${room.roof ? ', a roof' : ''}. Picked as one: it moves, turns and copies whole. Ungroup it to edit its walls one by one: their gaps, doors and own looks.`;
  const wallWord = names.size > 1 ? 'Walls: mixed looks' : names.has(null) ? 'Walls: no look chosen' : `Walls: ${[...names][0]}`;
  $('roomWallsLook').textContent = wallWord;
  $('roomWallsLook').classList.toggle('warn', names.has(null));
  $('roomWallsChoose').disabled = !tool;
  $('roomWallsPlain').disabled = !tool || (names.size === 1 && names.has(null));
  $('roomRoofRow').hidden = !room.roof;
  if (room.roof) {
    const name = madeLookName(room.roof);
    $('roomRoofLook').textContent = name ? `Roof: ${name}` : 'Roof: no look chosen';
    $('roomRoofLook').classList.toggle('warn', !name);
    $('roomRoofPlain').disabled = !name;
  }
  // (a room with a roof keeps its height: its roof and building stand on its walls' tops)
  $('roomStoreysRow').hidden = Boolean(room.roof);
  storeyButtons('room', tool && !room.roof ? w : null);
}
$('roomWallsChoose').onclick = () => { const r = roomShown; if (r) openLookPicker('wall', { onChoose: look => setMadeLook(r.walls[0], 'wall', look) }); };
$('roomWallsPlain').onclick = () => { const r = roomShown; if (r) setMadeLook(r.walls[0], 'wall', plainLook('wall')); };
$('roomRoofChoose').onclick = () => { const r = roomShown; if (r?.roof) openLookPicker('slab', { onChoose: look => setMadeLook(r.roof, 'slab', look) }); };
$('roomRoofPlain').onclick = () => { const r = roomShown; if (r?.roof) setMadeLook(r.roof, 'slab', plainLook('slab', r.roof.userData.source.added.generated.slab)); };
// (a room with no roof: its walls a storey lower or taller, in one undo step)
function roomStoreys(step) {
  const r = roomShown;
  if (!r) return;
  const stepped = steppedStoreys(r.walls[0].userData.source.added.generated.wall, step);
  if (!stepped) return;
  const next = storeysOf(stepped.wall), before = r.walls.map(wallState);
  r.walls.forEach((root, k) => setWall(root, { ...before[k], generated: { ...before[k].generated, wall: withStoreys(before[k].generated.wall, next).wall } }, before[k]));
  gizmo.joinLast(r.walls.length);
  flashHint(`Its walls now ${storeyWords(next)} · Ctrl+Z puts them back`);
}
$('roomStoreys').onclick = () => roomStoreys(1);
$('roomShorter').onclick = () => roomStoreys(-1);
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
  const pts = [], half = wallSpec(root.userData.source.added?.generated?.wall).half;
  for (const x of [p.x0, p.x1]) for (const y of [-half, half]) for (const z of [p.z0, p.z1]) {
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
// Add gap (the user, 19 November 2026: one button for the doorway's and the window's, as gaps are one kind): a gap
// shaped as the game's doorways, which its middle handle takes up to make a window. (`kind` 'window': the tests'.)
$('wallGap').onclick = () => addWallOpening('doorway');
function addWallOpening(kind = 'doorway') {
  const root = madeWallRoot(selected);
  if (!root) return;
  const r = withOpening(root.userData.source.added.generated.wall, kind);
  if (!r) { flashHint('Every tile of the wall has an opening'); return; }
  wallFocus = { id: root.userData.source.id, index: r.index };
  changeWall(s => ({ ...s, generated: { ...s.generated, wall: r.wall } }));
  flashHint('Added a gap · its blue handles move and size it, and cut the wall to its edges; drag its middle up to make a window');
}
$('wallFlip').onclick = () => changeWall(s => {
  const f = flippedWall(s.generated.wall, s.location, s.rotation);
  return { generated: { ...s.generated, wall: f.wall }, location: f.location, rotation: f.rotation };
});
$('wallShuffle').onclick = () => changeWall(s => ({ ...s, generated: { ...s.generated, wall: reshuffled(s.generated.wall) } }));
// Delete with an opening's handle last touched takes that opening out (the wall stays): true when it did.
function deleteWallOpening() {
  const slabRoot = madeRoot(selected);
  if (slabRoot && isMadeSlab(slabRoot.userData.source) && wallFocus?.id === slabRoot.userData.source.id && handleWall()) {
    const index = wallFocus.index;
    if (index >= (slabRoot.userData.source.added.generated.slab.holes ?? []).length) return false;
    wallFocus = null;
    changeWall(st => ({ ...st, generated: { ...st.generated, slab: withoutHole(st.generated.slab, index) } }));
    flashHint('Filled the hole · Ctrl+Z opens it again');
    return true;
  }
  const root = madeWallRoot(selected);
  if (!root || wallFocus?.id !== root.userData.source.id || !handleWall()) return false;
  const index = wallFocus.index;
  if (index >= (root.userData.source.added.generated.wall.openings ?? []).length) return false;
  wallFocus = null;
  changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } }));
  flashHint('Removed the opening · Ctrl+Z puts it back');
  return true;
}
$('playAreaToggle').onchange = e => { setPlayArea(e.target.checked); e.target.blur(); };
const WHOLE_OVERHANG = 4 * TILE;    // four tiles
function cutaway() {
  touchShadows();
  cutKey = editedKey();
  // The floor cut applies to every building at once (the user's choice, 7 November: no building list).
  const requested = $('floor').value ?? 'all';
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
let floorTileLayer = null, tileOwners = null;     // (tipDirty: editor_state.js)
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
  setTipDirty(false);
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
// (missionIndex, the picker's value, missionPickValue, and the streams shown, streamSet: editor_state.js)
// (an added kind the address asks for, askedPick: editor_state.js)
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
  if (askedPick && list.some(m => m.value === askedPick)) { chooseMission(askedPick); setAskedPick(null); }
  $('missionPick').hidden = list.length < 2;
  $('mission').replaceChildren(...list.map(m => new Option(m.label, m.value)));
  if (!list.some(m => m.value === missionPickValue)) chooseMission(list[0]?.value ?? '0');
  $('mission').value = missionPickValue;
  if (missionPickValue !== before) { refreshLightVisibility(); refreshSpawnMarkers(); placeMissionGizmo(); cutaway(); }
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
  if (v.startsWith('kind:')) { setMissionPickValue(v); setMissionIndex(-1); setStreamSet(new Set()); return; }
  const index = Number(v);
  setMissionIndex(Number.isInteger(index) && missions[index] ? index : 0);
  setMissionPickValue(String(missionIndex));
  setStreamSet(new Set(missions[missionIndex]?.streams ?? []));
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
  cachePrefix='/cache/'+encodeURIComponent(activeMapId)+'/';
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
// Both maps and the prefab workspace start the same editor on a scene.
async function startScene({ parameters, familiesAsked, mapName }) {
  setMergedBuildings(null);
  // No layout menu any more (the user's choice, 7 November): a patch preview (Bar's EXP-07 and EXP-08 layouts)
  // opens only from its address, ?scene=preview-<n>.json.
  document.title = `${data.name} · XCOM Map Workshop`;
  $('previewChip').hidden = !data.preview;
  // Configure light data before the first lit material compiles.
  setLighting(createMapLighting({ world, sun, hemisphere, scene: data, maxTextureSize:renderer.capabilities.maxTextureSize }));
  $('scenery').value=data.preview ? 'full' : data.tactical?.recommendedView || 'full';
  $('sceneryGroup').hidden=!data.playableBounds || data.scope!=='map';
  $('projectSize').hidden = !projectsAvailable();     // Map grid: any whole map
  $('projectClear').hidden = !projectsAvailable();
  $('projectMissions').hidden = !projectsAvailable();
  $('projectPicture').hidden = !projectsAvailable();
  ownGrid = null; startingCache = null; landingLines = { kind: null, lines: [] };
  // the install's landing lines for the map (Clear map plan, section 4): the starting list of landing zones. A failed
  // read leaves the game unknown, with the reason (review finding 31).
  if (data.scope === 'map' && !data.preview && !builderMode && activeMapId)
    setLandingRead(fetch(`/maps/${encodeURIComponent(activeMapId)}/landing-lines.json`)
      .then(async r => {
        const v = await r.json().catch(() => null);
        if (!r.ok || !v || !Array.isArray(v.lines)) throw new Error(v?.error ?? `the editor's server answered ${r.status}`);
        return v;
      })
      .then(v => { landingLines = v; }, error => {
        landingLines = { kind: null, lines: [], failed: String(error?.message ?? error) };
        banner(`The game install's landing lines for this map couldn't be read (${landingLines.failed}), so the editor doesn't know which game is set: the Long War landing lines are missing and Long War only missions aren't checked. Open the map again to ask again.`);
      })
      .then(() => { startingCache = null; refreshGroundGrid(); refreshLandingZones(); }));
  drawPlayArea();
  for (const button of $('lighting').querySelectorAll('button')) button.disabled = button.dataset.value !== 'neutral' && !lighting.available;
  // Neutral light by default: our map lighting is an approximation (the user's choice, 7 November).
  $('lighting').value = 'neutral';
  // What the original layout's missions stream into the map (export 13), shown for reference and never edited.
  const streamObjects = data.preview ? [] : Object.values(data.streams || {}).flatMap(s => s.objects);
  chooseMission(parameters.get('mission') ?? '0');
  if (parameters.get('project') && parameters.get('mission')?.startsWith('kind:')) setAskedPick(parameters.get('mission'));
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
    catch (e) { console.error(obj.actor, e); setLoadErrorCount(loadErrorCount + 1); }
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
  placeObjects(); floorOptions(); frame();
  applyLighting = () => {
    // the lights as edited (lightRecords), when they changed since
    if (lightsDirty && data.scope === 'map' && !data.preview) {
      lighting.setLights(lightRecords()); setLightsDirty(false); setLastLightSync(performance.now());
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
  void refreshInstalls();     // the header's Play button goes by them
  if (!projectsAvailable()) $('projectButton').title = 'Project: open one (Ctrl+O). Saving needs the map\'s original layout: open the map from the map browser (M)';
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
    $('projectButton').title = 'Prefab: Save and Open';
    $('mapButton').querySelector('small').textContent = 'Prefab';
    $('mapButton').title = 'Open a map or prefab (M)';
    $('projectLoad').querySelector('span').textContent = 'Open…';
    const loadProjectButton = text($('projectLoad').parentElement, 'button', 'Load project…');
    loadProjectButton.type = 'button'; loadProjectButton.onclick = () => showFileDialog('load');
    setLibraryScope('all');
    await openPrefabDocument(prefabParameter);
    void prefabTest.reconnect();
  } else if (parameters.get('project')) await openProject(parameters.get('project'));
  window.viewer = {data, mapId:activeMapId, mapPicture, gizmo, renderer, world, camera, controls, roots, select, frame, lighting, sun, hemisphere, grid,
    // the selected cover piece's handles on the screen ({ key: [x, y] }, none when they don't show), and a record put on a
    // cover piece as one undo step (for scripts: the guide's shots, the checks)
    // (each [x, y, x', y']: the handle, and where a point `tiles` tiles further out along its face's axis is, in below 0)
    coverHandles: (tiles = 1) => { const r = handleCover(), project = projector();
      return r ? Object.fromEntries(coverFacesNow(r).map(f => { const p = coverHandlePoint(f);
        return [f.face[0], [...project(p), ...project(p.clone().addScaledVector(f.dir, TILE * tiles))]]; })) : {}; },
    setCover: (id, cover) => { const r = roots.get(id); if (r?.userData.source.cover) setCover(r, normalCover(cover, coverRecipe())); },
    // made walls (custom geometry plan, M1): the Build menu's tools (B1), drawing, a game point on the screen, the picked
    // wall's handles on the screen ({ key: [x, y, x', y'] }: the handle and a point `units` along its drag axis), its state
    buildTools: () => Object.keys(BUILD_TOOLS), startBuild, buildTool: () => buildTool, startWallDrawing, stopWallDrawing,
    plainLook, isPlain: id => isPlain(roots.get(id)?.userData.source.added?.generated),
    // the group a piece is in: { id, locked, keys (its pieces' and buildings' keys, inner groups' too) } or null
    groupOf: id => { const r = roots.get(id), g = r && groupIndex.get(memberOf(r.userData.source));
                     return g ? { id: g.id, locked: g.locked, keys: liveKeys(g) } : null; },
    roomPicked: () => { const r = roomOfSelection(); return r && { walls: r.walls.map(w => w.userData.source.id), roof: r.roof?.userData.source.id ?? null }; },
    groundPanelText: () => sectionText('groundBox'),
    // looks from any piece (M4c): the picker, the eyedropper, a made piece's look changed, the catalogue read
    openLookPicker, closeLookPicker, startLookPick, lookPicking: () => lookPicking && { kind: lookPicking.kind },
    lookMode: () => (lookPicker?.isOpen ? lookPicker.state().kind : null), lookPickerState: () => lookPicker?.state() ?? null,
    setMadeLook: (id, kind, look) => setMadeLook(roots.get(id), kind, look),
    catalogued, lookFromEntry, storedLook,
    wallDrawing: () => wallDrawing && { look: wallDrawing.look.id, donor: wallDrawing.look.donor ?? null, room: wallDrawing.room, slab: wallDrawing.slab, roof: wallDrawing.roof, ground: wallDrawing.ground,
                                        ready: Boolean(wallDrawing.template && (!wallDrawing.roof || wallDrawing.roofTemplate)), drawing: Boolean(wallDrawing.start),
                                        last: wallDrawing.last ? { ...wallDrawing.last } : null },
    wallHandles: (units = TILE) => { const r = handleWall(), project = projector();
      return r ? Object.fromEntries(wallHandlesNow(r).map(h => { const p = wallHandlePoint(h);
        const way = h.dir ?? h.along;      // (a gap's middle, dragged in the wall's plane: along the wall)
        return [h.key, [...project(p), ...project(way ? p.clone().addScaledVector(way, units) : p)]]; })) : {}; },
    rockPoint: () => (rockPoint ? { ...rockPoint, gizmo: pointGizmo.enabled, up: pointGizmo.showY } : null),
    rockCorners: () => [...rockCorners.entries()].map(([k, v]) => [k, v?.then ? 'asking' : v]),
    wallState: id => { const r = madeRoot(id); return r ? wallState(r) : null; },
    slabPanelText: () => sectionText('slabBox'),
    buildingsNow: () => buildingsFromVolumes().map(b => ({ name: b.name, floors: b.floors.map(f => f.boxes) })),
    // the map's surface below a point (game x, y, from z down: 4096 when not given), as the wall tool and the Add panel
    // find the floor, and as invisible floors read it (the game's collision once it has come). (One key each for this
    // and screenOf: a second, later in the list, took its place; review finding 34.)
    groundAt: (x, y, fromZ = 4096) => groundAt(x, y, fromZ),
    wallMeshReady: id => { const r = madeRoot(id); return Boolean(r && loaded(geometryCache, r.userData.source.mesh)); },
    addWallOpening, wallPanelText: () => sectionText('wallBox'),
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
    // (the dialogs' keys and a state put on the map, for the browser checks: browser_editing.py)
    showPrepare, applyState,
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
    collisionRead: () => (lineCollision ? !lineCollisionFailed : null),
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
    setSpawnFilter: (family, on) => { setSpawnFilters({ ...spawnFilters, [family]: on }); syncSpawnFilters(); refreshSpawnMarkers(); },
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
    setPickBox: box => { setPickBoxValue([...box]); setPickToolValue(false); refreshPickBox(true); },
    pieceBox: id => (roots.get(id) ? boxOf(roots.get(id))?.slice() ?? null : null),
    pickMoveHandle: () => (pickBox ? projector()(viewPoint(pickMovePoint())) : null),
    pickFaceHandle: key => (pickBox ? projector()(viewPoint(handlePoint(pickBox, key))) : null),
    // the Buildings view, for the browser smoke test
    buildings: () => buildings, allBuildings, volumeRoots, volumesOn: () => volumesOn, setVolumesShown, volumeBox, addVolumes, newBuilding, setVolumeTool,
    volumeHandle: key => { const r = volumeRoots.get(selected); return r ? projector()(viewPoint(handlePoint(volumeBox(r), key))) : null; },
    ownPicked: () => ownPicked?.userData.own ?? null,
    // the map's own buildings made editable (map buildings plan), for the browser smoke test
    savedBuildings, restoreMapBuildings, copyVolumes, pasteVolumes, deleteVolumes, clipboard: () => clipboard,
    mapEdits: () => { const e = mapEdits(); return { changed: [...e.changed], gone: [...e.gone] }; },
    putVolume: (id, box) => { const r = volumeRoots.get(id); recordVolumes([r], () => setVolumeBox(r, box)); },
    listingsNow: id => roots.get(id) && listingsNow(roots.get(id)), floorTiles: () => floorTileLayer && floorTileLayer.userData.tiles.length,
    project: () => project && { id: project.doc.id, name: project.doc.name, revision: project.revision, dirty: dirty(), carried: project.carried, doc: project.doc },
    // this page's session (its drafts for recovery are kept under it) and its last build status (the document checks)
    session: SESSION, lastBuild: () => lastBuild };
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
segmented($('floor'), () => { cutaway(); ghostDirty = true; restingHint(); });
$('hideHelpers').onchange = () => cutaway();
segmented($('scenery'), () => {cutaway();frame();refreshLightVisibility();setEffectsDirty(true);});
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
renderer.domElement.addEventListener('pointermove', e => { setPointer([e.clientX, e.clientY]); ghostDirty = true; setTipDirty(true); });
renderer.domElement.addEventListener('pointerleave', () => { setPointer(null); ghostDirty = true; setTipDirty(true); });
controls.addEventListener('change', () => { ghostDirty = true; setTipDirty(true); });
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
  snapMode = next; gizmo.setSnap(next); ghostDirty = true;
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
lookPicker = createLookPicker({ prepare: prepareSample, tagsOf: lookTags, recall, remember, hint: flashHint });
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
