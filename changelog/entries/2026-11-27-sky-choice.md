### The time of day's sky: another map's dome in place of the map's own

Stage T-S6 of the game-likeness plan: the Map settings window's Sun, moon and sky section has a Sky row. A project can
keep the map's own sky, take the sky dome of one of the game's maps, or let the time of day pick one as the bar
moves. The editor draws the chosen sky in the Game look, and the Build brings its dome from its map.

- **The skies offered** are the curve's new `domes` ([sun_curve.json](../../tools/viewer/sun_curve.json)), each the
  dome of one of the game's maps, from T-S0's survey. They are grouped as day (the noon sky of URB_TruckStop_EWI, a
  dynamic day sky), low sun (the dusk sky) and night (the night sky, the terror maps' night sky, a clear night sky).
  Follows the light takes the first sky of the group the bar's time is in: night while the moon is up, low sun while
  the sun is under 20 degrees, day above.
- **The record**: the project's `sun` gains `dome` (schema 10, not released yet). It is `{map, actor}`, with
  `follows: true` beside them when the time picks it, or `{follows: true}` alone where the time's pick looks as the
  map's own domes already do. A dome of the map itself is the map's own sky. The shape is held on both sides by the
  shared [sun_record_cases.json](../../tools/viewer/tests/sun_record_cases.json):
  [sun_curve.py](../../tools/viewer/sun_curve.py) `dome_shape` and [sun_rules.js](../../tools/viewer/web/sun_rules.js)
  `validDome`. The rules (`skyGroups`, `skyAt`, `skySet`, `skyChoice`, `skyWords`, the map's own domes in `ownSun`) are
  sun_rules.js's. A moved bar keeps a chosen sky, and re-picks one that follows the light. As the map has it takes
  the sky back too.
- **The page**: the Sky row ([sun_settings.js](../../tools/viewer/web/sun_settings.js),
  [index.html](../../tools/viewer/web/index.html)) is a select in the section's own style. It is hidden on a map with
  no dome of its own, and each choice is one undo step. [sun_wiring.js](../../tools/viewer/web/sun_wiring.js) draws
  the chosen dome in the Game look where each of the map's own stands, at its turn, in the chosen dome's own scale. The
  dome is read as any piece of another map is, and the copies are never picked. The map's own domes are no longer
  drawn while the copies stand ([cutaway.js](../../tools/viewer/web/cutaway.js)).
- **The compiler** ([light_edits.py](../../tools/editor/light_edits.py) `dome_mark`): each of the map's own shown
  domes is taken out (an exact hide). A copy of the chosen dome is made where it stood, as a piece of another map
  (`Compiler.add`; [compiler.py](../../tools/editor/compiler.py)'s `foreign_piece` asks the library for it as a sky,
  as it does for the prefab test's backdrop). The copies are kept apart from the compiler's own, so no check of pieces
  in the way, on a floor or in a building reads a backdrop 127,000 units across. They join the spec's copies. A dome
  that can't be had is left out on the record `sun.dome`, and the map keeps its own sky. The report's `sun.dome` says
  what was replaced.
- **The Build** makes them as it makes any copy of another map (the transplant stage stages the dome) and any hide,
  with two changes in [native_copy.py](../../tools/bake/native_copy.py):
  - A hidden piece that collides with nothing gets no rebuild volume (F-201).
  - A hidden sky dome is not passed to the relight as a removed caster. Bar's turned-over dome casts in the bake's
    model, and its box would have made a Build with baking relight the whole map.
- **EXP-99's project** takes `--sky` ([exp99_project.py](../../tools/editor/examples/exp99_project.py)).
  [build_outputs.py](../../tools/editor/tests/build_outputs.py) holds the sky with it (input `bar-sky`: 13:00 and the
  noon sky).
- Documents: the `sun` row of [editor-contracts.md](../../research/editor-contracts.md), and
  [ARCHITECTURE.md](../../ARCHITECTURE.md) (the family, the time of day's row, the rebuild volume's row). Findings
  F-201 and F-202.
- Checked:
  - [test_compiler_sun.py](../../tools/editor/tests/test_compiler_sun.py): the noon dome brought where Bar's two domes
    stood, asked as a sky; the two taken out; the ground plane and a hidden dome left; nothing warned of. A dome that
    can't be had left out, and nothing to build for one that follows with the map's own sky, a dome of the map itself,
    or a map with no dome.
  - [test_native_copy.py](../../tools/bake/tests/test_native_copy.py) on the install's URB_Bar: the dome hidden with no
    rebuild volume, and the hidden domes not in the relight's command.
  - [test_sun_curve.py](../../tools/viewer/tests/test_sun_curve.py): each sky the survey map's dome with its material.
  - [sun_rules_test.mjs](../../tools/viewer/tests/sun_rules_test.mjs): the groups, the time's pick, a choice kept and
    followed as the bar moves.
  - The browser check `sky-choice` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) on a test server
    with Bar at export 45: the noon sky drawn twice in place of Bar's two domes, in the Game look alone; Follows the
    light at night and at noon; one undo step each.
  - A quick Build of EXP-99's project with the noon sky, read back: Bar's two night domes out of the level's list, two
    noon domes at their places and turns, the tile data as it was, no rebuild volume. A Build with baking of it in
    9 s: the relight reached no piece of the map (it wrote the two copies' own shadow maps).
  - `build_outputs.py`, recorded on the stage's base and on the change: the thirteen inputs before it the same, byte
    for byte, quick and baked.
- Known gaps: not seen in the game (the requester's game look). The copies take the chosen dome's own scale, so Bar's
  small dome under the map becomes a full-size one (F-202). The editor's view draws the sky only in the Game look, as it
  draws the map's own.
