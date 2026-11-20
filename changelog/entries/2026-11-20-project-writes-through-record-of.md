### A project's added records written through recordOf

Editor refactor, stage P2: the page's writer of a project's edits writes each added thing's record through
[piece_records.js](../../tools/viewer/web/piece_records.js)'s `recordOf`. The prefab builder's document is written
from the same edit state, so it goes through it too. Nothing the editor writes changes.

- **[app.js](../../tools/viewer/web/app.js)**:
  - `editStateNow` gathers a unit for each added piece while it reads the roots: its names, source, components, pose,
    links, state, and in the builder its library recipe. It gathers one for each cover block too, and makes each a
    record once all its components are read. The sort of every record's components at the end went with it, since
    `recordOf` lists a copy's components sorted (a light copy has one).
  - `lightState` writes a recipe light's record and a light copy's through it.
  - `effectState` writes an effect's, a sound's and a lens flare's through it.
- The overrides of the map's own pieces, lights and effects are written as before: they are not an added thing's
  record.

Checked:
- **Every kind of piece, recorded before and after** by a browser script on a test server: one scene on the Bar
  holding a copy of a door and of its partner, a made wall, a made floor, a ramp and a rock, a broken copy of a
  fracturing piece, a tinted copy, a copy of two components, a piece of another map, three cover blocks, a recipe
  spot light, a recipe point light, a copy of a map's light, an effect, a sound and a lens flare. Ids were made the
  same in each run. These are all the same, field for field and in the same order, as on the commit before:
  - the project's 19 records (`editState`), and the 38 after a copy and paste of them all;
  - the prefab's records and the 57 after it was placed;
  - the builder's document (19 pieces) and its edit state.

  The arguments of `addedObject`, `addedLight` and `addedEffect`, and every added root, are the same too.
- [moved_code.py](../../tools/repo/moved_code.py) over app.js against the commit before: 808 of its 811 functions are
  the same, and `editStateNow`, `lightState` and `effectState` differ.
- `web_names` is clean, and the node suite passes.
