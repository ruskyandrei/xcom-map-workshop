// A made piece's texture mapping on the page (the custom geometry improvements plan, section 5, stage 4; the design
// chosen, B: its section 10.6): what is pure about it. tools/bake/uv_mapping.py is the rule the generators apply; `uv`
// here is its twin, for the handles drawn on a surface (made_mapping_test.mjs checks it on test_uv_mapping.py's
// numbers). The mapping is the free form's `mapping` {surfaces: {role: surface}} (made_free.js; a role left out keeps
// its look's own mapping). Here:
// - each kind's surfaces (MAPPING_ROLES; a wall's 'faces' is one surface on both its faces, picked on either: SURFACES
//   is what Tab steps through, nextSurface), the surface a click's normal falls on (surfaceOfNormal), where a surface
//   lies in the piece's frame (surfacePlane), its extent (surfaceExtent) and the snap steps a drag on it takes
//   (surfaceSteps);
// - a surface's mapping read and written in the numbers (surfaceMapping, withSurface, tidySurface), a mode chosen
//   (withMode: Size first takes the look's repeat, lookRepeat; Count and Fit one by one; Original takes the surface's
//   entry out), a field's value (withValue) and the words of the fold's shut line (mappingWords, surfaceWords);
// - what the look draws on a surface, from its catalogue entry (lookSurface: tools/bake/looks.py surfaces, whether its
//   texture tiles there or is a part of a larger one; surfaceSlots, the materials it draws in), and what the fold says
//   of it (textureNotes); a material's own tiling as the map's export records it (materialTiling) and the pattern's
//   real size it gives a mapped surface (patternSize);
// - the rule (uv) and its inverse (patternPoint): the pattern's corner nearest a point (patternCorner), a handle's
//   drag (slidMapping, turnedMapping, sizedMapping), in the snap setting's steps (snap_steps.js), and the offsets that
//   keep a pattern in place when the piece's frame moves (reframed);
// - where a world-aligned surface's pattern is counted from (mappingOrigin): the mesh request's and the Build's
//   `mappingOrigin` {role: [a0, b0] or [x, y, z]}, made_edits.mapping_origin the compiler's twin, with the cases both
//   tests read (tools/editor/tests/mapping_origin_cases.json).
//
// A surface's point is (a, b), game units on its two axes in the piece's frame (uv_mapping.py's words): a wall's face a
// along the wall (x), b up (z), both faces; a top or underside a along x, b along y (a ramp's slope in its own plane: a
// along it, x0 at its low edge); a ground side a along x or y, b up. The handles work on the rule's (U, V); the generators write them times each face's
// signs (uv_mapping.face_signs), which mirror the image and keep its corners and its turn's sense. Pure: no
// three.js, no document.
import { groundLookOf } from './ground.js';
import { catalogued } from './looks.js';
import { stepped, stepsOf } from './snap_steps.js';

/** Each kind's surfaces that take a mapping (D8: the main faces), in their order. */
export const MAPPING_ROLES = Object.freeze({ fracWall: ['faces'], fracSlab: ['top', 'underside'], ground: ['top', 'sides'] });
export const MAPPING_MODES = ['size', 'fit', 'count'];
/** What Tab steps through on a picked piece: a wall's faces one side then the other (one surface, two places). */
export const SURFACES = Object.freeze({
  fracWall: [{ role: 'faces', side: 'y1' }, { role: 'faces', side: 'y0' }],
  fracSlab: [{ role: 'top' }, { role: 'underside' }],
  ground: [{ role: 'top' }, { role: 'sides' }],
});
// a look's repeat, game units, when its catalogue entry gives none
export const DEFAULT_REPEAT = 192;
const FIELDS = ['mode', 'modeV', 'u', 'v', 'turn', 'flipU', 'flipV', 'offsetU', 'offsetV', 'world'];
const tidy = v => { const r = Math.round(v * 1e6) / 1e6; return r === 0 ? 0 : r; };
// (an offset is in repeats, a small number: kept finer)
const fine = v => { const r = Math.round(v * 1e9) / 1e9; return r === 0 ? 0 : r; };
const finite = v => typeof v === 'number' && Number.isFinite(v);
// a turn in (-180, 180]
const wrapped = t => { const r = ((t % 360) + 360) % 360; return r > 180 ? r - 360 : r; };
// (rounded as the compiler's mapping_origin rounds: half up, to a millionth)
const r6 = v => { const r = Math.floor(v * 1e6 + 0.5) / 1e6; return r === 0 ? 0 : r; };

