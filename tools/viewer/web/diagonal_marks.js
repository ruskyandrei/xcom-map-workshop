// Diagonal cover marks (private/plans/todo/diagonal-cover-by-hand-and-views-plan.md; KNOWN-BUGS.md KB-20): the rules,
// records and words of the Diagonal cover view, with no page (diagonal_marks_test.mjs). diagonal_wiring.js draws them
// and edits them.
//
// A mark is a floor tile and one to four of its corners: a unit on the tile gets cover toward those corners, along the
// tile's diagonals. A corner is [sx, sy], each +1 or -1, in game axes (the diagonal table's N [-1, 1], S [1, -1],
// E [-1, -1], W [1, 1]: research/native/cover-build.md, section 4).
// - The map's own marks are the export's tactical.diagonalCover (the tiles its makers' seeds marked), each with the
//   corners the game's build gave it, counted from the game's tile corner (map_grid.js tileCorner).
// - The project's own (`hand`: the editor state's projectDiagonal) is { marks: [{ at, toward, from? }], removed: [at] }
//   or null: a mark the project adds, or one of the map's it moves or turns (`from`: the map's tile it was); and the
//   map's marks it deletes. Places (`at`, `from`, `removed`) are a tile's middle in the world, the level's middle in
//   height, so a grid grown by whole tiles leaves each on its tile (the compiler and the Build count tiles so too:
//   tools/editor/diagonal_edits.py, tools/bake/native_copy.py diagonal_edit).
// - The marks that follow their pieces (`carried`: worked out by the wiring from the pieces as they stand; plan,
//   section 5) are [{ at, toward, from?, by }]: saved with the project for the Build, worked out again when it opens.
// Every edit here returns a new `hand` (the old one is the undo), null for no edit at all.

export const TILE_SIZE = [96, 96, 64];
// the four corners, in the diagonal table's order
export const CORNERS = [[-1, 1], [1, -1], [-1, -1], [1, 1]];
export const cornerKey = c => `${c[0]},${c[1]}`;
const sameCorner = (a, b) => a[0] === b[0] && a[1] === b[1];
const sortCorners = list => CORNERS.filter(c => list.some(d => sameCorner(c, d)));
export const tileKey = t => t.join(',');

/** The tile a world point [x, y, z] is in, counted from the game's tile corner. */
export const tileOf = (point, corner) => [0, 1, 2].map(k => Math.floor((point[k] - corner[k]) / TILE_SIZE[k]));
/** A tile's middle in the world (the level's middle in height): the place a project names it by. */
export const middleOf = (tile, corner) => [0, 1, 2].map(k => Number((corner[k] + TILE_SIZE[k] * (tile[k] + 0.5)).toFixed(4)));

/** The map's own marks, from the export's tactical.diagonalCover: [{ tile, toward, floor, low, wall (the actor path of
 *  the piece its first corner takes its cover from, export 40; null where none) }]. */
export function ownMarks(scene) {
  return (scene?.preview ? [] : scene?.tactical?.diagonalCover ?? []).map(t => ({
    tile: [...t.tile], floor: t.floor ?? null, toward: sortCorners((t.directions ?? []).map(d => d.toward)),
    low: (t.directions ?? []).filter(d => d.low).map(d => d.toward), wall: (t.directions ?? []).find(d => d.wall)?.wall ?? null }));
}

// A point or a direction through a view-space matrix (column-major 4 by 4, three.js's elements), in game axes: the view
// is the game's [x, z, y] (handles.js gameToView).
const through = (m, g, w) => {
  const v = [g[0], g[2], g[1], w], o = [0, 1, 2].map(r => m[r] * v[0] + m[4 + r] * v[1] + m[8 + r] * v[2] + m[12 + r] * v[3]);
  return [o[0], o[2], o[1]];
};
const SKEW = Math.cos(3 * Math.PI / 180);      // a turn more than 3 degrees off a quarter turn leaves the diagonals

/** A mark carried by a piece's move (`m`: the view-space matrix that takes the piece from where the mark was made to
 *  where it stands now): its tile there and its corners turned with it, { at, toward, skew }. A corner the move turns
 *  off the tiles' diagonals is taken to the nearest (skew: true; the game gives diagonal cover along a tile's
 *  diagonals alone). */
