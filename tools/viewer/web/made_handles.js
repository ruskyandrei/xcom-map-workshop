// A made piece, and its handles and drags (refactor stage P7; the custom geometry plan's M1 to M6, the custom geometry
// editing plan and the look picker and rock points plan; walls.js and ground.js hold what is pure about walls, slabs
// and ground shapes). Here:
// - what a made piece is (isMadeWall, isMadeSlab, isMadeGround, isMade, madeRoot, madeWallRoot), the look a wall was
//   made in (wallLookOf, lookWall) and its look's donor as a template (wallTemplate);
// - the piece as it is now (wallState) and changing it: its mesh's record (madeMesh, madeWallMesh), a state put on it
//   with its mesh drawn anew (applyWall), one undo step (setWall, changeWall), and where made walls meet, their ends
//   worked out again after every change (refreshJoins);
// - the picked made piece's handles (handleWall, wallHandlesNow, groundHandlesNow, slabHandlesNow, updateWallHandles,
//   wallHandleNear, hoverWallHandle) and their drags (startWallDrag, moveWallDrag, moveSlabDrag, moveGroundDrag,
//   endWallDrag), a drag's meshes asked of the server one at a time (applyWallSoon, dropQueuedWall);
// - a rock's corners asked of the server (rockCornersOf) and one moved with a gizmo of its own (pickRockPoint,
//   releaseRockPoint, placePointGizmo, cancelPointDrag).
//
// createMadeHandles takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the camera,
// the controls, the renderer and the scene, the pieces' parts and the meshes' loading, the pointer's ray, the made
// pieces' panels and drawing, the selection and the hints. Its own state is inside it (the hovered handle, the joins'
// queue, a rock point's drag, Shift held, the rocks' corners asked); what other areas read or set (a handle's drag,
// the opening last touched, the rock point picked, and the snap setting and a cover handle's drag it reads) is
// editor_state.js's.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { call } from './api.js';
import { PL, TILE } from './constants.js';
import { onHub } from './edit_hub.js';
import { coverDrag, data, effectsOn, geometryCache, lightsOn, placing, rockPoint, roots, selected, setRockPoint,
         setWallDrag, setWallFocus, snapMode, spawnsOn, volumeDrag, volumesOn, wallDrag, wallDrawing, wallFocus,
         zonesOn } from './editor_state.js';
import { groundBounds, groundBox as groundShapeBox, groundWords as groundShapeWords, madeGroundNumbers, movedPoint,
         raisedGround, resizedGround, ROCK, slopeWords, toolGround, versionedGround } from './ground.js';
import { scaleMarker } from './lights_view.js';
import { targetKey } from './project.js';
import { blastQuery, holeWords, madeBounds, madeSlabNumbers, madeWallNumbers, movedHole, movedOpening, OPENING as GAP,
         openingParts, openingWords, raisedWall, resizedSlab, resizedWall, shiftedLocation, slabBounds, slabLookOf,
         slabWords, sortedOpenings, storeysOf, storeyWords, toolSlab, toolWall, WALL, WALL_LOOKS, wallJoins, wallSpec,
         wallTop, wallWords } from './walls.js';
import { plural, short } from './dom_words.js';

