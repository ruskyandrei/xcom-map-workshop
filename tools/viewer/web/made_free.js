// Made pieces in the free form (the custom geometry improvements plan, stage 2, its section 10.2): what is pure about a
// wall's, slab's or ground shape's numbers when they say everything in fields. A free-form request is its kind's
// FREE_VERSION, its numbers `free: 1` with extents at any size in the piece's own frame: x0..x1 and y0..y1 (a wall's
// faces, a slab's or ground shape's footprint) and z0..z1 (a wall's bottom and top over its floor, a slab's plate, a
// ground shape's plate or body); a wall's `tall` ('repeat' or 'stretch', decision D3); openings or holes anywhere
// inside; `look` absent (the kind's default), a look id or a donor look, with `plain` when none was chosen; a rock's
// `points`; a texture `mapping` (stage 4). tools/editor/made_edits.py free_valid checks the same on the compiler's side.
//
// Here: a request in the free form from any older one (freeRequest, from the old numbers' heights: walls.js wallSpec
// and wallTop, slabLookOf, ground.js groundBox), a face dragged with the piece's origin staying where it is (decision
// D1: resizedFace, with the openings or holes it no longer holds clipped or gone), the piece renumbered from its low
// corner (Pivot to corner: pivotedToCorner, its blasts and points shifted with it), whether numbers are a free form's
// the editor makes (toolFree), and its mesh as the editor's server draws it (freeNumbers, freeBounds, freeMesh,
// freeShape: the same endpoints as the older numbers', which the server reads by their `free`). Locations are game units; a piece's frame has x and y across, z up.
import { GROUND_LOOKS, groundBox, POINTS_VERSION } from './ground.js';
import { blastQuery, madeRecord, SLAB_LOOKS, slabLookOf, spelledLook, WALL_LOOKS, wallSpec, wallTop } from './walls.js';

/** The free form's request version of each kind (made_edits.py FREE_VERSION). */
export const FREE_VERSION = { fracWall: 5, fracSlab: 4, ground: 5 };
const KEY = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' };
const PLAIN_VERSION = { fracWall: 4, fracSlab: 3, ground: 3 };
// the least a piece's extent comes to along any axis (a drag stops there), and a cut-out's least size
export const FREE = { least: 1, leastCut: 1 };
const AXES = { x0: 0, x1: 0, y0: 1, y1: 1, z0: 2, z1: 2 };
const tidy = v => { const r = Math.round(v * 1e6) / 1e6; return r === 0 ? 0 : r; };
// (a texture offset is in repeats, a small number: kept finer)
const fine = v => { const r = Math.round(v * 1e12) / 1e12; return r === 0 ? 0 : r; };

/** Whether a request is in the free form. */
export const isFree = g => Boolean(g) && g.version === FREE_VERSION[g.kind] && g[KEY[g.kind]]?.free === 1;

/** A made piece's request in the free form, from any version: its numbers' extents as its look made them (a wall's
 *  faces its look's `through` either side, its bottom and top its look's and storeys', `tall` 'repeat'; a slab's
 *  plate its look's heights; a ground shape's its groundBox), its look as it was (a plain one `plain`), its other
 *  numbers kept; storeys and height go, said by the extents. A free one as it is. */
export function freeRequest(g) {
  if (!g || !KEY[g.kind] || isFree(g)) return g;
  const key = KEY[g.kind], n = g[key], plain = g.version === PLAIN_VERSION[g.kind] || (g.kind === 'ground' && g.version === POINTS_VERSION && n.look === undefined);
  const { storeys: _s, height: _h, ...rest } = n;
  let out;
  if (g.kind === 'fracWall') {
    const spec = wallSpec(n);
    out = { ...rest, free: 1, y0: -spec.through, y1: spec.through, z0: spec.bottom, z1: wallTop(n), tall: 'repeat' };
  } else if (g.kind === 'fracSlab') {
    const look = slabLookOf(n);
    out = { ...rest, free: 1, z0: look?.bottom ?? -2, z1: look?.top ?? 2 };
  } else {
    const b = groundBox(n);
    out = { ...rest, free: 1, z0: b[4], z1: b[5] };
  }
  if (plain) out.plain = true;
  return { ...g, version: FREE_VERSION[g.kind], [key]: out };
}

