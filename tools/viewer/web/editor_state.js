// The page's state that several of its areas use (ARCHITECTURE.md, "The page"): this module is its one owner. Other
// modules read a name through the import (a live binding: the reader sees each new value) and give it a new value only
// through its setter here, set<Name> (set<Name>Value where the area that owns it has a set<Name> of its own that also
// draws: map_grid.js's setStage, build_play.js's setLastBuild, navigation.js's setSnapMode, and the like).
// A collection is changed in place through the import as it is. The top level only declares.

// The prefab builder (?prefab=<id>, or new) or a map.
export const prefabParameter = new URLSearchParams(location.search).get('prefab');
export const builderMode = prefabParameter !== null;

// The server's list of maps (maps.json), read as the page opens (app.js's open), or null before; and the map browser
// made from it (map_menu.js's makeMapBrowser), or null before: a map's name in the lists, the list brought up to the
// server's, the Map menu, Prepare's check of an outdated map, open() and the prefab builder's Open read them.
export let mapCatalogue = null, mapBrowser = null;
export function setMapCatalogue(next) { mapCatalogue = next; }
export function setMapBrowser(next) { mapBrowser = next; }

// The scene: the map's export (its scene.json) or the builder's prefab scene, read as the page opens, and the map's
// id (null in the builder).
export let data, activeMapId;
export function setData(next) { data = next; }
export function setActiveMapId(next) { activeMapId = next; }

// The scene's roots, each a piece's, light's, building box's or effect's group, by id: the pieces; the map's lights,
// their own roots (editor lights plan 4.6; lights_wiring.js); the project's building boxes, their own roots too
// (the Buildings view); each effect, sound and lens flare (effects and sounds plan, FX3).
export const roots = new Map();
export const lightRoots = new Map();
export const lightIndex = new Map();     // an original light's key (package|level|actor) -> its root
export const volumeRoots = new Map();
export const effectRoots = new Map(), effectIndex = new Map();     // (effectIndex: an original's, by its key)
// every root the gizmo moves: pieces, lights, building boxes and effects
export const allRoots = { get: id => roots.get(id) ?? lightRoots.get(id) ?? volumeRoots.get(id) ?? effectRoots.get(id),
                          has: id => roots.has(id) || lightRoots.has(id) || volumeRoots.has(id) || effectRoots.has(id),
                          values: () => [...roots.values(), ...lightRoots.values(), ...volumeRoots.values(), ...effectRoots.values()][Symbol.iterator]() };

// The root picked, whose panel shows (selection.js's select sets it).
export let selected;
export function setSelected(next) { selected = next; }

// The project open (document_session.js opens and saves it): null, or { doc, revision, carried: {overrides, added} kept as they
// were, savedKey }.
export let project = null;
export function setProject(next) { project = next; }

// groups: id -> { id, locked, breakTogether, members: Map(member key -> member record) }; groupIndex: member key -> the
// group it is a direct member of (a piece's key, or a group's: groupKey(id)). (What a group is: groups.js, above
// parentGroup.)
export let groups = new Map(), groupIndex = new Map();
export function setGroups(next) {
  groups = next; groupIndex = new Map();
  for (const g of groups.values()) for (const k of g.members.keys()) groupIndex.set(k, g);
}

