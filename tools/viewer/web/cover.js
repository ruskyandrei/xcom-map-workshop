// Cover blocks and invisible floors (tools/editor/compiler.py COVER_RECIPES and cover_shape, tools/bake/cover_blocks.py):
// pieces hidden in the game, made by the Build from a recipe on any install. This page keeps a record as
// { type, size: [x, y], heights: [z0, z1] } in units: `size` along the piece's own X and Y from its corner (its actor's
// location), `heights` below and above its floor (the location's height), as the handles set them
// (private/plans/done/cover-block-handles-plan.md); an invisible floor's is { type: 'floor', size }, its plate the
// recipe's. Its `type`:
// - 'high' or 'low': a cover block, as LWR's patches place them, at first from 12 below the floor to the recipe's top for
//   its cover (96 above the floor for high cover, 84 for low);
// - 'floor': an invisible floor (EXP-32), a plate two units thin whose top is at the location, units can stand on;
// - 'block': a blocker (recipe version 2, Discord feedback S6), a cover block with Cover None: it blocks movement, gives
//   no cover and lets units see past it.
// Older records give the size in whole tiles, { width, length, type, height } (each tile of `height` past the first
// adding the recipe's heightStep, 96, to the top), and the first ones { width, length, height: 'high' | 'low' } (one tile
// tall): normalCover reads both. The editor draws a piece as a see-through box with its edges; in the game it is hidden.
import * as THREE from 'three';
import { LEVEL, TILE } from './constants.js';
import { stepped, stepsOf } from './snap_steps.js';

export const COVER_MATERIAL = 'cover:material';
export const COVER_KIND = 'cover';
const COLOURS = { high: 0xe0a040, low: 0x6fc0e0, floor: 0x7fd07f, block: 0xd07ad0 };

export const isFloor = c => c?.type === 'floor';
export const isBlocker = c => c?.type === 'block';
/** What a block gives units beside it, in words: "high cover", "low cover", "no cover". */
export const coverWords = c => (isBlocker(c) ? 'no cover' : `${c.type} cover`);
/** A type's first heights (below and above the floor): the recipe's. */
const typeHeights = (recipe, type) => [...recipe.heights[type]];
// What the Add panel's two entries place: one tile, a block of high cover from the recipe's bottom to its top; moved,
// sized and turned after.
export const coverStart = recipe => ({ type: 'high', size: [TILE, TILE], heights: typeHeights(recipe, 'high') });
export const floorStart = () => ({ type: 'floor', size: [TILE, TILE] });

/** A saved record as this page keeps it ({ type, size, heights }, a floor's { type, size }), from any of the three. */
export function normalCover(c, recipe) {
  if (!c || typeof c !== 'object') return c;
  let r = c;
  if (typeof r.height === 'string' && r.type === undefined && Object.keys(r).length === 3)
    r = { width: r.width, length: r.length, type: r.height, height: 1 };      // a first record: one tile tall
  if (Object.hasOwn(r, 'size') || !recipe?.heights?.[r.type]) return r.type === 'floor' && r.heights ? { type: r.type, size: r.size } : r;
  const size = [r.width * TILE, r.length * TILE];
  if (recipe.flat?.includes(r.type)) return { type: r.type, size };
  const [z0, z1] = recipe.heights[r.type];
  return { type: r.type, size, heights: [z0, z1 + (recipe.heightStep ?? TILE) * (r.height - 1)] };
}

/** The synthetic mesh id of a piece's box: one per size, heights and type, shared by the pieces alike. */
export const coverMeshId = c => `cover:${c.size[0]}x${c.size[1]}${c.heights ? `x${c.heights[0]}_${c.heights[1]}` : ''}:${c.type}`;
/** Its box in the actor's frame, game axes: [lo, hi]. */
export function coverBox(c, recipe) {
  const [z0, z1] = c.heights ?? recipe.heights[c.type];
  return [[0, 0, z0], [c.size[0], c.size[1], z1]];
}
const round = v => Math.round(v * 100) / 100;
/** A length in words: whole tiles as tiles ("2 tiles"), anything else in units ("48 units"). */
export const lengthWords = v => (v % TILE === 0 ? `${v / TILE} tile${v === TILE ? '' : 's'}` : `${round(v)} units`);
/** A size across in words: "1 × 2 tiles" when both are whole tiles, else "48 × 96 units". */
export const sizeWords = ([x, y]) => (x % TILE === 0 && y % TILE === 0 ? `${x / TILE} × ${y / TILE} tiles` : `${round(x)} × ${round(y)} units`);
const coverName = c => (isFloor(c) ? `Invisible floor ${sizeWords(c.size)}`
  : `${isBlocker(c) ? 'Blocker' : 'Cover block'} ${sizeWords(c.size)}, top ${round(c.heights[1])} (${coverWords(c)})`);

