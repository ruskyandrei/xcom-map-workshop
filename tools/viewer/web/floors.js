// Floor pieces and floor levels: plain functions of the page's data, so the browser smoke test can call them
// directly. Game axes throughout (x and y across the floor, z up) and game units. Nothing here draws or edits.
//
// A floor piece is a piece that carries the map's saved floor tiles (the game's bake names the actor under each
// walkable tile), is flat (48 units or less), and is not a decoration lying on another floor piece: a rug or a plate,
// 8 units or less, its bottom within 12 units of a floor piece's top over its centre. Sidewalks (18 units, on the
// asphalt) are floors; rugs (5 units, on the bar's floor) are decorations, placed as any piece is.
//
// Placing a floor piece keeps the height it has in the map, moved by whole levels (64 units) to the saved floor under
// the cursor: a sidewalk dropped on the road or on another sidewalk stands as the map's sidewalks do, and a storey's
// floor dropped upstairs lands on that storey.

import { POSE_SLACK, turned } from './poserule.js';
import { LEVEL as STOREY, QUARTER } from './constants.js';
import { plural } from './dom_words.js';

const FLAT = 48;        // units: a floor piece is at most this tall
const THIN = 8;         // units: a decoration (rug, plate) is at most this thick
const RESTS = 12;       // units: a decoration's bottom lies this close to the floor piece under it

const median = values => { const s = [...values].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };

/** What a copy of a component is: class, archetype, mesh, materials, scale and tint. */
const partSignature = o => [o.actorClass, o.archetype ?? '', o.mesh, (o.materials ?? []).join(','),
                                   (o.scale ?? [1, 1, 1]).join(','), (o.tint ?? []).join(',')].join('|');
/** What a copy of an actor is: its components' signatures. Two actors with one signature are copies of one piece. */
export const stampSignature = parts => parts.map(partSignature).sort().join('\n');

/** An actor's meshes' box in the world, [x0, y0, z0, x1, y1, z1], from the meshes' bounds ([cx, cy, cz, ex, ey, ez,
 *  r] in their own frame), scaled and turned by the actor's yaw. */
export function worldBox(parts, meshes) {
  const box = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
  for (const o of parts) {
    const b = meshes[o.mesh]?.bounds;
    if (!b) continue;
    const [sx, sy, sz] = o.scale ?? [1, 1, 1], yaw = (o.rotation[1] / 65536) * 2 * Math.PI, c = Math.cos(yaw), s = Math.sin(yaw);
    for (const dx of [-b[3], b[3]]) for (const dy of [-b[4], b[4]]) for (const dz of [-b[5], b[5]]) {
      const x = (b[0] + dx) * sx, y = (b[1] + dy) * sy, z = (b[2] + dz) * sz;
      const p = [o.location[0] + c * x - s * y, o.location[1] + s * x + c * y, o.location[2] + z];
      for (let k = 0; k < 3; k++) { box[k] = Math.min(box[k], p[k]); box[k + 3] = Math.max(box[k + 3], p[k]); }
    }
  }
  return box;
}

/** Each actor's saved floor: { z, level, count }, the median height of the floor tiles it carries on its most common
 *  level. floorTiles: the export's [{tile: [x, y, level], location, actor}]. */
export function ownedFloors(floorTiles) {
  const byActor = new Map();
  for (const t of floorTiles ?? []) { if (!t.actor) continue; if (!byActor.has(t.actor)) byActor.set(t.actor, []); byActor.get(t.actor).push(t); }
  const out = new Map();
  for (const [actor, tiles] of byActor) {
    const levels = new Map();
    for (const t of tiles) levels.set(t.tile[2], (levels.get(t.tile[2]) ?? 0) + 1);
    const level = [...levels].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
    out.set(actor, { z: median(tiles.filter(t => t.tile[2] === level).map(t => t.location[2])), level, count: tiles.length });
  }
  return out;
}

/** Which of the actors carrying saved floor are floor pieces. carriers: [{ actor, box: worldBox }]. Returns a Map of
 *  actor to 'floor', 'decoration' (thin, lying on a floor piece) or 'other' (taller than FLAT: a wall, ramp or crate
 *  whose top is walked on). */
export function classifyFloors(carriers) {
  const flat = carriers.filter(c => c.box[5] - c.box[2] <= FLAT), out = new Map();
  for (const c of carriers) {
    const b = c.box, thick = b[5] - b[2];
    if (thick > FLAT) { out.set(c.actor, 'other'); continue; }
    const mx = (b[0] + b[3]) / 2, my = (b[1] + b[4]) / 2;
    const rests = thick <= THIN && flat.some(d => d !== c && d.box[0] <= mx && mx <= d.box[3] && d.box[1] <= my && my <= d.box[4]
                                                && Math.abs(d.box[5] - b[2]) <= RESTS);
    out.set(c.actor, rests ? 'decoration' : 'floor');
  }
  return out;
}

/** The floor pieces by stamp signature: Map signature -> { support (the saved floor's height over the pivot), actor
 *  (one carrying it), z (that one's pivot height in the map: its levels, Align to level's) }. actors: [{ actor, parts,
 *  location }] (the base map's, as exported); kinds: classifyFloors; floors: ownedFloors. Pieces of more than one
 *  component (a van, a car) are never floor pieces. */
export function floorStamps(actors, kinds, floors) {
  const out = new Map();
  for (const a of actors) {
    if (kinds.get(a.actor) !== 'floor' || a.parts.length !== 1) continue;
    const signature = stampSignature(a.parts);
    if (!out.has(signature)) out.set(signature, { support: floors.get(a.actor).z - a.location[2], actor: a.actor, z: a.location[2] });
  }
  return out;
}

// ---------------------------------------------------------------- the map's tiles and levels
/** A point's tile [x, y] on a grid { origin: [x, y, z], size: [96, 96, 64], dims } in game axes: for the game's tiles
 *  (the floor under a point), origin is the corner the game counts them from (map_grid.js tileCorner). */
export const tileOf = (grid, x, y) => [Math.floor((x - grid.origin[0]) / grid.size[0]), Math.floor((y - grid.origin[1]) / grid.size[1])];
/** The saved floor tiles by "x,y" key, each a list of the tile's floors (one per level). */
export function floorIndex(floorTiles) {
  const index = new Map();
  for (const f of floorTiles ?? []) {
    const k = `${f.tile[0]},${f.tile[1]}`;
    if (!index.has(k)) index.set(k, []);
    index.get(k).push(f);
  }
  return index;
}
/** The floor under a point: the saved floor of its tile that the point lies on (the highest at most 8 units over it
 *  and at most a level under it), else the point's own height. { z, floor (the saved floor tile or null) }. */
