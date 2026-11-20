### Smaller defects in the page put right: warning colour, test keys, pasted buildings, the squad panel, the ladder chip and more

Review finding 34, every item but two: "Build results" and "A failed save cancels the waiting map change" belong to
the document session's work.

- **Warnings drawn dimmer than notes** ([style.css](../../tools/viewer/web/style.css)): `.optionsnote.warn` is now the
  warning colour. That fixes the missions warning, Clear map's warning, the bake note, the squad's problem line and the
  cache's space line.
- **`window.viewer` listed `groundAt`, `screenOf` and `pasteSnapshot` twice** ([app.js](../../tools/viewer/web/app.js)).
  Each is now listed once. `groundAt` keeps its `fromZ = 4096` default (the later key had dropped it), and `screenOf`
  keeps the one that was in effect.
  - [take_shots.py](../../tools/release/guide/take_shots.py) passes the height, so the guide's made-piece site stands on
    the ground, not at 0.
- **Undoing a paste left its copied buildings' names**, so the next paste was named "… copy 2". The undo now takes
  them back.
- **Pasting floor boxes made one undo step per building.** `pasteVolumes` is now one step, which also takes back the
  name of a new building (one made for a building that is gone).
- **Test squad setup after a failed read** ([squad.js](../../tools/viewer/web/squad.js)): Add, Copy, the name box, the
  arrow keys, Export, Import, Reset and Save are off and do nothing. The status line says how to try again.
- **The squad count on plain EW** said "of at most 6" while Add allowed 8. Now the count and Add go by the squad's own
  limit (8), and an install that lands fewer is named beside it ("plain Enemy Within lands at most 6"). Its check still
  says when the squad has more.
- **The ladder chip could contradict the Build's warning.** This was real: turning a roof's Floor off by its flags
  left the chip saying "Climbs". `ladderNow` now counts floor as the compiler's `added_floors` and `ladder_ends` do:
  - a copy whose flags make it no floor (and that collides) gives none;
  - with one of the map's pieces made no floor, the floor tiles of those pieces and of the moved or deleted ones are
    taken out;
  - one of the map's pieces made floor where it stands gives floor;
  - a grown grid's levels count.
- **The Floor field stopped at 8** ([index.html](../../tools/viewer/web/index.html)). It now goes to 10, set from
  `BUILDING_FLOORS_MAX`.
- **A build time of 119.6 s showed "1:60"** ([build_options.js](../../tools/viewer/web/build_options.js)). The panel now
  uses [build_queue.js](../../tools/viewer/web/build_queue.js)'s `clock`. app.js's own copy, in the build status code,
  already rounds down and is left to that work.
- **Reshuffle on a floor could give back the same seed** ([walls.js](../../tools/viewer/web/walls.js)). It now never
  does, as a wall's Reshuffle.
- **An unknown ship type** left the Missions select empty and sent `ship: ''`
  ([missions_panel.js](../../tools/viewer/web/missions_panel.js)). Now it is shown as it is, and OK stays off with a
  warning until a ship is chosen.
- **Two rules for a no-spawn box** ([project.js](../../tools/viewer/web/project.js)): a project's no-spawn box now
  takes each far side past the near one, as the Spawns view and the compiler's `spawn_box` have it. A box under a unit
  thick is no longer dropped at load.
- Checked:
  - node: [walls_test.mjs](../../tools/viewer/tests/walls_test.mjs) for the floor's Reshuffle,
    [build_queue_test.mjs](../../tools/viewer/tests/build_queue_test.mjs) for the clock, and
    [project_spawns_test.mjs](../../tools/viewer/tests/project_spawns_test.mjs), where both no-spawn rules agree.
  - New browser checks in [browser_editing.py](../../tools/viewer/tests/browser_editing.py): `paste-buildings`,
    `squad-read`, `ladder-floor` and `small-defects`.
    - `ladder-floor` fails on the page before this change.
    - `small-defects` covers the warning colour, the Floor field and the unknown ship.
  - The checks `squad`, `spawns`, `clear-map`, `map-buildings` and `recipe` still pass, and so does the node suite.
- Not checked: the guide's shots weren't retaken.
