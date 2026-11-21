### The factories stage P5 changed import the plain exports they were given

Editor follow-ups, stage P5, after item 3.30: [ARCHITECTURE.md](../../ARCHITECTURE.md)'s rule for factories ("a
change to such a factory imports them") applied to the three whose argument lists the stage changed. Nothing the
editor does changes.

- [delete_reset.js](../../tools/viewer/web/delete_reset.js) imports `cloneGroups` (groups.js) and `selectionWords`
  (selection.js);
- [zones_wiring.js](../../tools/viewer/web/zones_wiring.js) imports `projectsAvailable` (document_session.js) and
  `tileCorner` (map_grid.js);
- [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) imports `HANDLE_PICK` (handles.js),
  `projectsAvailable` and `selectionWords`;

instead of being given them; [app.js](../../tools/viewer/web/app.js)'s argument objects shrink by them. Each is a
plain export (a function or a constant) that reads the shared state when called, so the import is the same function
or value. The views' switching, the fourth factory whose list the stage changed, was given none.

Checked: `web_names` clean; every factory's parameters against its call (61 factories, none differing); the node
suite; the twenty-edit recording (52 steps) and the stage's probe (46 steps) the same as on the stage's start commit;
browser checks `typed-pose`, `groups`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `spawns`,
`reset-all`, `small-defects` and `paste-buildings` pass on the Bar.
