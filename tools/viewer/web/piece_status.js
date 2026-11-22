// The pose fields and the edit status (refactor stage P9): the edit hub's piece-status refresh (edit_hub.js), after an
// edit, an undo or a selection. The piece panel's pose fields (the gizmo's pose, or a streamed piece's or a view-only
// light's place, read only), the pose and source lines, Delete; while a gizmo handle is held, the drag's run and the
// end of this one (what is seen to move is kept up, the rest waits for the drag's end); then the edit status (what has
// changed, by kind, and whether it is saved; in the builder only whether it is saved), Undo, Redo, Reset and Reset all.
// The pose fields and the edit count share the pose and the count of changes, so they are one refresh.
//
// createPieceStatus takes what it needs of app.js as one argument object, when app.js makes it, after the document
// session: the gizmo, the pose fields (app.js's typed-pose handlers use them too), the count of changes and the save
// state, the Lights view's pose and values of a light. It registers the refresh as it is made and keeps no state.
import { plural } from './dom_words.js';
import { onHub, runHub, STOP } from './edit_hub.js';
import { allRoots, builder, builderMode, cleared, data, groups, selected } from './editor_state.js';
import { isStream } from './piece_records.js';

export function createPieceStatus({ $, changes, gizmo, lightPose, lightViewOnly, poseInputs, saveState,
                                    valuesEdited }) {
  // After an edit, an undo or a selection (the edit hub, edit_hub.js).
  onHub('edit', 'piece-status', () => {
    const pose = gizmo.pose(), count = changes();
    if (pose) [...pose.location, ...pose.rotation].forEach((v, i) => {
      if (document.activeElement !== poseInputs[i]) poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2);
    });
    // while a handle is held, only what is seen to move is kept up: the pieces, the highlight, the pose fields, the
    // grid chip. The status, the save state, the panels, the size line and the warnings wait for the drag's end, which
    // runs this again in full (the gizmo's dragging-changed).
    if (gizmo.controls.dragging) { runHub('drag'); return STOP; }
    // a streamed piece, or a view-only light, is shown, not edited: its place, read only
    const pickedRoot = allRoots.get(selected), pickedSource = pickedRoot?.userData.source;
    const fixedPick = isStream(pickedSource) || Boolean(pickedRoot?.userData.light && lightViewOnly(pickedSource));
    if (fixedPick && !pose) {
      const at = pickedRoot.userData.light ? lightPose(pickedRoot) : pickedSource;
      [...at.location, ...at.rotation.map(r => r * 360 / 65536)].forEach((v, i) => { poseInputs[i].value = (Math.abs(v) < 0.005 ? 0 : v).toFixed(2); });
    }
    { const n = i => Math.round(Number(poseInputs[i].value) || 0);
      $('poseSum').textContent = `${n(0)}, ${n(1)}, ${n(2)} · ${n(4)}°`;
      $('sourceSum').textContent = pickedSource?.actorClass ?? ''; }
    poseInputs.forEach((input, i) => { input.disabled = fixedPick || (i >= 3 && pickedRoot?.userData.light && pickedSource.kind === 'point'); });
    $('editDelete').disabled = fixedPick;
    // (in the builder every piece is the prefab's own, so only whether it is saved is said)
    $('editCount').hidden = builderMode ? !count.total && !builder.doc?.revision : !count.total;
    // a hidden chip keeps no words: with nothing changed it kept "not saved", which a test reading the page's text
    // took for shown
    $('editCount').textContent = $('editCount').hidden ? '' : builderMode ? saveState() : [count.moved && `${count.moved} moved`, count.added && `${count.added} added`,
      count.deleted && `${count.deleted} deleted`, count.lights && plural(count.lights, 'light edit'),
      count.effects && plural(count.effects, 'effect or sound edit'),
      count.grid && `grid ${data.tileGrid.dimensions[0]} × ${data.tileGrid.dimensions[1]}${cleared ? ` × ${data.tileGrid.dimensions[2]}` : ''}`,
      count.zones && 'landing zones changed', count.sound && 'background sound changed', count.buildings && plural(count.buildings, 'building'),
      count.missions && `${plural(count.missions, 'mission object')} moved`, count.spawns && plural(count.spawns, 'spawn point edit'), count.flags && `${plural(count.flags, 'piece')} with flags changed`, count.broken && `${plural(count.broken, 'piece')} broken`,
      saveState()].filter(Boolean).join(' · ');
    $('editCount').title = $('editCount').textContent;        // (whole, where a narrow header cuts the chip's words)
    $('editCount').classList.toggle('warn', saveState() !== 'saved');
    $('editUndo').hidden = $('editRedo').hidden = !(count.total || gizmo.canUndo() || gizmo.canRedo());
    $('editUndo').disabled = !gizmo.canUndo(); $('editRedo').disabled = !gizmo.canRedo();
    $('editReset').disabled = !gizmo.selection().some(r => r.userData.edit || (r.userData.light && valuesEdited(r)) || (r.userData.effect && r.userData.values));
    $('editResetAll').hidden = builderMode || (!count.total && !groups.size && !cleared);
  });
}