export function carryMark(m, home, toward, corner) {
  const at = middleOf(tileOf(through(m, home, 1), corner), corner);
  let skew = false;
  const turned = toward.map(c => {
    const d = through(m, [c[0], c[1], 0], 0), len = Math.hypot(d[0], d[1]) || 1;
    const snapped = [d[0] < 0 ? -1 : 1, d[1] < 0 ? -1 : 1];
    if ((d[0] * snapped[0] + d[1] * snapped[1]) / (len * Math.SQRT2) < SKEW) skew = true;
    return snapped;
  });
  return { at, toward: sortCorners(turned), ...(skew ? { skew: true } : {}) };
}

/** A hand state as saved (null for none), its marks and places sorted, its corners in the table's order. */
export function tidyHand(hand) {
  const marks = (hand?.marks ?? []).filter(m => m.toward?.length).map(m => ({ at: [...m.at], toward: sortCorners(m.toward),
                                                                            ...(m.from ? { from: [...m.from] } : {}) }));
  const removed = (hand?.removed ?? []).map(a => [...a]);
  if (!marks.length && !removed.length) return null;
  const byPlace = (a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b));
  return { marks: marks.sort((a, b) => byPlace(a.at, b.at)), removed: removed.sort(byPlace) };
}

/** A project record's diagonalCover read as the hand state (the marks a piece carries are worked out again: dropped
 *  here, as are records this editor can't read, which stay in `carriedOver` for the save). */
export function handFromSaved(saved) {
  const ok = m => m && Array.isArray(m.at) && m.at.length === 3 && m.at.every(Number.isFinite) && Array.isArray(m.toward) && m.toward.length
    && m.toward.every(c => Array.isArray(c) && CORNERS.some(d => sameCorner(c, d)))
    && (m.from === undefined || (Array.isArray(m.from) && m.from.length === 3 && m.from.every(Number.isFinite)));
  const marks = (saved?.marks ?? []).filter(m => ok(m) && m.by === undefined);
  const carriedOver = (saved?.marks ?? []).filter(m => !ok(m));
  const removed = (saved?.removed ?? []).filter(a => Array.isArray(a) && a.length === 3 && a.every(Number.isFinite));
  return { hand: tidyHand({ marks, removed }), carriedOver };
}

/** What the project saves (its `diagonalCover`): the hand marks and deletions, the carried marks with what carries
 *  them, and the records this editor can't read as they were; null for none. */
export function savedDiagonal(hand, carried = [], carriedOver = []) {
  const own = tidyHand(hand);
  const marks = [...(own?.marks ?? []), ...carried.map(m => ({ at: [...m.at], toward: sortCorners(m.toward),
                                                            ...(m.from ? { from: [...m.from] } : {}), by: m.by,
                                                            ...(m.moves ? { moves: true } : {}), ...(m.gone ? { gone: true } : {}) })),
                 ...carriedOver];
  const removed = own?.removed ?? [];
  return marks.length || removed.length ? { marks, removed } : null;
}

/** The marks as the view shows them: [{ key (the tile's), tile, at, toward, kind ('map' | 'changed' | 'moved' | 'added'
 *  | 'carried' | 'deleted'), from (a map mark's home tile), own (the map's mark it is or was), by }]. A deleted map
 *  mark is listed with kind 'deleted' at its home. */
export function marksNow(scene, hand, corner, carried = []) {
  if (!corner) return [];
  const own = ownMarks(scene), out = [], at = t => middleOf(t, corner);
  const removed = new Set((hand?.removed ?? []).map(a => tileKey(tileOf(a, corner))));
  const handMarks = (hand?.marks ?? []).map(m => ({ ...m, tile: tileOf(m.at, corner), home: m.from ? tileOf(m.from, corner) : null }));
  const changedFrom = new Map(handMarks.filter(m => m.home).map(m => [tileKey(m.home), m]));
  const carriedFrom = new Map(carried.filter(m => m.from).map(m => [tileKey(tileOf(m.from, corner)), m]));
  for (const o of own) {
    const k = tileKey(o.tile), h = changedFrom.get(k);
    if (removed.has(k)) out.push({ key: k, tile: o.tile, at: at(o.tile), toward: o.toward, kind: 'deleted', from: o.tile, own: o });
    else if (h) out.push({ key: tileKey(h.tile), tile: h.tile, at: at(h.tile), toward: h.toward, own: o, from: o.tile,
                           kind: tileKey(h.tile) === k ? 'changed' : 'moved' });
    else if (carriedFrom.has(k) && (carriedFrom.get(k).moves || carriedFrom.get(k).gone)) continue;       // (its piece moved
    // it, listed with the carried; or its piece is deleted, and it goes with it)
    else out.push({ key: k, tile: o.tile, at: at(o.tile), toward: o.toward, kind: 'map', from: o.tile, own: o });
  }
  for (const h of handMarks) if (!h.home) out.push({ key: tileKey(h.tile), tile: h.tile, at: at(h.tile), toward: h.toward, kind: 'added' });
  const taken = new Set(out.filter(m => m.kind !== 'deleted').map(m => m.key));
  for (const c of carried) {
    if (c.gone) continue;
    const t = tileOf(c.at, corner), k = tileKey(t);
    if (taken.has(k)) continue;          // (a mark of the project's own on the tile wins: the Build does the same)
    const home = c.from ? tileOf(c.from, corner) : null;
    out.push({ key: k, tile: t, at: at(t), toward: sortCorners(c.toward), kind: 'carried', by: c.by, ...(c.skew ? { skew: true } : {}),
               ...(home ? { from: home, own: own.find(o => tileKey(o.tile) === tileKey(home)) } : {}) });
    taken.add(k);
  }
  return out;
}

