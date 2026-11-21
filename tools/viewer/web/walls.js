// Made walls on the page (private/plans/done/custom-geometry-implementation-plan.md, stage M1): what is pure about the
// wall tool. A made wall is an added copy of its look's donor (a fracturing wall of the game's) that carries
// `generated: { kind: 'fracWall', version: 1, wall }`, the wall's numbers in the donor mesh's frame
// (tools/bake/frac_wall.py): `x0` and `x1` its tile edges along the wall (the tool always writes x0 0 and puts the
// piece at the wall's start), `openings` [{ x0, x1, z0, z1 }] (rectangles through it; z 0 is the floor the wall
// stands on, its bottom WALL.bottom), `seed` (the break pattern), `storeys` (1 to WALL.maxStoreys, left out for its
// look's own: stage M2; custom geometry editing plan B4). Its solid stops WALL.endInset short of each end. A wall
// longer than WALL.pieceTiles or taller than its look's storeys is drawn whole and made by the Build as pieces of
// those sizes, joined end to end and stacked (tools/bake/made_split.py; the editing plan's D-3).
// Locations are game units (x, y, z up), rotations rotator units (pitch, yaw, roll).
import { QUARTER, TILE } from './constants.js';
import { catalogued } from './looks.js';
import { stepped } from './snap_steps.js';
import { plural } from './dom_words.js';

// The looks a wall is drawn in: each a donor (one of the game's fracturing walls, placed in a map of the base game), the
// mesh its actor holds, and what it looks like in words. M1 has one, the Bar's inside wall (frac_wall.RECIPE).
export const WALL_LOOKS = [{ id: 'bar-inside', name: 'Bar inside wall', package: 'URB_Bar', actor: 'XComDecoFracLevelActor_17',
  mesh: 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', lwrOnly: false,
  words: 'one or two storeys: diamond tiles under dark panelling on one side, brick over panelling on the other, with a skirting and a cornice' }];
// The one look of M1, the Bar's inside wall (frac_wall.RECIPE): its heights over the floor (a two-storey wall's top and
// face), and the tool's limits: any length and height up to these (the compiler's made_edits.py MADE_MAX_TILES,
// MADE_MAX_STOREYS), the Build cutting it into pieces of at most pieceTiles and its look's storeys.
export const WALL = { endInset: 8, bottom: -16, top: 384, faceTop: 372, storey: 192, half: 12, minTiles: 1, maxTiles: 128,
                      maxStoreys: 12, pieceTiles: 16 };
// The lengths of made wall the editor's server draws a mesh for (scene_pieces.js madeShapeOf; generated.py's
// MIN_LENGTH and MAX_LENGTH, pinned in tests/twin_constants.json, review finding 55); the mesh's other numbers are
// WALL's
export const FRAC_WALL = { minLength: 40, maxLength: WALL.maxTiles * TILE };
// A wall's tops by its storeys (frac_wall.shaped: one storey stands to 192, as the game's one-storey inside walls do;
// its cornice is the top 12 and an opening's top stays 24 under the top, as on a tall wall)
const STOREY_TOPS = { 1: 192, 2: 384 };
// A gap's limits: the highest its top goes under the cornice (past it, the gap is cut through to the wall's top), the
// smallest sizes, the Alt step, and the threshold a doorway starts with: the strip of wall kept under it, so no gap is
// left under its door (the user, 19 November 2026; under the game's cover line, so it gives no cover and units walk
// over it). One kind of gap since 19 November 2026 (the user: doorways and windows merged, every handle reaching the
// wall's edges).
export const OPENING = { topMost: 360, width: 16, height: 24, fine: 8, sill: 8 };
// The presets, as the game's are (the plan, M1: a doorway one tile wide and 176 tall with its sides on tile edges, 242
// openings in seven URB maps; the game's windows run 64 to 170 over the floor, one or two tiles wide
// (research/evidence/wall-openings.py). Ours starts at 72, so the walking sweep at 64 meets the wall under it as it
// meets the game's glass: units see through it, not climb through.
export const PRESETS = { doorway: { width: TILE, z0: OPENING.sill, z1: 160 }, window: { width: TILE, z0: 72, z1: 168 } };
// The game's sweeps over a tile's floor, along the line between two tiles' centres (research/native/cover-build.md,
// line-of-sight.md): cover 44 to 60, high or low cover 88 to 104, walking 64 (half a unit thick), sight from the eye
// tile, 96 over the floor's level.
export const SWEEP = { cover: [44, 60], high: [88, 104], walk: 64, sight: 96, half: 0.5 };

const round = (v, step) => step * Math.round(v / step);
const sign = v => (v < 0 ? -1 : 1);
const tidy = v => { const r = Math.round(v * 1e4) / 1e4; return r === 0 ? 0 : r; };

// ---- heights
// The Bar's inside wall's numbers as wallSpec gives them (its two storeys, the donor's height).
const BAR_SPEC = { bottom: WALL.bottom, top: WALL.top, faceTop: WALL.faceTop, storey: WALL.storey, endInset: WALL.endInset,
                   half: WALL.half, through: 8, sections: 6, storeys: 2, lower: true };
/** A wall's look's numbers (custom geometry plan, M4): its bottom, its top and its face's top at the donor's height,
 *  the storey a lower wall loses, its free ends' inset, its half thickness (`half`, the section's widest; `through`, its
 *  faces'), its sections, the donor's storeys (1 to 4) and whether a wall one storey tall can be made in it (`lower`:
 *  the catalogue's facts.storeys holds 1 as well, frac_wall.storeys_of). The Bar's inside wall's for a look id; a donor
 *  look's from the catalogue (looks.js); the Bar's for a donor look whose catalogue isn't read (drawn with the
 *  template's mesh). */
export function wallSpec(wall) {
  const cat = catalogued('wall', wall?.look);
  if (!cat) return BAR_SPEC;
  const r = cat.recipe, own = cat.facts?.storeys ?? [2], storeys = Math.max(...own);
  const thickness = cat.facts?.size?.thickness;
  return { bottom: r.bottom, top: r.top, faceTop: r.face?.[1] ?? r.top, storey: r.storey ?? WALL.storey, endInset: r.endInset,
           half: thickness ? thickness / 2 : r.half + 4, through: r.half, sections: r.sections ?? 6, storeys,
           lower: storeys > 1 && own.includes(1) };
}
/** A wall's storeys: its own (`storeys`), or its look's when left out (two for the Bar's, up to four for a donor's). */
export const storeysOf = wall => wall?.storeys ?? wallSpec(wall).storeys;
/** How many storeys, in words. */
export const storeyWords = n => `${['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven',
  'twelve'][n] ?? n} ${n === 1 ? 'storey' : 'storeys'}`;
