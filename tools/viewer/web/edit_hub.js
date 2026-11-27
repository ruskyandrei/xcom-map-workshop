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
  // After any edit, undo or selection (editChangedNow, which app.js's editChanged calls: the gizmo calls it after
  // each edit, and the areas after theirs).
  edit: [
    'effects',       // effects_wiring.js: what the Effects view draws is worked out again (its markers follow the
                     // pieces that carry them)
    'diagonal',      // diagonal_wiring.js: the diagonal cover marks drawn again, those that follow their pieces worked
                     // out again, and the view's panel
    'textures',      // made_handles.js: a made piece with a surface aligned to the world, moved or turned, is drawn
                     // again from where it stands, once a drag ends
    'selection',     // selection.js: a command (the undo of a paste, a delete) changed the selection under us: select
                     // follows the gizmo and ends the run, which it ran itself
    'buildings',     // buildings_wiring.js: the project's buildings follow their boxes, the view's panel; a box being
                     // turned ends the run (the gizmo goes back to moving)
    'cutaway',       // cutaway.js: pieces moved, deleted or brought back, once a drag ends; with a selection it ends the
                     // run, which the cutaway's select ran
    'marks',         // selection.js: the selected piece's highlight, its ladder's ends and its grid chip
    'floor-note',    // cover_wiring.js: an invisible floor's height over the ground, once a drag ends
    'piece-status',  // piece_status.js: the pose fields; while a gizmo handle is held, the drag's run and the end of this one;
                     // then the edit status, Delete, Undo, Redo, Reset and Reset all
    'flags',         // flags_panel.js: the piece panel's Flags group
    'kind',          // select_kind.js: Select all of a kind
    'groups',        // groups.js: the group section (none for a building's box)
    'align',         // align.js: the Align section and its white box (none for a building's box)
    'room',          // made_panel.js: the Room section
    'tools',         // navigation.js: the gizmo's buttons, snap, the axes, the pivot and Selected
    'project',       // document_session.js: the project's title, its save state and its draft
    'add-panel',     // clipboard.js: the prefab builder's This prefab tab follows the prefab's pieces
    'lights',        // lights_wiring.js: the lights drawn follow, and their warnings
    'baked-light',   // app.js: the Game look's baked light (baked_light.js): the map's pieces moved, deleted or relit, and
                     // the added ones, lit live (B4)
  ],
  // While a gizmo handle is held, what is seen to move besides the pieces, the highlight and the pose fields
  // (piece_status.js's piece-status runs it, then ends the edit's run: the rest waits for the drag's end).
  drag: [
    'lights',        // lights_wiring.js: the lights drawn follow
  ],
  // The scene's pieces changed (app.js's sceneChanged, after it asks for the sun's shadows again, the groups' pieces
  // now to be worked out again and the Effects view's markers to be redrawn).
  scene: [
    'cutaway',       // cutaway.js: which pieces are drawn and how each is cut
    'ground-grid',   // clear_map.js: the ground grid, drawn again if its pieces changed
    'joins',         // made_handles.js: where made walls meet
    'textures',      // made_handles.js: a made piece with a surface aligned to the world, pasted or put back, is drawn
                     // from where it stands
    'diagonal',      // diagonal_wiring.js: the diagonal cover marks (a mark follows its piece) and the view's panel
    'baked-light',   // app.js: the baked light (baked_light.js): pieces added or put back lit live or by their lightmaps
  ],
  // The project's landing zones changed or were read (clear_map.js: the install's landing lines read as a map opens,
  // a clear done or undone; delete_reset.js: Reset all done or undone, after the cleared run).
  'landing-zones': [
    'zones',         // zones_wiring.js: the zones drawn
  ],
  // Pieces and lights deleted or brought back by one step, done or undone, before it asks for the lights' redraw and
  // sets the selection: a clear (clear_map.js's clearMap, after the landing zones it keeps), a Delete or Reset all
  // (delete_reset.js's deleteNow and resetAll).
  clear: [
    'lights',        // lights_wiring.js: which lights are drawn (those deleted, or brought back)
  ],
  // The cleared mark set (zones_wiring.js's clearedChanged: a clear or Reset all done or undone, a project opened or
  // closed), after it shows the Map menu's items, lets the merged buildings go and asks for the Effects view's redraw
  // (whose mark none of these reads).
  cleared: [
    'mission-picker', // clear_map.js: the header's Mission picker (a project's missions, or none)
    'lights',        // lights_wiring.js: which lights are drawn (a cleared map draws no view-only light: the Build
                     // takes them out)
    'cutaway',       // cutaway.js: the streamed patches' pieces drawn or not (not in the prefab builder)
    'ground-grid',   // clear_map.js: the ground grid, drawn again
    'zones',         // zones_wiring.js: the zones drawn
  ],
  // The project's missions set again (delete_reset.js: Reset all done or undone, after the landing-zones run).
  'project-missions': [
    'mission-picker', // clear_map.js: the header's Mission picker's choices
  ],
  // A landing zone edited in the Landing zones view (zones_wiring.js's setZones, done or undone), after the zones are
  // drawn, before the project's change and the edit run.
  'zone-edit': [
    'ground-grid',   // clear_map.js: the ground grid, drawn again (the ground's height goes by the zones)
    'cutaway',       // cutaway.js: which pieces are drawn (a moved zone's own landing pieces are not)
  ],
  // A no-spawn volume's box dragged by a face handle (buildings_wiring.js, whose handles they are: as the handle moves,
  // and once it is let go with no change).
  'spawn-box': [
    'spawns',        // spawns_wiring.js: the markers and the no-spawn volumes' boxes drawn
  ],
  // The header's mission picked changed: picked in the header (app.js's handler of its select, after it asks for the
  // Effects view's redraw, which none of these reads), or changed with its choices (clear_map.js's
  // refreshMissionPicker).
  mission: [
    'lights',        // lights_wiring.js: which lights are drawn (the streams' among them)
    'spawns',        // spawns_wiring.js: the markers, and the picked marker's gizmo
    'cutaway',       // cutaway.js: the streams shown
  ],
  // The snap setting changed (navigation.js's setSnapMode, given the selected piece's root).
  snap: [
    'grid',          // selection.js: the selected piece's grid chip
  ],
  // select's (selection.js), each where it fills the piece panel for what is picked. Each area's section of the panel
  // shown or hidden for it (given the root picked, or nothing):
  'select-sections': [
    'lights',        // lights_wiring.js: the light section
    'cover',         // cover_wiring.js: the cover section
    'made',          // made_panel.js: the Wall, Floor and Ground sections
    'break',         // made_breaking.js: the Break row of one of the map's fracturing pieces
  ],
  // nothing, a building's box or an effect picked (given the root, or nothing)
  'select-none': [
    'effects',       // effects_wiring.js: the Effects view's markers painted, its panel, the picked one's shape
  ],
  // a light picked (given its root)
  'select-light': [
    'lights',        // lights_wiring.js: its panel
  ],
  // a cover block or invisible floor picked (given its root): showCover's
  'select-cover': [
    'cover',         // cover_wiring.js: its cover section
  ],
  // a piece picked (given its root and its source), before its name and chips
  'select-piece': [
    'made',          // made_panel.js: a made piece's sections
    'break',         // made_breaking.js: the Break row of one of the map's fracturing pieces
  ],
  // a piece's chips (given the chips' row and the root)
  'select-chips': [
    'flags',         // flags_panel.js: the flags chip
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
// Every name of every run has its refresh registered, or this throws, naming those that have none: app.js's startScene
// calls it once the page has started, when every area's module is made, so a registration lost (which its run would
// pass over without a word) fails there, where the browser checks see it.
export function checkHub() {
  const missing = Object.entries(RUNS).flatMap(([run, names]) => names.filter((name, k) => !registered.get(run)[k]).map(name => `${run}/${name}`));
  if (missing.length) throw new Error(`The edit hub has no refresh registered for ${missing.join(', ')}`);
}
// The edit run (app.js's editChanged calls it once it has made the edit event's memo).
export function editChangedNow() {
  runHub('edit');
}