// The map's size as the project sets it (project.js validStage): { grid: [nx, ny], ground } or null for the map's own
// (map_grid.js's setStage sets it and draws it).
export let stage = null;
export function setStageValue(next) { stage = next; }
// The parts of the map the project cleared (the clear-by-parts plan; clear_parts.js): null, or { part: { keepOutside? } }
// for its pieces, lights, effects and triggers, the Build taking out of each what the editor never showed, and that
// part's clear keeping the scenery outside the play area or not. `cleared` is the Pieces part, what most readers ask:
// with it the map's size may be set as on the blank map, smaller too, no ground is laid and none of Long War's patch
// levels is streamed. setClearedParts sets both.
export let clearedParts = null, cleared = false;
export function setClearedParts(next) { clearedParts = next; cleared = Boolean(next?.pieces); }
// The landing zones as the project sets them (project.js validLandingZone): null while the project keeps the map's own
// landings and the install's lines (clear_map.js's zonesNow gives those).
export let landingZones = null;
export function setLandingZones(next) { landingZones = next; }
// The missions the project is for (mission types plan, D1): null, every mission of the base map; else the list of
// {record: i} and {kind, ship?} entries the Build writes records for (the Missions panel, Clear map's question)
export let projectMissions = null;
export function setProjectMissions(next) { projectMissions = next; }
// The project's map picture (LWR map packs plan, 4.3): null, or { sha256 } of the picture the server keeps with it
export let projectPicture = null;
export function setProjectPicture(next) { projectPicture = next; }
// the project's spawn rules (spawns plan, SP8): null, or { dropIns: 'placed' } (a malformed one is carried as saved)
export let projectSpawnRules = null;
export function setProjectSpawnRules(next) { projectSpawnRules = next; }
// The project's background sound (schema 5; project.js validBackgroundSound): null, the map's own
export let projectBackgroundSound = null;
export function setProjectBackgroundSound(next) { projectBackgroundSound = next; }
// What the project tells Long War Rebalance of the map (schema 6; missions.js validMapInfo): null, nothing
export let projectMapInfo = null;
export function setProjectMapInfo(next) { projectMapInfo = next; }
// The map's fog and colour the project changes (schema 10; atmosphere_rules.js): null, the map's own, or the members
// that differ ({ fog?, postProcess? })
export let projectAtmosphere = null;
export function setProjectAtmosphere(next) { projectAtmosphere = next; }
// The diagonal cover the project marks (schema 7; diagonal_marks.js): its own marks and the map's it deletes ({ marks,
// removed }, or null: the map's as it is), the marks that follow their pieces as the pieces stand now (worked out by
// diagonal_wiring.js after each edit: saved with the project for the Build, worked out again when it opens), and the
// records of a project this editor can't read (saved back as they were)
export let projectDiagonal = null;
export function setProjectDiagonal(next) { projectDiagonal = next; }
export let diagonalCarried = [];
export function setDiagonalCarried(next) { diagonalCarried = next; }
export let diagonalCarriedOver = [];
export function setDiagonalCarriedOver(next) { diagonalCarriedOver = next; }
// Whether the Diagonal cover view is on (diagonal_wiring.js setDiagonalShown; one view at a time, as the others)
export let diagonalOn = false;
export function setDiagonalOnValue(next) { diagonalOn = next; }

// The buildings drawn as boxes and edited (project.js validBuilding; buildings_wiring.js's setBuildings draws them):
// the project's, made from nothing by the Build, and the map's own that can be edited, each as the project's are (map
// buildings plan, section 1). buildingsVersion is raised with each new list, for what is worked out from it.
export let buildings = [], buildingsVersion = 0;
export function setBuildingsValue(next) { buildings = next; }
export function setBuildingsVersion(next) { buildingsVersion = next; }