/** The storeys of each piece the Build stacks for a wall `storeys` tall in a look made `own` storeys tall (and one
 *  storey where `lower`), from the bottom (made_split.levels). */
export function levelsOf(storeys, own, lower) {
  if (storeys === own || (storeys === 1 && lower)) return [storeys];
  const out = Array(Math.floor(storeys / own)).fill(own), rest = storeys - own * out.length;
  return rest ? [...out, ...(lower ? Array(rest).fill(1) : [own])] : out;
}
/** The storey counts a wall can be in its look: any up to WALL.maxStoreys where it can be made one storey, else its
 *  look's own and their multiples. */
export function storeyCounts(wall) {
  const spec = wallSpec(wall);
  return Array.from({ length: WALL.maxStoreys }, (_, k) => k + 1).filter(n => spec.lower || n % spec.storeys === 0);
}
/** The wall's top over the floor (its bottom wallSpec's), its face's top, and the highest an opening's top goes. A wall
 *  one storey tall in a taller donor's look loses the storeys over its first off its top (frac_wall.shaped); a taller
 *  one is its look's pieces stacked, each on the top of the one under it (levelsOf). */
export const wallTop = wall => {
  const spec = wallSpec(wall);
  const pieceTop = n => (n === spec.storeys ? spec.top : spec.top - spec.storey * (spec.storeys - 1));
  return levelsOf(storeysOf(wall), spec.storeys, spec.lower).reduce((top, n) => top + pieceTop(n) - spec.bottom, spec.bottom);
};
export const faceTopOf = wall => { const spec = wallSpec(wall); return wallTop(wall) - (spec.top - spec.faceTop); };
export const topMostOf = wall => { const spec = wallSpec(wall); return wallTop(wall) - Math.max(WALL.top - OPENING.topMost, spec.top - spec.faceTop); };
/** The wall at `storeys` (its look's own leaves the number out). A gap cut through the wall's top stays cut through the
 *  new top; another the lower wall can't hold has its top brought down to the highest a top goes under the cornice;
 *  one left smaller than OPENING.height (a window in the upper storey) goes. Gives { wall, cut (gaps brought down),
 *  removed (gaps gone) }. */
export function withStoreys(wall, storeys) {
  const { storeys: _, ...rest } = wall;
  const out = storeys === wallSpec(rest).storeys ? rest : { ...rest, storeys };
  const top = wallTop(out), most = topMostOf(out), through = wallTop(wall);
  let cut = 0, removed = 0;
  const openings = [];
  for (const o of wall.openings ?? []) {
    const z1 = o.z1 >= through - 1e-6 ? top : o.z1 <= most + 1e-6 ? o.z1 : most;
    if (z1 - Math.max(0, o.z0) < OPENING.height - 1e-6) { removed++; continue; }
    if (z1 !== o.z1 && o.z1 < through - 1e-6) cut++;
    openings.push(z1 === o.z1 ? o : { ...o, z1 });
  }
  return { wall: { ...out, openings }, cut, removed };
}
/** The wall after its top handle moved `delta` units up: the storey count (storeyCounts) whose top is nearest the
 *  handle (custom geometry editing plan, B4: as many storeys as the user drags up). Gives withStoreys' { wall, cut,
 *  removed }. */
export function raisedWall(wall, delta) {
  const now = storeysOf(wall), want = wallTop(wall) + delta;
  const next = storeyCounts(wall).map(n => [Math.abs(wallTop({ ...wall, storeys: n }) - want), n]).sort((a, b) => a[0] - b[0])[0]?.[1] ?? now;
  return next === now ? { wall, cut: 0, removed: 0 } : withStoreys(wall, next);
}
/** The wall a storey taller (`step` 1) or lower (-1), in the counts its look takes (storeyCounts); null past the ends. */
export function steppedStoreys(wall, step) {
  const counts = storeyCounts(wall), now = storeysOf(wall);
  const next = step > 0 ? counts.find(n => n > now) : [...counts].reverse().find(n => n < now);
  return next === undefined ? null : withStoreys(wall, next);
}
/** A wall changed from look `old` to the look in `numbers`, its gaps on the new look's bottom: one cut to the old
 *  bottom (a doorway to the floor) is cut to the new one, and none starts below it (a door added before a look whose
 *  bottom is higher had kept the old bottom, and the wall then had no handles: the user, 19 November 2026). */
export function openingsInLook(old, numbers) {
  const was = wallSpec(old).bottom, bottom = wallSpec(numbers).bottom;
  if (!(numbers.openings ?? []).length) return numbers;
  return { ...numbers, openings: numbers.openings.map(o => (o.z0 !== bottom && (o.z0 <= was + 1e-6 || o.z0 < bottom) ? { ...o, z0: bottom } : o)) };
}
/** The storeys a wall changed to another look keeps: one storey when it was one and the new look can be made so; the
 *  new look's own when it stood at its old look's own; else as many as it had (the Build stacks them), in the counts
 *  the new look takes. */
export function storeysInLook(old, numbers) {
  const n = storeysOf(old), spec = wallSpec(numbers);
  if (n === 1 && spec.lower) return 1;
  if (n === wallSpec(old).storeys) return spec.storeys;
  if (spec.lower) return n;
  return Math.min(Math.floor(WALL.maxStoreys / spec.storeys) * spec.storeys, Math.max(spec.storeys, Math.round(n / spec.storeys) * spec.storeys));
}

/** Whether `wall` is numbers this tool makes: tile edges 0 and a whole number of tiles (1 to WALL.maxTiles), 1 to
 *  WALL.maxStoreys storeys, gaps inside it and apart, none taking the whole wall, a whole-number seed. A gap may start
 *  below the wall's bottom: it is cut to the floor, as one at the bottom is (openingEdges; the Build cuts it so too). */
export function toolWall(wall) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!wall || wall.x0 !== 0 || !finite(wall.x1) || !Number.isInteger(wall.seed ?? 1)
    || !(wall.storeys === undefined || (Number.isInteger(wall.storeys) && wall.storeys >= 1 && wall.storeys <= WALL.maxStoreys))) return false;
  const tiles = wall.x1 / TILE;
  if (!Number.isInteger(tiles) || tiles < WALL.minTiles || tiles > WALL.maxTiles) return false;
  const list = sortedOpenings(wall.openings ?? []);
  return list.every((o, i) => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o[k])) && o.x0 >= 0 && o.x1 <= wall.x1 && o.x1 > o.x0
    && o.z1 > o.z0 && o.z1 > wallSpec(wall).bottom && o.z1 <= wallTop(wall) && !takesWhole(wall, o) && (i === 0 || list[i - 1].x1 <= o.x0));
}
export const sortedOpenings = list => [...list].sort((a, b) => a.x0 - b.x0 || a.z0 - b.z0);
/** Which of the wall's edges a gap reaches: { bottom (cut to the wall's bottom, through the floor), top (cut through
 *  the wall's top), start, end (cut away to that end) }. */
