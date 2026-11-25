// The Diagonal cover view (Shift+C; private/plans/done/diagonal-cover-by-hand-and-views-plan.md, section 4;
// KNOWN-BUGS.md KB-20). It behaves as the Landing zones and Spawns views do (23 November 2026). Here:
// - the marks drawn (diagonal_marks.js marksNow): in the view over everything, and picked there alone; in the normal
//   view with View options' Diagonal cover, drawn and never picked. A half-cover corner's arrow is drawn half as long
//   as a full one's. Amber: the map's own as it is; the accent colour:
//   added or changed by the project, or following its piece; pale and dashed (the view's Deleted marks): a map's mark
//   the project deleted;
// - the view on and off (setDiagonalShown): the other views step aside (and it steps aside for them: views.js
//   lightButton), and a piece selected another way leaves it (selection.js);
// - in the view, a click on a mark picks it (Ctrl or Shift: adds it to the picked, or takes it out) and a click beside
//   the marks lets the picked go. The picked mark shows its four corner dots: a click on one switches that corner
//   (the last one off deletes the mark), and [ and ] turn its corners a quarter. The picked marks move with a gizmo by
//   whole tiles across and levels up: a mark belongs to a tile, so Snap does not apply, and the hint says so;
// - a new mark comes from the Add panel (its Diagonal cover entry, diagonalEntries): the view comes on, a ghost mark
//   follows the pointer over the tiles with its corner toward the quarter of the tile the pointer is in, and a click
//   puts it down (startDiagonalPlacing, placeDiagonal);
// - the panel of the picked marks (#diagonalPanel): one mark's kind, tile and level, its corners as four buttons laid
//   out as the view shows them, Cover (full or half, for all the picked marks' corners), what the last build wrote for
//   it; Delete; Reset for a map's mark changed, moved or deleted;
// - a mark on a tile one of the map's streamed levels reworks at the battle's start (Long War's patch levels, a
//   mission's own: diagonal_marks.js reworkAreas, export 41; KNOWN-BUGS.md KB-22) gets no cover in the game: a yellow
//   warning triangle stands on its tile wherever the marks are drawn; picked in the view, the areas that take it are
//   drawn dashed with their level's name, the triangle tells why on hover, and the panel says so;
// - the marks that follow their pieces (carried: the plan's section 5), worked out after each edit (carriedNow): a
//   map's mark whose wall piece (export 40's `wall`) is moved goes with it, turned with it (a turn off the quarter
//   turns takes its corners to the nearest diagonals, drawn in the warning colour); one whose piece is deleted goes;
//   each copy of the piece carries one of its own, and so does each copy of a piece of another map that gives one in
//   its home map (the library's piece record 12, `foreign.diagonal`). A mark the project moved, turned or deleted by
//   hand follows nothing.
// Each edit is one undo step (gizmo.record): the edit hub's edit run draws the marks again and fills the panel.
//
// createDiagonalWiring takes what it needs of app.js as one argument object, when app.js makes it, after the other
// views (whose switches it calls): the world, the camera and its controls, the camera's helpers, the gizmo (for its
// undo), the pickable pieces, the hints, the selection, box select's stop, the Add panel and the views' list. Its own
// state (the picked marks, the tile under the pointer, the placing, its gizmo's drag) is inside it; whether the view is
// on and the project's marks are editor_state.js's.
import * as THREE from 'three';
import { onHub } from './edit_hub.js';
import { cleared, data, diagonalCarried, diagonalOn, effectsOn, foreignTemplates, lastBuild, lightsOn, missionMoves, pieces,
         projectDiagonal, projectMissions, roots, setDiagonalCarried, setDiagonalOnValue, setProjectDiagonal, spawnsOn,
         volumesOn, zonesOn } from './editor_state.js';
import { CORNERS, KIND_WORDS, TILE_SIZE, addMark, areaWords, builtWords, carryMark, cornerKey, cornerNear, deleteMark,
         marksNow, heightOf, middleOf, moveMark, ownMarks, resetMark, reworkAreas, reworkWords, reworkedBy, setCorners,
         setHalf, tileKey, tileOf, toggleCorner, turnedCorners } from './diagonal_marks.js';
import { fromOf, isStream } from './piece_records.js';
import { ADDED_KINDS } from './missions.js';
import { spawnKey } from './spawns_view.js';
import { targetKey } from './project.js';
import { HANDLE_PICK, gameToView } from './handles.js';
import { tileCorner } from './map_grid.js';
import { createViewGizmo } from './view_gizmo.js';

