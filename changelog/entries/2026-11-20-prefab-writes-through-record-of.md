### A prefab's records written through recordOf

Editor refactor, stage P2: the page's writer of a prefab saved from a selection (`prefabRecords` in
[app.js](../../tools/viewer/web/app.js)) writes each piece's record through
[piece_records.js](../../tools/viewer/web/piece_records.js)'s `recordOf`, on its `'prefab'` path: a copy of a piece
(with its library recipe when it is of another map), a cover block, an effect, a sound or a lens flare, and a light,
which a prefab keeps as a recipe light whatever it copied. Nothing the editor writes changes.

How the prefab's records differ from a project's, each kept as it was:
- they have no `id`, so a prefab's units have none;
- a recipe light's `light` comes before its pose (`'prefab'` path);
- a copy of a map's light is saved as a recipe light, with every value and its cone in the Build's ranges, and a point
  light's rotation zeroed (worked out in `prefabRecords`, as before);
- a lens flare's values are never written (`prefabRecords` gives a flare none, as before); a project writes those a
  flare copy holds;
- `from` is a new record of the three names, where a project's piece copy keeps its root's own;
- the partner is named by its name in the prefab, after every piece is named (as before).

Checked: the browser recording of every kind of piece (the entry before this one says what it holds) gives the same
records from all three writers, field for field and in the same order, and the same arguments to the readers, as on
the commit before. [moved_code.py](../../tools/repo/moved_code.py) over app.js: 810 of its 811 functions are the same,
and `prefabRecords` differs. `web_names` is clean.
