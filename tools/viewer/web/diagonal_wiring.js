// The Diagonal cover view (Shift+C; private/plans/todo/diagonal-cover-by-hand-and-views-plan.md, section 4, design 1:
// corner dots; KNOWN-BUGS.md KB-20). Here:
// - the marks drawn (diagonal_marks.js marksNow): in the view over everything, and picked there alone; in the normal
//   view with View options' Diagonal cover, drawn and never picked. Amber: the map's own as it is; the accent colour:
//   added or changed by the project, or following its piece; pale and dashed (the view's Deleted marks): a map's mark
//   the project deleted;
// - the view on and off (setDiagonalShown): the other views step aside (and it steps aside for them: views.js
//   lightButton), and a piece selected another way leaves it (selection.js);
// - in the view, the tile under the pointer shows its four corner dots: a click on one switches that corner of the
//   tile's mark, adding a mark or deleting it with its last corner. A click inside a marked tile picks its mark (Ctrl
//   or Shift: adds it to the picked, or takes it out), and a drag from a picked mark's middle dot moves the picked
//   marks by whole tiles: a mark belongs to a tile, so Snap does not apply, and the hint says so;
// - the panel of the picked marks (#diagonalPanel): one mark's kind, tile and level, its corners as four buttons laid
//   out as the view shows them, what the last build wrote for it; Delete; Reset for a map's mark changed, moved or
//   deleted;
// - the marks that follow their pieces (carried: the plan's section 5), worked out after each edit (carriedNow): a
//   map's mark whose wall piece (export 40's `wall`) is moved goes with it, turned with it (a turn off the quarter
//   turns takes its corners to the nearest diagonals, drawn in the warning colour); one whose piece is deleted goes;
//   each copy of the piece carries one of its own, and so does each copy of a piece of another map that gives one in
//   its home map (the library's piece record 11, `foreign.diagonal`). A mark the project moved, turned or deleted by
//   hand follows nothing.
// Each edit is one undo step (gizmo.record): the edit hub's edit run draws the marks again and fills the panel.
//
// createDiagonalWiring takes what it needs of app.js as one argument object, when app.js makes it, after the other
// views (whose switches it calls): the world and the camera's helpers, the gizmo (for its undo), picking, the hints, the
// selection, box select's stop and the views' list. Its own state (the picked marks, the tile under the pointer, a drag)
// is inside it; whether the view is on and the project's marks are editor_state.js's.
import * as THREE from 'three';
import { onHub } from './edit_hub.js';
import { data, diagonalCarried, diagonalOn, effectsOn, foreignTemplates, lastBuild, lightsOn, projectDiagonal, roots,
         setDiagonalCarried, setDiagonalOnValue, setProjectDiagonal, spawnsOn, volumesOn, zonesOn } from './editor_state.js';
import { CORNERS, KIND_WORDS, TILE_SIZE, builtWords, carryMark, cornerKey, deleteMark, marksNow, middleOf, moveMark, ownMarks,
         resetMark, tileKey, tileOf, toggleCorner } from './diagonal_marks.js';
import { fromOf, isStream } from './piece_records.js';
import { targetKey } from './project.js';
import { HANDLE_PICK, gameToView } from './handles.js';
import { tileCorner } from './map_grid.js';

const MAP = 0xf0b84a, PROJECT = 0x82d5ce, DELETED = 0x6f7f88, PICKED = 0xffffff, HOVER = 0xb4f0e7, SKEWED = 0xe7c594;
const INSET = 0.06, ARROW = 40, DOT = 0.36;       // the outline's inset and the arrows' length (of a tile), the dots' place