/** The surface a hit's normal falls on, the normal in the piece's frame (game axes: x and y across, z up): { role,
 *  side } (a wall's face, `side` 'y1' or 'y0'), or null where no mapping is taken (a wall's ends and top, a slab's
 *  edges, a ground shape's bottom). */
export function surfaceOfNormal(kind, [x, y, z]) {
  if (kind === 'fracWall') return Math.abs(y) >= Math.max(Math.abs(x), Math.abs(z)) ? { role: 'faces', side: y >= 0 ? 'y1' : 'y0' } : null;
  if (kind === 'fracSlab') return z > 0.5 ? { role: 'top' } : z < -0.5 ? { role: 'underside' } : null;
  if (kind === 'ground') return z > 0.5 ? { role: 'top' } : z < -0.5 ? null : { role: 'sides' };
  return null;
}
/** The surface after `now` (or before it, `step` -1) in the kind's SURFACES; the first when `now` is none of them. */
export function nextSurface(kind, now, step = 1) {
  const list = SURFACES[kind], i = list.findIndex(s => s.role === now?.role && (s.side ?? null) === (now?.side ?? null));
  return i < 0 ? list[0] : list[(i + step + list.length) % list.length];
}
// (a ramp's slope, rising from its x0 edge at z0 to its x1 edge at z1: its length up the slope, and its run's share)
const isRamp = (kind, n, role) => kind === 'ground' && role === 'top' && n.shape === 'ramp';
const slopeOf = n => { const run = n.x1 - n.x0, rise = n.z1 - n.z0, l = Math.hypot(run, rise); return { l, c: run / l, s: rise / l }; };
/** Where a surface lies in the piece's frame, its numbers `n` free-form: { origin, a, b, normal } (game axes), its
 *  point (a, b) at origin + a·a + b·b, a and b at right angles; a ramp's top on its slope, a along it (its low edge at
 *  a = x0, a the distance up the slope from there: uv_mapping.along_slope); null for a ground shape's sides (fields
 *  only). */
export function surfacePlane(kind, n, { role, side = null }) {
  if (kind === 'fracWall') return role === 'faces' ? { origin: [0, side === 'y0' ? n.y0 : n.y1, 0], a: [1, 0, 0], b: [0, 0, 1], normal: [0, side === 'y0' ? -1 : 1, 0] } : null;
  if (role === 'underside') return kind === 'fracSlab' ? { origin: [0, 0, n.z0], a: [1, 0, 0], b: [0, 1, 0], normal: [0, 0, -1] } : null;
  if (role !== 'top') return null;
  if (isRamp(kind, n, role)) {
    const { c, s } = slopeOf(n);
    return { origin: [n.x0 - n.x0 * c, 0, n.z0 - n.x0 * s], a: [c, 0, s], b: [0, 1, 0], normal: [-s, 0, c] };
  }
  return { origin: [0, 0, n.z1], a: [1, 0, 0], b: [0, 1, 0], normal: [0, 0, 1] };
}
/** A surface's extent (a0, a1, b0, b1): the whole piece's, as the generators read a fit or a count from it (a ramp's
 *  slope's from its low edge x0 to x0 plus its length up it: uv_mapping.slope_extent). */
