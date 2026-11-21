### A map's own landing stays where the map has it while its zone does (KB-13 fixed)

The editor and the Build took a map's own landing as moved, with nothing changed, on most maps: 89 of the install's
141 landings with a frame, on 71 maps. Both compared the landing's six soldier points with where LWR's landing-zone
mutator lays them out for the zone, and on those maps the points stand elsewhere: on the police station on raised
ground, on many maps a third of a tile off, on some in a layout of their own. In the view the landing's Skyranger,
frame, dust and sound were hidden as moved (seen on the police station as it opened). A Build of a project that
changes its landing zones moved such a landing's soldier points, evac volume, player start and PointInSpace onto the
layout, up to 384 units across or down from raised ground.

- [spawns.js](../../tools/viewer/web/spawns.js) `landingUnmoved` and [native_spawns.py](../../tools/bake/native_spawns.py)
  `unmoved` now compare the zone's layout with the layout of the landing's own zone, the one its frame gives: the same
  direction, and the frame and the six soldier points within 4 units. The map's own soldier points are not compared,
  so an unmoved landing keeps them; a zone moved, turned or of another kind still moves the landing.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-13 taken out. [T-51](../../research/findings-register.md) says what was
  found and fixed.

Checked: new cases in [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) and
[test_native_spawns.py](../../tools/bake/tests/test_native_spawns.py) failed before the fix (soldier points off the
layout across, higher and in another layout; the police station's and the Boulevard's own landings read from the
install). A survey of the install's 96 base maps: 89 of 141 landings read as moved before, 0 after. In the page on a
test server the police station opens with nothing listed as moved and its Skyranger and frame drawn; the browser
checks `spawns` and `streams` on the police station and `clear-map`, `spawns`, `effects` and `reset-all` on the Bar
pass. Every suite passes.

Known gap: the `clear-map` check still stops on the police station, at a later step: a landing zone's first drag puts
its ground on a level of the grid, and the police station's own zone stands 16 under the first level, so it rises by
16 where the check expects the height kept. Not played in the game: the Build no longer moves an unmoved landing, which
leaves the map as it was.