export function openingEdges(wall, o) {
  return { bottom: o.z0 <= wallSpec(wall).bottom + 1e-6, top: o.z1 >= wallTop(wall) - 1e-6, start: o.x0 <= 1e-6, end: o.x1 >= wall.x1 - 1e-6 };
}
/** Whether a gap would take the whole wall away (every edge reached). */
const takesWhole = (wall, o) => Object.values(openingEdges(wall, o)).every(Boolean);
export const tilesOf = wall => Math.round(wall.x1 / TILE);

// ---- drawing: the pose and numbers of a wall dragged out on the ground
const YAWS = [[0, 1, 0], [1, 1, 1], [0, -1, 2], [1, -1, 3]];      // [axis, direction, quarter turns]
/** The wall a drag from `start` to `end` ([x, y] on the ground, game units) draws: from the tile edge nearest the start
 *  to the one nearest the end, along x or y by the drag's longer way, on the tile line nearest the start; at least one
 *  tile (in the drag's direction), at most WALL.maxTiles. `origin`: the tile grid's corner (tile edges at origin +
 *  96k); `template`: the donor's location and rotation (the copy keeps its pitch and roll and turns by quarter turns
 *  from its yaw); `floor`: the height of the floor under the start, where the wall stands (its bottom WALL.bottom
 *  under it). A made wall's height is free: its columns are made for where it stands, so the pose rule's whole
 *  storeys from the donor don't hold it (the donor's height on its own map seldom matches this map's floors).
 *  Gives { location, rotation, wall: { x0: 0, x1, openings: [], seed }, axis, direction, tiles }. */
export function drawnWall(start, end, { origin, template, floor, seed = 1 }) {
  const d = [end[0] - start[0], end[1] - start[1]], axis = Math.abs(d[0]) >= Math.abs(d[1]) ? 0 : 1, across = 1 - axis;
  const edge = (v, k) => origin[k] + round(v - origin[k], TILE);
  const a = edge(start[axis], axis);
  let b = edge(end[axis], axis);
  if (b === a) b = a + TILE * sign(d[axis]);
  const direction = sign(b - a), tiles = Math.min(WALL.maxTiles, Math.round(Math.abs(b - a) / TILE));
  const location = [0, 0, tidy(floor)];
  location[axis] = a; location[across] = edge(start[across], across);
  return { location: location.map(tidy), rotation: wallRotation(template.rotation, axis, direction),
           wall: { x0: 0, x1: tiles * TILE, openings: [], seed }, axis, direction, tiles };
}
/** The room a drag from `start` to `end` draws (custom geometry plan, M3 item 6, D6): the rectangle between the tile
 *  edges nearest them (a click with no drag: one tile; each side at most WALL.maxTiles), its four sides walls running
 *  round it anticlockwise from the corner nearest the start's lower x and y, so each has its first face (the look's
 *  side A) inside; their corners meet, so they join (wallJoins). One doorway, in the middle tile of the side nearest
 *  `camera` ([x, y] on the ground). Gives { walls: [{ location, rotation, wall }] (south, east, north, west),
 *  tiles: [along x, along y], door (the side with the doorway) }. */
export function drawnRoom(start, end, { origin, template, floor, seed = 1, camera = null }) {
  const edge = (v, k) => origin[k] + round(v - origin[k], TILE);
  const span = k => {
    const a = edge(start[k], k);
    let b = edge(end[k], k);
    if (b === a) b = a + TILE * sign(end[k] - start[k]);
    const tiles = Math.min(WALL.maxTiles, Math.round(Math.abs(b - a) / TILE));
    const lo = Math.min(a, a + sign(b - a) * tiles * TILE);
    return [lo, lo + tiles * TILE, tiles];
  };
  const [x0, x1, nx] = span(0), [y0, y1, ny] = span(1);
  const z = tidy(floor);
  // [axis, direction, from corner]: south along +x, east along +y, north along -x, west along -y
  const sides = [[0, 1, [x0, y0]], [1, 1, [x1, y0]], [0, -1, [x1, y1]], [1, -1, [x0, y1]]];
  const walls = sides.map(([axis, direction, at], k) => ({
    location: [tidy(at[0]), tidy(at[1]), z], rotation: wallRotation(template.rotation, axis, direction),
    wall: { x0: 0, x1: (axis === 0 ? nx : ny) * TILE, openings: [], seed: seed + k } }));
  const middles = [[(x0 + x1) / 2, y0], [x1, (y0 + y1) / 2], [(x0 + x1) / 2, y1], [x0, (y0 + y1) / 2]];
  const c = camera ?? [x0, y0 - 1];
  const door = middles.map((m, k) => [Math.hypot(m[0] - c[0], m[1] - c[1]), k]).sort((a, b) => a[0] - b[0])[0][1];
  walls[door].wall = withOpening(walls[door].wall, 'doorway').wall;
  return { walls, tiles: [nx, ny], door };
}
/** The rotation that runs the wall's +x along `axis` in `direction`, a whole number of quarter turns from the donor's. */
export function wallRotation(templateRotation, axis, direction) {
  const turns = YAWS.find(([x, s]) => x === axis && s === direction)[2];
  const base = Math.trunc(templateRotation[1]);
  const k = Math.round((turns * QUARTER - base) / QUARTER);
  return [Math.trunc(templateRotation[0]), base + k * QUARTER, Math.trunc(templateRotation[2])];
}
/** The wall's direction along the ground for a yaw (its +x): [dx, dy], each -1, 0 or 1. */
export function wallDirection(yaw) {
  const t = ((Math.round(yaw / QUARTER) % 4) + 4) % 4;
  return [[1, 0], [0, 1], [-1, 0], [0, -1]][t];
}

// ---- the ends
/** The wall with one end moved `delta` units along it ('x1' the far end, 'x0' the start), in whole tiles, kept to
 *  WALL.minTiles..maxTiles. The openings stay where they are in the world: moving the start shifts them in the wall's
 *  frame, and those the wall no longer holds whole are dropped. Gives { wall, shift (how far the start moved along the
 *  wall), removed (how many openings went) }. */