/** Whether free-form numbers are ones the editor makes and draws: finite extents with at least FREE.least each way,
 *  openings or holes inside and of some size, a whole seed. */
export function toolFree(kind, n) {
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  if (!n || n.free !== 1 || !['x0', 'x1', 'y0', 'y1', 'z0', 'z1'].every(k => finite(n[k]))) return false;
  if (!(n.x1 - n.x0 >= FREE.least - 1e-9 && n.y1 - n.y0 >= FREE.least - 1e-9 && n.z1 - n.z0 >= FREE.least - 1e-9)) return false;
  if (!Number.isInteger(n.seed ?? 1)) return false;
  if (kind === 'fracWall') return (n.openings ?? []).every(o => ['x0', 'x1', 'z0', 'z1'].every(k => finite(o[k]))
    && n.x0 <= o.x0 && o.x0 < o.x1 && o.x1 <= n.x1 && o.z0 < o.z1);
  if (kind === 'fracSlab') return (n.holes ?? []).every(h => ['x0', 'x1', 'y0', 'y1'].every(k => finite(h[k]))
    && n.x0 <= h.x0 && h.x0 < h.x1 && h.x1 <= n.x1 && n.y0 <= h.y0 && h.y0 < h.y1 && h.y1 <= n.y1);
  return true;
}

/** Openings (walls, x and z) or holes (slabs, x and y) clipped to the piece's extents: each one's part inside them,
 *  those left smaller than FREE.leastCut gone. Gives { cuts, removed }. */
function clippedCuts(cuts, n, ka, kb) {
  const out = [];
  let removed = 0;
  for (const c of cuts ?? []) {
    const d = { ...c, [`${ka}0`]: tidy(Math.max(c[`${ka}0`], n[`${ka}0`])), [`${ka}1`]: tidy(Math.min(c[`${ka}1`], n[`${ka}1`])) };
    if (kb === 'y') { d.y0 = tidy(Math.max(c.y0, n.y0)); d.y1 = tidy(Math.min(c.y1, n.y1)); }
    const ok = d[`${ka}1`] - d[`${ka}0`] >= FREE.leastCut - 1e-9 && (kb !== 'y' || d.y1 - d.y0 >= FREE.leastCut - 1e-9);
    if (ok) out.push(d); else removed++;
  }
  return { cuts: out, removed };
}

/** The numbers with one face ('x0', 'x1', 'y0', 'y1', 'z0' or 'z1') moved `delta` units along its axis (out of the low
 *  faces is below 0), the piece's origin staying where it is (decision D1): only that face's number changes, so its
 *  openings, holes, blasts, points and texture stay where they are in the world. The face stops FREE.least from the
 *  opposite one. A wall's openings (x and z) or a slab's holes (x and y) are clipped to the new extents, and one left
 *  too small goes; a wall's opening cut through its old top or to its old bottom stays cut through. Gives { numbers,
 *  removed, clipped }. */
export function resizedFace(kind, n, face, delta) {
  const axis = AXES[face], low = face.endsWith('0'), other = `${face[0]}${low ? 1 : 0}`;
  let v = n[face] + delta;
  v = low ? Math.min(v, n[other] - FREE.least) : Math.max(v, n[other] + FREE.least);
  const out = { ...n, [face]: tidy(v) };
  let removed = 0, clipped = 0;
  if (kind === 'fracWall' && (axis === 0 || axis === 2)) {
    // (a gap reaching the old top or bottom keeps reaching it)
    const cuts = (n.openings ?? []).map(o => ({ ...o,
      ...(face === 'z1' && o.z1 >= n.z1 - 1e-6 ? { z1: out.z1 } : {}), ...(face === 'z0' && o.z0 <= n.z0 + 1e-6 ? { z0: out.z0 } : {}) }));
    const r = clippedCuts(cuts, out, axis === 0 ? 'x' : 'z', null);
    out.openings = r.cuts;
    removed = r.removed;
    clipped = out.openings.filter((o, i) => JSON.stringify(o) !== JSON.stringify(cuts[i])).length;
  } else if (kind === 'fracSlab' && axis < 2) {
    const r = clippedCuts(n.holes, out, 'x', 'y');
    out.holes = r.cuts; removed = r.removed;
  } else if (kind === 'ground' && n.points && axis < 2) {
    // (a rock's moved points stay inside its footprint)
    out.points = n.points.map(p => [tidy(Math.max(out.x0, Math.min(out.x1, p[0]))), tidy(Math.max(out.y0, Math.min(out.y1, p[1]))), p[2]]);
  }
  return { numbers: out, removed, clipped };
}

