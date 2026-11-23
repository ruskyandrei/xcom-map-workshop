// Stepping through what is under the cursor (Discord S16; the editor controls and clipboard plan, Part B): with the real
// Ctrl key held and the pointer over the view, each notch of the wheel selects the next thing a click at that point
// could pick in the view that is on, nearest first (wheel down further, up nearer, round at either end), instead of
// zooming. One step is one piece, also inside a group: a click takes a group whole, the wheel the piece itself (with
// its actor's parts, its assembly and its linked pieces, which always go together), picked out of its group without
// ungrouping. With Shift as well, what was selected before the stepping stays selected and the stepped thing is added
// to it. Here:
// - the Ctrl key's state, from its own key events (a touchpad's pinch is a wheel event with ctrlKey set and no key
//   down: it still zooms), cleared when the window loses focus;
// - what a click could pick under the pointer in the view that is on (candidates), as one list of distinct things,
//   kept while the pointer stays within a few pixels and the camera still (pick_stack.js);
// - the thing a notch leads to selected through what a click calls, the hint line, and the piece panel filled once
//   the wheel rests (STEP_REST), not at every notch.
// Its pure part (the list, where a notch leads, the words) is pick_stack.js, with its node test.
//
// createPickStep takes what it needs of app.js as one argument object, when app.js makes it (after the views it asks,
// before navigation, whose wheel asks it first): the camera, the gizmo, each view's candidates under a point (pieces,
// lights, effects, spawn markers, floor boxes, landing zones), what a click on each calls, and the hints. Its own state
// is inside it (the Ctrl key, the list kept, the wheel's rest).
import { short } from './dom_words.js';
import { allRoots, data, diagonalOn, effectsOn, gridTool, lightsOn, ownPicked, pickBox, pickedSpawn, pickedZone, pickTool, placing,
         spawnsOn, volumeRoots, volumesOn, wallDrawing, zonesOn } from './editor_state.js';
import { samePlace, stackOf, standing, STEP_REST, stepIn, stepWords } from './pick_stack.js';
import { rootName } from './selection.js';
import { KINDS } from './spawns_view.js';

