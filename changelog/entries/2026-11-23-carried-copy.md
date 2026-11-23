### A copy goes along to the next map or prefab: Ctrl+C, change map, Ctrl+V

Discord suggestion S17 asked for several maps open with copy and paste between them. At the user's choice it is the
copy carried: Ctrl+C or Ctrl+X in a map or in the prefab builder, then open another map, project or prefab, then Ctrl+V:
the copy is on the cursor and a click places it, as after any copy.

- **Packed as the page leaves** ([clipboard.js](../../tools/viewer/web/clipboard.js) `carryCopy`, which
  [document_session.js](../../tools/viewer/web/document_session.js) `goTo` asks for once the question about unsaved
  work is answered): what Ctrl+V would place, when it is a copy (pieces with their state, cover blocks, lights,
  effects, sounds, flares, the buildings selected with them and the groups among them), is written as a prefab's
  records without the file ([prefab_place.js](../../tools/viewer/web/prefab_place.js) `prefabRecords`, given the
  copy's own clip: its entries as copied, so a cut is carried, its footprint by where they stand; it now also gives
  `base` and `names`), with the copy's pivot in their space, and kept by the tab (storage.js `rememberSession`, which
  now says whether it was kept). Ctrl+C itself does nothing new. Packing all 966 of Bar's pieces took 6 ms (records 5,
  text 1; 335 thousand characters), so a change of map is not slowed.
- **The format** ([carried_clip.js](../../tools/viewer/web/carried_clip.js), new): `{ format: 1, id, from, name, words,
  pivot, pivotActor, pieces, groups, buildings, donors, left, boxes }`, one reader and writer. A copy over 4 million
  characters, or one the tab's storage refuses, is not carried: a small marker is kept, and the arrival and Ctrl+V say
  it was too large and name a prefab as the way. Another format is refused with its sentence.
- **Brought on Ctrl+V** (clipboard.js `bringCarried`) when the page has nothing copied of its own: prefab_place.js
  `prefabClip` makes a copy's clip of the records (its new `plain`: no group round it, no prefab mark, held by the
  copy's own pivot and pivot piece, by whole tiles only when it holds a building), the destination's own pieces its own
  again and another map's read as All maps reads them (the first time under the busy mark). What can't come (left out
  as it was packed, or here) is named in a banner and the rest placed. The clip made is the page's own, so the next
  Ctrl+V is at once, and leaving again carries it on as it came. An Add panel entry or a prefab chosen last is not
  carried (the tab then carries nothing); with nothing on the clipboard, what the tab carries stays for the next map.
- **The Buildings view's boxes** ([buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) `volumeCopy`):
  carried under `boxes`, relative to the tile grid's corner; `pasteVolumes` reads them where the view has no copy of its
  own (a building the map lacks is a new one).
- **The arrival** (clipboard.js `announceCarried`, which app.js's `startScene` calls once the scene, the project or the
  prefab has opened): the hint says once "The copy came along: Ctrl+V places it here".
- The help panel ([index.html](../../tools/viewer/web/index.html)), the [guide](../../tools/release/guide/guide.html)
  (a task, "Bring pieces from one map to another") and [ARCHITECTURE.md](../../ARCHITECTURE.md) (its row) say it.

Checked: the node test `carried_clip_test.mjs` (packed and unpacked the records come back, the boxes too, another
format and a broken text refused with their sentences, a copy too large kept as its marker); a new browser check,
`carried-copy` ([browser_controls.py](../../tools/viewer/tests/browser_controls.py), run by
[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)): on Bar two of its pieces grouped, a drawn wall, a cover
block, a light, an effect and a building are copied; on Police Station the arrival's hint shows, and Ctrl+V and a click
place what Save as prefab's records hold (each piece's home and actor, the made wall, the cover block, the recipe
light, the effect, the building's box, the group of two and no prefab's group); the project saved there compiles with
no error (tools/editor/compiler.py with the scratch cache and the install, the pieces brought from Bar as pieces of other
maps are); the same copy placed in the prefab builder, and copied there, placed on Bar; a cut carried; an Add panel
entry chosen last not carried ("Nothing copied yet"); a carried copy with a stream level's piece left out and a piece of
a map the install lacks placed the rest and named both; the Buildings view's box carried to a building of its own. The
browser checks the changed code touches (`builder`, `prefabs`, `prefab-effects`, `projects`, `documents`, `adding`,
`copy-drag`, `library`, `floor-boxes`, `paste-buildings`); the repo, node and viewer suites. Not done: the zones' and
diagonal cover marks' copies, which come with the same controls on every thing (Part A).
