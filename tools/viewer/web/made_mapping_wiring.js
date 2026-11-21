// A made piece's texture mapping in the piece panel and the view (the custom geometry improvements plan, section 5,
// stage 4; the design chosen, B: its section 10.6; made_mapping.js is the pure part). Here:
// - the Texture mapping fold of the Wall, Floor and Ground sections (texturePanel, which made_panel.js's sections call
//   as they fill: the fold is one element, put after the Look row of the section shown), showing one surface's mapping:
//   Original, Size, Fit or Count, its repeat, offset and turn, its flips, Aligned to the world and Reset surface, each
//   change one undo step (made_handles.js changeWall), an older piece put into the free form first (made_free.js
//   freeRequest), and what the look draws there in a note (made_mapping.js textureNotes: a part of a larger texture,
//   which a mapping repeats whole; a wall's side with no face; its faces' materials up the wall);
// - while the fold is open, the surface picked: by a click on the picked piece, by the hit's normal (pickSurface), or
//   Tab (stepSurface), outlined in the accent colour; editor_state.js's texturePicked says which, and every other
//   handle steps aside meanwhile: the piece's size handles (made_handles.js) and the move and turn gizmo (held here);
// - its handles in the view (updateTextureHandles, textureHandleNear, hoverTextureHandle): a blue dot at the pattern's
//   corner that slides it, a ring round the dot that turns it, a white dot along u that sizes a repeat (u and v in
//   proportion), dragged in the snap setting's steps on the surface (startTextureDrag, moveTextureDrag,
//   endTextureDrag): one undo step at the release, Esc putting it back. A ground shape's sides take the fields alone.
//
// createMadeMapping takes what it needs of app.js and the made pieces' base as one argument object, when app.js makes
// it (after the made pieces' handles, before their panel sections): the made pieces' state and changes (applyWall,
// applyWallSoon, dropQueuedWall, setWall, changeWall, wallState, handleWall), the camera, the renderer, the gizmo and the
// world, the pieces' pick and the pointer's ray, the handles' projector, the hints and the menus. Its own state is the
// surface the fold shows and the handle under the pointer; the surface picked while the fold is open and a handle's
// drag are editor_state.js's (texturePicked, textureDrag: the keys, the pointer handlers, the size handles and the test
// hooks read them).
import * as THREE from 'three';
import { segmented, text } from './dom_words.js';
import { setTextureDrag, setTexturePicked, snapMode, textureDrag, texturePicked } from './editor_state.js';
import { HANDLE_PICK } from './handles.js';
import { scaleMarker } from './lights_view.js';
import { freeRequest, toolFree } from './made_free.js';
import { framePoint, MAPPING_ROLES, mappingOrigin, mappingWords, nextSurface, patternCorner, patternPoint, sizable,
         sizedMapping, slidMapping, surfaceAt, surfaceExtent, surfaceMapping, surfaceOfNormal, surfacePlane,
         surfaceSteps, surfaceWords, textureNotes, turnedMapping, withMode, withSurface, withValue } from './made_mapping.js';
import { actorPose } from './scene_pieces.js';
import { moveWords, stepsOf, stepWords } from './snap_steps.js';

const KEY = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' };
const BOX = { fracWall: 'wallBox', fracSlab: 'slabBox', ground: 'groundBox' };
// the accent colour (style.css --accent): the picked surface's outline and the ring; the blue of a cut-out's picked
// handle for the dot that slides; white for the one that sizes
const ACCENT = 0x82d5ce, DOT = 0x9fdcff, WHITE = 0xffffff, LIT = 0xffe27a;
const RING_PX = 46, RING_SEGMENTS = 64;
const num = v => `${Math.round(v * 100) / 100}`;
const turnWords = snap => (stepsOf(snap).turn ? `in steps of ${stepsOf(snap).turn}°` : 'smoothly');
// (a slide on a wall's face or a ground shape's side steps across and up; on a top or underside, across both ways)
const slideWords = (snap, upright) => moveWords(snap, { across: !upright });
const TITLES = {
  slide: (snap, upright) => `The pattern's corner: drag to slide the pattern on the surface (${slideWords(snap, upright)}, as the snap setting)`,
  turn: snap => `The ring: drag round to turn the pattern about its corner (${turnWords(snap)}, as the snap setting)`,
  size: snap => `The white dot: drag to size a repeat, the other way in proportion (${stepWords(snap)}, as the snap setting)`,
};