export function surfaceExtent(kind, n, role) {
  if (kind === 'fracWall' || role === 'sides') return [n.x0, n.x1, n.z0, n.z1];
  return isRamp(kind, n, role) ? [n.x0, n.x0 + slopeOf(n).l, n.y0, n.y1] : [n.x0, n.x1, n.y0, n.y1];
}
/** The surface's point (a, b) of a point [x, y, z] of the piece's frame on its plane `plane` (surfacePlane's). */
export function surfaceAt(plane, p) {
  const d = p.map((v, k) => v - plane.origin[k]), dot = q => d[0] * q[0] + d[1] * q[1] + d[2] * q[2];
  return [dot(plane.a), dot(plane.b)];
}
/** The point of the piece's frame at the surface's point (a, b) (surfacePlane's). */
export const framePoint = (plane, [a, b]) => plane.origin.map((o, k) => o + a * plane.a[k] + b * plane.b[k]);
/** The snap setting's steps along a surface's a and b: across and up on a face or side, across both ways on a top. */
export function surfaceSteps(kind, role, snap) {
  const s = stepsOf(snap);
  return kind === 'fracWall' || role === 'sides' ? [s.across, s.up] : [s.across, s.across];
}

// ---- the mapping in the numbers
/** A surface's mapping in free-form numbers, or null (its look's own). */
export const surfaceMapping = (n, role) => n?.mapping?.surfaces?.[role] ?? null;
/** A surface's fields in their one order, those at their defaults left out (a turn of 0, no flip, no offset, not
 *  aligned to the world; modeV when it is the mode): the mesh's key and the saved record take this spelling. */
export function tidySurface(s) {
  const out = {};
  for (const k of FIELDS) {
    const v = s[k];
    if (v === undefined || v === null) continue;
    if (k === 'modeV' && v === s.mode) continue;
    if ((k === 'turn' || k === 'offsetU' || k === 'offsetV') && v === 0) continue;
    if ((k === 'flipU' || k === 'flipV' || k === 'world') && v !== true) continue;
    out[k] = v;
  }
  return out;
}
/** The numbers with a surface's mapping set, or taken out (`surface` null): `mapping` goes when no surface is left. */
export function withSurface(n, role, surface) {
  const surfaces = { ...(n.mapping?.surfaces ?? {}) };
  if (surface) surfaces[role] = tidySurface(surface); else delete surfaces[role];
  const { mapping: _was, ...rest } = n;
  return Object.keys(surfaces).length ? { ...rest, mapping: { ...(n.mapping ?? {}), surfaces } } : rest;
}
/** A look's repeat on a surface, [u, v] in game units: a ground look's own; a wall's or slab's catalogue entry's
 *  measured repeat of that surface when it has one (a slab's facts' repeats, else its surfaces': a wall's faces' side
 *  A's, else side B's); DEFAULT_REPEAT otherwise. */
export function lookRepeat(kind, n, role) {
  const one = v => Math.round(v * 10) / 10;
  const pair = r => (Array.isArray(r) ? r : [r, r]);
  const ok = r => r.length === 2 && r.every(v => finite(v) && v > 0);
  if (kind === 'ground') {
    const r = pair(groundLookOf(n)?.repeat);
    return ok(r) ? r.map(one) : [DEFAULT_REPEAT, DEFAULT_REPEAT];
  }
  const cat = n?.look && typeof n.look === 'object' ? catalogued(CATALOGUE_KIND[kind], n.look) : null;
  const f = lookSurface(kind, n, role);
  const r = pair(cat?.facts?.repeats?.[role]?.repeat ?? (kind === 'fracWall' ? (f?.A ?? f?.B)?.repeat : f?.repeat));
  return ok(r) ? r.map(one) : [DEFAULT_REPEAT, DEFAULT_REPEAT];
}
// ---- what a look draws on a surface (its catalogue entry's surfaces, tools/bake/looks.py)
const CATALOGUE_KIND = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' };
/** A look's surface as its catalogue entry says the look draws it on its donor (tools/bake/looks.py surfaces): a
 *  slab's or ground shape's { slots, repeat, share, tiles } (tiles [u, v]: whether its texture tiles along each, or
 *  the look draws a part of a larger one there); a wall's faces' { A, B } (A its face toward +y, the fold's side 'y1';
 *  a side null where the look has no face there, only trims); null for a look no catalogue read holds. */