export function resizedWall(wall, end, delta) {
  const tiles = tilesOf(wall);
  let step = Math.round(delta / TILE);
  if (end === 'x1') step = Math.max(WALL.minTiles - tiles, Math.min(WALL.maxTiles - tiles, step));
  else step = Math.min(tiles - WALL.minTiles, Math.max(tiles - WALL.maxTiles, step));
  const shift = end === 'x0' ? step * TILE : 0, length = end === 'x1' ? (tiles + step) * TILE : (tiles - step) * TILE;
  const moved = (wall.openings ?? []).map(o => ({ ...o, x0: tidy(o.x0 - shift), x1: tidy(o.x1 - shift) }));
  const kept = moved.filter(o => o.x0 >= -1e-6 && o.x1 <= length + 1e-6);
  return { wall: { ...wall, x0: 0, x1: length, openings: kept }, shift, removed: moved.length - kept.length };
}
/** The pose of a wall whose start moved `shift` units along it. */
export function shiftedLocation(location, rotation, shift) {
  const [dx, dy] = wallDirection(rotation[1]);
  return [tidy(location[0] + dx * shift), tidy(location[1] + dy * shift), location[2]];
}

// ---- flip and reshuffle
/** The wall turned round (its two faces swapped) where it stands: its start at its old far end, a half turn of yaw, the
 *  openings mirrored so they stay where they were. Gives { wall, location, rotation }. */
export function flippedWall(wall, location, rotation) {
  const length = wall.x1;
  const openings = sortedOpenings((wall.openings ?? []).map(o => ({ ...o, x0: tidy(length - o.x1), x1: tidy(length - o.x0) })));
  return { wall: { ...wall, openings }, location: shiftedLocation(location, rotation, length),
           rotation: [rotation[0], rotation[1] + 2 * QUARTER, rotation[2]] };
}
/** Another break pattern: a new seed (from `pick`, a number from 0 to 1), never the old one. */
export function reshuffled(wall, pick = Math.random()) {
  let seed = 1 + Math.floor(pick * 999999);
  if (seed === (wall.seed ?? 1)) seed = seed % 999999 + 1;
  return { ...wall, seed };
}

// ---- openings
/** The wall with a new opening of `kind` ('doorway' or 'window', the preset's size) in the free tile nearest its
 *  middle; null when no tile is free. Gives { wall, index } (its index in the wall's sorted openings). */
export function withOpening(wall, kind) {
  const preset = PRESETS[kind], tiles = tilesOf(wall), list = wall.openings ?? [];
  const free = k => !list.some(o => o.x0 < (k + 1) * TILE - 1e-6 && o.x1 > k * TILE + 1e-6);
  const middle = wall.x1 / 2;
  const order = [...Array(tiles).keys()].filter(free).sort((a, b) => Math.abs((a + 0.5) * TILE - middle) - Math.abs((b + 0.5) * TILE - middle) || a - b);
  if (!order.length) return null;
  const k = order[0], o = { x0: k * TILE, x1: k * TILE + preset.width, z0: preset.z0, z1: preset.z1 };
  const openings = sortedOpenings([...list, o]);
  return { wall: { ...wall, openings }, index: openings.indexOf(o) };
}
/** The wall without opening `index` (of its sorted openings). */
export function withoutOpening(wall, index) {
  return { ...wall, openings: sortedOpenings(wall.openings ?? []).filter((_, i) => i !== index) };
}
/** A gap's handles: its middle (slides it along the wall), its two sides, its top and its bottom. */
export const openingParts = () => ['middle', 'x0', 'x1', 'z1', 'z0'];
/** The wall with one part of gap `index` moved `delta` units (along the wall for the middle and sides, up for the top
 *  and bottom), the distance moved in steps of `along` and `up` (the editor's snap, snap_steps.js: 0 when it is off, so
 *  the handles move smoothly). The gap stays off its neighbours, at least OPENING.width wide (a tile when it moves by
 *  whole tiles) and OPENING.height tall, and reaches the wall's edges: a side to the wall's end, the bottom at or under
 *  the floor to the wall's bottom (its handle stands on the floor), the top past topMostOf(wall) through the wall's
 *  top. One part moved to the last edge a gap hasn't reached stops short of it (topMostOf, OPENING.sill, a side a step
 *  in, the gap at least OPENING.width wide): a gap never takes the whole wall. Gives the wall. */
export function movedOpening(wall, index, part, delta, { along = TILE, up = OPENING.fine } = {}) {
  const list = sortedOpenings(wall.openings ?? []);
  if (!list[index]) return wall;
  const o = { ...list[index] };
  const before = index > 0 ? list[index - 1].x1 : 0, after = index < list.length - 1 ? list[index + 1].x0 : wall.x1;
  const least = along >= TILE ? TILE : OPENING.width, bottom = wallSpec(wall).bottom, top = wallTop(wall);
  if (part === 'middle') {
    // (`delta` [along, up]: the middle handle drags in the wall's plane, the user, 19 November 2026; a number: along)
    const [dx, dz] = Array.isArray(delta) ? delta : [delta, 0];
    const width = o.x1 - o.x0;
    let x0 = o.x0 + stepped(dx, along);
    x0 = Math.max(before, Math.min(after - width, x0));
    o.x0 = tidy(x0); o.x1 = tidy(x0 + width);
    // up and down its height kept, from the floor (a doorway's bottom is the floor) to the highest a gap's top goes
    // under the wall's top; at the floor it is cut to the wall's bottom (a doorway), off it a window. One cut through
    // the wall's top stays where it is up and down.
    const lo = Math.max(0, o.z0), height = o.z1 - lo, most = topMostOf(wall);
    if (dz && o.z1 < top - 1e-6 && height <= most + 1e-6) {
      const z0 = Math.max(0, Math.min(most - height, lo + stepped(dz, up)));
      o.z0 = z0 <= 1e-6 ? bottom : tidy(z0);
      o.z1 = tidy(z0 + height);
    }
  } else if (part === 'x0') {
    o.x0 = tidy(Math.max(before, Math.min(o.x1 - least, o.x0 + stepped(delta, along))));
  } else if (part === 'x1') {
    o.x1 = tidy(Math.min(after, Math.max(o.x0 + least, o.x1 + stepped(delta, along))));
  } else if (part === 'z1') {
    const v = Math.max(Math.max(0, o.z0) + OPENING.height, o.z1 + stepped(delta, up));
    o.z1 = v > topMostOf(wall) + 1e-6 ? top : tidy(v);
  } else if (part === 'z0') {
    const v = Math.min(o.z1 - OPENING.height, Math.max(0, o.z0) + stepped(delta, up));
    o.z0 = v <= 1e-6 ? bottom : tidy(v);
  }
  if (takesWhole(wall, o)) {
    // (a side stops a step in, and the gap keeps at least OPENING.width: on a one-tile wall moved by whole tiles, the
    // side stays where it was rather than the gap closing up; review finding 32)
    const was = list[index];
    if (part === 'z1') o.z1 = topMostOf(wall);
    else if (part === 'z0') o.z0 = OPENING.sill;
    else if (part === 'x0') {
      const most = Math.min(least, o.x1 - OPENING.width);
      o.x0 = tidy(was.x0 > 0 ? Math.min(most, was.x0) : most);
    } else if (part === 'x1') {
      const least1 = Math.max(wall.x1 - least, o.x0 + OPENING.width);
      o.x1 = tidy(was.x1 < wall.x1 ? Math.max(least1, was.x1) : least1);
    } else return wall;
  }
  const openings = list.map((p, i) => (i === index ? o : p));
  return { ...wall, openings };
}