export function floorUnder(index, grid, point) {
  const tile = tileOf(grid, point[0], point[1]);
  let best = null;
  for (const f of index.get(`${tile[0]},${tile[1]}`) ?? []) {
    const z = f.location[2];
    if (z <= point[2] + 8 && z >= point[2] - STOREY && (!best || z > best.location[2])) best = f;
  }
  return best ? { z: best.location[2], floor: best } : { z: point[2], floor: null };
}
/** The pivot height for a floor piece placed on floor z: its own pivot height (pivotZ, its saved floor `support`
 *  over it), moved by whole levels to the level of z. */
export const levelHeight = (pivotZ, support, z) => pivotZ + Math.round((z - pivotZ - support) / STOREY) * STOREY;
/** A floor piece's height on its levels (Align to level, align.js): the height `z` its pivot stands at taken to the
 *  nearest of its height in its map (`mapZ`) moved by whole levels. */
export const nearestLevel = (z, mapZ) => mapZ + Math.round((z - mapZ) / STOREY) * STOREY + 0;

// ---------------------------------------------------------------- building floors' heights (the Floor picker)
const inPlan = (v, x, y) => v.min[0] <= x && x <= v.max[0] && v.min[1] <= y && y <= v.max[1];
/** A building floor's walking height: the median of the saved floor tiles inside its volumes near its bottom (at most
 *  8 units under it, less than a level over it), else its bottom; null for a floor without volumes. Floors differ per
 *  building: Bar's main building has its floor 2 at 210, the Police Station's at 274. floor: the export's
 *  { bottom, boxes: [{min, max}] }. */
export function storeyHeight(floor, floorTiles) {
  const boxes = floor?.boxes ?? [];
  if (!boxes.length) return null;
  const bottom = floor.bottom ?? Math.min(...boxes.map(v => v.min[2]));
  const near = (floorTiles ?? []).filter(t => { const [x, y, z] = t.location;
    return z >= bottom - 8 && z < bottom + STOREY && boxes.some(v => inPlan(v, x, y) && v.min[2] - 8 <= z && z <= v.max[2]); });
  return near.length ? median(near.map(t => t.location[2])) : bottom;
}
/** The building whose floor k (0 the ground floor) stands over the point (x, y) in plan, else the nearest one that has
 *  a floor k with volumes: its index, or -1 when none has. buildings: the export's. */
export function buildingWithFloor(buildings, k, x, y) {
  let best = -1, nearest = Infinity;
  (buildings ?? []).forEach((b, i) => {
    for (const v of b.floors?.[k]?.boxes ?? []) {
      const dx = Math.max(v.min[0] - x, 0, x - v.max[0]), dy = Math.max(v.min[1] - y, 0, y - v.max[1]), d = Math.hypot(dx, dy);
      if (d < nearest) { nearest = d; best = i; }
    }
  });
  return best;
}

// ---------------------------------------------------------------- building floors (the cutaway)
/** The building floor whose volumes overlap a world box [x0, x1, y0, y1, z0, z1] most: { building (index), floor }
 *  or null, as the Build's native_copy.floor_at finds it (first wins a tie). buildings: the export's. */
export function floorAt(buildings, box) {
  let best = null, most = 0;
  (buildings ?? []).forEach((b, i) => (b.floors ?? []).forEach((floor, k) => {
    let got = 0;
    for (const v of floor.boxes ?? []) {
      let inter = 1;
      for (let j = 0; j < 3; j++) inter *= Math.max(0, Math.min(box[2 * j + 1], v.max[j]) - Math.max(box[2 * j], v.min[j]));
      got += inter;
    }
    if (got > most) { best = { building: i, floor: k }; most = got; }
  }));
  return best;
}
/** A CutdownFloor moved by `floors` floors, as the Build moves it (0 names none and stays). */
const movedCutdown = (cut, floors) => (cut ? Math.max(1, Math.min(255, cut + floors)) : 0);
/** A copy's building-floor listings (the Build's rule, native_copy.copy_floors, with the shared cases in
 *  tools/bake/tests/floor_membership_cases.json): listings, the original's [{building, floor, cutdownFloor}]
 *  (building: an index); here and there, floorAt of the original's and the copy's boxes; floorCount(building). A piece
 *  listed nowhere stays so; one standing in no floor volume, copied to none either, keeps its listings; a copy
 *  standing in no floor gets none; else each listing moves to the floor the copy stands in, as far above it as the
 *  original's is above the floor the original stands in. */
export function copyFloors(listings, here, there, floorCount) {
  if (!listings.length) return [];
  if (!there && !here) return listings.map(l => ({ ...l }));
  if (!there) return [];
  return listings.map(l => {
    const rise = here && here.building === l.building ? l.floor - here.floor : 0;
    const floor = Math.max(0, Math.min(floorCount(there.building) - 1, there.floor + rise));
    return { building: there.building, floor, cutdownFloor: movedCutdown(l.cutdownFloor, floor - l.floor) };
  });
}

// ---------------------------------------------------------------- buildings made from nothing (prefab plan 5.1, 5.3)
/** The classes a building floor lists (the Build's buildings.LISTED; pinned in tests/twin_constants.json, review
 *  finding 55): a StaticMeshActor never hides. */
export const LISTED_CLASSES = new Set(['XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComFracLevelActor',
                                       'XComDecoFracLevelActor', 'XComInteractiveLevelActor', 'XComLadder', 'XComCollectible', 'KAsset']);
// The game editor's own rule for which floors of a building list a piece (findings register F-87), as the Build
// applies it to a project's buildings (tools/bake/buildings.py, audit_buildings.touched and listing).
// The cursor's floors (the map's cursor volumes, export 20): which floor a height is to the cursor, and so where the
// mouse wheel stops. A building's storeys should start where they do (floor_edits.py cursor_storeys is the twin).
export const CURSOR_NEAR = 32, CURSOR_STOREY = 192, CURSOR_STOREYS = 4;

