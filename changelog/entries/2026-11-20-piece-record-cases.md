### Every kind of piece's record held by recorded cases

Editor refactor, stage P2: the node test of [piece_records.js](../../tools/viewer/web/piece_records.js) holds the
records the page's writers gave, and what its readers handed on, before the stage moved them onto `recordOf` and
`optionsOf`.

- **[piece_record_cases.json](../../tools/viewer/tests/piece_record_cases.json)** is new, recorded by a browser script
  on a test server. It uses one scene on the Bar holding every kind of piece:
  - a copy of a door and of its partner, a tinted copy, a copy of two components and a piece of another map;
  - a made wall, a made floor, a ramp and a rock, and a broken copy of a fracturing piece;
  - three cover blocks (high, block, invisible floor);
  - a recipe spot light, a recipe point light and a copy of a map's light;
  - an effect, a sound and a lens flare.

  It holds 57 writer cases and 88 reader cases:
  - the records written before the stage by the project's `editState`, the prefab's `prefabRecords` and the
    builder's `editState`, 19 each, each with the unit `recordOf` is now given for it. A prefab's partner names and
    its move to the prefab's origin come after `recordOf`, and are given beside the case;
  - for the project's and the builder's `applyState`, `prefabClip` and two pastes: the record and state `optionsOf` is
    now given, and what `addedObject`, `addedLight` and `addedEffect` were given before, or the clip's entry.
- **[piece_records_test.mjs](../../tools/viewer/tests/piece_records_test.mjs)** checks each writer case: the record is
  `recordOf`'s, field for field and in the same order. It also checks that each kind is there for each writer. It
  checks each reader case against what was handed on: `applyState`'s options in the same order, a paste's by value,
  and a light's and an effect's actor, entity and values.

- **[app.js](../../tools/viewer/web/app.js)** loses the comments the stage's earlier commits added that only said
  what `recordOf` and `optionsOf` say, and one record of a prefab's light is joined onto one line. app.js is back to
  12,767 lines, its size before the stage. Only comments and a line break changed.

Checked: the node suite. Six breaks planted one at a time in a copy of `recordOf` and `optionsOf` were each caught: a
prefab light's order, the place of a piece's partner, an effect's field order, a cover block given flags, an effect's
values left as saved, and the components left unsorted.
