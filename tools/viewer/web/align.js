// Align (refactor stage P8; the custom geometry improvements plan, 3.1 and 3.3, decisions D4, D5 and D12): the piece
// panel's Align section. With two or more pieces or groups selected, the others lined up with one of them, the target,
// along the chosen game axes (any of X, Y and Z), their boxes' centres, low edges or high edges meeting. With one or
// more, its Align to row: Grid (L) puts the selection's pivot on the nearest multiple of the snap setting's steps
// (gizmo.js alignToGrid), Level puts a floor piece's height on its map height's levels (alignToLevel), Game pose puts
// a ladder, door, car, van or fracturing piece on its pose rule (gizmo.js alignToGamePose). What moves as one stays
// together (a locked group, and with linked pieces on, linked pieces), and each is one undo step. Here: the choices
// remembered in the browser (alignPrefs, saveAlignPrefs), the units moved and their names (alignUnits, unitBox,
// unitName, unitLabel), the section with the white box on the target (alignPanel, targetHelper: the edit hub runs it
// after an edit, edit_hub.js) and the moves (align, alignToGrid, alignToLevel, alignToGamePose).
//
// createAlign takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the scene, the
// pieces that can be copied, a piece's member key and its group (groups.js), a floor piece's support and levels
// (level_snap.js),
// the tile grid's corner and lowest level, and the hints. Its own state is inside it (the white box); the target chosen
// in the panel (alignTarget) is editor_state.js's, since app.js's handler of the target list sets it.
import * as THREE from 'three';
import { onHub } from './edit_hub.js';
import { alignTarget, data, groupIndex, selected, setAlignTarget, snapMode, volumeRoots } from './editor_state.js';
import { nearestLevel } from './floors.js';
import { actorMatrix } from './gizmo.js';
import { stepsOf } from './snap_steps.js';
import { recall, remember } from './storage.js';
import { plural, short } from './dom_words.js';