/** The cursor's floors of an exported map: [{ floor, box: [x0, y0, z0, x1, y1, z1], made }], or null when the export
 *  predates them. A map with no cursor volumes, or a `cleared` one, gets the ones the Build gives it (shell.py): even
 *  storeys of CURSOR_STOREY from the tile grid's bottom over the whole map (CURSOR_STOREYS, more on a taller grid),
 *  the last one up to the grid's top (`made`). A map as it is on a grid larger than its own size `own` has its own as
 *  shell.py grow_cursors leaves them: those reaching the old far X or Y side stretched to the new one, and with more
 *  levels even storeys over the whole grid from the top of its own to the new top. Stair volumes are left out.
 *  The made floors and roofs `slabs` ([{ box: [x0, y0, z0, x1, y1, z1] }]) bring floors of their own over their
 *  footprints, and the buildings whose floors are the cursor's `areas` ([{ label, floors: [[box, ...]] }],
 *  cursorAreas) theirs (madeStoreys). floor_edits.py cursor_storeys is the twin. */
export function cursorStoreys(data, { cleared = false, own: ownDims = null, slabs = null, areas = null } = {}) {
  if (!(data?.exporterVersion >= 20)) return null;
  const grid = data.tileGrid;
  const size = grid?.size ?? [96, 96, 64];
  const gridBox = grid?.origin && grid.dimensions ? [0, 1, 2].map(k => grid.origin[k]).concat([0, 1, 2].map(k => grid.origin[k] + grid.dimensions[k] * size[k])) : null;
  const st = cursorStoreysOf(data, cleared, ownDims);
  return (slabs?.length || areas?.length) && st ? madeStoreys(st, slabs ?? [], gridBox, areas ?? []) : st;
}
function cursorStoreysOf(data, cleared, ownDims) {
  const own = (data.cursorVolumes ?? []).filter(v => v.box && !v.stair).map(v => ({ floor: v.floor, box: [...v.box.min, ...v.box.max], made: false }));
  const grid = data.tileGrid;
  if (!grid?.origin) return own;
  const size = grid.size ?? [96, 96, 64];
  if ((own.length || (data.cursorVolumes ?? []).length) && !cleared) {
    // a map as it is on a larger grid (shell.py grow_cursors): `ownDims` is the map's own size, data.tileGrid the
    // project's (map_grid.js showGrid draws it there)
    if (!ownDims || ownDims.every((v, k) => v === grid.dimensions[k])) return own;
    const old = [0, 1, 2].map(k => grid.origin[k] + ownDims[k] * size[k]);
    const now = [0, 1, 2].map(k => grid.origin[k] + grid.dimensions[k] * size[k]);
    const out = own.map(s => {
      const box = [...s.box];
      for (const k of [0, 1]) if (box[k + 3] >= old[k] - 1 && now[k] > box[k + 3]) box[k + 3] = now[k];
      return { ...s, box };
    });
    if (own.length && now[2] > old[2] + 1e-3) {
      const top = Math.max(...own.map(s => s.box[5])), highest = Math.max(...own.map(s => s.floor ?? 0));
      if (now[2] > top + CURSOR_NEAR) {
        const count = Math.max(1, Math.round((now[2] - top) / CURSOR_STOREY));
        for (let n = 0; n < count; n++) {
          const z0 = top + CURSOR_STOREY * n, z1 = n === count - 1 ? now[2] : z0 + CURSOR_STOREY;
          out.push({ floor: highest + 1 + n, box: [grid.origin[0], grid.origin[1], z0, now[0], now[1], z1], made: true });
        }
      }
    }
    return out;
  }
  // none of its own, or cleared: even storeys from the bottom, a storey more for each 192 units of a taller grid
  const bottom = grid.origin[2], top = bottom + grid.dimensions[2] * size[2], out = [];
  const count = Math.max(CURSOR_STOREYS, Math.round((top - bottom) / CURSOR_STOREY));
  for (let n = 0; n < count; n++) {
    const z0 = bottom + CURSOR_STOREY * n, z1 = n === count - 1 ? Math.max(top, z0 + CURSOR_STOREY) : z0 + CURSOR_STOREY;
    out.push({ floor: n + 1, box: [-1e9, -1e9, z0, 1e9, 1e9, z1], made: true });
  }
  return out;
}

// The made floors' and roofs' own cursor floors (custom geometry plan M5b, F-128): tools/bake/made_cursors.py is the
// rule and the Build's writer, this its twin (tools/bake/tests/test_made_cursors.py checks the two agree).
const MADE_HALF = 96, MADE_EDGE = 1, MADE_TOP_SLACK = 2, MADE_UNDER = 2;
// where a made slab's floor starts: MADE_UNDER under its underside (made_cursors.slab_break)
const slabBreak = box => box[2] - MADE_UNDER;
const madeOverlap = (a, b) => Math.min(a[3], b[3]) - Math.max(a[0], b[0]) > MADE_EDGE && Math.min(a[4], b[4]) - Math.max(a[1], b[1]) > MADE_EDGE;
const madeCovers = (b, x, y) => b[0] <= x && x <= b[3] && b[1] <= y && y <= b[4];
const round3 = v => Math.round(v * 1000) / 1000;
const sortedUnique = values => [...new Set(values)].sort((a, b) => a - b);

/** Cells [xs[i], xs[i + 1]] x [ys[j], ys[j + 1]] merged into rectangles of one value (`value(i, j)`: a string or
 *  number, or null for a cell left out): runs along X in each row, carried up Y while the run and value hold.
 *  [[value, [x0, y0, x1, y1]]] (made_cursors.rectangles). */