// The document session's state (document_session.js; the prefab builder, builder_session.js, saves and keeps its
// drafts with it):
// - leaving: the page is going by the editor's own doing (a document switched to, a map opened as asked), so the
//   browser's own leave question is not asked;
// - saving: a project's or a prefab's save is under way; no switch of document, other save or draft starts meanwhile;
// - recoveryTimer: the draft's next write, a second after the last change;
// - recoveryKept: this page's draft of the open document is kept on the server;
// - adoptedDraft: a draft the user restored, { owner, savedAt }: deleted once this page's own draft or a save holds
//   its changes (review finding 3; projects.py);
// - recoveryTrouble: the last draft write failed ('failed') or was kept against an older revision than the saved one
//   ('stale'), and the user was told.
export let leaving = false, saving = false, recoveryTimer = null, recoveryKept = false, adoptedDraft = null, recoveryTrouble = null;
export function setLeaving(next) { leaving = next; }
export function setSaving(next) { saving = next; }
export function setRecoveryTimer(next) { recoveryTimer = next; }
export function setRecoveryKept(next) { recoveryKept = next; }
export function setAdoptedDraft(next) { adoptedDraft = next; }
export function setRecoveryTrouble(next) { recoveryTrouble = next; }
// An added kind the address asks for (?mission=kind:...), picked once the project that adds it is open (clear_map.js's
// mission picker).
export let askedPick = null;
export function setAskedPick(next) { askedPick = next; }
// The open project's Build (build_play.js's Build window): lastBuild, its last build status as the server gave it, with
// the project's id (build_play.js's setLastBuild takes one for the open project only: review finding 10); buildTimer,
// the next ask for a running build's status.
export let lastBuild = null, buildTimer = null;
export function setLastBuildValue(next) { lastBuild = next; }
export function setBuildTimer(next) { buildTimer = next; }
// Play in game (build_play.js) and what it goes by:
// - playStatus: the play status as the server last gave it (/play.json, or a play's answer: the install plays go to,
//   how the game is started, the squad, each mission kind's line), null until asked; the Missions panel reads its
//   kinds too;
// - pickedZone: the landing zone picked in the Landing zones view, by id, or null (zones_wiring.js's pickZone); Land
//   here plays the project landing there;
// - missionPickValue: the header's Mission picker's value (clear_map.js's chooseMission), a record's index ('0', '1',
//   ...) or 'kind:<kind>' for a kind the project adds (mission types plan, D2); a play is of that mission unless one is
//   chosen.
export let playStatus = null, pickedZone = null, missionPickValue = '0';
export function setPlayStatus(next) { playStatus = next; }
export function setPickedZone(next) { pickedZone = next; }
export function setMissionPickValue(next) { missionPickValue = next; }
// The serial the last copy's name took (`<actor>_copy<n>`): output names already used, applied or not, are never
// handed out again (a project saves it as nextSerial). nextCopySerial() takes the next one.
export let copySerial = 0;
export function setCopySerial(next) { copySerial = next; }
export function nextCopySerial() { return ++copySerial; }
// The reads a project waits for before it opens: the looks made pieces can take (app.js's readLooks; a read that
// failed is asked again), and the install's landing lines for the map (app.js's startScene: review finding 31).
export let looksReady = null, landingRead = Promise.resolve();
export function setLooksReady(next) { looksReady = next; }
export function setLandingRead(next) { landingRead = next; }

// What the scene to and from a document (document_state.js) shares with the areas that own it:
// - library: the Add panel's All maps, the pieces of every map of the install (library.js's browser), made as the
//   page loads; the prefab builder's document names a piece of another map by its entry there;
// - areaBindings: an area light's actor path -> its glowing piece as the project sets it ({ target, component }), or
//   null: kept fixed (the Lights view);
// - loadErrorCount: the pieces that could not be drawn, the map's own and a document's (said with the map's issues);
// - mergedBuildings: buildings_wiring.js's allBuildings, worked out once for each state of the buildings (null: to work
//   out again).
export let library = null, areaBindings = new Map(), loadErrorCount = 0, mergedBuildings = null;
export function setLibrary(next) { library = next; }
export function setAreaBindings(next) { areaBindings = next; }
export function setLoadErrorCount(next) { loadErrorCount = next; }
export function setMergedBuildings(next) { mergedBuildings = next; }