export function lookSurface(kind, n, role) {
  const cat = n?.look && typeof n.look === 'object' ? catalogued(CATALOGUE_KIND[kind], n.look) : null;
  return cat?.surfaces?.[role] ?? null;
}
// (a surface whose look draws a part of a larger texture along an axis: looks.py's rule)
const windowed = f => Array.isArray(f?.tiles) && f.tiles.includes(false);
/** What the fold says of the picked surface `picked` ({ role, side }) beside its fields, each a sentence ([] for
 *  nothing): a wall's look with no face on a side (its outline there all trims, which keep their texture: the mapping
 *  changes nothing on it); and, once the surface is mapped, a look that draws a part of a larger texture there (an
 *  atlas: mapped, the whole texture repeats, its other parts with it) and a wall's faces drawn in several materials up
 *  it (the pattern runs on across them, each drawing it in its own material). Nothing for a look no catalogue holds. */
export function textureNotes(kind, n, picked) {
  const role = picked.role, mapped = Boolean(surfaceMapping(n, role)), f = lookSurface(kind, n, role), out = [];
  const atlas = where => `This look draws a part of a larger texture (an atlas) on ${where}: mapped, the whole texture repeats there, its other parts with it`;
  if (!f) return out;
  if (kind !== 'fracWall') {
    if (mapped && windowed(f)) out.push(atlas(`its ${ROLE_WORDS[role]}`));
    return out;
  }
  const here = picked.side === 'y0' ? 'B' : 'A', there = here === 'A' ? 'B' : 'A';
  if (!f[here] && !f[there]) return ['This look has no faces, only trims, which keep their texture: the mapping changes nothing on it'];
  if (!f[here]) out.push('This side of the look has no face, only trims, which keep their texture: the mapping takes its other side alone');
  else if (!f[there]) out.push('The other side of this look has no face, only trims: the mapping takes this side alone');
  if (!mapped) return out;
  const windows = [here, there].filter(X => windowed(f[X]));
  if (windows.length) out.push(atlas(windows.length === 2 ? 'both its faces' : windows[0] === here ? 'this face' : 'its other face'));
  const slots = Math.max(f[here]?.slots?.length ?? 0, f[there]?.slots?.length ?? 0);
  if (slots > 1) out.push(`Its faces draw ${slots} materials up the wall, a storey each: the pattern runs on across them, each drawing it in its own material, so a picture across the whole wall needs a look with one face material`);
  return out;
}
/** The donor's material slots a surface draws in, from its look's catalogue entry (a wall's the picked side's face
 *  slots), or null where the look is in no catalogue read (the piece's every drawn material then stands for it). */
export function surfaceSlots(kind, n, picked) {
  const f = lookSurface(kind, n, picked.role);
  if (!f) return null;
  return (kind === 'fracWall' ? f[picked.side === 'y0' ? 'B' : 'A'] : f)?.slots ?? [];
}

// ---- a pattern's real size: what a material's own tiling does to the texture coordinates a mapping writes
// (the families whose tiling scalar the export reads into a material's render.uv, tools/viewer/materials.py profile;
// material_tiling_cases.json holds the two sides to the same cases)
const READ_TILING = ['BLDG_Enterable'];
/** What a material multiplies its texture's coordinates by, as the map's export records it (its record's render.uv:
 *  tools/viewer/materials.py profile): { scale [u, v], known }, known where the export read it (a scale other than 1,
 *  read from a texture coordinate node or a family's tiling scalar, or a family whose tiling scalar it reads: a
 *  building's TileXY, 1 where unset), not where it found nothing to read (cooked materials mostly keep no expressions:
 *  its 1 is then only the default) or the coordinates go through a node it can't follow (approximate). */
