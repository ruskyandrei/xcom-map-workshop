### A building's own cursor floors played (EXP-96); new buildings start with the tick on; the guide

[EXP-96](../../research/experiments/EXP-96-building-cursor-floors.md) passed in two hidden runs in the lab copy. On a
reported boat (four floors at the hold, the deck, the cabin floor and its roof, on a cleared map) the mouse wheel
stops once a floor at the boxes' heights and the cutaway follows the stops; on a two-floor tower on URB_Bar the cursor
is carried on and off the building on any floor, a floor the building lacks too, without sticking, and a soldier moves
as before. The camera's floor height lags a step across the building's edge, as it does on the game's own maps with
local cursor volumes ([F-164](../../research/findings-register.md)); a roof's box starts under its slab for the slab
to be cut away with it.

- A building made in the Buildings view now starts with "Cursor stops at its floors" ticked (the plan's decision D2,
  [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) `NEW_CURSOR_FLOORS`); saved buildings keep theirs.
- The guide's section on the cursor's floors says what the tick does and how to lay the boxes
  ([guide.html](../../tools/release/guide/guide.html)); its pictures are not retaken (the box panel's picture lacks
  the new tick).
- [exp96_bar_project.py](../../tools/editor/examples/exp96_bar_project.py) makes the run's URB_Bar project.

Checked: the runs' readbacks against the game log; the browser checks `cursor-floors` (now on at first, off, on, undo),
`floor-boxes`, `map-buildings`, `floors-cut`, `projects`, `prefabs`, `builder`, `paste-buildings`, `reset-all` on the
bar and `walls`, `room-buttons` on the police station (the pair failed once on a Prepare dialog's timing, then passed
together and alone); the guide's test; every suite on the branch before the switch.