// The prefab builder's document (builder_session.js opens, keeps and saves it; the document session, the scene to and
// from a document, Build and Play and the Save as prefab dialog read it): doc, the prefab open; kept, the records of
// its pieces that could not be made here, carried as the file had them; envelope, the size's box while such pieces
// are kept; metadata, each piece's record as opened or last saved, by actor (a field this editor doesn't know is
// carried from it); savedKey, what builderKey gave when it was saved; loading, a document being put on the scene;
// repairing, missing pieces being looked for by recipe.
export const builder = { doc: null, kept: [], envelope: null, metadata: new Map(), savedKey: '', loading: true, repairing: false };
// The edit hub's memo of one edit event (app.js's editChanged makes it and drops it): editState, builderDocument and
// builderKey keep what they worked out first in it.
export let eventMemo = null;
export function setEventMemo(next) { eventMemo = next; }
// The map's families of pieces and its assemblies (families.json, tools/viewer/families.py: the compiler's own), or
// null from a server without them (map_families.js's useMapFamilies sets them).
export let families = null;
export function setFamilies(next) { families = next; }
// The Add panel's piece list (pieces.js's browser) and its Prefabs tab (prefabs.js's), made as the page loads; the
// prefab library behind the tab, the Open window's Prefabs side, the menu's count and a placed prefab's group
// (prefab_library.js's store), made once by app.js before the tab.
export let pieces, prefabTab = null, prefabLibrary = null;
export function setPieces(next) { pieces = next; }
export function setPrefabTab(next) { prefabTab = next; }
export function setPrefabLibrary(next) { prefabLibrary = next; }
// What a paste and a placing put down: clipboard, the clip copied or chosen last (a copy, an entry of the Add panel, a
// prefab); chooseToken, raised by each choice in the Add panel, so that a read ending after another choice places
// nothing. nextChooseToken() raises it.
export let clipboard = null, chooseToken = 0;
export function setClipboard(next) { clipboard = next; }
export function nextChooseToken() { return ++chooseToken; }
// Pieces of other maps as read (library_templates.js): libraryRecords, a piece's record by its id (package|actor,
// lower case); effectTemplates, an effect's, sound's or lens flare's, by its id; foreignEffects, those as effect roots'
// sources, by their target; donorHashes, a map's package, lower case -> its SHA-256, as its pieces' records give it.
export const libraryRecords = new Map(), effectTemplates = new Map(), foreignEffects = new Map(), donorHashes = new Map();
// The components of the pieces of other maps read, as templates a copy is made of (library_templates.js's
// libraryTemplate adds them; scene_pieces.js's recipeOf and templateFor and floor_listings.js's projectListings read
// them): `<target key>|<component>` -> its source.
export const foreignTemplates = new Map();
// The url the open map's export is served under (app.js's open sets it): an asset's url in the export is under it
// (library_templates.js's assetUrl); a piece of another map gives its own.
export let cachePrefix = '/cache/';
export function setCachePrefix(next) { cachePrefix = next; }
// The meshes loaded, by mesh key, each shared by every piece that uses it (scene_pieces.js's track and loaded).
export const geometryCache = new Map();
// The saved prefabs' pictures waiting to be drawn (prefab_place.js's drawPrefabPictures draws one a frame).
export const prefabPictures = [];

// Which view is on (11 November 2026: one at a time; views.js's setNormalView leaves them all), each set by
// its own switch: the Lights view (lightsOn; lights_wiring.js's setLightsShown), the Buildings view (volumesOn), the
// Landing zones view (zonesOn), the Effects view (effectsOn) and the Spawns view (spawnsOn). The Normal button's Lights
// switch (normalLights) draws and picks lights with pieces in the normal view; lightsShown, whether lights are drawn
// now, follows from them (views.js's syncLights). Each view's switch reads the others', as do the selection and the
// keys.
export let lightsOn = false, normalLights = false, lightsShown = false, volumesOn = false, zonesOn = false, effectsOn = false,
           spawnsOn = false;
