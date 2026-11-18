// Made walls on the page (private/plans/todo/custom-geometry-implementation-plan.md, stage M1): what is pure about the
// wall tool. A made wall is an added copy of its look's donor (a fracturing wall of the game's) that carries
// `generated: { kind: 'fracWall', version: 1, wall }`, the wall's numbers in the donor mesh's frame
// (tools/bake/frac_wall.py): `x0` and `x1` its tile edges along the wall (the tool always writes x0 0 and puts the
// piece at the wall's start), `openings` [{ x0, x1, z0, z1 }] (rectangles through it; z 0 is the floor the wall
// stands on, its bottom WALL.bottom), `seed` (the break pattern), `storeys` (1, or left out for 2: stage M2). Its solid
// stops WALL.endInset short of each end.
// Locations are game units (x, y, z up), rotations rotator units (pitch, yaw, roll).
import { QUARTER, TILE } from './poserule.js';

// The looks a wall is drawn in: each a donor (one of the game's fracturing walls, placed in a map of the base game), the
// mesh its actor holds, and what it looks like in words. M1 has one, the Bar's inside wall (frac_wall.RECIPE).
export const WALL_LOOKS = [{ id: 'bar-inside', name: 'Bar inside wall', package: 'URB_Bar', actor: 'XComDecoFracLevelActor_17',
  mesh: 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', lwrOnly: false,
  words: 'one or two storeys: diamond tiles under dark panelling on one side, brick over panelling on the other, with a skirting and a cornice' }];
// The one look of M1, the Bar's inside wall (frac_wall.RECIPE): its heights over the floor (a two-storey wall's top and
// face), and the tool's limits.
export const WALL = { endInset: 8, bottom: -16, top: 384, faceTop: 372, storey: 192, half: 12, minTiles: 1, maxTiles: 16 };
// A wall's tops by its storeys (frac_wall.shaped: one storey stands to 192, as the game's one-storey inside walls do;
// its cornice is the top 12 and an opening's top stays 24 under the top, as on a tall wall)
export const STOREY_TOPS = { 1: 192, 2: 384 };
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

// ---- heights
/** A wall's storeys: 1 or 2 (left out, the donor's two). */
export const storeysOf = wall => (wall?.storeys === 1 ? 1 : 2);
/** The wall's top over the floor (its bottom WALL.bottom), its face's top, and the highest an opening's top goes. */
export const wallTop = wall => STOREY_TOPS[storeysOf(wall)];
export const faceTopOf = wall => wallTop(wall) - (WALL.top - WALL.faceTop);
export const topMostOf = wall => wallTop(wall) - (WALL.top - OPENING.topMost);
/** The wall at `storeys` (1 or 2; 2 leaves the number out). An opening the lower wall can't hold has its top brought
 *  down to the highest an opening goes; one left smaller than OPENING.height (a window in the upper storey) goes.
 *  Gives { wall, cut (openings brought down), removed (openings gone) }. */
export function withStoreys(wall, storeys) {
  const { storeys: _, ...rest } = wall;
  const out = storeys === 1 ? { ...rest, storeys: 1 } : rest;
  const top = topMostOf(out);
  let cut = 0, removed = 0;
  const openings = [];
  for (const o of wall.openings ?? []) {
    if (o.z1 <= top + 1e-6) { openings.push(o); continue; }
    if (top - Math.max(0, o.z0) < OPENING.height - 1e-6) { removed++; continue; }
    cut++;
    openings.push({ ...o, z1: top });
  }
  return { wall: { ...out, openings }, cut, removed };
}
/** The wall after its top handle moved `delta` units up: past half a storey down a two-storey wall becomes one storey,
 *  past half a storey up a one-storey wall two. Gives withStoreys' { wall, cut, removed }. */
export function raisedWall(wall, delta) {
  const now = storeysOf(wall), half = WALL.storey / 2;
  const next = now === 2 && delta < -half ? 1 : now === 1 && delta > half ? 2 : now;
  return next === now ? { wall, cut: 0, removed: 0 } : withStoreys(wall, next);
}

/** Whether `wall` is numbers this tool makes: tile edges 0 and a whole number of tiles (1 to WALL.maxTiles), one or two
 *  storeys, openings inside it and under its face's top and apart, a whole-number seed. */
export function toolWall(wall) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!wall || wall.x0 !== 0 || !finite(wall.x1) || !Number.isInteger(wall.seed ?? 1) || ![undefined, 1, 2].includes(wall.storeys)) return false;
  const tiles = wall.x1 / TILE;
  if (!Number.isInteger(tiles) || tiles < WALL.minTiles || tiles > WALL.maxTiles) return false;
  const list = sortedOpenings(wall.openings ?? []);
  return list.every((o, i) => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o[k])) && o.x0 >= 0 && o.x1 <= wall.x1 && o.x1 > o.x0
    && o.z1 > o.z0 && o.z0 >= WALL.bottom && o.z1 <= faceTopOf(wall) && (i === 0 || list[i - 1].x1 <= o.x0));
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
 *  steps of OPENING.fine. The opening stays inside the wall, off its neighbours, under topMostOf(wall), a window's sill
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
    o.z1 = tidy(Math.min(topMostOf(wall), Math.max(floor + OPENING.height, round(o.z1 + delta, OPENING.fine))));
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
  out.push(p.walk ? 'units walk through it' : p.climb ? 'units climb through it' : 'units can\'t walk through it');
  out.push(p.sight ? 'see and shoot through it' : 'don\'t see through it');
  const cover = { none: 'it gives no cover', low: 'the wall under it gives low cover', high: 'the wall under it gives high cover' }[p.cover];
  let words = `${out.join(', ')}; ${cover}.`;
  if (openingKind(o) === 'doorway' && p.walk && !door) words += ' A unit in a doorway with no door has cover toward its sides: put a door in it, as the game\'s doorways have.';
  return words[0].toUpperCase() + words.slice(1);
}
/** The wall's size in words: "4 tiles long, two storeys (400 tall)" or "..., one storey (208 tall)". */
// ---- joints (custom geometry plan, M3 item 2; compiler.py wall_joins is the twin)
// An end's style for its solid (frac_wall.END_INSETS: how far in from its tile edge it stops) and how it meets: the
// game's inside walls stop square 8 short of a wall they meet (a T's stem, as a free end); at an L one runs through to
// the other's far face and the other butts on its face; end to end both reach the line (research/evidence/wall-joints.py).
export const END_INSETS = { free: WALL.endInset, line: 0, through: -8 };
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
                z: [w.location[2] + WALL.bottom, w.location[2] + top], height: top, length: x1 - x0, loc: [w.location[0], w.location[1]] });
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
export const wallWords = wall => `${plural(tilesOf(wall), 'tile')} long, ${storeysOf(wall) === 1 ? 'one storey' : 'two storeys'} (${wallTop(wall) - WALL.bottom} tall)`;
