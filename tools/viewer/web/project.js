// Projects (first-editor plan E1; the format is in research/editor-contracts.md). A project is a delta over one base
// map as exported, bound to it by the source package's SHA-256: original pieces moved or deleted, keyed by package,
// level and actor; added pieces, each a copy of a source actor's components under its own output name and pose; and
// the user's groups of pieces, with their lock and options. The viewer's server stores it (tools/viewer/projects.py). Nothing here touches the game.
import { validFlags } from './piece_flags.js';
import { clearedPartsOf } from './clear_parts.js';
import { carriedMapInfo, tidyMapInfo, validMapInfo } from './missions.js';
import { validAtmosphere } from './atmosphere_rules.js';
import { call } from './api.js';

// 2: pieces' flags (overrides[].flags, added[].flags; piece flags plan); 3: effects and sounds (the effects and sounds
// plan, Part C: an override of an effect or a sound, and an added record with a `kind`); 4: the spawns plan's
// (`spawnRules`, SP8; the base map's spawn points' overrides and added records, SP6 and SP7); 5: the map's background
// sound (`backgroundSound`) and a clear that keeps the map's triggers (`clearKeepsTriggers`); 6: what Long War
// Rebalance is told of the map (`lwrMapInfo`; missions.js's MAP_INFO); 7: the diagonal cover the project marks
// (`diagonalCover`; diagonal_marks.js); 8: a building's floors as the cursor's; 9: the parts of the map the project
// cleared (`cleared`: {part: {keepOutside?}}, the clear-by-parts plan; `cleared: true` of 1 to 8 is every part); 10:
// the map's fog and colour the project changes (`atmosphere`: {fog?, postProcess?}, the members that differ from the
// map's own; atmosphere_rules.js). A project of schema 1 to 9 opens, and saves as 10.
export const SCHEMA = 'xcom-map-workshop/project', SCHEMA_VERSION = 10;

// Poses as saved: game units to 1/10000, rotators in native units (65536 a turn), whole where they are within 1/1000.
export const tidyLocation = v => Number(v.toFixed(4)) + 0;
export const tidyRotator = v => { const r = Math.round(v); return Math.abs(v - r) < 1e-3 ? r + 0 : Number(v.toFixed(3)); };
export const targetKey = t => `${t.package}|${t.level}|${t.actor}`;
const byTarget = (a, b) => targetKey(a.target).localeCompare(targetKey(b.target));
const byActor = (a, b) => a.actor.localeCompare(b.actor);
// A group member: an original by its target ({package, level, actor}), an added piece by its output name ({added}),
// or another group by its id ({group}: groups nest; prefab plan 5.4). The key is the viewer's own name for it.
export const groupKey = id => `group|${id}`;
// (one of the project's buildings as a member: {building: id}; prefab plan 5.4a)
export const buildingKey = id => `building|${id}`;
export const memberKey = m => (typeof m?.group === 'string' ? groupKey(m.group)
  : typeof m?.building === 'string' ? buildingKey(m.building)
  : typeof m?.added === 'string' ? `added|${m.added}` : `orig|${targetKey(m)}`);

/** Groups made sound after a change (a Map id -> { id, members: Map(key -> record), ... }, changed in place): a member
 *  naming a group that is gone is dropped, and a group left with fewer than two members ends, its last member taking
 *  its place in the group it was in (or standing free). */
export function pruneGroups(groups) {
  for (let changed = true; changed;) {
    changed = false;
    for (const g of [...groups.values()]) {
      for (const [k, m] of [...g.members]) if (m.group !== undefined && (!groups.has(m.group) || m.group === g.id)) { g.members.delete(k); changed = true; }
      if (g.members.size >= 2) continue;
      const parent = [...groups.values()].find(p => p !== g && p.members.has(groupKey(g.id)));
      groups.delete(g.id); changed = true;
      if (!parent) continue;
      parent.members.delete(groupKey(g.id));
      for (const [k, m] of g.members) parent.members.set(k, m);
    }
  }
  return groups;
}
const byKey = (a, b) => memberKey(a).localeCompare(memberKey(b));
// (`prefab`: the prefab a group was placed from, { id, name, revision }: a label, for "update to the newest" later)
export const validPrefabMark = p => p && typeof p === 'object' && typeof p.id === 'string' && typeof p.name === 'string'
  && Number.isInteger(p.revision) && Object.keys(p).length === 3;