export function materialTiling(info) {
  const uv = info?.render?.uv ?? {}, scale = Array.isArray(uv.scale) && uv.scale.length === 2 && uv.scale.every(finite) ? uv.scale : [1, 1];
  const family = (info?.parents ?? []).some(p => READ_TILING.includes(String(p).split('.').at(-1)));
  return { scale: [...scale], known: !uv.approximate && (family || scale[0] !== 1 || scale[1] !== 1) };
}
/** The pattern's real size on a mapped surface `s` drawn by materials of tilings `tilings` (materialTiling's, one per
 *  material the surface draws in): { note, known }: known when every one is; a note (a sentence) when they are and
 *  scale the coordinates (all alike), saying where the pattern repeats ("Its material repeats its texture 2 times in
 *  each repeat: the pattern shows every 96"); null otherwise (unscaled, unknown, unmapped, or materials that differ). */
export function patternSize(s, tilings) {
  const known = tilings.length > 0 && tilings.every(t => t.known);
  if (!s || !known) return { note: null, known };
  const [su, sv] = tilings[0].scale;
  if (tilings.some(t => t.scale[0] !== su || t.scale[1] !== sv) || (su === 1 && sv === 1)) return { note: null, known };
  const mv = s.modeV ?? s.mode;
  const times = su === sv ? `${num(su)} times` : `${num(su)} by ${num(sv)} times`;
  const often = (mode, value, k) => (mode === 'fit' ? 1 : value) * k;
  let shows;
  if (s.mode === 'size' && mv === 'size') shows = `every ${num(s.u / su)}${s.u / su !== s.v / sv ? ` by ${num(s.v / sv)}` : ''}`;
  else if (s.mode !== 'size' && mv !== 'size') shows = `${num(often(s.mode, s.u, su))} by ${num(often(mv, s.v, sv))} times over the surface`;
  else {
    const axis = (mode, value, k) => (mode === 'size' ? `every ${num(value / k)}` : `${num(often(mode, value, k))} times`);
    shows = `${axis(s.mode, s.u, su)} along U and ${axis(mv, s.v, sv)} along V`;
  }
  return { note: `Its material repeats its texture ${times} in each repeat: the pattern shows ${shows}`, known };
}
/** The numbers with a surface's mode chosen: 'original' takes its entry out; 'size' first fills u and v with the
 *  look's repeat, 'count' and 'fit' with 1 and 1; the turn, flips, offsets and world kept; the same mode leaves it. */
export function withMode(kind, n, role, mode) {
  const s = surfaceMapping(n, role);
  if (mode === 'original') return s ? withSurface(n, role, null) : n;
  if (!MAPPING_MODES.includes(mode) || (s && s.mode === mode && (s.modeV ?? s.mode) === mode)) return n;
  const [u, v] = mode === 'size' ? lookRepeat(kind, n, role) : [1, 1];
  const { modeV: _v, ...keep } = s ?? {};
  return withSurface(n, role, { ...keep, mode, u, v });
}
/** The numbers with one field of a surface's mapping set ('u', 'v': above 0; 'turn' (kept in -180..180], 'offsetU',
 *  'offsetV': any number; 'flipU', 'flipV', 'world': true or false), or null for a value it cannot take or a surface
 *  with no mapping. */
