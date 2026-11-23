### A diagonal cover mark the battle's rework takes away shows a warning triangle (KB-22 warned of)

- **What changed.** A map's streamed levels (Long War's patch levels, a mission's own) work some areas of the map out
  again as every battle starts, and the game never writes diagonal cover back, so a mark there gives no cover in the
  game ([KB-22](../../KNOWN-BUGS.md)). The editor now says so; the Build still writes the mark as before.
  - **On the map:** a yellow warning triangle stands on every such mark's tile, picked or not, in the Diagonal cover
    view and with View options' Diagonal cover.
  - **The picked mark:** the areas that take it are drawn dashed in yellow at its floor, labelled
    "<level> reworks this area"; pointing at its triangle gives the tooltip "No cover in the game: Long War's patch_farm
    reworks this tile at every battle's start"; and its panel says why, under its tile, and to move it off the area.
  - **The Build** warns of it (`diagonal-mark-reworked`, one warning a level, its tiles named).
  - A cleared map streams no patch level ([KB-23](2026-11-23-kb23-cleared-map-drops-patches.md)), so their areas warn of
    nothing there; a mission's own level still does.
  The design is the user's pick from three mockups (a badge on the tile, plus the area when the mark is picked).
- **Where.**
  - Export 41 ([export.py](../../tools/viewer/export.py), [scene_metadata.py](../../tools/viewer/scene_metadata.py)
    `rebuild_spheres`): each streamed package's rebuild volumes as the battle reads them (`streams[<name>].rebuildSpheres`:
    centre and sphere radius, findings register F-150). Maps re-export when opened.
  - [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js) `reworkAreas`, `reworkedBy`, `reworkWords`: the
    areas as tile boxes (centre ± radius on every axis, floored from the game's tile corner) and the words.
  - [diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js): the triangle, the dashed areas and their labels,
    the tooltip and the panel line ([index.html](../../tools/viewer/web/index.html) `#diagonalRework`,
    [style.css](../../tools/viewer/web/style.css)); the page's help names the triangle; a test hook,
    `viewer.diagonalWarnings()`.
  - [diagonal_edits.py](../../tools/editor/diagonal_edits.py) `rework_areas`, `reworked`: the Build's warning.
  - The guide's Diagonal cover section and its in-game limits ([guide.html](../../tools/release/guide/guide.html)).
- **Checked.** The export's reading against the Build's (`native_copy.volume_sphere`) on all 409 rebuild volumes of
  the install's 90 patch levels: the same centre and radius each (and in test_streams on Police Station's patch). Node
  tests of the areas and words; a compiler test of the warning, a mission stream's and a cleared map's; the browser
  check `diagonal` adds a mark in front of the farm scout's door, inside patch_farm's area: its triangle, picked its area,
  panel line and tooltip, let go the triangle alone, undone none. Seen in a test server's page on the farm. The
  editor, viewer, lab, node and repo suites.
- **Known gaps.** A mission object the project moves takes its stream's rebuild volume with it in the Build (a bomb's),
  but the warning goes by where the volume stands in the original stream. The guide's pictures don't show the
  triangle yet. LWR's meld containers and blasts take diagonal cover too, where no warning can know.