const tidyGroup = g => ({ id: g.id, locked: g.locked !== false, breakTogether: g.breakTogether === true,
                                 ...(validPrefabMark(g.prefab) ? { prefab: { id: g.prefab.id, name: g.prefab.name, revision: g.prefab.revision } } : {}),
                                 members: [...g.members].sort(byKey) });
// Two edit states are the same project content when these match (records come sorted).
export const stateKey = state => JSON.stringify([state.overrides, state.added, state.groups ?? [], state.areaLightBindings ?? [], state.stage ?? null,
                                                 state.buildings ?? [], clearedPartsOf(state), state.landingZones ?? null,
                                                 state.missions ?? null, state.spawnRules ?? null, state.picture?.sha256 ?? null,
                                                 state.backgroundSound ?? null,
                                                 state.lwrMapInfo ?? null, state.diagonalCover ?? null, state.atmosphere ?? null]);
// The project's map picture (LWR map packs plan, 4.3): null, or { sha256 }, the SHA-256 of the 512 x 256 picture the
// server keeps with the project (tools/viewer/pictures.py); the Build writes it into the map.
export const validPicture = p => Boolean(p) && typeof p === 'object' && !Array.isArray(p) && Object.keys(p).length === 1
  && typeof p.sha256 === 'string' && /^[0-9a-f]{64}$/.test(p.sha256);
// The project's spawn rules (spawns plan, SP8): null (the install's behaviour) or { dropIns: 'placed' } (Long War's
// scripted drop-ins land where placed: the Build excludes the variant from its drop-in mutator). Nothing else is read.
export const validSpawnRules = r => r && typeof r === 'object' && !Array.isArray(r) && Object.keys(r).length === 1 && r.dropIns === 'placed';
// The map's background sound (schema 5): null (the map's own), or { cue: a cue's path or null (none), volume?: a
// multiplier, 0 to 4 }, the sound bed its script starts when it loads; the compiler checks the cue against the beds the
// editor offers (tools/viewer/background_sounds.json). The server takes any { cue, volume? } (projects.py), so one of
// that shape the page can't read is carried as it is, for the compiler to leave out; any other is dropped.
export const BACKGROUND_VOLUME = [0, 4];
const soundShape = s => Boolean(s) && typeof s === 'object' && !Array.isArray(s) && 'cue' in s && Object.keys(s).every(k => k === 'cue' || k === 'volume');
export const validBackgroundSound = s => soundShape(s) && (s.cue === null || (typeof s.cue === 'string' && s.cue !== ''))
  && (s.volume === undefined || (Number.isFinite(s.volume) && s.volume >= BACKGROUND_VOLUME[0] && s.volume <= BACKGROUND_VOLUME[1]));
const tidyBackgroundSound = s => ({ cue: s.cue, ...(s.volume !== undefined ? { volume: Number(s.volume.toFixed(4)) + 0 } : {}) });
// A building the Build makes from nothing (prefab plan 5.1; building_edits.py BuildingEdits.buildings): { id, name,
// kind: 'building' | 'ufo', floors: [{ boxes: [[x0, y0, z0, x1, y1, z1]] }] }, floor 0 first, game units, unturned.
// Which pieces each floor lists is not saved: the Build works it out from where the pieces stand.
// One of the map's own buildings that the project changed (map buildings plan, section 2) has `replaces`, the map's
// building volume as a piece's target ({ package, level: 'base', actor: its path }), and its id is mapBuildingId's;
// each floor then has `volumes` beside `boxes`, as long: the floor volume (its short name) each box came from, null
// for a new box. One the project deleted is { id, replaces, deleted: true }, with no floors. A map building with no
// record is the map's, as exported.
export const BUILDING_KINDS = ['building', 'ufo'], BUILDING_FLOORS_MAX = 10;
// "Unchanged": every coordinate of a box within this of the export's box for its volume (the compiler's twin)
export const BUILDING_SAME = 0.01;
export const mapBuildingId = (level, actor) => `map:${level}.${actor.split('.').at(-1)}`;
const validBox = b => Array.isArray(b) && b.length === 6 && b.every(Number.isFinite) && [0, 1, 2].every(k => b[k + 3] - b[k] >= 1);
const validReplaces = r => r && typeof r === 'object' && typeof r.package === 'string' && typeof r.level === 'string'
  && typeof r.actor === 'string' && Object.keys(r).length === 3;