export function withValue(n, role, field, value) {
  const s = surfaceMapping(n, role);
  if (!s) return null;
  if (['flipU', 'flipV', 'world'].includes(field)) return typeof value === 'boolean' ? withSurface(n, role, { ...s, [field]: value }) : null;
  if (!finite(value) || ((field === 'u' || field === 'v') && !(value > 0))) return null;
  if (!['u', 'v', 'turn', 'offsetU', 'offsetV'].includes(field)) return null;
  const v = field === 'turn' ? tidy(wrapped(value)) : field.startsWith('offset') ? fine(value) : tidy(value);
  return withSurface(n, role, { ...s, [field]: v });
}
const num = v => `${Math.round(v * 100) / 100}`;
const ROLE_WORDS = { faces: 'faces', top: 'top', underside: 'underside', sides: 'sides' };
/** The fold's shut line for a surface: "faces: size 64, 30°", "top: count 3 × 2", "underside: original". */
export function mappingWords(role, s) {
  if (!s) return `${ROLE_WORDS[role]}: original`;
  const axis = (mode, v) => (mode === 'fit' ? 'fit' : `${mode} ${num(v)}`);
  const mv = s.modeV ?? s.mode;
  const how = mv !== s.mode ? `${axis(s.mode, s.u)} / ${axis(mv, s.v)}` : s.mode === 'fit' ? 'fit'
    : `${s.mode} ${num(s.u)}${s.u !== s.v ? ` × ${num(s.v)}` : ''}`;
  const more = [s.turn ? `${num(s.turn)}°` : '', s.flipU || s.flipV ? 'flipped' : '', s.world ? 'world' : ''].filter(Boolean);
  return `${ROLE_WORDS[role]}: ${[how, ...more].join(', ')}`;
}
/** Which surface is picked, in words, and what Tab picks next. */
export function surfaceWords(kind, picked) {
  if (kind === 'fracWall') return 'Its faces: both take this mapping (Tab: the other face)';
  if (picked.role === 'sides') return 'Its sides: set here, with no handles on them (Tab: its top)';
  return picked.role === 'top' ? `Its top (Tab: its ${kind === 'ground' ? 'sides' : 'underside'})` : 'Its underside (Tab: its top)';
}

// ---- the rule and its inverse
const scaled = (value, mode, size, low, high) => {
  if (mode === 'size') return value / size;
  const span = high - low;
  return span <= 0 ? 0 : (value - low) / span * (mode === 'fit' ? 1 : size);
};
/** The texture coordinates [u, v] of the point (a, b) of a surface mapped by `surface` (uv_mapping.uv's twin):
 *  `extent` (a0, a1, b0, b1) the whole surface's, `origin` where the piece's frame stands on the surface's axes in the
 *  world (a world-aligned surface's). The point turned, scaled along the turned axes (a count or a fit over the run of
 *  the surface's turned corners along each), mirrored, then slid by the offsets. (The generators write these times
 *  each face's signs, uv_mapping.face_signs; a whole number stays whole, so the pattern's corners are where they are.) */
export function uv(surface, a, b, extent, origin = [0, 0]) {
  let [a0, a1, b0, b1] = extent;
  if (surface.world) { a += origin[0]; b += origin[1]; a0 += origin[0]; a1 += origin[0]; b0 += origin[1]; b1 += origin[1]; }
  const turn = Number(surface.turn ?? 0) * (Math.PI / 180);
  if (turn) {
    const c = Math.cos(turn), s = Math.sin(turn), corners = [a0, a1].flatMap(x => [b0, b1].map(y => [x * c - y * s, x * s + y * c]));
    [a, b] = [a * c - b * s, a * s + b * c];
    [a0, a1, b0, b1] = [Math.min(...corners.map(q => q[0])), Math.max(...corners.map(q => q[0])),
                        Math.min(...corners.map(q => q[1])), Math.max(...corners.map(q => q[1]))];
  }
  let U = scaled(a, surface.mode, Number(surface.u), a0, a1), V = scaled(b, surface.modeV ?? surface.mode, Number(surface.v), b0, b1);
  if (surface.flipU) U = -U;
  if (surface.flipV) V = -V;
  return [U + Number(surface.offsetU ?? 0), V + Number(surface.offsetV ?? 0)];
}
// One axis of the rule, on the turned axes, as (q - lo) * k.
function axisMap(mode, size, low, high) {
  if (mode === 'size') return { k: 1 / size, lo: 0 };
  const span = high - low;
  return { k: span > 0 ? (mode === 'fit' ? 1 : size) / span : 0, lo: low };
}
// The rule's parts: its turn (c, s), each turned axis's (q - lo) * k, the flips, the frame's world origin, the offsets.
function mapOf(s, extent, origin) {
  const o = s.world ? origin : [0, 0], t = Number(s.turn ?? 0) * (Math.PI / 180), c = t ? Math.cos(t) : 1, sn = t ? Math.sin(t) : 0;
  const [a0, a1, b0, b1] = [extent[0] + o[0], extent[1] + o[0], extent[2] + o[1], extent[3] + o[1]];
  const corners = [a0, a1].flatMap(x => [b0, b1].map(y => [x * c - y * sn, x * sn + y * c]));
  const run = k => [Math.min(...corners.map(q => q[k])), Math.max(...corners.map(q => q[k]))];
  return { A: axisMap(s.mode, Number(s.u), ...run(0)), B: axisMap(s.modeV ?? s.mode, Number(s.v), ...run(1)),
           fu: s.flipU ? -1 : 1, fv: s.flipV ? -1 : 1, c, s: sn, o, off: [Number(s.offsetU ?? 0), Number(s.offsetV ?? 0)] };
}
/** Where on the surface the texture coordinates [U, V] fall (uv's inverse), or null when a fit or count has no
 *  extent to stand on. */