export function setLightsOn(next) { lightsOn = next; }
export function setNormalLightsValue(next) { normalLights = next; }
export function setLightsShownValue(next) { lightsShown = next; }
export function setVolumesOn(next) { volumesOn = next; }
export function setZonesOn(next) { zonesOn = next; }
export function setEffectsOn(next) { effectsOn = next; }
export function setSpawnsOn(next) { spawnsOn = next; }
// The effect, sound or lens flare picked (selection.js's select sets it), whose panel and handles show, or null.
export let pickedEffect = null;
export function setPickedEffect(next) { pickedEffect = next; }
// The streams of the mission the header's Mission picker shows (clear_map.js's chooseMission): their pieces, lights,
// effects and spawn points are drawn.
export let streamSet = new Set();
export function setStreamSet(next) { streamSet = next; }
// The mission the header's Mission picker shows (clear_map.js's chooseMission): its record's index, -1 for a kind the
// project adds (missionPickValue says which).
export let missionIndex = 0;
export function setMissionIndex(next) { missionIndex = next; }
// What is being placed (clipboard.js's startPlacing): { clip, entry (from the piece list, or null), ghost }, or null.
export let placing = null;
export function setPlacing(next) { placing = next; }
// The hint's timer (hints.js's flashHint): the resting hint comes back when it fires.
export let hintTimer;
export function setHintTimer(next) { hintTimer = next; }
// The Map lighting mode (lighting.js, made with the scene in app.js's startScene) and the radius the view's lights are
// reckoned within (navigation.js's frame).
export let lighting, lightRadius = 700;
export function setLighting(next) { lighting = next; }
export function setLightRadius(next) { lightRadius = next; }
// The Lights view's state that other areas read or set (lights_wiring.js; app.js's pointer handlers, View options
// and draw loop, the keys and the test hooks):
// - areaShown, reachShown: View options' Area lights and "Outline the pieces a light reaches" (read from the browser's
//   storage as the page loads);
// - soloOn: Solo is on; lightsDirty: the lights changed since the Map lighting mode last had them (lastLightSync, when);
// - assigning: the light whose glowing piece the next click assigns, by id, or null;
// - derivedCopies: the area lights a copy of their glowing piece carries ({ root, matrix, owner });
// - handleDefs: the selected light's (or effect's) drag handles now; lightDrag: the drag of one under way, or null;
// - reachKey, reachNow: what the selected light's reach was worked out for, and its answer.
export let areaShown = false, reachShown = false, soloOn = false, lightsDirty = true, lastLightSync = 0, assigning = null;
export function setAreaShown(next) { areaShown = next; }
export function setReachShown(next) { reachShown = next; }
export function setSoloOn(next) { soloOn = next; }
export function setLightsDirty(next) { lightsDirty = next; }
export function setLastLightSync(next) { lastLightSync = next; }
export function setAssigning(next) { assigning = next; }
export let derivedCopies = [], handleDefs = [], lightDrag = null, reachKey = '', reachNow = null;
export function setDerivedCopies(next) { derivedCopies = next; }
export function setHandleDefs(next) { handleDefs = next; }
export function setLightDrag(next) { lightDrag = next; }
export function setReachKey(next) { reachKey = next; }
export function setReachNow(next) { reachNow = next; }

// What other areas read or set of the Effects view (effects_wiring.js; the selection, selection.js; app.js's
// pointer handlers and draw loop, the keys and the test hooks):
// - effectsDirty: what is drawn is to be worked out again (refreshEffects) before it is next read; effectMarkers: the
//   markers drawn now, the roots' and the copies a piece's copy carries;
// - normalEffects: the Normal button's Effects switch, which draws and picks them with pieces in the normal view;
// - wavePlayer: the Wave preview's player, { audio, wave, record (its id), state: loading, playing or failed, why }, or
//   null (setWavePlayer gives back what it set: playWave names it in the same statement);
// - likenessOn: View options' Effects as they look (read from the browser's storage as the page loads); likenessThin,
//   likenessCount: how far the likenesses' particles are thinned to the view's budget, and how many there are.
export let effectsDirty = true, effectMarkers = [], normalEffects = false, wavePlayer = null;
export function setEffectsDirty(next) { effectsDirty = next; }
export function setEffectMarkers(next) { effectMarkers = next; }
export function setNormalEffectsValue(next) { normalEffects = next; }
export function setWavePlayer(next) { wavePlayer = next; return next; }
export let likenessOn = true, likenessThin = 1, likenessCount = 0;
export function setLikenessOn(next) { likenessOn = next; }
export function setLikenessThin(next) { likenessThin = next; }
export function setLikenessCount(next) { likenessCount = next; }
// Groups' pieces on the map now (groups.js's liveMembers makes it; whatever adds or takes away roots drops it):
// member key -> its roots, or null.
export let liveCache = null;
export function setLiveCache(next) { liveCache = next; }
// Box select's pieces' middles while its box is up (buildings_wiring.js's pickCandidates), or null: worked out again
// when what is drawn changes.
export let pickCentres = null;
export function setPickCentres(next) { pickCentres = next; }
// The picked spawn marker's key (spawns_view.js spawnKey; spawns_wiring.js's setPickedSpawn sets it and draws), or null.
export let pickedSpawn = null;
export function setPickedSpawnValue(next) { pickedSpawn = next; }
// The last pointer position over the view, for paste and the tips under the pointer, or null; tipDirty: a tip is to be
// worked out again.
export let pointer = null, tipDirty = false;
export function setPointer(next) { pointer = next; }
export function setTipDirty(next) { tipDirty = next; }