export const validBuilding = b => {
  if (!b || typeof b !== 'object' || typeof b.id !== 'string' || b.id === '' || typeof (b.name ?? '') !== 'string') return false;
  if (b.replaces !== undefined && !validReplaces(b.replaces)) return false;
  if (b.cursorFloors !== undefined && typeof b.cursorFloors !== 'boolean') return false;
  if (b.deleted !== undefined) return b.deleted === true && b.replaces !== undefined && b.floors === undefined;
  return BUILDING_KINDS.includes(b.kind ?? 'building') && Array.isArray(b.floors) && b.floors.length >= 1 && b.floors.length <= BUILDING_FLOORS_MAX
    && b.floors.every(f => f && Array.isArray(f.boxes) && f.boxes.length >= 1 && f.boxes.every(validBox)
      && (b.replaces === undefined ? f.volumes === undefined
        : Array.isArray(f.volumes) && f.volumes.length === f.boxes.length && f.volumes.every(v => v === null || (typeof v === 'string' && v !== ''))));
};
const tidyBox = x => x.map(v => Number(v.toFixed(3)) + 0);
// (a map building's boxes and volumes are sorted together, by box)
function tidyFloor(f, map) {
  if (!map) return { boxes: f.boxes.map(tidyBox) };
  const pairs = f.boxes.map((x, k) => [tidyBox(x), f.volumes[k]]).sort((a, b) => a[0].join().localeCompare(b[0].join()));
  return { boxes: pairs.map(p => p[0]), volumes: pairs.map(p => p[1]) };
}
// (`cursorFloors`, schema 8: the building's floors are the cursor's over it, the building cursor floors plan; kept on a
// building made from nothing only, and only when true)
export const tidyBuilding = b => (b.deleted ? { id: b.id, ...(b.name ? { name: b.name } : {}), replaces: { ...b.replaces }, deleted: true }
  : { id: b.id, name: b.name ?? '', kind: b.kind ?? 'building', ...(b.replaces ? { replaces: { ...b.replaces } } : {}),
      ...(b.cursorFloors === true && !b.replaces ? { cursorFloors: true } : {}),
      floors: b.floors.map(f => tidyFloor(f, Boolean(b.replaces))) });
// The map's size as the project sets it (prefab plan 5.11): { grid: [tiles along x, tiles along y] }, the map's tile
// grid made that large from its own corner, or with a third number its levels, from its own bottom (5.6b), and
// ground: false to lay no ground over the new area. Absent or null: the map's own size. On a cleared project (Clear
// map plan, section 6) the grid may also be smaller than the map's, in any of the three; the corner and the bottom
// never move.
// (256 tiles a side since 16 November 2026; 128 before)
export const STAGE_GRID_MAX = 256, STAGE_LEVELS_MAX = 30;
// The maps whose size can be set without clearing them: the bare map a new prefab or a new map starts from
// (compiler_tables.py STAGE_MAPS). Any map as it is may grow (13 November 2026); a cleared one may also shrink.
export const STAGE_MAPS = ['CB2_MP_Blank'];
// The landing zones the project sets (Clear map plan, section 4): the whole list, in order, written as LWR's LZArray
// lines and, for the first zones that name no mission, as the map's own landings moved in place. Each is { id,
// location: [x, y, z] (the line's StartLoc), direction: 'north' | 'east' | 'south' | 'west' (StartDir), kind:
// 'normal' | 'inside' | 'alternate' | 'noEvac' | 'default' (ESpawnLoc; no line of the install uses the last three),
// missionType?, councilType? (the mission a line is kept for, as written), alternate?: { location, direction }
// (AltSpawnLoc, AltSpawnDir), lwr?: false (no line is written for it), other?: string (a line's fields the editor does
// not know, as written) }. Absent: the base map's lines and its own landings, as they are. tools/viewer/spawns.py
// reads and writes the lines.
const LANDING_DIRECTIONS = ['north', 'east', 'south', 'west'], LANDING_KINDS = ['normal', 'inside', 'alternate', 'noEvac', 'default'];
const LANDING_KEYS = ['id', 'location', 'direction', 'kind', 'missionType', 'councilType', 'alternate', 'lwr', 'ew', 'other'];
const typeName = v => v === undefined || (typeof v === 'string' && /^[A-Za-z0-9_]+$/.test(v));
// `other` goes into the game's ini as written: it must stay on its line (spawns.py plain_other is the twin)
const plainOther = v => v === undefined || (typeof v === 'string' && /^[^\x00-\x08\x0a-\x1f\x7f\x85\u2028\u2029]{0,4000}$/.test(v));
// (spawns.py valid_zone is the twin: tests/zone_cases.json holds the cases both pass; a field given is one of its kind,
// null is no value of any of them)
export const validLandingZone = z => Boolean(z) && typeof z === 'object' && !Array.isArray(z) && typeof z.id === 'string' && z.id !== ''
  && Array.isArray(z.location) && z.location.length === 3 && z.location.every(Number.isFinite)
  && LANDING_DIRECTIONS.includes(z.direction) && (z.kind === undefined || LANDING_KINDS.includes(z.kind))
  && typeName(z.missionType) && typeName(z.councilType)
  && (z.alternate === undefined || (Boolean(z.alternate) && typeof z.alternate === 'object' && Object.keys(z.alternate).length === 2
    && Array.isArray(z.alternate.location) && z.alternate.location.length === 3 && z.alternate.location.every(Number.isFinite)
    && LANDING_DIRECTIONS.includes(z.alternate.direction)))
  && [undefined, false].includes(z.lwr) && [undefined, true].includes(z.ew) && plainOther(z.other)
  && Object.keys(z).every(k => LANDING_KEYS.includes(k));
