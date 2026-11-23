### A building's `cursorFloors`: the record, project schema 8 and the compiler

A project building made from nothing may say `cursorFloors: true`: its floor boxes are then the cursor's floors over
it (the rule of [made_cursors.py](../../tools/bake/made_cursors.py)). Project schema 8 brings it
([projects.py](../../tools/viewer/projects.py), [compiler.py](../../tools/editor/compiler.py),
[project.js](../../tools/viewer/web/project.js); the server refuses a save of 1 to 7, and a project of schema 7
builds as it did), and [editor-contracts.md](../../research/editor-contracts.md) says what it does.

The compiler ([floor_edits.py](../../tools/editor/floor_edits.py) `cursor_areas`, `with_made_slabs`;
[building_edits.py](../../tools/editor/building_edits.py) `cursor_floors`) gives the cursor's floors with such a
building's own over it, so every reader of `cursor_storeys` sees what the Build will make. Such a building is not held
to the map's cursor floors (`building-cursor`), and gets instead:
- `building-cursor-order` (a warning): a floor starting at or under the floor before it somewhere, left out of the
  cursor's floors there;
- `building-cursor-volume` (a warning): a stair or turned cursor volume of the map under it, which stays (not on a
  cleared map, whose own go);
- `building-cursor-floors` (a note): where its floors start.
The tick goes to the native edit's building and the report's. A tick that is not a boolean leaves the record out
(`building-shape`); the map's own buildings (`replaces`) bring none.

Checked: [test_compiler.py](../../tools/editor/tests/test_compiler.py) `test_a_building_whose_floors_are_the_cursors`
(the floors over and off a building, each warning and note, the tick in the native edit, a cleared map, a malformed
tick, a map building); the tests that pin the schema number; the editor and node suites, the viewer's project and
twin-constant tests.
