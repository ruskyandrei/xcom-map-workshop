### The prefab menus' smaller places: a placed prefab's group, the note after a save, help and documents

Stage M4 of the prefab menus plan: the places round the new button and the Open window brought level with them.

- **A placed prefab's group** ([groups.js](../../tools/viewer/web/groups.js), [index.html](../../tools/viewer/web/index.html)
  `groupPrefabOpen`): its section, which says "Placed from the prefab X (revision N)", gains a button, **Open X in the
  builder**, while the library still has that prefab (read from the library store); what is placed stays as it is.
- **After Save as prefab… in a map** ([prefab_place.js](../../tools/viewer/web/prefab_place.js)): the note is a banner
  under the header (decision P8), saying the Add panel's Prefabs tab places it and the Map button's A prefab… opens it,
  with an **Edit in the builder** action; it goes after 12 seconds. It was a hint that went after 2.5 seconds with no
  action.
- **The help panel** ([index.html](../../tools/viewer/web/index.html)): M is the Open window's Maps side, Ctrl+O a
  project, or in the builder the Prefabs side. The piece panel's Save as prefab… tip names where prefabs are placed and
  opened.
- **The viewer's notes** ([README.md](../../tools/viewer/README.md)): the header (the logo, the one button and its
  menu), the map browser as the Open window's Maps side, and the prefab builder's ways in, the Prefabs side and the
  library store.
- **The interface's rules** ([UI-GUIDELINES.md](../../UI-GUIDELINES.md)): the header's line names the logo and the one
  button; kinds of one job share a window with sides, and a library's files are managed in its window, not on the rows
  of the panel that places from it; the Open window's cards are the Add panel's.

Checked: the browser check `prefabs` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) now finds the
banner with its Edit in the builder after a save, and Open Smoke prefab in the builder on the placed prefab's group;
`open-window`, `groups` and `text-select`, on a test server with fresh stores; the repo and node suites. Not done: the
user guide, which the update-guide skill brings level (the header's, the Map menu's, the map browser's and the Prefabs
tab's pictures and words, and the guide's take_shots.py, which still marks the Map menu's Change map and the Prefabs
tab's Import and row buttons).