export const tidyLandingZone = z => ({ id: z.id, location: z.location.map(tidyLocation), direction: z.direction, kind: z.kind ?? 'normal',
  ...(z.missionType ? { missionType: z.missionType } : {}), ...(z.councilType ? { councilType: z.councilType } : {}),
  ...(z.alternate ? { alternate: { location: z.alternate.location.map(tidyLocation), direction: z.alternate.direction } } : {}), ...(z.lwr === false ? { lwr: false } : {}),
  ...(z.ew === true ? { ew: true } : {}), ...(z.other ? { other: z.other } : {}) });
// The most a project's grid may be on each axis, given the map's own grid [nx, ny, nz]: 256 tiles across and deep and
// 30 levels, or the map's own where that is more, so a map is never past the limit at its own size (compiler.py
// stage_max is the twin; while the limit was 128, TempleShip, 203 tiles deep, snapped back: T-41)
export const stageMax = (own = null) => [STAGE_GRID_MAX, STAGE_GRID_MAX, STAGE_LEVELS_MAX].map((v, k) => Math.max(v, own?.[k] ?? 0));
// A stage's shape, whatever its size
const stageShape = s => typeof s === 'object' && s !== null && !Array.isArray(s) && Array.isArray(s.grid) && [2, 3].includes(s.grid.length)
  && s.grid.every(v => Number.isInteger(v) && v >= 1) && [undefined, true, false].includes(s.ground)
  && [undefined, true, false].includes(s.lines) && [undefined, true, false].includes(s.hideGround)
  && Object.keys(s).every(k => ['grid', 'ground', 'lines', 'hideGround'].includes(k));
// A stage the map whose own grid is `own` can take in size (without `own`, the plain limits)
export const validStage = (s, own = null) => s == null || (stageShape(s) && s.grid.every((v, k) => v <= stageMax(own)[k]));
export const tidyStage = s => (s ? { grid: [...s.grid], ...(s.ground === false ? { ground: false } : {}),
                                     ...(s.lines === true ? { lines: true } : {}),
                                     ...(s.hideGround === true ? { hideGround: true } : {}) } : null);