function madeRectangles(xs, ys, value) {
  const out = [], nx = xs.length - 1, ny = ys.length - 1;
  let open = new Map();
  for (let j = 0; j <= ny; j++) {
    const runs = [];
    for (let i = 0; j < ny && i < nx; i++) {
      const v = value(i, j);
      if (v == null) continue;
      const start = i;
      while (i + 1 < nx && value(i + 1, j) === v) i++;
      runs.push([start, i + 1, v]);
    }
    const now = new Map();
    for (const [a, b, v] of runs) {
      const key = `${a}|${b}|${v}`;
      now.set(key, { a, b, v, start: open.has(key) ? open.get(key).start : j });
      open.delete(key);
    }
    for (const r of open.values()) out.push([r.v, [xs[r.a], ys[r.start], xs[r.b], ys[j]]]);
    open = now;
  }
  return out;
}
function madeColumn(cx, cy, plain, slabs, grid) {
  const over = plain.filter(v => madeCovers(v.box, cx, cy));
  let bottom, top, marks;
  if (over.length) {
    bottom = Math.min(...over.map(v => v.box[2]));
    top = Math.max(...over.map(v => v.box[5]));
    marks = [];
    const order = [...over].sort((a, b) => a.box[2] - b.box[2] || (b.floor || 0) - (a.floor || 0) || (String(a.key) < String(b.key) ? -1 : String(a.key) > String(b.key) ? 1 : 0));
    for (const v of order) if (!marks.some(m => Math.abs(v.box[2] - m.z) <= MADE_EDGE)) marks.push({ z: v.box[2], floor: v.floor || 0, source: v.key, taken: false });
  } else if (grid) {
    [bottom, top] = [grid[2], grid[5]];
    marks = [{ z: bottom, floor: 1, source: null, taken: false }];
  } else return null;
  for (const t of sortedUnique(slabs.filter(s => madeCovers(s.box, cx, cy)).map(s => slabBreak(s.box)))) {
    if (t <= bottom + MADE_HALF || t >= top - MADE_TOP_SLACK) continue;
    const near = marks.slice(1).filter(m => !m.taken && Math.abs(m.z - t) <= MADE_HALF);
    if (near.length) {
      const m = near.reduce((a, b) => (Math.abs(b.z - t) < Math.abs(a.z - t) || (Math.abs(b.z - t) === Math.abs(a.z - t) && b.z < a.z) ? b : a));
      m.z = t; m.taken = true;
    } else {
      const below = marks.filter(m => m.z < t).reduce((a, b) => (b.z > a.z ? b : a));
      marks.push({ z: t, floor: null, source: below.source, taken: true });
    }
    marks.sort((a, b) => a.z - b.z);
  }
  let floor = null;
  for (const m of marks) {
    if (m.floor == null || (floor != null && m.floor <= floor)) m.floor = (floor ?? 0) + 1;
    floor = m.floor;
  }
  const ends = [...marks.slice(1).map(m => m.z), top];
  return { bands: marks.map((m, k) => [round3(m.z), round3(ends[k]), m.floor]), sources: marks.map(m => m.source) };
}
// A building whose floors are the cursor's (the building cursor floors plan; made_cursors.building_breaks,
// area_boxes and unordered are the twins): its floor boxes are a footprint, over which the cursor's floors are its
// own, each starting MADE_UNDER under its box's bottom.
const areaBoxes = area => area.floors.flat().filter(b => b[3] - b[0] > MADE_EDGE && b[4] - b[1] > MADE_EDGE);
/** The cursor's floors a building area gives the cell at (cx, cy): { bands: [[z0, z1, floor]] from the lowest up, or
 *  null where no floor box of it is over the cell, dropped: [the floors left out for starting at or under the one
 *  before] } (made_cursors.building_breaks). */
export function buildingBreaks(area, cx, cy) {
  const marks = [], dropped = [];
  area.floors.forEach((boxes, k) => {
    const over = boxes.filter(b => b[3] - b[0] > MADE_EDGE && b[4] - b[1] > MADE_EDGE && madeCovers(b, cx, cy));
    if (!over.length) return;
    const z0 = Math.min(...over.map(b => b[2])) - MADE_UNDER, top = Math.max(...over.map(b => b[5]));
    if (marks.length && z0 <= marks.at(-1)[0] + MADE_EDGE) { dropped.push(k + 1); return; }
    marks.push([z0, top, k + 1]);
  });
  if (!marks.length) return { bands: null, dropped };
  return { bands: marks.map(([z0, top, floor], n) => [round3(z0), round3(n + 1 < marks.length ? marks[n + 1][0] : top), floor]), dropped };
}
/** The floors of a building area that start at or under the floor before them over some part of its footprint, and
 *  so are left out of the cursor's floors there: sorted floor numbers from 1 (made_cursors.unordered). */
export function buildingUnordered(area) {
  const boxes = areaBoxes(area), out = new Set();
  const xs = sortedUnique(boxes.flatMap(b => [b[0], b[3]])), ys = sortedUnique(boxes.flatMap(b => [b[1], b[4]]));
  for (let i = 0; i + 1 < xs.length; i++) for (let j = 0; j + 1 < ys.length; j++) {
    for (const f of buildingBreaks(area, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2).dropped) out.add(f);
  }
  return [...out].sort((a, b) => a - b);
}
/** The buildings whose floors are the cursor's, as madeStoreys takes them: the project's buildings made from nothing
 *  with `cursorFloors` ([{ id, name, floors: [{ boxes }] }]), in order (the compiler's floor_edits.cursor_areas). */
export function cursorAreas(buildings) {
  return (buildings ?? []).filter(b => b && b.cursorFloors === true && !b.replaces && !b.deleted && Array.isArray(b.floors))
    .map(b => ({ label: b.name || b.id, id: b.id, floors: b.floors.map(f => (f.boxes ?? []).map(x => x.map(Number))) }));
}
const areaSource = (plain, cx, cy) => {
  const over = plain.filter(v => madeCovers(v.box, cx, cy));
  if (!over.length) return null;
  return over.reduce((a, b) => ((b.floor || 0) < (a.floor || 0) || ((b.floor || 0) === (a.floor || 0) && String(b.key) < String(a.key)) ? b : a)).key;
};
function madeMoves(slab, plain, grid) {
  const b = slab.box, cx = (b[0] + b[3]) / 2, cy = (b[1] + b[4]) / 2, t = slabBreak(b);
  const over = plain.filter(v => madeCovers(v.box, cx, cy));
  let bottom, top, breaks;
  if (over.length) {
    bottom = Math.min(...over.map(v => v.box[2])); top = Math.max(...over.map(v => v.box[5]));
    breaks = over.map(v => v.box[2]).filter(z => z > bottom + MADE_EDGE);
  } else if (grid) [bottom, top, breaks] = [grid[2], grid[5], []];
  else return false;
  return bottom + MADE_HALF < t && t < top - MADE_TOP_SLACK && !breaks.some(z => Math.abs(z - t) <= MADE_EDGE);
}
/** made_cursors.split: { hidden: [keys], volumes: [{ source, floor, box, over, building? }], crossed: [{ slab or
 *  building, volume, why }] } for the cursor volumes [{ key, floor, box, stair, turned }], the made slabs
 *  [{ box, label }] and the building areas [{ label, floors }]. */