export function createPickStep({ boxEdgesAt, camera, effectsAt, effectsShown, flashHint, gizmo, lightsAt, pickAll, pickOwn,
                                 pickZone, select, selectStepped, setOwnPicked, setPickedSpawn, spawnEntry, spawnMarkersAt,
                                 spawnsShown, volumesAt, zonesAt }) {
  let ctrl = false, list = null, rest = 0, wheelDelta = 0;
  document.addEventListener('keydown', e => { if (e.key === 'Control') ctrl = true; });
  // (each hold of the Ctrl key steps through a list of its own)
  document.addEventListener('keyup', e => { if (e.key === 'Control') { ctrl = false; list = null; } });
  window.addEventListener('blur', () => { ctrl = false; list = null; });
  const cameraKey = () => camera.matrixWorld.elements.map(v => v.toFixed(2)).join(',');

  // What a click at a screen point could pick in the view that is on, as [{ kind, distance, ... }]: in the normal view
  // the pieces along the ray (every one drawn and not cut away), and the effect, light and spawn markers and the floor
  // boxes' edges where they are drawn; in a view of its own that view's things alone. (The diagonal cover marks are
  // left out: one mark to a tile, nothing lies behind one.)
  function candidates(x, y) {
    const roots = (kind, list) => list.map(({ root, distance }) => ({ kind, id: root.userData.source.id, distance }));
    if (volumesOn) return volumesAt(x, y).map(v => (v.id ? { kind: 'volume', ...v } : { kind: 'own', ...v }));
    if (zonesOn) return zonesAt(x, y).map(z => ({ kind: 'zone', ...z }));
    if (effectsOn) return roots('effect', effectsAt(x, y));
    if (spawnsOn) return spawnMarkersAt(x, y).map(s => ({ kind: 'spawn', key: s.key, distance: s.distance }));
    if (lightsOn) return roots('light', lightsAt(x, y));
    if (diagonalOn) return [];
    return [
      ...(effectsShown() ? roots('effect', effectsAt(x, y)) : []),
      ...roots('light', lightsAt(x, y)),
      ...(spawnsShown() ? spawnMarkersAt(x, y).map(s => ({ kind: 'spawn', key: s.key, distance: s.distance })) : []),
      ...boxEdgesAt(x, y).map(b => (b.id ? { kind: 'box', id: b.id, distance: b.distance } : { kind: 'own', own: b.own, distance: b.distance })),
      ...pickAll(x, y).map(h => ({ kind: 'piece', id: h.object.userData.objectId, distance: h.distance })),
    ];
  }
  // What selecting a thing takes, as a key: two things of one key select the same. A piece, light or effect: its actor
  // with its parts, assembly and linked pieces (never the user's groups: gizmo.looseKeys); a floor box in the normal
  // view its building, whole; anything else itself.
  function keysOf(items) {
    const loose = gizmo.looseKeys(items.filter(i => i.id && i.kind !== 'box' && i.kind !== 'volume').map(i => i.id));
    return items.map(i => (i.kind === 'box' ? `building|${volumeRoots.get(i.id)?.userData.volume.building}`
      : i.kind === 'volume' ? `volume|${i.id}` : i.kind === 'own' ? `own|${i.own.userData.own.building.name}`
      : i.kind === 'spawn' ? `spawn|${i.key}` : i.kind === 'zone' ? `zone|${i.id}` : loose.get(i.id) ?? null));
  }
  // The keys of what is selected now, as keysOf gives them (a spawn point or a zone picked counts where the view that
  // is on picks them: one left picked in a view switched off is none of this view's).
  function selectedKeys() {
    const ids = gizmo.selection().map(r => r.userData.source.id);
    const items = ids.map(id => ({ id, kind: volumeRoots.has(id) ? (volumesOn ? 'volume' : 'box') : 'piece' }));
    const spawnsPicked = spawnsOn || (!volumesOn && !zonesOn && !effectsOn && !lightsOn && spawnsShown());
    return [...new Set([...keysOf(items).filter(Boolean),
                        ...(pickedSpawn && spawnsPicked ? [`spawn|${pickedSpawn}`] : []), ...(pickedZone && zonesOn ? [`zone|${pickedZone}`] : []),
                        ...(ownPicked?.userData?.own ? [`own|${ownPicked.userData.own.building.name}`] : [])])];
  }
  function nameOf(item) {
    if (item.kind === 'own') return `${short(item.own.userData.own.building.name)}, a building of the map`;
    if (item.kind === 'zone') return 'Landing zone';
    if (item.kind === 'spawn') { const o = spawnEntry(item.key)?.record; return o ? `${KINDS[o.kind]?.label ?? o.kind} ${short(o.actor)}` : 'Spawn point'; }
    const root = allRoots.get(item.id);
    return root ? rootName(root) : 'Piece';
  }
  // The thing at `index` selected, as a click would, the piece panel waiting for the wheel to rest. With `base` (Shift
  // held at the list's first notch: the selection then), it is added to that selection, in place of the one stepped
  // to before.
  function choose(item, base) {
    clearTimeout(rest);
    const gizmoKind = ['piece', 'light', 'effect', 'box', 'volume'].includes(item.kind);
    if (!gizmoKind) {
      if (item.kind === 'spawn') setPickedSpawn(item.key);
      else if (item.kind === 'zone') pickZone(item.id);
      else if (volumesOn) { select(null); setOwnPicked(item.own); }
      else pickOwn(item.own, false);
      return;
    }
    // (a floor box in the normal view picks its building, as a click on its edge does; anything else alone)
    const alone = item.kind !== 'box';
    if (base) gizmo.setSelection([...base.ids.filter(id => id !== item.id), item.id], item.id, [...base.loose, ...(alone ? [item.id] : [])]);
    else gizmo.select(item.id, false, alone);
    selectStepped(Boolean(base));
    rest = setTimeout(() => { if (gizmo.active === item.id) select(item.id, false, true); }, STEP_REST);
  }
  /** A wheel event over the view: true when it was the Ctrl key's stepping (then it is done), false for the zoom. */
  function wheel(e) {
    if (!ctrl || !e.ctrlKey || !data || placing || wallDrawing || gridTool || pickTool || pickBox || gizmo.controls.dragging) return false;
    // pixels, lines or pages to notches; a notch is one step (a fine wheel's small deltas add up to one)
    wheelDelta += e.deltaY * (e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 800 : 1);
    if (Math.abs(wheelDelta) < 50) return true;
    const dir = Math.sign(wheelDelta);
    wheelDelta = 0;
    const place = { x: e.clientX, y: e.clientY, camera: cameraKey() };
    if (!list || !samePlace(list.place, place)) {
      const items = candidates(e.clientX, e.clientY), keys = keysOf(items);
      const stack = stackOf(items, item => keys[items.indexOf(item)]);
      list = { place, stack, base: e.shiftKey ? gizmo.picks() : null, held: e.shiftKey ? new Set(selectedKeys()) : null, index: -1 };
    }
    const { stack, held } = list;
    if (!stack.length) { flashHint('Nothing under the cursor to pick'); return true; }
    const { at, among } = list.base ? { at: list.index, among: [] } : standing(stack, selectedKeys());
    list.index = stepIn(stack.length, dir, at, among);
    // (adding, what the selection holds already is passed over: each stop adds something)
    for (let n = 1; held && n < stack.length && held.has(stack[list.index].unit); n++) list.index = stepIn(stack.length, dir, list.index);
    const item = stack[list.index];
    choose(item, list.base);
    flashHint(stepWords(list.index, stack.length, nameOf(item), Boolean(list.base)));
    return true;
  }
  return { wheel };
}