// Area lights bound to their glowing pieces (editor lights plan 3.5), sorted by the area light; malformed ones last.
const byBinding = (a, b) => String(validBinding(a) ? targetKey(a.target) : '~').localeCompare(String(validBinding(b) ? targetKey(b.target) : '~'));
export function sortState(state) {
  return { overrides: [...state.overrides].sort(byTarget), added: [...state.added].sort(byActor),
           // Malformed groups are carried as they are.
           groups: (state.groups ?? []).map(g => (validGroup(g) ? tidyGroup(g) : g)).sort((a, b) => String(a?.id).localeCompare(String(b?.id))),
           areaLightBindings: [...(state.areaLightBindings ?? [])].sort(byBinding),
           // the size was checked against the map when the stage was set (map_grid.js setStage): only its shape here, so a
           // map past the plain limits at its own size keeps its larger grid
           stage: state.stage != null && stageShape(state.stage) ? tidyStage(state.stage) : null,
           // Malformed buildings are carried as they are.
           buildings: (state.buildings ?? []).map(b => (validBuilding(b) ? tidyBuilding(b) : b)).sort((a, b) => String(a?.id).localeCompare(String(b?.id))),
           // the parts the project cleared (schema 9; clear_parts.js): { part: { keepOutside? } } or null, the Build
           // taking out of each what the editor never showed; schema 1 to 8's `cleared: true` with its ticks reads as
           // every part
           cleared: clearedPartsOf(state),
           // the landing zones keep their order (it says which are the map's own); a malformed one is carried in place
           landingZones: Array.isArray(state.landingZones) ? state.landingZones.map(z => (validLandingZone(z) ? tidyLandingZone(z) : z)) : null,
           // the missions the variant serves (mission types plan, D1): null, every mission of the base map
           missions: Array.isArray(state.missions) ? state.missions.map(e => ({ ...e })) : null,
           // the spawn rules (SP8): a malformed one is carried as it is, for the compiler to refuse
           spawnRules: validSpawnRules(state.spawnRules) ? { dropIns: 'placed' } : (state.spawnRules ?? null),
           // the background sound (schema 5): one the page can't read is carried as it is when the server takes it
           backgroundSound: validBackgroundSound(state.backgroundSound) ? tidyBackgroundSound(state.backgroundSound)
             : soundShape(state.backgroundSound) ? { ...state.backgroundSound } : null,
           // what Long War Rebalance is told of the map (schema 6): one the page can't read is carried as it is when
           // the server takes it, for the compiler to leave out; an empty one says nothing
           lwrMapInfo: validMapInfo(state.lwrMapInfo) ? tidyMapInfo(state.lwrMapInfo)
             : carriedMapInfo(state.lwrMapInfo) && Object.keys(state.lwrMapInfo).length ? { ...state.lwrMapInfo } : null,
           // the map's fog and colour (schema 10): the window keeps it tidied (atmosphere_rules.js tidyAtmosphere); one the
           // page can't read is carried as it is, for the compiler to leave out; an empty one says nothing
           atmosphere: state.atmosphere && typeof state.atmosphere === 'object' && Object.keys(state.atmosphere).length
             ? (validAtmosphere(state.atmosphere) ? JSON.parse(JSON.stringify(state.atmosphere)) : { ...state.atmosphere }) : null,
           // the diagonal cover the project marks (schema 7): diagonal_marks.js savedDiagonal made it, its marks and places
           // in order; a record the page can't read is carried in it as saved, for the compiler to leave out
           diagonalCover: diagonalShape(state.diagonalCover) ? { marks: state.diagonalCover.marks ?? [], removed: state.diagonalCover.removed ?? [] } : null,
           // the map picture: a malformed one is dropped (the server would refuse the save)
           picture: validPicture(state.picture) ? { sha256: state.picture.sha256 } : null };
}

// The diagonal cover a project marks (schema 7): { marks: [records], removed: [places] }, the frame the server takes
// (projects.py); diagonal_marks.js reads the records. Anything else is dropped (the server would refuse the save).
const diagonalShape = d => Boolean(d) && typeof d === 'object' && !Array.isArray(d) && Object.keys(d).every(k => ['marks', 'removed'].includes(k))
  && (d.marks === undefined || (Array.isArray(d.marks) && d.marks.every(m => m && typeof m === 'object' && !Array.isArray(m))))
  && (d.removed === undefined || Array.isArray(d.removed)) && Boolean(d.marks?.length || d.removed?.length);
// A record the browser can apply: a known shape with finite numbers (the server checks only the document's frame).
const finite3 = v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite);
const isTarget = t => t && typeof t.package === 'string' && typeof t.level === 'string' && typeof t.actor === 'string';
// A light's values (editor lights plan 9.1), as an override or added light carries them: an object of known keys.
const LIGHT_KEYS = ['color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled'];
const validLight = v => v === undefined || (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).every(k => LIGHT_KEYS.includes(k))
  && Object.entries(v).every(([k, x]) => (k === 'color' ? Array.isArray(x) && x.length === 3 && x.every(Number.isInteger)
                                          : k === 'enabled' ? typeof x === 'boolean' : Number.isFinite(x))));
