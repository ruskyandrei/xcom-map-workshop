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