// ---- what an opening does in play
/** The centres along the wall (in its frame) of the tiles whose centre line passes through the opening. */
const centresThrough = (wall, o) => [...Array(tilesOf(wall)).keys()].map(k => (k + 0.5) * TILE)
  .filter(c => c > o.x0 + 1 && c < o.x1 - 1);
/** What the game does at an opening, by its sweeps at the tile centres it spans: { tiles, walk, climb, sight, cover
 *  ('none' | 'low' | 'high' | 'whole': the wall's own cover at those tiles) }. `climb`: units vault through it, as
 *  through the game's windows: the wall under it is low cover, and the game gives a low-cover tile its ClimbOver
 *  (EXP-73, F-126). */
export function openingPlay(wall, o) {
  const tiles = centresThrough(wall, o).length;
  const spans = (a, b) => o.z0 < a && o.z1 > b;
  if (!tiles) return { tiles, walk: false, climb: false, sight: false, cover: 'whole' };
  const coverHit = !spans(SWEEP.cover[0], SWEEP.cover[1]), highHit = !spans(SWEEP.high[0], SWEEP.high[1]);
  const walk = spans(SWEEP.walk - SWEEP.half, SWEEP.walk + SWEEP.half), cover = !coverHit ? 'none' : highHit ? 'high' : 'low';
  return { tiles, walk, climb: !walk && cover === 'low', sight: spans(SWEEP.sight - SWEEP.half, SWEEP.sight + SWEEP.half), cover };
}
const size = v => (v % TILE === 0 ? `${plural(v / TILE, 'tile')} wide` : `${Math.round(v)} wide`);
/** A gap in words, for the piece panel's list: "Gap, 1 tile wide, from 8 over the floor to 160", "Gap, 1 tile wide,
 *  from the wall's bottom to its top, at its end". */
export function openingWords(o, wall) {
  const e = openingEdges(wall, o), ends = [e.start && 'its start', e.end && 'its end'].filter(Boolean);
  const from = e.bottom ? 'from the wall\'s bottom' : `from ${Math.round(o.z0)} over the floor`;
  return `Gap, ${size(o.x1 - o.x0)}, ${from} to ${e.top ? 'its top' : Math.round(o.z1)}${ends.length ? `, at ${ends.join(' and ')}` : ''}`;
}
/** What the game does there, in a sentence or two (`door`: a door stands in it). */
export function playWords(wall, o, { door = false } = {}) {
  const p = openingPlay(wall, o);
  if (!p.tiles) return 'No tile\'s centre line passes through it: units can\'t walk or see through it, and the wall gives cover there as if whole.';
  const out = [];
  out.push(p.walk ? 'units walk through it' : p.climb ? 'units climb through it' : 'units can\'t walk through it');
  out.push(p.sight ? 'see and shoot through it' : 'don\'t see through it');
  const cover = { none: 'it gives no cover', low: 'the wall under it gives low cover', high: 'the wall under it gives high cover' }[p.cover];
  let words = `${out.join(', ')}; ${cover}.`;
  if (p.walk && p.cover === 'none' && !door) words += ' A unit in a gap with no door has cover toward its sides: put a door in it (a door from the Add panel), as the game\'s doorways have.';
  return words[0].toUpperCase() + words.slice(1);
}
// ---- joints (custom geometry plan, M3 item 2; made_edits.py wall_joins is the twin)
// An end's style for its solid (frac_wall.END_INSETS: how far in from its tile edge it stops) and how it meets: the
// game's inside walls stop square 8 short of a wall they meet (a T's stem, as a free end); at an L one runs through to
// the other's far face and the other butts on its face; end to end both reach the line (research/evidence/wall-joints.py).
export const END_INSETS = { free: WALL.endInset, line: 0, through: -8 };
/** A wall's end styles' insets by its look (frac_wall.end_insets): a free end its endInset, 'line' on the tile edge,
 *  'through' its faces' half thickness past it. */
export const endInsetsOf = wall => { const spec = wallSpec(wall); return { free: spec.endInset, line: 0, through: -spec.through }; };
const JOIN_REACH = 1, JOIN_FLOOR = 32;
/** Where made walls meet: `walls` [{ key, location, rotation, wall }] gives { key: { ends: [the x0 end's style, the x1
 *  end's] ('free' | 'through' | 'line'), joins: [{ end (0 | 1), how ('corner' (runs through) | 'butt' | 'line' |
 *  'stem'), other (key) }] } }. The rule is compiler.wall_joins's, word for word. */