export function createMadeMapping({ $, applyWall, applyWallSoon, camera, changeWall, dropQueuedWall, editChanged,
                                    flashHint, gizmo, handleWall, pick, projector, rayAt, renderer, restingHint,
                                    setWall, showPop, volumeHint, wallState, world }) {
  const fold = $('texFold');
  let surface = null;     // { id, role, side }: the surface the fold shows (a click, Tab, or the piece's first)
  let hover = null;       // the handle under the pointer: 'slide', 'turn' or 'size'

  // ---- the piece and its surface
  // A made piece's numbers as the free form has them (an older piece's as its first edit will make them).
  const numbersOf = root => { const g = freeRequest(root.userData.source.added.generated); return { g, kind: g.kind, n: g[KEY[g.kind]] }; };
  // The surface toward the camera first: a wall's face on the camera's side, a slab's top from above.
  function firstSurface(root, kind, n) {
    root.updateMatrixWorld(true);
    const eye = camera.position.clone().applyMatrix4(root.matrixWorld.clone().invert());      // (the view's axes: x, up, y)
    if (kind === 'fracWall') return { role: 'faces', side: eye.z >= (n.y0 + n.y1) / 2 ? 'y1' : 'y0' };
    if (kind === 'fracSlab') return { role: eye.y >= (n.z0 + n.z1) / 2 ? 'top' : 'underside', side: null };
    return { role: 'top', side: null };
  }
  function surfaceOf(root) {
    const { kind, n } = numbersOf(root), id = root.userData.source.id;
    if (!surface || surface.id !== id || !MAPPING_ROLES[kind].includes(surface.role)) surface = { id, ...firstSurface(root, kind, n) };
    return surface;
  }
  // texturePicked follows the fold: the surface while the fold is open on the made piece handled, else null; the move
  // and turn gizmo held aside while there is one (the texture handles show alone). Gives the piece, or null.
  function syncPicked() {
    const root = fold.open ? handleWall() : null, want = root ? surfaceOf(root) : null;
    const same = want ? texturePicked?.id === want.id && texturePicked.role === want.role && texturePicked.side === want.side : !texturePicked;
    if (same) return root;
    if (Boolean(want) !== Boolean(texturePicked)) gizmo.hold(Boolean(want), 'texture');
    setTexturePicked(want ? { ...want } : null);
    return root;
  }
  // Where the piece's frame stands on a world-aligned surface's axes (made_mapping.js mappingOrigin, as its mesh's
  // request gives it), [0, 0] for one in the piece's own frame.
  function originOf(root, kind, n, role) {
    const pose = actorPose(root.userData.source, root.matrix);
    return mappingOrigin(kind, n.mapping, pose.location, pose.rotation)?.[role] ?? [0, 0];
  }

  // ---- the fold
  function texturePanel(root, tool) {
    const { kind, n } = numbersOf(root);
    const look = $(BOX[kind]).querySelector('.lookrow');
    if (look.nextElementSibling !== fold) look.after(fold);
    const at = surfaceOf(root), s = surfaceMapping(n, at.role), off = !tool || !s;
    $('texFoldVal').textContent = mappingWords(at.role, s);
    $('texSurface').textContent = surfaceWords(kind, at);
    // (what the look draws there: a part of a larger texture, no face on a side, several materials up a wall)
    $('texNotes').replaceChildren();
    for (const note of textureNotes(kind, n, at)) text($('texNotes'), 'div', note);
    $('texMode').value = s ? s.mode : 'original';
    for (const b of $('texMode').querySelectorAll('button')) b.disabled = !tool;
    // (a field being typed in keeps what is typed)
    const put = (id, v) => { if (document.activeElement !== $(id)) $(id).value = v; };
    put('texU', s ? s.u : ''); put('texV', s ? s.v : '');
    put('texOffsetU', s ? s.offsetU ?? 0 : ''); put('texOffsetV', s ? s.offsetV ?? 0 : ''); put('texTurn', s ? s.turn ?? 0 : '');
    $('texSizeName').textContent = s?.mode === 'count' ? 'Count' : 'Repeat';
    $('texU').disabled = off || s.mode === 'fit';
    $('texV').disabled = off || (s.modeV ?? s.mode) === 'fit';
    for (const id of ['texOffsetU', 'texOffsetV', 'texTurn', 'texFlipU', 'texFlipV', 'texWorld']) $(id).disabled = off;
    $('texFlipU').checked = Boolean(s?.flipU); $('texFlipV').checked = Boolean(s?.flipV); $('texWorld').checked = Boolean(s?.world);
    $('texReset').disabled = off;
    syncPicked();
  }
  const refresh = root => texturePanel(root, true);
  fold.addEventListener('toggle', () => {
    if (!fold.open && textureDrag) endTextureDrag(false);
    const root = syncPicked();
    if (root && fold.open) flashHint('Click a surface of it to pick it (Tab: the next): drag the blue dot to slide its pattern, the ring to turn it, the white dot to size a repeat');
  });
  // A change of the surface's mapping, one undo step: `change(kind, numbers)` gives the new numbers, the same ones for
  // no change, or null for a value they cannot take (false then).
  function changeMapping(change) {
    let refused = false;
    changeWall(st => {
      const g = freeRequest(st.generated), key = KEY[g.kind], n = g[key], next = change(g.kind, n);
      if (next === null) refused = true;
      return next === null || next === n ? null : { ...st, generated: { ...g, [key]: next } };
    });
    return !refused;
  }
  const pickedRoot = () => { const root = handleWall(); return root ? { root, at: surfaceOf(root) } : null; };
  segmented($('texMode'), () => {
    const p = pickedRoot();
    if (!p) return;
    changeMapping((kind, n) => withMode(kind, n, p.at.role, $('texMode').value));
    refresh(p.root);
    document.activeElement?.blur?.();
  });
  const FIELDS = { texU: 'u', texV: 'v', texOffsetU: 'offsetU', texOffsetV: 'offsetV', texTurn: 'turn' };
  for (const [id, field] of Object.entries(FIELDS)) {
    const input = $(id);
    input.addEventListener('change', () => {
      const p = pickedRoot();
      if (!p) return;
      const value = input.value.trim() === '' ? Number.NaN : Number(input.value);
      if (!changeMapping((kind, n) => withValue(n, p.at.role, field, value)))
        flashHint(field === 'u' || field === 'v' ? 'A repeat is a number above 0' : 'It takes a number');
      refresh(p.root);       // (a value it could not take put back)
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') input.blur();
      else if (e.key === 'Escape') { input.blur(); const p = pickedRoot(); if (p) refresh(p.root); }
    });
  }
  for (const [id, field] of [['texFlipU', 'flipU'], ['texFlipV', 'flipV'], ['texWorld', 'world']]) {
    $(id).addEventListener('change', e => {
      const p = pickedRoot();
      if (p) { changeMapping((kind, n) => withValue(n, p.at.role, field, e.target.checked)); refresh(p.root); }
      e.target.blur();
    });
  }
  $('texReset').onclick = e => {
    const p = pickedRoot();
    if (p) { changeMapping((kind, n) => withMode(kind, n, p.at.role, 'original')); refresh(p.root); }
    e.currentTarget.blur();
  };

  // ---- picking a surface
  // A click on the picked piece while the fold is open picks the surface it falls on (true: the click is taken).
  function pickSurface(e) {
    if (!texturePicked) return false;
    const root = syncPicked();
    if (!root) return false;
    const hit = pick(e.clientX, e.clientY);
    if (!hit?.face || hit.object.userData.objectId !== root.userData.source.id) return false;
    root.updateMatrixWorld(true);
    const v = hit.face.normal.clone().transformDirection(hit.object.matrixWorld).transformDirection(root.matrixWorld.clone().invert());
    const kind = root.userData.source.added.generated.kind, at = surfaceOfNormal(kind, [v.x, v.z, v.y]);
    if (!at) {
      flashHint(kind === 'fracWall' ? "A wall's ends and top keep its look's texture: its faces take a mapping"
        : kind === 'fracSlab' ? "A floor's edges keep its look's texture: its top and underside take a mapping" : 'Its bottom is not drawn');
      return true;
    }
    surface = { id: root.userData.source.id, side: null, ...at };
    refresh(root);
    flashHint(`${surfaceWords(kind, surface)} · picked`);
    return true;
  }
  // Tab: the piece's next surface (Shift+Tab the one before); false when the fold is not open on a piece.
  function stepSurface(step) {
    const root = texturePicked ? syncPicked() : null;
    if (!root) return false;
    surface = { id: root.userData.source.id, side: null, ...nextSurface(root.userData.source.added.generated.kind, surfaceOf(root), step) };
    refresh(root);
    flashHint(`${surfaceWords(root.userData.source.added.generated.kind, surface)} · picked`);
    return true;
  }

  // ---- the outline and the handles in the view
  const layer = new THREE.Group(); layer.visible = false; world.add(layer);
  const lines = (count, loop) => {
    const geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    const material = new THREE.LineBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.95, depthTest: false });
    const line = loop ? new THREE.LineLoop(geometry, material) : new THREE.LineSegments(geometry, material);
    line.renderOrder = 8; line.raycast = () => {}; line.frustumCulled = false; layer.add(line);
    return line;
  };
  const outline = lines(24, false), ring = lines(RING_SEGMENTS, true);
  const ball = color => {
    const material = new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
    mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.color = color; layer.add(mesh);
    return mesh;
  };
  const dot = ball(DOT), white = ball(WHITE), grip = ball(ACCENT);
  // A rectangle of the surface (its extent) and a piece's box, as segments of the piece's frame.
  const rectangle = (plane, [a0, a1, b0, b1]) => {
    const c = [[a0, b0], [a1, b0], [a1, b1], [a0, b1]].map(ab => framePoint(plane, ab));
    return [[c[0], c[1]], [c[1], c[2]], [c[2], c[3]], [c[3], c[0]]];
  };
  const boxEdges = n => {
    const out = [];
    for (const [i, j, k] of [[0, 1, 2], [1, 0, 2], [2, 0, 1]]) for (const p of [0, 1]) for (const q of [0, 1]) {
      const lo = [0, 0, 0], hi = [0, 0, 0], ends = [[n.x0, n.x1], [n.y0, n.y1], [n.z0, n.z1]];
      lo[i] = ends[i][0]; hi[i] = ends[i][1]; lo[j] = hi[j] = ends[j][p]; lo[k] = hi[k] = ends[k][q];
      out.push([lo, hi]);
    }
    return out;
  };
  // Game units a pixel spans at a point of the view.
  const unitsPerPixel = v => 2 * camera.position.distanceTo(v) * Math.tan(camera.fov * Math.PI / 360) / Math.max(1, renderer.domElement.clientHeight);
  // The handles of the picked surface now: its outline, and (on a surface with a mapping and a plane) the dot at the
  // pattern's corner nearest the surface's middle, the white dot `reach` repeats along u (out where it can be told
  // apart from the dot and the ring), the ring round the dot and its grip; a drag holds its corner, reach and ring.
  function handlesNow(root) {
    const picked = textureDrag?.picked ?? texturePicked, { kind, n } = numbersOf(root);
    root.updateMatrixWorld(true);
    const m = root.matrixWorld, toView = p => new THREE.Vector3(p[0], p[2], p[1]).applyMatrix4(m);
    const plane = surfacePlane(kind, n, picked);
    const out = { root, kind, n, picked, plane, edges: (plane ? rectangle(plane, surfaceExtent(kind, n, picked.role)) : boxEdges(n)).map(([p, q]) => [toView(p), toView(q)]) };
    const s = surfaceMapping(n, picked.role);
    if (!plane || !s) return out;
    const extent = surfaceExtent(kind, n, picked.role), origin = textureDrag?.origin ?? originOf(root, kind, n, picked.role);
    const corner = textureDrag?.corner ?? patternCorner(s, extent, origin, [(extent[0] + extent[1]) / 2, (extent[2] + extent[3]) / 2]);
    const at = patternPoint(s, extent, origin, corner);
    if (!at) return out;
    const view = ab => toView(framePoint(plane, ab)), dotView = view(at);
    const aAxis = view([at[0] + 1, at[1]]).sub(dotView).normalize(), bAxis = view([at[0], at[1] + 1]).sub(dotView).normalize();
    const project = projector(), sp = project(dotView);
    const px = q => { const t = q && sp ? project(q.view) : null; return t ? Math.hypot(t[0] - sp[0], t[1] - sp[1]) : 0; };
    const place = r => { const p = patternPoint(s, extent, origin, [corner[0] + r, corner[1]]); return p && { ab: p, view: view(p) }; };
    let reach = textureDrag?.reach ?? 1, size = null, sizePx = 0;
    if (sizable(s)) {
      size = place(reach);
      if (!textureDrag) {
        for (let k = 0; k < 12 && px(size) < 3 * HANDLE_PICK; k++) size = place(reach *= 2);
        for (let k = 0; k < 12 && px(size) > 240 && px(place(reach / 2)) >= 3 * HANDLE_PICK; k++) size = place(reach /= 2);
      }
      sizePx = px(size);
    }
    // (the ring stays clear of the white dot: inside it, or out past it)
    let ringPx = textureDrag?.ringPx ?? RING_PX;
    if (!textureDrag && size && Math.abs(sizePx - ringPx) < 1.6 * HANDLE_PICK)
      ringPx = sizePx - 1.6 * HANDLE_PICK >= 2.2 * HANDLE_PICK ? sizePx - 1.6 * HANDLE_PICK : sizePx + 1.6 * HANDLE_PICK;
    const radius = ringPx * unitsPerPixel(dotView);
    const ringPoints = [...Array(RING_SEGMENTS).keys()].map(i => {
      const t = i / RING_SEGMENTS * 2 * Math.PI;
      return dotView.clone().addScaledVector(aAxis, Math.cos(t) * radius).addScaledVector(bAxis, Math.sin(t) * radius);
    });
    // (its grip a quarter round from where u runs, clear of the white dot)
    const u = size ? size.view.clone().sub(dotView).normalize() : aAxis.clone();
    const across = bAxis.clone().multiplyScalar(u.dot(aAxis)).addScaledVector(aAxis, -u.dot(bAxis)).normalize();
    return Object.assign(out, { s, extent, origin, corner, at, dotView, size, reach, ringPx, radius, ringPoints,
                                gripView: dotView.clone().addScaledVector(across, radius) });
  }
  function updateTextureHandles() {
    const root = textureDrag?.root ?? syncPicked();
    layer.visible = Boolean(root && (textureDrag || texturePicked)) && !gizmo.controls.dragging;
    if (!layer.visible) { if (hover) hoverTextureHandle(null); return; }
    const h = handlesNow(root), at = outline.geometry.attributes.position;
    for (let i = 0; i < 12; i++) {
      const [p, q] = h.edges[i] ?? [new THREE.Vector3(), new THREE.Vector3()];
      at.setXYZ(2 * i, p.x, p.y, p.z); at.setXYZ(2 * i + 1, q.x, q.y, q.z);
    }
    at.needsUpdate = true;
    outline.geometry.setDrawRange(0, 2 * h.edges.length);
    const lit = textureDrag?.which ?? hover;
    ring.visible = dot.visible = grip.visible = Boolean(h.dotView);
    white.visible = Boolean(h.size);
    if (!h.dotView) return;
    const rp = ring.geometry.attributes.position;
    h.ringPoints.forEach((v, i) => rp.setXYZ(i, v.x, v.y, v.z));
    rp.needsUpdate = true;
    ring.material.color.setHex(lit === 'turn' ? LIT : ACCENT);
    for (const [mesh, where, which, scale] of [[dot, h.dotView, 'slide', 1], [white, h.size?.view, 'size', 0.85], [grip, h.gripView, 'turn', 0.7]]) {
      if (!where) continue;
      mesh.position.copy(where);
      mesh.material.color.setHex(lit === which ? LIT : mesh.userData.color);
      scaleMarker(mesh, camera, where);
      mesh.scale.multiplyScalar(scale);
    }
  }
  // The handle near a point of the screen: the dot, the white dot, then the ring's line; null for none.
  function textureHandleNear(x, y) {
    const root = textureDrag ? null : texturePicked && syncPicked();
    if (!root || gizmo.controls.dragging) return null;
    const h = handlesNow(root);
    if (!h.dotView) return null;
    const project = projector(), d = v => { const p = project(v); return p ? Math.hypot(p[0] - x, p[1] - y) : Infinity; };
    if (d(h.dotView) <= HANDLE_PICK + 2) return 'slide';
    if (h.size && d(h.size.view) <= HANDLE_PICK + 2) return 'size';
    const pts = h.ringPoints.map(v => project(v));
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i], q = pts[(i + 1) % pts.length];
      if (!p || !q) continue;
      const dx = q[0] - p[0], dy = q[1] - p[1], t = Math.max(0, Math.min(1, ((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy || 1)));
      if (Math.hypot(p[0] + t * dx - x, p[1] + t * dy - y) <= HANDLE_PICK + 2) return 'turn';
    }
    return null;
  }
  function hoverTextureHandle(which) {
    if (which === hover) return;
    hover = which;
    renderer.domElement.style.cursor = which ? 'grab' : '';
    const upright = texturePicked?.role === 'faces' || texturePicked?.role === 'sides';
    renderer.domElement.title = which ? TITLES[which](snapMode, upright) : '';
  }

  // ---- a handle's drag
  // The point of the surface (a, b) under the pointer, on the surface's plane as the drag began; null when the ray runs
  // along it.
  function onSurface(e, d) {
    const hit = rayAt(e.clientX, e.clientY).ray.intersectPlane(d.plane, new THREE.Vector3());
    if (!hit) return null;
    const v = hit.applyMatrix4(d.inverse);
    return surfaceAt(d.kind, d.picked.role, [v.x, v.z, v.y]);
  }
  function startTextureDrag(e) {
    if (e.button !== 0 || textureDrag || !texturePicked || gizmo.controls.dragging) return false;
    const which = textureHandleNear(e.clientX, e.clientY), root = which && syncPicked();
    if (!root) return false;
    const h = handlesNow(root), m = root.matrixWorld.clone();
    const p0 = new THREE.Vector3(...[0, 2, 1].map(k => h.plane.origin[k])).applyMatrix4(m);
    const normal = new THREE.Vector3(h.plane.normal[0], h.plane.normal[2], h.plane.normal[1]).transformDirection(m);
    const d = { root, which, kind: h.kind, picked: { ...h.picked }, pointerId: e.pointerId, before: wallState(root), s: h.s,
                extent: h.extent, origin: h.origin, corner: h.corner, at: h.at, reach: h.reach, ringPx: h.ringPx,
                plane: new THREE.Plane().setFromNormalAndCoplanarPoint(normal, p0), inverse: m.clone().invert(),
                after: null, shown: null };
    d.from = onSurface(e, d);
    if (!d.from) return false;
    if (which === 'turn') { d.last = Math.atan2(d.from[1] - d.at[1], d.from[0] - d.at[0]); d.turned = 0; }
    if (which === 'size') {
      const way = [h.size.ab[0] - h.at[0], h.size.ab[1] - h.at[1]], l = Math.hypot(...way);
      d.way = way.map(v => v / l);
      d.t0 = (d.from[0] - d.at[0]) * d.way[0] + (d.from[1] - d.at[1]) * d.way[1];
      // (its step: up when the repeat runs more up a wall's face than along it)
      d.up = (h.kind === 'fracWall' || h.picked.role === 'sides') && Math.abs(d.way[1]) > Math.abs(d.way[0]);
    }
    setTextureDrag(d);
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  function moveTextureDrag(e) {
    const d = textureDrag, ab = onSurface(e, d);
    if (!ab) return;
    let s, words;
    if (d.which === 'slide') {
      s = slidMapping(d.s, d.extent, d.origin, [ab[0] - d.from[0], ab[1] - d.from[1]], surfaceSteps(d.kind, d.picked.role, snapMode));
      words = `Offset ${num(s.offsetU ?? 0)}, ${num(s.offsetV ?? 0)} repeats (${slideWords(snapMode, d.kind === 'fracWall' || d.picked.role === 'sides')})`;
    } else if (d.which === 'turn') {
      const a = Math.atan2(ab[1] - d.at[1], ab[0] - d.at[0]);
      let step = a - d.last;
      if (step > Math.PI) step -= 2 * Math.PI; else if (step < -Math.PI) step += 2 * Math.PI;
      d.turned += step; d.last = a;
      s = turnedMapping(d.s, d.extent, d.origin, d.corner, d.turned * 180 / Math.PI, stepsOf(snapMode).turn);
      words = `Turned ${num(s.turn ?? 0)}° (${turnWords(snapMode)})`;
    } else {
      const t = (ab[0] - d.at[0]) * d.way[0] + (ab[1] - d.at[1]) * d.way[1], steps = stepsOf(snapMode);
      s = sizedMapping(d.s, d.extent, d.origin, d.corner, d.reach, d.t0, t, d.up ? steps.up : steps.across);
      words = `${s.mode === 'count' ? 'Count' : 'Repeat'} ${num(s.u)} × ${num(s.v)} (${stepWords(snapMode, { up: d.up })})`;
    }
    const g = freeRequest(d.before.generated), key = KEY[g.kind], numbers = withSurface(g[key], d.picked.role, s);
    if (!toolFree(g.kind, numbers)) return;
    const shown = JSON.stringify(numbers.mapping);
    if (shown === d.shown) return;
    d.shown = shown;
    d.after = { generated: { ...g, [key]: numbers }, location: d.before.location, rotation: d.before.rotation };
    applyWallSoon(d.root, d.after);
    volumeHint(`${words} · Esc puts it back`);
  }
  // The drag ended: kept, one undo step, or (`keep` false: Esc, the pointer lost) put back.
  function endTextureDrag(keep) {
    const d = textureDrag;
    if (!d) return false;
    setTextureDrag(null);
    dropQueuedWall(d.root);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
    renderer.domElement.style.cursor = '';
    if (keep && d.after) setWall(d.root, d.after, d.before);
    else applyWall(d.root, d.before);
    restingHint(); editChanged();
    return true;
  }

  // ---- for the test hooks: the handles on the screen (and where they stand on the surface: `at` the dot, `turnAt` the
  // ring's grip, `sizeAt` the white dot), and where a point of a surface of the picked piece is drawn (its middle when
  // `ab` is not given)
  function textureHandleScreens() {
    const root = textureDrag?.root ?? (texturePicked && syncPicked());
    if (!root) return null;
    const h = handlesNow(root), project = projector();
    const onSurface = v => { const p = v.clone().applyMatrix4(root.matrixWorld.clone().invert()); return surfaceAt(h.kind, h.picked.role, [p.x, p.z, p.y]); };
    return { picked: { ...h.picked }, slide: h.dotView ? project(h.dotView) : null, turn: h.gripView ? project(h.gripView) : null,
             size: h.size ? project(h.size.view) : null, reach: h.reach ?? null, corner: h.corner ?? null, at: h.at ?? null,
             turnAt: h.gripView ? onSurface(h.gripView) : null, sizeAt: h.size?.ab ?? null };
  }
  function textureSurfaceAt(role, side = null, ab = null) {
    const root = handleWall();
    if (!root) return null;
    const { kind, n } = numbersOf(root), plane = surfacePlane(kind, n, { role, side });
    if (!plane) return null;
    const e = surfaceExtent(kind, n, role), p = framePoint(plane, ab ?? [(e[0] + e[1]) / 2, (e[2] + e[3]) / 2]);
    root.updateMatrixWorld(true);
    return projector()(new THREE.Vector3(p[0], p[2], p[1]).applyMatrix4(root.matrixWorld));
  }

  return { endTextureDrag, hoverTextureHandle, moveTextureDrag, pickSurface, startTextureDrag, stepSurface,
           textureHandleNear, textureHandleScreens, texturePanel, textureSurfaceAt, updateTextureHandles };
}
