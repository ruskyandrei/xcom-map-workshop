### One button for the map or the prefab that is open

Stage M2 of the prefab menus plan, the design the user chose on 24 November: a map and a prefab are never open
together, so the header's second button names whichever is open, and its menu leads to the other.

- **The button** ([index.html](../../tools/viewer/web/index.html) `mapButton`): Map and the map's name in a map, Prefab
  and the prefab's name in the builder, with the unsaved mark there
  ([builder_session.js](../../tools/viewer/web/builder_session.js) `builderTitle`). It always opens its menu (it used
  to open the map browser itself in the builder and on a patch preview). The builder no longer renames the Project
  button and its menu to Prefab: the bar read "Prefab X · Prefab X".
- **Its menu** ([map_menu.js](../../tools/viewer/web/map_menu.js) `renderMapMenu`, drawn as it opens by
  [popups.js](../../tools/viewer/web/popups.js)):
  - what is open: This map, its name and its own items as before (Map settings, Missions, Map picture, Map grid,
    Clear map), or This prefab, its name and revision and the prefab's items: Save (Ctrl+S), Save as…, Export to a
    file… (new here: the saved revision, off until the prefab is saved, its tip saying so with unsaved changes) and
    Find missing pieces (moved from the Project menu);
  - Open: two buttons side by side, **A map…** (M) and **A prefab…**, each with how many there are (the prefab count
    from the library store), each opening its side of the Open window (`showOpen`). Change map… is gone: A map…
    takes its place. Until the next stage A prefab… opens the map browser's Prefabs group, as Open… did in the
    builder;
  - New prefab.
  - On a patch preview, where the map has no items of its own, the menu is Open alone.
- **The Project menu in the builder** ([project_menu.js](../../tools/viewer/web/project_menu.js)): a line (a prefab
  is open; opening a project closes it, asking to save first), Open… and the recent projects, which the builder used
  to hide; no Save or Save as ([style.css](../../tools/viewer/web/style.css)). Its Open… opens the project dialog; the
  extra Load project… item the builder added is gone.
- **Keys** ([navigation.js](../../tools/viewer/web/navigation.js)): M opens the Open window's Maps side; in the
  builder Ctrl+O opens its Prefabs side (in a map it is the project dialog, as before).
- A map icon (`i-map`) for A map…; Open's buttons are a stylesheet part of their own (`.openpair`).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the map menu's row.

Checked: the browser checks `project-menu` (the menu in a map: its head and name, the map's items, no prefab's
items, Open's two buttons and their counts, New prefab, A map… opening the map browser and the focus back on the
button), `builder` (in the builder: Project None, the second button Prefab and the prefab's name, the Project menu
with Open… alone and its recent projects, the menu's prefab items with Export off before a save, Ctrl+O shown; saves
through the menu's Save as…), `modals`, `header`, `prefabs` and `documents`, and the maps check (it opens the browser
by A map…; one run of three had the Prepare dialog in the way of a click), on a test server with fresh stores; the
repo and node suites. Looked at both menus and the builder's Project menu: no page error.