// An effect's or a sound's values (effects and sounds plan, Part C): `effect` {scale?, startsOn?, parameters?, follow?}
// or `sound` {radiusMin?, radiusMax?, volume?, pitch?, startsOn?}, known keys only. `follow` ('none': it stays where
// it is when the piece that carries it moves; 'auto': it follows) is stage FX3's; the others are carried as saved.
const EFFECT_VALUE_KEYS = { effect: ['scale', 'startsOn', 'parameters', 'follow'], sound: ['radiusMin', 'radiusMax', 'volume', 'pitch', 'startsOn'] };
const validEffectValues = (v, kind) => v === undefined || (v && typeof v === 'object' && !Array.isArray(v)
  && Object.keys(v).every(k => EFFECT_VALUE_KEYS[kind].includes(k)) && (v.follow === undefined || ['none', 'auto'].includes(v.follow)));
// A base spawn point's values (the editor spawns plan, SP6): `spawn` {commander?, secondary?, use?} of a pod or
// {difficulty?, destroyedOnTurn?, spawnGroup?} of a Meld point, each a boolean, a string or a whole number; which kind's
// keys a point takes is the compiler's to check.
const validSpawnValues = v => v === undefined || (v && typeof v === 'object' && !Array.isArray(v)
  && Object.values(v).every(x => typeof x === 'boolean' || typeof x === 'string' || Number.isInteger(x)));
// (a no-spawn volume's box, [x0, y0, z0, x1, y1, z1]: each far side past the near one, as spawns_view.js validBox and
// spawn_edits.py SpawnEdits.spawn_box have it, not a building box's at least 1 unit; review finding 34)
const validSpawnBox = b => Array.isArray(b) && b.length === 6 && b.every(Number.isFinite) && b[3] > b[0] && b[4] > b[1] && b[5] > b[2];
// (flags: a piece's flags, piece_flags.js validFlags; an override may be flags alone, with no pose: the piece where the
// map has it; an effect's may be its values alone, and a spawn point's too; a no-spawn volume's is its box, its values
// or both, never a pose)
// (blasts: one of the map's fracturing pieces broken, custom geometry editing plan E6: [{ at, radius }] in its mesh's
// frame; an override may be blasts alone, or with flags, the piece where the map has it; the compiler checks the
// numbers, tools/bake/made_blasts.py; `breaksFurther: true` with them lets a roof or floor the game keeps whole break
// further in battle, F-139)
const validBlasts = b => Array.isArray(b) && b.length > 0
  && b.every(x => x && typeof x === 'object' && finite3(x.at) && Number.isFinite(x.radius) && Object.keys(x).length === 2);
export const validOverride = r => isTarget(r?.target) && validLight(r.light) && (r.flags === undefined || validFlags(r.flags))
  && (r.breaksFurther === undefined || (r.breaksFurther === true && r.blasts !== undefined))
  && (r.blasts === undefined || (validBlasts(r.blasts) && r.light === undefined && r.effect === undefined && r.sound === undefined
      && r.spawn === undefined && r.box === undefined))
  && validEffectValues(r.effect, 'effect') && validEffectValues(r.sound, 'sound') && !(r.effect && r.sound) && r.flare === undefined
  && validSpawnValues(r.spawn) && !(r.spawn !== undefined && (r.effect !== undefined || r.sound !== undefined || r.light !== undefined || r.flags !== undefined))
  && (r.box === undefined || (validSpawnBox(r.box) && r.location === undefined && r.rotation === undefined && r.light === undefined
      && r.flags === undefined && r.effect === undefined && r.sound === undefined))
  && (r.deleted === true || (finite3(r.location) && finite3(r.rotation))
      || ((r.flags !== undefined || r.blasts !== undefined) && r.location === undefined && r.rotation === undefined && r.light === undefined)
      || ((r.effect !== undefined || r.sound !== undefined) && r.location === undefined && r.rotation === undefined
          && r.light === undefined && r.flags === undefined)
      || (r.spawn !== undefined && r.location === undefined && r.rotation === undefined)
      || r.box !== undefined);
