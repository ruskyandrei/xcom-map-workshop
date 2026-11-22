### A made floor says which tiles it is floor on, and a turned one's cursor floors stand in steps

EXP-90's floors read offline from the built package (F-147). Floor B's collision is its exact shape (four boxes round
its hole) and its cursor floors are its footprint's box; nothing of the Build rounds it to tiles. The tiles it covers
29% and 24% have their centres off it, and the game looks for a tile's floor with one line down through the tile's
centre (the native code notes), so they are no floor: the game's rule, not ours. Floor E (turned 20 degrees) had one
turned collision box and its cursor floors in the box round it (floors breaking at 190 there, at the map's 210 round
it); the readings near its corners were those of tiles it covers in part, and nothing showed the box's corners, but
the cursor floors now follow the slab.

- The rule, on plain numbers: [made_cursors.py](../../tools/bake/made_cursors.py) `outline`, `tiles` (the tiles a slab
  is floor on, by their centres, out of its holes, and those it reaches into by more than 2 short of their centres,
  with how much of each it covers) and `steps` (a turned slab as a box round its part of each tile it reaches);
  [floors.js](../../tools/viewer/web/floors.js) `slabOutline`, `slabTiles` and `slabSteps` are the twins, with the
  cases both read, [slab_tiles_cases.json](../../tools/bake/tests/slab_tiles_cases.json) (B and E among them), and
  `slabTileWords`.
- The compiler: [made_edits.py](../../tools/editor/made_edits.py) `made_slab_tiles` notes `slab-edge-tiles` (a made
  floor covering tiles at its edge in part, short of their centres: no floor at its height, the tiles named at the
  game's level), run by [compiler.py](../../tools/editor/compiler.py) after `made_tilted`. `made_slab_boxes` gives a
  slab turned off the quarter turns about the vertical in steps on the game's grid, so its cursor floors (the floor
  family's `cursor_storeys`) follow it; `slab-turned` is a note now, saying how many boxes they stand in (it was a
  warning that the box round it might put the cursor beside it).
- The Build: `made_cursors.build_slabs` gives the copy tool the same slabs, from the record of each made piece and its
  copy's pose and numbers; [native_copy.py](../../tools/bake/native_copy.py) `floors_and_cursors` calls it (a small
  hunk). An unturned slab's box is as before.
- The page: the Floor section's line ends "floor on N of M tiles" where it covers tiles in part, and its notes say
  why ([made_panel.js](../../tools/viewer/web/made_panel.js)); the tile grid round a picked made floor fills the tiles
  it is floor on and outlines those it covers in part, its note "N floor tiles + M in part: no floor"
  ([cutaway.js](../../tools/viewer/web/cutaway.js), from [made_handles.js](../../tools/viewer/web/made_handles.js)
  `slabTilesOf`); the cursor's floors the page keeps ([map_grid.js](../../tools/viewer/web/map_grid.js)) take a turned
  slab's steps (`slabStepsOf`). A test hook, `cursorStoreys`.

Checked: [test_made_cursors.py](../../tools/bake/tests/test_made_cursors.py) (the cases, EXP-90's readings, E's twelve
steps beside it 13,587 square units against the box's 38,507, `build_slabs`, and the page's split of the steps),
[shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs),
[floor_rules_test.mjs](../../tools/viewer/tests/floor_rules_test.mjs),
[test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (B's note, nothing for whole tiles, E's steps
the Build's too); the editor, node, viewer, repo suites and the bake suite's cursor tests; `web_names.py`; the
`made-openings` browser check (a free floor off the tile lines: its line, notes and drawn tiles as the Build's rule has
them; a turned one: its cursor floors over the steps' area) and `walls`, `api-names`, on a test server.
`build_outputs.py` against `04b9ee4`: the eleven inputs' quick and baked Builds byte for byte. `compile_record.py`
against `04b9ee4`: eleven tests whose made floors stand off the test scene's tile lines each gain one `slab-edge-tiles`
note after their other notes, nothing else of them changed; the test of a turned slab (renamed) has `slab-turned` among
its notes instead of its warnings, and two `slab-edge-tiles` notes, its spec and native edit the same; three new tests.

Known gaps: not played. A turned slab's steps make more cursor volumes (EXP-90's project: 108 against 36). A turned
slab the Build cuts into pieces has its steps worked out piece by piece in the Build and the compiler, and whole on the
page, which can differ in a tile on a cut. The cursor reading E's height once over a tile it covers in part (z 262,
four over its top's) is put down to the mouse's pick along its ray (F-135), not read in the code.