export function createAlign({ $, copyablePieces, flashHint, floorBaseOf, floorSupportOf, gizmo, gridBase, liveGroup, memberOf,
                              world }) {
  // Align (the piece panel, with two or more pieces or groups selected): lines the others up with one of them, the
  // target, along the chosen game axes, any of X, Y and Z: their boxes' centres, low edges or high edges meet. The
  // target is the last one picked (the one the gizmo sits on) unless another is chosen in the panel; a white box marks
  // it in the view. What moves as one stays together: a locked group, and with linked pieces on, linked pieces. Only
  // moves, never turns; one undo step.
  const AXES = { x: 'x', y: 'z', z: 'y' };   // game axis -> the viewer's
  const ALIGN = 'workshop.align';
  const targetHelper = new THREE.Box3Helper(new THREE.Box3(), 0xffffff);
  targetHelper.visible = false; world.add(targetHelper);
  // (alignTarget, the id of a piece of the chosen target or null for the last one picked: editor_state.js)
  function alignPrefs() {
    try { const p = JSON.parse(recall(ALIGN)); if (p && Array.isArray(p.axes)) return p; } catch { /* the defaults */ }
    return { axes: ['x'], by: 'centre' };
  }
  function alignUnits() {
    const units = gizmo.units(copyablePieces()), holding = id => units.find(u => u.some(r => r.userData.source.id === id));
    const last = holding(gizmo.active) ?? units.at(-1);
    return { units, last, ref: holding(alignTarget) ?? last };
  }
  const unitBox = u => { const b = new THREE.Box3(); for (const r of u) b.expandByObject(r); return b; };
  const unitName = u => {
    const g = liveGroup(memberOf(u[0].userData.source)), name = short(data.meshes[u[0].userData.source.mesh].name);
    return g && u.every(r => groupIndex.get(memberOf(r.userData.source)) === g) ? `the group of ${name}` : name;
  };
  // A target's label: its name and where its box's centre is (game X and Y), so two alike are told apart.
  function unitLabel(u, last) {
    const c = unitBox(u).getCenter(new THREE.Vector3()), name = unitName(u);
    return `${name[0].toUpperCase()}${name.slice(1)} · X ${Math.round(c.x)}, Y ${Math.round(c.z)}${u === last ? ' (last picked)' : ''}`;
  }
  // The units holding a floor piece (one component, the map's saved floor on it), each with that piece's root.
  const floorUnits = units => units.map(u => [u, u.find(r => floorSupportOf([r.userData.source]) != null)]).filter(([, r]) => r);
  function alignPanel() {
    const box = $('alignBox'), { units, last, ref } = alignUnits();
    box.hidden = units.length < 1;
    if (box.hidden) { targetHelper.visible = false; setAlignTarget(null); return; }
    // the Align to row, for one piece or more: Level and Game pose where the selection has such a piece
    const s = stepsOf(snapMode);
    $('alignGrid').title = `Move the selection's pivot onto the grid: the nearest ${s.across ? `multiple of ${s.across} across and ${s.up} up, turned to whole steps of ${s.turn}°` : 'tile corner and level, turned to quarter turns (snap is off)'}; one undo step (L)`;
    $('alignLevel').hidden = !floorUnits(units).length;
    $('alignPose').hidden = !gizmo.gridPiece;
    const pair = units.length >= 2;
    $('alignPair').hidden = !pair;
    $('alignFold').textContent = pair ? 'to the target' : '';
    targetHelper.visible = pair;
    if (!pair) { setAlignTarget(null); return; }   // a chosen target lasts while two or more stay selected
    targetHelper.box.copy(unitBox(ref));
    const prefs = alignPrefs();
    for (const a of ['x', 'y', 'z']) $(`align${a.toUpperCase()}`).checked = prefs.axes.includes(a);
    $('alignBy').value = prefs.by;
    $('alignGo').disabled = !prefs.axes.length;
    // The target list: one entry per piece or group selected, the target chosen.
    const select = $('alignTarget'), options = units.map(u => [u[0].userData.source.id, unitLabel(u, last)]);
    if (select.dataset.key !== JSON.stringify(options)) {
      select.replaceChildren(...options.map(([value, label]) => Object.assign(document.createElement('option'), { value, textContent: label })));
      select.dataset.key = JSON.stringify(options);
    }
    select.value = ref[0].userData.source.id;
    $('alignText').textContent = `Moves ${units.length === 2 ? 'the other one' : `the other ${units.length - 1}`} to line up with the target`
      + ' (the white box in the view). X and Y are across the floor, Z is up.';
  }
  function saveAlignPrefs() {
    const axes = ['x', 'y', 'z'].filter(a => $(`align${a.toUpperCase()}`).checked);
    remember(ALIGN, JSON.stringify({ axes, by: $('alignBy').value }));
    $('alignGo').disabled = !axes.length;
  }
  function align() {
    const { axes, by } = alignPrefs(), { units, ref } = alignUnits();
    if (units.length < 2 || !axes.length) return;
    const at = (b, k) => (by === 'min' ? b.min[k] : by === 'max' ? b.max[k] : (b.min[k] + b.max[k]) / 2);
    const goal = unitBox(ref), targets = [], before = [], after = [];
    for (const u of units) {
      if (u === ref) continue;
      const b = unitBox(u), d = new THREE.Vector3();
      for (const a of axes) d[AXES[a]] = at(goal, AXES[a]) - at(b, AXES[a]);
      if (d.lengthSq() < 1e-8) continue;
      const move = new THREE.Matrix4().makeTranslation(d.x, d.y, d.z);
      for (const r of u) { targets.push(r); before.push(r.matrix.clone()); after.push(move.clone().multiply(r.matrix)); }
    }
    const what = `${axes.map(a => a.toUpperCase()).join(', ')} (${by === 'centre' ? 'centres' : by === 'min' ? 'low edges' : 'high edges'})`;
    if (!targets.length) { flashHint(`Already aligned on ${what}`); return; }
    gizmo.record({ redo: () => gizmo.applyMatrices(targets, after), undo: () => gizmo.applyMatrices(targets, before) });
    flashHint(`Aligned ${plural(units.length - 1, 'piece')} with ${unitName(ref)} on ${what} · Ctrl+Z undoes it`);
  }
  // Align to grid (L): the selection's pivot on the nearest multiple of the snap setting's steps from the tile grid's
  // corner and lowest level (the world's middle without a grid).
  function alignToGrid() {
    if (!gizmo.selection().length) { flashHint('Select a piece to align to the grid (L)'); return; }
    const s = stepsOf(snapMode);
    const moved = gizmo.alignToGrid(gridBase());
    flashHint(moved ? `Aligned to the grid (${s.across ? `steps of ${s.across} across, ${s.up} up and ${s.turn}°` : 'whole tiles, levels and quarter turns: snap is off'}) · Ctrl+Z undoes it`
                    : 'Already on the grid');
  }
  // Align to level (decision D5, in Level snap's place): each piece or group holding a floor piece moved up or down so
  // that the floor piece stands at its height in its map moved by whole levels (64), the nearest such height; one undo
  // step.
  function alignToLevel() {
    const targets = [], before = [], after = [];
    for (const [u, r] of floorUnits(alignUnits().units)) {
      const s = r.userData.source;
      const actor = r.matrix.clone().multiply(new THREE.Matrix4().fromArray(s.matrix).invert()).multiply(actorMatrix(s.location, s.rotation));
      const z = new THREE.Vector3().setFromMatrixPosition(actor).y, dz = nearestLevel(z, floorBaseOf([s])) - z;
      if (Math.abs(dz) < 1e-6) continue;
      const move = new THREE.Matrix4().makeTranslation(0, dz, 0);
      for (const p of u) { targets.push(p); before.push(p.matrix.clone()); after.push(move.clone().multiply(p.matrix)); }
    }
    if (!targets.length) { flashHint('Already on its levels'); return; }
    gizmo.record({ redo: () => gizmo.applyMatrices(targets, after), undo: () => gizmo.applyMatrices(targets, before) });
    flashHint('Aligned to its levels: its height in its map moved by whole levels (64 units) · Ctrl+Z undoes it');
  }
  // Align to game pose (decision D4, in the recipe snap's place)
  function alignToGamePose() {
    flashHint(gizmo.alignToGamePose()
      ? 'Aligned to its game pose: whole tiles and storeys and quarter turns from where its original stands, so the Build maps its tiles exactly · Ctrl+Z undoes it'
      : 'Already at a game pose');
  }

  // After an edit (the edit hub, edit_hub.js). (a building's box is not aligned)
  onHub('edit', 'align', () => {
    if (volumeRoots.has(selected)) { $('alignBox').hidden = true; targetHelper.visible = false; } else alignPanel();
  });

  return { align, alignPanel, alignToGamePose, alignToGrid, alignToLevel, saveAlignPrefs };
}