const MAP = 0xf0b84a, PROJECT = 0x82d5ce, DELETED = 0x6f7f88, PICKED = 0xffffff, HOVER = 0xb4f0e7, SKEWED = 0xe7c594;
const INSET = 0.06, ARROW = 40, DOT = 0.42;       // the outline's inset and the arrows' length (of a tile), the dots' place
// a mark the battle's rework takes (KB-22): its warning triangle (its size on the screen, its place from the tile's
// middle toward a corner the mark has no arrow to, the pointer's reach for its tooltip) and the areas' labels
const WARN = 0xf2c94c, WARN_PX = 20, WARN_AT = 0.24, AREA_LABEL_PX = 18, TIP_PX = 13;
let warnTexture = null;
function warnMap() {
  if (warnTexture) return warnTexture;
  const canvas = Object.assign(document.createElement('canvas'), { width: 64, height: 64 }), c = canvas.getContext('2d');
  c.lineJoin = 'round'; c.lineCap = 'round';
  c.beginPath(); c.moveTo(32, 5); c.lineTo(60, 56); c.lineTo(4, 56); c.closePath();
  c.fillStyle = '#f2c94c'; c.fill(); c.strokeStyle = '#2a2110'; c.lineWidth = 4; c.stroke();
  c.lineWidth = 6.5; c.beginPath(); c.moveTo(32, 23); c.lineTo(32, 39); c.moveTo(32, 48); c.lineTo(32, 48.5); c.stroke();
  warnTexture = new THREE.CanvasTexture(canvas);
  return warnTexture;
}

