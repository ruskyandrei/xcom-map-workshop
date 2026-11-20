### A prefab saved from a selection keeps its made pieces and broken copies; one conversion for a piece's record

Review finding 6. A drawn wall, floor, roof or ground shape saved into a prefab from a selection was stored and placed
again as a plain copy of its donor, and a broken copy of a map's fracturing piece lost its blasts, with nothing said.
Test in game built them as their donors too.

- [piece_records.js](../../tools/viewer/web/piece_records.js) is the one conversion between a piece as the page holds
  it (its tint, flags, made numbers and blasts) and its record. The clipboard (`snapshot`, `pasteSnapshot`), a project
  (`editState`, `applyState`), a prefab saved from a selection (`prefabRecords`), the prefab builder's document and a
  prefab placed (`prefabClip`) all use it, so none of them can leave a field out. It is the first module taken out of
  [app.js](../../tools/viewer/web/app.js), which also takes `PIECE_FIELDS`, `MADE_KINDS` and `cloneBlasts` from it.
- A clip's entry now carries the piece's `state`. The placing preview draws a prefab's made pieces from their own
  meshes, which `prefabClip` asks for before the preview shows.
- Prefab files are schema 4: a copied piece may have `generated`, `blasts` and `breaksFurther`, as a project's added
  record has them. [prefabs.py](../../tools/viewer/prefabs.py) reads schema 1 to 4 and stores 4. It checks a made
  piece's numbers as data only (a kind it knows, then numbers, words and short texts, bounded), and the compiler
  checks what they mean. [prefabs.js](../../tools/viewer/web/prefabs.js) writes 4. The
  [contracts](../../research/editor-contracts.md) say so.
- [prefab_stage.py](../../tools/editor/prefab_stage.py) passes the three fields to the test's project, so Test in
  game builds the pieces as they are.
- Checked: [piece_records_test.mjs](../../tools/viewer/tests/piece_records_test.mjs) round-trips a wall with an
  opening and a blast, a floor with a hole, a ramp, a rock with moved points and a broken copy.
  [test_prefabs.py](../../tools/viewer/tests/test_prefabs.py) saves and reads them back and refuses malformed ones, and
  [test_prefab_stage.py](../../tools/editor/tests/test_prefab_stage.py) checks they reach the test's project. The new
  browser check `made-prefab` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py), through
  `browser_smoke.py --only made-prefab`) pastes those pieces on the Bar, saves the selection as a prefab, places it
  again and compares every record. It also compares the placing preview's size with the pieces placed, and checks
  that the builder opens the prefab unchanged. Two prefab checks in `browser_smoke.py` now expect schema 4. The
  `prefabs`, `prefab_effects`, `builder` and `prefab-test` checks pass. The `prefab-test` check's stand-in play status
  now carries the game install that the Game menu's Installs section reads
  ([browser_prefab_test.py](../../tools/viewer/tests/browser_prefab_test.py)). Before, the check failed on every page
  it opened with "Cannot read properties of undefined (reading 'folder')".
- Not checked in the game: a prefab holding a made wall and a broken copy built through Test in game.
