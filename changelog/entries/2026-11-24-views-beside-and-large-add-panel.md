### The Views list opens beside its button; the Add panel can be made large, with large pictures

The user asked for the Views list to show up next to the Views button, as the Build menu shows up next to Add, and for
a maximise button on the Add panel that makes it large, as the look picker is, with larger pictures of the pieces.

- **The Views list beside its button** ([views.js](../../tools/viewer/web/views.js) `placeList`,
  [style.css](../../tools/viewer/web/style.css)): it stood from the rail's top; it now stands with its top by the
  button's, as the Build menu does, and where it would run past the window's foot (the Spawns view's switches in a
  short window) it is lifted as far as it must, never above the window's top. The rail is drawn over the other
  panels, so its lists show over the dock (Frame, Scene, Floors) and the Add panel.
- **The Add panel made large** ([index.html](../../tools/viewer/web/index.html) its `libraryLarge` button beside Close
  and its two icons, [clipboard.js](../../tools/viewer/web/clipboard.js) `setAddLarge`, style.css `#library.large`):
  over most of the view beside the rail, each tab's pieces as cards in a grid, several to a row, their pictures
  168 pixels square where they were 48. Back to its size by the button, Esc
  ([navigation.js](../../tools/viewer/web/navigation.js)), the panel shut, or a card chosen (so the click that places
  it falls in the view: chooseEntry, and startPlacing for an entry of any tab).
  - This map and This prefab ([pieces.js](../../tools/viewer/web/pieces.js) `setLarge`, `LARGE_THUMB`): the rows
    made again at the large size and their pictures drawn again; `paintThumbs` draws each picture at its canvas's size
    (it drew all at 48).
  - All maps ([library.js](../../tools/viewer/web/library.js) `setLarge`): its windowed list lays the cards out in
    rows of as many columns as its width holds (188 by 246 each); a large picture is kept by the server under a key of
    its own (`largeKey`), drawn the first time it comes into view, as the small ones are.
  - Prefabs ([prefabs.js](../../tools/viewer/web/prefabs.js), [prefab_place.js](../../tools/viewer/web/prefab_place.js)
    `drawPrefabPictures`): a prefab's picture is now drawn 256 pixels square (it was 96), so a prefab saved from now on
    shows large; an older one's picture is enlarged. A card's buttons wrap within it.
- The [guide](../../tools/release/guide/guide.html) (the Views list, the Add panel's Larger) and
  [UI-GUIDELINES.md](../../UI-GUIDELINES.md) (the rail's list, the Add panel) say it.

Checked: a new browser check, `rail-lists` ([browser_controls.py](../../tools/viewer/tests/browser_controls.py), run by
[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)): the Views list's top by the button's and to its right;
in a window 1000 by 560 with the Spawns view on, the list inside the window and drawn over the dock; the Add panel made
large over 1200 pixels wide, This map's cards side by side with pictures 168 pixels square drawn, a card chosen bringing
it back to its size with placing begun, Esc bringing the large panel back; All maps' cards with large pictures, 32 in
view once scrolled 30 rows down; Close leaving it small. Looked at in the browser on Bar (This map, All maps, Prefabs
with a prefab saved, the Views list in a short window): no console error. The browser checks `library`, `adding`,
`builder`, `prefabs`, `api-names`, `grid-panel`, `header` and `text-select`; the repo, node and viewer suites. Not done: the guide's pictures of
the Add panel and the Views list.
