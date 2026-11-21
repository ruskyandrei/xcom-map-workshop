// One snap policy for every editing path (the custom geometry improvements plan, section 3): the steps of the editor's
// snap setting (editor_state.js snapMode, set by navigation.js's setSnapMode) for a move or a size across the floor, one
// up, and a turn, and the helpers each path that steps takes them from. A step is taken on the distance moved from
// where a drag started or a piece stood, so a piece off the grid keeps its offset; with snap off nothing is rounded, to
// fractions of a unit. Game units; a turn in degrees.
import { LEVEL, TILE } from './constants.js';

/** The snap setting's steps: across the floor, up, and a turn (degrees); 0 is continuous. */
export const SNAP_STEPS = Object.freeze({
  off: Object.freeze({ across: 0, up: 0, turn: 0 }),
  fine: Object.freeze({ across: 24, up: 24, turn: 15 }),
  tile: Object.freeze({ across: TILE, up: LEVEL, turn: 90 }),
});
/** A snap setting's steps (an unknown one is snap off). */
export const stepsOf = snap => SNAP_STEPS[snap] ?? SNAP_STEPS.off;
/** A distance in whole steps (the nearest; halves away from zero, as Math.round); a step of 0 leaves it as it is. */
export const stepped = (delta, step) => (step > 0 ? Math.round(delta / step) * step + 0 : delta);
/** A move [dx, dy, dz] (game axes: x and y across, z up) in the snap setting's steps. */
export function steppedMove(move, snap) {
  const s = stepsOf(snap);
  return [stepped(move[0], s.across), stepped(move[1], s.across), stepped(move[2], s.up)];
}
/** A move in the viewer's axes [dx, dy up, dz] in the snap setting's steps. */
export function steppedViewMove(move, snap) {
  const s = stepsOf(snap);
  return [stepped(move[0], s.across), stepped(move[1], s.up), stepped(move[2], s.across)];
}
/** How a move goes under the snap setting, for a hint: "smoothly", "in steps of 24 units", "by whole tiles across and
 *  levels (64) up"; `across` alone (a move on the floor) leaves up out. */
export function moveWords(snap, { across = false } = {}) {
  const s = stepsOf(snap);
  if (!s.across) return 'smoothly';
  if (s.across === s.up || across) return s.across === SNAP_STEPS.tile.across ? 'by whole tiles' : `in steps of ${s.across} units`;
  return `by whole tiles across and levels (${s.up}) up`;
}
/** How a size or a handle's move goes along one axis (`up`: the vertical), for a hint: "smoothly", "in steps of 24
 *  units", "by whole tiles", "in levels of 64". */
export function stepWords(snap, { up = false } = {}) {
  const s = stepsOf(snap), step = up ? s.up : s.across;
  if (!step) return 'smoothly';
  if (!up && step === SNAP_STEPS.tile.across) return 'by whole tiles';
  if (up && snap === 'tile') return `in levels of ${step}`;
  return `in steps of ${step} units`;
}
/** Where a piece placed or pasted stands across the floor: the point [x, y] under the cursor, as a move from `from`
 *  (where the piece stands in the map) in the snap setting's steps across, so a piece keeps its offset from the grid;
 *  with snap off, the point itself. */
export function droppedAcross([x, y], from, snap) {
  const step = stepsOf(snap).across;
  return step ? [from[0] + stepped(x - from[0], step), from[1] + stepped(y - from[1], step)] : [x, y];
}
