// Made walls on the page (private/plans/todo/custom-geometry-implementation-plan.md, stage M1): what is pure about the
// wall tool. A made wall is an added copy of its look's donor (a fracturing wall of the game's) that carries
// `generated: { kind: 'fracWall', version: 1, wall }`, the wall's numbers in the donor mesh's frame
// (tools/bake/frac_wall.py): `x0` and `x1` its tile edges along the wall (the tool always writes x0 0 and puts the
// piece at the wall's start), `openings` [{ x0, x1, z0, z1 }] (rectangles through it; z 0 is the floor the wall
// stands on, its bottom WALL.bottom), `seed` (the break pattern). Its solid stops WALL.endInset short of each end.
// Locations are game units (x, y, z up), rotations rotator units (pitch, yaw, roll).
import { QUARTER, TILE } from './poserule.js';

// The looks a wall is drawn in: each a donor (one of the game's fracturing walls, placed in a map of the base game), the
// mesh its actor holds, and what it looks like in words. M1 has one, the Bar's inside wall (frac_wall.RECIPE).
export const WALL_LOOKS = [{ id: 'bar-inside', name: 'Bar inside wall', package: 'URB_Bar', actor: 'XComDecoFracLevelActor_17',
  mesh: 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', lwrOnly: false,
  words: 'two storeys: diamond tiles under dark panelling on one side, brick over panelling on the other, with a skirting and a cornice' }];
// The one look of M1, the Bar's inside wall (frac_wall.RECIPE): its heights over the floor, and the tool's limits.
export const WALL = { endInset: 8, bottom: -16, top: 384, faceTop: 372, storey: 192, half: 12, minTiles: 1, maxTiles: 16 };
// An opening's limits: its top under the cornice, a window's sill over the floor, the smallest sizes, the fine step
// (D3: sides on tile edges, with Alt in steps of 8)
export const OPENING = { topMost: 360, sillLeast: 8, width: 16, height: 24, fine: 8 };
// The presets, as the game's are (the plan, M1: a doorway one tile wide and 176 tall with its sides on tile edges, 242
// openings in seven URB maps; the game's windows run 64 to 170 over the floor, one or two tiles wide
// (research/evidence/wall-openings.py). Ours starts at 72, so the walking sweep at 64 meets the wall under it as it
// meets the game's glass: units see through it, not climb through.
export const PRESETS = { doorway: { width: TILE, z0: WALL.bottom, z1: 160 }, window: { width: TILE, z0: 72, z1: 168 } };
// The game's sweeps over a tile's floor, along the line between two tiles' centres (research/native/cover-build.md,
// line-of-sight.md): cover 44 to 60, high or low cover 88 to 104, walking 64 (half a unit thick), sight from the eye
// tile, 96 over the floor's level.
export const SWEEP = { cover: [44, 60], high: [88, 104], walk: 64, sight: 96, half: 0.5 };

const round = (v, step) => step * Math.round(v / step);
const sign = v => (v < 0 ? -1 : 1);
const tidy = v => { const r = Math.round(v * 1e4) / 1e4; return r === 0 ? 0 : r; };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** Whether `wall` is numbers this tool makes: tile edges 0 and a whole number of tiles (1 to WALL.maxTiles), openings
 *  inside it and apart, a whole-number seed. */
export function toolWall(wall) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!wall || wall.x0 !== 0 || !finite(wall.x1) || !Number.isInteger(wall.seed ?? 1)) return false;
  const tiles = wall.x1 / TILE;
  if (!Number.isInteger(tiles) || tiles < WALL.minTiles || tiles > WALL.maxTiles) return false;
  const list = sortedOpenings(wall.openings ?? []);
  return list.every((o, i) => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o[k])) && o.x0 >= 0 && o.x1 <= wall.x1 && o.x1 > o.x0
    && o.z1 > o.z0 && o.z0 >= WALL.bottom && o.z1 <= WALL.faceTop && (i === 0 || list[i - 1].x1 <= o.x0));
}
export const sortedOpenings = list => [...list].sort((a, b) => a.x0 - b.x0 || a.z0 - b.z0);
/** A doorway reaches the wall's bottom; anything else is a window. */
export const openingKind = o => (o.z0 <= WALL.bottom + 1e-6 ? 'doorway' : 'window');
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
/** An opening's handles: its middle (slides it along the wall), its two sides, its top, and a window's sill. */
export const openingParts = o => (openingKind(o) === 'doorway' ? ['middle', 'x0', 'x1', 'z1'] : ['middle', 'x0', 'x1', 'z1', 'z0']);
/** The wall with one part of opening `index` moved `delta` units (along the wall for the middle and sides, up for the
 *  top and sill): sides and the middle in whole tiles, or with `fine` in steps of OPENING.fine; the top and sill in
 *  steps of OPENING.fine. The opening stays inside the wall, off its neighbours, under OPENING.topMost, a window's sill
 *  at OPENING.sillLeast or more, and at least OPENING.width wide and OPENING.height tall. Gives the wall. */