export function patternPoint(surface, extent, origin, [U, V]) {
  const m = mapOf(surface, extent, origin);
  if (!m.A.k || !m.B.k) return null;
  const qa = (U - m.off[0]) * m.fu / m.A.k + m.A.lo, qb = (V - m.off[1]) * m.fv / m.B.k + m.B.lo;
  // (turned back)
  return [qa * m.c + qb * m.s - m.o[0], -qa * m.s + qb * m.c - m.o[1]];
}
/** The pattern's corner (whole texture coordinates) nearest the point (a, b) of the surface: where its handles
 *  stand. */
export function patternCorner(surface, extent, origin, [a, b]) {
  const [U, V] = uv(surface, a, b, extent, origin);
  return [Math.round(U) + 0, Math.round(V) + 0];
}
// The surface with its offsets set so that the point `p` of the surface is at the texture coordinates `corner`.
function pinned(surface, extent, origin, p, corner) {
  const raw = uv({ ...surface, offsetU: 0, offsetV: 0 }, p[0], p[1], extent, origin);
  return tidySurface({ ...surface, offsetU: fine(corner[0] - raw[0]), offsetV: fine(corner[1] - raw[1]) });
}
// The change of the rule's (U, V) for a move (da, db) on the surface: turned, scaled, mirrored.
function linear(m, da, db) {
  const qa = da * m.c - db * m.s, qb = da * m.s + db * m.c;
  return [qa * m.A.k * m.fu, qb * m.B.k * m.fv];
}
/** The surface slid by the move `d` [da, db] on it (the blue dot's drag), each in its step (`steps`, 0: smoothly):
 *  its offsets change, so the pattern moves with the pointer. */
export function slidMapping(surface, extent, origin, d, steps = [0, 0]) {
  const m = mapOf(surface, extent, origin), [du, dv] = linear(m, stepped(d[0], steps[0]), stepped(d[1], steps[1]));
  return tidySurface({ ...surface, offsetU: fine(m.off[0] - du), offsetV: fine(m.off[1] - dv) });
}
/** The surface turned as the pointer turned `delta` degrees about the corner `corner` on it (the ring's drag: the
 *  angle on the surface's own axes a, b), in steps of `step` degrees (0: smoothly): its turn kept in (-180, 180], the
 *  corner staying where it is. The rule turns the point by the turn, so the pattern turns the other way on (a, b),
 *  flipped or not: the ring's turn is the pointer's, seen from either side (a face's signs mirror the image, not its
 *  turn). */
export function turnedMapping(surface, extent, origin, corner, delta, step = 0) {
  const p = patternPoint(surface, extent, origin, corner);
  if (!p) return tidySurface(surface);
  const turn = tidy(wrapped(Number(surface.turn ?? 0) - stepped(delta, step)));
  return pinned({ ...surface, turn }, extent, origin, p, corner);
}
/** The surface with its offsets moved so that its pattern stays where it is when the piece's frame moves by `shift`
 *  [da, db] on the surface (Pivot to corner: made_free.js pivotedToCorner): flips * S * R(turn) * shift on each axis
 *  tiled by size (a count's or a fit's goes with the surface's extent, which moves with the frame); one aligned to the
 *  world stays as it is (it is counted from the world's origin). */