/** Pivot to corner (decision D1): the numbers renumbered from their low corner (x0 and y0 to 0; a wall's z0 and a
 *  slab's or ground shape's stay, as its floor or ground is its origin's height), every number in the frame shifted
 *  with them: openings, holes, a rock's points, the blasts (`blasts`, [{ at: [x, y, z], radius }] in the piece's
 *  frame) and a mapping's offsets (in repeats of a surface's size; a world-aligned surface stays). Gives { numbers,
 *  blasts, shift: [dx, dy, dz] }: the piece's origin moves by `shift` in its own frame, so nothing moves in the world. */
export function pivotedToCorner(kind, n, blasts = null) {
  const shift = [n.x0, n.y0, 0];
  const out = { ...n, x0: 0, x1: tidy(n.x1 - n.x0), y0: 0, y1: tidy(n.y1 - n.y0) };
  if (kind === 'fracWall') {
    // (a wall's y0 and y1 are its faces about its line: they stay, the line is its origin's)
    out.y0 = n.y0; out.y1 = n.y1; shift[1] = 0;
    out.openings = (n.openings ?? []).map(o => ({ ...o, x0: tidy(o.x0 - shift[0]), x1: tidy(o.x1 - shift[0]) }));
  }
  if (kind === 'fracSlab') out.holes = (n.holes ?? []).map(h => ({ ...h, x0: tidy(h.x0 - shift[0]), x1: tidy(h.x1 - shift[0]), y0: tidy(h.y0 - shift[1]), y1: tidy(h.y1 - shift[1]) }));
  if (kind === 'ground' && n.points) out.points = n.points.map(p => [tidy(p[0] - shift[0]), tidy(p[1] - shift[1]), p[2]]);
  if (n.mapping?.surfaces) {
    const surfaces = {};
    for (const [role, s] of Object.entries(n.mapping.surfaces)) {
      // (a surface's u runs along x on a wall's faces and a slab's or ground's top; its v up or along y)
      const du = s.mode === 'size' && !s.world ? shift[0] / s.u : 0, dv = s.mode === 'size' && !s.world && role !== 'faces' ? shift[1] / s.v : 0;
      surfaces[role] = du || dv ? { ...s, offsetU: fine((s.offsetU ?? 0) + du), offsetV: fine((s.offsetV ?? 0) + dv) } : s;
    }
    out.mapping = { ...n.mapping, surfaces };
  }
  const moved = blasts?.map(b => ({ ...b, at: [tidy(b.at[0] - shift[0]), tidy(b.at[1] - shift[1]), b.at[2]] })) ?? blasts;
  return { numbers: out, blasts: moved, shift };
}

/** A free-form piece's box in its frame [x0, x1, y0, y1, z0, z1]. */
export const freeBox = n => [n.x0, n.x1, n.y0, n.y1, n.z0, n.z1];
/** Its size in words: "143.5 × 24 × 217.25" (along, across, up), to two places. */
export const freeSizeWords = n => [n.x1 - n.x0, n.y1 - n.y0, n.z1 - n.z0].map(v => `${Math.round(v * 100) / 100}`).join(' × ');