function madeSplit(volumes, slabs, grid = null, areas = []) {
  slabs = (slabs ?? []).filter(s => s.box[3] - s.box[0] > MADE_EDGE && s.box[4] - s.box[1] > MADE_EDGE);
  areas = (areas ?? []).filter(a => areaBoxes(a).length);
  const out = { hidden: [], volumes: [], crossed: [] };
  const plain = volumes.filter(v => !v.stair && !v.turned);
  const moving = slabs.filter(s => madeMoves(s, plain, grid));
  if (!moving.length && !areas.length) return out;
  for (const v of volumes) if (v.stair || v.turned) {
    const why = v.stair ? 'stair' : 'turned';
    for (const s of moving) if (madeOverlap(v.box, s.box)) out.crossed.push({ slab: s.label, volume: v.key, why });
    for (const a of areas) if (areaBoxes(a).some(b => madeOverlap(v.box, b))) out.crossed.push({ building: a.label, volume: v.key, why });
  }
  const feet = [...moving.map(s => s.box), ...areas.flatMap(areaBoxes)];
  const hit = plain.filter(v => feet.some(f => madeOverlap(v.box, f)));
  const inside = (x, y) => feet.some(f => f[0] < x && x < f[3] && f[1] < y && y < f[4]);
  for (const v of hit) {
    const b = v.box;
    const xs = sortedUnique([b[0], b[3], ...feet.flatMap(f => [f[0], f[3]]).filter(e => b[0] < e && e < b[3])]);
    const ys = sortedUnique([b[1], b[4], ...feet.flatMap(f => [f[1], f[4]]).filter(e => b[1] < e && e < b[4])]);
    for (const [, r] of madeRectangles(xs, ys, (i, j) => (inside((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) ? null : 1))) {
      out.volumes.push({ source: v.key, floor: v.floor, box: [r[0], r[1], b[2], r[2], r[3], b[5]], over: false });
    }
  }
  const lo = [0, 1].map(k => Math.min(...feet.map(f => f[k]))), hi = [0, 1].map(k => Math.max(...feet.map(f => f[k + 3])));
  const xs = sortedUnique([...feet.flatMap(f => [f[0], f[3]]), ...hit.flatMap(v => [v.box[0], v.box[3]]).filter(e => lo[0] < e && e < hi[0])]);
  const ys = sortedUnique([...feet.flatMap(f => [f[1], f[4]]), ...hit.flatMap(v => [v.box[1], v.box[4]]).filter(e => lo[1] < e && e < hi[1])]);
  const columns = new Map();
  // a building's cells: `${i}|${j}` -> Set of band keys, laid floor by floor below
  const owned = new Map(), bandOf = new Map();
  const cell = (i, j) => {
    const cx = (xs[i] + xs[i + 1]) / 2, cy = (ys[j] + ys[j + 1]) / 2;
    if (!inside(cx, cy)) return null;
    // a building's floors first (the first area over the cell), else the made slabs' over the map's
    for (let n = 0; n < areas.length; n++) {
      const { bands } = buildingBreaks(areas[n], cx, cy);
      if (!bands) continue;
      const source = areaSource(plain, cx, cy), keys = new Set();
      for (const band of bands) {
        const key = JSON.stringify([n, band, source]);
        bandOf.set(key, { n, band, source });
        keys.add(key);
      }
      owned.set(`${i}|${j}`, keys);
      return null;
    }
    const c = madeColumn(cx, cy, plain, slabs, grid);
    if (!c) return null;
    const key = JSON.stringify(c.bands);
    if (!columns.has(key)) columns.set(key, c);
    return key;
  };
  for (const [key, r] of madeRectangles(xs, ys, cell)) {
    const c = columns.get(key);
    c.bands.forEach(([z0, z1, floor], k) => out.volumes.push({ source: c.sources[k], floor, box: [r[0], r[1], z0, r[2], r[3], z1], over: true }));
  }
  // each floor of a building as few boxes as its cells make (made_cursors.split)
  const order = [...bandOf.entries()].sort(([, a], [, b]) => a.n - b.n || a.band[2] - b.band[2] || a.band[0] - b.band[0] || a.band[1] - b.band[1]
                                           || (String(a.source) < String(b.source) ? -1 : String(a.source) > String(b.source) ? 1 : 0));
  for (const [key, { n, band: [z0, z1, floor], source }] of order) {
    for (const [, r] of madeRectangles(xs, ys, (i, j) => (owned.get(`${i}|${j}`)?.has(key) ? 1 : null))) {
      out.volumes.push({ source, floor, box: [r[0], r[1], z0, r[2], r[3], z1], over: true, building: areas[n].label });
    }
  }
  out.hidden = hit.map(v => v.key);
  return out;
}
/** The cursor's floors `storeys` ([{ floor, box, made }], cursorStoreys) with the made slabs' own over their
 *  footprints and the building areas' over theirs (made_cursors.storeys). A floor over a made slab's footprint has
 *  `slab: true`; one of a building's floors, `building`: its label. */
export function madeStoreys(storeys, slabs, grid = null, areas = []) {
  const volumes = storeys.map((s, k) => ({ key: k, floor: s.floor, box: s.box }));
  const s = madeSplit(volumes, slabs, grid, areas);
  if (!s.hidden.length && !s.volumes.length) return storeys;
  const gone = new Set(s.hidden);
  return [...storeys.filter((_, k) => !gone.has(k)),
          ...s.volumes.map(v => ({ floor: v.floor, box: v.box, made: v.source == null || storeys[v.source].made,
                                   ...(v.building !== undefined ? { building: v.building } : v.over ? { slab: true } : {}) }))];
}

// A made slab against the game's tiles (F-147; EXP-90 checks 2 and 5): made_cursors.py's outline, tiles and steps are
// the twins, with the cases both sides read (tools/bake/tests/slab_tiles_cases.json).
const SLAB_TILE = 96;
// a made slab reaching into a tile by no more than this covers none of it (the editor's tile lines, where a slab drawn
// with the snap on stands, are a unit inside the game's: tileGrid.origin against tileGrid.tiles)
const SLAB_TILE_EDGE = 2;
const halfUp3 = v => { const r = Math.floor(v * 1000 + 0.5) / 1000; return r === 0 ? 0 : r; };
/** Whether a made slab's rotator turns it off the quarter turns about the vertical alone. */
export function slabTurned(rotation) {
  const [pitch, yaw, roll] = rotation.map(v => Math.round(v));
  return yaw % 16384 !== 0 && pitch % 65536 === 0 && roll % 65536 === 0;
}
/** A made slab's footprint, or a hole of it, in the world: the four corners [[x, y]] round the rectangle `n` (x0, x1,
 *  y0, y1 in the piece's frame), the frame turned by the rotator's yaw as the package holds it (a whole number). */
export function slabOutline(location, rotation, n) {
  const yaw = Math.round(rotation[1]) * 2 * Math.PI / 65536, c = Math.cos(yaw), s = Math.sin(yaw);
  return [[n.x0, n.y0], [n.x1, n.y0], [n.x1, n.y1], [n.x0, n.y1]].map(([x, y]) => [location[0] + c * x - s * y, location[1] + s * x + c * y]);
}
function insideConvex(poly, p) {
  let sign = 0;
  for (let k = 0; k < poly.length; k++) {
    const [ax, ay] = poly[k], [bx, by] = poly[(k + 1) % poly.length];
    const cross = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax);
    if (Math.abs(cross) <= 1e-9) continue;
    if (sign === 0) sign = cross > 0 ? 1 : -1;
    else if ((cross > 0) !== (sign > 0)) return false;
  }
  return true;
}
function clipConvex(poly, x0, y0, x1, y1) {
  let pts = [...poly];
  for (const [k, v, keep] of [[0, x0, 1], [0, x1, -1], [1, y0, 1], [1, y1, -1]]) {
    const out = [];
    pts.forEach((b, i) => {
      const a = pts[(i + pts.length - 1) % pts.length], ina = (a[k] - v) * keep >= 0, inb = (b[k] - v) * keep >= 0;
      if (ina !== inb) {
        const t = (v - a[k]) / (b[k] - a[k]), cut = a[1 - k] + (b[1 - k] - a[1 - k]) * t;
        out.push(k === 0 ? [v, cut] : [cut, v]);
      }
      if (inb) out.push(b);
    });
    pts = out;
    if (!pts.length) break;
  }
  return pts;
}
function polygonArea(pts) {
  if (pts.length < 3) return 0;
  let sum = 0;
  pts.forEach((p, i) => { const a = pts[(i + pts.length - 1) % pts.length]; sum += a[0] * p[1] - p[0] * a[1]; });
  return Math.abs(sum) / 2;
}
function tileSpan(points, corner, k) {
  const lo = Math.floor((Math.min(...points.map(p => p[k])) - corner[k]) / SLAB_TILE), hi = Math.floor((Math.max(...points.map(p => p[k])) - corner[k]) / SLAB_TILE);
  return Array.from({ length: hi - lo + 1 }, (_, n) => lo + n);
}
/** Which tiles of the game's grid a made floor or roof is floor on, by the game's rule (one line down through each
 *  tile's centre: a slab is a tile's floor only where it covers the centre, out of its holes). `solids` [{ outline,
 *  holes }] (slabOutline's corners, each hole's too), `corner` where the game counts its tiles from (map_grid.js
 *  tileCorner). Gives { floor: [[i, j]], part: [[i, j, share]] (the tiles it reaches into by more than SLAB_TILE_EDGE
 *  short of their centre, share: how much of the tile its footprint covers, to a thousandth) }, by tile. */