/** The record the page keeps in data.meshes for a piece's box (the name, bounds and counts the panels read). */
export function coverMeshRecord(c, recipe) {
  const [lo, hi] = coverBox(c, recipe);
  const half = hi.map((v, k) => (v - lo[k]) / 2), centre = hi.map((v, k) => (v + lo[k]) / 2);
  return { name: coverName(c), url: null, vertices: 24, triangles: 12, kind: 'static', bones: [], pose: null,
           bounds: [...centre, ...half, Math.hypot(...half)], sections: [], cover: { ...c } };
}

const fills = new Map(), edges = new Map();
/** The drawn box as a loaded mesh file would give it ({ scene }), in the actor's frame (viewer basis: x, z up, y). */
export function coverScene(c, recipe) {
  const [lo, hi] = coverBox(c, recipe);
  const size = [hi[0] - lo[0], hi[2] - lo[2], hi[1] - lo[1]];
  const geometry = new THREE.BoxGeometry(...size).translate(lo[0] + size[0] / 2, lo[2] + size[1] / 2, lo[1] + size[2] / 2);
  const box = new THREE.Mesh(geometry);
  if (!edges.has(c.type)) edges.set(c.type, new THREE.LineBasicMaterial({ color: COLOURS[c.type], transparent: true, opacity: 0.9 }));
  const lines = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), edges.get(c.type));
  lines.raycast = () => {};
  const scene = new THREE.Group();
  scene.add(box, lines);
  return { scene };
}

/** The see-through fill of a piece's box, by its type. */
export function coverMaterial(type) {
  if (!fills.has(type)) {
    fills.set(type, new THREE.MeshBasicMaterial({ color: COLOURS[type], transparent: true, opacity: type === 'floor' ? 0.4 : 0.28,
                                                  depthWrite: false, side: THREE.DoubleSide }));
  }
  return fills.get(type);
}

// ---- resizing by the handles (cover-block-handles-plan.md, decisions 2 and 3)
export const MIN_ACROSS = 8, MIN_HIGH = 8;
/** The faces a piece's handles stand on: four sides and top and bottom for a block, four sides for a floor. Each is
 *  [key, local game axis 0 | 1 | 2, side -1 | 1]. */
export const coverFaces = c => [['-x', 0, -1], ['+x', 0, 1], ['-y', 1, -1], ['+y', 1, 1],
                                ...(isFloor(c) ? [] : [['-z', 2, -1], ['+z', 2, 1]])];
/** A face moved `delta` units out from the piece (in: below 0), the distance moved in the snap setting's steps (`snap`:
 *  'off', 'fine' or 'tile'; snap_steps.js): { cover, shift }, the new record and how far the corner moves along the
 *  face's axis (a low side's drag moves it, so the opposite side stays where it is). Across, off is continuous, fine
 *  steps of 24 and tile whole tiles; up and down, off continuous, fine 24 and tile levels of 64. A size off the steps
 *  keeps its offset. A side never comes closer than MIN_ACROSS to the other (the nearest step that stays that far),
 *  nor a top than MIN_HIGH to the bottom. */