// An added actor: a copy of a source actor's components (`from`, `components`), a light made from a built-in recipe
// (`template`: { kind, version }, editor lights plan 3.5), or a cover block or invisible floor (`template` { kind: 'cover',
// version } and `cover` { type, size, heights } in units, an invisible floor's { type, size }, an older record's
// { width, length, type, height } in whole tiles, or a first record's { width, length, height: 'high' | 'low' }:
// tools/viewer/web/cover.js), never two of them.
const validRecipe = t => t && typeof t.kind === 'string' && Number.isInteger(t.version) && Object.keys(t).length === 2;
const finiteList = (v, n) => Array.isArray(v) && v.length === n && v.every(Number.isFinite);
const validCover = c => c && typeof c === 'object' && (Object.hasOwn(c, 'size')
  ? typeof c.type === 'string' && finiteList(c.size, 2)
    && (Object.keys(c).length === 2 || (Object.keys(c).length === 3 && finiteList(c.heights, 2)))
  : Number.isInteger(c.width) && Number.isInteger(c.length)
    && (Object.keys(c).length === 4 ? typeof c.type === 'string' && Number.isInteger(c.height)
      : Object.keys(c).length === 3 && typeof c.height === 'string'));
// An added effect, sound or lens flare (effects and sounds plan, Part C): `kind` and the original it copies (`from`),
// with its own values object at most, and nothing a piece's copy has. A lens flare has no values object (stage FX6b:
// its template and colour stay as the map has them).
export const EFFECT_KINDS = ['effect', 'sound', 'flare'];
const validAddedEffect = e => EFFECT_KINDS.includes(e.kind) && isTarget(e.from) && ['components', 'template', 'light', 'cover', 'flags',
  'prefab', 'partner', 'tinted'].every(k => e[k] === undefined) && validEffectValues(e.effect, 'effect') && validEffectValues(e.sound, 'sound')
  && (e.kind === 'effect' || e.effect === undefined) && (e.kind === 'sound' || e.sound === undefined) && e.flare === undefined;
// A copy of one of the map's pods or Meld points (the editor spawns plan, SP7): `kind` pod or meld, `from` its template,
// its own `spawn` values, nothing of a piece's.
const validAddedSpawn = e => ['pod', 'meld'].includes(e.kind) && isTarget(e.from) && validSpawnValues(e.spawn)
  && Object.keys(e).every(k => ['id', 'kind', 'actor', 'from', 'location', 'rotation', 'spawn'].includes(k));
// A no-spawn volume the project adds: a copy of the map's (`from`) or a new one (no `from`), placed by its box alone.
const validAddedVolume = e => e.kind === 'noSpawn' && (e.from === undefined || isTarget(e.from)) && validSpawnBox(e.box) && validSpawnValues(e.spawn)
  && Object.keys(e).every(k => ['id', 'kind', 'actor', 'from', 'box', 'spawn'].includes(k));
export const validAdded = e => typeof e?.id === 'string' && typeof e.actor === 'string'
  && (e.kind === 'noSpawn' ? validAddedVolume(e) : finite3(e.location) && finite3(e.rotation)
  && (['pod', 'meld'].includes(e.kind) ? validAddedSpawn(e) : e.kind !== undefined ? validAddedEffect(e) : e.effect === undefined && e.sound === undefined
  && validLight(e.light) && (e.flags === undefined || (e.template === undefined && validFlags(e.flags)))
  && (e.blasts === undefined || (e.template === undefined && e.generated === undefined && validBlasts(e.blasts)))
  && (e.breaksFurther === undefined || (e.breaksFurther === true && e.blasts !== undefined))
  && (e.template === undefined
    ? isTarget(e.from) && Array.isArray(e.components) && e.components.length > 0 && e.components.every(c => typeof c === 'string')
      && e.cover === undefined
    : e.template?.kind === 'cover'
      ? validRecipe(e.template) && validCover(e.cover) && e.from === undefined && e.components === undefined && e.light === undefined
      : validRecipe(e.template) && e.from === undefined && e.components === undefined && e.light !== undefined && e.cover === undefined)));
// An area light's glowing piece as the project sets it: { target, owner: { target, component } } or owner null (kept
// fixed).
export const validBinding = b => isTarget(b?.target) && (b.owner === null
  || (b.owner && isTarget(b.owner.target) && typeof b.owner.component === 'string'));