const markAt = (marks, tile) => marks.find(m => m.kind !== 'deleted' && m.key === tileKey(tile)) ?? null;
const withoutHand = (hand, test) => ({ marks: (hand?.marks ?? []).filter(m => !test(m)), removed: [...(hand?.removed ?? [])] });
const sameToward = (a, b) => a.length === b.length && a.every(c => b.some(d => sameCorner(c, d)));

/** A corner of a tile switched: on where it is off, off where it is on. A tile with no mark gets one with that corner
 *  (a deleted map mark's tile: the map's mark comes back with that corner alone); the last corner off deletes the
 *  mark. A map's mark keeps its own record where its corners come back to the map's. A carried mark switched becomes
 *  the project's own (it then follows nothing). Returns the new hand, or null when nothing changes. */
export function toggleCorner(scene, hand, corner, tile, c, carried = []) {
  const marks = marksNow(scene, hand, corner, carried), k = tileKey(tile), place = middleOf(tile, corner);
  const m = markAt(marks, tile);
  const deleted = marks.find(x => x.kind === 'deleted' && x.key === k);
  let next;
  if (!m) {
    if (deleted) {
      next = withoutHand(hand, () => false);
      next.removed = next.removed.filter(a => tileKey(tileOf(a, corner)) !== k);
      if (!sameToward([c], deleted.own.toward)) next.marks.push({ at: place, toward: [c], from: place });
    } else next = { marks: [...(hand?.marks ?? []), { at: place, toward: [c] }], removed: [...(hand?.removed ?? [])] };
    return tidyHand(next) ?? { marks: [], removed: [] };
  }
  const on = m.toward.some(d => sameCorner(d, c));
  return setCorners(scene, hand, corner, tile, on ? m.toward.filter(d => !sameCorner(d, c)) : [...m.toward, c], carried);
}

/** The corners of the mark on a tile set to `toward` (none: the mark deleted). A map's mark keeps its own record where
 *  its corners come back to the map's; a carried mark set by hand is the project's own (the wiring carries no map mark
 *  the hand names by its `from`, and a mark of the project's own on a tile wins over a copy's). Null where the tile has
 *  no mark. */
export function setCorners(scene, hand, corner, tile, toward, carried = []) {
  const marks = marksNow(scene, hand, corner, carried), m = markAt(marks, tile), k = tileKey(tile), place = middleOf(tile, corner);
  if (!m) return null;
  toward = sortCorners(toward);
  if (!toward.length) return deleteMark(scene, hand, corner, tile, carried);
  const home = m.from ? middleOf(m.from, corner) : null;
  const next = withoutHand(hand, h => tileKey(tileOf(h.at, corner)) === k);
  if (m.kind !== 'carried' && m.own && m.kind !== 'moved' && sameToward(toward, m.own.toward) && m.key === tileKey(m.from)) { /* back to the map's */ }
  else next.marks.push({ at: place, toward, ...(home ? { from: home } : {}) });
  return tidyHand(next) ?? { marks: [], removed: [] };
}

/** The corners a quarter turn takes a mark's to: `way` 1 turns them counter-clockwise in game axes (x to y), -1
 *  clockwise. */
export const turnedCorners = (toward, way) => toward.map(([x, y]) => (way > 0 ? [-y, x] : [y, -x]));