export function movedOpening(wall, index, part, delta, { fine = false } = {}) {
  const list = sortedOpenings(wall.openings ?? []), o = { ...list[index] };
  if (!o) return wall;
  const before = index > 0 ? list[index - 1].x1 : 0, after = index < list.length - 1 ? list[index + 1].x0 : wall.x1;
  const along = fine ? OPENING.fine : TILE, least = fine ? OPENING.width : TILE;
  const at = v => round(v, along);
  if (part === 'middle') {
    const width = o.x1 - o.x0;
    let x0 = o.x0 + round(delta, along);
    x0 = Math.max(before, Math.min(after - width, x0));
    o.x0 = tidy(x0); o.x1 = tidy(x0 + width);
  } else if (part === 'x0') {
    o.x0 = tidy(Math.max(before, Math.min(o.x1 - least, at(o.x0 + delta))));
  } else if (part === 'x1') {
    o.x1 = tidy(Math.min(after, Math.max(o.x0 + least, at(o.x1 + delta))));
  } else if (part === 'z1') {
    const floor = openingKind(o) === 'doorway' ? 0 : o.z0;
    o.z1 = tidy(Math.min(OPENING.topMost, Math.max(floor + OPENING.height, round(o.z1 + delta, OPENING.fine))));
  } else if (part === 'z0' && openingKind(o) === 'window') {
    o.z0 = tidy(Math.max(OPENING.sillLeast, Math.min(o.z1 - OPENING.height, round(o.z0 + delta, OPENING.fine))));
  }
  const openings = list.map((p, i) => (i === index ? o : p));
  return { ...wall, openings };
}

// ---- what an opening does in play
/** The centres along the wall (in its frame) of the tiles whose centre line passes through the opening. */
export const centresThrough = (wall, o) => [...Array(tilesOf(wall)).keys()].map(k => (k + 0.5) * TILE)
  .filter(c => c > o.x0 + 1 && c < o.x1 - 1);
/** What the game does at an opening, by its sweeps at the tile centres it spans: { tiles, walk, sight, cover
 *  ('none' | 'low' | 'high' | 'whole': the wall's own cover at those tiles) }. */
export function openingPlay(wall, o) {
  const tiles = centresThrough(wall, o).length;
  const spans = (a, b) => o.z0 < a && o.z1 > b;
  if (!tiles) return { tiles, walk: false, sight: false, cover: 'whole' };
  const coverHit = !spans(SWEEP.cover[0], SWEEP.cover[1]), highHit = !spans(SWEEP.high[0], SWEEP.high[1]);
  return { tiles, walk: spans(SWEEP.walk - SWEEP.half, SWEEP.walk + SWEEP.half),
           sight: spans(SWEEP.sight - SWEEP.half, SWEEP.sight + SWEEP.half),
           cover: !coverHit ? 'none' : highHit ? 'high' : 'low' };
}
const size = v => (v % TILE === 0 ? `${plural(v / TILE, 'tile')} wide` : `${Math.round(v)} wide`);
/** An opening in words, for the piece panel's list: "Doorway, 1 tile wide, 176 tall" or "Window, 1 tile wide, 96 tall,
 *  its sill 72 over the floor". */
export function openingWords(o) {
  const tall = Math.round(o.z1 - Math.max(0, o.z0));
  return openingKind(o) === 'doorway' ? `Doorway, ${size(o.x1 - o.x0)}, ${tall} tall`
    : `Window, ${size(o.x1 - o.x0)}, ${tall} tall, its sill ${Math.round(o.z0)} over the floor`;
}
/** What the game does there, in a sentence or two (`door`: a door stands in it). */
export function playWords(wall, o, { door = false } = {}) {
  const p = openingPlay(wall, o);
  if (!p.tiles) return 'No tile\'s centre line passes through it: units can\'t walk or see through it, and the wall gives cover there as if whole.';
  const out = [];
  out.push(p.walk ? 'units walk through it' : 'units can\'t walk through it');
  out.push(p.sight ? 'see and shoot through it' : 'don\'t see through it');
  const cover = { none: 'it gives no cover', low: 'the wall under it gives low cover', high: 'the wall under it gives high cover' }[p.cover];
  let words = `${out.join(', ')}; ${cover}.`;
  if (openingKind(o) === 'doorway' && p.walk && !door) words += ' A unit in a doorway with no door has cover toward its sides: put a door in it, as the game\'s doorways have.';
  return words[0].toUpperCase() + words.slice(1);
}
/** The wall's size in words: "4 tiles long, two storeys (400 tall)". */
export const wallWords = wall => `${plural(tilesOf(wall), 'tile')} long, two storeys (${WALL.top - WALL.bottom} tall)`;
