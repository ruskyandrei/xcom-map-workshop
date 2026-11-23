### The Buildings view's tick: "Cursor stops at its floors"

A building of the project's (one made from nothing) has a tick in the Buildings view's box panel, **Cursor stops at
its floors** ([index.html](../../tools/viewer/web/index.html), [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js)).
Ticked, the mouse wheel stops once for each of its floors over it, at the height its floor's box starts: the cursor's
floors on the grid follow it ([map_grid.js](../../tools/viewer/web/map_grid.js) `storeysNow` with
[floors.js](../../tools/viewer/web/floors.js) `cursorAreas`), so the yellow lines over it are its own floors' starts;
the panel's line says where they start, the "mouse wheel would not stop" warning is not said of it, a floor starting
at or under the one before it is warned of, and a dragged bottom is no longer pulled to a cursor start near by (its
own follow it). The tick is one undo step, saved as the building's `cursorFloors`
([project.js](../../tools/viewer/web/project.js) `validBuilding`, `tidyBuilding`: kept when true on a building made
from nothing), and goes with a building copied with its pieces ([clipboard.js](../../tools/viewer/web/clipboard.js)),
saved as a prefab and placed from one ([prefab_place.js](../../tools/viewer/web/prefab_place.js)). The map's own
buildings have no tick. A new building starts with it off (`NEW_CURSOR_FLOORS`, the plan's decision D2) until the game
check has passed.

Checked: the browser check `cursor-floors` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py): off at
first, ticked, the floors over the building its own, the panel's line, no miss warning, the record and the project's
state, a floor out of order warned of, Ctrl+Z) with `floor-boxes` and `map-buildings` on a test server;
[map_buildings_test.mjs](../../tools/viewer/tests/map_buildings_test.mjs) for the record; the node suite.
