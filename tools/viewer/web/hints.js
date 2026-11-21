// The hint line under the view (refactor stage P9): one short line of what is going on, in one place. While a gizmo
// handle is held, what is moving and how to back out (dragHint, which the gizmo's dragging-changed calls); a short
// notice that goes after a moment (flashHint: copied, deleted, nothing to paste); and, with nothing else to say, how to
// place the piece being placed or box select's drag (restingHint).
//
// createHints takes `$` and the gizmo when app.js makes it (before the factories that are given the hints; nothing of
// it runs as the page loads). The notice's timer (hintTimer) is editor_state.js's: the keys and the areas' tools clear
// it too.
import { plural, text } from './dom_words.js';
import { hintTimer, levelSnap, ownSet, pickTool, placing, setHintTimer } from './editor_state.js';

export function createHints({ $, gizmo }) {
  // While a gizmo handle is held: one short line on what is moving and how to back out.
  function dragHint(dragging) {
    const hint = $('dragHint');
    clearTimeout(hintTimer);
    if (!dragging) { restingHint(); return; }
    hint.hidden = false;
    hint.replaceChildren(`${gizmo.mode === 'rotate' ? 'Rotating' : 'Moving'} ${plural(gizmo.selection().length, 'piece')} · `
      + `${ownSet.size ? 'the map\'s own building stays where it is (copy it instead) · ' : ''}`);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
  }
  // A short notice in the same place (copied, deleted, nothing to paste); it goes after a moment.
  // (its timer, hintTimer: editor_state.js)
  function flashHint(message) {
    if (gizmo.controls.dragging) return;
    const hint = $('dragHint');
    hint.replaceChildren(message); hint.hidden = false;
    clearTimeout(hintTimer);
    setHintTimer(setTimeout(restingHint, 2500));
  }
  // With nothing else to say: how to place the piece being placed, or nothing.
  function restingHint() {
    const hint = $('dragHint');
    if (pickTool && !placing) {
      hint.hidden = false; hint.replaceChildren('Box select: drag over the ground, around the pieces to take · ');
      text(hint, 'kbd', 'Esc'); hint.append(' cancels');
      return;
    }
    hint.hidden = !placing;
    if (!placing) return;
    const turned = placing.turns ? ` (turned ${placing.turns * 90}°)` : '';
    const storey = $('floor').value !== 'all' ? `floor ${$('floor').value}'s height (the Floor picker)` : 'the level under the cursor';
    const floor = placing.clip.floor != null && levelSnap ? ` · a floor piece: its height snaps to ${storey}` : '';
    hint.replaceChildren(`Placing ${placing.clip.name}${turned}${floor} · click to place · R turns · Shift+click places more · `);
    text(hint, 'kbd', 'Esc'); hint.append(' stops');
  }

  return { dragHint, flashHint, restingHint };
}
