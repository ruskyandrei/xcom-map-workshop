// One home for a view's gizmo (the editor controls and clipboard plan, Part A; Discord S18): the move and turn handles
// of a landing zone, a spawn point or mission object and a diagonal cover mark are made here alike, so that the rail's
// Move, Rotate and Select, G, R and V, Shift+drag for a copy, Esc during a drag, the press's busy test and the Snap
// button's step come with every one of them (UI-GUIDELINES.md, section 2, "The same controls on every thing"). A view
// gives createViewGizmo:
// - at(): where the gizmo stands for what is picked (a view point), or null when nothing is;
// - modes: the modes it has, ['translate'] or ['translate', 'rotate'] (a ring that steps by quarter turns), or a
//   function giving them for what is picked;
// - leastSnap: the least step what it moves takes ('tile': whole tiles across and levels up, for a thing the game keeps
//   per tile), or null to follow the Snap setting; `what` names it for the Snap button's tip;
// - step(delta): the move allowed for a dragged one (game units [dx, dy, dz]); by default the steps in force (the Snap
//   setting, or the least step where that is coarser);
// - preview(change), commit(change), revert(): the drag drawn, made one undo step, and put back. A change is
//   { move: [dx, dy, dz] } (game units, stepped) or { turns: n } (quarter turns of the game's yaw, 1 to 3);
// - copy(change): a Shift+drag's copy put down where the drag ended (the original stays, one undo step), or none
//   where the thing isn't copied; noTurn, noCopy: what the hint says where it does neither (noCopy a function too,
//   giving the sentence, or null where what is picked copies).
// The pieces' gizmo (gizmo.js) joins the list of gizmos through joinGizmo, so that activeGizmo (the one that is up),
// anyGizmoBusy (a press on a handle never also picks) and cancelGizmoDrag (Esc) answer for every gizmo. The list is
// editor_state.js's (viewGizmos). The steps in force are snap_steps.js's (stepsInForce, snapInForce).
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { snapMode, viewGizmos } from './editor_state.js';
import { snapInForce, steppedMove } from './snap_steps.js';

const QUARTER_TURN = Math.PI / 2;

/** A view's gizmo, as the module's comment says. Gives { controls, helper, proxy, place, setMode, mode, busy, cancel,
 *  enabled, leastSnap, what, noTurn, turns, snap }. */
