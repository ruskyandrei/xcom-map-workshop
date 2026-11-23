### The diagonal cover rework warning follows moved mission objects, the kept missions and an added bomb

- **What changed.** The warning triangle on a diagonal cover mark the battle's rework takes
  ([KB-22](../../KNOWN-BUGS.md), [the warning](2026-11-23-diagonal-rework-warning.md)) went by where each streamed
  level's rebuild volumes stand in the original level. Now:
  - **A mission object's volume** (a bomb's, a power node's, a capture point's) stands where the project's move of it
    puts it, as the Build moves it in the stream's copy, its offset from the actor turned with the move; a mission
    object the project deletes takes its volume with it.
  - **Only the missions the variant keeps count** (the project's Missions), so a record it drops warns of nothing.
  - **An added bomb mission** brings its donor's volumes (Slaughterhouse's stream: the bomb's and its eight power
    nodes'), moved with the bomb and the nodes as the project places them.
  - **The words** say, for a bomb's or node's area, that Long War's bomb mutator places the bomb and its nodes itself,
    so their areas may land elsewhere.
  The page and the Build agree on all of it.
- **Where.**
  - Export 42 ([export.py](../../tools/viewer/export.py), [scene_metadata.py](../../tools/viewer/scene_metadata.py)
    `donor_objects`): the bomb donor's `rebuildSpheres`. Maps re-export when opened.
  - [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js) `reworkAreas` (options: cleared, missions, moved,
    label) and `movedCentre`; [diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js) passes the project's
    missions and mission object moves.
  - [diagonal_edits.py](../../tools/editor/diagonal_edits.py) `rework_areas`: the kept missions, the added kinds'
    donors, the compiler's stream moves and deletes.
  - The guide's Diagonal cover section ([guide.html](../../tools/release/guide/guide.html)).
- **Checked.** Node tests (a record dropped, an added bomb's donor, a volume moved ten tiles and turned a quarter, a
  deleted one, the mutator's words); compiler tests (a bomb's volume moved and deleted, the added bomb's donor); the
  donor export's nine volumes named as its mission objects (test_spawn_metadata). In a test server's page on the Bar
  with a Council bomb added: no triangle on a mark at tile (20, 20) until the bomb is moved there, then one naming
  URB_Slaughterhouse_Stream, gone again with the undo. The browser checks `diagonal` and `spawns`; the editor, viewer,
  lab, node and repo suites.
- **Known gaps.** Under Long War the bomb mutator places the bomb and its nodes, with their volumes, where it chooses
  as the mission starts: the warning there holds only where it leaves them.