export function reframed(surface, shift) {
  if (surface.world) return surface;
  const m = mapOf(surface, [0, 1, 0, 1], [0, 0]), [du, dv] = linear(m, shift[0], shift[1]), mv = surface.modeV ?? surface.mode;
  const offsetU = surface.mode === 'size' ? fine(m.off[0] + du) : m.off[0], offsetV = mv === 'size' ? fine(m.off[1] + dv) : m.off[1];
  return offsetU === m.off[0] && offsetV === m.off[1] ? surface : tidySurface({ ...surface, offsetU, offsetV });
}
/** The surface with its repeat sized by the white dot's drag: the dot `reach` repeats along u from the corner, the
 *  pointer moved from `from` to `to` (distances from the corner along the dot's way, game units on the surface) in
 *  steps of `step` (0: smoothly); u and v scaled alike (a count's the other way), a repeat 1 unit long at least, the
 *  corner staying where it is. */
export function sizedMapping(surface, extent, origin, corner, reach, from, to, step = 0) {
  const p0 = patternPoint(surface, extent, origin, corner), p1 = patternPoint(surface, extent, origin, [corner[0] + reach, corner[1]]);
  if (!p0 || !p1) return tidySurface(surface);
  const L = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
  if (!(L > 0)) return tidySurface(surface);
  let len = L + stepped(to - from, step);
  if (len < reach) len = step > 0 && L >= reach ? L - Math.floor((L - reach) / step) * step : Math.min(L, reach);
  const k = len / L, next = { ...surface }, mv = surface.modeV ?? surface.mode;
  if (surface.mode === 'size') next.u = tidy(surface.u * k); else if (surface.mode === 'count') next.u = tidy(surface.u / k);
  if (mv === 'size') next.v = tidy(surface.v * k); else if (mv === 'count') next.v = tidy(surface.v / k);
  return pinned(next, extent, origin, p0, corner);
}
/** Whether a surface's repeat can be sized by a handle (a fit both ways cannot). */
export const sizable = s => Boolean(s) && !(s.mode === 'fit' && (s.modeV ?? s.mode) === 'fit');

// ---- world alignment
// (a rotator's step as the package holds it: half away from zero, compiler_tables.game_round)
const gameRound = v => (v >= 0 ? Math.floor(v + 0.5) : Math.ceil(v - 0.5));
/** Where the piece's frame stands on each world-aligned surface's axes in the world (uv_mapping.origin_of reads it),
 *  {role: place}, or null when no surface of the kind is aligned to the world: a wall's faces [the location along the
 *  piece's x, its z]; a top or underside [the location along the piece's x and along its y]; a ground shape's sides
 *  [along its x, along its y, z] (a side along x reads x, one along y reads y). The piece's axes are its rotator's yaw
 *  rounded to a whole step, as the package holds it; each number to a millionth, half up (made_edits.mapping_origin,
 *  the same rule). */
export function mappingOrigin(kind, mapping, location, rotation) {
  const surfaces = mapping?.surfaces ?? {}, roles = (MAPPING_ROLES[kind] ?? []).filter(r => surfaces[r]?.world === true);
  if (!roles.length) return null;
  const yaw = gameRound(rotation[1]) * 2 * Math.PI / 65536, c = Math.cos(yaw), s = Math.sin(yaw);
  const ax = location[0] * c + location[1] * s, ay = -location[0] * s + location[1] * c;
  const place = { faces: [ax, location[2]], top: [ax, ay], underside: [ax, ay], sides: [ax, ay, location[2]] };
  return Object.fromEntries(roles.map(r => [r, place[r].map(r6)]));
}
