### An effect copy's panel keeps its number fields in view; a collectible's copy reads as mission loot

Two reports from the Discord feedback list (B6 and S15).

- **B6: a copied effect's particle parameters lost their number fields.** In the Effects panel of an effect's copy,
  the value rows ran past the panel's right edge, so the number beside each slider (and Velocity's z) was cut off;
  the original's panel was fine. The panels on the right (`#effectPanel`, `#spawnPanel`, `#volumePanel`,
  `#landingPanel`, `#gridPanel`) are grids with no column set, and an implicit grid column is as wide as its widest
  unwrapped line: the About fold's one-line summary (`.foldval`, no wrap), which for a copy reads "A copy of
  Emitter_38: the Build makes it an actor of its own.", made the column, and with it every row, about 80 pixels wider
  than the panel, whose `overflow-x: hidden` then cut the fields off. [style.css](../../tools/viewer/web/style.css)
  gives those panels one column no wider than the panel (`minmax(0, 1fr)`); the About summary now ends in an ellipsis
  there, its full text in its title as before. The screen's size played no part: the panel is 300 pixels wide at any.
- **S15: a collectible's copy said "Not loot".** The piece panel's chip ([pieces.js](../../tools/viewer/web/pieces.js)
  `lootNote`) still described the copier's copies of before 7 November. Since EXP-20 run 8 the Build makes a
  collectible's copy a collectible in the level's actor list, which the game's loot count walks, and takes a deleted
  one out of it ([compiler.py](../../tools/editor/compiler.py) `LOOT_NOTES`). The chip now reads **Mission loot** for
  a copy as for an original, and its title says that a copy counts, a moved one still counts once, a deleted one no
  longer counts and a damaged one counts as the damaged item. The [guide](../../tools/release/guide/guide.html)'s chip
  table and its kinds of pieces table said the same wrong thing and are corrected.

Checked:
- On a test server (URB_Bar, export 38): Emitter_38's copy, before the fix, laid its panel out 368 pixels wide in a
  288-pixel box with every number field 63 pixels past the edge (as reported); after it, nothing past the edge and
  the original unchanged.
- [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py): `check_effect_values` now checks that the copy's
  panel is no wider than it shows and no value row or field crosses its right edge (it fails without the fix:
  80 pixels wider, 46 rows and fields cut); `check_adding` checks a collectible's copy's chip. The checks
  effect-values, adding, spawns, text-select, floor-boxes, map-buildings, tile-grid, pivot and typed-pose pass.
- The node, repo and release suites.

Known gaps: the browser smoke's effects check didn't run whole here (its wave preview needs a server with a piece
library, and this test server served one export). That a copy counts at the loot screen has still not been seen in
the game (EXP-20 run 10 couldn't end Temple Ship's mission); the chip says what the Build makes.
