### The guide says the one Map or Prefab button, the Open window and the large Add panel

The user guide ([guide.html](../../tools/release/guide/guide.html)) brought level with the prefab menus (stages M0 to
M4) and the Add panel made large:

- **The header** (`#header`): the logo at the left; Map names the map that is open and its menu holds the map's items
  and Open (A map…, A prefab…), and in the prefab builder the same button reads Prefab with the prefab's name. The
  four menus' table and the window picture's legend say it. The guide page's own brand, which copied the editor's
  boxed X, is the shield logo too.
- **The Map menu** (`#map-menu`): This map and its name, the map's five items, Open's two buttons with their counts
  and New prefab; Change map… is gone.
- **The Open window** (`#maps`, now "The Open window: maps"): the map browser as its Maps side, with the Maps and
  Prefabs switch in its head and no Prefabs group; a new section, `#open-prefabs`, for its Prefabs side: the cards,
  the find box and order, New prefab, the chosen prefab's Rename, Duplicate, Export and Delete, Import… and Open.
- **Prefabs** (`#prefabs`): the Prefabs tab places prefabs (a row's Edit, All prefabs… at its foot; Import… and the
  rows' other buttons moved to the window); the banner with Edit in the builder after Save as prefab…; a placed
  prefab's group opening it in the builder.
- **The prefab builder** (`#prefab-builder`): its ways in (New prefab in the menu and the window, a card's Open, a
  row's Edit); the Prefab menu (`#prefab-menu`: Project reading None, This prefab, Save, Save as…, Export to a
  file…, Find missing pieces, Open and New prefab) in place of the Project button renamed Prefab; the This prefab
  tab with a picture.
- **The Add panel** (`#add`): its Larger button (item 9) and a section of its own, `#add-large`, with a picture of
  the panel made large.
- **Smaller places:** the Project menu in the builder, the keys table's M and Ctrl+O, and a group's piece moved alone
  by Ctrl and the wheel (the Groups legend still said only ungroup).

Pictures ([shots/](../../tools/release/guide/shots)): new `add-large`, `open-prefabs`, `prefab-menu` and
`this-prefab`; taken again `window` and `header-left` (the logo), `map-menu`, `map-browser`, `add` (its Larger
button), `prefabs`, the Views list's three (`views-list`, `effects-switches`, `spawns-switches`) and `map-grid`, the
list now opening beside its button (map-grid's camera moved so the far X side's handle is clear of it), and `play`
(its window says the play name). Kept: the other whole-window pictures, whose subject didn't change though their
header shows the old brand, and the Project and Game menus, the other Add panel tabs, the prefab test, `group` and
`flags`.

[take_shots.py](../../tools/release/guide/take_shots.py): the Map menu's shot marks This map, the items, Open's pair
and New prefab, and saves the two demo prefabs first so Open counts them (`save_prefabs`, `PREFABS`); map-browser
opens by A map… and marks the switch; add marks Larger; new shots `add-large`, `open-prefabs` and `prefab-builder`
(a third prefab, `BUILDER_PREFAB`, saved and opened in the builder: `prefab-menu` and `this-prefab`); prefabs marks
Edit and All prefabs… where it marked Import… and the rows' buttons.

Checked: a full run of take_shots.py on a test server with fresh stores, every new and retaken picture looked at and
compared with the guide's (guide_tools.py compare and sheet); `python tools/run_tests.py viewer -k guide`, `release`
and `repo`; the page as published photographed at each changed section (guide_tools.py look). Known gaps: the run
stopped at `mission-objects`, the cache's URB_SlaughterhouseA asking to be prepared again, so it and `diagonal` were
not taken (both kept, their parts unchanged); `buildings-view` still predates the box panel's Cursor stops at its
floors tick (23 November); a group's section now has a 6-pixel empty row under it where the hidden Open in the
builder button stands, left out of the `group` picture. The last release's zip still carries the earlier guide; the
published page changes when main is pushed.