export function slabFloorTiles(solids, corner) {
  const pts = solids.flatMap(s => s.outline), floor = [], part = [];
  if (!pts.length) return { floor, part };
  for (const i of tileSpan(pts, corner, 0)) for (const j of tileSpan(pts, corner, 1)) {
    const x0 = corner[0] + SLAB_TILE * i, y0 = corner[1] + SLAB_TILE * j, centre = [x0 + SLAB_TILE / 2, y0 + SLAB_TILE / 2];
    const on = solids.filter(s => insideConvex(s.outline, centre));
    if (on.some(s => !(s.holes ?? []).some(h => insideConvex(h, centre)))) floor.push([i, j]);
    else if (!on.length && solids.some(s => polygonArea(clipConvex(s.outline, x0 + SLAB_TILE_EDGE, y0 + SLAB_TILE_EDGE, x0 + SLAB_TILE - SLAB_TILE_EDGE,
                                                                     y0 + SLAB_TILE - SLAB_TILE_EDGE)) > 1e-9)) {
      let share = 0;
      for (const s of solids) share += polygonArea(clipConvex(s.outline, x0, y0, x0 + SLAB_TILE, y0 + SLAB_TILE));
      part.push([i, j, halfUp3(share / (SLAB_TILE * SLAB_TILE))]);
    }
  }
  return { floor, part };
}
/** A made floor's tiles (slabFloorTiles' answer) in words, for its section's line and its notes: null when it covers no
 *  tile in part. */
export function slabTileWords(t) {
  if (!t?.part.length) return null;
  const n = t.floor.length, m = t.part.length;
  return { short: `floor on ${n} of ${n + m} tiles`,
           long: `It is floor on ${plural(n, 'tile')}: a tile is floor where it covers the tile's centre, as the game looks for a `
             + `tile's floor there, so the ${plural(m, 'tile')} at its edge it covers in part ${m === 1 ? 'is' : 'are'} no floor at its height.` };
}
/** A made slab turned off the quarter turns as boxes square to the world over its footprint, the slabs madeStoreys
 *  takes: for each tile of the game's grid its footprint reaches into by more than SLAB_TILE_EDGE, the box round its
 *  part of that tile [x0, y0, z0, x1, y1, z1], to a thousandth, by tile (holes not taken out, as an unturned slab's box
 *  keeps them). */
export function slabSteps(solids, z0, z1, corner) {
  const pts = solids.flatMap(s => s.outline), out = [], e = SLAB_TILE_EDGE;
  if (!pts.length) return out;
  for (const i of tileSpan(pts, corner, 0)) for (const j of tileSpan(pts, corner, 1)) {
    const x0 = corner[0] + SLAB_TILE * i, y0 = corner[1] + SLAB_TILE * j;
    const q = solids.filter(s => polygonArea(clipConvex(s.outline, x0 + e, y0 + e, x0 + SLAB_TILE - e, y0 + SLAB_TILE - e)) > 1e-9)
      .map(s => clipConvex(s.outline, x0, y0, x0 + SLAB_TILE, y0 + SLAB_TILE)).flat();
    if (q.length) out.push([halfUp3(Math.min(...q.map(p => p[0]))), halfUp3(Math.min(...q.map(p => p[1]))), z0,
                            halfUp3(Math.max(...q.map(p => p[0]))), halfUp3(Math.max(...q.map(p => p[1]))), z1]);
  }
  return out;
}

