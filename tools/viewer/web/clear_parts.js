// The parts of a map a clear takes (private/plans/todo/modular-clear-plan.md, section 2): the rules the page shares for
// them, with no state of its own (clear_map.js makes the clear and its window; editor_state.js keeps the parts the
// project cleared).
//
// A project's `cleared` (schema 9) is { part: { keepOutside?: true } } for the parts of CLEAR_PARTS it cleared, the
// marks the Build acts on (tools/bake/native_copy.py CLEAR_PARTS): its pieces and ground, its lights, its effects and
// sounds, its triggers and sight points. `keepOutside` says that part's clear left what stands wholly outside the play
// area. `cleared: true` (schema 1 to 8) is every part, `clearKeepsOutside` on each and the triggers left out with
// `clearKeepsTriggers`. The window's other rows, the spawn points and the landing zones, leave no mark: a clear deletes
// them by records, as a hand edit does.

// the parts the project marks, in the order the Build and the window name them (the compiler's mission_edits.py
// CLEAR_PARTS and the server's projects.py, pinned in tests/twin_constants.json)
export const CLEAR_PARTS = ['pieces', 'lights', 'effects', 'triggers'];
// the Clear map window's rows, in its order
export const WINDOW_PARTS = ['pieces', 'lights', 'effects', 'spawns', 'zones', 'triggers'];
export const PART_LABELS = { pieces: 'Pieces and ground', lights: 'Lights', effects: 'Effects and sounds', spawns: 'Spawn points',
                             zones: 'Landing zones', triggers: 'Triggers and scripts' };

/** The parts a document or an edit state names as cleared, tidied: { part: {} | { keepOutside: true } } in
 *  CLEAR_PARTS' order, or null for none. Reads schema 9's record (a part it doesn't know, or one that isn't a record,
 *  is left out) and schema 1 to 8's `cleared: true` with its two ticks. */
export function clearedPartsOf(state) {
  const c = state?.cleared;
  let parts = null;
  if (c === true) {
    const keep = state.clearKeepsOutside === true;
    parts = Object.fromEntries(CLEAR_PARTS.filter(k => !(k === 'triggers' && state.clearKeepsTriggers === true))
      .map(k => [k, keep ? { keepOutside: true } : {}]));
  } else if (c && typeof c === 'object' && !Array.isArray(c)) {
    parts = Object.fromEntries(CLEAR_PARTS.filter(k => c[k] && typeof c[k] === 'object' && !Array.isArray(c[k]))
      .map(k => [k, c[k].keepOutside === true ? { keepOutside: true } : {}]));
  }
  return parts && Object.keys(parts).length ? parts : null;
}

/** Whether `parts` (clearedPartsOf's) has `part` cleared. */
export const partCleared = (parts, part) => Boolean(parts?.[part]);
/** Whether `part`'s clear kept the scenery outside the play area. */
export const keepsOutside = (parts, part) => parts?.[part]?.keepOutside === true;

/** The parts cleared after a clear of `asked` (window parts; those of CLEAR_PARTS are marked) over `before`
 *  (clearedPartsOf's), the clear keeping the outside or not: a part cleared twice keeps the outside only if both clears
 *  kept it (the first one took what stood out there). null for none. */
export function partsAfter(before, asked, keepOutside) {
  const out = { ...(before ?? {}) };
  for (const k of CLEAR_PARTS) {
    if (!asked.includes(k)) continue;
    out[k] = keepOutside && (!before?.[k] || before[k].keepOutside === true) ? { keepOutside: true } : {};
  }
  return clearedPartsOf({ cleared: out });
}
