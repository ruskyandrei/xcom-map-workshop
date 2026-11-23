### The prefab builder's Add panel lists the prefab's own pieces: This prefab

Discord suggestion S19: "Like how maps have the 'this map' list of stuff in their menu". In the prefab builder the Add
panel's first tab, hidden until now, reads **This prefab** and lists the pieces the prefab holds now.

- **One row for each distinct piece** ([pieces.js](../../tools/viewer/web/pieces.js) `collectPieces`, its `live`
  form): pieces alike in class, archetype, mesh, materials and tint make one row, with its picture, its kind and how
  many the prefab has (the count's tip says "in this prefab"). Each part is taken as it stands (its matrix and pose
  where it was moved to, and its state: tint, flags, blasts), so a row's picture and copy are the piece as it is.
  Drawn walls, floors and ground and cover blocks give no row: each is made to its own size (the Build menu, the cover
  rows every tab has). An empty prefab says "Nothing in the prefab yet: All maps has every piece of the game".
- **A row's click puts another on the cursor** ([clipboard.js](../../tools/viewer/web/clipboard.js) `chooseEntry`,
  `entryParts`): a copy of the piece with its state, as Ctrl+C and Ctrl+V of it make; it joins none of the groups its
  original stands in (a row is a piece).
- **The list follows the prefab**: the edit hub's new `add-panel` refresh
  ([edit_hub.js](../../tools/viewer/web/edit_hub.js), clipboard.js) collects it again after an edit, an undo or a
  selection while the tab shows, once a frame at most; a row whose count changed is made again and a row of a piece
  gone is let go ([pieces.js](../../tools/viewer/web/pieces.js) `load`), and a row always chooses its key's entry as
  the list has it now. Opening the panel or switching to the tab collects it afresh.
- The tab's words are set by [builder_session.js](../../tools/viewer/web/builder_session.js) `builderPage`; the rule
  in [style.css](../../tools/viewer/web/style.css) that hid it is gone, and `setLibraryScope` no longer turns This map
  into All maps in the builder. The builder still opens the Add panel on All maps, as it did.
- In a map, This map is unchanged: the map's pieces as exported.
- The [guide](../../tools/release/guide/guide.html)'s prefab builder section says what the tab lists.

Checked: a new browser check, `check_this_prefab`
([browser_builder.py](../../tools/viewer/tests/browser_builder.py), run with the `builder` check of
[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)), on a test server with Bar and Police Station: an empty
prefab's line; two arcade machines and a computer give two rows counted 2 and 1, with their pictures; a row's click
and a click in the view place a third, in no group, and the row reads 3; deleting the computer takes its row and Ctrl+Z
brings it back; a drawn wall and a cover block give no row; in Bar, This map's rows are the same after a copy is
placed. The browser checks `builder`, `library`, `adding` and `api-names`; the node suite. Not done: the guide's
picture of the Add panel in the builder.
