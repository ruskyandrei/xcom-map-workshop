### A piece's whole record written and read in piece_records.js (recordOf, optionsOf)

Editor refactor, stage P2, first step: the page gets one writer and one reader of an added thing's whole record, beside
the conversion of a piece's state that review finding 6 put in the same module. Nothing uses them yet: the writers
and readers of app.js move onto them one by one in the commits after this. Nothing the editor does changes.

- **[piece_records.js](../../tools/viewer/web/piece_records.js)**:
  - `recordOf(unit, path)`: what the page knows of one added thing (a unit) as its record, by the unit's form: a copy
    of a piece (its names, source, components sorted, pose, link tag, partner, state and library recipe), a cover
    block, a recipe light or a copy of a map's light, an effect, a sound or a lens flare. The fields and their order
    are the ones a project, a prefab and the builder's document have always written. The unit's `id` is written only
    when it has one, as a prefab's records have none. `path` is `'project'` (a project and the builder's document)
    or `'prefab'` (a prefab saved from a selection): a prefab has always put a recipe light's values before its pose.
  - `optionsOf(record, form, state)`: a record as what makes its root again. For a piece it gives `addedObject`'s
    options, its state the record's or the one a paste's clip entry carries. A cover block's options take no link,
    tint, flags or blasts from its record. For a light and an effect it gives what `addedLight` and `addedEffect`
    are made from, the page finding the template.
  - It imports `keptValues` from [effects_rules.js](../../tools/viewer/web/effects_rules.js), itself pure: no
    three.js and no page.
- **[piece_records_test.mjs](../../tools/viewer/tests/piece_records_test.mjs)** checks each form's fields and their
  order on both paths, the components sorted in a copy, and each form read back.

Checked: the node test; `web_names` is clean (51 files).
