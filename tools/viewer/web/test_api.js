// The test hooks: window.viewer, what the browser checks (tools/viewer/tests/browser_*.py), the guide's pictures and
// the refactor's scripts drive and read. app.js's startScene sets it once a scene has opened (createTestApi's object).
// Every name a browser check uses is in the recorded list (tools/viewer/tests/viewer_api_names.json, which the api-names
// check holds on the Bar, the blank map and the prefab builder): a name added or taken out on purpose is written into
// it in the same change. The hooks are built from the modules' exports: the shared state (editor_state.js) and the
// pure modules' functions are imported here, a live binding each, and what app.js's factories return (with app.js's
// own objects and helpers, and the streamed objects startScene worked out) is given as one argument object.
import * as THREE from 'three';
import { TILE } from './constants.js';
import { normalCover } from './cover.js';
import { activeMapId, areaBindings, boxesShown, builderMode, buildings, buildTool, cleared, clearKeepsOutside,
         clipboard, copySerial, data, derivedCopies, effectMarkers, effectRoots, effectsDirty, effectsOn, families,
         floorTileLayer, geometryCache, gridTool, groupIndex, groups, handleDefs, landingLines, lastBuild, lastClearMs,
         library, lightDrag, lighting, lightRoots, lightsOn, lightsShown, likenessCount, likenessOn,
         likenessThin, lineCollision, lineCollisionFailed, lookPicker, lookPicking, missionIndex, missionMoves,
         missionPickValue, normalEffects, normalLights, normalSpawns, ownPicked, ownSet, pickBox, pickedEffect,
         pickedSpawn, pickedZone, pickHits, pickTool, pieces, placing, prefabTab, project, projectMissions,
         projectSpawnRules, reachNow, rockPoint, roots, selected, setPickBoxValue, setPickToolValue, setSpawnFilters,
         soloOn, spawnEntriesNow, spawnFilters, spawnPlacing, spawnRulesData, spawnsOn, stage, textureDrag,
         texturePicked, volumeRoots, volumesOn, wallDrawing, wavePlayer, zonesOn } from './editor_state.js';
import { catalogued, lookFromEntry } from './looks.js';
import { api as prefabApi } from './prefabs.js';
import { stateKey } from './project.js';
import { ownLandings } from './spawns.js';
import { spawnKey } from './spawns_view.js';
import { gameToView } from './handles.js';