// What other areas read or set of the Spawns view (spawns_wiring.js; app.js's map opening, the Clear map window, the
// Buildings view's handles on a no-spawn volume, the keys, the pointer handlers, the draw loop and the test hooks):
// - normalSpawns: the Normal button's "Spawn points and objectives" switch (remembered; read from the browser's
//   storage as a map opens);
// - spawnFilters: the families the flyout shows, by family (remembered);
// - spawnZonePick: a landing zone picked in the Spawns view, described only (decision D3), or null;
// - spawnRulesData: what the install does with spawn points (spawn-rules.json), read as a map opens, or null;
// - spawnEntriesNow: spawnRecords' entries for the mission the header shows, as drawn;
// - missionMoves: the project's moves and edits of mission objects and spawn points, by marker key (spawns_view.js
//   spawnKey): a stream object's {stream, actor, location, rotation}; a base spawn point's, with the values it changes
//   (stream null, saved as overrides of level "base"); a copy's (stream 'copy'); missionDragView: those moves while a
//   drag lasts, drawn in their place, or null (setMissionMovesValue: the view's setMissionMoves also draws them);
// - spawnPlacing: the kind of spawn point the next click places (the Add panel's Spawn points), a pasted copy's clip
//   (spawns_wiring.js spawnClip: Ctrl+V), or null.
export let normalSpawns = false, spawnFilters = {}, spawnZonePick = null, spawnRulesData = null, spawnEntriesNow = [];
export function setNormalSpawnsValue(next) { normalSpawns = next; }
export function setSpawnFilters(next) { spawnFilters = next; }
export function setSpawnZonePick(next) { spawnZonePick = next; }
export function setSpawnRulesData(next) { spawnRulesData = next; }
export function setSpawnEntriesNow(next) { spawnEntriesNow = next; }
export let missionMoves = new Map(), missionDragView = null, spawnPlacing = null;
export function setMissionMovesValue(next) { missionMoves = next; }
export function setMissionDragView(next) { missionDragView = next; }
export function setSpawnPlacing(next) { spawnPlacing = next; }

// What other areas read or set of the Landing zones view (zones_wiring.js; the keys and app.js's pointer handlers):
// zonePlacing, whether the next click places a landing zone (the Add panel's Landing zones kind): true, a pasted copy's
// zone (its fields but the place, Ctrl+V), or false.
export let zonePlacing = false;
export function setZonePlacing(next) { zonePlacing = next; }

// What other areas read or set of the Buildings view and box select (buildings_wiring.js; the selection,
// selection.js; the views' switching, views.js; the map's buildings' records, the clipboard, Select all of a kind, the
// keys, app.js's pointer handlers and draw loop, and the test hooks):
// - boxesShown: the Normal button's Floor boxes switch, the project's boxes drawn and picked in the normal view (off
//   whenever a map opens; setBoxesShownValue, beside the view's setBoxesShown, which also draws);
// - buildingMeta: building id -> { name, kind }, and for one of the map's own its record (map); changed in place;
// - ownSet: the map's own buildings selected with pieces in the normal view (a copy of the selection gets a building
//   of the project with the same boxes); ownPicked: one of the map's own boxes picked to be read, its fill mesh, or
//   null (setOwnPickedValue, beside the view's setOwnPicked, which also draws);
// - volumeTool: the view's tool, 'new' while the next drag draws a box, or null; volumeDrag: a box's face, a new box
//   or a no-spawn volume's face being dragged, or null (setVolumeToolValue, beside the view's setVolumeTool);
// - box select's tool waiting for a drag (pickTool; setPickToolValue, beside setPickTool), its box in game units
//   (pickBox; setPickBoxValue, beside the test hooks' setPickBox, which also draws), its drag (pickDrag) and what the
//   box would take (pickHits); the pieces' middles while it is up are pickCentres, above.
export let boxesShown = false, ownPicked = null, volumeTool = null, volumeDrag = null;
export const buildingMeta = new Map(), ownSet = new Set();
export function setBoxesShownValue(next) { boxesShown = next; }
export function setOwnPickedValue(next) { ownPicked = next; }
export function setVolumeToolValue(next) { volumeTool = next; }
export function setVolumeDrag(next) { volumeDrag = next; }
export let pickTool = false, pickBox = null, pickDrag = null, pickHits = [];
export function setPickToolValue(next) { pickTool = next; }
export function setPickBoxValue(next) { pickBox = next; }
export function setPickDrag(next) { pickDrag = next; }
export function setPickHits(next) { pickHits = next; }