// ---- a free-form piece's mesh, drawn by the editor's server (generated.py) from the same endpoints as the older
// numbers' (it reads them by their `free`)
const ENDPOINT = { fracWall: ['fracwall', 'wall'], fracSlab: ['fracslab', 'slab'], ground: ['ground', 'ground'] };
const DEFAULT_LOOK = { fracWall: WALL_LOOKS[0].id, fracSlab: SLAB_LOOKS[0].id, ground: GROUND_LOOKS[0].id };
/** Free-form numbers in the one spelling their mesh's key and request use: the extents, the kind's own fields, a look
 *  other than the default (spelled as generated.py donor_look), the mapping, and a wall's end styles where it is
 *  joined (`ends`: madeWallJoins', two free ends left out). */
export function freeNumbers(kind, n, ends = null) {
  const out = { free: 1, x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: n.z0, z1: n.z1, seed: n.seed ?? 1 };
  if (kind === 'fracWall') {
    out.tall = n.tall ?? 'repeat';
    out.openings = (n.openings ?? []).map(o => ({ x0: o.x0, x1: o.x1, z0: o.z0, z1: o.z1 }));
    if (ends && (ends[0] !== 'free' || ends[1] !== 'free')) out.ends = ends.map(e => (typeof e === 'string' ? e : { inset: e.inset, lean: e.lean }));
  } else if (kind === 'fracSlab') out.holes = (n.holes ?? []).map(h => ({ x0: h.x0, x1: h.x1, y0: h.y0, y1: h.y1 }));
  else {
    out.shape = n.shape;
    if (n.points) out.points = n.points.map(p => [...p]);
  }
  if (n.look !== undefined && n.look !== DEFAULT_LOOK[kind] && !n.plain) out.look = spelledLook(n.look);
  if (n.mapping) out.mapping = structuredClone(n.mapping);
  return out;
}
/** A free-form piece's mesh bounds (the mesh form's [centre, half sizes, radius]): its box, a wall's x in from its ends
 *  as they reach (a free end its look's inset, 'line' 0, 'through' its half thickness past it, a leaning end its inset
 *  less its lean across the faces) and its faces widened by its look's trims. */
export function freeBounds(kind, n, ends = null) {
  let b = freeBox(n);
  if (kind === 'fracWall') {
    const spec = wallSpec(n), half = (n.y1 - n.y0) / 2, proud = Math.max(0, spec.half - spec.through);
    const reach = e => (typeof e === 'object' && e ? e.inset - Math.abs(e.lean) * half : e === 'line' ? 0 : e === 'through' ? -half : spec.endInset);
    const [e0, e1] = ends ?? ['free', 'free'];
    b = [n.x0 + reach(e0), n.x1 - reach(e1), n.y0 - proud, n.y1 + proud, n.z0, n.z1];
  }
  const h = [0, 1, 2].map(k => (b[2 * k + 1] - b[2 * k]) / 2);
  return [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2, ...h, Math.hypot(...h)];
}
/** A free-form piece's mesh: { key, url, bounds, sections } (its blasts, a wall's or slab's, in its key and request). */
export function freeMesh(kind, n, ends = null, blasts = null) {
  const [path, param] = ENDPOINT[kind], numbers = freeNumbers(kind, n, ends), broken = kind === 'ground' ? { key: '', query: {} } : blastQuery(blasts);
  const sections = kind === 'fracWall' ? wallSpec(n).sections : kind === 'fracSlab' ? slabLookOf(n)?.sections ?? 2 : 1;
  return { key: `made:${path}:${JSON.stringify(numbers)}${broken.key}`, sections, bounds: freeBounds(kind, n, ends),
           url: `/generated/${path}.glb?${new URLSearchParams({ [param]: JSON.stringify(numbers), ...broken.query })}` };
}
/** A free-form piece's { mesh, materials } on its template's materials by slot (walls.js madeRecord), or {} when the
 *  editor would not draw its numbers. */
export function freeShape(template, generated, meshes) {
  const n = generated[KEY[generated.kind]];
  if (!toolFree(generated.kind, n)) return {};
  const m = freeMesh(generated.kind, n, null, generated.blasts);
  return madeRecord(template, meshes, m.key, { noun: { fracWall: 'a wall', fracSlab: 'a slab', ground: 'ground' }[generated.kind],
                                               url: m.url, sections: m.sections, bounds: m.bounds });
}