export function createDiagonalWiring({ $, camera, controls, flashHint, gizmo, lightButton, pickables, projector,
                                       projectsAvailable, rayAt, renderer, restingHint, select, setEffectsShown,
                                       setLightsShown, setSpawnsShown, setVolumesShown, setZonesShown, stopPickBox,
                                       world }) {
  const layer = new THREE.Group();
  layer.name = 'diagonalMarks'; layer.renderOrder = 8;
  world.add(layer);
  const picked = new Set();          // the picked marks' tiles (tileKey)
  let hover = null;                  // { tile, z, point, corner (the picked mark's corner dot under it, or -1) }
  let adding = false;                // a new mark asked for from the Add panel and not put down yet
  let drag = null;                   // the gizmo's drag, as it moves: { from (a tile), to (a tile) }
  let badges = [];                   // the warning triangles drawn now (KB-22): { key, point, hits }
  const corner = () => tileCorner();
  const marks = () => marksNow(data, projectDiagonal, corner(), diagonalCarried);
  const editable = () => projectsAvailable() && Boolean(corner());
  const showDeleted = () => Boolean($('diagonalShowDeleted')?.checked);
  const onePicked = () => { const list = marks().filter(m => picked.has(m.key) && m.kind !== 'deleted'); return list.length === 1 ? list[0] : null; };
  // (a mark a copy carries goes with the copy: it is turned by hand, but not moved or deleted on its own)
  const withCopy = m => m.kind === 'carried' && !m.from;

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
    for (const o of [...layer.children]) {
      layer.remove(o); o.geometry?.dispose();
      if (o.userData.ownMap) o.material?.map?.dispose();
      o.material?.dispose();
    }
    badges = [];
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
  function arrows(out, tile, z, toward, low = []) {
    const c = at(tile, 0.5, 0.5, z);
    for (const d of toward) {
      const half = low.some(x => cornerKey(x) === cornerKey(d));
      const u = new THREE.Vector3(d[0], 0, d[1]).normalize(), tip = c.clone().addScaledVector(u, half ? ARROW / 2 : ARROW);
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
    if (!diagonalOn && renderer.domElement.title) renderer.domElement.title = '';
    if (!shown) return;
    floorsNow();
    const all = marks(), out = { map: [], project: [], deleted: [], picked: [], skew: [], hover: [] };
    const moving = drag && tileKey(drag.from) !== tileKey(drag.to) ? [0, 1, 2].map(k => drag.to[k] - drag.from[k]) : null;
    const over = diagonalOn && !adding && hover ? tileKey(hover.tile) : null;
    for (const m of all) {
      if (m.kind === 'deleted' && !(diagonalOn && showDeleted())) continue;
      const z = floorOf(m.tile, m.own), key = diagonalOn && picked.has(m.key) ? 'picked' : m.kind === 'map' ? 'map'
        : m.kind === 'deleted' ? 'deleted' : m.skew ? 'skew' : 'project';
      outline(out[key], m.tile, z); arrows(out[key], m.tile, z, m.toward, m.low);
      if (over === m.key && key !== 'picked') outline(out.hover, m.tile, z, 0);     // (the mark a click would pick)
      if (moving && picked.has(m.key)) {
        const to = [m.tile[0] + moving[0], m.tile[1] + moving[1], m.tile[2] + moving[2]];
        outline(out.project, to, floorOf(to)); arrows(out.project, to, floorOf(to), m.toward, m.low);
      }
    }
    // the ghost of a mark being added: on the tile under the pointer, toward the corner nearest it
    if (diagonalOn && adding && hover) {
      const z = floorOf(hover.tile), c = cornerNear(hover.tile, hover.point, corner());
      outline(out.hover, hover.tile, z, 0); outline(out.project, hover.tile, z); arrows(out.project, hover.tile, z, [c]);
    }
    lines(out.map, MAP); lines(out.project, PROJECT); lines(out.deleted, DELETED, true); lines(out.picked, PICKED); lines(out.skew, SKEWED);
    lines(out.hover, HOVER);
    reworked(all);
    // (a triangle's tooltip goes with its mark's pick)
    if (renderer.domElement.title && !badges.some(b => diagonalOn && picked.has(b.key))) renderer.domElement.title = '';
    // the picked mark's four corner dots (filled where it has that corner): a click on one switches it
    const one = diagonalOn && !adding && !drag ? onePicked() : null;
    if (one && editable()) {
      const z = floorOf(one.tile, one.own);
      CORNERS.forEach((c, i) => disc(one.tile, c, z, hover?.corner === i ? PICKED : PROJECT,
                                     one.toward.some(d => cornerKey(d) === cornerKey(c)), hover?.corner === i ? 9 : 7));
    }
  }

  // ---------------------------------------------------------------- the battle's rework (KB-22)
  // The marks the map's streamed levels rework at the battle's start: a warning triangle on each one's tile, drawn
  // wherever the marks are (badges keeps where each stands, for the tooltip); picked in the view, the areas that take
  // the picked marks dashed at their floor's height, clipped to the grid, each level's name at the corner of its areas
  // lowest on the screen.
  // (the variant's missions' streams, a mission object's volume where the project's move puts it)
  const areas = () => reworkAreas(data, corner(), { cleared, missions: projectMissions,
                                                    moved: (stream, actor) => missionMoves.get(spawnKey(stream, actor)),
                                                    label: kind => ADDED_KINDS[kind]?.label ?? kind });
  // a sprite's scale for `px` pixels high whatever its distance (sizeAttenuation off: scale times the distance)
  const screenScale = px => px / Math.max(1, renderer.domElement.clientHeight) * 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov ?? 50) / 2);
  function sprite(material, px, point, centre = [0.5, 0.5]) {
    const s = new THREE.Sprite(material), image = material.map.image;
    s.scale.set(screenScale(px) * image.width / image.height, screenScale(px), 1);
    s.center.set(centre[0], centre[1]); s.position.copy(point); s.renderOrder = 10; s.raycast = () => {};
    layer.add(s);
    return s;
  }
  function badgeAt(m, z) {
    const free = CORNERS.find(c => !m.toward.some(d => cornerKey(d) === cornerKey(c))) ?? CORNERS[0];
    return at(m.tile, 0.5 + free[0] * WARN_AT, 0.5 + free[1] * WARN_AT, z);
  }
  function areaLabel(text, point) {
    const font = '600 26px system-ui, Segoe UI, sans-serif', probe = document.createElement('canvas').getContext('2d');
    probe.font = font;
    const w = Math.ceil(probe.measureText(text).width) + 24, canvas = Object.assign(document.createElement('canvas'), { width: w, height: 40 });
    const c = canvas.getContext('2d');
    c.fillStyle = 'rgba(28, 26, 20, 0.88)'; c.beginPath(); c.roundRect(1, 1, w - 2, 38, 7); c.fill();
    c.strokeStyle = '#6f5a35'; c.lineWidth = 2; c.stroke();
    c.fillStyle = '#f2c94c'; c.font = font; c.textBaseline = 'middle'; c.fillText(text, 12, 21);
    const map = new THREE.CanvasTexture(canvas);
    const s = sprite(new THREE.SpriteMaterial({ map, depthTest: false, transparent: true, sizeAttenuation: false }),
                     AREA_LABEL_PX, point, [0.5, -0.25]);
    s.userData.ownMap = true;
  }
  function reworked(all) {
    const list = areas();
    if (!list.length) return;
    const material = new THREE.SpriteMaterial({ map: warnMap(), depthTest: false, transparent: true, sizeAttenuation: false });
    const takes = [];
    for (const m of all) {
      if (m.kind === 'deleted') continue;
      const hits = reworkedBy(list, m.tile);
      if (!hits.length) continue;
      const z = floorOf(m.tile, m.own), point = badgeAt(m, z);
      sprite(material, WARN_PX, point).userData.warn = m.key;
      badges.push({ key: m.key, point, hits });
      if (diagonalOn && picked.has(m.key)) takes.push({ hits, z });
    }
    if (!badges.length) material.dispose();
    // the areas that take the picked marks, each once, at the floor of the first picked mark it takes
    const dims = data.tileGrid?.dimensions ?? [Infinity, Infinity, Infinity], seen = new Set(), dashed = [], named = new Map();
    const screen = projector();
    for (const { hits, z } of takes) {
      for (const a of hits) {
        const key = `${a.stream}|${a.actor}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const x0 = Math.max(0, a.lo[0]), y0 = Math.max(0, a.lo[1]), x1 = Math.min(dims[0], a.hi[0] + 1), y1 = Math.min(dims[1], a.hi[1] + 1);
        if (x1 <= x0 || y1 <= y0) continue;
        const p = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => at([x, y, 0], 0, 0, z));
        for (let i = 0; i < 4; i++) dashed.push(p[i], p[(i + 1) % 4]);
        for (const q of p) {
          const s = screen(q), best = named.get(a.stream);
          if (s && (!best || s[1] > best.y)) named.set(a.stream, { y: s[1], q });
        }
      }
    }
    if (!dashed.length) return;
    const seg = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(dashed),
                                       new THREE.LineDashedMaterial({ color: WARN, dashSize: 10, gapSize: 7, depthTest: false, transparent: true }));
    seg.computeLineDistances(); seg.renderOrder = 8; seg.raycast = () => {}; seg.userData.reworkArea = true;
    layer.add(seg);
    for (const [stream, { q }] of named) areaLabel(areaWords({ stream }), q);
  }
  // The tooltip of a picked mark's triangle under the pointer (the canvas's title), or none.
  function warnTip(clientX, clientY) {
    const screen = projector();
    const near = badges.find(b => picked.has(b.key) && (s => Boolean(s) && Math.hypot(s[0] - clientX, s[1] - clientY) <= TIP_PX)(screen(b.point)));
    const words = near ? reworkWords(near.hits, true) : '';
    if (renderer.domElement.title !== words) renderer.domElement.title = words;
  }

  // ---------------------------------------------------------------- the tile under the pointer
  // The tile a screen point falls on: along the pointer's ray, the first drawn and uncut surface that is one of the
  // map's saved floors there (a surface within 16 units of the floor of its tile), else the first that faces up (a
  // floor the project makes), else the ground's plane; null off the grid. With the point it fell on (game axes).
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
      if (floor !== undefined && Math.abs(floor - point[2]) < 16) return inGrid({ tile, z: floor, point });
      if (!up && h.face && normal.copy(h.face.normal).transformDirection(h.object.matrixWorld).y > 0.7) up = { tile, z: point[2], point };
    }
    if (up) return inGrid(up);
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -(data.tileGrid.origin?.[2] ?? c[2] + 1));
    const v = ray.ray.intersectPlane(plane, new THREE.Vector3());
    return v ? inGrid({ tile: tileOf([v.x, v.z, v.y + 4], c), z: v.y, point: [v.x, v.z, v.y] }) : null;
  }
  // What is under a screen point in the view: the tile, and the picked mark's corner dot within the pick distance.
  function hoverAt(clientX, clientY) {
    const t = tileAt(clientX, clientY);
    let near = -1;
    const one = !adding ? onePicked() : null;
    if (one && editable()) {
      const screen = projector(), z = floorOf(one.tile, one.own);
      let best = HANDLE_PICK;
      CORNERS.forEach((c, i) => {
        const s = screen(dotAt(one.tile, c, z)), d = s ? Math.hypot(s[0] - clientX, s[1] - clientY) : Infinity;
        if (d < best) { best = d; near = i; }
      });
    }
    return t || near >= 0 ? { ...(t ?? { tile: one.tile, z: floorOf(one.tile, one.own), point: null }), corner: near } : null;
  }
  function hoverDiagonal(e) {
    if (!diagonalOn || drag) return;
    const was = JSON.stringify(hover);
    hover = hoverAt(e.clientX, e.clientY);
    if (JSON.stringify(hover) !== was) { draw(); hint(); }
    warnTip(e.clientX, e.clientY);
  }
  function hint() {
    if (!diagonalOn) return;
    const one = onePicked();
    const words = !editable() ? 'Diagonal cover view: marks are edited on a map opened from the map browser'
      : adding ? `Click a floor tile: a new mark there, with cover toward its corner nearest the pointer${hover?.point ? ` (${glyph(hover.tile, cornerNear(hover.tile, hover.point, corner()))})` : ''} · Esc cancels`
      : drag ? 'Drag: the marks move by whole tiles and levels (a mark belongs to a tile, whatever Snap says) · Esc puts them back'
      : one && hover?.corner >= 0 ? `Click: cover toward this corner of the tile (${glyph(one.tile, CORNERS[hover.corner])}), or none that way again`
      : hover && marks().some(m => m.key === tileKey(hover.tile) && (m.kind !== 'deleted' || showDeleted())) ? 'Click: pick this mark (Ctrl or Shift: add it)'
      : one ? 'The gizmo moves the mark by whole tiles · its corner dots switch its corners · [ and ] turn it · Delete deletes it'
      : 'Diagonal cover view: click a mark to pick it · new marks come from the Add panel (Diagonal cover) · Shift+C leaves it';
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
    draw(); panel(); placeGizmo();
  }
  function switchCorner(tile, i) {
    if (!editable()) { hint(); return; }
    commit(toggleCorner(data, projectDiagonal, corner(), tile, CORNERS[i], diagonalCarried), null, [tileKey(tile)]);
  }
  // [ and ]: the picked marks' corners turned a quarter (way 1: counter-clockwise in game axes)
  // The picked marks' corners a quarter turn (`way` 1: the game's yaw, to the right as seen from above; -1 to the left),
  // `times` over: one undo step
  function turnPicked(way, times = 1) {
    if (!editable() || !picked.size) return false;
    let next = projectDiagonal, count = 0;
    const turned = list => { let out = list; for (let n = 0; n < times; n++) out = turnedCorners(out, way); return out; };
    for (const m of marks().filter(x => picked.has(x.key) && x.kind !== 'deleted')) {
      const r = setCorners(data, next, corner(), m.tile, turned(m.toward), diagonalCarried, turned(m.low));
      if (r) { next = r; count++; }
    }
    if (count) commit(next, `Turned ${count === 1 ? 'the mark' : `${count} marks`} a quarter`);
    return true;
  }
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
  // Cover: the picked marks' corners all half cover (`half`) or all full
  function halfPicked(half) {
    if (!editable() || !picked.size) return;
    let next = projectDiagonal, count = 0;
    for (const m of marks().filter(x => picked.has(x.key) && x.kind !== 'deleted')) {
      const r = setHalf(data, next, corner(), m.tile, half, diagonalCarried);
      if (r) { next = r; count++; }
    }
    if (count) commit(next, `${count === 1 ? 'The mark gives' : `${count} marks give`} ${half ? 'half' : 'full'} cover`);
    else panel();
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
  // Copies of the picked marks `delta` tiles away (a Shift+drag on the gizmo's arrows), picked; one undo step. A copy
  // can't land on a tile that has a mark.
  const copyPicked = delta => placeMarks(marks().filter(m => picked.has(m.key) && m.kind !== 'deleted')
    .map(m => ({ tile: [0, 1, 2].map(k => m.tile[k] + delta[k]), toward: m.toward, low: m.low })), 'copied');
  // The picked marks as a copy carries them (Ctrl+C, Ctrl+X): each one's corners and its tile from the first one's;
  // null with none picked.
  function markClip() {
    const list = diagonalOn ? marks().filter(m => picked.has(m.key) && m.kind !== 'deleted' && m.toward.length) : [];
    if (!list.length) return null;
    const first = list[0].tile;
    return { thing: 'marks', name: list.length === 1 ? 'the mark' : `${list.length} marks`,
             marks: list.map(m => ({ offset: [0, 1, 2].map(k => m.tile[k] - first[k]), toward: m.toward.map(c => [...c]), low: m.low.map(c => [...c]) })) };
  }
  // Pasted marks put down, the first on `tile` (Ctrl+V and a click), picked
  function placeCopies(list, tile) {
    if (placeMarks(list.map(m => ({ tile: [0, 1, 2].map(k => tile[k] + m.offset[k]), toward: m.toward, low: m.low })), 'placed')) stopDiagonalPlacing();
  }
  // Marks with these corners put on these tiles, picked; one undo step. Refused where a tile has a mark already.
  function placeMarks(list, words) {
    let next = projectDiagonal;
    const keys = [];
    for (const m of list) {
      const added = addMark(data, next, corner(), m.tile, m.toward[0], diagonalCarried);
      const shaped = added && setCorners(data, added, corner(), m.tile, m.toward, diagonalCarried, m.low);
      if (!shaped) { flashHint(`Not ${words}: a tile has one mark, and a copy would land on another`); return false; }
      next = shaped; keys.push(tileKey(m.tile));
    }
    return commit(next, `${list.length === 1 ? 'A copy of the mark' : `Copies of ${list.length} marks`} ${words}`, keys);
  }
  function movePicked(delta) {
    const list = marks().filter(m => picked.has(m.key) && m.kind !== 'deleted');
    if (list.some(withCopy)) { flashHint('A mark a copy carries moves with the copy: move the copy'); return false; }
    const from = list.map(m => m.tile);
    // (the marks furthest along the move go first, so none lands on one that has not moved yet)
    from.sort((a, b) => (b[0] - a[0]) * delta[0] + (b[1] - a[1]) * delta[1] + (b[2] - a[2]) * delta[2]);
    let next = projectDiagonal;
    const keys = [];
    for (const t of from) {
      const to = [t[0] + delta[0], t[1] + delta[1], t[2] + delta[2]];
      const moved = moveMark(data, next, corner(), t, to, diagonalCarried);
      if (!moved) { flashHint('Not moved: a tile has one mark, and a mark would land on another'); return false; }
      next = moved; keys.push(tileKey(to));
    }
    return commit(next, `${from.length === 1 ? 'The mark' : `${from.length} marks`} moved by whole tiles`, keys);
  }

  // ---------------------------------------------------------------- the gizmo
  // The picked marks move with a gizmo at the first one's middle (view_gizmo.js, as every view's is), by whole tiles
  // across and levels up whatever Snap says (a mark belongs to a tile: the Snap button shows the step, and the hint says
  // so); its ring (R) turns their corners by quarters, as [ and ] do. A drag is one undo step, Escape during it puts it
  // back, and Shift on an arrow drags off copies of the picked marks.
  const firstPicked = () => marks().find(m => picked.has(m.key) && m.kind !== 'deleted' && !withCopy(m));
  // (a drag's move in whole tiles of the grid)
  const tilesOf = move => [0, 1, 2].map(k => Math.round(move[k] / TILE_SIZE[k]));
  const markView = createViewGizmo({ camera, dom: renderer.domElement, world, orbit: controls, flashHint, size: 0.6,      // (smaller than a piece's, so its handles stay clear of the corner dots at the tile's corners)
    at: () => { const first = diagonalOn && !adding && editable() ? firstPicked() : null; return first ? at(first.tile, 0.5, 0.5, floorOf(first.tile, first.own)) : null; },
    modes: ['translate', 'rotate'], leastSnap: 'tile', what: 'a diagonal cover mark belongs to a tile',
    step: move => tilesOf(move).map((n, k) => n * TILE_SIZE[k]),
    preview: change => {
      const first = firstPicked();
      drag = change?.move && first ? { from: first.tile, to: [0, 1, 2].map(k => first.tile[k] + tilesOf(change.move)[k]) } : null;
      draw(); hint();
    },
    commit: change => {
      drag = null;
      if (change.turns) { turnPicked(1, change.turns); return; }
      const delta = tilesOf(change.move);
      if (!delta.some(Boolean) || !movePicked(delta)) draw();
      hint();
    },
    revert: () => { drag = null; draw(); hint(); },
    copy: change => { drag = null; if (!copyPicked(tilesOf(change.move))) draw(); hint(); } });
  const { controls: markGizmo, helper: markGizmoHelper, proxy, place: placeGizmo, cancel: cancelGizmo } = markView;

  // ---------------------------------------------------------------- adding, from the Add panel
  // The Add panel's Diagonal cover kind: one entry, a new mark put down with a click (the one way to add one)
  function diagonalEntries() {
    if (!data || data.scope !== 'map' || data.preview || !corner()) return [];
    const count = marks().filter(m => m.kind !== 'deleted').length;
    return [{ key: 'diagonal', id: 'diagonal-new', diagonal: true, name: 'Diagonal cover', kind: 'Diagonal cover',
              pkg: 'cover toward a corner of a tile', detail: 'Put on a floor tile; turned and moved in the Diagonal cover view', count, builds: true,
              title: 'A new diagonal cover mark: click the floor tile it is to stand on, nearest the corner a unit there is to get cover toward (along the tile\'s diagonal). It gives full cover, or half with the panel\'s Cover; where no wall stands, cover against nothing',
              sources: [], pivotIndex: 0, materials: [], milestone: 1, role: null, size: [0, 0, 0], extent: 0, mesh: '',
              text: 'diagonal cover corner slanted wall ufo hull mark' }];
  }
  // (`template`: pasted copies, markClip's marks, put down with the first on the tile clicked; none for a new mark)
  function startDiagonalPlacing(template = null) {
    setDiagonalShown(true);
    if (!diagonalOn) return;
    picked.clear(); adding = template ?? true; renderer.domElement.style.cursor = 'crosshair';
    draw(); panel(); placeGizmo(); hint();
  }
  function stopDiagonalPlacing() {
    if (!adding) return;
    adding = false; renderer.domElement.style.cursor = ''; pieces.setChosen?.(null);
    draw(); placeGizmo(); hint();
  }
  function placeDiagonal(clientX, clientY) {
    const t = tileAt(clientX, clientY);
    if (!t) { flashHint('Click a floor tile of the map\'s grid'); return; }
    if (Array.isArray(adding)) { placeCopies(adding, t.tile); return; }
    const c = cornerNear(t.tile, t.point, corner());
    const next = addMark(data, projectDiagonal, corner(), t.tile, c, diagonalCarried);
    if (!next) { flashHint('That tile has a mark already: click it to pick it, and switch its corners there'); return; }
    stopDiagonalPlacing();
    commit(next, 'Added a diagonal cover mark', [tileKey(t.tile)]);
  }

  // ---------------------------------------------------------------- pointer and keys
  // A click in the view: while adding, puts the new mark down; on the picked mark's corner dot, switches that corner;
  // on a mark, picks it (Ctrl or Shift: adds it, or takes it out again); beside the marks, lets the picked go.
  function diagonalClick(e) {
    if (adding) { placeDiagonal(e.clientX, e.clientY); return; }
    const h = hoverAt(e.clientX, e.clientY);
    hover = h;
    const one = onePicked();
    if (one && h?.corner >= 0) { switchCorner(one.tile, h.corner); return; }
    const m = h && marks().find(x => (x.kind !== 'deleted' || showDeleted()) && x.key === tileKey(h.tile));
    const add = e.ctrlKey || e.shiftKey || e.metaKey;
    if (!m) { if (!add) { picked.clear(); draw(); panel(); placeGizmo(); hint(); } return; }
    if (add) { if (picked.has(m.key)) picked.delete(m.key); else picked.add(m.key); }
    else { picked.clear(); picked.add(m.key); }
    draw(); panel(); placeGizmo(); hint();
  }
  // The view's keys (navigation.js asks first): Delete deletes the picked marks, [ and ] turn them a quarter, Escape
  // puts a gizmo drag back, stops adding, or lets the picked go.
  function diagonalKey(key) {
    if (!diagonalOn) return false;
    if (key === 'escape') {
      if (cancelGizmo()) return true;
      if (adding) { stopDiagonalPlacing(); return true; }
      if (picked.size) { picked.clear(); draw(); panel(); placeGizmo(); hint(); return true; }
      return false;
    }
    if (drag) return true;
    if (key === 'delete' && picked.size) return deletePicked();
    if ((key === '[' || key === ']') && picked.size) return turnPicked(key === '[' ? -1 : 1);
    return false;
  }

  // ---------------------------------------------------------------- the view on and off
  function setDiagonalShown(on) {
    on = Boolean(on) && Boolean(data) && Boolean(corner());
    if (on === diagonalOn) { draw(); panel(); placeGizmo(); return; }
    if (on) {
      if (spawnsOn) setSpawnsShown(false);
      if (volumesOn) setVolumesShown(false);
      if (lightsOn) setLightsShown(false);
      if (zonesOn) setZonesShown(false);
      if (effectsOn) setEffectsShown(false);
      stopPickBox(); select(null);
    } else {
      cancelGizmo(); stopDiagonalPlacing(); picked.clear(); hover = null; renderer.domElement.title = '';
      $('dragHint').hidden = true; restingHint?.();
    }
    setDiagonalOnValue(on);
    lightButton(); draw(); panel(); placeGizmo();
    if (on) { flashHint('Diagonal cover view: only diagonal cover marks are picked · Shift+C leaves it'); hint(); }
  }

  // ---------------------------------------------------------------- the panel
  const els = { panel: $('diagonalPanel'), chip: $('diagonalChip'), where: $('diagonalWhere'), corners: $('diagonalCorners'),
                built: $('diagonalBuilt'), del: $('diagonalDelete'), reset: $('diagonalReset'), title: $('diagonalTitle'),
                height: $('diagonalHeight'), heightRow: $('diagonalHeightRow'), rework: $('diagonalRework'),
                reworkText: $('diagonalReworkText') };
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
      + (one.kind === 'carried' ? ` · follows ${String(one.by ?? '').split('.').pop()}` : '') : 'The gizmo moves them all; Delete deletes them all.';
    els.corners.hidden = !one || one.kind === 'deleted';
    if (one && one.kind !== 'deleted') layoutCorners(one);
    // the battle's rework (KB-22): why the picked marks it takes get no cover in the game
    const zone = areas(), taken = list.filter(m => m.kind !== 'deleted').map(m => reworkedBy(zone, m.tile)).filter(h => h.length);
    els.rework.hidden = !taken.length;
    if (taken.length) els.reworkText.textContent = reworkWords(taken.flat(), false, one ? 1 : taken.length);
    // Cover: the picked marks' as one (Full and half where they differ, which only a choice changes)
    const standing = list.filter(m => m.kind !== 'deleted'), heights = new Set(standing.map(heightOf));
    els.heightRow.hidden = !standing.length;
    els.height.value = heights.size === 1 ? [...heights][0] : 'mixed';
    els.height.querySelector('option[value="mixed"]').hidden = els.height.value !== 'mixed';
    els.height.disabled = !editable();
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
    const glyphs = ['↖', '↗', '↙', '↘'];
    els.corners.replaceChildren(...order.map((p, n) => {
      const b = document.createElement('button');
      b.type = 'button';
      const on = m.toward.some(d => cornerKey(d) === cornerKey(p.d));
      b.textContent = glyphs[order === placed ? n : slot(p)];
      b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
      b.title = `Cover toward this corner of the tile (game axes ${p.d[0] > 0 ? '+' : '-'}X ${p.d[1] > 0 ? '+' : '-'}Y): ${on ? 'on' : 'off'}`;
      b.disabled = !editable();
      b.onclick = () => switchCorner(m.tile, p.i);
      return b;
    }));
  }
  els.height.onchange = e => { if (e.target.value !== 'mixed') halfPicked(e.target.value === 'half'); e.target.blur(); };
  els.del.onclick = () => deletePicked();
  els.reset.onclick = () => resetPicked();
  $('diagonalShowDeleted').onchange = e => { draw(); panel(); e.target.blur(); };

  // The marks that follow their pieces, as the pieces stand now (the plan's section 5): [{ at, toward, low?, from?, by,
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
      if (piece.userData.edit) out.push({ ...carryMark(piece.userData.edit.elements, home, own.toward, c, own.low), from: home, by: own.wall, moves: true });
      const back = base(piece).invert();
      for (const copy of copies.get(own.wall) ?? []) {
        const m = carryMark(copy.matrix.clone().multiply(back).elements, home, own.toward, c, own.low);
        if (!handTiles.has(tileKey(tileOf(m.at, c)))) out.push({ ...m, by: copy.userData.source.actor });
      }
    }
    // a piece of another map brings the marks it gives at home: from its template's place to where it stands
    for (const [actor, r] of foreign) {
      const o = r.userData.source, template = foreignTemplates.get(`${targetKey(fromOf(o))}|${o.component}`);
      if (!template) continue;
      const move = r.matrix.clone().multiply(new THREE.Matrix4().fromArray(template.matrix).invert()).elements;
      for (const d of o.foreign.diagonal.filter(x => x.wall === fromOf(o).actor)) {
        const m = carryMark(move, d.at, d.toward, c, d.low ?? []);
        if (!handTiles.has(tileKey(tileOf(m.at, c)))) out.push({ ...m, by: actor });
      }
    }
    return out;
  }
  // After an edit, an undo or a change of the scene's pieces: the marks that follow their pieces worked out again, the
  // marks drawn, the picked ones that are gone let go, the panel and the gizmo.
  function refresh() {
    setDiagonalCarried(carriedNow());
    const now = new Set(marks().map(m => m.key));
    for (const k of [...picked]) if (!now.has(k)) picked.delete(k);
    draw(); panel(); placeGizmo();
  }
  onHub('edit', 'diagonal', refresh);
  onHub('scene', 'diagonal', refresh);

  return { deletePicked, diagonalClick, diagonalEntries, markClip, diagonalGizmo: () => ({ enabled: markGizmo.enabled, shown: markGizmoHelper.visible,
                                                                    axis: markGizmo.axis, dragging: markGizmo.dragging,
                                                                    at: [proxy.position.x, proxy.position.z, proxy.position.y] }),
           diagonalKey, diagonalPlacing: () => adding, drawDiagonal: draw, hoverDiagonal,
           pickedMarks: () => [...picked], diagonalWarnings: () => ({ badges: badges.map(b => ({ key: b.key, streams: [...new Set(b.hits.map(h => h.stream))],
                                                                                    screen: projector()(b.point) })),
                                                                  areas: layer.children.some(o => o.userData.reworkArea), title: renderer.domElement.title }),
           refreshDiagonal: refresh, setDiagonalShown, startDiagonalPlacing,
           stopDiagonalPlacing };
}
