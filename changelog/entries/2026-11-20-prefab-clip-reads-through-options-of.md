### A prefab placed reads its records through optionsOf

Editor refactor, stage P2: `prefabClip` in [app.js](../../tools/viewer/web/app.js), which reads a saved prefab into the
clip a placing pastes, reads each piece's record through
[piece_records.js](../../tools/viewer/web/piece_records.js)'s `optionsOf`. Nothing a placed prefab makes changes.

- A copy of a piece: its clip entries take their pose, `unit` (its actor), `link` (its link tag), `partner` and state
  from `optionsOf(record, 'piece', stateOf(record))`.
- A cover block: its entry's `unit`, and its `link` and `partner` (none), from `optionsOf(record, 'cover')`.
- A recipe light: its recipe, values and pose for the recipe light come from `optionsOf(record, 'light')`.
- An effect, a sound or a lens flare: its original, pose and values from `optionsOf(record, 'effect')`. Its values
  are still placed only where their family builds, and never for a lens flare.

Checked: the browser recording of every kind of piece (the first of these entries says what it holds) gives the same
clip entries (unit, key, link, partner, state, values, source and matrix of each), the same arguments of the paste
that places them, and the same records after, as on the commit before.
[moved_code.py](../../tools/repo/moved_code.py) over app.js: 810 of its 811 functions are the same, and `prefabClip`
differs. `web_names` is clean.