export function wallJoins(walls) {
  const info = [], out = {};
  for (const w of walls) {
    out[w.key] = { ends: ['free', 'free'], joins: [] };
    const [p, yawRaw, r] = w.rotation;
    if (Math.round(p) % 65536 || Math.round(r) % 65536) continue;
    const yaw = yawRaw * 2 * Math.PI / 65536, d = [Math.cos(yaw), Math.sin(yaw)];
    const x0 = w.wall.x0, x1 = w.wall.x1, top = wallTop(w.wall);
    info.push({ key: w.key, d, x0, x1, p: [x0, x1].map(x => [w.location[0] + d[0] * x, w.location[1] + d[1] * x]),
                z: [w.location[2] + wallSpec(w.wall).bottom, w.location[2] + top], height: top, length: x1 - x0, loc: [w.location[0], w.location[1]] });
  }
  const floor = (a, b) => Math.min(a.z[1], b.z[1]) - Math.max(a.z[0], b.z[0]) > JOIN_FLOOR;
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const through = (pt, b) => {
    const vx = pt[0] - b.loc[0], vy = pt[1] - b.loc[1], t = vx * b.d[0] + vy * b.d[1];
    return Math.abs(b.d[0] * vy - b.d[1] * vx) <= JOIN_REACH && b.x0 + JOIN_REACH < t && t < b.x1 - JOIN_REACH;
  };
  const leaving = (w, m) => {
    const [dx, dy] = m === 0 ? w.d : [-w.d[0], -w.d[1]];
    return Math.abs(dx) > Math.abs(dy) ? (dx > 0.5 ? 0 : 2) : (dy > 0.5 ? 1 : 3);
  };
  const done = new Set();
  info.forEach((a, i) => {
    for (const k of [0, 1]) {
      if (done.has(`${i}:${k}`)) continue;
      const pt = a.p[k], ends = [];
      info.forEach((b, j) => { for (const m of [0, 1]) if ((j === i || floor(a, b)) && dist(b.p[m], pt) <= JOIN_REACH) ends.push([j, m]); });
      ends.forEach(([j, m]) => done.add(`${j}:${m}`));
      const passes = info.map((b, j) => j).filter(j => j !== i && floor(a, info[j]) && through(pt, info[j]));
      if (ends.length < 2 && !passes.length) continue;
      const style = [];
      if (passes.length) {
        for (const [j, m] of ends) style.push([j, m, 'free', 'stem', info[passes[0]].key]);
      } else {
        const by = new Map();
        for (const [j, m] of ends) { const q = leaving(info[j], m); by.set(q, [...(by.get(q) ?? []), [j, m]]); }
        if ([...by.values()].some(v => v.length > 1)) continue;
        const pairs = [0, 1].filter(q => by.has(q) && by.has(q + 2));
        if (pairs.length) {
          const line = pairs[0], [ja, ma] = by.get(line)[0], [jb, mb] = by.get(line + 2)[0];
          style.push([ja, ma, 'line', 'line', info[jb].key], [jb, mb, 'line', 'line', info[ja].key]);
          for (const q of line === 0 ? [1, 3] : [0, 2]) if (by.has(q)) { const [j, m] = by.get(q)[0]; style.push([j, m, 'free', 'stem', info[ja].key]); }
        } else if (ends.length === 2) {
          let [[ja, ma], [jb, mb]] = ends;
          const rank = w => [w.height, w.length, Math.abs(w.d[0]) > Math.abs(w.d[1]) ? 1 : 0];
          const less = (x, y) => { for (let n = 0; n < 3; n++) if (x[n] !== y[n]) return x[n] < y[n]; return false; };
          if (less(rank(info[ja]), rank(info[jb]))) [[ja, ma], [jb, mb]] = [[jb, mb], [ja, ma]];
          style.push([ja, ma, 'through', 'corner', info[jb].key], [jb, mb, 'free', 'butt', info[ja].key]);
        }
      }
      for (const [j, m, shape, how, other] of style) {
        const rec = out[info[j].key];
        rec.ends[m] = shape;
        rec.joins.push({ end: m, how, other });
      }
    }
  });
  return out;
}
/** A wall's joins in words, for its panel: '' when it meets nothing. */
export function joinWords(joins) {
  const say = { corner: 'runs through at a corner', butt: 'butts on another wall at a corner', line: 'meets another wall end to end', stem: 'stops against another wall' };
  if (!joins?.length) return '';
  const byEnd = [0, 1].map(e => joins.filter(j => j.end === e).map(j => say[j.how]));
  const parts = byEnd.map((w, e) => (w.length ? `${e === 0 ? 'its start' : 'its far end'} ${w.join(', ')}` : '')).filter(Boolean);
  return `Joined: ${parts.join('; ')}. A break passes between joined walls, as between the game's.`;
}
/** The wall's size in words: "4 tiles long, two storeys (400 tall)" or "..., one storey (208 tall)". */
export const wallWords = wall => `${plural(tilesOf(wall), 'tile')} long, ${storeyWords(storeysOf(wall))} (${wallTop(wall) - wallSpec(wall).bottom} tall)`;

// ---- floors and roofs (custom geometry plan, M5): a slab is an added copy of its look's donor (one of the game's
// fracturing floors or roofs) carrying `generated: { kind: 'fracSlab', version: 1, slab }`, its numbers in the donor
// mesh's frame (tools/bake/frac_slab.py): `x0`, `x1`, `y0`, `y1` its footprint on tile lines (the tool always writes
// x0 and y0 0 and puts the piece at the footprint's corner, its mesh's axes the world's), `holes` [{ x0, x1, y0, y1 }]
// (whole tiles inside it), `seed`, `look` (left out, the first). Its plate lies between its look's heights.
export const SLAB_LOOKS = [
  { id: 'roof', name: 'Roof', role: 'roof', package: 'URB_Bar', actor: 'XComFracLevelActor_3',
    mesh: 'ComKit_Meshes.Roofing.Roof_BarrierSmallFloor_FRACTURED', lwrOnly: false, bottom: -2, top: 2,
    words: 'a flat roof: gravel and asphalt on top, ceiling tiles under it' },
  { id: 'floor', name: 'Upper floor', role: 'floor', package: 'URB_Bar', actor: 'XComFracLevelActor_17',
    mesh: 'ComKit_Meshes.Cores.Core_384FloorB_FRACTURED', lwrOnly: false, bottom: 192, top: 194,
    words: "a storey floor: dark brown floor tiles on top, butcher's tiles under it" }];
// (any size up to maxTiles each way: the Build cuts it into slabs of at most pieceTiles, made_split)
export const SLAB = { maxTiles: 128, maxHoles: 256, pieceTiles: 16 };
/** A slab's look: one of SLAB_LOOKS by its id, or a donor look (M4: { mesh, measure }) as the catalogue has it, with
 *  its heights and role (null when no catalogue read holds it). */
export function slabLookOf(slab) {
  const look = slab?.look ?? SLAB_LOOKS[0].id;
  if (typeof look !== 'object') return SLAB_LOOKS.find(l => l.id === look) ?? null;
  const cat = catalogued('slab', look);
  return cat ? { id: null, name: cat.name, role: cat.facts?.role === 'floor' ? 'floor' : 'roof', package: cat.map, actor: cat.actor,
                 mesh: cat.mesh, lwrOnly: Boolean(cat.lwrOnly), bottom: cat.recipe.bottom, top: cat.recipe.top,
                 words: cat.setting ?? '', donor: { mesh: look.mesh, measure: look.measure }, sections: cat.recipe.sections ?? 2 } : null;
}
export const slabTiles = slab => [Math.round((slab.x1 - slab.x0) / TILE), Math.round((slab.y1 - slab.y0) / TILE)];
/** Whether the slab's numbers are ones the tool edits (its own: x0 and y0 0, whole tiles, holes of whole tiles). */
export function toolSlab(slab) {
  const whole = v => Math.abs(v / TILE - Math.round(v / TILE)) < 1e-6;
  if (!slab || slab.x0 !== 0 || slab.y0 !== 0 || !whole(slab.x1) || !whole(slab.y1) || !slabLookOf(slab)) return false;
  const [nx, ny] = slabTiles(slab);
  return nx >= 1 && ny >= 1 && nx <= SLAB.maxTiles && ny <= SLAB.maxTiles
    && (slab.holes ?? []).every(h => ['x0', 'x1', 'y0', 'y1'].every(k => whole(h[k])) && 0 <= h.x0 && h.x0 < h.x1 && h.x1 <= slab.x1
                                     && 0 <= h.y0 && h.y0 < h.y1 && h.y1 <= slab.y1);
}
/** The slab a drag from `start` to `end` ([x, y] on the ground) draws: the rectangle between the tile edges nearest them
 *  (a click: one tile; at most SLAB.maxTiles each way), the piece at `z` (its plate lies its look's heights over it:
 *  an upper floor's donor carries its plate a storey up, so for one it is the floor under the start; for a roof, the
 *  roof's height). Gives { location, rotation (the donor's pitch and roll, its mesh's x along the world's),
 *  slab: { x0: 0, x1, y0: 0, y1, holes: [], seed, look? }, tiles: [along x, along y] }. */
