// Align (refactor stage P8): with two or more pieces or groups selected, the others lined up with one of them, the
// target, along the chosen game axes (any of X, Y and Z), their boxes' centres, low edges or high edges meeting. What
// moves as one stays together (a locked group, and with linked pieces on, linked pieces), and the move is one undo
// step. Here: the choices remembered in the browser (alignPrefs, saveAlignPrefs), the units moved and their names
// (alignUnits, unitBox, unitName, unitLabel), the piece panel's Align section with the white box on the target
// (alignPanel, targetHelper) and the move (align).
//
// createAlign takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the scene, the
// pieces that can be copied, a piece's member key and its group (groups.js), the recipe snap's move, and the hints. Its
// own state is inside it (the white box); the target chosen in the panel (alignTarget) is editor_state.js's, since
// app.js's handler of the target list sets it.
import * as THREE from 'three';
import { alignTarget, data, groupIndex, setAlignTarget } from './editor_state.js';
import { recall, remember } from './storage.js';

export function createAlign({ $, copyablePieces, flashHint, gizmo, keepRecipe, liveGroup, memberOf, plural, short,
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
  function alignPanel() {
    const box = $('alignBox'), { units, last, ref } = alignUnits();
    box.hidden = units.length < 2;
    targetHelper.visible = !box.hidden;
    if (box.hidden) { setAlignTarget(null); return; }   // a chosen target lasts while two or more stay selected
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
      // under tile snap, a ladder, door, car or van lines up as near as its pose rule lets it
      const move = keepRecipe(new THREE.Matrix4().makeTranslation(d.x, d.y, d.z), u.map(r => ({ source: r.userData.source, matrix: r.matrix })));
      for (const r of u) { targets.push(r); before.push(r.matrix.clone()); after.push(move.clone().multiply(r.matrix)); }
    }
    const what = `${axes.map(a => a.toUpperCase()).join(', ')} (${by === 'centre' ? 'centres' : by === 'min' ? 'low edges' : 'high edges'})`;
    if (!targets.length) { flashHint(`Already aligned on ${what}`); return; }
    gizmo.record({ redo: () => gizmo.applyMatrices(targets, after), undo: () => gizmo.applyMatrices(targets, before) });
    flashHint(`Aligned ${plural(units.length - 1, 'piece')} with ${unitName(ref)} on ${what} · Ctrl+Z undoes it`);
  }

  return { align, alignPanel, saveAlignPrefs, targetHelper };
}
