// Stepping through what is under the cursor (Discord S16): with the Ctrl key held, each notch of the wheel over the view
// selects the next thing a click at that point could pick, nearest first. This is its pure part: the list of distinct
// things under the cursor, where a notch leads from what is selected, whether a list is still the one for the place,
// and the hint's words. pick_step.js does the rest (pick_stack_test.mjs).

// How far the pointer may move (screen pixels) before the next notch takes a fresh list from the new place.
export const STEP_SLACK = 4;
// How long the wheel rests (milliseconds) before the piece panel is filled for what it stopped on.
export const STEP_REST = 150;

/** The distinct things under the cursor, nearest first. `hits` ({ id, distance, ... }: a piece's part met by the ray,
 *  a marker or a box near the pointer, `distance` from the camera); `unitOf(hit)` the key of what selecting it takes
 *  (a piece: its actor's parts, its assembly and its linked pieces, never the user's groups), or null to leave it out.
 *  Each thing comes once, at its nearest hit, which stands for it (its fields, and `unit`: its key). */
export function stackOf(hits, unitOf) {
  const seen = new Map();
  for (const hit of [...hits].sort((a, b) => a.distance - b.distance)) {
    const key = unitOf(hit);
    if (key == null || seen.has(key)) continue;
    seen.set(key, { ...hit, unit: key });
  }
  return [...seen.values()];
}

/** The index a notch leads to among `count` things: `dir` 1 the next further (the wheel turned down), -1 the next nearer
 *  (up), round at either end. `at`: the index of what is selected, when the selection is that one thing alone (else
 *  -1). `among`: the indices of the things the selection holds when it is more than one of them (a group picked
 *  whole), of which the first notch takes the nearest. With neither, the first notch down takes the nearest and the
 *  first notch up the furthest. -1 when there is nothing. */
export function stepIn(count, dir, at = -1, among = []) {
  if (!(count > 0)) return -1;
  if (at >= 0 && at < count) return (((at + dir) % count) + count) % count;
  if (among.length) return Math.min(...among);
  return dir > 0 ? 0 : count - 1;
}

/** Where the selection stands in a list: { at, among } for stepIn, from `keys`, the keys of what the selection takes
 *  (as stackOf's `unitOf` gives them). */
export function standing(list, keys) {
  const held = new Set(keys), among = list.flatMap((item, k) => (held.has(item.unit) ? [k] : []));
  return { at: held.size === 1 && among.length === 1 ? among[0] : -1, among: held.size === 1 ? [] : among };
}

/** Whether a list taken at `from` ({ x, y, camera }: the pointer and the camera's key) is still the one for `now`: the
 *  pointer within STEP_SLACK pixels, the camera where it was. */
export const samePlace = (from, now) => Boolean(from) && from.camera === now.camera
  && Math.hypot(now.x - from.x, now.y - from.y) <= STEP_SLACK;

/** The hint while stepping: "2 of 5 under the cursor: Desk_A · wheel for the next · with Shift it is added", or, with
 *  Shift held, "... · added to the selection". */
export function stepWords(index, count, name, adding = false) {
  return `${index + 1} of ${count} under the cursor: ${name} · wheel for the next · ${adding ? 'added to the selection' : 'with Shift it is added'}`;
}
