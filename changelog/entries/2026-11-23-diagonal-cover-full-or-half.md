### Diagonal cover marks give full or half cover, as the panel's Cover says

- The Diagonal cover view's panel has **Cover** (Full, Half; "Full and half" shown where the picked marks' corners
  differ): it sets every corner of the picked marks, one undo step. The game keeps full or half for each corner of a
  tile (the low bit beside each corner's cover bit); the Build used to take it from the wall's height and wrote a
  corner with no wall as full, so a mark by something the rule doesn't take for a slanted wall (a user's mark beside
  a car on the intro map) always came out full.
- A mark keeps its half corners as `low` ([[sx, sy], ...], a subset of `toward`): the project's records, the marks
  that follow their pieces (turned with them), the library's piece record (12: `low` on each mark a piece of another
  map brings), the compiler's lane and the Build (each half corner's low bit; full cover gets no climb). The map's own
  marks show what the map gives; a new mark gives full cover; a corner switched on comes on half where all the mark's
  corners are half. A map's mark set back to its own corners and heights is the map's own again.
- In the view, a half corner's arrow is drawn half as long. The build record says each mark's `half` corners.
- The guide's in-game limits say that a blast takes diagonal cover away: a tile the game works out again after
  something nearby is destroyed loses it, wall or no wall, as the maps' own do (F-149's rebuild, which never writes
  the diagonal flag; research/native/cover-build.md, section 1).
- The help panel's view words now name the rail's Views list (they still named the old rail buttons and flyouts),
  and so does the Clear map window's note on Map grid.
- Where: [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js) (`heightOf`, `setHalf`, `low` through every
  edit), [diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js) (the Cover row, the arrows, the carried marks),
  [index.html](../../tools/viewer/web/index.html), [diagonal_edits.py](../../tools/editor/diagonal_edits.py),
  [native_copy.py](../../tools/bake/native_copy.py) (`diagonal_edit`), [diagonal_keep.py](../../tools/bake/diagonal_keep.py)
  (`mark_cover`, the record), [mark_walls.py](../../tools/bake/mark_walls.py) and [library.py](../../tools/viewer/library.py)
  (`low`, PIECE_VERSION 12), [build.py](../../tools/editor/build.py) (the manifest's `half`), the editor contracts,
  the guide (the Diagonal cover section's Cover, its picture retaken).
- Checked: the node, viewer, editor, bake and repo suites (new: the page rules for heights, the compiler's lane, the
  lane's bits, a farm build with both corners of a mark half: 0x10033), the browser check of the Diagonal cover view
  (Cover set Half and undone), the panel seen on a test server.
- Not seen in the game: a half mark (the game reads the same low bit the map's own half marks have).