const validMember = m => (typeof m?.added === 'string' && Object.keys(m).length === 1)
  || (typeof m?.group === 'string' && Object.keys(m).length === 1)
  || (typeof m?.building === 'string' && Object.keys(m).length === 1) || isTarget(m);
export const validGroup = g => typeof g?.id === 'string' && Array.isArray(g.members) && g.members.length >= 2
  && g.members.every(validMember) && new Set(g.members.map(memberKey)).size === g.members.length
  && [undefined, true, false].includes(g.locked) && [undefined, true, false].includes(g.breakTogether);

export const uuid = () => globalThis.crypto?.randomUUID?.()
  ?? '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c => (c ^ Math.random() * 16 >> c / 4).toString(16));
// Output names (output names plan): the map's package name and its edit patch's, { shipAs, patch }. The server gives a
// new project's (api.names: its project name as one word, at most 24 characters, numbered when taken; the Save dialog
// shows it) and keeps them fixed once the project is saved (tools/viewer/outputnames.py, projects.py). Projects saved
// before 16 November 2026 keep the names they have (the base map's, the project's and a piece of the id).
/** The base map a project binds to: the scene's map as exported. */
export const sourceOf = (mapId, data) => ({ map: mapId, package: data.source.file.split(/[\\/]/).at(-1),
                                            sha256: data.source.sha256, exporterVersion: data.exporterVersion });
/** A new project's document, bound to the scene's base map, with the output names the Save dialog showed. */
export function newDocument(name, mapId, data, output) {
  const id = uuid();
  return {
    schema: SCHEMA, schemaVersion: SCHEMA_VERSION, id, name, mode: 'edit',
    source: sourceOf(mapId, data),
    output: { shipAs: output.shipAs, patch: output.patch },
    overrides: [], added: [], groups: [], areaLightBindings: [],
  };
}

const at = id => `/projects/${encodeURIComponent(id)}`;
/** A draft's DELETE query: its owner (blank: the draft kept before drafts had owners) and, for one shown, its time. */
export const draftQuery = (owner, savedAt = null) => new URLSearchParams({ owner: owner ?? '', ...(savedAt ? { savedAt } : {}) }).toString();
export const api = {
  list: () => call('GET', '/projects.json'),
  // the map name saving under `name` gives: a new project's ({ fresh: true, output, reason }), or with `target` (a
  // project's id: the open one, or one replaced) that project's fixed one ({ fresh: false, output, conflicts })
  names: (name, map, target = null) => call('POST', '/projects/output-names', { name, map, target }),
  load: id => call('GET', `${at(id)}/project.json`),
  // extra: { owner } (the page session saving: its draft for recovery goes), { pictureFrom } (Save as: the project
  // whose kept map picture the document names, copied with the save)
  save: (id, document, expectedRevision, extra = {}) => call('PUT', `${at(id)}/project.json`, { expectedRevision, document, ...extra }),
  // Drafts for recovery (review finding 3), one per page session (`owner`, the id a page makes when it loads):
  // recovery() is the newest ({ owner, savedAt, baseRevision, others, ... }) or null; keepRecovery(id, { owner, ... })
  // answers { revision, stale }; dropRecovery deletes that owner's draft alone (null: one kept before drafts had
  // owners), and with savedAt only while it is still that one.
  recovery: id => call('GET', `${at(id)}/recovery.json`),
  keepRecovery: (id, state) => call('PUT', `${at(id)}/recovery.json`, state),
  dropRecovery: (id, owner, savedAt = null) => call('DELETE', `${at(id)}/recovery.json?${draftQuery(owner, savedAt)}`),
  // Build (tools/viewer/builds.py): the saved project into a variant package; build.json follows it. quick: the
  // edit made in the map without baking its lighting.
  build: (id, quick = false) => call('POST', `${at(id)}/build`, quick ? { quick: true } : {}),
  buildStatus: id => call('GET', `${at(id)}/build.json`),
  // attempt: only that launch (a page that saw an older build stops no newer one)
  cancelBuild: (id, attempt = null) => call('POST', `${at(id)}/build-cancel`, attempt ? { attempt } : {}),
  report: id => call('POST', `${at(id)}/report`, {}),
  // a folder or file of the builds folder shown in Windows Explorer (a folder opened, a file selected)
  reveal: path => call('POST', '/builds/reveal', { path }),
};
