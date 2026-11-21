### The ladders' numbers and the document versions held on both sides; a case file for a ladder's ends

Three rules the page and Python each write had nothing tying their copies (follow-ups 6.5 and 3.29):

- **A ladder's climb ends.** [ladders.py](../../tools/viewer/ladders.py) `ends` (the compiler's climb warning) and
  [web/ladders.js](../../tools/viewer/web/ladders.js) `ladderEnds` (the inspector's end marks) each carry
  `TOP_REACH`, `FOOT_BACK`, `END_LIFT` and `TURN`, and `ladders.js`' `addedFloors` copies `FLOOR_THICK` and
  `HEADROOM` from [compiler_tables.py](../../tools/editor/compiler_tables.py). `ladders.js` now exports them (nothing
  else in it changes), and [twin_constants.json](../../tools/viewer/tests/twin_constants.json) holds them as `ladders`.
- **The document versions.** [project.js](../../tools/viewer/web/project.js) and
  [projects.py](../../tools/viewer/projects.py), [prefabs.js](../../tools/viewer/web/prefabs.js) and
  [prefabs.py](../../tools/viewer/prefabs.py) each set their schema version, and each side's tests pinned only their
  own. `twin_constants.json` holds them as `schemaVersions`.
- **A case file for the ends,** [ladder_cases.json](../../tools/viewer/tests/ladder_cases.json): 15 ladders (their
  place, turn, height and grid corner, the floor tiles) and their ends, the tiles and verdicts exact and the points to
  1e-9: every verdict (climbs, no foot, no top, neither), a linked top under the top's own tile, the four quarter
  turns, an eighth, a tall ladder, a top at a storey's height, and three quarter turns on a grid corner at 0, where
  the turn's cosine is a hair under 0 and the top falls in tile -1. A new node test,
  [ladders_test.mjs](../../tools/viewer/tests/ladders_test.mjs), and `ladders.py`'s first test,
  [test_ladders.py](../../tools/viewer/tests/test_ladders.py), read it.

[twin_constants_test.mjs](../../tools/viewer/tests/twin_constants_test.mjs) and
[test_twin_constants.py](../../tools/viewer/tests/test_twin_constants.py) hold both sides to the file.

Checked: node (the two files) and the viewer suite's ladder and twin tests (8) pass; `web_names.py` clean (98 files).
A one-sided change fails the other's test, tried once and put back: `TOP_REACH` 77 in `ladders.js` fails
`twin_constants_test.mjs`; schema version 5 in `projects.py` fails `test_twin_constants.py`; `FOOT_BACK` 17 in
`ladders.js` fails `ladders_test.mjs`; `END_LIFT` 9 in `ladders.py` fails `test_ladders.py`.
