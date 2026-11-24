### The Open window: a Maps side and a Prefabs side

Stage M3 of the prefab menus plan. Prefabs are no longer rows of the map list: the window that changes what is open has
two sides, each a browser made for its kind, and a switch in its head to cross from one to the other.

- **One window, titled Open, with two sides** ([map_menu.js](../../tools/viewer/web/map_menu.js) `makeMapBrowser`,
  `showOpen`, `switchTo`): the menu's A map… and M open it on Maps, A prefab… and the builder's Ctrl+O on Prefabs. Each
  side's head carries the same switch, Maps and Prefabs with their counts
  ([prefab_browser.js](../../tools/viewer/web/prefab_browser.js) `openSwitch`); a click on the other half shuts this
  side and shows the other in its place, the focus on the switch's lit half. The two sides are two dialogs the same
  size and place; Esc closes either, the focus back where the window was opened from (the bar's button, when opened
  from its menu).
- **The Maps side** ([map_browser.js](../../tools/viewer/web/map_browser.js)): the map browser as it was, back to maps
  alone: no Prefabs group, no made-up rows, so its count and Prepared only are true of all it lists. Its title is
  Open. With no map open (an address naming none listed) the page shows it with its message, and its switch is the way
  to a prefab from there.
- **The Prefabs side** ([prefab_browser.js](../../tools/viewer/web/prefab_browser.js) `createPrefabBrowserWindow`,
  new; [index.html](../../tools/viewer/web/index.html) `openPrefabDialog`): the library as cards with their pictures,
  the first card New prefab; on a card its name, what it holds and its tiles, the maps its pieces come from, its
  revision and date, and its chips (the open prefab marked "open"). A filter by name or map, an order (last saved
  first, or by name). Open (Enter, a double-click, the accent button) opens the chosen prefab in the builder. Under
  the cards, the chosen prefab's Rename, Duplicate, Export and Delete (rename and delete asking in the row), and
  Import… at the foot with its clash question: the one place the library's files are managed (decision P9). In a map a
  line says a prefab is placed from the Add panel. It draws from the library store, so a change shows in the Add
  panel's tab at once.
- **The Add panel's Prefabs tab** ([prefabs.js](../../tools/viewer/web/prefabs.js) `createPrefabTab`): where a prefab
  is placed. A row keeps Edit; its Rename, Duplicate, Export and Delete and the tab's Import… moved to the window, and
  its foot gains All prefabs…, which opens it. A prefab chosen to place and deleted meanwhile stops the placing.
- **Cards** are one stylesheet part for the large Add panel and the window ([style.css](../../tools/viewer/web/style.css)
  `.cards`, `.card`); the window's bar, actions and switch are parts of their own (`.openbar`, `.openacts`,
  `.opensides`).
- The test hooks gain `showOpen` and `prefabLibrary` ([test_api.js](../../tools/viewer/web/test_api.js),
  [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json)). [ARCHITECTURE.md](../../ARCHITECTURE.md):
  the window in the map menu's row.

Checked: a new browser check, `open-window` ([browser_open_window.py](../../tools/viewer/tests/browser_open_window.py),
run by [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)): in a map the bar's order, the menu's items and
counts, A map… and A prefab… on their sides, the switch both ways with the focus on its lit half and the two sides in
the same place, Esc and the focus back on the button, M, the Maps side with no prefab and its count the maps', the
Prefabs side with New prefab first and every prefab, New prefab with a trial's edit asking and Cancel keeping the map,
a copied piece placed by Ctrl+V in the prefab the window opened; in the builder Project None, the Prefab button with
the prefab's name and the unsaved mark, the Project menu with Open… alone, Save as… and Ctrl+S through the menu, Export
to a file…, Ctrl+O on Prefabs with the open prefab marked and chosen, M on Maps; with no map open the Maps side's
message and its switch to New prefab; at 1280, 1024 and 800 wide nothing pushed out of the header and the menu and the
window inside the page. The browser checks `prefabs` (the window's rename, duplicate, export, delete and both imports,
the tab hearing of each), `documents` (the import clash through the window), `builder`, `project-menu`, `modals`,
`api-names`, `prefab-effects` and `rail-lists`, and the maps check, on a test server with fresh stores; the repo and
node suites. Looked at both sides, the switch and the tab: no page error.
