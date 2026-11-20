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

export const COVER_MATERIAL = 'cover:material';
export const COVER_KIND = 'cover';
const TILE = 96;
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
/** A face moved `delta` units out from the piece (in: below 0), with the snap setting's steps (`snap`: 'off', 'fine' or 'tile'):
 *  { cover, shift }, the new record and how far the corner moves along the face's axis (a low side's drag moves it,
 *  so the opposite side stays where it is).
 *  - Across, the size counts from the opposite side: off to 1 unit, fine in steps of 24, tile in whole tiles.
 *  - Up and down, the face keeps to steps from the type's first top or bottom (the recipe's): off to 1 unit, fine in
 *    steps of 24, tile in steps of 96 (today's tile heights). */
export function resizedCover(c, recipe, [, axis, side], delta, snap) {
  const out = { ...c, size: [...c.size], ...(c.heights ? { heights: [...c.heights] } : {}) };
  if (axis < 2) {
    const step = snap === 'tile' ? TILE : snap === 'fine' ? 24 : 1;
    const raw = c.size[axis] + delta;
    const size = Math.min((recipe.maxTiles ?? 16) * TILE, Math.max(snap === 'off' ? MIN_ACROSS : step, Math.round(raw / step) * step));
    out.size[axis] = size;
    return { cover: out, shift: side < 0 ? c.size[axis] - size : 0 };
  }
  const step = snap === 'tile' ? (recipe.heightStep ?? TILE) : snap === 'fine' ? 24 : 1;
  const [b0, t0] = typeHeights(recipe, c.type), k = side < 0 ? 0 : 1, anchor = side < 0 ? b0 : t0;
  let v = anchor + Math.round((c.heights[k] + side * delta - anchor) / step) * step;
  if (side < 0) v = Math.min(v, c.heights[1] - MIN_HIGH); else v = Math.max(v, c.heights[0] + MIN_HIGH);
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