// What other areas read or set of the made pieces' looks (made_looks_wiring.js; the dialogs' check, modal.js's
// modalOpen; the Add panel's browsers, the keys, app.js's pointer handlers and draw loop, and the test hooks):
// - lookPicker: the look picker (look_picker.js), made with the Add panel's piece browser (it paints);
// - lookPicking: the eyedropper, { kind, onChoose }, while the next click in the view takes the look of the piece under
//   it, or null.
export let lookPicker = null, lookPicking = null;
export function setLookPicker(next) { lookPicker = next; }
export function setLookPicking(next) { lookPicking = next; }

// What other areas read or set of the made pieces' drawing (made_drawing.js; the made pieces' handles, app.js's
// pointer handlers, the keys and the test hooks):
// - buildTool: the Build menu's tool being drawn (its button is lit), or null;
// - wallDrawing: the made piece being drawn, or null: { look, room (a room's four walls), slab, roof (a room's roof:
//   roofTemplate), template (once read), start, floor, pointerId, last } (setWallDrawing gives back what it set:
//   startWallDrawing names it in the same statement).
export let buildTool = null, wallDrawing = null;
export function setBuildTool(next) { buildTool = next; }
export function setWallDrawing(next) { wallDrawing = next; return next; }

// What other areas read or set of a made piece's handles (made_handles.js; the selection, selection.js; app.js's
// pointer handlers, the keys and the test hooks; the made pieces' panel):
// - wallDrag: the drag of one of the picked made piece's handles under way, or null;
// - wallFocus: { id, index }: the opening (or slab's hole) whose handle was last touched, which the panel rings and
//   Delete takes out, or null (the selection lets it go when another piece is picked);
// - rockPoint: { id, index }, the rock's point the point gizmo stands on, or null.
export let wallDrag = null, wallFocus = null, rockPoint = null;
export function setWallDrag(next) { wallDrag = next; }
export function setWallFocus(next) { wallFocus = next; }
export function setRockPoint(next) { rockPoint = next; }
// What other areas read of a made piece's texture mapping (made_mapping_wiring.js sets them; the made pieces' handles,
// which hide their size handles meanwhile, app.js's pointer handlers, the keys and the test hooks):
// - texturePicked: { id, role, side }, the surface picked on the made piece `id` while its Texture mapping fold is
//   open (its handles show), or null;
// - textureDrag: the drag of one of its handles under way (its blue dot, ring or white dot), or null.
export let texturePicked = null, textureDrag = null;
export function setTexturePicked(next) { texturePicked = next; }
export function setTextureDrag(next) { textureDrag = next; }
// The snap setting (navigation.js's setSnapMode sets it, the gizmo's with it, and draws its button): 'off', 'fine' (24 units,
// 15 degrees) or 'tile' (whole tiles, 90 degrees); the placing, the cover blocks' and the made pieces' handles read it.
export let snapMode = 'off';
export function setSnapModeValue(next) { snapMode = next; }
// A cover block's or invisible floor's handle being dragged (cover_wiring.js's handles), or null: the made pieces'
// handles take no press meanwhile.
export let coverDrag = null;
export function setCoverDrag(next) { coverDrag = next; }
// The game's collision for line checks by mesh (collision.json), which the invisible floors measure the ground by
// (cover_wiring.js's askLineCollision asks for the map's once): mesh id -> { simple: false } or { simple: true, solids
// }, or null until it comes; a piece of another map read adds its meshes' (library_templates.js's libraryTemplate).
// lineCollisionFailed: the map's could not be read (the test hooks read both).
export let lineCollision = null, lineCollisionFailed = false;
export function setLineCollision(next) { lineCollision = next; }
export function setLineCollisionFailed(next) { lineCollisionFailed = next; }

