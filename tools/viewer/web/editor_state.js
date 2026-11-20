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
// their own roots (editor lights plan 4.6; app.js's lights section); the project's building boxes, their own roots too
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

// The project open (app.js's Projects section): null, or { doc, revision, carried: {overrides, added} kept as they
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
