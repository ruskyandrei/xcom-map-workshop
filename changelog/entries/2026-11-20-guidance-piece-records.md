### The guidance names piece_records.js as the one writer and reader of a piece's record

Editor refactor, stage P2, its last step: [ARCHITECTURE.md](../../ARCHITECTURE.md) says what the stage made true.

- Section 1, the page: an added thing's record, as a project, a prefab and the builder's document keep it, is written
  and read in [piece_records.js](../../tools/viewer/web/piece_records.js).
- Section 2 gets a row for a new field of an added thing's record. It goes into `recordOf`, `optionsOf` and
  `PIECE_FIELDS`, with a case in the node test, then where a field of the project document goes, and into the
  prefab's check of a piece.
- Section 3, "One home", says what `piece_records.js` is the one home of. "The page" gets the rule itself:
  - writers gather a unit and hand it to `recordOf`, readers hand the record to `optionsOf`;
  - the record's field order is kept, since the saved files and a project's saved key follow it;
  - where the writers differ, the difference is the unit's or the path's.

Checked: the repo suite.