export function drawnSlab(start, end, { origin, template, z, seed = 1, look = SLAB_LOOKS[0] }) {
  const edge = (v, k) => origin[k] + round(v - origin[k], TILE);
  const span = k => {
    const a = edge(start[k], k);
    let b = edge(end[k], k);
    if (b === a) b = a + TILE * sign(end[k] - start[k]);
    const tiles = Math.min(SLAB.maxTiles, Math.round(Math.abs(b - a) / TILE));
    return [Math.min(a, a + sign(b - a) * tiles * TILE), tiles];
  };
  const [x0, nx] = span(0), [y0, ny] = span(1);
  return { location: [tidy(x0), tidy(y0), tidy(z)], rotation: wallRotation(template.rotation, 0, 1),
           slab: { x0: 0, x1: nx * TILE, y0: 0, y1: ny * TILE, holes: [], seed,
                   ...(look.donor ? { look: { ...look.donor } } : look.id !== SLAB_LOOKS[0].id ? { look: look.id } : {}) },
           tiles: [nx, ny] };
}
const holeInside = (h, slab) => h.x0 >= 0 && h.x1 <= slab.x1 && h.y0 >= 0 && h.y1 <= slab.y1;
/** The slab with one side ('x0', 'x1', 'y0', 'y1') moved `delta` units outwards, in whole tiles, kept to
 *  1..SLAB.maxTiles. The holes stay where they are in the world (moving x0 or y0 shifts them in the slab's frame);
 *  those no longer inside go. Gives { slab, shift: [dx, dy] (how far the piece's corner moves), removed }. */
export function resizedSlab(slab, side, delta) {
  const [nx, ny] = slabTiles(slab), axis = side[0] === 'x' ? 0 : 1, n = axis ? ny : nx, key = side[0];
  const step = Math.max(1 - n, Math.min(SLAB.maxTiles - n, Math.round(delta / TILE)));
  const shift = [0, 0];
  if (side[1] === '0') shift[axis] = -step * TILE;
  const moved = (slab.holes ?? []).map(h => ({ ...h, [`${key}0`]: h[`${key}0`] - shift[axis], [`${key}1`]: h[`${key}1`] - shift[axis] }));
  const out = { ...slab, [`${key}1`]: (n + step) * TILE };
  out.holes = moved.filter(h => holeInside(h, out));
  return { slab: out, shift, removed: moved.length - out.holes.length };
}
/** The slab with a hole one tile square in the free tile nearest its middle: { slab, index } or null when every tile
 *  is a hole (or it has SLAB.maxHoles). */
export function withHole(slab) {
  const [nx, ny] = slabTiles(slab), holes = slab.holes ?? [];
  if (holes.length >= SLAB.maxHoles) return null;
  const free = [];
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
    const cx = (i + 0.5) * TILE, cy = (j + 0.5) * TILE;
    if (!holes.some(h => h.x0 < cx && cx < h.x1 && h.y0 < cy && cy < h.y1))
      free.push([Math.hypot(cx - slab.x1 / 2, cy - slab.y1 / 2), i, j]);
  }
  if (!free.length) return null;
  free.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  const [, i, j] = free[0];
  return { slab: { ...slab, holes: [...holes, { x0: i * TILE, x1: (i + 1) * TILE, y0: j * TILE, y1: (j + 1) * TILE }] }, index: holes.length };
}
export const withoutHole = (slab, index) => ({ ...slab, holes: (slab.holes ?? []).filter((_, k) => k !== index) });
/** The slab with its hole `index` changed by a drag of `delta` units: 'x' or 'y' slides it along that axis, a side
 *  ('x0', 'x1', 'y0', 'y1') moves that side; whole tiles, kept inside the slab and a tile wide at least. */
export function movedHole(slab, index, part, delta) {
  const holes = [...(slab.holes ?? [])], h = { ...holes[index] }, step = Math.round(delta / TILE) * TILE;
  const k = part[0], size = k === 'x' ? slab.x1 : slab.y1;
  if (part === 'x' || part === 'y') {
    const s = Math.max(-h[`${k}0`], Math.min(size - h[`${k}1`], step));
    h[`${k}0`] += s; h[`${k}1`] += s;
  } else if (part[1] === '0') h[part] = Math.max(0, Math.min(h[`${k}1`] - TILE, h[part] + step));
  else h[part] = Math.min(size, Math.max(h[`${k}0`] + TILE, h[part] + step));
  holes[index] = h;
  return { ...slab, holes };
}
/** Another break pattern: a new seed (`pick` in [0, 1)), never the old one (as a wall's: review finding 34). */
export const reshuffledSlab = (slab, pick = Math.random()) => ({ ...slab, seed: reshuffled(slab, pick).seed });
const tileWords = (a, b) => `${a} by ${b} tile${a * b === 1 ? '' : 's'}`;
export const holeWords = h => `Hole, ${tileWords(Math.round((h.x1 - h.x0) / TILE), Math.round((h.y1 - h.y0) / TILE))}`;
export const slabWords = slab => {
  const [nx, ny] = slabTiles(slab), n = (slab.holes ?? []).length;
  return `${tileWords(nx, ny)}${n ? `, ${plural(n, 'hole')}` : ''}`;
};
/** The roof a room drawn as `room` (drawnRoom) takes: its footprint the room's rectangle, on its walls' tops. */
export function roomRoof(room, { template, floor, storeys = 2, seed = 1, top = null }) {
  const [south] = room.walls, [nx, ny] = room.tiles;
  // (on the walls' top: `top` over the floor, the Bar's by its storeys when not given)
  return { location: [south.location[0], south.location[1], tidy(floor + (top ?? STOREY_TOPS[storeys]))], rotation: wallRotation(template.rotation, 0, 1),
           slab: { x0: 0, x1: nx * TILE, y0: 0, y1: ny * TILE, holes: [], seed }, tiles: [nx, ny] };
}

