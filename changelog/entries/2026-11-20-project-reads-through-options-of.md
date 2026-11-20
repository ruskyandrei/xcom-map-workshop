### A project's added records read through optionsOf

Editor refactor, stage P2: the page's reader of a project's edits (`applyState` in
[app.js](../../tools/viewer/web/app.js), which the prefab builder's opening uses too) makes each added thing from its
record through [piece_records.js](../../tools/viewer/web/piece_records.js)'s `optionsOf`. Nothing the editor makes of a
record changes.

- A copy of a piece: `addedObject`'s options are `optionsOf(record)`, made for each of its parts as before.
- A cover block: `optionsOf(record, 'cover')`, which takes no link, tint, flags or blasts from its record, as before.
- A light (`addedLightOf`): its names, pose, recipe or original and values come from `optionsOf(record, 'light')`. The
  page finds its source (the recipe made, or the map's light it copies) as before.
- An effect, a sound or a lens flare (`addedEffectOf`): from `optionsOf(record, 'effect')`, whose values are the
  page's (`keptValues`). They are now worked out before the page looks for the original, where they were after; the
  conversion has no other effect.

Checked: the browser recording of every kind of piece (the first of these entries says what it holds) gives the same
arguments to `addedObject`, `addedLight` and `addedEffect` as on the commit before, the same options in the same order
included, with the same roots and records. [moved_code.py](../../tools/repo/moved_code.py) over app.js: 808 of its 811
functions are the same, and `applyState`, `addedLightOf` and `addedEffectOf` differ. `web_names` is clean.