export function createDiagonalWiring({ $, camera, flashHint, gizmo, lightButton, pickables, projector,
                                       projectsAvailable, rayAt, renderer, select, setEffectsShown, setLightsShown,
                                       setSpawnsShown, setVolumesShown, setZonesShown, stopPickBox, world }) {
  const layer = new THREE.Group();
  layer.name = 'diagonalMarks'; layer.renderOrder = 8;
  world.add(layer);
  const picked = new Set();          // the picked marks' tiles (tileKey)
  let hover = null;                  // { tile, corner (a corner's index, or -1), middle (over a mark's middle dot) }
  let drag = null;                   // { pointerId, from (a tile), to (a tile) }
  const corner = () => tileCorner();
  const marks = () => marksNow(data, projectDiagonal, corner(), diagonalCarried);
  const editable = () => projectsAvailable() && Boolean(corner());
  const showDeleted = () => Boolean($('diagonalShowDeleted')?.checked);

  // A tile's floor height (the map's saved floor there, else the floor under the pointer or the level's bottom), and
  // its points in the world (game axes): its middle, a corner's dot, a corner of its outline.
  const floors = new Map();
  function floorsNow() {
    floors.clear();
    for (const f of data?.tactical?.floorTiles ?? []) floors.set(tileKey(f.tile), f.location[2]);
  }
  const floorOf = (tile, own = null) => own?.floor ?? floors.get(tileKey(tile)) ?? (hover && tileKey(hover.tile) === tileKey(tile) ? hover.z : null)
    ?? corner()[2] + TILE_SIZE[2] * tile[2] + 1;
  const at = (tile, fx, fy, z) => gameToView([corner()[0] + TILE_SIZE[0] * (tile[0] + fx), corner()[1] + TILE_SIZE[1] * (tile[1] + fy), z + 3]);
  const dotAt = (tile, c, z) => at(tile, 0.5 + c[0] * DOT, 0.5 + c[1] * DOT, z);

  // ---------------------------------------------------------------- drawing
  function clear() {
    for (const o of [...layer.children]) { layer.remove(o); o.geometry?.dispose(); o.material?.dispose(); }
  }
  function lines(points, color, dashed = false) {
    if (!points.length) return;
    const g = new THREE.BufferGeometry().setFromPoints(points);
    const m = dashed ? new THREE.LineDashedMaterial({ color, dashSize: 8, gapSize: 6, depthTest: false, transparent: true })
      : new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.95 });
    const seg = new THREE.LineSegments(g, m);
    if (dashed) seg.computeLineDistances();
    seg.renderOrder = 8; seg.raycast = () => {};
    layer.add(seg);
  }
  function outline(out, tile, z, inset = INSET) {
    const p = [[inset, inset], [1 - inset, inset], [1 - inset, 1 - inset], [inset, 1 - inset]].map(([x, y]) => at(tile, x, y, z));
    for (let i = 0; i < 4; i++) out.push(p[i], p[(i + 1) % 4]);
  }
  function arrows(out, tile, z, toward) {
    const c = at(tile, 0.5, 0.5, z);
    for (const d of toward) {
      const u = new THREE.Vector3(d[0], 0, d[1]).normalize(), tip = c.clone().addScaledVector(u, ARROW);
      out.push(c, tip);
      const side = new THREE.Vector3(-u.z, 0, u.x);
      for (const s of [-1, 1]) out.push(tip, tip.clone().addScaledVector(u, -12).addScaledVector(side, s * 8));
    }
  }
  function disc(tile, c, z, color, filled, size) {
    const centre = c ? dotAt(tile, c, z) : at(tile, 0.5, 0.5, z);
    // (its size a share of its distance, so a dot reads the same near and far: about `size` pixels)
    const radius = Math.max(3, camera.position.distanceTo(centre) * size * 0.0016);
    const g = filled ? new THREE.CircleGeometry(radius, 18).rotateX(-Math.PI / 2) : new THREE.RingGeometry(radius * 0.7, radius, 18).rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true, side: THREE.DoubleSide }));
    mesh.position.copy(centre); mesh.renderOrder = 9; mesh.raycast = () => {};
    layer.add(mesh);
  }
  function draw() {
    clear();
    if (!data || !corner()) return;
    const shown = diagonalOn || $('diagonalCover')?.checked;
    if (!shown) return;
    floorsNow();
    const all = marks(), out = { map: [], project: [], deleted: [], picked: [], skew: [] };
    const moving = drag && tileKey(drag.from) !== tileKey(drag.to) ? [drag.to[0] - drag.from[0], drag.to[1] - drag.from[1], drag.to[2] - drag.from[2]] : null;
    for (const m of all) {
      if (m.kind === 'deleted' && !(diagonalOn && showDeleted())) continue;
      const z = floorOf(m.tile, m.own), key = diagonalOn && picked.has(m.key) ? 'picked' : m.kind === 'map' ? 'map'
        : m.kind === 'deleted' ? 'deleted' : m.skew ? 'skew' : 'project';
      outline(out[key], m.tile, z); arrows(out[key], m.tile, z, m.toward);
      if (moving && picked.has(m.key)) {
        const to = [m.tile[0] + moving[0], m.tile[1] + moving[1], m.tile[2] + moving[2]];
        outline(out.project, to, floorOf(to)); arrows(out.project, to, floorOf(to), m.toward);
      }
    }
    lines(out.map, MAP); lines(out.project, PROJECT); lines(out.deleted, DELETED, true); lines(out.picked, PICKED); lines(out.skew, SKEWED);
    if (!diagonalOn || drag) return;
    // the tile under the pointer: its outline and four corner dots (filled where its mark has that corner), and a mark's
    // middle dot, which picks it and moves it
    if (hover) {
      const z = floorOf(hover.tile), m = all.find(x => x.kind !== 'deleted' && x.key === tileKey(hover.tile));
      const edge = [];
      outline(edge, hover.tile, z, 0);
      lines(edge, HOVER);
      CORNERS.forEach((c, i) => disc(hover.tile, c, z, i === hover.corner ? PICKED : PROJECT,
                                     Boolean(m?.toward.some(d => cornerKey(d) === cornerKey(c))), i === hover.corner ? 9 : 7));
      if (m) disc(hover.tile, null, z, hover.middle ? PICKED : HOVER, true, hover.middle ? 8 : 6);
    }
    for (const m of all) if (picked.has(m.key) && m.kind !== 'deleted' && (!hover || tileKey(hover.tile) !== m.key)) disc(m.tile, null, floorOf(m.tile, m.own), PICKED, true, 6);
  }

  // ---------------------------------------------------------------- the tile under the pointer
  // The tile a screen point falls on: along the pointer's ray, the first drawn and uncut surface that is one of the
  // map's saved floors there (a surface within 16 units of the floor of its tile), else the first that faces up (a
  // floor the project makes), else the ground's plane; null off the grid.
  function tileAt(clientX, clientY) {
    const c = corner(), dims = data?.tileGrid?.dimensions;
    if (!c || !dims) return null;
    if (!floors.size) floorsNow();
    const inGrid = t => (t.tile.every((v, k) => v >= 0 && v < dims[k]) ? t : null);
    const ray = rayAt(clientX, clientY), normal = new THREE.Vector3();
    let up = null;
    for (const h of ray.intersectObjects(pickables)) {
      const root = roots.get(h.object.userData.objectId);
      if (!root?.visible || !(root.userData.clippingPlanes || []).every(p => p.distanceToPoint(h.point) >= -0.01)) continue;
      const point = [h.point.x, h.point.z, h.point.y], tile = tileOf([point[0], point[1], point[2] + 4], c);
      const floor = floors.get(tileKey(tile));
      if (floor !== undefined && Math.abs(floor - point[2]) < 16) return inGrid({ tile, z: floor });
      if (!up && h.face && normal.copy(h.face.normal).transformDirection(h.object.matrixWorld).y > 0.7) up = { tile, z: point[2] };
    }
    if (up) return inGrid(up);
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -(data.tileGrid.origin?.[2] ?? c[2] + 1));
    const v = ray.ray.intersectPlane(plane, new THREE.Vector3());
    return v ? inGrid({ tile: tileOf([v.x, v.z, v.y + 4], c), z: v.y }) : null;
  }
  // What is under a screen point in the view: the tile, the corner dot within the pick distance, a mark's middle dot.
  function hoverAt(clientX, clientY) {
    const t = tileAt(clientX, clientY);
    if (!t) return null;
    hover = { ...(hover ?? {}), tile: t.tile, z: t.z };        // (floorOf reads the tile's height from it)
    const z = floorOf(t.tile), screen = projector();
    const near = p => { const s = screen(p); return s ? Math.hypot(s[0] - clientX, s[1] - clientY) : Infinity; };
    let best = -1, bestD = HANDLE_PICK;
    CORNERS.forEach((c, i) => { const d = near(dotAt(t.tile, c, z)); if (d < bestD) { best = i; bestD = d; } });
    const m = marks().find(x => x.kind !== 'deleted' && x.key === tileKey(t.tile));
    const middle = Boolean(m) && best < 0 && near(at(t.tile, 0.5, 0.5, z)) < HANDLE_PICK;
    return { tile: t.tile, z: t.z, corner: best, middle };
  }
  function hoverDiagonal(e) {
    if (!diagonalOn || drag) return;
    const was = JSON.stringify(hover);
    hover = hoverAt(e.clientX, e.clientY);
    if (JSON.stringify(hover) !== was) { draw(); hint(); }
  }
  function hint() {
    if (!diagonalOn) return;
    const words = !editable() ? 'Diagonal cover view: marks are edited on a map opened from the map browser'
      : drag ? 'Drag: the marks move by whole tiles (a mark belongs to a tile, whatever Snap says) · Esc puts them back'
      : hover?.corner >= 0 ? `Click: cover toward this corner of the tile (${glyph(hover.tile, CORNERS[hover.corner])}), or none that way again`
      : hover?.middle ? 'Click: pick this mark (Ctrl or Shift: add it) · drag: move it'
      : 'Diagonal cover view: click a corner dot of a tile to give it cover that way · Shift+C leaves it';
    $('dragHint').textContent = words; $('dragHint').hidden = false;
  }

  // A corner's arrow as the view shows it: the way its dot lies from the tile's middle on the screen.
  function glyph(tile, c) {
    const screen = projector(), z = floorOf(tile), m = screen(at(tile, 0.5, 0.5, z)), d = screen(dotAt(tile, c, z));
    const dx = m && d ? d[0] - m[0] : c[0], dy = m && d ? d[1] - m[1] : -c[1];
    return dy < 0 ? (dx < 0 ? '↖' : '↗') : (dx < 0 ? '↙' : '↘');
  }

  // ---------------------------------------------------------------- edits
  // One undo step: the project's marks set to `next` (an edit of diagonal_marks.js), and back.
  function commit(next, words, pickAfter = null) {
    if (!next) return false;
    const before = projectDiagonal, pickedBefore = [...picked], tidy = next.marks?.length || next.removed?.length ? next : null;
    gizmo.record({ redo: () => { setProjectDiagonal(tidy); repick(pickAfter ?? pickedBefore); },
                   undo: () => { setProjectDiagonal(before); repick(pickedBefore); } });
    if (words) flashHint(words);
    return true;
  }
  function repick(keys) {
    picked.clear();
    const now = new Set(marks().map(m => m.key));
    for (const k of keys) if (now.has(k)) picked.add(k);
    draw(); panel();
  }
  function switchCorner(tile, i) {
    if (!editable()) { hint(); return; }
    const next = toggleCorner(data, projectDiagonal, corner(), tile, CORNERS[i], diagonalCarried);
    commit(next, null, [tileKey(tile)]);       // (its mark picked alone)
  }
  // (a mark a copy carries goes with the copy: it is turned by hand, but not moved or deleted on its own)
  const withCopy = m => m.kind === 'carried' && !m.from;
  function deletePicked() {
    if (!editable() || !picked.size) return false;
    let next = projectDiagonal, count = 0;
    const list = marks().filter(m => picked.has(m.key));
    for (const m of list) {
      if (withCopy(m)) continue;
      const r = deleteMark(data, next, corner(), m.tile, diagonalCarried);
      if (r) { next = r; count++; }
    }
    if (!count) {
      if (list.some(withCopy)) flashHint('A mark a copy carries goes with the copy: delete the copy, or turn the mark\'s corners off');
      return list.length > 0;
    }
    commit(next, `${count === 1 ? 'A mark' : `${count} marks`} deleted · Ctrl+Z brings ${count === 1 ? 'it' : 'them'} back`, []);
    return true;
  }
  // the picked marks of the map put back as the map has them, and picked at home
  function resetPicked() {
    if (!editable()) return;
    let next = projectDiagonal;
    const homes = [];
    for (const m of marks().filter(x => picked.has(x.key))) {
      const r = resetMark(data, next, corner(), m.tile, diagonalCarried);
      if (r) { next = r; homes.push(tileKey(m.from)); }
    }
    if (homes.length) commit(next, 'Put back as the map has it', homes);
  }
  // the picked marks moved by `delta` tiles, as one step; refused whole where one would land on a tile with a mark
  function movePicked(delta) {
    const from = [...picked].map(k => k.split(',').map(Number));
    // (the marks furthest along the move go first, so none lands on one that has not moved yet)
    from.sort((a, b) => (b[0] - a[0]) * delta[0] + (b[1] - a[1]) * delta[1] + (b[2] - a[2]) * delta[2]);
    let next = projectDiagonal;
    const keys = [];
    for (const t of from) {
      const to = [t[0] + delta[0], t[1] + delta[1], t[2] + delta[2]];
      const moved = moveMark(data, next, corner(), t, to, diagonalCarried);
      if (!moved) { flashHint('Not moved: a tile has one mark, and a mark would land on another'); return; }
      next = moved; keys.push(tileKey(to));
    }
    commit(next, `${from.length === 1 ? 'A mark' : `${from.length} marks`} moved by whole tiles`, keys);
  }

  // ---------------------------------------------------------------- pointer
  // A click in the view: a corner dot switches that corner; inside a marked tile picks its mark (Ctrl or Shift: adds it,
  // or takes it out again); elsewhere lets the picked go.
  function diagonalClick(e) {
    const h = hoverAt(e.clientX, e.clientY);
    hover = h;
    if (h && h.corner >= 0) { switchCorner(h.tile, h.corner); return; }
    const m = h && marks().find(x => (x.kind !== 'deleted' || showDeleted()) && x.key === tileKey(h.tile));
    const add = e.ctrlKey || e.shiftKey || e.metaKey;
    if (!m) { if (!add) { picked.clear(); draw(); panel(); } return; }
    if (add) { if (picked.has(m.key)) picked.delete(m.key); else picked.add(m.key); }
    else { picked.clear(); picked.add(m.key); }
    draw(); panel(); hint();
  }
  // A press on a mark's middle dot starts its drag (the picked marks move with it; one not picked is picked alone).
  function startDiagonalDrag(e) {
    if (!diagonalOn || e.button !== 0 || !editable()) return false;
    const h = hoverAt(e.clientX, e.clientY);
    if (!h?.middle) return false;
    const k = tileKey(h.tile);
    if (!picked.has(k)) { picked.clear(); picked.add(k); }
    if (marks().some(m => picked.has(m.key) && withCopy(m))) {
      flashHint('A mark a copy carries moves with the copy: move the copy');
      draw(); panel();
      return true;
    }
    drag = { pointerId: e.pointerId, from: h.tile, to: h.tile };
    try { renderer.domElement.setPointerCapture(e.pointerId); } catch { /* not a pointer that can be captured */ }
    draw(); panel(); hint();
    return true;
  }
  function moveDiagonalDrag(e) {
    const t = tileAt(e.clientX, e.clientY);
    if (!t || tileKey(t.tile) === tileKey(drag.to)) return;
    drag.to = t.tile; draw();
  }
  function endDiagonalDrag(apply) {
    if (!drag) return;
    try { renderer.domElement.releasePointerCapture(drag.pointerId); } catch { /* released */ }
    const delta = [0, 1, 2].map(k => drag.to[k] - drag.from[k]);
    drag = null;
    if (apply && delta.some(Boolean)) movePicked(delta); else draw();
    hint();
  }
  // The view's keys (navigation.js asks first): Delete deletes the picked marks, Escape lets them go (or a drag ends).
  function diagonalKey(key) {
    if (!diagonalOn) return false;
    if (drag) { if (key === 'escape') endDiagonalDrag(false); return true; }
    if (key === 'delete' && picked.size) return deletePicked();
    if (key === 'escape' && picked.size) { picked.clear(); draw(); panel(); return true; }
    return false;
  }

  // ---------------------------------------------------------------- the view on and off
  function setDiagonalShown(on) {
    on = Boolean(on) && Boolean(data) && Boolean(corner());
    if (on === diagonalOn) { draw(); panel(); return; }
    if (on) {
      if (spawnsOn) setSpawnsShown(false);
      if (volumesOn) setVolumesShown(false);
      if (lightsOn) setLightsShown(false);
      if (zonesOn) setZonesShown(false);
      if (effectsOn) setEffectsShown(false);
      stopPickBox(); select(null);
    } else { picked.clear(); hover = null; endDiagonalDrag(false); $('dragHint').hidden = true; }
    setDiagonalOnValue(on);
    lightButton(); draw(); panel();
    if (on) { flashHint('Diagonal cover view: click a corner dot of a tile to give it cover that way · Shift+C leaves it'); hint(); }
  }

  // ---------------------------------------------------------------- the panel
  const els = { panel: $('diagonalPanel'), chip: $('diagonalChip'), where: $('diagonalWhere'), corners: $('diagonalCorners'),
                built: $('diagonalBuilt'), del: $('diagonalDelete'), reset: $('diagonalReset'), title: $('diagonalTitle') };
  function panel() {
    const all = marks(), list = all.filter(m => picked.has(m.key));
    els.panel.hidden = !diagonalOn || !list.length;
    if (els.panel.hidden) return;
    const one = list.length === 1 ? list[0] : null;
    els.title.textContent = one ? 'Diagonal cover' : `${list.length} diagonal cover marks`;
    els.chip.hidden = !one; els.chip.textContent = one ? KIND_WORDS[one.kind] : '';
    els.chip.classList.toggle('warn', one?.kind === 'deleted');
    els.where.textContent = one ? `Tile ${one.tile[0]}, ${one.tile[1]} · level ${one.tile[2]}`
      + (one.from && one.kind === 'moved' ? ` · the map's mark of tile ${one.from[0]}, ${one.from[1]}` : '')
      + (one.kind === 'carried' ? ` · follows ${String(one.by ?? '').split('.').pop()}` : '') : 'Delete deletes them all; a drag of one moves them all.';
    els.corners.hidden = !one || one.kind === 'deleted';
    if (one && one.kind !== 'deleted') layoutCorners(one);
    const built = one && one.kind !== 'deleted' ? builtWords(lastBuild?.package?.diagonalCover, middleOf(one.tile, corner())) : '';
    els.built.textContent = built; els.built.hidden = !built;
    els.del.disabled = !editable() || list.every(m => m.kind === 'deleted' || withCopy(m));
    els.reset.hidden = !list.some(m => m.own && m.kind !== 'map');
    els.reset.disabled = !editable();
  }
  // The four corner buttons laid out as the view shows them: each in the quarter of the panel its corner falls in on
  // the screen, with its arrow (a camera looking along a tile's side keeps the table's order).
  function layoutCorners(m) {
    const screen = projector(), z = floorOf(m.tile, m.own), c = screen(at(m.tile, 0.5, 0.5, z));
    const placed = CORNERS.map((d, i) => {
      const s = c && screen(dotAt(m.tile, d, z));
      return { d, i, dx: s ? s[0] - c[0] : d[0], dy: s ? s[1] - c[1] : -d[1] };
    });
    const slot = p => (p.dy < 0 ? 0 : 2) + (p.dx < 0 ? 0 : 1);
    const order = new Set(placed.map(slot)).size === 4 ? [...placed].sort((a, b) => slot(a) - slot(b)) : placed;
    const glyph = ['↖', '↗', '↙', '↘'];
    els.corners.replaceChildren(...order.map((p, n) => {
      const b = document.createElement('button');
      b.type = 'button';
      const on = m.toward.some(d => cornerKey(d) === cornerKey(p.d));
      b.textContent = glyph[order === placed ? n : slot(p)];
      b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
      b.title = `Cover toward this corner of the tile (game axes ${p.d[0] > 0 ? '+' : '-'}X ${p.d[1] > 0 ? '+' : '-'}Y): ${on ? 'on' : 'off'}`;
      b.disabled = !editable();
      b.onclick = () => switchCorner(m.tile, p.i);
      return b;
    }));
  }
  els.del.onclick = () => deletePicked();
  els.reset.onclick = () => resetPicked();
  $('diagonalShowDeleted').onchange = e => { draw(); panel(); e.target.blur(); };

  // The marks that follow their pieces, as the pieces stand now (the plan's section 5): [{ at, toward, from?, by,
  // moves?, gone?, skew? }] (diagonal_marks.js marksNow and savedDiagonal read them).
  function carriedNow() {
    const c = corner();
    if (!c || !data || data.preview) return [];
    const hand = projectDiagonal, homes = new Set([...(hand?.marks ?? []).filter(m => m.from).map(m => m.from),
                                                   ...(hand?.removed ?? [])].map(a => tileKey(tileOf(a, c))));
    // (a tile the project marks by hand keeps its own mark: a copy's carried mark there gives way, as in the Build)
    const handTiles = new Set((hand?.marks ?? []).map(m => tileKey(tileOf(m.at, c))));
    // each of the map's pieces by its actor (its first root), and the copies of each (a copy's root per copy)
    const originals = new Map(), copies = new Map(), foreign = new Map();
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (!o || isStream(o)) continue;
      if (!o.added) { if (!originals.has(o.actor)) originals.set(o.actor, r); continue; }
      if (o.foreign && o.foreign.diagonal?.length && !r.userData.deleted && !foreign.has(o.actor)) { foreign.set(o.actor, r); continue; }
      if (!o.added.from || o.foreign || r.userData.deleted) continue;
      const list = copies.get(o.added.from.actor) ?? [];
      if (!list.some(x => x.userData.source.actor === o.actor)) list.push(r);
      copies.set(o.added.from.actor, list);
    }
    const out = [], base = r => new THREE.Matrix4().fromArray(r.userData.source.matrix);
    for (const own of ownMarks(data)) {
      const home = middleOf(own.tile, c), piece = own.wall && originals.get(own.wall);
      if (!piece || homes.has(tileKey(own.tile))) continue;
      if (piece.userData.deleted) { out.push({ at: home, toward: own.toward, from: home, by: own.wall, gone: true }); continue; }
      if (piece.userData.edit) out.push({ ...carryMark(piece.userData.edit.elements, home, own.toward, c), from: home, by: own.wall, moves: true });
      const back = base(piece).invert();
      for (const copy of copies.get(own.wall) ?? []) {
        const m = carryMark(copy.matrix.clone().multiply(back).elements, home, own.toward, c);
        if (!handTiles.has(tileKey(tileOf(m.at, c)))) out.push({ ...m, by: copy.userData.source.actor });
      }
    }
    // a piece of another map brings the marks it gives at home: from its template's place to where it stands
    for (const [actor, r] of foreign) {
      const o = r.userData.source, template = foreignTemplates.get(`${targetKey(fromOf(o))}|${o.component}`);
      if (!template) continue;
      const move = r.matrix.clone().multiply(new THREE.Matrix4().fromArray(template.matrix).invert()).elements;
      for (const d of o.foreign.diagonal.filter(x => x.wall === fromOf(o).actor)) {
        const m = carryMark(move, d.at, d.toward, c);
        if (!handTiles.has(tileKey(tileOf(m.at, c)))) out.push({ ...m, by: actor });
      }
    }
    return out;
  }
  // After an edit, an undo or a change of the scene's pieces: the marks that follow their pieces worked out again, the
  // marks drawn, the picked ones that are gone let go, the panel.
  function refresh() {
    setDiagonalCarried(carriedNow());
    const now = new Set(marks().map(m => m.key));
    for (const k of [...picked]) if (!now.has(k)) picked.delete(k);
    draw(); panel();
  }
  onHub('edit', 'diagonal', refresh);
  onHub('scene', 'diagonal', refresh);

  return { diagonalClick, diagonalKey, drawDiagonal: draw, endDiagonalDrag, hoverDiagonal, moveDiagonalDrag,
           pickedMarks: () => [...picked], refreshDiagonal: refresh, setDiagonalShown, startDiagonalDrag,
           diagonalDrag: () => drag };
}
