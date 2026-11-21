// The edit hub (ARCHITECTURE.md, "The page"): what the page keeps up after an edit, an undo or a selection. A panel,
// a button or a mark of one area is not called by name from another: its module registers its refresh here, under
// its name in one of the runs below, as the module is made, and whoever starts the run calls the hub. A run calls the
// refreshes registered in it in the order it lists them, the order the page has always called them in, whatever order
// the modules are made in; a refresh that returns STOP ends the run, and those after it wait for the next one.
// Its own module, and not editor_state.js, so that node can import it (editor_state.js reads the page's address as it
// loads): edit_hub_test.mjs. The top level only declares.

// What a refresh gives back to end its run.
export const STOP = Symbol('STOP');

// Each run, its refreshes in their order, and whose each is.
export const RUNS = {
  // After any edit, undo or selection (app.js's editChanged: the gizmo calls it after each edit, and the areas after
  // theirs).
  edit: [
    'effects',       // effects_wiring.js: what the Effects view draws is worked out again (its markers follow the
                     // pieces that carry them)
    'selection',     // app.js: a command (the undo of a paste, a delete) changed the selection under us: select follows
                     // the gizmo and ends the run, which it ran itself
    'buildings',     // buildings_wiring.js: the project's buildings follow their boxes, the view's panel; a box being
                     // turned ends the run (the gizmo goes back to moving)
    'cutaway',       // cutaway.js: pieces moved, deleted or brought back, once a drag ends; with a selection it ends the
                     // run, which the cutaway's select ran
    'marks',         // app.js: the selected piece's highlight, its ladder's ends and its grid chip
    'floor-note',    // cover_wiring.js: an invisible floor's height over the ground, once a drag ends
    'piece-status',  // app.js: the pose fields; while a gizmo handle is held, the drag's run and the end of this one;
                     // then the edit status, Delete, Undo, Redo, Reset and Reset all
    'flags',         // flags_panel.js: the piece panel's Flags group
    'kind',          // select_kind.js: Select all of a kind
    'groups',        // groups.js: the group section (none for a building's box)
    'align',         // align.js: the Align section and its white box (none for a building's box)
    'room',          // made_panel.js: the Room section
    'tools',         // app.js: the gizmo's buttons, snap, the axes, the pivot and Selected
    'project',       // document_session.js: the project's title, its save state and its draft
    'lights',        // lights_wiring.js: the lights drawn follow, and their warnings
  ],
  // While a gizmo handle is held, what is seen to move besides the pieces, the highlight and the pose fields (app.js's
  // piece-status runs it, then ends the edit's run: the rest waits for the drag's end).
  drag: [
    'lights',        // lights_wiring.js: the lights drawn follow
  ],
};

// what each run's names have registered, by the names' places in RUNS
const registered = new Map(Object.entries(RUNS).map(([run, names]) => [run, names.map(() => null)]));

// `refresh` registered as `name` in `run`. A run or a name RUNS doesn't have, or a name registered already, throws.
export function onHub(run, name, refresh) {
  const slots = registered.get(run), at = RUNS[run]?.indexOf(name) ?? -1;
  if (at < 0) throw new Error(`The edit hub has no ${name} in its ${run} run`);
  if (slots[at]) throw new Error(`The edit hub's ${run} run has its ${name} already`);
  slots[at] = refresh;
}

// The refreshes registered in `run`, in its order, each given `args`; STOP if one ended the run.
export function runHub(run, ...args) {
  for (const refresh of registered.get(run)) if (refresh && refresh(...args) === STOP) return STOP;
  return undefined;
}
