### The user guide gone over for the custom geometry work: snap and Align, made pieces at any size and angle, their handles, corners and texture mapping

The [user guide](../../tools/release/guide/guide.html) read whole against the editor after the custom geometry
improvements (the ledger entries from align-to-grid-level-game-pose to wall-in-a-tile-row), and brought level with it:

- **Stale, now as the editor is:** Level snap and the recipe snap are gone from the tool strip's legend (17 buttons),
  the keys (L is Align to grid), the chips (Off the grid in place of Recipe snap), the task "Work on an upper floor"
  (a floor piece placed as any piece, then Level), the bottom bar (the floor chosen no longer sets a floor piece's
  height; it starts a new floor box there) and "How pieces move" (the kinds table, "The grid rule and Game pose",
  "Floor pieces and Level"). The snap's words in the tasks, the cover blocks' sizes (levels of 64 up, smooth with snap
  off), a door's copy, pieces from other maps, prefab placing (only a prefab with a building goes by whole tiles),
  the prefab builder (its Build menu draws made pieces; Align prefab to grid) and the limits. The cover block task's
  Width and Length fields, gone before this work, are its handles now.
- **New:** "Snap: the steps of every move, size and turn" (a table of the three settings, steps counted from where a
  drag starts, typed values); the Align section's Align to row (Grid, Level, Game pose) in "Groups and Align" and the
  piece panel's legend; the made pieces' section rewritten: drawing under each snap setting, "Sizing a made piece: its
  white handles" (design A: ends, top, bottom, face; sides, top, underside; no size limit; Pivot to corner), the wall's
  new legend, gaps read where the lines between tiles' centres cross the wall, a wall standing inside a tile row,
  Taller than its look, "Corners: mitred ends and Join ends" (J held), which tiles a made floor is floor on, turned and
  tipped floors; "Texture mapping" (design B: the fold, the picked surface, the blue dot, ring and white dot, the
  modes and fields, the notes for atlases, faceless sides and a pattern's real size, a ramp along its slope); a task,
  "Draw walls at an angle, and give one a pattern of its own"; a line in "In the game: known limits".
- **Pictures:** new texture-mapping.webp (a drawn wall with its fold open and the three handles); retaken rail.webp,
  window.webp, piece-panel.webp and align.webp (the Align to row; the Level snap button gone), made-walls.webp (two
  walls drawn with snap at 24 meeting in a mitred corner, the size handles of design A, the gaps a set at a time),
  made-ground.webp (the bottom handle, the Texture mapping fold and Pivot to corner) and clear-map.webp (its warning in
  the warning colour). The others are kept; full-window pictures still show the Level snap button in the rail, where
  the rail is not what they explain.
- [take_shots.py](../../tools/release/guide/take_shots.py): the rail's marks lose `#editLevels` (the release suite's
  guide test failed on it); the piece panel's and Align's marks take the Align to row; `made_corner` draws the two
  walls under fine snap for `made-walls` (rewritten) and the new `texture-mapping`; `made-ground` marks the bottom
  handle.

Checked: `run_tests.py viewer -k guide`, `release` and `repo` pass; every new and retaken picture looked at; the
published page photographed at each changed section (`guide_tools.py look`) and read. The shots were taken on a test
server with scratch projects, builds and squad; no map was read into the cache for them.

The last release's zip (0.6.0) keeps the earlier guide; this one goes out with the next release, or with a push of
main, which republishes the guide page.