export function resizedCover(c, recipe, [, axis, side], delta, snap) {
  const out = { ...c, size: [...c.size], ...(c.heights ? { heights: [...c.heights] } : {}) };
  const steps = stepsOf(snap);
  // the least a side or height moved in steps can come to: the nearest step that keeps `least` (or `least` itself)
  const kept = (from, least, step) => (step ? from - Math.floor((from - least) / step + 1e-9) * step : least);
  if (axis < 2) {
    const step = steps.across, max = (recipe.maxTiles ?? 16) * TILE;
    let size = c.size[axis] + stepped(delta, step);
    if (size < MIN_ACROSS) size = kept(c.size[axis], MIN_ACROSS, step);
    if (size > max) size = Math.max(c.size[axis], step ? c.size[axis] + Math.floor((max - c.size[axis]) / step + 1e-9) * step : max);
    out.size[axis] = size;
    return { cover: out, shift: side < 0 ? c.size[axis] - size : 0 };
  }
  const step = steps.up, k = side < 0 ? 0 : 1, span = c.heights[1] - c.heights[0];
  let v = c.heights[k] + stepped(side * delta, step);
  if (side < 0 && v > c.heights[1] - MIN_HIGH) v = c.heights[1] - kept(span, MIN_HIGH, step);
  if (side > 0 && v < c.heights[0] + MIN_HIGH) v = c.heights[0] + kept(span, MIN_HIGH, step);
  out.heights[k] = v;
  return { cover: out, shift: 0 };
}
/** A new type's record: a height on the old type's tile steps moves to the new type's (high's top 96 to low's 84, two
 *  tiles' 192 to 180); any other stays where it is. */
export function retyped(c, recipe, type) {
  if (isFloor(c) || type === 'floor') return { ...c, type };
  const was = typeHeights(recipe, c.type), now = typeHeights(recipe, type), step = recipe.heightStep ?? TILE;
  return { ...c, type, heights: c.heights.map((v, k) => (Math.abs((v - was[k]) % step) < 1e-6 ? v + now[k] - was[k] : v)) };
}

// ---- what the game makes of a cover piece (moved from app.js, review finding 22)
// A cover piece's footprint against the map's tiles, as the game's tile rebuild reads it (research/native/cover-build.md,
// sections 2 to 5; cover-block-handles-plan.md, section 1; EXP-59 to play). `at(u, v)` is a point of the piece's own
// frame (its corner's floor, game axes) in the world, `local(x, y)` a world point across in its frame.
export function coverFrame(root) {
  root.updateMatrixWorld(true);
  const toLocal = root.matrixWorld.clone().invert();
  const at = (u, v, w = 0) => { const p = new THREE.Vector3(u, w, v).applyMatrix4(root.matrixWorld); return [p.x, p.z, p.y]; };
  const local = (x, y, z) => { const p = new THREE.Vector3(x, z, y).applyMatrix4(toLocal); return [p.x, p.z, p.y]; };
  return { at, local };
}
// The game's numbers (cover-build.md): a tile is occupied when its box, 48 each way across and 28 to 92 over its level's
// bottom, meets a piece at least 4 units through every way (or 384 across); fully occupied, with no floor to stand on,
// when the middle 40 x 40 from 60 to 92 meets it too. Crossing to a neighbour is blocked by a sweep from 64 over the
// floor to the neighbour's centre; cover by a sweep from the middle, 44 to 60 over the floor, meeting the piece within 88
// of the middle, looked for only toward an occupied neighbour or from a partly occupied tile.
// Sight is walked between the tiles one level above the floor (eye height: line-of-sight.md, section 2.3), whose own
// blocking sweep runs from their centre, EYE_SWEEP over the floor level's bottom, and stops only at a piece that
// blocks sight (a high block; low cover and blockers let units see past).
const TILE_BOX = [48, 28, 92], TILE_MIDDLE = [20, 60, 92], WALL_SWEEP = 64, COVER_SWEEP = [44, 60], COVER_REACH = 88;
const EYE_SWEEP = 96;
/** A cover piece (`c`, its record) against the tiles round it, its frame { at, local } as coverFrame gives it, the
 *  tile grid's corner [x, y, z] and the cover recipe (for a record with no heights of its own): { tiles: [{ centre,
 *  occupied, full, carried }] (the tiles it reaches), thin, walls (the lines between neighbouring tiles' centres it
 *  blocks), looked (the ways tiles look for cover toward or from it), covered (the tiles that get cover from it), seen
 *  (the lines between tiles' centres it crosses at eye height, eye over its floor), sweep (false when it misses the
 *  height cover is looked for at), top (its floor's height) }. */