// ---- made pieces' meshes (custom geometry plan, section 0, M4, M5): the numbers a made wall or slab is drawn from by
// the editor's server (generated.py), its mesh's key, request and bounds, and the mesh record put into the scene's
// meshes (`meshes`: data.meshes, keyed by the request), on its template's materials by slot. Numbers the server can't
// draw (generated.py's limits) give {}: the template's own mesh is drawn.
/** A look in one spelling (generated.py donor_look): a look id as it is; a donor look (M4) its mesh, a ground look's
 *  material, and the measurer's version. */
export const spelledLook = look => (typeof look === 'object' && look
  ? { mesh: look.mesh, ...(look.material ? { material: look.material } : {}), measure: look.measure } : look);
/** A made piece's blasts (B5) in its mesh's key and request (generated.py: ?blasts=), none when it has none. */
export const blastQuery = blasts => (blasts?.length ? { key: `|${JSON.stringify(blasts)}`, query: { blasts: JSON.stringify(blasts) } } : { key: '', query: {} });
// the mesh record of a made piece over its template's (the mesh form: name, sections by slot, bounds), and its
// materials: the template's by slot
function madeRecord(template, meshes, key, { noun, url, sections, bounds }) {
  if (!meshes[key]) {
    // (`look`: the template's mesh, which Select all of a kind counts it as)
    meshes[key] = { name: `${meshes[template.mesh]?.name ?? noun}, made from numbers`, kind: 'static', made: true,
      look: meshes[template.mesh]?.name ?? null, fallback: { mesh: template.mesh, materials: [...template.materials] },
      url, sections: Array.from({ length: sections }, (_, slot) => ({ slot, count: 1 })), bounds };
  }
  const slots = (meshes[template.mesh]?.sections ?? []).filter(s => s.count).map(s => s.slot);
  const bySlot = new Map(slots.map((slot, i) => [slot, template.materials[i]]));
  return { mesh: key, materials: Array.from({ length: sections }, (_, slot) => bySlot.get(slot) ?? template.materials[0]) };
}
/** A made wall's numbers in the one spelling its mesh's key and request use (generated.py wall_numbers: its look's own
 *  storeys left out), with its end styles where they are joined (`ends`, worked out from where it stands:
 *  made_handles.js refreshJoins; two free ends left out). */
export const madeWallNumbers = (w, ends = null) => ({ x0: w.x0, x1: w.x1, openings: (w.openings ?? []).map(o => ({ x0: o.x0, x1: o.x1, z0: o.z0, z1: o.z1 })),
                                seed: w.seed ?? 1, ...(w.storeys !== undefined && w.storeys !== wallSpec(w).storeys ? { storeys: w.storeys } : {}),
                                ...(w.look && w.look !== WALL_LOOKS[0].id ? { look: spelledLook(w.look) } : {}),
                                ...(ends && (ends[0] !== 'free' || ends[1] !== 'free') ? { ends: [...ends] } : {}) });
/** A made wall's mesh bounds (the mesh form's [centre, half sizes, radius]): its solid between its ends' insets
 *  (tools/bake/frac_wall.py RECIPE), its look's height and thickness. */
export function madeBounds(wall) {
  // (its look's heights, insets and thickness: the Bar's for a look id, wallSpec's for a donor look)
  const spec = wallSpec(wall), insets = endInsetsOf(wall), top = wallTop(wall), [e0, e1] = wall.ends ?? ['free', 'free'];
  const a = wall.x0 + insets[e0], b = wall.x1 - insets[e1], hx = (b - a) / 2, hz = (top - spec.bottom) / 2;
  return [(a + b) / 2, 0, spec.bottom + hz, hx, spec.half, hz, Math.hypot(hx, spec.half, hz)];
}
/** A fracturing wall made from numbers: drawn from /generated/fracwall.glb, its look's sections bound to its template's
 *  materials by slot (the made mesh's sections are slots 0 to 5 in order). { mesh, materials }, or {}. */
export function madeWallShape(template, w, blasts, meshes) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!w || !finite(w.x0) || !finite(w.x1) || w.x1 - w.x0 < FRAC_WALL.minLength || w.x1 - w.x0 > FRAC_WALL.maxLength
    || !Number.isInteger(w.seed ?? 1) || !(w.openings ?? []).every(o => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o?.[k]))
      && w.x0 <= o.x0 && o.x0 < o.x1 && o.x1 <= w.x1 && o.z0 < o.z1)
    || !(w.storeys === undefined || (Number.isInteger(w.storeys) && w.storeys >= 1 && w.storeys <= WALL.maxStoreys))
    || (w.look !== undefined && !WALL_LOOKS.some(l => l.id === w.look) && !catalogued('wall', w.look))) return {};
  const wall = madeWallNumbers(w), broken = blastQuery(blasts);
  return madeRecord(template, meshes, `made:fracwall:${JSON.stringify(wall)}${broken.key}`, { noun: 'a wall',
    url: `/generated/fracwall.glb?${new URLSearchParams({ wall: JSON.stringify(wall), ...broken.query })}`,
    sections: wallSpec(wall).sections, bounds: madeBounds(wall) });
}
// A made slab: drawn from /generated/fracslab.glb, its two sections (the top with the edges, the underside) bound to
// its template's materials by slot; its bounds its footprint between its look's heights.
const FRAC_SLAB = { slots: 2 };
export const madeSlabNumbers = s => ({ x0: s.x0, x1: s.x1, y0: s.y0, y1: s.y1, holes: (s.holes ?? []).map(h => ({ x0: h.x0, x1: h.x1, y0: h.y0, y1: h.y1 })),
                                       seed: s.seed ?? 1, ...(s.look && s.look !== SLAB_LOOKS[0].id ? { look: spelledLook(s.look) } : {}) });
export function slabBounds(s) {
  const look = slabLookOf(s), hx = (s.x1 - s.x0) / 2, hy = (s.y1 - s.y0) / 2, hz = (look.top - look.bottom) / 2;
  return [(s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2, (look.top + look.bottom) / 2, hx, hy, hz, Math.hypot(hx, hy, hz)];
}
/** A made slab's { mesh, materials }, or {}. */
export function madeSlabShape(template, s, blasts, meshes) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!s || !['x0', 'x1', 'y0', 'y1'].every(k => finite(s[k])) || !slabLookOf(s) || !Number.isInteger(s.seed ?? 1)
    || (s.holes ?? []).length > SLAB.maxHoles) return {};
  const numbers = madeSlabNumbers(s), broken = blastQuery(blasts);
  return madeRecord(template, meshes, `made:fracslab:${JSON.stringify(numbers)}${broken.key}`, { noun: 'a slab',
    url: `/generated/fracslab.glb?${new URLSearchParams({ slab: JSON.stringify(numbers), ...broken.query })}`,
    sections: slabLookOf(numbers).sections ?? FRAC_SLAB.slots, bounds: slabBounds(numbers) });
}
