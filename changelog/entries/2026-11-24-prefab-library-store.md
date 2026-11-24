### The prefab library is one store behind its views

Stage M0 of the prefab menus plan (one button for the map or the prefab, an Open window with Maps and Prefabs sides):
the list of prefabs and the actions on them move out of the Add panel's Prefabs tab into a store of their own, so that
the Open window's Prefabs side and the bar's menu (the next stages) draw from the same list. Nothing looks different.

- **The store** ([prefab_library.js](../../tools/viewer/web/prefab_library.js), new, `createPrefabLibrary`): the
  list and its folder, read again after every change (one request at a time), and rename, duplicate (the picture
  with it), export, delete and import (a clash refused with what is here, answered by replace or copy), each telling
  every view that listens (`onChange`). It is given the server's routes and how to hand the user a file, and holds no
  document and no three.js. Made once by [app.js](../../tools/viewer/web/app.js) and kept in
  [editor_state.js](../../tools/viewer/web/editor_state.js) (`prefabLibrary`).
- **The Add panel's tab** ([prefabs.js](../../tools/viewer/web/prefabs.js) `createPrefabTab`, which was
  `createPrefabBrowser`): drawn from the store, its rows, buttons and answers to the tests (`refresh`, `list`,
  `byName`, `setChosen`) as they were. A prefab's chips (`prefabChips`) and its maps shortened (`prefabMaps`) are plain
  exports now, for the window's cards to share. prefabs.js's `api` gains `pictureBlob`, the fetch a duplicate made in
  the tab.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): a row for the store.
- Two browser checks still expected prefab schema 4, which prefabs left on 23 November (cursorFloors, schema 5):
  `made-prefab` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py)) and `library-flares`
  ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) now expect 5. Both failed on main.

Checked: a node test, [prefab_library_test.mjs](../../tools/viewer/tests/prefab_library_test.mjs), drives the store
with a stand-in for the server (the list and a broken file in it, two refreshes asking once, rename and its no-change
cases, duplicate with its picture and a second copy's free name, export, delete, an import, its clash and both
answers, a failed change still reading the list, a library that cannot be read, a view that stops listening). The
browser checks `prefabs`, `prefab-effects`, `library-flares`, `builder`, `made-prefab` and `rail-lists` on a test
server with fresh stores; the node and repo suites.
