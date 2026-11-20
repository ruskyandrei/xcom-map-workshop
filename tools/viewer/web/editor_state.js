// The page's state that several of its areas use (ARCHITECTURE.md, "The page"): this module is its one owner. Other
// modules read a name through the import (a live binding: the reader sees each new value) and give it a new value only
// through its setter here, set<Name> (set<Name>Value where app.js has a set<Name> of its own that also draws).
// A collection is changed in place through the import as it is. The top level only declares.

// The prefab builder (?prefab=<id>, or new) or a map.
export const prefabParameter = new URLSearchParams(location.search).get('prefab');
export const builderMode = prefabParameter !== null;

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

// The root picked, whose panel shows (app.js's select sets it).
export let selected;
export function setSelected(next) { selected = next; }

// The project open (document_session.js opens and saves it): null, or { doc, revision, carried: {overrides, added} kept as they
// were, savedKey }.
export let project = null;
export function setProject(next) { project = next; }

// groups: id -> { id, locked, breakTogether, members: Map(member key -> member record) }; groupIndex: member key -> the
// group it is a direct member of (a piece's key, or a group's: groupKey(id)). (What a group is: app.js, above
// parentGroup.)
export let groups = new Map(), groupIndex = new Map();
export function setGroups(next) {
  groups = next; groupIndex = new Map();
  for (const g of groups.values()) for (const k of g.members.keys()) groupIndex.set(k, g);
}

// The map's size as the project sets it (project.js validStage): { grid: [nx, ny], ground } or null for the map's own
// (app.js's setStage sets it and draws it).
export let stage = null;
export function setStageValue(next) { stage = next; }
// A cleared map (Clear map plan, section 6): the Build takes out what the editor never showed; the map's size may then
// be set as on the blank map, smaller too. The landing zones as the project sets them (project.js validLandingZone):
// null while the project keeps the map's own landings and the install's lines (app.js's zonesNow gives those).
export let cleared = false, landingZones = null;
export function setCleared(next) { cleared = next; }
export function setLandingZones(next) { landingZones = next; }
// The clear kept the scenery outside the play area (the Clear map window's tick): the Build's clear_level then leaves
// the lights, smoke, stains and glints placed out there, and so does the view
export let clearKeepsOutside = false;
export function setClearKeepsOutside(next) { clearKeepsOutside = next; }
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

// The buildings drawn as boxes and edited (project.js validBuilding; app.js's setBuildings draws them): the project's,
// made from nothing by the Build, and the map's own that can be edited, each as the project's are (map buildings plan,
// section 1). buildingsVersion is raised with each new list, for what is worked out from it.
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
// An added kind the address asks for (?mission=kind:...), picked once the project that adds it is open (app.js's
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
// - pickedZone: the landing zone picked in the Landing zones view, by id, or null (app.js's pickZone); Land here plays
//   the project landing there;
// - missionPickValue: the header's Mission picker's value (app.js's chooseMission), a record's index ('0', '1', ...) or
//   'kind:<kind>' for a kind the project adds (mission types plan, D2); a play is of that mission unless one is chosen.
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
// - mergedBuildings: app.js's allBuildings, worked out once for each state of the buildings (null: to work out again).
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
// null from a server without them (app.js's useMapFamilies sets them).
export let families = null;
export function setFamilies(next) { families = next; }
// The Add panel's piece list (pieces.js's browser) and its Prefabs tab (prefabs.js's), made as the page loads.
export let pieces, prefabTab = null;
export function setPieces(next) { pieces = next; }
export function setPrefabTab(next) { prefabTab = next; }
// What a paste and a placing put down: clipboard, the clip copied or chosen last (a copy, an entry of the Add panel, a
// prefab); chooseToken, raised by each choice in the Add panel, so that a read ending after another choice places
// nothing. nextChooseToken() raises it.
export let clipboard = null, chooseToken = 0;
export function setClipboard(next) { clipboard = next; }
export function nextChooseToken() { return ++chooseToken; }
// Pieces of other maps as read (app.js's library templates): libraryRecords, a piece's record by its id
// (package|actor, lower case); effectTemplates, an effect's, sound's or lens flare's, by its id; foreignEffects, those
// as effect roots' sources, by their target; donorHashes, a map's package, lower case -> its SHA-256, as its pieces'
// records give it.
export const libraryRecords = new Map(), effectTemplates = new Map(), foreignEffects = new Map(), donorHashes = new Map();
// The meshes loaded, by mesh key, each shared by every piece that uses it (app.js's track and loaded).
export const geometryCache = new Map();
// The saved prefabs' pictures waiting to be drawn (prefab_place.js's drawPrefabPictures draws one a frame).
export const prefabPictures = [];