/** A new mark on a tile with one corner (the Add panel's Diagonal cover): null where the tile has a mark already (a
 *  tile has one mark); on a deleted map mark's tile, the map's mark comes back with that corner. */
export function addMark(scene, hand, corner, tile, c, carried = []) {
  const marks = marksNow(scene, hand, corner, carried);
  if (markAt(marks, tile)) return null;
  return toggleCorner(scene, hand, corner, tile, c, carried);
}

/** The corner of a tile nearest a point in it (game axes): the quarter of the tile the point falls in. */
export function cornerNear(tile, point, corner) {
  const m = middleOf(tile, corner);
  return [point[0] < m[0] ? -1 : 1, point[1] < m[1] ? -1 : 1];
}

/** A mark moved from tile `from` to tile `to`, its corners kept: null where there is no mark at `from`, or one at
 *  `to` (a tile has one mark). A map's mark moved home again is the map's own again. */
export function moveMark(scene, hand, corner, from, to, carried = []) {
  const marks = marksNow(scene, hand, corner, carried), m = markAt(marks, from);
  if (!m || tileKey(from) === tileKey(to) || markAt(marks, to)) return null;
  const k = tileKey(from), place = middleOf(to, corner), home = m.from ? middleOf(m.from, corner) : null;
  const next = withoutHand(hand, h => tileKey(tileOf(h.at, corner)) === k);
  if (m.own && tileKey(to) === tileKey(m.from) && sameToward(m.toward, m.own.toward)) { /* home: the map's own again */ }
  else next.marks.push({ at: place, toward: [...m.toward], ...(home ? { from: home } : {}) });
  return tidyHand(next) ?? { marks: [], removed: [] };
}

/** A mark deleted: a map's mark (where it stands or moved) is listed as deleted at its home, the project's own goes. */
export function deleteMark(scene, hand, corner, tile, carried = []) {
  const marks = marksNow(scene, hand, corner, carried), m = markAt(marks, tile);
  if (!m) return null;
  const k = tileKey(tile);
  const next = withoutHand(hand, h => tileKey(tileOf(h.at, corner)) === k);
  if (m.own) next.removed.push(middleOf(m.from, corner));
  return tidyHand(next) ?? { marks: [], removed: [] };
}

/** A map's mark put back as the map has it (one changed, moved, carried or deleted): null for any other. */
export function resetMark(scene, hand, corner, tile, carried = []) {
  const marks = marksNow(scene, hand, corner, carried), k = tileKey(tile);
  const m = marks.find(x => x.key === k && x.own && x.kind !== 'map');
  if (!m) return null;
  const home = tileKey(m.from);
  const next = { marks: (hand?.marks ?? []).filter(h => !(h.from && tileKey(tileOf(h.from, corner)) === home)
                                                         && tileKey(tileOf(h.at, corner)) !== k),
                 removed: (hand?.removed ?? []).filter(a => tileKey(tileOf(a, corner)) !== home) };
  return tidyHand(next) ?? { marks: [], removed: [] };
}

/** The words of a mark's kind, for its chip. */
export const KIND_WORDS = { map: 'Map\'s own', changed: 'Changed', moved: 'Moved', added: 'Added', carried: 'Follows its piece',
                            deleted: 'Deleted' };

/** What the last build wrote for a mark (the package summary's diagonalCover, build.py diagonal_record), found by its
 *  place: a line, or '' when the last build has no record of it. */
export function builtWords(built, at) {
  const r = (built?.marks ?? []).find(b => Array.isArray(b.at) && b.at.every((v, k) => Math.abs(v - at[k]) < 1));
  if (!r) return '';
  const cover = parseInt(r.cover, 16) || 0;
  const low = [0x10, 0x20, 0x40, 0x80].some(bit => cover & bit), high = [0, 1, 2, 3].some(i => cover & (1 << i) && !(cover & (0x10 << i)));
  const steps = [0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000].filter(bit => cover & bit).length;
  if (r.noFloor) return 'Last build: no floor on this tile, so no cover.';
  return `Last build: ${high && low ? 'high and low' : low ? 'low' : 'high'} cover${steps ? `, ${steps === 1 ? 'a step-out' : `${steps} step-outs`}` : ''}`
    + (r.noWall?.length ? `; no wall toward ${r.noWall.length === 1 ? 'one corner' : `${r.noWall.length} corners`} (cover against nothing).` : '.');
}
