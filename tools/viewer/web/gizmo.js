// Move/rotate gizmo for trying out edits in the viewer. Edits change only what is drawn:
// nothing is saved or built. An edit moves a whole actor (all its components) about the
// actor's own pivot, on all three axes, and is undoable.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { nearestGridPose } from './poserule.js';

const TURN = 65536;   // native rotator units per turn
// Game space (X, Y, Z up) and the viewer's (X, Y up, Z) differ by a Y/Z swap, its own inverse.
const BASIS = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const conjugate = m => BASIS.clone().multiply(m).multiply(BASIS);

/** The actor's placement without scale, in the viewer's basis (as export_math.transform). */
export function actorMatrix(location, rotation) {
  const [p, y, r] = rotation.map(v => v * 2 * Math.PI / TURN);
  const [cp, sp, cy, sy, cr, sr] = [Math.cos(p), Math.sin(p), Math.cos(y), Math.sin(y), Math.cos(r), Math.sin(r)];
  const axes = [[cp * cy, cp * sy, sp], [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
                [-cr * sp * cy - sr * sy, cy * sr - cr * sp * sy, cr * cp]];
  const game = new THREE.Matrix4().set(
    axes[0][0], axes[1][0], axes[2][0], location[0],
    axes[0][1], axes[1][1], axes[2][1], location[1],
    axes[0][2], axes[1][2], axes[2][2], location[2], 0, 0, 0, 1);
  return conjugate(game);
}

/** The actor pose (game location, native rotator units) of a piece whose exported source is `source`,
 *  drawn at render matrix `matrix`. A copy placed at a new matrix gets its own pivot this way. */
export function placedPose(source, matrix) {
  const actor = matrix.clone().multiply(new THREE.Matrix4().fromArray(source.matrix).invert())
    .multiply(actorMatrix(source.location, source.rotation));
  const pose = gamePose(actor);
  return { location: pose.location, rotation: pose.rotation.map(d => d * TURN / 360) };
}

/** Game location and rotator (degrees) of a pose in the viewer's basis. */
export function gamePose(matrix) {
  const g = conjugate(matrix).elements;   // column-major
  const at = (row, col) => g[col * 4 + row];
  const deg = v => v * 180 / Math.PI;
  const pitch = Math.asin(THREE.MathUtils.clamp(at(2, 0), -1, 1));
  // Pitched straight up or down, yaw and roll turn about the same axis: report it all as yaw.
  const gimbal = Math.abs(Math.cos(pitch)) < 1e-6;
  return {
    location: [at(0, 3), at(1, 3), at(2, 3)],
    rotation: [deg(pitch), deg(gimbal ? Math.atan2(-at(0, 1), at(1, 1)) : Math.atan2(at(1, 0), at(0, 0))),
               gimbal ? 0 : deg(Math.atan2(-at(2, 1), at(2, 2)))],
  };
}

/** The move nearest `delta` (viewer space) that keeps a ladder, door, car or van to its pose rule (poserule.js, the
 *  recipe snap): `actor` is the piece's actor matrix before the move, `from` its original's game pose ({ location,
 *  rotation in rotator units }), `origin` the tile grid's corner (game x, y). */
export function recipeMove(delta, actor, from, origin) {
  const pose = gamePose(delta.clone().multiply(actor));
  const near = nearestGridPose(from.location, from.rotation, pose.location, pose.rotation.map(d => d * TURN / 360), origin);
  return actorMatrix(near.location, near.rotation).multiply(actor.clone().invert());
}

// lockedGroup(source): the id of the locked group (the user's own, kept in the project) this piece belongs to, or null.
// fixed(source): a piece that never moves (a streamed package's, shown for reference): it can be picked to inspect, but
// no selection takes it in.
// assemblyOf(source): the map's assembly (families.py) this original is in, or for a copy the one its original is in,
// or null. Its pieces always move together, whatever linked pieces says: a car's body, glass and light bar, a door's
// leaf and frame. An original's assembly joins by its key; a copy's by the prefab and partner links its paste gave it.
// recipe(root): the game pose of the original whose pose rule this piece keeps under tile snap (a ladder, door, car,
// van or fracturing piece), or null;
// gridOrigin(): the tile grid's corner (game x, y), or null.
// copyDrag: { begin(), end(token, delta) }, for a move handle (an axis or a plane) taken with Shift held: the drag
// moves a copy. begin() returns the viewer's token for it (what is copied), or null for a plain move. The selection
// moves as in any drag, and at the end goes back to where it was: end(token, delta) places the copy, moved by `delta`
// (viewer space), or drops it with a null delta (cancelled, or not moved).
export function createGizmo({ world, camera, dom, orbit, roots, baseMatrix, onEdit, lockedGroup = () => null, fixed = () => false,
                              assemblyOf = () => null, recipe = () => null, gridOrigin = () => null, levels = () => false,
                              tiles = () => false, copyDrag = null }) {
  const proxy = new THREE.Object3D();
  world.add(proxy);
  const controls = new TransformControls(camera, dom);
  controls.attach(proxy);
  controls.enabled = false;
  const helper = controls.getHelper();
  helper.visible = false;
  world.add(helper);

  let group = [], picked = [], active = null, linked = true, mode = 'translate', drag = null, cancelled = false, held = false;
  let snap = 'off', rule = null, pivot = 'origin';
  const undo = [], redo = [];

  const sourceOf = root => root.userData.source;
  const scope = o => `${o.sourcePackage}|${o.layer}`;
  const actorKey = o => `${scope(o)}|${o.actor}`;
  // Every component of a picked actor moves with it, and so do the other pieces of a locked group and of an assembly,
  // always. With linked pieces on, so do the actors placed by the same prefab instance (a pool table's parts) and
  // named partners (HidingPartner), and theirs in turn.
  // linkFinder(list) joins the actors of those roots into groups in one pass and returns each actor's group.
  function linkFinder(list, links = true, locked = true) {
    const parent = new Map();
    const find = k => {
      if (!parent.has(k)) return k;
      let top = k;
      while (parent.get(top) !== top) top = parent.get(top);
      for (let next; k !== top; k = next) { next = parent.get(k); parent.set(k, top); }
      return top;
    };
    const join = (a, b) => { for (const k of [a, b]) if (!parent.has(k)) parent.set(k, k); parent.set(find(a), find(b)); };
    const actors = new Set(list.map(r => actorKey(sourceOf(r))));
    for (const o of list.map(sourceOf)) {
      const k = actorKey(o);
      join(k, k);
      const g = locked ? lockedGroup(o) : null;
      if (g) join(k, `group|${g}`);
      const assembly = assemblyOf(o);
      if (assembly && !o.added) join(k, `assembly|${scope(o)}|${assembly}`);
      if (!links && !assembly) continue;
      if (o.prefab) join(k, `prefab|${scope(o)}|${o.prefab}`);
      // A partner joins only when it is there: two pieces naming one missing partner stay apart.
      if (o.partner && actors.has(`${scope(o)}|${o.partner}`)) join(k, `${scope(o)}|${o.partner}`);
    }
    return find;
  }
  function expand(ids, withLinks = linked) {
    const all = [...roots.values()].filter(r => !r.userData.deleted && !fixed(sourceOf(r)));
    const keys = ids.map(id => roots.get(id)).filter(Boolean).map(r => actorKey(sourceOf(r)));
    const find = linkFinder(all, withLinks), groups = new Set(keys.map(find));
    return all.filter(r => groups.has(find(actorKey(sourceOf(r)))));
  }
  function regroup() {
    group = expand(picked);
    rule = ruleOf(group);
    placeProxy(); applySnap(); show();
  }
  // The piece whose pose rule an edit keeps under tile snap (the recipe snap): the active piece if it has one, else the
  // first of the group that has. null when none has, or the map has no tile grid. Snap off or fine, it moves as any
  // piece does (the Build warns of a pose off the grid).
  const ruled = () => (snap === 'tile' ? rule : null);
  // A selection with a building's box in it (tiles(root)) moves by whole tiles and levels and turns by quarter turns
  // about the vertical, whatever the snap: a box stays a box of the tile grid.
  const boxed = () => group.some(tiles);
  function ruleOf(targets) {
    const origin = gridOrigin();
    if (!origin) return null;
    for (const root of [roots.get(active), ...targets]) {
      if (!root || !targets.includes(root)) continue;
      const from = recipe(root);
      if (from) return { root, from, origin };
    }
    return null;
  }
  // A piece's actor matrix where it is drawn now: its offset from the exported pose times the actor's placement.
  const actorOf = root => {
    const s = sourceOf(root);
    return root.matrix.clone().multiply(new THREE.Matrix4().fromArray(s.matrix).invert()).multiply(actorMatrix(s.location, s.rotation));
  };
  // The controls' own steps: tile snap turns by quarter turns and does its own moves (the recipe snap's for a piece with
  // a pose rule).
  function applySnap() {
    controls.setTranslationSnap(snap === 'fine' ? 24 : null);
    controls.setRotationSnap(snap === 'tile' || boxed() ? Math.PI / 2 : snap === 'fine' ? THREE.MathUtils.degToRad(15) : null);
    show();
  }
  // After a command added or removed pieces: drop picks that are gone or deleted.
  function refresh() {
    picked = picked.filter(id => roots.has(id) && !roots.get(id).userData.deleted);
    if (!picked.includes(active)) active = picked.at(-1) ?? null;
    regroup();
  }
  // The active actor's matrix where it is drawn now (what the pose fields show and setPose moves).
  const activeActor = () => actorOf(roots.get(active) || group[0]);
  // The middle of the selection's box (viewer space), for the centre pivot (Discord feedback S4). With tile snap, or a
  // building's box in the selection, it keeps to the nearest tile corner or tile centre across: a quarter turn about
  // either maps the tile grid onto itself, so pieces on the tiles stay on them. (A piece one tile by two still moves half
  // a tile when turned: its own middle is on a tile's edge.) Its height is the box's middle.
  function centreOf(list) {
    const box = new THREE.Box3();
    for (const root of list) box.expandByObject(root);
    if (box.isEmpty()) return null;
    const c = box.getCenter(new THREE.Vector3()), origin = gridOrigin();
    if (origin && (snap === 'tile' || boxed())) {
      const near = (v, o, half) => o + (Math.round((v - o) / 96 - half) + half) * 96;   // half: 0 a corner, 0.5 a centre
      const corner = [near(c.x, origin[0], 0), near(c.z, origin[1], 0)], middle = [near(c.x, origin[0], 0.5), near(c.z, origin[1], 0.5)];
      const off = ([x, z]) => Math.hypot(x - c.x, z - c.z);
      [c.x, c.z] = off(corner) <= off(middle) ? corner : middle;
    }
    return c;
  }
  // The proxy (what the handles drag) sits on the active actor's pivot, with its axes: its current offset from the
  // exported pose times the actor's placement. With the centre pivot it keeps those axes and sits on the selection's
  // middle instead. A drag applies the proxy's change to the whole selection as one move, so where the proxy sits is
  // what the selection turns about.
  function placeProxy() {
    if (!group.length) return;
    activeActor().decompose(proxy.position, proxy.quaternion, new THREE.Vector3());
    if (pivot === 'centre') { const c = centreOf(group); if (c) proxy.position.copy(c); }
    proxy.scale.set(1, 1, 1);
    proxy.updateMatrixWorld(true);
  }
  function apply(targets, matrices) {
    targets.forEach((root, i) => {
      root.matrix.copy(matrices[i]);
      root.matrixWorldNeedsUpdate = true;
      // Back at its base pose (undo, reset, or dragged back) the piece counts as unedited; the edit
      // matrix itself carries rounding noise, so compare poses with a tolerance instead.
      const base = baseMatrix(root);
      const unchanged = root.matrix.elements.every((v, k) => Math.abs(v - base.elements[k]) < 1e-6);
      root.userData.edit = unchanged ? null : root.matrix.clone().multiply(base.invert());
    });
  }
  // History entries are commands, { undo(), redo() }: a matrix change is one kind, and the viewer
  // records its own (adding, deleting, resetting pieces) through api.record.
  function commit(targets, before, after) {
    if (before.every((m, i) => m.equals(after[i]))) return;
    undo.push({ undo: () => apply(targets, before), redo: () => apply(targets, after) });
    redo.length = 0;
  }
  function show() {
    const on = group.length > 0 && mode !== 'off' && !held;
    controls.enabled = on;
    helper.visible = on;
    // The recipe snap turns about the vertical only: no pitch or roll rings.
    controls.showX = controls.showZ = !((ruled() || boxed()) && mode === 'rotate');
    if (on) controls.setMode(mode);
  }

  controls.addEventListener('dragging-changed', e => { orbit.enabled = !e.value; });
  // (whether Shift is held as a handle is taken: the controls' own events don't say)
  let shiftDown = false;
  dom.addEventListener('pointerdown', e => { shiftDown = e.shiftKey; }, true);
  controls.addEventListener('mouseDown', () => {
    proxy.updateMatrix();
    const copy = shiftDown && controls.mode === 'translate' && copyDrag ? copyDrag.begin() : null;
    drag = { proxy: proxy.matrix.clone(), position: proxy.position.clone(), quaternion: proxy.quaternion.clone(),
             targets: group, before: group.map(r => r.matrix.clone()), rule: ruled() && { ...rule, actor: actorOf(rule.root) },
             // levels(root): whether the active piece keeps to whole levels up and down (the viewer's Level snap)
             levels: group.length > 0 && levels(roots.get(active) || group[0]),
             // tiles(root): a building's box; with one in the selection it all moves by whole tiles and levels
             tiles: boxed(), copy };
    cancelled = false;
  });
  controls.addEventListener('objectChange', () => {
    if (!drag) return;
    if (cancelled) {
      // Escape ends the edit; ignore the rest of this drag.
      proxy.position.copy(drag.position); proxy.quaternion.copy(drag.quaternion);
      proxy.updateMatrixWorld(true);
      return;
    }
    // Tile snap moves by whole tiles from where the drag started (96 across, 64 up), so a piece keeps its offset
    // within its tile; the controls' own snap would round the pivot to absolute multiples instead.
    // The recipe snap puts the rule's piece at the nearest pose its rule allows, and the rest of the group with it.
    if (drag.rule) {
      proxy.updateMatrix();
      const delta = recipeMove(proxy.matrix.clone().multiply(drag.proxy.clone().invert()), drag.rule.actor, drag.rule.from, drag.rule.origin);
      delta.multiply(drag.proxy).decompose(proxy.position, proxy.quaternion, new THREE.Vector3());
    } else if ((snap === 'tile' || drag.tiles) && controls.mode === 'translate') {
      const d = proxy.position.clone().sub(drag.position);
      proxy.position.set(drag.position.x + Math.round(d.x / 96) * 96, drag.position.y + Math.round(d.y / 64) * 64,
                         drag.position.z + Math.round(d.z / 96) * 96);
    }
    // Level snap: a floor piece moves up and down by whole levels (64 units) from where the drag started; across, as set
    if (!drag.rule && drag.levels && controls.mode === 'translate')
      proxy.position.y = drag.position.y + Math.round((proxy.position.y - drag.position.y) / 64) * 64;
    proxy.updateMatrix();
    const delta = proxy.matrix.clone().multiply(drag.proxy.clone().invert());
    apply(drag.targets, drag.before.map(m => delta.clone().multiply(m)));
    onEdit();
  });
  controls.addEventListener('mouseUp', () => {
    if (drag?.copy) {
      // a copy's drag: the selection goes back, and the viewer places the copy where it was dragged to
      proxy.updateMatrix();
      const delta = proxy.matrix.clone().multiply(drag.proxy.clone().invert());
      const moved = !cancelled && drag.targets.some((r, i) => !r.matrix.equals(drag.before[i]));
      const token = drag.copy;
      apply(drag.targets, drag.before); placeProxy();
      drag = null; cancelled = false;
      onEdit();
      copyDrag.end(token, moved ? delta : null);
      return;
    }
    if (drag && !cancelled) commit(drag.targets, drag.before, drag.targets.map(r => r.matrix.clone()));
    if (drag && cancelled) { apply(drag.targets, drag.before); placeProxy(); onEdit(); }
    drag = null; cancelled = false;
  });

  function step(from, to) {
    const entry = from.pop();
    if (!entry) return;
    to.push(entry);
    (from === undo ? entry.undo : entry.redo)();
    refresh(); onEdit();
  }
  function reset(targets) {
    const edited = targets.filter(r => r.userData.edit);
    if (!edited.length) return;
    const before = edited.map(r => r.matrix.clone());
    apply(edited, edited.map(r => baseMatrix(r)));
    commit(edited, before, edited.map(r => r.matrix.clone()));
    placeProxy(); onEdit();
  }

  const api = {
    /** Select a piece; with add, toggle it in the selection instead. The last one picked holds the pivot. */
    select(id, add = false) {
      if (!id) picked = [];
      else if (!add) picked = [id];
      else if (picked.includes(id)) picked = picked.filter(p => p !== id);
      else picked = [...picked, id];
      active = picked.includes(id) ? id : picked.at(-1) ?? null;
      regroup();
    },
    setLinked(on) { linked = on; regroup(); },
    /** Hide the handles and ignore them, keeping the selection (while the viewer places pieces). */
    hold(on) { held = on; show(); },
    /** The picked ids (before linked pieces are added) and the one holding the pivot. */
    picks() { return { ids: [...picked], active }; },
    /** Replace the selection, for commands that add or remove pieces. */
    setSelection(ids, pivot = ids.at(-1) ?? null) {
      picked = ids.filter(id => roots.has(id));
      active = picked.includes(pivot) ? pivot : picked.at(-1) ?? null;
      regroup();
    },
    /** Run a viewer command now and make it one undo step. */
    record(command) { command.redo(); undo.push(command); redo.length = 0; refresh(); onEdit(); },
    /** Set render matrices as the gizmo does (keeping each root's edit in step); for commands. */
    applyMatrices(targets, matrices) { apply(targets, matrices); },
    /** Every root that moves with the current selection. */
    selection() { return group; },
    /** These roots split into what moves as one: an actor's components, a locked group, and with linked pieces on, its
     *  linked pieces. */
    units(list) {
      const find = linkFinder(list, linked), out = new Map();
      for (const r of list) {
        const k = find(actorKey(sourceOf(r)));
        if (!out.has(k)) out.set(k, []);
        out.get(k).push(r);
      }
      return [...out.values()];
    },
    /** How many other pieces would move with this one with linked pieces on. */
    linkedCount(id) { return roots.has(id) ? expand([id], true).length - 1 : 0; },
    /** The ids of these roots in the groups a copy takes along: each actor's components with, always, its linked pieces
     *  (the map's own assemblies, not the user's groups). */
    linkedGroups(list) {
      const find = linkFinder(list, true, false), groups = new Map();
      for (const r of list) {
        const g = find(actorKey(sourceOf(r)));
        if (!groups.has(g)) groups.set(g, []);
        groups.get(g).push(sourceOf(r).id);
      }
      return [...groups.values()];
    },
    get active() { return active; },
    setMode(next) { mode = next; show(); onEdit(); },
    get mode() { return mode; },
    toggleSpace() { controls.setSpace(controls.space === 'world' ? 'local' : 'world'); onEdit(); },
    get space() { return controls.space; },
    /** Pivot: 'origin', the active piece's own pivot (usually a corner); 'centre', the selection's middle. `quiet`
     *  skips onEdit (while the page starts). */
    setPivot(next, quiet = false) { pivot = next === 'centre' ? 'centre' : 'origin'; placeProxy(); if (!quiet) onEdit(); },
    get pivot() { return pivot; },
    /** Snap: 'off'; 'fine', steps of 24 units and 15 degrees; 'tile', whole tiles from where a drag started (96
     *  across, 64 up) and 90-degree turns, which for a selection with a ladder, door, car, van or fracturing piece is
     *  the recipe snap (its pose rule). */
    setSnap(next) { snap = next; placeProxy(); applySnap(); },
    get snap() { return snap; },
    /** Whether the selection keeps a pose rule now (the recipe snap: tile snap, and a piece with a rule). */
    get recipe() { return Boolean(ruled()); },
    /** Whether the selection has a piece with a pose rule (a ladder, door, car, van or fracturing piece). */
    get gridPiece() { return Boolean(rule); },
    /** Work out the groups and pose rules again (the map's families arrived). */
    regroup() { regroup(); },
    /** True while the pointer is on a handle or dragging, so a click does not also pick the scene. */
    busy() { return controls.enabled && (controls.dragging || controls.axis !== null); },
    cancel() { if (drag && !cancelled) { cancelled = true; controls.reset(); apply(drag.targets, drag.before); onEdit(); return true; } return false; },
    undo() { step(undo, redo); },
    redo() { step(redo, undo); },
    /** The command the next undo or redo would run, or undefined (a command may say how many pieces it touches: `size`). */
    peekUndo: () => undo.at(-1), peekRedo: () => redo.at(-1),
    resetSelection() { reset(group); },
    /** Roots moved or turned from their base pose (added pieces count from where they were placed). */
    edited() { return [...roots.values()].filter(r => r.userData.edit); },
    /** The selected actor's pose in game units and degrees, or null. */
    pose() { if (!group.length) return null; return gamePose(activeActor()); },
    /** Put the selected actor at a typed game location (units) or rotation (degrees); its group moves with it.
     *  Pass null for the part that stays: a location alone keeps the exact orientation. A rotation alone turns about
     *  the actor's pivot, or with the centre pivot about the selection's middle. One undo step. */
    setPose(location, rotation) {
      if (!group.length || (!location && !rotation)) return;
      if (rotation && boxed()) rotation = [0, Math.round(rotation[1] / 90) * 90, 0];
      const current = activeActor();
      const target = rotation
        ? actorMatrix(location ?? gamePose(current).location, rotation.map(d => d * TURN / 360))
        : current.clone().setPosition(location[0], location[2], location[1]);
      let delta = target.multiply(current.invert());
      // a typed turn with the centre pivot turns about the selection's middle, as a drag on the ring does
      if (rotation && !location && pivot === 'centre') {
        const c = centreOf(group);
        if (c) delta = new THREE.Matrix4().makeTranslation(c.x, c.y, c.z).multiply(new THREE.Matrix4().extractRotation(delta))
          .multiply(new THREE.Matrix4().makeTranslation(-c.x, -c.y, -c.z));
      }
      if (ruled()) delta = recipeMove(delta, actorOf(rule.root), rule.from, rule.origin);
      const targets = group, before = targets.map(r => r.matrix.clone());
      apply(targets, before.map(m => delta.clone().multiply(m)));
      commit(targets, before, targets.map(r => r.matrix.clone()));
      placeProxy(); onEdit();
    },
    /** Forget the history: a project was opened or restored, and its state is the new start. */
    clearHistory() { undo.length = 0; redo.length = 0; onEdit(); },
    canUndo: () => undo.length > 0, canRedo: () => redo.length > 0, undoDepth: () => undo.length,
    controls,
  };
  return api;
}