/** Where the cursor's floors start over a box's footprint: [{ z, top, floor }] from the lowest up, one for each
 *  height. */
export function storeysOver(storeys, box) {
  const out = new Map();
  for (const s of storeys ?? []) {
    if (Math.min(s.box[3], box[3]) - Math.max(s.box[0], box[0]) <= 0 || Math.min(s.box[4], box[4]) - Math.max(s.box[1], box[1]) <= 0) continue;
    const key = Math.round(s.box[2]);
    if (!out.has(key)) out.set(key, { z: s.box[2], top: s.box[5], floor: s.floor });
  }
  return [...out.values()].sort((a, b) => a.z - b.z);
}

/** Whether a box starts at none of the cursor's floors over it (within CURSOR_NEAR). */
export const cursorMiss = (box, over) => over.length > 0 && !over.some(s => Math.abs(box[2] - s.z) <= CURSOR_NEAR);

const LIST_MARGIN = 20;   // a piece is a floor's when its bottom is more than this under the volume's top
const LIST_SLACK = 2;     // how near a floor's box a piece's box counts as touching it
export const STOREY_HEIGHT = 192;
/** The floors (indices) a piece's world box [x0, x1, y0, y1, z0, z1] counts for. floors: [{ boxes: [{min, max}] }]. */
export function touchedFloors(box, floors, margin = LIST_MARGIN, slack = LIST_SLACK) {
  const out = [];
  (floors ?? []).forEach((floor, k) => {
    for (const v of floor.boxes ?? []) {
      if (box[4] < v.max[2] - margin && [0, 1, 2].every(j => box[2 * j] <= v.max[j] + slack && box[2 * j + 1] >= v.min[j] - slack)) { out.push(k); break; }
    }
  });
  return out;
}
/** Where a piece that counts for `floors` is listed: [{ floor, cutdownFloor }]. With the cutout mask on the lowest
 *  only, its cutdownFloor the highest when that is another floor; else on each, with none. */
export function ruleListing(floors, mask) {
  if (!floors.length) return [];
  if (mask && floors.length > 1) return [{ floor: Math.min(...floors), cutdownFloor: Math.max(...floors) }];
  return [...floors].sort((a, b) => a - b).map(floor => ({ floor, cutdownFloor: 0 }));
}
/** A project building's floors as the export has a building's: [{ index, bottom, top, boxes: [{min, max}] }]. */
export const floorsOf = building => building.floors.map((f, index) => {
  const boxes = f.boxes.map(b => ({ min: b.slice(0, 3), max: b.slice(3, 6) }));
  return { index, boxes, volumes: [], members: [], bottom: Math.min(...boxes.map(b => b.min[2])), top: Math.max(...boxes.map(b => b.max[2])) };
});

/** The source building a building of the project comes from, as seen from one piece taken from that source: the
 *  source's buildings carried by the piece's move (from its source pose `from` to `to`, a whole number of quarter
 *  turns), each floor paired with the project floor its boxes overlap most. `floors`: the project building's, as
 *  floorsOf gives them. The source building chosen is the one that overlaps the project building most, and it must
 *  pair its floors with distinct project floors (one at least). Returns { building, floorMap: { source floor: project
 *  floor or null }, moved: the source's floors carried ({ boxes: [{ min, max }] }) } or null. The boxes may have been
 *  edited since: the piece keeps what its map saved where the rule agrees (carriedListing). compiler.py
 *  source_floor_match is the twin; both pass tools/editor/tests/source_floor_match_cases.json. */
export function sourceFloorMatch(buildings, floors, from, to) {
  const [pitch, yaw, roll] = to.rotation.map((v, k) => ((v - from.rotation[k] + 32768) % 65536 + 65536) % 65536 - 32768);
  const turns = Math.round(yaw / QUARTER);
  if ([pitch, yaw - turns * QUARTER, roll].some(v => Math.abs(v) > POSE_SLACK)) return null;
  const anchor = turned(from.location, turns);
  const shift = to.location.map((v, k) => v - (k < 2 ? anchor[k] : from.location[k]));
  const move = point => [...turned(point, turns), point[2]].map((v, k) => v + shift[k]);
  const carry = box => { const a = move(box.min), z = move(box.max); return { min: a.map((v, j) => Math.min(v, z[j])), max: a.map((v, j) => Math.max(v, z[j])) }; };
  const meet = (p, q) => [0, 1, 2].reduce((n, j) => n * Math.max(0, Math.min(p.max[j], q.max[j]) - Math.max(p.min[j], q.min[j])), 1);
  let best = null;
  for (const b of buildings ?? []) {
    if (!b.floors?.length) continue;
    const moved = b.floors.map(f => ({ boxes: (f.boxes ?? []).map(carry) }));
    const floorMap = {}, used = new Set();
    let total = 0, fine = true;
    moved.forEach((f, k) => {
      let pick = null, most = 0;
      floors.forEach((g, j) => {
        const got = f.boxes.reduce((n, x) => n + g.boxes.reduce((m, y) => m + meet(x, y), 0), 0);
        if (got > most) { most = got; pick = j; }
      });
      if (pick != null && used.has(pick)) fine = false;
      if (pick != null) used.add(pick);
      floorMap[k] = pick;
      total += most;
    });
    if (!fine || !used.size || (best && total <= best.total)) continue;
    best = { building: b, floorMap, moved, total };
  }
  return best && { building: best.building, floorMap: best.floorMap, moved: best.moved };
}
/** `count` floors of one box each over a footprint [x0, y0, x1, y1], from `base` up, each `storey` high. */
const stackedFloors = (footprint, base, count, storey = STOREY_HEIGHT) => Array.from({ length: count }, (_, k) => (
  { boxes: [[footprint[0], footprint[1], base + k * storey, footprint[2], footprint[3], base + (k + 1) * storey]] }));
/** The floors of a building around pieces' boxes ([x0, x1, y0, y1, z0, z1] each): the footprint out to whole tiles
 *  (an edge within a quarter tile of a tile line goes to that line: a wall stands on the line), the base at the
 *  lowest piece (to the level it is within 24 units of), storeys `storey` high with one more on top for a roof, and
 *  the floors at the top that would list none of the pieces left out. grid: { origin, size, dimensions }. Null without
 *  pieces. */