export function createTestApi({ $, addVolumes, addWallOpening, alignToGamePose, alignToGrid, alignToLevel,
                                allBuildings, applyPrefabDocument, applyState,
                                bombHelperFix, boxOf, BUILD_TOOLS, builderDocument, builderRecords,
                                buildingsFromVolumes, camera, changes, choosePrefab, chosenStorey, clearMap, clearPlan,
                                closeLookPicker, controls, copySpawn, copyVolumes, coverFacesNow, coverHandlePoint,
                                coverRecipe, deleteSpawn, deleteVolumes, dirty, dropTarget, editBaseSpawn,
                                editSpawnCopy, editState, effectNow, effectShapes, effectViewOnly, FACES, fileDialog,
                                floorData, frame, ghostLikenesses, gizmo, goTo, grid, gridHandleAt, gridHandles,
                                gridNow, groundAt, groundGrid, groundHeight, handleCover, handlePoint, handleWall,
                                headerMissions, hemisphere, highlight, isPlain, keepRecovery, ladderMarks, ladderNow,
                                landingLayer, libraryTemplate, lightPanel, lightRecords, lightShapes, likenesses,
                                likenessPane, listingsNow, liveKeys, loaded, madeRoot, mapEdits, mapPicture, memberOf,
                                missionGizmo, missionProxy, missionsPanel, movedLandingActors, moveMissionGroup,
                                newBuilding, openLookPicker, openPrefabDocument, outsideBox, ownVolumeLayer,
                                pasteSnapshot, pasteVolumes, pick, pickables, pickBoxEdge, pickEffect, pickLight,
                                pickMovePoint, pickVolumeEdge, pickZone, placeMove, placeSpawn, plainLook, playArea,
                                playWave, pointGizmo, prefabClip, prefabPlacementProblem, prefabRecords, projector,
                                recipeOf, recordVolumes, refreshEffects, refreshPickBox, refreshSpawnMarkers, renderer,
                                resetBaseSpawn, restoreMapBuildings, rockCorners, roomOfSelection, saveBuilder,
                                savedBuildings, savePrefab, saveProject, select, SESSION, setBinding, setBoxesShown,
                                setCover, setEffectsShown, setEffectStays, setGridTool, setLibraryScope,
                                setLightsShown, setLikeness, setMadeLook, setNormalEffects, setNormalLights,
                                setNormalSpawns, setNormalView, setPickedSpawn, setPickTool, setSnapMode, setSolo,
                                setSpawnRule, setSpawnsShown, setVolumeBox, setVolumesShown, setVolumeTool, setZones,
                                setZonesShown, showClearMap, showMissions, showPieces, showPrepare, showSpawn, snapshot,
                                textureHandleScreens, textureSurfaceAt, spawnAddEntries, spawnAt, spawnBoxNow, spawnDeleted, spawnEntry, spawnLayer,
                                spawnVolumeHandle, startBuild, startLookPick, startSpawnPlacing, startWallDrawing,
                                stopWallDrawing, stopWave, storedLook, streamObjects, sun, syncSpawnFilters,
                                takePickBox, updateTileGrid, volumeBox, wallHandlePoint, wallHandlesNow,
                                wallState, world, zoneGizmo, zoneGizmoHelper, zoneHit, zoneProxy, zonesNow }) {
  // Where a game point is drawn in the view's canvas, in client pixels (clientAt and screenOf). Not the handles'
  // projector, which gives null for a point outside the camera's depth range: a check clicks at, or reads, the point
  // it asked for wherever it is.
  function clientAt(point) {
    const p = gameToView(point).project(camera), r = renderer.domElement.getBoundingClientRect();
    return [r.left + (p.x + 1) / 2 * r.width, r.top + (1 - p.y) / 2 * r.height];
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
  return {data, mapId:activeMapId, mapPicture, gizmo, renderer, world, camera, controls, roots, select, frame, lighting, sun, hemisphere, grid,
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
    // (none while the piece's Texture mapping fold is open: its texture handles show instead)
    wallHandles: (units = TILE) => { const r = handleWall(), project = projector();
      return r && texturePicked?.id !== r.userData.source.id ? Object.fromEntries(wallHandlesNow(r).map(h => { const p = wallHandlePoint(h);
        const way = h.dir ?? h.along;      // (a gap's middle, dragged in the wall's plane: along the wall)
        return [h.key, [...project(p), ...project(way ? p.clone().addScaledVector(way, units) : p)]]; })) : {}; },
    rockPoint: () => (rockPoint ? { ...rockPoint, gizmo: pointGizmo.enabled, up: pointGizmo.showY } : null),
    rockCorners: () => [...rockCorners.entries()].map(([k, v]) => [k, v?.then ? 'asking' : v]),
    wallState: id => { const r = madeRoot(id); return r ? wallState(r) : null; },
    // a made piece's texture mapping (stage 4, design B): the surface picked while its fold is open, whether a handle
    // is dragged, its handles on the screen ({ picked, slide, turn, size: [x, y] or null, reach, corner }, null when
    // the fold is shut), and where the middle of one of its surfaces is drawn (to click it)
    texturePicked: () => (texturePicked ? { ...texturePicked } : null), textureDragging: () => Boolean(textureDrag),
    textureHandles: () => textureHandleScreens(), textureSurfaceAt: (role, side = null, ab = null) => textureSurfaceAt(role, side, ab),
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
    clientAt,
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
    alignToGrid, alignToLevel, alignToGamePose, chosenStorey: (x, y) => chosenStorey(x, y),
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
      return b ? Object.fromEntries(FACES.map(([key]) => [key, project(gameToView(handlePoint(b, key)))])) : null; },
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
    screenOf: clientAt,
    // box select, for the browser smoke test
    boxesShown: () => boxesShown, setBoxesShown, pickVolumeEdge,
    ownSelected: () => [...ownSet].map(b => b.name), ownEdge: (x, y) => pickBoxEdge(x, y)?.own?.userData.own.building.name ?? null,
    ownBoxes: () => ownVolumeLayer.children.filter(c => c.userData.own).map(c => ({ building: c.userData.own.building.name, floor: c.userData.own.floor, box: c.userData.own.box })),
    lightsOn: () => lightsOn, normalLights: () => normalLights, setNormalLights, setNormalView,
    pickBox: () => pickBox && [...pickBox], pickTool: () => pickTool, setPickTool, takePickBox, pickHits: () => pickHits.map(c => c.id),
    setPickBox: box => { setPickBoxValue([...box]); setPickToolValue(false); refreshPickBox(true); },
    pieceBox: id => (roots.get(id) ? boxOf(roots.get(id))?.slice() ?? null : null),
    pickMoveHandle: () => (pickBox ? projector()(gameToView(pickMovePoint())) : null),
    pickFaceHandle: key => (pickBox ? projector()(gameToView(handlePoint(pickBox, key))) : null),
    // the Buildings view, for the browser smoke test
    buildings: () => buildings, allBuildings, volumeRoots, volumesOn: () => volumesOn, setVolumesShown, volumeBox, addVolumes, newBuilding, setVolumeTool,
    volumeHandle: key => { const r = volumeRoots.get(selected); return r ? projector()(gameToView(handlePoint(volumeBox(r), key))) : null; },
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