export function createMadeHandles({ actorPose, alongLine, assetUrl, camera, controls, editChanged, flashHint, gizmo,
                                    gltfLoader, groundPanel, HANDLE_PICK, libraryTemplate, movedMatrix, partsOf,
                                    pickables, projector, rayAt, refreshHighlight, renderer, restingHint, sceneChanged,
                                    select, showPop, slabPanel, startWallDraw, track, volumeHint, wallPanel, world }) {
  // ---- made walls (custom geometry plan, stage M1; walls.js is the pure part). The Build menu's Wall draws a wall
  // (made_drawing.js): press on the ground at one end, drag along a tile line, release (Shift keeps drawing, Esc
  // stops). The wall is an added copy of the look's donor (a fracturing wall of the game's, this map's own or brought
  // from its map) that carries the numbers the Build makes its mesh from. A picked made wall has white handles at its
  // ends (whole tiles) and blue ones on each opening (its middle slides it, its sides, its top, a window's sill; in the
  // snap setting's steps, OPENING_STEPS, with Alt in steps of 8); the piece panel's Wall section adds, lists and
  // removes openings, flips it and reshuffles its break pattern. Each change is one undo step; the view draws the wall
  // as the Build makes it (generated.py), the last drawing kept until the next arrives.
  const isMadeWall = o => o?.added?.generated?.kind === 'fracWall';
  const madeWallRoot = id => { const r = roots.get(id); return r && isMadeWall(r.userData.source) ? r : null; };
  // floor and roof slabs (custom geometry plan, M5): drawn by dragging a rectangle (the floor under the start, an upper
  // floor a storey over it, a roof on the tops of the made walls round it, or two storeys up); white handles on its four
  // edges grow or shrink it by whole tiles, blue ones move and size its holes; the piece panel's Floor section adds and
  // removes holes and reshuffles its break pattern. Shared with the walls: the drawing, the handles, the undo steps.
  const isMadeSlab = o => o?.added?.generated?.kind === 'fracSlab';
  const isMadeGround = o => o?.added?.generated?.kind === 'ground';
  const isMade = o => isMadeWall(o) || isMadeSlab(o) || isMadeGround(o);
  const madeRoot = id => { const r = roots.get(id); return r && isMade(r.userData.source) ? r : null; };
  const wallLookOf = o => WALL_LOOKS.find(l => short(o.added?.from?.actor ?? '') === l.actor && (o.added?.from?.package ?? '').toLowerCase() === l.package.toLowerCase()) ?? null;
  // A wall standing for a look's heights (wallSpec): a donor look's numbers carry it; a look id's are the Bar's.
  const lookWall = look => (look?.donor ? { look: look.donor } : {});
  // The look's donor as a template: this map's own piece, or the piece read from its home map (libraryTemplate).
  async function wallTemplate(look) {
    const actor = `${PL}${look.actor}`;
    if (data.name?.toLowerCase() === look.package.toLowerCase()) {
      const parts = partsOf(targetKey({ package: data.name, level: 'base', actor }));
      if (!parts.length) throw Error(`${look.actor} is not in this export of the map`);
      return parts[0];
    }
    const t = await libraryTemplate({ package: look.package, actor });
    return t.sources.find(s => short(s.actor) === look.actor) ?? t.sources[t.pivotIndex];
  }
  // ---- the wall as it is now, and changing it
  const wallState = root => ({ generated: structuredClone(root.userData.source.added.generated), ...actorPose(root.userData.source, root.matrix) });
  // The mesh record for a made wall's numbers (as madeShape makes it) and end styles, its key.
  function madeMesh(o, generated, ends = null) {
    if (generated.kind === 'ground') {
      const numbers = madeGroundNumbers(generated.ground), key = `made:ground:${JSON.stringify(numbers)}`;
      if (!data.meshes[key])
        data.meshes[key] = { ...data.meshes[o.mesh], url: `/generated/ground.glb?${new URLSearchParams({ ground: JSON.stringify(numbers) })}`, bounds: groundBounds(numbers) };
      return key;
    }
    if (generated.kind !== 'fracSlab') return madeWallMesh(o, generated.wall, ends, generated.blasts);
    // (its blasts, B5, in its key and request)
    const numbers = madeSlabNumbers(generated.slab), broken = blastQuery(generated.blasts);
    const key = `made:fracslab:${JSON.stringify(numbers)}${broken.key}`;
    if (!data.meshes[key])
      data.meshes[key] = { ...data.meshes[o.mesh], url: `/generated/fracslab.glb?${new URLSearchParams({ slab: JSON.stringify(numbers), ...broken.query })}`, bounds: slabBounds(numbers) };
    return key;
  }
  function madeWallMesh(o, wall, ends = null, blasts = null) {
    const numbers = madeWallNumbers(wall, ends), broken = blastQuery(blasts);
    const key = `made:fracwall:${JSON.stringify(numbers)}${broken.key}`;
    if (!data.meshes[key]) {
      const was = data.meshes[o.mesh];
      data.meshes[key] = { ...was, url: `/generated/fracwall.glb?${new URLSearchParams({ wall: JSON.stringify(numbers), ...broken.query })}`,
        bounds: madeBounds(numbers) };
    }
    return key;
  }
  // ---- joined walls (custom geometry plan, M3 item 2): where made walls meet, each end's style follows (wallJoins, the
  // compiler's wall_joins), worked out again after every change and never saved (the Build works it out the same way);
  // a wall whose ends changed is drawn anew. root.userData.joins: its { ends, joins } now.
  let joinsQueued = false;
  function refreshJoins() {
    if (joinsQueued) return;
    joinsQueued = true;
    queueMicrotask(() => {
      joinsQueued = false;
      const walls = [...roots.values()].filter(r => isMadeWall(r.userData.source) && !r.userData.deleted
        && r.userData.source.added.generated.kind === 'fracWall');
      const found = wallJoins(walls.map(r => ({ key: r.userData.source.id, wall: r.userData.source.added.generated.wall,
                                                ...actorPose(r.userData.source, r.matrix) })));
      for (const r of walls) {
        const now = found[r.userData.source.id], was = r.userData.joins?.ends ?? ['free', 'free'];
        r.userData.joins = now;
        if (now.ends[0] !== was[0] || now.ends[1] !== was[1]) applyWall(r, wallState(r));
        else if (selected === r.userData.source.id && JSON.stringify(now.joins) !== JSON.stringify(r.userData.joinsShown ?? [])) wallPanel(r);
      }
    });
  }
  // A state put on the wall's piece: its numbers, its pose, its mesh drawn anew once loaded (no undo step).
  async function applyWall(root, state) {
    state = { ...state, generated: versionedGround(state.generated) };
    const o = root.userData.source;
    o.added = { ...o.added, generated: structuredClone(state.generated) };
    const key = madeMesh(o, state.generated, root.userData.joins?.ends), was = root.userData.drawnMesh ?? o.mesh;
    o.mesh = key;
    gizmo.applyMatrices([root], [movedMatrix(o, state.location, state.rotation)]);
    root.updateMatrixWorld(true);
    const token = root.userData.wallToken = (root.userData.wallToken ?? 0) + 1;
    track(geometryCache, key, () => gltfLoader.loadAsync(assetUrl(data.meshes[key].url)));
    let base;
    try { base = await geometryCache.get(key); }
    catch (error) {
      // a mesh the server didn't make (review finding 31): the piece keeps the numbers (its panel, handles and the save
      // have them, and the Build makes them) and its drawing the shape it had, which its mesh key says too; the hint says
      // why. (track drops the failed load, so the next change asks again.)
      if (root.userData.wallToken !== token) return;
      o.mesh = was;
      flashHint(`${data.meshes[key]?.name ?? 'The piece'}: the editor couldn't draw these numbers (${error?.message ?? error}), so it shows the shape it had; the Build makes the new one`);
      return;
    }
    if (root.userData.wallToken !== token) return;
    const old = root.userData.parts, materials = old.map(p => p.userData.baseMaterial);
    const fresh = base.scene.clone(true), parts = [];
    fresh.traverse(child => { if (child.isMesh) parts.push(child); });
    parts.forEach((part, i) => {
      part.material = materials[i] ?? materials[0];
      Object.assign(part.userData, { baseMaterial: part.material, objectId: o.id });
      part.castShadow = !part.material.transparent; part.receiveShadow = true;
    });
    root.clear();
    for (const child of [...fresh.children]) root.add(child);
    root.userData.parts = parts;
    // (the made mesh it drew before leaves the cache when no piece draws it: a drag passes through many, each a whole
    // wall's; undo asks the server again, which keeps its recent answers)
    root.userData.drawnMesh = key;
    if (was && was !== key && was.startsWith('made:') && ![...roots.values()].some(r => r.userData.source.mesh === was || r.userData.drawnMesh === was))
      geometryCache.delete(was);
    const gone = new Set(old);
    pickables.splice(0, pickables.length, ...pickables.filter(p => !gone.has(p)), ...(roots.get(o.id) === root ? parts : []));
    root.updateMatrixWorld(true);
    sceneChanged();
    if (selected === o.id) { refreshHighlight(root); (isMadeGround(o) ? groundPanel : isMadeSlab(o) ? slabPanel : wallPanel)(root); }
  }
  // One undo step from `before` to `after` (states), the piece picked again each way.
  function setWall(root, after, before) {
    const id = root.userData.source.id;
    after = { ...after, generated: versionedGround(after.generated) };
    if (JSON.stringify(after) === JSON.stringify(before)) { applyWall(root, before); return; }
    gizmo.record({ redo: () => { applyWall(root, after); select(id, false, true); },
                   undo: () => { applyWall(root, before); select(id, false, true); } });
  }
  function changeWall(change) {
    const root = madeRoot(selected);
    if (!root) return;
    const before = wallState(root), after = change(before);
    if (after) setWall(root, after, before);
  }
  // ---- the handles
  const wallHandleLayer = new THREE.Group(); world.add(wallHandleLayer);
  const wallHandleMeshes = [];
  const wallStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(24), 3)),
                                           new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
  wallStems.renderOrder = 8; wallStems.raycast = () => {}; wallStems.frustumCulled = false; wallHandleLayer.add(wallStems);
  let wallHover = null;     // (wallDrag, and wallFocus, the opening whose handle was last touched: editor_state.js)
  const WALL_PART_WORDS = { middle: 'Gap: drag to move it along the wall or up and down (down to the floor it is a doorway)', x0: 'Gap\'s side: drag it to the wall\'s end to cut the wall away to there',
                            x1: 'Gap\'s side: drag it to the wall\'s end to cut the wall away to there',
                            z1: 'Gap\'s top: drag it up to the wall\'s top to cut through it',
                            z0: 'Gap\'s bottom: drag it down to the floor to cut to the wall\'s bottom' };
  // A gap's handles move by the snap setting (the user, 19 November 2026: smoothly unless the snap is on), [along the
  // wall, up]; Alt: steps of GAP.fine
  const OPENING_STEPS = { off: [1, 1], fine: [24, 24], tile: [TILE, 24] };
  const OPENING_STEP_WORDS = { off: 'steps of 1 unit', fine: 'steps of 24', tile: 'whole tiles along the wall, steps of 24 up' };
  function handleWall() {
    const root = madeRoot(selected);
    if (!root || root.userData.deleted || !root.visible || placing || wallDrawing || volumesOn || lightsOn || zonesOn || effectsOn || spawnsOn
        || gizmo.picks().ids.length !== 1) return null;
    const g = root.userData.source.added.generated;
    return (g.kind === 'ground' ? toolGround(g.ground) : g.kind === 'fracSlab' ? toolSlab(g.slab) : toolWall(g.wall)) ? root : null;
  }
  // A ground shape's handles: a white one out of each edge ('side') at its top's middle height, and one on top ('top': a
  // block's top, a ramp's high edge) that raises it.
  function groundHandlesNow(root) {
    const g = root.userData.source.added.generated.ground, b = groundShapeBox(g);
    root.updateMatrixWorld(true);
    const toView = (x, y, h) => new THREE.Vector3(x, h, y).applyMatrix4(root.matrixWorld);
    const axis = (x, y, z = 0) => toView(x, y, z).sub(toView(0, 0, 0)).normalize();
    const mid = g.shape === 'ramp' ? b[5] / 2 : b[5], cx = (b[0] + b[1]) / 2, cy = (b[2] + b[3]) / 2;
    const out = [
      { key: 'side:x0', kind: 'side', part: 'x0', at: toView(b[0], cy, g.shape === 'ramp' ? 0 : mid), dir: axis(-1, 0) },
      { key: 'side:x1', kind: 'side', part: 'x1', at: toView(b[1], cy, mid), dir: axis(1, 0) },
      { key: 'side:y0', kind: 'side', part: 'y0', at: toView(cx, b[2], mid), dir: axis(0, -1) },
      { key: 'side:y1', kind: 'side', part: 'y1', at: toView(cx, b[3], mid), dir: axis(0, 1) }];
    if (g.shape !== 'patch')
      out.push({ key: 'end:top', kind: 'end', part: 'top', at: toView(g.shape === 'ramp' ? b[1] : cx, cy, b[5]), dir: axis(0, 0, 1) });
    // a rock's corners: a blue point on each (look picker and rock points plan, R3), from the server's answer
    const c = g.shape === 'rock' && !pointGizmo.dragging ? rockCornersOf(g) : null;
    for (const index of c?.corners ?? [])
      out.push({ key: `point:${index}`, kind: 'point', part: 'point', index, at: toView(...c.points[index]), dir: null });
    return out;
  }
  // ---- a rock's corners (look picker and rock points plan, R2, R3): its points and which are corners, asked of the
  // server (Python's seeded random isn't the page's) for each rock's numbers; a point picked takes the move gizmo
  const rockCorners = new Map();      // the rock's numbers, look aside (JSON) -> { points, corners } or a promise
  // A failed answer isn't kept (review finding 31): the hint says why, once, and the corners are asked for again after a
  // pause (the handles are worked out often, so not straight away)
  const rockCornersFailed = new Map();  // the rock's numbers -> performance.now() of its last failed answer
  function rockCornersOf(g) {
    const { look: _, ...shape } = madeGroundNumbers(g), key = JSON.stringify(shape), known = rockCorners.get(key);
    if (known && !known.then) return known;
    if (!known && !(performance.now() - (rockCornersFailed.get(key) ?? -Infinity) < 4000)) {
      const asking = call('GET', `/generated/ground-corners.json?${new URLSearchParams({ ground: key })}`, undefined,
                          { fallback: r => `the editor's server answered ${r.status}` })
        .then(answer => {
          if (!answer.points) throw new Error(answer.error ?? "the editor's server answered 200");
          return answer;
        })
        .then(answer => {
          rockCorners.set(key, answer);
          rockCornersFailed.delete(key);
          if (rockCorners.size > 300) rockCorners.delete(rockCorners.keys().next().value);
        }, error => {
          if (rockCorners.get(key) === asking) rockCorners.delete(key);
          if (!rockCornersFailed.has(key))
            flashHint(`The rock's corner points couldn't be read (${error?.message ?? error}); the editor asks again in a moment`);
          rockCornersFailed.set(key, performance.now());
        });
      rockCorners.set(key, asking);
    }
    return null;
  }
  let pointDrag = null;     // (rockPoint, the rock's point the gizmo stands on: editor_state.js)
  let shiftHeld = false;
  window.addEventListener('keydown', e => { if (e.key === 'Shift') shiftHeld = true; });
  window.addEventListener('keyup', e => { if (e.key === 'Shift') shiftHeld = false; });
  window.addEventListener('blur', () => { shiftHeld = false; });
  const pointProxy = new THREE.Object3D(); world.add(pointProxy);
  const pointGizmo = new TransformControls(camera, renderer.domElement);
  pointGizmo.attach(pointProxy); pointGizmo.enabled = false; pointGizmo.setSpace('local'); pointGizmo.setMode('translate');
  const pointGizmoHelper = pointGizmo.getHelper(); pointGizmoHelper.visible = false; world.add(pointGizmoHelper);
  pointGizmo.addEventListener('dragging-changed', e => { controls.enabled = !e.value; });
  // The picked rock's points now: its moved ones, else its seed's from the server (null until they are known).
  function rockPointsOf(g) { return g.points ?? rockCornersOf(g)?.points ?? null; }
  function pickRockPoint(root, index) {
    if (!rockPoint) gizmo.hold(true);
    setRockPoint({ id: root.userData.source.id, index });
    placePointGizmo();
    groundPanel(root);
    flashHint(`A corner of the rock: drag its arrows to move it${index < ROCK.ring ? ' on the ground (it is of the rock\'s foot)' : ''}; Shift: steps of 8 · Esc lets it go`);
  }
  function releaseRockPoint() {
    if (!rockPoint) return;
    const root = roots.get(rockPoint.id);
    setRockPoint(null); pointDrag = null;
    pointGizmo.enabled = pointGizmoHelper.visible = false;
    gizmo.hold(false);
    if (root && selected === root.userData.source.id && isMadeGround(root.userData.source)) groundPanel(root);
  }
  // Each frame: the gizmo on the picked point, or the point let go when its rock is no longer the one handled.
  function placePointGizmo() {
    if (!rockPoint) return;
    const root = roots.get(rockPoint.id);
    if (!root || (handleWall() !== root && !pointDrag) || root.userData.source.added?.generated?.ground?.shape !== 'rock') { releaseRockPoint(); return; }
    if (pointGizmo.dragging) return;
    const p = rockPointsOf(root.userData.source.added.generated.ground)?.[rockPoint.index];
    pointGizmo.enabled = pointGizmoHelper.visible = Boolean(p);
    if (!p) return;
    root.updateMatrixWorld(true);
    pointProxy.position.copy(new THREE.Vector3(p[0], p[2], p[1]).applyMatrix4(root.matrixWorld));
    pointProxy.quaternion.setFromRotationMatrix(new THREE.Matrix4().extractRotation(root.matrixWorld));
    pointProxy.updateMatrixWorld(true);
    // (a point of the rock's foot moves on the ground only: no up arrow, the view's y)
    pointGizmo.showY = rockPoint.index >= ROCK.ring;
  }
  pointGizmo.addEventListener('mouseDown', () => {
    const root = rockPoint && roots.get(rockPoint.id);
    const points = root && rockPointsOf(root.userData.source.added.generated.ground);
    if (!points) { pointDrag = null; return; }
    root.updateMatrixWorld(true);
    pointDrag = { root, index: rockPoint.index, points, before: wallState(root), frame: root.matrixWorld.clone(),
                  start: points[rockPoint.index], after: null, shown: '' };
  });
  pointGizmo.addEventListener('objectChange', () => {
    const d = pointDrag;
    if (!d) return;
    // the proxy's place in the rock's frame as it was when the drag began (its corner may move as the footprint grows)
    const local = pointProxy.position.clone().applyMatrix4(d.frame.clone().invert());
    let to = [local.x, local.z, local.y];
    if (shiftHeld) {
      to = to.map((v, k) => d.start[k] + Math.round((v - d.start[k]) / 8) * 8);
      pointProxy.position.copy(new THREE.Vector3(to[0], to[2], to[1]).applyMatrix4(d.frame));
    }
    const b = d.before, r = movedPoint(b.generated.ground, d.points, d.index, to);
    const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.frame))
      .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
    const location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
    const key = JSON.stringify([r.ground, location]);
    if (key === d.shown) return;
    d.shown = key;
    d.after = { generated: { ...b.generated, ground: r.ground }, location, rotation: b.rotation };
    applyWallSoon(d.root, d.after);
    const grown = r.ground.x1 !== b.generated.ground.x1 || r.ground.y1 !== b.generated.ground.y1;
    volumeHint(`Corner at ${r.ground.points[d.index].map(Math.round).join(', ')} in the rock's frame${grown ? ` · grown to ${groundShapeWords(r.ground).toLowerCase()}` : ''}`);
  });
  pointGizmo.addEventListener('mouseUp', () => {
    const d = pointDrag;
    pointDrag = null;
    dropQueuedWall(d?.root);
    if (d?.after && !d.cancelled) setWall(d.root, d.after, d.before);
    restingHint(); editChanged();
    setTimeout(placePointGizmo, 0);       // (the controls end their drag after this event)
  });
  function cancelPointDrag() {
    const d = pointDrag;
    if (!d) return false;
    d.cancelled = true; pointGizmo.reset?.();
    dropQueuedWall(d.root);
    applyWall(d.root, d.before);
    return true;
  }
  // A slab's handles: a white one out of the middle of each edge ('side', its part the side), at its top; on each hole a
  // blue one at each side and one in its middle ('hole'; the middle slides it on the slab, `dir` null).
  function slabHandlesNow(root) {
    const s = root.userData.source.added.generated.slab, look = slabLookOf(s), z = look.top + 1;
    root.updateMatrixWorld(true);
    const toView = (x, y, h) => new THREE.Vector3(x, h, y).applyMatrix4(root.matrixWorld);
    const axis = (x, y) => toView(x, y, 0).sub(toView(0, 0, 0)).normalize();
    const out = [
      { key: 'side:x0', kind: 'side', part: 'x0', at: toView(0, s.y1 / 2, z), dir: axis(-1, 0) },
      { key: 'side:x1', kind: 'side', part: 'x1', at: toView(s.x1, s.y1 / 2, z), dir: axis(1, 0) },
      { key: 'side:y0', kind: 'side', part: 'y0', at: toView(s.x1 / 2, 0, z), dir: axis(0, -1) },
      { key: 'side:y1', kind: 'side', part: 'y1', at: toView(s.x1 / 2, s.y1, z), dir: axis(0, 1) }];
    (s.holes ?? []).forEach((h, index) => {
      const cx = (h.x0 + h.x1) / 2, cy = (h.y0 + h.y1) / 2;
      out.push({ key: `hole:${index}:middle`, kind: 'hole', part: 'middle', index, at: toView(cx, cy, z), dir: null });
      for (const [part, x, y, d] of [['x0', h.x0, cy, [1, 0]], ['x1', h.x1, cy, [1, 0]], ['y0', cx, h.y0, [0, 1]], ['y1', cx, h.y1, [0, 1]]])
        out.push({ key: `hole:${index}:${part}`, kind: 'hole', part, index, at: toView(x, y, z), dir: axis(...d) });
    });
    return out;
  }
  // The handles of the wall now: each { key, kind ('end' | 'opening'), part, index, at (on the wall), dir (the drag's
  // axis, out of an end), out (whether it stands off the wall, out from `at`) } in the view.
  function wallHandlesNow(root) {
    if (isMadeGround(root.userData.source)) return groundHandlesNow(root);
    if (isMadeSlab(root.userData.source)) return slabHandlesNow(root);
    const w = root.userData.source.added.generated.wall;
    root.updateMatrixWorld(true);
    const toView = (x, y, z) => new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
    const axis = (x, y, z) => toView(x, y, z).sub(toView(0, 0, 0)).normalize();
    // the openings' handles on the face toward the camera
    const toCamera = camera.position.clone().sub(toView(w.x1 / 2, 0, 184));
    const spec = wallSpec(w), side = toCamera.dot(axis(0, 1, 0)) >= 0 ? spec.half + 1 : -spec.half - 1;
    const mid = (wallTop(w) + spec.bottom) / 2, out = [];
    out.push({ key: 'end:x0', kind: 'end', part: 'x0', at: toView(0, 0, mid), dir: axis(-1, 0, 0) });
    out.push({ key: 'end:x1', kind: 'end', part: 'x1', at: toView(w.x1, 0, mid), dir: axis(1, 0, 0) });
    // the top: up or down a storey (M2)
    out.push({ key: 'end:top', kind: 'end', part: 'top', at: toView(w.x1 / 2, 0, wallTop(w)), dir: axis(0, 0, 1) });
    sortedOpenings(w.openings ?? []).forEach((o, index) => {
      // (a gap cut to the wall's bottom has its bottom handle on the floor)
      const cx = (o.x0 + o.x1) / 2, bottom = Math.max(0, o.z0), cz = (bottom + o.z1) / 2;
      const at = { middle: [cx, cz], x0: [o.x0, cz], x1: [o.x1, cz], z1: [cx, o.z1], z0: [cx, bottom] };
      // (the middle drags in the wall's plane: `plane` its normal; the sides and ends along their axis)
      for (const part of openingParts())
        out.push({ key: `open:${index}:${part}`, kind: 'opening', part, index, at: toView(at[part][0], side, at[part][1]),
                   dir: part === 'middle' ? null : part === 'z0' || part === 'z1' ? axis(0, 0, 1) : axis(1, 0, 0),
                   plane: part === 'middle' ? axis(0, 1, 0) : null, along: part === 'middle' ? axis(1, 0, 0) : null });
    });
    return out;
  }
  const wallHandlePoint = h => (h.kind === 'end' || h.kind === 'side' ? h.at.clone().addScaledVector(h.dir, camera.position.distanceTo(h.at) * 0.06) : h.at);
  function updateWallHandles() {
    const root = wallDrag?.root ?? handleWall();
    wallHandleLayer.visible = Boolean(root) && !gizmo.controls.dragging && !pointGizmo.dragging;
    if (!wallHandleLayer.visible) { if (wallHover) hoverWallHandle(null); return; }
    const handles = wallHandlesNow(root), lit = wallDrag?.key ?? wallHover;
    while (wallHandleMeshes.length < handles.length) {
      const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
      mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material;
      wallHandleLayer.add(mesh); wallHandleMeshes.push(mesh);
    }
    const stems = wallStems.geometry.attributes.position;
    let n = 0;
    wallHandleMeshes.forEach((mesh, i) => {
      const h = handles[i];
      mesh.visible = Boolean(h);
      if (!h) return;
      mesh.position.copy(wallHandlePoint(h));
      const white = h.kind === 'end' || h.kind === 'side';
      const focused = !white && h.kind !== 'point' && wallFocus?.id === root.userData.source.id && wallFocus.index === h.index;
      const pickedPoint = h.kind === 'point' && rockPoint?.id === root.userData.source.id && rockPoint.index === h.index;
      mesh.userData.material.color.setHex(h.key === lit ? 0xffe27a : white || pickedPoint ? 0xffffff : focused ? 0x9fdcff : 0x4aa8ff);
      scaleMarker(mesh, camera, mesh.position);
      if (!white) mesh.scale.multiplyScalar(h.part === 'middle' ? 1 : h.kind === 'point' ? 0.7 : 0.8);
      if (white && n < 8) { stems.setXYZ(n++, h.at.x, h.at.y, h.at.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z); }
    });
    for (; n < 8; n++) stems.setXYZ(n, 0, 0, 0);
    stems.needsUpdate = true;
  }
  function wallHandleNear(x, y) {
    const root = handleWall();
    if (!root || gizmo.controls.dragging) return null;
    const project = projector();
    return wallHandlesNow(root).map(h => { const s = project(wallHandlePoint(h)); return s && { h, d: Math.hypot(s[0] - x, s[1] - y) }; })
      .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.h ?? null;
  }
  function hoverWallHandle(h) {
    const key = h?.key ?? null;
    if (key === wallHover) return;
    wallHover = key;
    renderer.domElement.style.cursor = key ? 'grab' : wallDrawing ? 'crosshair' : '';
    renderer.domElement.title = !h ? '' : h.kind === 'point' ? 'A corner of the rock: click it, then drag its arrows to move it (Shift: steps of 8)'
      : h.part === 'top' && isMadeGround(handleWall()?.userData.source) ? 'The top: drag to raise or lower it (steps of 8)'
      : h.kind === 'side' ? 'The edge: drag to grow or shrink it by whole tiles'
      : h.kind === 'hole' ? (h.part === 'middle' ? 'Hole: drag to slide it (whole tiles)' : 'Hole\'s side: drag to size it (whole tiles)')
      : h.part === 'top' ? topHandleWords(handleWall()?.userData.source.added.generated.wall)
      : h.kind === 'end' ? 'The wall\'s end: drag to lengthen or shorten it by whole tiles'
      : `${WALL_PART_WORDS[h.part]} (${OPENING_STEP_WORDS[snapMode]}, as the snap setting; Alt: steps of ${GAP.fine})`;
  }
  // What the wall's top handle does: adds or takes storeys (B4), its look's storeys at a time where it can't be made
  // one storey.
  function topHandleWords(w) {
    const spec = wallSpec(w);
    return `The wall's top: drag up or down to add or take storeys${spec.lower ? '' : ` (${storeyWords(spec.storeys)} at a time: its look is made that tall only)`}`;
  }
  // What the Build makes of a wall longer or taller than the game's (B4, D-3: made_split), in words; '' for one piece.
  function wallPiecesWords(w) {
    const spec = wallSpec(w), long = Math.round((w.x1 - w.x0) / TILE) > WALL.pieceTiles, tall = storeysOf(w) > spec.storeys;
    if (!long && !tall) return '';
    return ` The Build makes it as walls of at most ${WALL.pieceTiles} tiles and ${storeyWords(spec.storeys)} (its look's), `
      + `${long && tall ? 'joined end to end and stacked' : long ? 'joined end to end' : 'stacked'}: they break as one wall.`;
  }
  function startWallDrag(e) {
    if (wallDrawing) return startWallDraw(e);
    if (e.button !== 0 || wallDrag || coverDrag || volumeDrag || gizmo.controls.dragging) return false;
    // (a press on the point's gizmo is the gizmo's: it works out its arrow in its own press handler, after this one, so
    // it is asked here first)
    if (pointGizmo.enabled && !pointGizmo.dragging) {
      const r = renderer.domElement.getBoundingClientRect();
      pointGizmo.pointerHover({ x: (e.clientX - r.left) / r.width * 2 - 1, y: -(e.clientY - r.top) / r.height * 2 + 1, button: e.button });
    }
    if (pointGizmo.enabled && (pointGizmo.dragging || pointGizmo.axis !== null)) return false;
    const h = wallHandleNear(e.clientX, e.clientY);
    if (h?.kind === 'point') { pickRockPoint(handleWall(), h.index); return true; }
    if (rockPoint) releaseRockPoint();
    if (!h) return false;
    const root = handleWall(), from = h.dir ? alongLine(e.clientX, e.clientY, h.at, h.dir)
      : h.plane ? onPlane(e.clientX, e.clientY, h.at, h.plane) : onLevel(e.clientX, e.clientY, h.at.y);
    if (from == null) return false;
    root.updateMatrixWorld(true);
    setWallDrag({ root, key: h.key, handle: h, from, pointerId: e.pointerId, before: wallState(root), after: null, shown: null,
                 inverse: root.matrixWorld.clone().invert() });
    if (h.kind === 'opening') { setWallFocus({ id: root.userData.source.id, index: h.index }); wallPanel(root); }
    if (h.kind === 'hole') { setWallFocus({ id: root.userData.source.id, index: h.index }); slabPanel(root); }
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  // The point where the pointer's ray meets the level at view height y (null when it runs along it).
  function onLevel(clientX, clientY, y) {
    return rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -y), new THREE.Vector3());
  }
  // The point where the pointer's ray meets the plane through `at` square to `normal` (null when it runs along it).
  function onPlane(clientX, clientY, at, normal) {
    return rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(normal, at), new THREE.Vector3());
  }
  // A handle's drag asks the server for one made mesh at a time, the latest state, while the numbers and pose change at
  // once (so the handles follow the pointer): each answer for a long or tall wall takes a while, and asking for every
  // step had piled them up behind each other (the user, 19 November 2026: the gaps lagged far behind their handles).
  function applyWallSoon(root, state) {
    const o = root.userData.source;
    o.added = { ...o.added, generated: structuredClone(versionedGround(state.generated)) };
    gizmo.applyMatrices([root], [movedMatrix(o, state.location, state.rotation)]);
    root.updateMatrixWorld(true);
    const q = root.userData.applyQueue ??= { busy: false, next: null };
    q.next = state;
    if (q.busy) return;
    q.busy = true;
    (async () => {
      try { while (q.next) { const s = q.next; q.next = null; await applyWall(root, s); } } finally { q.busy = false; }
    })();
  }
  // The drag's queued states dropped (its last state is then applied by setWall, or the one before it put back).
  function dropQueuedWall(root) { if (root?.userData.applyQueue) root.userData.applyQueue.next = null; }
  function moveSlabDrag(e) {
    const d = wallDrag, h = d.handle, b = d.before, s = b.generated.slab;
    let slab = s, location = b.location, words;
    if (h.part === 'middle') {
      const at = onLevel(e.clientX, e.clientY, h.at.y);
      if (!at) return;
      // the pointer's move in the slab's own frame (its x and y), a hole slid by whole tiles each way
      const inv = new THREE.Matrix4().copy(d.root.matrixWorld).invert();
      const a = d.from.clone().applyMatrix4(inv), c = at.clone().applyMatrix4(inv);
      slab = movedHole(movedHole(s, h.index, 'x', c.x - a.x), h.index, 'y', c.z - a.z);
      words = holeWords(slab.holes[h.index]);
    } else {
      const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
      if (t == null) return;
      if (h.kind === 'side') {
        const r = resizedSlab(s, h.part, t - d.from);
        slab = r.slab;
        const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.root.matrixWorld))
          .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
        location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
        words = `${slabWords(slab)}${r.removed ? ` · ${plural(r.removed, 'hole')} past the edge will go` : ''}`;
      } else {
        slab = movedHole(s, h.index, h.part, t - d.from);
        words = holeWords(slab.holes[h.index]);
      }
    }
    const key = JSON.stringify([slab, location]);
    if (key === d.shown) return;
    d.shown = key;
    d.after = { generated: { ...b.generated, slab }, location, rotation: b.rotation };
    applyWallSoon(d.root, d.after);
    volumeHint(words);
  }
  function moveGroundDrag(e) {
    const d = wallDrag, h = d.handle, b = d.before, g0 = b.generated.ground;
    const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
    if (t == null) return;
    let g = g0, location = b.location;
    if (h.part === 'top') g = raisedGround(g0, t - d.from);
    else {
      const r = resizedGround(g0, h.part, t - d.from);
      g = r.ground;
      const turned = new THREE.Vector3(r.shift[0], 0, r.shift[1]).transformDirection(new THREE.Matrix4().extractRotation(d.root.matrixWorld))
        .multiplyScalar(Math.hypot(r.shift[0], r.shift[1]));
      location = [b.location[0] + turned.x, b.location[1] + turned.z, b.location[2]].map(v => Math.round(v * 1000) / 1000);
    }
    const key = JSON.stringify([g, location]);
    if (key === d.shown) return;
    d.shown = key;
    d.after = { generated: { ...b.generated, ground: g }, location, rotation: b.rotation };
    applyWallSoon(d.root, d.after);
    volumeHint(`${groundShapeWords(g)}${g.shape === 'ramp' ? ` · ${slopeWords(g)}` : ''}`);
  }
  function moveWallDrag(e) {
    if (isMadeGround(wallDrag.root.userData.source)) { moveGroundDrag(e); return; }
    if (isMadeSlab(wallDrag.root.userData.source)) { moveSlabDrag(e); return; }
    const d = wallDrag, h = d.handle, b = d.before, w = b.generated.wall;
    let wall = w, location = b.location, words, delta = 0;
    if (h.plane) {
      // (the gap's middle: the pointer's move in the wall's plane, in its frame: along it and up)
      const at = onPlane(e.clientX, e.clientY, h.at, h.plane);
      if (!at) return;
      const a = d.from.clone().applyMatrix4(d.inverse), c = at.clone().applyMatrix4(d.inverse);
      const [along, up] = e.altKey ? [GAP.fine, GAP.fine] : OPENING_STEPS[snapMode];
      wall = movedOpening(w, h.index, 'middle', [c.x - a.x, c.y - a.y], { along, up });
      words = `${openingWords(sortedOpenings(wall.openings)[h.index], wall)} (${e.altKey ? `steps of ${GAP.fine}` : OPENING_STEP_WORDS[snapMode]})`;
    } else {
      const t = alongLine(e.clientX, e.clientY, h.at, h.dir);
      if (t == null) return;
      delta = t - d.from;
    }
    if (h.plane) { /* moved above */ } else if (h.part === 'top') {
      const r = raisedWall(w, delta);
      wall = r.wall;
      words = `${wallWords(wall)}${r.cut ? ` · ${plural(r.cut, 'opening')} brought under the top` : ''}${r.removed ? ` · ${plural(r.removed, 'opening')} in the upper storey will go` : ''}`;
    } else if (h.kind === 'end') {
      // (out of the start end is back along the wall)
      const r = resizedWall(w, h.part, h.part === 'x0' ? -delta : delta);
      wall = r.wall; location = shiftedLocation(b.location, b.rotation, r.shift);
      words = `${wallWords(wall)}${r.removed ? ` · ${plural(r.removed, 'opening')} past the end will go` : ''}`;
    } else {
      const [along, up] = e.altKey ? [GAP.fine, GAP.fine] : OPENING_STEPS[snapMode];
      wall = movedOpening(w, h.index, h.part, delta, { along, up });
      words = `${openingWords(sortedOpenings(wall.openings)[h.index], wall)} (${e.altKey ? `steps of ${GAP.fine}` : OPENING_STEP_WORDS[snapMode]})`;
    }
    // (numbers the tool doesn't make, which the mesh server and the Build would refuse, aren't applied: the drag stays
    // at its last state the tool makes; review finding 32)
    if (!toolWall(wall)) return;
    const key = JSON.stringify([wall, location]);
    if (key === d.shown) return;
    d.shown = key;
    d.after = { generated: { ...b.generated, wall }, location, rotation: b.rotation };
    applyWallSoon(d.root, d.after);
    volumeHint(words);
  }
  function endWallDrag(keep) {
    const d = wallDrag;
    if (!d) return false;
    setWallDrag(null);
    dropQueuedWall(d.root);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
    renderer.domElement.style.cursor = '';
    if (keep && d.after) setWall(d.root, d.after, d.before);
    else applyWall(d.root, d.before);
    restingHint(); editChanged();
    return true;
  }

  // The scene's pieces changed (the edit hub's scene run, edit_hub.js): where made walls meet.
  onHub('scene', 'joins', () => { refreshJoins(); });

  return { cancelPointDrag, changeWall, endWallDrag, handleWall, hoverWallHandle, isMade, isMadeGround, isMadeSlab,
           isMadeWall, lookWall, madeRoot, madeWallRoot, moveWallDrag, placePointGizmo, pointGizmo, refreshJoins,
           releaseRockPoint, rockCorners, setWall, startWallDrag, updateWallHandles, wallHandleNear, wallHandlePoint,
           wallHandlesNow, wallLookOf, wallPiecesWords, wallState, wallTemplate };
}
