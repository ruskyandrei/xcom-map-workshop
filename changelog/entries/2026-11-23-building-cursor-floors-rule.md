### A building's floor boxes as the cursor's floors: the rule and its twin

The first stage of cursor floors a building brings for itself (a mapper's boat, where the mouse wheel was to stop on
the hold, the deck, the cabin and its roof). A building whose floors are the cursor's is an `area` of the made
floors' cursor rule ([made_cursors.py](../../tools/bake/made_cursors.py) `split`, `storeys`, `apply`): the map's
cursor volumes it crosses stand again round its footprint, and over it the floors are its own, cell by cell
(`building_breaks`). Floor k starts 2 under the bottom of its box over the cell (as a made slab's floor starts under
its underside), ends where the next floor over the cell starts, the last at its box's top, and keeps the building's
floor number, so a cell an upper floor alone covers starts at that floor, as the game's own maps do. A floor starting
at or under the one before it is left out there (`unordered`). A made slab inside such a building brings no break of
its own there; of two such buildings over one cell the first has it; a stair or turned volume under one is reported.
Each floor is laid as few boxes as its cells make. The page's twin is [floors.js](../../tools/viewer/web/floors.js)
(`madeStoreys` and `cursorStoreys` take `areas`; `buildingBreaks`, `buildingUnordered`, `cursorAreas`). Nothing uses
it yet: the record, the compiler, the Build and the page follow.

Checked: [building_cursor_cases.json](../../tools/bake/tests/building_cursor_cases.json), nine cases (the report's
boat, an L-shaped floor, a gap, floors out of order, an overhang, a made floor half inside, two buildings over one
cell, a stair, a map with no cursor volumes), passed by
[test_made_cursors.py](../../tools/bake/tests/test_made_cursors.py) and
[shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs); the made floors' own cases unchanged
(`bake -k made_cursors`, the node suite's floor and shared cases).