export function floorsAround(boxes, grid, storey = STOREY_HEIGHT) {
  if (!boxes.length) return null;
  const lo = k => Math.min(...boxes.map(b => b[2 * k])), hi = k => Math.max(...boxes.map(b => b[2 * k + 1]));
  const footprint = [0, 0, 0, 0];
  for (const k of [0, 1]) {
    const o = grid.origin[k], s = grid.size[k], n = grid.dimensions[k];
    const edge = (v, out) => { const t = (v - o) / s, r = Math.round(t); return Math.abs(t - r) <= 0.25 ? r : out(t); };
    const a = grid.unbounded ? edge(lo(k), Math.floor) : Math.max(0, edge(lo(k), Math.floor));
    const b = grid.unbounded ? Math.max(a + 1, edge(hi(k), Math.ceil)) : Math.min(n, Math.max(a + 1, edge(hi(k), Math.ceil)));
    footprint[k] = o + a * s; footprint[k + 2] = o + b * s;
  }
  const level = grid.size[2] ?? STOREY, bottom = lo(2), near = grid.origin[2] + Math.round((bottom - grid.origin[2]) / level) * level;
  const base = Math.abs(bottom - near) <= 24 ? near : bottom, top = grid.origin[2] + grid.dimensions[2] * level;
  let count = Math.max(1, Math.ceil((hi(2) - base) / storey)) + 1;
  while (!grid.unbounded && count > 1 && base + count * storey > top + 0.01) count--;
  let floors = stackedFloors(footprint, base, count, storey);
  const used = new Set(boxes.flatMap(b => touchedFloors(b, floorsOf({ floors }))));
  while (count > 1 && !used.has(count - 1)) count--;
  return stackedFloors(footprint, base, count, storey);
}
/** What the compiler warns of in a building (building_edits.py BuildingEdits.buildings), as sentences: a box that
 *  overlaps a floor of another building or another floor of its own. (A box reaching outside the tile grid is only a
 *  note there: it covers a place with no tiles, which harms nothing; 14 November 2026.) others: the map's and
 *  the project's other buildings, [{ name, floors: [{ boxes: [{min, max}] }] }]. fresh(floor, box index): whether a box
 *  is changed or new (a map building's boxes as the map has them are not said; default: every box). `grid` is kept for
 *  the callers. */
export function buildingProblems(building, grid, others, authored = false, fresh = () => true) {
  const out = new Set();
  const meet = (a, b) => [0, 1, 2].every(j => Math.min(a.max[j], b.max[j]) - Math.max(a.min[j], b.min[j]) > 0.5);
  const mine = floorsOf(building);
  mine.forEach((floor, k) => floor.boxes.forEach((box, n) => {
    if (!fresh(k, n)) return;
    for (const other of others) (other.floors ?? []).forEach((f, n) => {
      if ((f.boxes ?? []).some(v => meet(box, v))) out.add(`floor ${k + 1} overlaps floor ${n + 1} of ${other.name}`);
    });
    if (!authored) mine.forEach((f, n) => { if (n !== k && f.boxes.some(v => meet(box, v))) out.add(`floor ${k + 1} overlaps floor ${n + 1}`); });
  }));
  return [...out];
}

// ---------------------------------------------------------------- the map's own buildings edited (map buildings plan)
/** Which new floor each old floor of a map building comes to, by their volumes (the Build's buildings.floor_map):
 *  oldVolumes [[name]], newVolumes [[name or null]] per floor -> { old index: new index (the lowest holding one of its
 *  volumes) or null }. */
export function floorMapOf(oldVolumes, newVolumes) {
  const where = new Map();
  newVolumes.forEach((names, j) => { for (const v of names) if (v != null && !where.has(v)) where.set(v, j); });
  const out = {};
  oldVolumes.forEach((names, k) => {
    const found = names.filter(v => where.has(v)).map(v => where.get(v));
    out[k] = found.length ? Math.min(...found) : null;
  });
  return out;
}
/** A piece's entries in an edited map building (the Build's buildings.carried; both pass
 *  tools/bake/tests/carried_listing_cases.json): the rule with the old boxes at its old pose (oldRule) and with the
 *  new boxes at its new pose (newRule), each [[floor, cutdownFloor]]. Where they agree once the old floors are carried
 *  by floorMap, the piece keeps what the map saved (saved, carried the same way); else the new rule's answer.
 *  Returns { entries, kept }. */
export function carriedListing(saved, oldRule, newRule, floorMap) {
  const order = list => [...list].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const mapped = list => {
    const out = [];
    for (const [k, cut] of list) {
      if (floorMap[k] == null || (cut && floorMap[cut] == null)) return null;
      out.push([floorMap[k], cut ? floorMap[cut] : 0]);
    }
    return order(out);
  };
  const old = mapped(oldRule), now = order(newRule);
  if (old && JSON.stringify(old) === JSON.stringify(now)) {
    const kept = mapped(saved);
    if (kept) return { entries: kept, kept: true };
  }
  return { entries: now, kept: false };
}

/** The tiles world boxes stand on, as the Build's native_copy.changed_tiles works them out: each box
 *  [x0, y0, z0, x1, y1, z1] (game axes) with a quarter tile round it in x and y, every level it reaches (the ground's
 *  included), on the grid `origin` (the level volume's corner) and `dims`. A Set of 'x,y,z'. The Build writes a
 *  diagonal cover tile one stands on whole, and one only next to a change for what the change alters (findings
 *  register F-149, F-155). */
export function changedTiles(boxes, origin, dims, tile = [96, 96, 64], margin = 24) {
  const out = new Set(), e = 1e-3;
  for (const b of boxes) {
    const x0 = Math.max(0, Math.floor((b[0] - margin - origin[0]) / tile[0] + e));
    const x1 = Math.min(dims[0] - 1, Math.ceil((b[3] + margin - origin[0]) / tile[0] - e) - 1);
    const y0 = Math.max(0, Math.floor((b[1] - margin - origin[1]) / tile[1] + e));
    const y1 = Math.min(dims[1] - 1, Math.ceil((b[4] + margin - origin[1]) / tile[1] - e) - 1);
    const z0 = Math.max(0, Math.floor((b[2] - origin[2]) / tile[2] + e));
    const z1 = Math.min(dims[2] - 1, Math.ceil((b[5] - origin[2]) / tile[2] - e) - 1);
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++) out.add(`${x},${y},${z}`);
  }
  return out;
}