export function coverTiles(c, { at, local }, [ox, oy, oz], recipe) {
  const corners = [[0, 0], [c.size[0], 0], [c.size[0], c.size[1]], [0, c.size[1]]].map(([u, v]) => at(u, v));
  const xs = corners.map(p => p[0]), ys = corners.map(p => p[1]), z = corners[0][2];
  const [h0, h1] = c.heights ?? coverBox(c, recipe).map(p => p[2]);
  const inside = (x, y) => { const [u, v] = local(x, y, z); return u >= -1e-6 && v >= -1e-6 && u <= c.size[0] + 1e-6 && v <= c.size[1] + 1e-6; };
  // the footprint's own axes in the world, for an exact test against a tile's square (separating axes)
  const axes = [corners[1], corners[3]].map((q, k) => [(q[0] - corners[0][0]) / c.size[k], (q[1] - corners[0][1]) / c.size[k]]);
  const meets = (cx, cy, half) => {
    if (Math.max(...xs) <= cx - half + 1e-6 || Math.min(...xs) >= cx + half - 1e-6
        || Math.max(...ys) <= cy - half + 1e-6 || Math.min(...ys) >= cy + half - 1e-6) return false;
    return axes.every(([dx, dy], k) => {
      const m = (cx - corners[0][0]) * dx + (cy - corners[0][1]) * dy, r = half * (Math.abs(dx) + Math.abs(dy));
      return m + r > 1e-6 && m - r < c.size[k] - 1e-6;
    });
  };
  // does the footprint cross the line from p to q (across)? (clipped to it in its own frame)
  const crosses = (p, q) => {
    const a = local(p[0], p[1], z), b = local(q[0], q[1], z);
    let t0 = 0, t1 = 1;
    for (let k = 0; k < 2; k++) {
      const d = b[k] - a[k];
      for (const [pk, qk] of [[-d, a[k]], [d, c.size[k] - a[k]]]) {
        if (Math.abs(pk) < 1e-9) { if (qk < 1e-6) return false; continue; }
        if (pk < 0) t0 = Math.max(t0, qk / pk); else t1 = Math.min(t1, qk / pk);
      }
    }
    return t1 - t0 > 1e-6;
  };
  // heights against its floor's level (the level its location stands in)
  const bottom = oz + LEVEL * Math.floor((z - oz) / LEVEL + 1e-6), lo = z + h0, hi = z + h1;
  const spans = (a, b) => hi > bottom + a + 1e-6 && lo < bottom + b - 1e-6;
  const thin = Math.min(c.size[0], c.size[1], h1 - h0) < 4 && Math.max(c.size[0], c.size[1]) < 384;
  const tx0 = Math.floor((Math.min(...xs) - ox) / TILE) - 1, tx1 = Math.ceil((Math.max(...xs) - ox) / TILE);
  const ty0 = Math.floor((Math.min(...ys) - oy) / TILE) - 1, ty1 = Math.ceil((Math.max(...ys) - oy) / TILE);
  const centre = (tx, ty) => [ox + (tx + 0.5) * TILE, oy + (ty + 0.5) * TILE];
  const tile = new Map(), key = (tx, ty) => `${tx},${ty}`;
  for (let tx = tx0; tx <= tx1; tx++) {
    for (let ty = ty0; ty <= ty1; ty++) {
      const [cx, cy] = centre(tx, ty);
      if (!meets(cx, cy, 47.5)) continue;
      const occupied = !thin && spans(TILE_BOX[1], TILE_BOX[2]);
      tile.set(key(tx, ty), { centre: [cx, cy], occupied, full: occupied && meets(cx, cy, TILE_MIDDLE[0]) && spans(TILE_MIDDLE[1], TILE_MIDDLE[2]),
                              carried: inside(cx, cy) });
    }
  }
  const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  let walls = 0, looked = 0, seen = 0;
  const covered = new Set(), wallUp = h0 < WALL_SWEEP && h1 > WALL_SWEEP, eyeUp = spans(EYE_SWEEP, EYE_SWEEP);
  const sweep = h1 > COVER_SWEEP[0] && h0 < COVER_SWEEP[1];
  for (let tx = tx0; tx <= tx1; tx++) {
    for (let ty = ty0; ty <= ty1; ty++) {
      const here = tile.get(key(tx, ty)), [cx, cy] = centre(tx, ty);
      for (const [dx, dy] of DIRS) {
        const next = tile.get(key(tx + dx, ty + dy));
        // a wall: counted once, from the tile on its low side, between two tiles a unit can stand in
        if ((dx > 0 || dy > 0) && wallUp && !here?.full && !next?.full && crosses([cx, cy], centre(tx + dx, ty + dy))) walls++;
        if ((dx > 0 || dy > 0) && eyeUp && crosses([cx, cy], centre(tx + dx, ty + dy))) seen++;
        // cover this way: looked for toward an occupied neighbour, or every way from a partly occupied tile
        if (here?.full || !sweep || !(next?.occupied || (here?.occupied && !here.full))) continue;
        looked++;
        if (crosses([cx, cy], [cx + dx * (COVER_REACH + 1), cy + dy * (COVER_REACH + 1)])) covered.add(key(tx, ty));
      }
    }
  }
  return { tiles: [...tile.values()], thin, walls, looked, covered: covered.size, seen, eye: bottom + EYE_SWEEP - z, sweep, top: z };
}
// What the game will do with a block, in words (coverTiles' model; EXP-59 to play): where units can stand, the tile
// edges it walls off, and the cover it gives.
export function coverGameWords(c, g) {
  const [h0, h1] = c.heights;
  const count = (n, one, many) => (n === 1 ? one : many.replace('#', n));
  const occupied = g.tiles.filter(t => t.occupied).length, full = g.tiles.filter(t => t.full).length;
  const stand = g.thin ? 'Under 4 units through: the game counts it as filling no tile, so units can stand all round it.'
    : full ? `Units can't stand in the ${count(full, 'tile', '# tiles')} whose middle it fills.`
    : occupied ? `It fills no tile's middle, so units can stand in the ${count(occupied, 'tile', 'tiles')} it reaches into.`
    : 'It reaches no tile of the map.';
  const walls = g.walls ? `It stops units crossing ${count(g.walls, 'the tile edge', 'the # tile edges')} it stands across, as a wall does.`
    : (occupied && !full) || g.thin ? 'It stands across no line between tile centres 64 over the floor, so units walk past it.' : '';
  const cover = isBlocker(c) ? 'Units beside it get no cover from it.'
    : h1 <= COVER_SWEEP[0] ? `Its top is under ${COVER_SWEEP[0]} over the floor, below where the game looks for cover (${COVER_SWEEP[0]} to ${COVER_SWEEP[1]}): it gives none.`
    : h0 >= COVER_SWEEP[1] ? `Its bottom is over ${COVER_SWEEP[1]} above the floor, above where the game looks for cover (${COVER_SWEEP[0]} to ${COVER_SWEEP[1]}): it gives none.`
    : g.covered ? `Units in ${count(g.covered, 'the tile', 'the # tiles')} beside it get ${c.type} cover from it.`
    : g.looked ? 'It stands off the lines the game looks for cover along, so it gives none.'
    : 'No tile looks for cover toward it, since it fills none: it gives none.';
  return ['Hidden in the game.', stand, walls, cover].filter(Boolean).join(' ');
}
// Its line of sight, in one sentence: a blocker and low cover are seen through or over; a high block stops sight where
// it stands across the line between tiles at eye height (a unit beside it still leans round a short wall's ends).
export function coverSightWords(c, g) {
  if (isBlocker(c)) return 'Sight: units see and shoot through it.';
  if (c.type === 'low') return 'Sight: units see and shoot over it, as over any low cover.';
  return g.seen ? 'Sight: it blocks line of sight as a wall does, though a unit beside it can lean round its ends.'
    : `Sight: it doesn't stand across eye height (${Math.round(g.eye)} over its floor), so units see and shoot past it.`;
}