// Break and Repair (made_breaking.js): the piece Break is on, { id }, or null; the keys and app.js's pointer handlers
// read it.
export let breaking = null;
export function setBreaking(next) { breaking = next; }

// The target Align lines the others up with (align.js; app.js's handler of the piece panel's target list sets it): the
// id of a piece of it, or null for the last one picked.
export let alignTarget = null;
export function setAlignTarget(next) { alignTarget = next; }

// The gizmos in the view (view_gizmo.js: the views' own, made by createViewGizmo, and the pieces' and a rock point's
// joined), each answering for its mode, its busy test and its cancel; navigation.js and app.js's press handler ask
// through view_gizmo.js's activeGizmo, anyGizmoBusy and cancelGizmoDrag. Filled as the factories are made.
export const viewGizmos = [];

// Placing (clipboard.js), and what of it app.js's pointer handlers and draw loop and the keys read or set:
// - ghostDirty: the preview of what is being placed is to be moved to the pointer again (the pointer handlers, the
//   keys ask for it, the draw loop moves it);
// - libraryScope: the Add panel's tab, 'map' (This map), 'all' (All maps) or 'prefabs' (app.js gives it the one the
//   browser's storage remembers as the page loads);
export let ghostDirty = false, libraryScope = 'map';
export function setGhostDirty(next) { ghostDirty = next; }
export function setLibraryScopeValue(next) { libraryScope = next; }

// The map grid (map_grid.js), and what of it app.js's scene start and pointer handlers, the keys and the test hooks
// read or set:
// - ownGrid: the map's own size as exported, { dims, max }, kept before the first change (the scene start drops it);
// - gridTool: the rail's Map grid is on, its handles shown (setGridToolValue, beside the grid's setGridTool, which also
//   draws); gridDrag: a handle's drag under way, or null.
export let ownGrid = null, gridTool = false, gridDrag = null;
export function setOwnGrid(next) { ownGrid = next; }
export function setGridToolValue(next) { gridTool = next; }
export function setGridDrag(next) { gridDrag = next; }

// Clear map and the landings (clear_map.js), and what of them app.js's scene start, the map's families
// (map_families.js) and the test hooks read or set:
// - landingLines: the install's landing lines for the map (GET landing-lines.json) and its kind, which come with the
//   map: 'lwr' or 'longwar' (Long War), 'ew' (plain Enemy Within), or null, a game the editor doesn't know (none set,
//   or the read failed: `failed` says why), a state of its own and not Long War (review finding 31) (the read a
//   project waits for: landingRead);
// - startingCache: the landing zones the map's own landings and those lines give (zonesNow), worked out once a scene,
//   or null;
// - lastClearMs: how long the last clear took, in milliseconds (the test hooks), or null;
// - landingActors: the landing zone's pieces as the server's families name them (map_families.js's useMapFamilies), or
//   null: then by their archetype (isLanding).
export let landingLines = { kind: null, lines: [] }, startingCache = null, lastClearMs = null, landingActors = null;
export function setLandingLines(next) { landingLines = next; }
export function setStartingCache(next) { startingCache = next; }
export function setLastClearMs(next) { lastClearMs = next; }
export function setLandingActors(next) { landingActors = next; }

// The cutaway (cutaway.js), and what of it app.js's View options and draw loop and the test hooks read or set:
// - tileKey: what the tile grid was last drawn round, or null to draw it again (View options' grid drops it);
// - floorTileLayer: View options' Floor tiles overlay as drawn (view_layout.js floorTilesOverlay), or null.
export let tileKey = '', floorTileLayer = null;
export function setTileKey(next) { tileKey = next; }
export function setFloorTileLayer(next) { floorTileLayer = next; }

// Prepare (prepare.js): what is wrong with the open map's export for lights and builds (families.json's exportProblem;
// prepare.js's prepareOpened sets it as the map opens), or null: a build or a play then asks for the map to be
// prepared.
export let exportProblem = null;
export function setExportProblem(next) { exportProblem = next; }