// Which view is on (the user, 11 November 2026: one at a time; app.js's setNormalView leaves them all), each set by its
// own switch: the Lights view (lightsOn; lights_wiring.js's setLightsShown), the Buildings view (volumesOn), the
// Landing zones view (zonesOn), the Effects view (effectsOn) and the Spawns view (spawnsOn). The Normal button's Lights
// switch (normalLights) draws and picks lights with pieces in the normal view; lightsShown, whether lights are drawn
// now, follows from them (app.js's syncLights). Each view's switch reads the others', as do the selection and the keys.
export let lightsOn = false, normalLights = false, lightsShown = false, volumesOn = false, zonesOn = false, effectsOn = false,
           spawnsOn = false;
export function setLightsOn(next) { lightsOn = next; }
export function setNormalLightsValue(next) { normalLights = next; }
export function setLightsShownValue(next) { lightsShown = next; }
export function setVolumesOn(next) { volumesOn = next; }
export function setZonesOn(next) { zonesOn = next; }
export function setEffectsOn(next) { effectsOn = next; }
export function setSpawnsOn(next) { spawnsOn = next; }
// The effect, sound or lens flare picked (app.js's select sets it), whose panel and handles show, or null.
export let pickedEffect = null;
export function setPickedEffect(next) { pickedEffect = next; }
// The streams of the mission the header's Mission picker shows (app.js's chooseMission): their pieces, lights, effects
// and spawn points are drawn.
export let streamSet = new Set();
export function setStreamSet(next) { streamSet = next; }
// What is being placed (app.js's startPlacing): { clip, entry (from the piece list, or null), ghost }, or null.
export let placing = null;
export function setPlacing(next) { placing = next; }
// The hint's timer (app.js's flashHint): the resting hint comes back when it fires.
export let hintTimer;
export function setHintTimer(next) { hintTimer = next; }
// The Map lighting mode (lighting.js, made with the scene in app.js's startScene) and the radius the view's lights are
// reckoned within (app.js's frame).
export let lighting, lightRadius = 700;
export function setLighting(next) { lighting = next; }
export function setLightRadius(next) { lightRadius = next; }
// The Lights view's state that other areas read or set (lights_wiring.js; app.js's keys, pointer handlers, View
// options and draw loop, and the test hooks):
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

// What other areas read or set of the Effects view (effects_wiring.js; app.js's selection, edit hub, keys, pointer
// handlers, draw loop and test hooks):
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
// Groups' pieces on the map now (app.js's liveMembers makes it; whatever adds or takes away roots drops it): member
// key -> its roots, or null.
export let liveCache = null;
export function setLiveCache(next) { liveCache = next; }
// Box select's pieces' middles while its box is up (app.js's pickCandidates), or null: worked out again when what is
// drawn changes.
export let pickCentres = null;
export function setPickCentres(next) { pickCentres = next; }
// The picked spawn marker's key (spawns_view.js spawnKey; app.js's setPickedSpawn sets it and draws), or null.
export let pickedSpawn = null;
export function setPickedSpawnValue(next) { pickedSpawn = next; }
// The last pointer position over the view, for paste and the tips under the pointer, or null; tipDirty: a tip is to be
// worked out again.
export let pointer = null, tipDirty = false;
export function setPointer(next) { pointer = next; }
export function setTipDirty(next) { tipDirty = next; }