export function createViewGizmo({ camera, dom, world, orbit, at, modes = ['translate'], leastSnap = null, what = '', step = null, preview,
                                  commit, revert, copy = null, noTurn = null, noCopy = null, said = null, flashHint = () => {}, size = 1 }) {
  const modesNow = () => (typeof modes === 'function' ? modes() : modes);
  const stepNow = step ?? (d => steppedMove(d, snapInForce(snapMode, leastSnap)));
  const proxy = new THREE.Object3D(); world.add(proxy);
  const controls = new TransformControls(camera, dom);
  controls.attach(proxy); controls.enabled = false; controls.setRotationSnap(QUARTER_TURN); controls.setSize(size);
  const helper = controls.getHelper(); helper.visible = false; world.add(helper);
  let mode = 'translate', drag = null, shift = false, up = false;     // (up: something picked it stands for)
  dom.addEventListener('pointerdown', e => { shift = e.shiftKey; }, true);
  // Where it stands for what is picked, in the mode it is in ('off': picked, no handles: the rail's Select, V)
  function place() {
    const point = at();
    up = Boolean(point);
    controls.enabled = helper.visible = up && mode !== 'off';
    if (mode === 'rotate' && !modesNow().includes('rotate')) mode = 'translate';      // (what is picked now doesn't turn)
    controls.enabled = helper.visible = up && mode !== 'off';
    if (!point || controls.dragging || mode === 'off') return;
    proxy.position.copy(point); proxy.quaternion.identity(); proxy.updateMatrixWorld(true);
    controls.setMode(mode);
    controls.showX = controls.showZ = mode !== 'rotate';
  }
  /** The mode (the rail's Move, Rotate and Select; G, R and V): false, with the hint, where the thing doesn't turn. */
  function setMode(next) {
    if (next === 'rotate' && !modesNow().includes('rotate')) { if (noTurn) flashHint(noTurn); return false; }
    mode = next; place();
    // (said(mode): the hint a view gives for a mode, or none)
    const words = said?.(next);
    if (words) flashHint(words);
    return true;
  }
  controls.addEventListener('dragging-changed', e => { orbit.enabled = !e.value; });
  controls.addEventListener('mouseDown', () => {
    // (Shift on an arrow drags off a copy, where the thing copies; else it says why not and moves it)
    const copying = shift && controls.mode === 'translate', why = copying ? (typeof noCopy === 'function' ? noCopy() : copy ? null : noCopy) : null;
    if (why) flashHint(why);
    drag = { at: proxy.position.clone(), change: null, key: '', copy: copying && Boolean(copy) && !why, cancelled: false };
  });
  controls.addEventListener('objectChange', () => {
    const d = drag;
    if (!d || d.cancelled) return;
    if (controls.mode === 'translate') {
      const p = proxy.position, moved = stepNow([p.x - d.at.x, p.z - d.at.z, p.y - d.at.y]);     // (game axes: x, y, up)
      p.set(d.at.x + moved[0], d.at.y + moved[2], d.at.z + moved[1]);
      d.change = moved.some(v => v) ? { move: moved } : null;
    } else {
      // a turn about the view's up is the opposite turn of the game's yaw (the view's basis is x, up, y)
      const q = Math.round(2 * Math.atan2(proxy.quaternion.y, proxy.quaternion.w) / QUARTER_TURN);
      proxy.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), q * QUARTER_TURN);
      const turns = ((-q % 4) + 4) % 4;
      d.change = turns ? { turns } : null;
    }
    const key = JSON.stringify(d.change);
    if (key !== d.key) { d.key = key; preview(d.change, d.copy); }
  });
  controls.addEventListener('mouseUp', () => {
    const d = drag;
    drag = null;
    if (d?.change && !d.cancelled) { if (d.copy) copy(d.change); else commit(d.change); }
    else if (d) revert();
    setTimeout(place, 0);       // (the controls end their drag after this event)
  });
  /** Escape during a drag: it is put back and the rest of it ignored. True when there was one. */
  function cancel() {
    if (!drag || drag.cancelled) return false;
    drag.cancelled = true; revert();
    return true;
  }
  const gizmo = {
    controls, helper, proxy, place, setMode, cancel, leastSnap, noTurn,
    get turns() { return modesNow().includes('rotate'); },
    get what() { return typeof what === 'function' ? what() : what; },
    get mode() { return mode; },
    get enabled() { return up; },
    /** A press on a handle, or a drag: a click then picks nothing behind it. */
    busy: () => controls.enabled && (controls.dragging || controls.axis !== null),
    get dragging() { return controls.dragging; },
    /** The snap setting in force for what it moves: its least step where that is coarser than the user's setting. */
    snap: () => snapInForce(snapMode, leastSnap),
  };
  viewGizmos.push(gizmo);
  return gizmo;
}

/** The pieces' gizmo (gizmo.js) in the list: what it answers as a view's gizmo does. */
export function joinGizmo(pieces) {
  const joined = {
    controls: pieces.controls, place: () => {}, cancel: () => pieces.cancel(), leastSnap: null, what: '', noTurn: null, turns: true,
    setMode: next => { pieces.setMode(next); return true; },
    get mode() { return pieces.mode; },
    get enabled() { return pieces.selection().length > 0; },
    busy: () => pieces.busy(), get dragging() { return pieces.controls.dragging; }, snap: () => snapMode, pieces: true,
  };
  viewGizmos.push(joined);
  return joined;
}

/** A gizmo of a thing that is moved but neither copied nor turned (a rock's corner point): busy and cancel only. */
export function joinBusy(controls, cancel) {
  viewGizmos.push({ controls, place: () => {}, cancel, leastSnap: null, what: '', noTurn: null, turns: false, setMode: () => false,
                    get mode() { return 'translate'; }, get enabled() { return false; },
                    busy: () => controls.enabled && (controls.dragging || controls.axis !== null), get dragging() { return controls.dragging; },
                    snap: () => snapMode, point: true });
}

/** The gizmo that is up: a view's, where one stands for what is picked; else the pieces'. */
export const activeGizmo = () => viewGizmos.find(g => !g.pieces && !g.point && g.enabled) ?? viewGizmos.find(g => g.pieces) ?? null;
/** Whether a press is on any gizmo's handle, or a drag goes on (app.js's press handler: the press then picks nothing). */
export const anyGizmoBusy = () => viewGizmos.some(g => g.busy());
/** Escape during a drag of any gizmo: put back. True when one was. */
export const cancelGizmoDrag = () => viewGizmos.some(g => g.dragging && g.cancel());
