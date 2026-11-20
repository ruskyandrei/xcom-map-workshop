# Map Workshop: original-map viewer preview

The first working slice of the editor plan. Reads original
Enemy Within v845/licensee-64 packages and inherited UDK v845/licensee-0 patches; checked on local URB_Bar and
TempleShip snapshots, plus `patch_bar`. Lights everything dynamically from the map's own placed lights.

## Run

Python 3.12 and a desktop browser with WebGL2 are required. One-time setup, from the repository root:

```powershell
python -m pip install -r tools/viewer/requirements.txt
python tools/viewer/setup_vendor.py
```

The second command downloads three.js **0.180.0**, matching addons and its MIT licence. Downloads are checked against
pinned SHA-256 values. Runtime is local/offline; Node is not needed. Generated dependencies are ignored by Git.

Export an original map from a content folder containing its matching texture caches:

```powershell
python tools/viewer/viewer.py export "<LWR install>\XEW\XComGame\CookedPCConsole\URB_Bar.upk" --scope map
```

It exports into the **cache** setting's folder (or `--cache <folder>`) and prints the generation's folder. Open that
exact generation:

```powershell
python tools/viewer/viewer.py serve "<cache>\URB_Bar\<generation>"
```

Day to day, double-click [xcom_editor.cmd](../../xcom_editor.cmd) in the repository root instead. It starts the main
server on port 8768 for the whole cache folder, or restarts it if it is running, then opens the browser. So running it
again after a re-export or a server change is all a restart takes.
- `xcom_editor.cmd restart` does the same.
- `xcom_editor.cmd start` starts it only if it is not running.
- `xcom_editor.cmd stop` stops it.
- `xcom_editor.cmd status` says what holds the port.

It never stops a process that is not this server.

The default port is **8768**, the main viewer/editor server. Keep one server there and restart it after a re-export
(it picks its exports when it starts); web changes only need a browser reload. Test servers use `--port`
8790–8799 and are stopped after the check. `--no-open` starts the server without opening a browser.
Use `--scope sample` on URB_Bar for a close study of asphalt, compact car body/glass and a fractured wall.
Sample mode can switch between study positions and original placements. Other maps require `--scope map`.
An arbitrary new map has not been validated just because its package version matches.

### Choose a base map in the UI

To switch between the prepared maps in one viewer, serve the cache root (with no folder given, the cache setting's):

```powershell
python tools/viewer/viewer.py serve
```

The header's **Map** button (or **M**) opens the map browser. Switching maps opens the original layout and resets
selection, search, floors and display controls; Temple Ship opens in its recommended interior view. URLs preserve
the map choice, including through reload and browser back/forward. (The Layout selector, which chose an exported
patch preview, went on 8 November: a preview opens by its address, `?map=URB_Bar&scene=preview-0.json`, and the
editor's projects replaced them.)

**The map browser** lists every map LWR plays (96; [`maplist.py`](maplist.py) reads them from the install's
`DefaultMaps.ini`, the strategy map left out, and Act1_IntroLevel, the tutorial's map, from its commented-out
abduction record), in sections by mission type: Abduction, UFO (crashed and landed),
Terror, Council (rescue, bomb, assault, extraction), EXALT (covert extraction, data recovery, the EXALT raid), Story
(alien bases, Temple Ship, base defence, the DLC and tutorial missions) and Other (multiplayer). A map that serves
several mission types is listed under each (41 maps do). The chips at the top show one section; the search finds a
map by its name, package or mission; **Prepared only** hides maps not exported yet. Each row says whether the map is
**checked in the game** (Bar, Temple Ship), **ready** (exported) or not exported yet.

**Export on first open.** A map not exported yet is exported the first time it is opened ([`exports.py`](exports.py)):
the server runs `viewer.py export <package> --scope map` in the background into the cache it serves, one map at a
time (about 20-30 s and 120 MB a map), the browser shows the time so far, and the page opens the map when it is done,
with no restart. A link to a map not exported yet (a project of one, say) opens the browser on it and exports it.
Listing every map needs the `lwr` setting; without it, or when serving one exact generation, only exported maps are
listed, as before.

**Updated maps prepare themselves again.** A map of the install whose export is older than the editor's exporter
(`EXPORT_VERSION`: an update since the map was prepared, such as export 19's masked props) is exported again when it
opens: `/maps.json` marks it `outdated` (only from a server that exports maps), and the page opens the Prepare
dialog under the map's name with just "Map schema updated. Re-exporting.", already running (about half a minute;
projects and edits are kept), then reloads on the new export. Should the export fail, the dialog says why and Later
leaves a short banner with **Re-export**; a map that comes
back still outdated in the same browser session waits for a click instead of starting again.

Library mode chooses one published full-map generation per map, preferring the highest exporter version and then
the latest manifest. It skips `.export-*` staging folders, malformed manifests and sample exports. An export made
outside the server (`viewer.py export`) needs a restart to be listed. Serving an exact generation, as above, keeps
that generation pinned and shows just its base map. A map-specific cache folder can also be served to select its
latest full generation.

**Old generations are deleted** ([prune.py](prune.py)) by the main server only (port 8768; a test server never),
when nothing of its own is in use:
- when it starts, before it picks its exports;
- after an export it made itself, once the map serves the new generation.

Of a map's generations of one package (the same SHA-256 prefix) and scope, the newest (exporter version, then the
scene's time) stays and the rest go. The library's piece folders go by the same rule. Another package's
generations, unfinished ones and `.export-*` folders stay. `python tools/viewer/prune.py --dry-run` lists what would
go. On 13 November 2026 this was 141 folders and 11.1 GB.

Only Bar and Temple Ship have been checked in the game; any other map exports and opens, and its Builds are untested
in the game until one is played. Runtime remains local/offline. The server lists the maps at `/maps.json` (each with
its label, whether it is exported and checked, its mission groups and missions), starts an export with
`POST /maps/<map-id>/export` and follows it at `/maps/<map-id>/export.json`, and serves each exported map's immutable
files under `/cache/<map-id>/`; scene and asset paths stay within that registered generation.
`/maps/<map-id>/families.json` ([families.py](families.py)) gives the page the compiler's families of pieces and the
map's assemblies (its cars, vans, doors with their frames, and ladders), worked out from the export once per server.
`/maps/<map-id>/collision.json` ([collision.py](collision.py); `?mesh=<id>` for some meshes only) gives what the game's
line checks meet of each of the map's own meshes: its convex hulls and boxes, one solid each, or that it uses its
triangles. It is read from the map's package in the install (which must be the file the map was exported from) once
per server, for invisible floors' ground.
Export 15 adds what of the map's Kismet names each piece (`referencedBy`, as "SeqAct_ToggleHidden_1 Target"; the
inspector's **Mission script** chip, and the compiler warns of moving or deleting such a piece) and each building
floor's volume boxes (`buildings[].floors[].boxes`, which the compiler's floor note reads). The library picks a map's
newest export and doesn't re-export it, so a map exported before needs `viewer.py export` again. Export 16 adds
what each fracturing piece's fragment columns break (`breaks`: a car's glass names its body and parts), from which the
compiler joins Police Station's standalone police light bars to their sedans. Export 17 adds what the game's damage
does to each piece (`destruction`, [scene_metadata.py](scene_metadata.py) `destruction`): its kind (a prop, with one
health, or a fracturing piece, which breaks a part at a time), the toughness it names (`Toughness_METAL`), that
toughness's health and its flags (`bFragile`, `bInvincible`), or null for pieces with no health (scenery, ladders). The
panel's source details show it as **Destructible** and **Health**, with the game's rules in the lines' tooltips.

To include the existing experimental layouts (opened by address, as above):

```powershell
python tools/viewer/viewer.py export "<LWR install>\XEW\XComGame\CookedPCConsole\URB_Bar.upk" --scope map --spec tools/patch/examples/exp07wing.json --spec tools/patch/examples/exp08blank.json
```

Restart library mode, or open the resulting generation with `serve`; `scene=preview-0.json` is the remix and
`preview-1.json` the blank layout. The **Floors** buttons in the bottom bar show all floors or cut down through a
selected floor, in every building at once (on a map with several, the floors are counted up to the tallest
building's; the per-building list went on 8 November).
Floor membership comes from the original cached actor lists; newly copied pieces transfer those memberships.
The remix also loads its inherited `patch_bar` package. Unticking **Hide patch helpers** (view options) displays remaining inherited
cover/ladder meshes as a cyan wireframe inspection overlay. Pieces removed by the layout stay removed. The package's
rebuild volumes and sequence-node records are retained as metadata; scripts/Kismet are not executed. Its three point
lights join the scene's lights.

## Available

- LOD-0 static/fractured geometry, UV channels, normals/tangents, source sections and initial painted fragment masks.
- Skeletal LOD-0 geometry, material slots, reference bones, chunk bone maps and normalized skin weights, exported as
  actual glTF skins. Doors and skeletal physics props render in their reference pose; repeated pieces have independent rigs.
- Actor/component transforms, local archetype resolution and component material overrides.
- Material-instance inheritance, static switch overrides, diffuse bindings, tint, masked surfaces and approximate glass.
- Alien packed opacity/emissive masks, source-colour glow on energy doors, and supported textureless constant materials.
- A masked material's cut-out follows its parent's OpacityMask input (export 19, T-29): wired straight to a texture
  parameter, that texture's masked channel (PROP_Objects, the common prop parent: `Spc_Ems_Mpc_Opc`'s alpha); an
  `OpacityMask` static switch that is off, nothing (PROP_Objects_Old: the farm's tractor, dairy tanks, pipes); else
  the colour texture's alpha, as before. Cooking strips plain nodes and blanks links to them, so only a direct link to a
  parameter, or the switch, says where a mask comes from (`materials.opacity_input`).
- The map's own lights, all dynamic (see Lighting below), with a **Lighting** switch: neutral studio light (the
  default since 7 November: our map lighting is an approximation), map lights, or map lights without Lightmass area
  lights.
- Materials with no texture parameter the viewer knows take the textures their compiled shaders sample (export 13):
  a colour texture by its name (`_DIFF`), and for a masked one a mask whose channel a 0/1 vector parameter picks
  (StreetSet's asphalt patches, which were pink, the diagnostic colour). A texture parameter of another name whose
  texture is named `_DIFF` serves as the diffuse too (Firaxis's own misspelt `Diffsue_Map`, window parallax's
  `Diffuse_GlassMask`). On URB_PoliceStation that leaves one diagnostic-colour material, the night sky (not drawn).
- **No diagnostic pink** (export 14, from a scan of every piece LWR's 95 maps and their streamed packages draw: 2,810
  visible pieces on 79 maps were pink, now none). A material's colour, after the profile's parameters:
  1. a texture parameter of another name: its texture named `_DIFF`; else named Diffuse... or Dif... (`Diffuse_Map`
     on burning trees' bark, `Diffuse Map A | CMod Mask` on the obsolete tiling material, whose alpha is a colour
     mask, not a cut-out); else the only parameter whose name and texture read as colour (`StaticScreenTexture` on
     the HQ console screens, `Rope_Tex`); never Firaxis's placeholders (`DiffuseDev`...);
  2. the compiled shaders' textures: one named `_DIFF`, else the first whose name has no word saying it isn't colour
     (normal, specular, mask, noise, smoke, fire, scrolling, gradient, placeholder...): `pineBranchSplit` on burning
     pines, whose masked branches keep its alpha as their cut-out, `Rough_Debris` on burning logs, `grassMulti`;
  3. a colour by kind (`materials.approximate_colour`): the alien wreck debris (the most common pink, 1,350 pieces
     on 29 maps; checked before step 2, since its `T_Alien_Destroyed` is a packed mask that draws as green blotches)
     as charred metal, the marsh bottom, burnt debris, distant city blocks, a water plane's own water or ground
     colour, dark water for other water materials; else neutral grey. These are flagged in Import notes.

  LWR's patch packages (`patch_clean_*`) carry the materials of their pieces as stubs (no parent, no parameters):
  the game has the real ones from the map, which is loaded first, and so does the export now. A fractured mesh's
  inside faces with no material (car glass, the abductor's railings) are hidden: the game draws them only where a
  fragment has broken off. A material the package only names (the highway bridge's cables use one from another
  package) draws neutral grey. Exports before 14 keep their pink: re-export, or delete the map's export folder and
  open it again.
- High-resolution texture payloads from inline data or named TFCs, including LZO/zlib bulk decompression.
- Portable PNG textures for this first version; source format, mip/cache identity and consumed-range hashes retained.
- Orbit, pan, zoom, framing the view or the selection, search, click selection, the piece panel, grid, wireframe and
  brightness (see The window below).
- A tile grid around the selection or the piece being placed, on the saved floor surfaces where there are any, with
  the tiles the piece covers marked (see The tile grid below).
- **Playable interior** and **Full scenery** views; authored scenery layers and floor bounds support reversible cutaway.
- Building/floor selection, source-cache roof hiding and clipped wall cutdown, with matching shadow/picking behavior.
- Experimental ordered copy/hide/spawn/ladder previews, copy scale, body/glass pairing and bounds-based vehicle snap.
- Original and patch previews selected in the header, with operation/source provenance and explicit preview notes.
- A map browser over every map LWR plays, by mission type, exporting a map on its first open, with independent
  per-map layouts and asset paths.
- Inherited patch composition with package-specific asset/object identities, source hashes, hidden helpers and content records.
- External cache generations published after export finishes, with import diagnostics in `scene.json` and the UI.

The complete-map path has been exercised on URB_Bar and TempleShip. Counts include hidden helper components;
sky-dome geometry is recorded but suppressed because its environment shader is not supported. **Frame** fits
the current view: the play area in **Interior**, the surrounding structure as well in **Full**. **Interior**
filters authored backdrop/roof/helper layers and clips geometry around the saved floor region: by height
always, and at the sides only for a piece that doesn't reach into the region or reaches more than four tiles past it
(big ground pieces, long walls). Since 10 November a piece with some part inside is otherwise drawn whole, a car
or a heap of rubble across the edge no longer sliced off (`WHOLE_OVERHANG`, `interiorWhole`). Selection,
picking and shadow coverage follow that cutaway. Source actor transforms and hidden flags are not modified.

The checked URB_Bar export contains **966 visible pieces**, including 7 door components and 14 skeletal prop components,
plus 110 hidden helper components and two suppressed sky domes. The shared cache for both previews has 271 geometry
variants, 260 textures and 197 material bindings. EXP-07 includes 17 hidden `patch_bar` components, eight rebuild-volume
records and sequence-node metadata; its hider removes one helper by name, leaving 16 available in the inspection overlay.
Forty-eight synthetic tests pass; browser checks cover roof opacity, source UV orientation, floors, map/layout switching,
reference skinning, independent cloned rigs, inherited helper visibility, dense light lists and whole-scene framing. No frame-rate target
has been established by this first check; draw-call reduction and loading optimization remain planned.

## The window

The 3D view fills the window. The rest appears when it is needed, so the screen is not covered in text:

- **Header:** the **Project** menu first after the name (Save, Save as, Open, Close project, the recent projects and
  Manage projects: see Projects), then the **Map** menu (Change map, and on a whole map Missions, Map picture, Map
  grid and Clear map; where it would hold Change map alone, the button opens the map browser), then the mission (see
  What the missions stream, below).
- On the right, before the icons: **Build** and **Play**, and on the arrow joined to Play the **Game** menu (Test
  squad setup, Game maps and the Installs). **Settings** (the gear) holds Game install and checks and Cache
  everything. The header has no find box (Ctrl+F is the browser's own).
- On the right of the header: once something has changed, a chip counting what was moved, added and deleted, and
  whether it is saved ("not saved" without a project, then "unsaved" or "saved"), with Undo, Redo and **Reset all**; then **Import notes** (with their count), **View options** and
  **Controls and shortcuts**. An experimental layout shows
  an "Experimental preview · not verified in game" chip.
- **Tool strip** (left): Select (V), Move (G), Rotate (R); **Add** (P), which opens the piece list beside it; world
  or the piece's own axes (X), snap, linked pieces; frame the selection (F, or double-click).
- **Camera:** drag to orbit, right-drag to pan, the wheel to zoom. The wheel zooms towards what is under the cursor
  (the piece there, else the ground), each notch a share of the way to it, so it never stalls however big the map;
  the point it looks at then sits at that depth, so orbiting and panning turn and move about what was zoomed to.
  (OrbitControls' own zoom went towards the orbit target only, slowing to a stop as it neared it.) The **arrow keys** and **WASD** move the camera while
  held (W and Up forward, S and Down back, A and Left left, D and Right right). By default they pan across the map:
  forward and back along the view's direction laid flat, left and right across it, so the camera keeps its height
  and angle. With View options' **Keys move along the view** ticked (remembered in the browser), forward and back
  follow the way the camera faces, climbing or descending with its tilt, and left and right go sideways across it.
  The orbit target moves with the camera. The speed is the same on every map and at every zoom, 5,000 units (about 52
  tiles) a second (`PAN_SPEED`); Shift moves three times as fast. **Q** and **E** turn the view left and right while held, keeping the tilt: round the point it looks at
  (as XCOM's camera turns), or with Keys move along the view, where the camera stands; 60° a second, Shift faster.
  With Keys move along the view, a left-drag also looks round from where the camera stands instead of orbiting:
  the camera keeps its place and only its aim moves (right looks right, up looks up, 90° for a drag the view's
  height, the tilt stopping short of straight up or down); Shift or Ctrl with the left button, right-drag and the
  wheel still pan and zoom, and a press on the gizmo still takes the gizmo.
  Not while typing in a field. (WASD, Q and E took the place of the Move, piece list, Solo, Rotate and axes
  shortcuts, which are now G, P, O, R and X; R still turns a piece while placing it.)
- **Play area:** the map's level volume, the box its tile grid fills and units can't leave, shows as faint amber
  walls with amber edges (faintly through whatever stands in front), from the lowest tile level to the top of the
  highest. **B** or View options' **Play area** shows and hides it (remembered in the browser). It is never picked
  or cut.
- **Bottom bar:** Frame, **Interior** or **Full** scenery and the **Floors** cutaway (every building at once). Each
  part shows only on maps where it applies.
- **View options:** lighting (Map, No area, Neutral), brightness, **Keys move along the view** (see Camera), the lights (see Lights), play area, tile grid, wireframe, **Hide patch helpers**
  (pieces a patch places hidden in the game, LWR's invisible cover and blockers: hidden by default since 8 November;
  unticked, they show as a cyan wireframe) and a
  performance stats line (pieces, meshes, textures, lights, draw calls, triangles). The stats choice is remembered in
  the browser.
- **Loading:** opening a map shows a progress bar (reading its layout, then building its pieces as their meshes and
  textures arrive), and so does a map's first export in the map browser (the map's pieces read, then its streams').

### What the missions stream

The game loads more than the map package: each of the map's `DefaultMaps.ini` records (one per mission) streams
other packages into it. Since export 13 the export reads them from the install the package is in (`missions` and
`streams` in `scene.json`, landing intros and other cinematics left out), and the original layout shows them:
- **LWR's patches** (`patch_<map>`, on 93 of LWR's 95 maps, and `patch_hide_randomized_objects`): mostly pieces
  placed hidden in the game, cover blocks and blockers (URB_PoliceStation's six: `highcover`, `Cover2x4`,
  `CoverSmallCar` over a burnt-out car...), hidden as in the game unless **Hide patch helpers** is unticked.
  `patch_bar` also has two ladders and three
  lights, which are recorded but not drawn or lit.
- **A mission's own stream** (`_CNH` for data recovery, `_Bomb`, ...): objects only that mission has
  (URB_PoliceStation's data recovery: the encoder, the transmitter, the drop zone).

The **Mission** picker in the header (shown when a map has more than one mission) chooses which record's streams
show; the first record is the default, and the choice stays in the URL (`mission=`; `mission=kind:<kind>` for a kind
the project adds), and it is the mission Play in game plays (the mission types plan,
private/plans/done/mission-types-plan.md). Streamed pieces can be
picked and inspected (a chip says which package they come from), but never moved, copied or deleted as pieces: the
Build edits the map's own pieces. So an edit that moves a piece LWR's patch covers (the burnt-out car) leaves LWR's
hidden cover where it was: untick Hide patch helpers to see it. A mission's own objects (export 24's
`missionObjects`, markers on View options' Mission objects) are the exception: a picked one's arrows move it with its
group, saved as overrides of `level: "stream"`, and the Build moves them in place in its copy of that mission's stream
(`tools/bake/stream_copy.py --moves`), which that mission's records alone stream. **Missions…** (Map menu,
`missions_panel.js`) sets the project's `missions`: the base map's records and kinds a record alone gives it.
Streamed pieces show whatever the floor cutaway (they carry no floors). Exports before 13 show none of this:
re-export, or delete the map's export folder and open it again.
- **Piece panel** (right): appears only with a selection. It has the mesh name, class and package; a "Moves with" chip
  ("Added copy" on copies and a milestone on kinds awaiting a build recipe); **Copy** and **Delete**; editable position and rotation; and Reset piece. The actor, mesh, materials, floors and geometry are
  folded under **Source details**, with full paths on hover and **Copy full paths**.

The [mock-up](../../research/ui/viewer-ui-mockup.html) this follows is kept in `research/ui/`.

### The user guide

The [user guide](../release/guide/guide.html) explains the window for the editor's users: each control on marked
screenshots, typical tasks, and what the editor can't do yet.
- **Controls and shortcuts** (the ? menu) links to it: the server sends it at `/guide.html` as one page
  ([guide.py](guide.py): the pictures put inside the page, the version filled in). A release serves its own
  `User Guide.html`, which `make_release.py` makes the same way.
- **When the window changes**, take its screenshots again and read the guide's lists against them. A control added,
  renamed or removed needs its entry there too (`test_release.py` fails when a control the pictures mark is gone
  from the page). Against a test server with empty scratch folders, stopped after:

  ```powershell
  python tools/viewer/viewer.py serve --port 8790 --no-open --projects "<scratch>\projects" --builds "<scratch>\builds"
  python tools/release/guide/take_shots.py
  ```

  [take_shots.py](../release/guide/take_shots.py) drives the page (Playwright and Edge) through a small demo project
  on the Bar, draws the numbered marks, and writes `tools/release/guide/shots/*.webp`. It saves a project and never
  builds or installs. The server's answers that would name this computer's folders are replaced by a usual install's.

## Editing (move, rotate, copy, add, delete)

The tool strip and the piece panel move, rotate, copy, add and delete pieces in the view. Without a project the edits
are a trial: they last until the page is reloaded (the browser asks first). **Save** them as a project (Ctrl+S, see
Projects). Nothing is built into the game yet.

- Select a piece, then **Move** (G) or **Rotate** (R). The gizmo moves the whole actor, all its components together,
  about the actor's own pivot, on all three axes. The axes button (X) switches between world axes and the piece's own.
- Or type a position (game units) or a pitch/yaw/roll (degrees) in the piece panel; Enter applies it as one undo
  step. A typed position keeps the piece's exact orientation.
- **Linked pieces** (the chain button, on by default) also moves the actors placed with it: everything its prefab
  instance placed and the partner it names (`HidingPartner`). The piece panel counts them ("Moves with 2 other
  pieces") and lists them under Source details. Turn it off to move one actor.
- **Assemblies always move together**, whatever Linked pieces says: a car's body, glass and light bar; a moving van's
  cab, walls and doors; a door's leaf and its frame. The Build makes them only together (the compiler's assemblies,
  served as `families.json`).
- **Ctrl+click or Shift+click** adds a piece to the selection, or takes it out again; in the search results too. The
  selection moves together about the last piece clicked.
- The gizmo uses three.js colours: red is game X, **green is up (game Z)**, blue is game Y. The piece panel gives the
  actor's pivot in game units and its pitch/yaw/roll in degrees, as the game stores them.
- **Snap** (the grid button) cycles three modes; its corner shows which:
  - **off**;
  - **24**: steps of 24 units and 15°, rounding the pivot to absolute multiples;
  - **96**: whole tiles, 96 across and 64 up, counted from where the piece stood when the drag began, and 90° turns.

  Tile mode keeps a piece's own offset within its tile, so a piece aligned to the map's tiles stays aligned (most
  pivots are not on tile corners: EXP-09). Recipe anchors (footprint centres, wall edges) are planned (first-editor
  plan, section 2).
- **Level snap** (the stacked-layers button under Snap, or **L**; on unless turned off, and remembered) is for floor
  pieces (see Floors under the piece list): placed or pasted, one keeps the height it has in the map moved by whole
  levels to the floor under the cursor, or to the floor chosen in the **Floor** picker; moved with the gizmo, it steps
  up and down by whole levels (64 units) from where the drag began, and moves freely across unless Snap says
  otherwise. Off, floor pieces are placed on the surface under the cursor and moved freely, as any piece is.
- **The recipe snap** is tile snap (**96**) for ladders, doors, cars, vans and fracturing pieces (walls, storey
  floors): the snap button's corner says **R** and the piece panel "Recipe snap". Such a piece moves by whole tiles
  (96 across) and storeys (64 up) and turns by quarter turns about the vertical, all counted from where its original
  stands in the map, so the tiles it stands on map onto the tiles of its new place exactly and the Build carries what
  the map saved for them exactly (the plan, section 3.2). The rotate
  handles lose their pitch and roll rings. Dragging, typed values, pasting, placing from the piece list and Align all
  snap to the nearest such pose ([poserule.js](web/poserule.js), the twin of the compiler's `grid_move` and
  `nearest_grid_pose`).
- **Snap off or 24, every piece moves freely**, these ones included (since 10 November 2026). One that stands off
  its original's grid gets an **Off the grid** chip naming what it misses; it builds where it stands, with an
  `off-grid` warning in the Build report naming the nearest pose on the grid. The Build carries its saved per-tile
  data by the exact move (fracture columns, a van's building, the floor cutaway), and the game rebuilds its tiles,
  but how such a piece plays off the grid is untested in the game.
- **The tile grid** shows only around the selection, or around the piece being placed. Nothing selected, no grid.
  - **The grid:** the tiles within three of the piece, fading out with distance. It is drawn at the tile level of the
    piece's lowest point (64 units a level). Where the map saved a floor at that level, the tile lies on that floor's
    surface, ramps included; elsewhere it is flat at the piece's lowest point.
  - **The piece's tiles:** filled where the piece reaches a quarter tile (24 units) or more into a tile. A lighter
    fill and an outline mark tiles it only reaches into at the edge (more than 2 units). Both show through the piece
    itself. The piece's own outline is drawn in white.
  - **The outline** comes from the drawn mesh: its farthest vertices in 96 directions, turned and moved as drawn. So a
    round fog pod covers one tile with four at the edge, not the 3 x 3 its bounding box would reach. The game decides
    from the piece's collision when the map loads.
  - **Floating:** when the piece's lowest point is more than 8 units above the saved floor under it, its tiles turn
    blue, with lines from the floor up to the piece. In EXP-11 a fog pod lifted 64 units gave no cover.
  - **The readout** above the bottom bar gives the counts, for example `1 tile + 4 at the edge · level 0`, and how
    high a floating piece is.
  - View options, **Tile grid**, turns it off.
- Escape cancels a drag; a hint says what is moving while a handle is held. With no drag, placing or open menu,
  Escape clears the selection. Undo/Redo (Ctrl+Z, Ctrl+Y or
  Ctrl+Shift+Z), **Reset piece** and **Reset all**. A piece put back exactly where it was no longer counts as moved.
- **Shift on a move handle** (an axis arrow or a plane square) drags a copy along it: the selection follows the
  cursor with the snaps of any drag, a drawn-only stand-in keeps its place, and on release the selection is back where
  it was and the copy is pasted where it was dragged to (one undo step, the copy selected). Escape, or a drag that
  went nowhere, makes no copy. In the Buildings view Shift is a plain move. The gizmo's `copyDrag` option
  ([gizmo.js](web/gizmo.js)); `copyDragBegin` and `copyDragEnd` in [app.js](web/app.js).
- **Copy** (Ctrl+C) takes the selection as it is now, linked pieces included; **Cut** (Ctrl+X) copies and deletes.
  **Paste** (Ctrl+V) shows the copy as a see-through preview that follows the cursor, as the piece list does, with
  the gizmo hidden meanwhile. A click (or Ctrl+V again) adds the new pieces with the copied piece's pivot on the point
  under the cursor: on whatever piece is there, or else level with where it was copied. Snap 24 rounds that spot to
  24 units across the floor; snap 96 puts it whole tiles from where the source stands. **R** turns the copy a
  quarter turn about its pivot before it is placed (Shift+R the other way). Shift+click places more; Esc cancels
  without adding anything. The pasted pieces keep their source's turn plus any quarter turns (a turned piece is
  previewed turned), become the selection, and each placement is one undo step.
- A copy is a new piece built from its source's mesh and materials, with its own entity id, output name
  (`<original actor>_copy3`, never reused) and pivot. A copy of a copy names the original. A copied car's body, glass and light bar stay linked to each other, not to the original car; so do a copied door's leaf and frame. The panel
  marks it "Added copy" and names its source; search tags it "added".
- **Delete** (Del) removes added pieces and hides originals. Undo, or **Reset all**, brings them back. Reset all puts
  the whole map back as exported (added pieces go, deleted ones return, moved ones go home, groups end) as one undo
  step.
- **Groups** keep pieces together, for a piece made of several (two consoles stacked into one cover piece). Select two
  or more pieces and **Lock as group** (the piece panel, or Ctrl+G).
  - **A locked group** selects and moves as one: picking any of its pieces picks them all, with linked pieces on or
    off. It shows in gold: the chip "Locked group of 2" beside the piece's name, the panel's group section with a
    lock, the selection box in the view, and the tag "locked group" in search results.
  - **Unlock** (the panel, or Ctrl+G on the group) keeps the group and its options while its pieces are moved one by
    one. The chip turns dashed ("Unlocked group of 2"), the panel offers **Select group**, and **Lock** (or Ctrl+G)
    locks it again.
  - **Ungroup** (Ctrl+Shift+G) ends the group; the pieces become separate. Locking pieces that are in another group
    takes them out of it (a group left with one piece ends).
  - **Break together in the game** is a group option: when one of its breakable pieces (destructible props) is
    damaged or destroyed in the game, the others are too, so a stacked piece can't stand half broken. It applies
    whether the group is locked or not. The panel says when a group has fewer than two breakable pieces, or pieces
    (walls, scenery) that move with it but can't break.
    - A cover block (high or low) in such a group goes when one of the group's breakable pieces is destroyed, so no
      invisible wall is left where the piece stood. One breakable piece and a block are enough, and the piece may be
      the map's own. Nothing else destroys the block. An invisible floor stays.
  - A copied group pastes as a new group of the copies, locked or not and with the same options. Every group change
    is one undo step, and a project saves its groups (`groups`, research/editor-contracts.md).
- **Align** lines pieces up. With two or more pieces or groups selected, the piece panel's Align section moves the
  others along any of game X, Y and Z (ticked; X and Y across the floor, Z up) until their boxes' centres, low edges
  or high edges meet the target's.
  - **The target** is the last one picked unless another is chosen in the panel's Target list, which names each piece
    or group with its position. A white box marks it in the view. The choice lasts while two or more stay selected.
  - What moves as one stays together: a locked group, and with linked pieces on, linked pieces. Align only moves,
    never turns, and is one undo step. The ticked axes and the edge are remembered.
- Hidden patch helpers shown for inspection cannot be copied or deleted.
- Linked pieces need export version 12 (re-export the map). Run `setup_vendor.py` once more: it adds the pinned
  three.js `TransformControls` addon.

### Effects, sounds and lens flares (export 23, 28)

The export lists the level's effects (`effects`: its Emitter actors, placed particle systems such as fires, rain
run-off and a Skyranger's idle lights; `scene_metadata.effect_metadata`): each one's actor, place, turn, scale, particle
system, whether the level lists it, `hidden`, its prefab and `carriedBy`. A mesh piece carries an effect standing at its
own place (within 2 units on each axis) when it is the only piece there. Since export 30 a piece also carries the
effects a prefab instance places around it: an effect that no piece carries by its place, placed by a prefab
instance at whose own place exactly one piece stands, is that piece's (`carriedHow: prefab`), and keeps its offset
and turn about the piece when the piece is moved, copied or deleted. The alien vapour pods' five smoke emitters
follow their pod so, and URB_Boulevard's splashes and glows their fountain's piece: 65 effects in 8 of the game's
maps. Where no piece or several stand at the prefab's place, nothing is guessed.
The compiler passes the carried pairs to the Build (`carriedEffects`), and
[native_effects.py](../bake/native_effects.py) moves, copies or deletes each with its piece: the tutorial's loose
Skyranger takes its lights along, as do Bar's claw machine and DEMO_SonOfFacemelt's water valves.

Since export 28 ([effects_metadata.py](effects_metadata.py); the effects and sounds plan's stage FX1) each effect also
carries its identity, where its starting state comes from, the particle parameters it saves (each against what its
system offers), the building floors that hide it, what of the mission's script names it, what it rides on, its
component's transform and what the editor may do with it (`can`, `why`). `sounds` (the ambient sound actors: cue, waves,
radii, volume and pitch, each value with where it came from) and `flares` (lens flares) are new, and `effectSystems` and
`soundWaves` describe each particle system and wave once. A mission stream's own are in its layer, read only. The
contract is section 8 of [editor-contracts.md](../../research/editor-contracts.md).

Since export 29 each effect is also **drawn as it looks**, in every view: a likeness, moving, made from its particle
system's own textures, blend and baked tables and the effect's own parameters and size
([effects_draw.py](effects_draw.py) reads them, [effects_sim.js](web/effects_sim.js) steps the particles,
[effects_preview.js](web/effects_preview.js) draws them). It is a likeness, not the game's shader: scrolling and
distorting textures, lit particles, swirls, bounces and what one emitter sets off in another are not followed, and
the game stays the judge of how an effect looks. View options' **Effects as they look** switches it off; an effect
that starts off is drawn only while it is picked; a likeness is never picked (its marker is the handle).
The Add panel uses the same drawing: an effect's row shows its likeness as its picture (drawn once, kept under
`/library/thumbs/` by a key of its own, `PICTURE_VERSION` in [library.js](web/library.js); the marker until then,
and for good where nothing can be drawn), the pointer on a row plays it in a small pane beside the panel, over the
outline of one tile for size, and while an effect is being placed its likeness comes with the cursor. A sound keeps
its marker.

The page's **Effects view** (Shift+X, the rail's spark; [effects_view.js](web/effects_view.js) draws,
[effects_rules.js](web/effects_rules.js) words) shows them as markers drawn over everything: a spark for an effect,
a speaker for a sound, a star for a flare, hollow when it starts off, greyed for a stream's. While it is on a click
picks one (never a piece) and the panel says what it plays, whether it starts with the mission and as what saves it,
its chips (starts off, named by the mission's script, carried by a piece, the landing's, hides with a floor, placed by
a prefab, rides on an actor, no sound set, shared cue) and an effect's particle parameters. A picked effect shows its
system's fixed box through its pose, scale and component, or says the bounds are unavailable; a picked sound shows
where it is heard. Each marker stands where the Build will have it: an effect a piece carries follows the piece, goes
with its delete and is copied with its copies (greyed); the landing's follow their moved zone; a cleared map keeps what
`clear_level` keeps (every sound, the landing's, a moved carrier's, and the scenery outside when asked). The flyout
on the rail button hides a kind; F or a double-click brings the camera to the picked one.

**Editing** (stage FX3; project schema 3). Where an effect's family builds, a picked effect or sound moves and turns
with the gizmo, copies (Ctrl+C, Ctrl+V), deletes, resets and groups with pieces (Ctrl+G) as a piece does, each one
undo step; a stream's and one the export says no to stay view only, and Delete or Ctrl+C says why. A **lens flare**
is edited the same way where the `flare` family builds (stage FX6b; the family is off until its game check, EXP-71:
`serve --family flare` and `build.py --family flare` lift it, and until then a flare is view only): moved, turned,
copied, deleted, box-selected and grouped, with no values (its template and colour stay as the map has them); one
that rides on another actor (a dropship's) stays view only, and one that names no template is not copied. An
effect a piece carries follows it until it is moved by itself; its panel's **Keep where it is** leaves it where the
map has it (`effect.follow: "none"` in its override) and **Follow** lets it follow again. The Normal button's flyout
has **Effects and sounds**: their markers drawn with the pieces and selected with them, so pieces and effects move,
copy and group as one selection. **Box select** (T) takes the effects and sounds inside the box with the pieces
while that switch is on, and counts them in its bar; in the Effects view it takes markers only and the view stays. A
picked effect's or sound's panel has **Select all**: every drawn effect of the same particle system, every sound of
the same waves (every lens flare of the same template, where flares are edited), inside the box where one is drawn. A project records an effect's or a sound's pose or delete as an override of its
actor, a copy as an added record with `kind` and the original it copies ([project.js](web/project.js)
`validAdded`, `validOverride`; contract section 4). The compiler turns them into the Build's `effects`, `sounds` and
`flares` lanes, which [native_effects.py](../bake/native_effects.py), [native_sounds.py](../bake/native_sounds.py) and
[native_flares.py](../bake/native_flares.py) write (a flare's copy is its actor and a LensFlareComponent of its own;
the flare template, and the archetype some are made from, stay shared):
moves in place, deletes out of the level's list, copies as actors of their own, then the buildings' floors list the
effects anew (contract section 8). The effect and sound families build for every project since EXP-68 passed
(17 November 2026); a family held back again (its `builds` off in the compiler's FAMILIES) shows view only, unless the
server is started with `serve --family <family>` (its Builds get the same `--family`).

**From other maps** (stage FX4). The Add panel's **All maps** lists the base maps' effects and ambient sounds beside
their pieces ([library.py](library.py) `scan_effects`; [effects_library.py](effects_library.py)): one entry per recipe
(an effect's class, particle system, saved parameters, scale, component offset and starting state; a sound's class,
cue, waves, values and starting state), so an effect placed the same way in two maps is one entry, brought from the
map whose copy brings least. The Kind menu has **Effects** and **Sounds**, each with its kinds (Fire, Smoke and steam,
Water, Light beams and glows, Nature, Alien, Wreckage and trash; Machines, Engines, Nature and weather, Alien, Music
and voices; Other where no rule matches). A row shows the Effects view's marker, what it plays (its emitters' kinds and
whether it is lit; a sound's length and a shared cue), where it is placed, and **Starts off** for one that waits for its
map's script. A landing's, one that rides on another and one that plays nothing are listed and can't be placed
(**Not brought**, with why). The base maps' **lens flares** are listed too since stage FX6b (library index 10, so a
library scanned before is scanned again): the Kind menu's **Lens flares**, one entry per template, colour and scale,
a row with the view's star, its template and its colour; one is placed where the flare family builds, as a sound
is. Placing one reads it from its map (`GET /library/effect.json?package=&actor=`: its export
28 record and its particle system or waves, described once per map into `effects-v1.json` in the map's pieces folder;
`POST /library/effects.json {sources}` many at once, as a project's opening asks) and places a copy as Ctrl+V places a
copy of the map's own; the project saves it as an added record whose `from` names the other map. Its panel's Wave
preview plays the wave from that map (`GET` or `HEAD /library/wave.ogg?package=&id=`, the donor read as it was when
its records were made). The compiler checks it against the library (the map the library was scanned from, an entry it
lists); the Build stages the actor in the map with what it needs ([transplant.py](../bake/transplant.py)
`stage_edit`: once, however many copies name it; a system or wave the map has by path is the map's own) and clones the
staged one. EXP-69 played them in the game (17 November 2026), and the compiler's foreign gate lists them since, so
the list shows them placeable.

**Values** (stage FX5; the `effect-values` and `sound-values` families, which build for every project since EXP-70
passed on 17 November 2026). A picked effect's or simple sound's panel has
**Values**: **Starts with the mission** (a sound's **Plays from the start**); an effect's particle parameters, each
the first of its name the effect saves in the kind it is saved in (a number with a slider guided by its system's
range, a vector's x, y and z, a colour; a vector that feeds a particle's colour as a colour and a strength, the maps'
going past 1) and then each its system offers that it doesn't save, in its distribution's kind; one saved as a random
or untyped value, or read as both kinds, shows why it stays as the map has it. A sound has **Volume** and **Pitch**,
each least and most. The sizes are dragged in the view, as a light's radius is: an effect's **size handle** beside
its marker (1/64 to 64 times the map's size, on a log scale; its box follows) and a sound's two handles on its
spheres (where it is heard at full volume, where it fades out). Each change is one undo step, ↺ and Reset put one
back, Reset piece and Reset all put them all back, and a copy takes the values of what it copies. A shared cue's
sound shows its values read only, and a lens flare has none to set. The project saves them in the override's or copy's `effect` or
`sound` ([effects_rules.js](web/effects_rules.js) `parameterControls`, `withValues`, `savedValues`; contract
section 4), and the Build writes them on the actor's own exports ([native_effects.py](../bake/native_effects.py)
`set_values`).

A picked sound's panel has a **Wave preview** (stage FX2): each of its waves with a Play button, one wave at a time,
at a preview volume, played by itself (the game's reach, volume, pitch, random choice and looping are not
reproduced). The button turns to Stop, the clock shows how far it has got, and picking something else, Escape,
leaving the view or opening another map or project stops it and lets it go; a wave that can't be played shows why.
The server's route is `GET` or `HEAD /maps/<id>/wave.ogg?id=<wave id>`, the id a key of the export's `soundWaves`
([audio.py](audio.py)): the wave's Ogg Vorbis stream is read from its package in the install (the map's own only
while it is the file the map was exported from, by its SHA-256; a stream's from its folder), checked as an Ogg stream
(one logical stream, every page's checksum and number, the three Vorbis headers, the end) before it is sent, and kept
in a cache of at most 64 MB. It answers with `audio/ogg`, its length, an ETag (`If-None-Match`: 304) and one byte
range at a time (206, 416 outside it); an id the export doesn't list is 404 and a wave it can't serve 422 with why,
so one bad wave never fails the map. Every wave of the 97 LWR maps' packages (7,192) passes the check.

### Clear map, the ground grid and landing zones

The plan; the guide's "Clear map and landing zones".

- **Clear map…** (Map menu, on a whole map) opens a window. It counts what goes (pieces, lights, the pieces the
  mission's script names) and what stays (the landing's pieces, one landing zone, the sun or moon and the sky
  light). It keeps the grid's size (the rail's Map grid changes it). The clear is one undo step:
  - every piece is deleted but the landing's;
  - one landing zone is kept (`clearKeptZone`): plain EW's first, the map's own first landing, else the first zone,
    used by both games; the others go with the same undo step;
  - the project gets `cleared: true` ([editor-contracts.md](../../research/editor-contracts.md)), and a grown grid
    is kept as `stage.grid`'s three numbers;
  - the map buildings it can no longer edit are hidden, and the LWR streams' pieces and the view-only and area lights
    are not drawn.
- **Keep the scenery outside the play area** (the window's tick, remembered) leaves the pieces whose every part's
  box lies wholly outside the play area, and the lights placed outside it (`clearPlan(size)`, `outsideBox`). The
  play area here is the map's level volume and the new grid together, across. The project says
  `clearKeepsOutside`, and the Build's `clear_level` leaves the lights, emitters, decals and lens flares placed
  outside it (the compiler's `outside_box`, passed as `cleared.keepOutside`). On Bar: 219 pieces and 29 lights stay,
  and in the Build 5 decals and 8 emitters too.
- **Map grid** (the rail's button, or the Map menu) replaces the Map size window. It shows the play area with a
  handle on each side that can move (`placeGridHandles`).
  - The red handle is the far X side, the blue one the far Y side, and the green one the top.
  - A drag follows its axis (`alongLine`) by whole tiles (96) or levels (64), within `gridRule`.
    - A map as it is, the blank map included, only grows, across and up (since 13 November any map, where the
      compiler refused all but the blank map before).
    - Each axis goes up to 256 tiles or 30 levels, or the map's own where that is more (`project.js stageMax`,
      `compiler.py stage_max`). The limit was 128 until 16 November, and TempleShip (45 by 203) snapped back
      (T-41); no map of the game's is past 256.
    - On a map that keeps its own cursor volumes, the Build's `shell.py grow_cursors` stretches those that reach the
      old far X or Y side to the new one, and with more levels clones the topmost plain one into even storeys of 192
      over the whole grid, from the top of its own up to the new top. `floors.js cursorStoreys` (given the map's own
      size; `storeysNow` in app.js) and `compiler.py cursor_storeys` draw and check the same storeys.
    - A cleared map goes from 1 tile or level up to the same limits.
  - Each drag is one undo step (`commitStage`). The panel gives the size, the notes (`sizeNotes`, the ground's level
    on a cleared map), **Lay the map's ground over the new area** (`stage.ground`, on a map as it is), **The map's
    own size** and Done (Esc).
  - The Build's shell stage lays more of the map's ground where it is laid as planes (Bar: 6 planes for 60 by 45,
    built in 8 s). Elsewhere the new area is open air for the project's floors.
  - **The map's own scenery in the new area is made walkable** (F-100; `shell.py walk_scenery`,
    `native_copy.make_walkable`). The ground planes and pavements a map is seen against beyond its play area save
    their collision off (`bCollideActors`, `bPathColliding`, the mesh's `CollideActors` and `BlockRigidBody`), so
    the battle finds no floor on them. The shell stage (`scenery_to_walk`) takes each level actor that meets all
    of these:
    - it is no taller than 32;
    - it lies within the grid's levels, from a quarter level under its bottom (not the sky's ground plane);
    - it reaches past the map's own far X or Y side;
    - it saves its collision off, which goes on, or it is a floor piece already (it collides and keeps
      `bPathColliding`).

    The tiles they give floor on (`scenery_tiles`, at the level of each one's top) get the seed bit. A new tile above
    the bottom level is open air, which the rebuild passes over. The rebuild volume reaches the level over the
    highest of them, and no ground plane is laid in a block one of them covers.
    - Act1_IntroLevel grown to 95 by 25: 21 pieces are made walkable.
    - CsmallScout_Farm grown to 91 along Y, ground laid: its raised backdrop's 24 floor pieces, at 0, two levels
      over the play area's ground. Their 844 tiles are queued, and the ground is laid in 9 blocks, not 21. Before,
      it was laid at -128 under the raised backdrop, and that was the only floor there. A copy of such a piece placed in the grid gets the same
    (`native_copy.build`, the copy's `walkable`). The compiler's `scenery_floor` and the page's zone notes count those
    pieces as floor for a landing zone, since the map's saved floor tiles stop at its own grid.
  - A landing zone's gizmo lands its ground on a level of the grid. A zone saved off the levels comes onto one with
    its first move.
- **On a cleared map** the Build takes out what the editor never showed (the compiler's `cleared_mark`,
  `native_copy.clear_level`, `shell.py --clear`) and gives the grid even cursor storeys.
- **The ground grid** (View options, **Ground grid**, on by default) lies at the landing zones' height, on the tiles
  with no floor that stays (`refreshGroundGrid`). Placing over nothing lands on its plane. Level snap and the Floor
  tiles overlay leave out a cleared map's gone floors.
- **Landing zones** come from the map's LWR lines (`GET /maps/<id>/landing-lines.json`) and its own landings (export
  22's `landings`), matched within 4 units ([spawns.js](web/spawns.js), the twin of
  [spawns.py](spawns.py)). They are drawn with LWR's mutator offsets: the frame, the evac box, the six
  soldier tiles and an arrow.
  - A landing with no drop zone frame (Act1_IntroLevel, TempleShip, AlienBase01 and 02, DEMO_SonOfFacemelt) is a zone
    too: `fitZone` fits the mutator's layout to its soldier points (direction, place, and a ground at the lowest of
    each point's height less 48 and its PointInSpace's). While the zone stays there, its six tiles are the map's own
    points (`soldierSpots`; the tutorial's are its own layout), and the Build leaves the landing as it is. Moved, its
    actors take the mutator's layout at the new place (native_spawns.py, from where the fitted zone's frame would
    stand).
  - Zones are picked in the **Landing zones view** only (Shift+Z, the rail's button under Lights; `setZonesShown`,
    `zonesOn`): they are drawn over everything there (depth test off), a click picks one (its number badge first) or
    lets the picked one go, and never a piece or a light. The normal view shows them but picks pieces, the landing's
    too. Picking a zone (`pickZone`) or placing one from the Add panel turns the view on; leaving it lets the zone go.
    It is one of the four views with Normal, Buildings and Lights.
  - Pick one by clicking it in that view. The panel sets its kind (normal or inside) and **Used by**, and
    copies or deletes it.
    - **Long War** unticked is `lwr: false`.
    - **Plain EW** is `ew: true`: one of the map's own landings is moved to the zone.
    - No more zones can be ticked than the map has landings of its own, and one stays ticked; each refusal says
      what to do instead. Deleting the only ticked zone ticks the first zone left.
    - A copy is Long War's alone.
  - **The zone gizmo** (a TransformControls of its own, `zoneGizmo`) stands on the picked zone's StartLoc, on the
    ground. Its arrows (G) move the zone by whole tiles (96) across and whole levels (64) up, snapped as it drags.
    R shows its ring, which turns the zone by quarter turns about the vertical only. A turn about the view's up is
    the opposite yaw in the game.
  - The zone is drawn moved as the gizmo drags (`zoneDragView`). Each drag is one undo step, and Escape during one
    puts it back.
  - Keys: Delete, Ctrl+D, `[` and `]` (turns), G and R, Escape.
  - The Add panel's **Landing zones** kind (`zoneEntries`, one entry) places one with a click: the one way to add
    a zone.
  - The first change writes the project's `landingZones`. Absent, the base map's lines and landings stand; an empty
    list means no zone. The zones ticked Plain EW, in list order, take the map's own landings, moved in the package
    for plain EW ([native_spawns.py](../bake/native_spawns.py)); their pieces move with them in the view. A list
    with no zone ticked (a project saved before the tick) goes by order: the first zones that name no mission. The
    first change writes that out as ticks (`explicitZones`).
  - A full Build relights such a move (F-98): `native_copy.py` hands each moved piece with a mesh (the grounded
    Skyranger) to `relight.py --moved-in-place` with its old pose, so its shadow leaves the old place and falls at
    the new one; its own lightmap keeps its bake. A build whose one change moves a landing is baked for it. Under
    LWR, XComLZMutator's `HideDropShip` takes every prefab Skyranger away at load (Act1_IntroLevel's, placed by
    hand, stays), so there only the shadow shows.
  - The panel notes, without blocking: soldier tiles outside the grid or over no floor, a piece on one, a zone
    played under LWR only or nowhere.
  - **Land here** (with a project open) is Play in game with `{project, zone}`: under LWR that zone's line alone; one
    of the map's own opens on its spawn group. A project still on the map's lines takes them in first.
- Checked by `browser_smoke.py --only clear-map` and [clear_map_test.mjs](tests/clear_map_test.mjs).

### The piece list (Add)

**Add** (A, or the box button in the tool strip) opens **Pieces in this map**: one entry for each distinct piece the
map has placed, 250 on the Bar and 175 on the Temple Ship.

- An entry is what copying one placed instance would take along: the actor with its linked pieces. A van is one
  entry of 7 to 14 parts, named after its prefab (`PRE_MovingVanA`); a single piece goes by its mesh name. Instances
  alike in every part (class, archetype, mesh, materials and tint) are one entry, with a count ("×12"). Pieces deleted
  in this session still have their entry: the list is the map as exported.
- Each row has a thumbnail, the name, the kind (Destructible, Scenery, Fracturing, Interactive, Physics, Ladder,
  Collectible, from the actor class), the mesh package, the number of parts, and width × depth × height in game units.
  Hover for the mesh path and materials.
- Classes awaiting a build recipe carry the **M3** milestone. Scenery, destructible props and collectibles build.
  Ladders, framed doors, cars and vans joined on 8 November (EXP-22, EXP-23, EXP-24). Frameless doors and opacity
  fade scenery also build. Fracturing pieces (walls, storey floors, roof
  slabs, a bar's counter) and physics props have built since 9 November, switched on before a game run of them
  (run 1 of [EXP-28](../../research/experiments/EXP-28-fracturing-physics.md) passed the same day on Bar). A copy of
  a storey floor gets floor in the game only on the tiles with standing room over them: under a duct or a low
  ceiling it stays without (F-71). A fracturing piece has
  the recipe snap under tile snap, as ladders and doors do (whole tiles, whole storeys and quarter turns from where its
  original stands): the map saves its fragment columns one to a tile, and the Build carries them with the copy, exactly
  on the grid (off it, with the off-grid warning). A physics prop has no pose rule. A collectible (a
  power core) is marked **Mission loot**, and its copies **Not loot**: a copy breaks at its first damage, as the
  original does, but the game doesn't count it as loot. A car's body, which
  names its glass as partner, builds with its car, as the compiler says. An assembly takes its latest part's milestone. The kind
  list gives each kind's count ("Scenery (85)", "Fracturing (37)") and adds the milestone only to a kind none of
  whose entries build yet ("Interactive (2) · M2" on a UFO map). Pieces of such a kind can be placed and saved; they
  are not built until their milestone (first-editor plan, section 6).
- **Filter** by name, kind, mesh, archetype or material; pick a **kind**; on maps with backdrop, choose **Play area**
  or **Backdrop**; sort **A to Z**, **Largest first** or **Most used**.
- **Floors** (in the kind list, and a search for "floor") lists the map's floor pieces, each with its size in tiles
  ("floor, 8 × 4 tiles"). They are not a class of their own in the game: a floor piece is one that carries the map's
  saved floor tiles (the game's bake names the piece under each walkable tile), is flat (48 units or less) and is a
  single piece. A thin one (8 units or less) lying on another floor piece is a decoration, not a floor: Bar's rugs and
  the plates on its floors, placed as any piece is. Bar has 15 (asphalt, the sidewalk pieces, the bar's two storey
  floors, the roof floors), Temple Ship 31 (its alien floors, trims and caps), Forest Trench its grass planes. The
  rules are in [floors.js](web/floors.js).
- **Lights** (in the kind list, and a search for "light") has Point Light and Spot Light, to add a new light (see
  Lights below). Their rows show what each starts as, its radius and brightness, the map's number of such lights, and
  a Test tag while light edits wait for their game test.
- **Invisible** (in the kind list, and a search for "cover" or "floor") has the editor's two hidden pieces.
  **Cover block** places an invisible piece that gives cover, as LWR's patches add cover where a map lacks it
  (URB_PoliceStation's `highcover`, `Cover2x4`...): a 1 × 1 block of high cover, one tile tall; once placed, the
  piece panel's **Cover block** section sets any width and length from 1 to 16 tiles, its height from 1 to 8 tiles
  and the cover, high or low (one undo step each). A block is whole tiles from its corner (placed by its first tile,
  so tile snap keeps it on the grid), from 12 units below the floor to 96 above it for high cover and 84 for low, as
  LWR's own helpers stand, each tile of height past the first adding 96 to the top (two tiles: 192, as a 1 × 2 block
  stood on end). **Invisible floor** (EXP-32) places a hidden plate units can stand on, two units thin, its top at
  the height it stands at (the Z field); its section sets its width and length. The game looks for a tile's floor
  along one line straight down through the tile's centre, so a plate is the tile's floor only where its top is over
  the ground there, and that line meets a piece's collision, which often stands a few units over its drawn surface
  (F-83): the ground here is the collision's (`collision.json`; the drawn mesh until it comes, or where it can't be
  read). Placed from the Add panel, a floor's top goes 1 unit over the ground at its first tile's centre; the
  section says how far its top is over the ground at each tile's centre (or that it is below it), and **Fit to
  ground** raises or lowers it to 1 unit over the highest of them. Over a ramp's sloped tiles a plate makes a flat
  floor, so a unit on it gets cover (F-81); the plate itself is ignored for cover, so the tile below it doesn't get
  half cover from it as from a step (F-82). The Build
  makes it of one hidden level actor per tile, each a valid destination with no cover forced: under 4 units thick and
  a tile across, the tile rebuild's occupancy test skips it, so it carries a floor without filling its tiles. The editor draws it as a see-through box, orange for high
  cover and blue for low; in the game it is hidden, blocks movement and gives units beside it its cover (low cover
  lets units see over it), but not to a unit on a sloped floor tile, where the game works out no cover at all (F-81).
  It moves, turns, copies and deletes as a piece does, and joins groups. In a group with **Break together** on, a
  cover block goes when a breakable piece of the group is destroyed (the Build makes it as a hidden prop for that:
  `cover_blocks.BREAKING`); otherwise it never breaks.
  The Build makes it from a recipe on any install, plain Enemy Within included ([cover_blocks.py](../bake/cover_blocks.py):
  a hidden XComLevelActor with LWR's helpers' properties, on a box mesh of the block's size with its own convex
  BodySetup, written by the Build), in its tiles as a copy is. A project saves either as an added piece with
  `template` {kind: cover, version} and `cover` {width, length, type, height} (`type` high, low or floor; the first
  records, {width, length, height: high or low}, open as one tile tall). Blocks played in EXP-31 runs 1 to 3 (they
  block and give cover on level ground); the floor and tall blocks not yet.
- **Click an entry** to start placing it. A see-through preview follows the cursor (fainter where walls or roofs hide
  it). A click in the view places a copy there: the pivot goes where paste would put it, on the piece under the
  cursor or level with the original, snapped when snap is on; **R** turns it first. With Level snap on (the
  default), a floor piece's height snaps by levels: it keeps the height it has in the map, moved by whole levels
  (64 units) to the saved floor under the cursor, so a sidewalk dropped on the road or on another sidewalk stands at
  the sidewalks' height (never stacked 18 units up), and a storey's floor dropped upstairs lands on that storey.
  With a floor chosen in the **Floor** picker (not All), it goes to that floor's height instead: in the building whose
  floor stands under the cursor, else the nearest building with that floor, so a piece dropped on the road beside the
  bar with floor 2 chosen goes up to the bar's floor 2. A building floor's height is that of its saved floor tiles near
  the bottom of its volume (Bar's floor 2 at 210, the Police Station's at 274), else the bottom. Across, it moves
  freely, or by snap (tile snap keeps it in whole tiles from the original, so kit pieces butt edge to edge). Pasting a
  floor piece snaps the same way. The copy becomes the selection,
  ready to move or turn. **Shift+click** keeps placing; **Esc**, or clicking the entry again, stops. Placing also puts the entry on the
  clipboard, so Ctrl+V places another. Each placement is one undo step.
- Thumbnails are drawn a few per frame when the list opens, in the corner of the main canvas just before the view
  is drawn over it, so they get the view's colours without a second WebGL context. They use a plain studio light,
  not the map's lights.
- Only pieces the map has placed are listed: the export has no other meshes. Other archetypes from the same packages
  and each piece's placement anchor are not shown yet.

**Floor tiles** (View options) shows the map's saved floor tiles, coloured by the piece that carries each (one colour
per kind of piece). A moved or deleted piece's tiles are hatched grey: the Build's rebuild checks them again. Copies
have no saved floor, so they show none. Hover a tile to name its piece; click it to select the piece.

A copy, or a piece moved, joins the cutaway of the building floor it now stands in, as the Build lists it
(`native_copy.copy_floors`, twinned by `floors.js copyFloors`, both passing
`tools/bake/tests/floor_membership_cases.json`): a piece listed in no floor stays so, a copy standing in no floor gets
none, a copy of a piece listed outside every floor volume (a ladder on an outer wall) keeps its listing. The piece
panel's Floors line follows it.

### Lights

The map's lights can be edited as pieces are (editor lights plan; export 18).
The Build makes light edits for every project: they were switched on on 9 November, after the first of their game
test's runs (EXP-26 run 1). A build with Bake the lighting bakes them. A quick build makes them in the map without baking
them, and the build window says what that leaves.

- **Shift+L**, the rail's bulb, or **Light markers** in View options shows the map's point and spot lights as markers
  that keep one size on screen: a bulb for a point light, a cone hanging from a spot light along its direction. Each
  takes its light's colour, grey when view only and hollow when switched off, and shows faintly through what covers
  it. In Interior only the lights whose radius reaches the play area show.
- **Area lights** (View options) adds the lights the bake made for glowing surfaces. They are view only and follow
  the piece they glow from. **Sun, moon and sky** lists the lights without a place.
- **A click on a marker** selects its light, ahead of the piece behind it. Ctrl or Shift adds it to the selection;
  pieces and lights selected together move together.
- **The light panel** has colour (a picker, and R, G, B), brightness, radius, falloff, a spot light's inner and outer
  cones, and On. A typed value applies on Enter or when the field is left, as one undo step; Escape puts it back.
  - Values out of range are refused: brightness 0 to 100, radius 1 to 16,384, falloff 0.1 to 64, inner cone 0 to
    89°, outer cone up to 89.99°.
  - The cone fields show the cones the game lights with. A stored cone wider than that stays as stored unless you
    change it.
- **Drag handles** on the selected light change it in the view:
  - the radius: a white dot on the left edge of a point light's sphere, or at the end of a spot light's axis;
  - a spot light's outer cone: a dot on the left of its rim;
  - its inner cone: a smaller dot on the right.
  The light's shapes, the panel and Map lighting or Solo follow while you drag. The release is one undo step, and Esc
  during a drag puts it back. Radii go in whole units and cones in half degrees, within the panel's limits; the inner
  cone stays inside the outer. A handle takes the press ahead of the gizmo and the camera. Where a spot light's inner
  cone is 0, its dot sits on the radius dot, and the first move picks the one whose way it goes.
- **What it lights:** the selected light's cones or radius spheres, with a line down to the floor. The panel counts
  the pieces it lights. **Outline the pieces a light reaches** (View options, off at first) outlines them: in teal the
  pieces its bake lists it in, and once it is moved, changed or added, in orange the pieces its new reach touches. A
  full build relights those, and the panel warns when they are over 300.
- **Solo** (S, or the panel's button) dims the map and lights it with the selected lights alone (up to four), with
  UE3's falloff and live shadows. S again, or a click on the button, ends it.
- **Map lighting** (View options) takes the lights as edited.
- **Copy, paste and delete** work as for pieces. **New lights** are in the piece list (Add): its **Lights** kind (and
  a search for "light") has **Point Light** and **Spot Light**, each with an icon in its starting colour. Each starts
  as a copy of the map's first light of that kind that can be edited, with that light's values; for a map with no spot
  light, Spot Light is the editor's own (recipe version 1). Choose one and click in the view to place it, as a piece.
- **View only:** area lights, lights switched by the map's scripts or by a breakable piece, a streamed level's
  lights, the sun and sky, lights with their own lighting channels, lights in no lightmap, and every light of an
  export older than 18. The panel says which reason applies. For an export older than 18 the page asks to prepare
  the map again, which exports it again (about half a minute; projects and edits are kept):
  - a dialog in the middle of the window when the map opens, with **Prepare now** and **Later** (Later leaves a
    banner that opens the dialog again);
  - the same dialog in place of Build or Play in game of a project;
  - **Prepare the map** in the window of a build that failed for want of a newer export.
- **Glowing pieces:** a piece the bake made area lights for says "Glows · N lights" in its panel. Moved, its lights
  move with it; deleted, they go; each copy gets copies of them. An area light the export couldn't tie to one piece
  ("May glow · N to settle") must be settled before a piece it may glow from is moved: select the light, then
  **Assign glowing piece** (and click the piece), or **Keep fixed**. **As exported** undoes either.

### Projects

A project saves the edits on one base map, to reopen and, later, to build (first-editor plan E1). Its format and
rules are in [the editor contracts](../../research/editor-contracts.md).

- **Project**, first in the header, opens a classic menu: the open project (name, revision, when saved, the variant
  name it will build as), then **Save** (Ctrl+S), **Save as…**, **Open…** (Ctrl+O) and **Close project**. Under them,
  **Recent** lists the three projects last opened or saved in this browser (or else saved most recently), the open
  one aside; a click opens one.
- **Save as…** and **Open…** open a file picker over the projects folder (shown as "Look in"). It lists the projects
  with their map, revision and when they were saved; the column heads sort it. Arrow keys move through the list,
  Enter or a double-click picks, Esc cancels. Projects with changes kept for recovery are marked, unreadable ones are
  listed greyed out.
  - **Save** lists this map's projects (a project belongs to one map) and starts on the open project's name. A new
    name makes a new project from what is on screen, with a map name of its own. The open project's name saves its
    next revision (renamed if only the case changed). Another project's name asks first ("already exists… Replace
    it?"); replacing puts what is on screen into that project as its next revision, keeping its id and map name,
    with the revision before kept as a backup.
  - Under the name box Save shows what the project builds as, before anything is written ("Builds as
    CommercialRestaurantFix · map names keep to 24 characters"): for a new project, the server's answer
    (`POST /projects/output-names`, [outputnames.py](outputnames.py)): the project's name as one word, accents taken
    off, at most 24 characters (so its patch, `patch_<name>`, keeps to UDK's 30), numbered (`_2`, `_3`…) when another
    project, a build in the builds folder or a package or record of the game installs has it, with the reason; for the
    open project or one replaced, its own name, fixed when it was first saved. Save waits for the answer for what is
    typed; a name taken between the answer and the save is refused, and the dialog stays open with the next one. The
    server refuses a save that changes a saved project's names: Save as under a new name makes a new project instead.
  - **Open** lists every map's projects ("Show" narrows it to this map) and starts on the open project. Typing finds
    the first name that starts with the text. Opening a project of another map switches to that map.
- **Ctrl+S** saves the next revision; without a project open it opens the Save dialog. The address carries
  `?map=…&project=<id>`, so a reload reopens it. Saving under another project drops the changes kept for recovery of
  the one open before: they are saved now.
- On a patch preview or piece study, Save and Save as… are off (projects edit a map's original layout); Load and the
  recent list still open a project on its map.
- **Opening** a project replays it onto the map as exported: originals moved or deleted, copies added. It also puts
  back the camera from the last save, and starts with an empty undo history.
  - The project names its pieces by package, level and actor, never by short name.
  - It binds to the map's SHA-256. A project made on a different package says so.
  - Edits naming pieces this export lacks are kept and saved back unchanged; the import notes count them.
- **Unsaved changes** are kept on the server a second after each change (never half a drag), in a draft of the page's
  own: two tabs keep one each, and each deletes only its own. Reopening offers back the newest: **Restore them** or
  **Discard them** (which offers the next).
- **A save based on an older revision** is refused, for example when another tab saved first. The banner offers to
  overwrite it or open the saved one.
- **Leaving with unsaved changes:** the browser asks before leaving, and before switching map or layout or loading
  another project.
- **Storage:**
  - Each project is one file in the projects folder (the **projects** setting, below), named after it: `Bar remix.json`. To share a
    project, send that file; to open one shared with you, put it in the projects folder under any name ending
    `.json` (Load lists it).
    - Characters Windows forbids in file names become `_`. When another project already has the file name, the
      file gets ` (2)`, ` (3)` and so on.
    - A save under a new name renames the file. A file renamed or moved in by hand is found by the project id
      inside it, and its next save names it after the project again.
    - Two files with one project id (a copy made beside it): the newest revision is the project. The other is listed
      greyed out as a copy.
  - What stays on this computer is kept by project id in the hidden `.workshop` folder beside them:
    `.workshop\<id>\project.prev.json` (the revision before) and a `recovery-<page>.json` for each page's unsaved
    changes (`recovery.json` from before 20 November 2026).
  - Project folders of the earlier layout (`<id>\project.json`, before 8 November 2026) are moved to this one the
    first time the server reads the folder. One of a project that a file here holds already never writes over it:
    the newer revision is the project, and the other is kept beside it as `<name> (kept copy).json`.
  - Saves are atomic.
  - A project with another schema version is refused with a message, not converted.
  - The **projects** setting moves the folder; `serve --projects <folder>` overrides it for one server (tests use a
    scratch folder).
- **Build…** (Ctrl+B, or Build in the header) opens a small panel ([`build_options.js`](web/build_options.js)) with one
  choice, **Bake the lighting**, off each time it opens. Build (or Enter) then saves the project if it has unsaved
  changes and builds the saved revision into a variant package in the builds folder
  ([`tools/editor/build.py`](../editor/build.py)). The package has:
  - the base map with the edit made in it: copies as new actors in their tiles, linked when they break together, and
    hidden pieces taken out;
  - an edit patch, only for what the map can't take yet (nothing in M1);
  - a copy of each landing intro the map's records stream;
  - a README with the config lines (a `DefaultMaps.ini` record for each mission the map serves), and a manifest.

  Save itself never builds. It installs nothing; for our lab, `tools/lab/lab_install.py` installs packages in the test
  slot.
  - **Without baking** (the default; `build.py --quick`) the build takes seconds. The edit is made in the map exactly
    as a baked build makes it, so pathing, cover and line of sight in the game are the same (findings register T-20).
    The lighting is wrong, though: copies keep their originals' lighting and cast no shadows, and deleted or moved
    pieces leave their shadows behind. It is for checking a layout in the game before the minutes of baking.
  - **With baking**, the copies get their own lighting and the pieces near the edit are relit, which takes minutes. The
    new lightmaps go inside the map file (`tools/bake/inline_lighting.py`), so the package has no texture cache to go
    beside it (a package built before 19 November 2026 has its `.tfc`, and so does a map that can't take its lightmaps
    in, its build says why). The panel says how long the project's last build of each kind took.
  - A package replaces the project's last one either way. The build window, the Project menu and the Installs section
    say when a package's lighting is not baked, and its manifest (`quick`) and README say so too.
  - The server runs one build at a time in the background ([`builds.py`](builds.py)): `POST
    /projects/<id>/build` starts it (`{"quick": true}` for one without baking), `GET /projects/<id>/build.json` gives its
    stages (with the time each ended), the step running and its progress, the log's last lines and the project's last
    package (whether it is quick, and how long the last full and quick builds took).
  - **While it builds, a window covers the editor.** It takes no clicks or keys until the build ends, since the build
    takes the saved revision. It shows:
    - the steps with their times; the patch step only when the edit makes a patch, which no project does today;
    - the step running, with a bar for the pieces the relight has done (its `progress:` lines; a small edit takes a
      few minutes, most of it baking the lighting);
    - the log's latest lines, or the last 40;
    - the time so far, with a bar against the project's last build of the same kind (full or quick) when there is
      one.
  - The window ends with the package's folder (Copy the folder path) or why the build failed, and closes with Close
    or Esc. Once built, its **Play in game** installs that build and starts the game on it, as the header's
    Play last build does (asking the server first, so a closed install or an open XCOM says why in the window); the
    outcome shows in the window, and a build Build and play started can be played again from there. The folder's path, and a bug report's zip once saved, are links: a click shows it in Windows Explorer
    (`POST /builds/reveal`: a folder opened, a file selected, never run; only paths in the builds folder). A reload picks a running build up again, and the Project menu shows the last build. If the server stops
    answering mid-build, the window says so and can be closed.
  - The **output** setting moves the builds folder; `serve --builds <folder>` overrides it for one server.
  - **Each build is an attempt** ([`builds.py`](builds.py)): an id of its own (`build.py --attempt`, written in the
    manifest and at the end of the build's id) and an origin (the editor's Build or Play in game's, a prefab test, the
    build queue's). Cancel with `{"attempt": id}` stops only that attempt, so a stale page never stops a newer build.
  - **Its processes are contained** ([`procs.py`](procs.py)): build.py is started suspended, put in a Windows Job
    Object that kills its processes when its last handle closes, then resumed. Cancel ends every process of the build
    (patchtool, UDK, the relight and its workers), and so does the server's death, however it dies. A build ends only
    once each of its processes has (findings register T-38, T-39).
  - **A package goes in through a journal** ([`publication.py`](publication.py)): the old package aside, the new one
    in, each step written down first in `<builds>\.work\publish\<variant>.json`. A build killed mid-swap leaves the old
    package or the new one, never half of each: the next server settles it, or blocks that variant with the reason.
    An operating-system lock per variant (`<builds>\.work\locks`), released when its holder ends however it ends, is
    held while a package goes in and while Install in the game, the map pack or Play in game reads one. Command-line
    builds (`tools/editor/build.py`) take the same lock and journal.
  - **A restarted server proves the old one's builds gone** before anything builds: each running attempt has a
    record in `<builds>\.work\writers` (its process and creation time, and the folder it writes). One still running,
    or one whose state can't be known, keeps the build slot busy with the reason.
- **Play** (in the header) starts the game straight in a battle on what is open, for testing in the game: no
  campaign to start, and no line the game had is changed ([`play.py`](play.py), [`gamelaunch.py`](gamelaunch.py),
  [`installs.py`](installs.py); how it was found and played: `research/experiments/EXP-29-direct-map-launch.md`).
  - **How the game is started.** With `-EXEC=<file>` the game runs a file of console commands as it starts, and the
    console's `open <Map>` loads a map as a battle with no campaign behind it. The editor writes the file
    (`XEW\Binaries\XComMapWorkshop-play.txt`) and starts the game through Steam (`steam.exe -applaunch 200510
    -EXEC=…`), which needs no launch option set; the game's launcher still asks which game, and Enemy Within is picked
    there (an install whose launcher was replaced starts the game at once: findings register F-84). Steam runs the folder its manifest names, so a game folder parked beside it under another name is refused.
    A game folder in no Steam library is started by its own `XComEW.exe` (not tried).
  - **The battle** is an ordinary one on the map: its streams and landing as its `DefaultMaps.ini` record has them,
    and aliens of the game's choosing. The commands set the test squad and tell the game to load soldiers'
    content when it is needed; without them the squad is the game's own developer one, invisible and, under Long War,
    half unarmed. The squad is resolved once for each play, before anything in the install is changed, from the
    saved squad (`test-squad.json` beside the settings, six squaddies until one is saved) and the install's own data:
    `gamedata.py` reads its enums (`tools/upk/script_enums.py`, cached by the package's hash under
    `<cache>\.gamedata`), its `DefaultGameCore.ini` rows and its localisation; `squadrecords.py` checks each unit
    under the family's rules (Long War Rebalance: soldiers, MEC troopers and SHIVs, eight units; plain Enemy Within
    and Long War: soldiers, six) and writes the records. A squad with an error stops the play before any file is
    touched; the play's reply carries the squad's name, count, warnings and notes. The records and the rules behind
    them are in `research/test-squad-records.md`.
  - **The squad API** (`squads.py`): `GET /squad.json` (the document, its revision, the install's choices and the
    check), `PUT /squad.json` with the revision it was read at (a different one is refused with 409 and the saved
    squad), `POST /squad/check` (a draft checked, nothing saved), `/squad/import` and `/squad/export` (the shared
    `.xcomsquad.json` form). Saving is atomic and keeps the previous file as `test-squad.prev.json`; a file that
    can't be read is kept aside as `test-squad.bad-<time>.json` on the next save. `serve --squad <file>` points a
    test server at a scratch squad.
  - **With a project open, a build of it** is installed first: the package's files are copied into `CookedPCConsole`,
    a record of its own is added to `DefaultMaps.ini` after the base map's (one of the base map's records under the
    variant's name, out of rotation, with its own landing intro streamed), and the base map's landing zones are added
    under that name (the project's own, when it has `landingZones`: see Clear map, the ground grid and landing
    zones). The record is an abduction whatever kind the base map's is (Temple Ship's is the final
    mission's), as the intro slot's was; a Temple Ship variant hasn't been played this way.
  - It opens Build's panel first ([`build_options.js`](web/build_options.js)), with the same **Bake the lighting**
    choice, off by default.
    - **Build and play** builds (saving first if there are unsaved changes), and installs and plays the package when
      the build ends; the build window says so.
    - **Play last build** shows only when the last build is of what is on screen. It plays that build as it is, and
      is then the focused default, so Enter doesn't replace a baked build with an unbaked one.
    - Esc or Cancel does nothing.
  - **With a map alone, the original map (no edits):** nothing is installed, since the game has its records, and the
    battle is of the kind the map's first record names (only abduction maps were played). If that
    install's copy of the map differs from the game install's the editor reads, the message says so. The one
    exception is Basic Training (Act1_IntroLevel, the tutorial's map), whose records LWR comments out: opened with
    no record the game crashed (F-78), so a live copy of its abduction record goes in for the play, out of
    rotation (`installs.install_map_record`), and Game maps' Undo everything takes it out. A map whose records the
    editor commented out (replaced by a build, or switched off in Game maps) gets such a copy too, named apart.
  - **The game's own config during a play.** The two `set` commands make the game save its `XComContent.ini` with
    them in it (the engine saves a class's config after `set`). The editor keeps the file aside before it starts the
    game and puts it back once the game has closed: a watch in the server does it, and a file still kept when the
    server next starts, or at the next play, goes back then.
- **Where it plays:** the **install** setting (a game folder), else the game install the editor reads. Any LWR
  install works, and plain Enemy Within as a best guess (no `DefaultLZMutator.ini`, so no landing-zone lines; not
  checked in the game). Nothing in it is specific to one computer.
- **A play leaves nothing in the game.** Once the game has closed, the server's watch takes out what the play put
  in (`installs.clear_play`): the build's record, its landing zones and files, and the commands file. If the server
  was stopped meanwhile, the next play, or the page's next look at the install, does it. What the project manager
  installed for campaigns stays. A tactical save made in a test battle on a build won't load afterwards. A server
  started with `--dry-play` starts no game, so it leaves a play's things in to be looked at.
- **Two ledgers, in the install itself** (`<game>\XCOM Map Workshop`): `play.json` for what a play put in, and
  `installs.json` for what stays until it is undone (the project manager's installs for campaigns, the records
  switched off in Game maps). A file or landing-zone block is noted in one only, the campaign's first: an install
  for campaigns takes over what a play of the same build put there, so clearing the play never takes it away. An
  `installs.json` from before the split is read as a play's. There are copies of
  `DefaultMaps.ini` and `DefaultLZMutator.ini` (where the install has it) from before each change in `backups\`. So it follows the folder if it is
  renamed or moved, and each install has its own.
- **Undo everything**, in the Game maps window (below; it was the Project menu's Remove from game), takes it all back out: the records and landing-zone lines it added, the files it copied
  (unless they changed since), the commands file and any config kept aside. Both INI files end up byte for byte as
  they were.
- **An install from before 9 November 2026** made a map the first mission of a new campaign (Install as intro map: it
  rewrote the record named `URB_CommercialAlley_EWI (Commercial Alley Redux) |0`). Its record of that is still read:
  the next play, or Undo everything, puts the game's own line back.
- **The editor reads an install the way the game does:** the map list, the exporter and Build read `DefaultMaps.ini` with the
  editor's lines taken out (`installs.maps_text`), so an installed variant never shows up as a map or a record.
- All of these refuse, with the reason, while XCOM runs. A package file already in `CookedPCConsole` is replaced only
  when the editor put it there for the same project (its ledger says whose) and it is unchanged since; anything else is
  refused before a file is copied (`installs.preflight`), and a Build refuses at its start to write a name anything
  but the project holds (`outputnames.Claims`; the patch's name only when the edit makes a patch). The one exception
  is the lab copy (its `XComLab-copy.txt` marker, with the **lab** setting set): a file of the project's own names
  that the lab's deploy tools put there before the editor could install (the bake fixtures' ledger, patchtool's
  `deployed.txt` and `seeded.txt`: `installs.lab_deploys`) is an earlier test of the project. It doesn't stop the
  Build, and an install replaces it if it still has the bytes the lab gave it, keeping it in that change's
  `backups` folder (`labFiles` in the ledger) and putting it back when the editor's file comes out.
- **Installs**, in the Game menu (the arrow beside Play): the game install the editor reads (the **game** setting, resolved
  to its game folder, with its kind: Long War Rebalance or Enemy Within), the install it plays in and whether that
  can be played now, how the game is started there, and what the editor has installed in it.
  - The server's routes ([`play.py`](play.py)): `GET /play.json`, `POST /play/start` (`{"project": id}` or
    `{"map": id}`) and `POST /play/remove`.
  - `serve --install <game folder>` points a test server at a scratch install, and `--dry-play` makes it do
    everything but start the game.
- **Manage projects…** (Project menu) opens the project manager ([`manager.js`](web/manager.js),
  [`manager.py`](manager.py)): every project with its last build (when, of which revision, baked or not, the editor
  version that built it), the missions its base map serves and what is in the game of it. The projects are listed
  on the left, the selected ones on the right with what to do with them.
  - Each row has the project's name, its base map and when it was saved, a badge when it is in the game, and its
    last build's state in one word: **Ready** (built, baked, of the saved revision), **Not baked** (a quick build),
    **Out of date** (built from an older revision) or **Not built**, beside its revision (`rev. 1 of 3` when out of
    date) or, for a build by another editor version, that version. The tooltip has the rest (when, the build id,
    the folder).
  - The list filters by text (name, map, mission, "baked", "not built"…) and by state (the chips **All**,
    **Ready**, **Needs a build**, **In the game**, each with its count), sorts by **Sort** (last saved, last built,
    name, map), and rows are ticked one by one, as a Shift+click run, or all that the filter shows (the header's
    box, Ctrl+A). The selection keeps projects the filter hides, and says how many.
  - Each selected project with a build goes into campaigns its own way, chosen on the right: **Additional** (the
    variant's records go into the rotation beside the base map's) or **Replace** (as well, the base map's own records
    for the missions the variant has records for are commented out, a `;` before each line: that is known to stop the
    game using a record, which `bInRotation=False` is not; a record of a mission the build has none for, its project
    being for other missions, stays in use: F-118). It starts as the way it is in the game now, else Additional; **Set all to** sets
    every selected one. A variant gets one record per record of its base map, each in or out of rotation as the base
    map's is. So one install, or one map pack, can hold maps that replace their originals beside maps that are
    added. The requests carry each project's way as `"modes": {project id: mode}`; a pack with both says
    `"mode": "mixed"` and each of its maps its own `mode`, which the pack's scripts go by. The warnings for a
    selected project (below) are listed under it.
  - **Council missions** (and the story's) don't come from the rotation: the game asks for their map by its record's
    display name (`XGFundingCouncil.BuildMission`; Long War's `XGFundingCouncil_Mod.FixDisplayName` takes the last
    record of that council type whose name contains it), and their records are out of rotation in the install. So a
    replacing variant's record for such a mission keeps the base map's display name, and the base map's is commented
    out. Beside the original, a variant is never picked there, but for bombs under Long War, whose mutator makes an
    extra bomb mission of each extra bomb record. None of this has been played in the game yet.
  - **A new campaign's first mission** asks for its map by name too, though its record is in rotation: under LWR the
    record `URB_CommercialAlley_EWI (Commercial Alley Redux) |0` (`installs.FIRST_MISSION`; EXP-03). A replacing
    variant's record for it keeps that display name and stays in rotation, so the variant plays the first mission;
    with a name of its own the first mission found no map (F-117). Beside the original, the original keeps it, as it
    does when the variant's build has no abduction record (F-118).
  - **Map packs** say which records each replacing map comments out the classic way: `pack.json`'s `switch` (their
    display names, which `Install.cmd` goes by) and `keep` (the base map's records left in use); the README lists
    both. A pack from before `switch` comments out every record of the base map. On a card nothing is commented
    out: a replacing map's lines take the original records' display names, and Long War Rebalance 3 swaps a line in
    by its display name (`installs.rotation_plan(cards=True)`).
  - **Install in the game** does that in the install Play in game uses (`installs.install_rotation`): files copied,
    landing zones added, the records added after the base map's (after Play in game's own record, which stays first
    and separate). The Game maps window undoes it. The map list, the exporter and Build still read the install
    without any of it (`installs.maps_text`).
  - **Export map pack** ([`manager.py`](manager.py) `_pack`) writes `<builds>\Map packs\<Folder> v<n>.zip`, a pack
    that is a drop-in for Long War Rebalance 3 (3.00.00 beta 15 or later) and installs the classic way anywhere
    else. In the zip:
    - **`CookedPCConsole\<Folder>\`, the pack itself.** Copied into `<LWR install>\XEW\XComGame\CookedPCConsole` it
      is installed: the game reads it as it starts, no file of the game changes, and deleting the folder takes the
      maps out. It holds every build's maps, the landing intro copies, the pack's card and a `README.txt` saying
      what the folder is. `<Folder>` is the pack's name made one word (letters, digits and `_`, 24 characters at
      most), fixed at the first export.
    - **The card**, `LWRMapPack_<nnnn>.upk` in that folder ([`tools/upk/pack_card.py`](../upk/pack_card.py)), is
      what Long War Rebalance 3 reads the pack from: the pack's name with its version and author, each map's
      records, a `Pictures` line for each map without a picture of its own that lends it its base map's (found in
      the install's map-image packages), and the landing zones. The number is drawn once, from those no saved pack
      and no card in the install the editor reads has, and kept.
    - **A map's picture** for the mission screens is inside the map: the Build writes the project's picture into it
      as its top-level texture `MapPicture` ([`pictures.py`](pictures.py)), so the pack needs no picture file. A
      map whose name has `_Bomb`, `_Rescue`, `_Extraction` or `_Assault` in it gets a warning: the game drops that
      ending before it looks for the picture.
    - **One copy of each landing intro** for all the pack's maps, `<Intro>_<Folder>_<card number>.upk`
      (`_shared_intros`, [`tools/bake/intro_copy.py`](../bake/intro_copy.py) `pack_copy`; F-142): the intro of the
      install the editor reads with a case for each map after its base map's, and each map's moved landing. It
      takes the place of the builds' own copies in the folder and in the maps' lines. A map whose flight differs
      from another's of the same base map keeps its own copy (`introOwn` in `pack.json` says why).
    - **No `.tfc`.** A baked build's lightmaps are inside its map; a build from before 19 November 2026 has its
      cache put inside the map as it is packed (`_inline_lighting`,
      [`tools/bake/inline_lighting.py`](../bake/inline_lighting.py)), the build itself left as it is. Only a map
      that can't take its lighting in ships its cache, as `CookedPCConsole\<cache>.tfc` beside the folder, with a
      warning: the game finds a `.tfc` only in `CookedPCConsole` itself, never in a folder under it (F-140).
    - `README.txt` (both ways of installing, the classic lines to add by hand, the pictures, the notes),
      `pack.json` (schema 2: the pack's record, the card's lines as text, each map's classic lines, `switch`,
      `keep`, landing zones and warnings, every file's SHA-256, `folderFiles`, `cacheFiles`, `introFiles`), and
      each build's own README and manifest under `packages\<variant>\`.
    - **`Install.cmd`** and **`Uninstall.cmd`** ([`pack_scripts.py`](pack_scripts.py); they run
      `pack-tools\pack.ps1` with Windows' own PowerShell), so whoever gets the pack needs no editor. `Install.cmd`
      asks for the game folder (it offers the Steam install it finds, or takes the folder as its argument), refuses
      while XCOM runs, checks every file's SHA-256, and goes one of two ways (a third argument, `cards` or
      `classic`, forces one):
      - *Cards*, where the game's `XComMutator.u` holds the name `LWRMapPackCard` (Long War Rebalance 3): the folder
        is copied into `CookedPCConsole`, a cache beside it if the pack has one, and nothing else changes, but for
        the drop-in exclusion lines of a map whose project leaves scripted drop-ins where placed, which go into
        `DefaultRandomSpawns.ini` (a card can't carry them). It names another pack's card of the same number and a
        map file of the same name elsewhere under `CookedPCConsole`.
      - *Classic*, on any other install (Long War Rebalance 2, Long War, plain Enemy Within): it keeps
        `DefaultMaps.ini`, `DefaultLZMutator.ini` and `DefaultRandomSpawns.ini` as they are in
        `<game>\XCOM Map Workshop\packs\<pack id>-before`, copies the maps' files into `CookedPCConsole` itself
        (the card is not needed), adds each map's records after its base map's (commenting out the base map's
        records named in `switch` for a map that replaces it), and adds the landing zones and drop-in exclusions
        where the install has Long War's files. A map whose base map the game has no record for is left out, as is
        one the game already has a record for. The lines are the ones worked out from the install the pack was made
        from; the README lists them, to add by hand.

      Either way it writes down what it did in `<game>\XCOM Map Workshop\packs\<pack id>.json`. The pack id is the
      folder's name, the same at every version, so a newer version's `Install.cmd` takes the older one out first,
      whichever way that went in. `Uninstall.cmd` undoes exactly what was written down (files deleted if unchanged,
      added lines gone, commented lines back) and, after the classic way, says whether `DefaultMaps.ini` is then
      as it was before the pack.
  - **Saved packs** ([`packs.py`](packs.py)): each export writes `<projects>\packs\<Folder>.json` (name, folder,
    card number, version, author, the maps and each one's way). The manager's **Pack** list offers New pack and
    every saved pack; one chosen is exported again as its next version with its folder and card number kept. A pack
    whose record is gone is offered from its zip in `Map packs` (one from before cards too: it gets a number when
    exported). **Forget pack** removes the record, never a zip.
  - **Include editor project files** (above Export map pack; the browser remembers it) adds each packed map's saved
    project under `projects\` in the zip, byte for byte as it is in the projects folder, so whoever gets the pack
    can open and change the maps in the editor. `pack.json` lists them under `projects` (file, revision, the
    build's revision, SHA-256), and the README says where to copy them and which were saved again after their
    build. A project's map picture goes along beside it, as `<file>.picture.png`. The request carries it as
    `"projectFiles": true`.
  - Warnings never stop it: a quick build (lighting not baked), a build of an older revision, what each way does for
    the missions asked for by name, an own picture the game won't find by the map's name, a drop-in exclusion (a
    card can't carry it), a map file with an all-zero GUID (Long War Rebalance 3 takes it as missing), a lighting
    cache that goes beside the folder; and for the pack as a whole, two lines with one display name and another
    card of the same number in the install the editor reads.
  - Routes: `GET /manager.json`, `POST /manager/install` and `/manager/pack` (`{"projects": [id...], "mode":
    "additional" | "replace", "modes": {id: mode}}`, and for the pack `"name"` (a new pack's), `"pack"` (a saved pack's
    folder), `"author"` and `"projectFiles"`), `GET /manager/packs.json` and `DELETE /manager/packs/<folder>`. [`test_manager.py`](tests/test_manager.py) covers them on temporary installs.
    Install and pack take a lease on each package they read (`builds.lease`): a project the build queue is building,
    or about to, is refused with the reason.
  - **Build** puts the ticked projects (in the list's order, those the filter hides included) in the **build queue**
    ([`buildqueue.py`](buildqueue.py), [`build_queue.js`](web/build_queue.js)). The server builds them one after
    another while the editor stays usable: each a full build (lighting baked) of the project as it is saved when its
    turn comes, captured into a snapshot of its own (`<builds>\.work\queue-attempts\<attempt>\project.json`, with
    the build's log beside it). Build saves the open project first when it is ticked and has unsaved changes. The
    chip **Needs a build** lists the projects not built, built quick, built from an older revision or by another
    editor version.
    - While it runs, the queue holds the build slot: the editor's Build, Play in game's build and prefab tests are
      refused with the reason, and a build already running finishes first (the queue waits for it). A queue build
      opens no window, even on the open project; the Project menu shows its last build when it ends.
    - Each row's build state says where it is in the queue (waiting with its place, building with the step and the step's
      bar, built, failed), and a waiting row has Remove. The strip above the footer has the project building and its
      step, a bar of the rows done, the queue's building time, the time left going by each project's last full build
      (approximate, and saying how many have none), the failures with their reasons, and **Stop**, **Resume**,
      **Clear** and, for a file that can't be read, **Reset the queue**; once every project in it is built, it is one
      line. The editor's header has a chip (Building 2 of
      5, Queue stopped, 4 built, 1 failed) that opens the manager.
    - A failure is that row's alone: the queue goes on. Stop stops the queue's build (the project's last package
      stays) and starts no other; Resume captures the first waiting project again, the latest save, and builds it
      from the beginning. Rows added while it is stopped wait for Resume. Clear takes rows and results out, never a
      project or a package.
    - The queue lives in `<builds>\.work\build-queue.json` (replaced whole, the last good copy kept as `.bak`), owned
      by one server through an operating-system lock taken once its port is bound. A restarted server starts
      nothing: rows that were building settle once their builds are proved gone (one whose package went in is
      built), and the queue is stopped until Resume. The game install, the folders and the install names are pinned
      when a queue starts; while it runs or is stopped, Game install and checks refuses another install.
    - The page asks for the queue every 2 seconds with the manager open and the queue running, 5 closed, 15 when
      idle, one request at a time, backing off while the server doesn't answer.
    - Routes (each change carries `{queueId, expectedRevision, requestId}`; a stale queue or revision is 409 with the
      queue as it is, and a request id seen before gets the answer it got then): `GET /manager/queue.json`, `POST
      /manager/queue` (`{"projects": [id...]}`: add), `/manager/queue/stop`, `/resume`, `/remove` (`{"items":
      [itemId...]}`), `/clear` and `/reset` (`{"requestId", "confirm": true}`). [`test_buildqueue.py`](tests/test_buildqueue.py)
      covers the queue with a stand-in build, [`build_queue_test.mjs`](tests/build_queue_test.mjs) the page's
      wording and polling, and `research/experiments/EXP-65-build-queue-real-builds.md` real builds, a Stop, a
      server killed mid-build and a result lost after its package went in.
- **Game maps…** (the Game menu, on the arrow beside Play) opens the Game maps window
  ([`gamemaps.js`](web/gamemaps.js), [`gamemaps.py`](gamemaps.py)): every map record of the install's
  `DefaultMaps.ini` as the game reads it now, by map, with its mission, whether it is in rotation or asked for by
  name, and what the editor did to it.
  - A record of the install's own has a tick. Unticked, its line is commented out (`installs.set_records_use`, kept
    in the ledger's `manualOff` and `linesOff`); ticked again, it is as the install had it. A record whose map a
    build replaces says by which project and stays off while it does. Records the install itself comments out are
    listed greyed and never changed. **Switch off the shown** and **Switch on the shown** act on every record the
    filter shows.
  - **Group by** lists the records by map, or by mission: each kind of mission with the maps the game can play it
    on, and how many of the shown records are in use.
  - The records the editor added sit under their base map (a build's records for campaigns, Play in game's record),
    each with **Undo**: everything of that build out of `DefaultMaps.ini` and the landing zones, and the map it
    replaced live again (`installs.remove_rotation(..., everything=True)`); its files stay.
  - **Undo everything** is `installs.reset` (`POST /play/remove`): records, landing zones, files, the commands file,
    and every record switched off back on. Both INI files end byte for byte as they were.
  - Routes: `GET /gamemaps.json`, `POST /gamemaps/use` (`{"records": [id...], "use": bool}`) and
    `POST /gamemaps/undo` (`{"variants": [name...]}`).

**First run and the game install, in the page** ([`gamesetup.py`](gamesetup.py), [`web/setup.js`](web/setup.js)).

- The server starts on an empty cache (it makes the folder): the map list is then the install's maps, each exported
  the first time it is opened.
- With no game install set and nothing exported, the page opens on **Welcome: choose your game install**:
  - the installs found in Steam's libraries (its registry keys and `libraryfolders.vdf`; the lab copy is listed
    greyed out);
  - a folder typed in, or **Browse…**, a Windows folder dialog on this computer;
  - the doctor's checks.
- **Use this install** saves the **game** setting, the server lists that install's maps with no restart, and the page
  reloads on the map browser.
- **Game install and checks…**, in Settings (the gear), opens the same dialog later.
- Routes: `GET /setup.json` (`?checks=0` leaves the doctor out), `POST /setup/game` `{"folder": ...}`, and
  `POST /setup/browse`. The two POSTs take changes from the viewer itself only.

**Settings and doctor.**

```powershell
python tools/viewer/viewer.py settings                      # show them
python tools/viewer/viewer.py settings --game "<Steam>\steamapps\common"   # --lwr is the same setting's older name
python tools/viewer/viewer.py settings --install ""        # an empty string clears a setting
python tools/viewer/viewer.py doctor --cache "<cache>"
```

- **Settings** live in `Documents\XCOM Map Workshop\settings.json`, beside the projects, where every program sees
  the same file. (Until 8 November 2026 they were in `%APPDATA%`; the Microsoft Store's Python redirects what it
  writes there to a folder of its own, out of sight of PowerShell. A file left there is moved the first time it is
  read.) `XCOM_MAP_WORKSHOP_SETTINGS` names another file. No tool in this repository hard-codes a folder of one
  computer: they all take these settings, or arguments. The settings:
  - **projects** and **output** (builds): in a release, default `projects` and `builds` in the editor's own folder
    (beside `tools` and `python`; `default_folders`), where an upgrade keeps them; under `Documents\XCOM Map
    Workshop` instead when run from the repository, when the editor's folder can't be written (installed for all
    users) and, for each of the two, while that Documents folder holds anything (an earlier release's work);
  - **cache**: exported maps (decoded game data, so never in a repository), default `Documents\XCOM Map Workshop\cache`;
  - **game**: the game install, read only: XCOM: Enemy Within with Long War Rebalance, or plain Enemy Within (a best
    guess, not checked against one). It was called **lwr** until 8 November 2026; a file with `lwr` is read the same.
    The setting is either the game folder itself (an install anywhere) or a folder that holds game folders, such as
    Steam's `steamapps\common`. In a folder, the game folder without the lab marker is the install, so the setting
    follows `switch_install`, which swaps the lab copy and LWR between `XCom-Enemy-Unknown` and their parked names. A
    lab copy is never taken for it. What is Long War's (`DefaultLZMutator.ini`, `DefaultMiniMods.ini`, LWR's
    streamed patches) is used where the install has it;
  - **install**: optional, the game folder Play in game installs into and starts; unset, the game install itself;
  - **udk**: optional, UDK 2011-09 with the XComGame stubs. Only a patch needs it, and no edit the editor builds has
    one;
  - **lab**: optional, our own lab's working folder (logs, fixtures, snapshots, compiled helpers). Only the lab tools
    (`tools/lab`, `tools/bake`, `tools/patch`, `tools/re`) use it, never the editor.
- **Doctor** reports each prerequisite as OK, missing, wrong or a warning, with what to do:
  - the folders are writable, and the install and lab settings, when set, are a game folder and a folder;
  - Python 3.10 or later is installed; PowerShell 7, when present, is version 7 (optional, like UDK);
  - the game install is set, is not the lab copy (a Long War other than LWR is a warning), and with `--cache` its maps
    match the exported ones by SHA-256;
  - UDK, when set, has `UDK.com`, the XComGame stubs and a compiled `XComMapEd` (a warning if not).

  It exits 1 while something is missing. Building (E4) will refuse to start until it passes.

A moved or added piece is only drawn: its collision, cover, floor membership and the map's baked tile data do not
follow it. Nothing is built into the game yet (E3 and E4).
- A copy joins the cutaway of the building floor it stands in, as the Build lists it (from export 15; see Floor
  tiles), but Interior never filters it out as backdrop.
- Copying a lamp copies its mesh, not its light; deleting one leaves its light on.

## Lighting

Export version 9 records every placed light in game units: URB_Bar has its dominant directional light (the moon:
dim blue, brightness 1.1, shadow-casting), one sky light, 54 point lights, 63 spot lights and 137 spot lights that
Lightmass generated from emissive surfaces (`GeneratedMeshAreaLight`). Values a light leaves unset take the UDK
engine's class defaults (radius 1024, falloff exponent 2, spot cones 0°/44°, brightness 1, white; spot and
directional lights point down). The viewer renders them all dynamically:

- The first directional light is the shadow-mapped sun; others light without shadows. Sky lights become a
  hemisphere light (upper and lower colour and brightness).
- Point and spot lights use UE3's falloff, `(1 - (d/R)²)^FalloffExponent`, and its squared cone blend. A 128-unit grid
  over the map lists the lights that reach each cell, and the material shader evaluates only those. Each cell stores
  an offset/count into a compact index texture, without a per-cell light cap. URB_Bar's busiest cell has 102 lights;
  TempleShip's has 269, all retained. GPU texture-capacity limits produce an explicit error rather than dropping lights.
- Colours use UE3's 2.2 power. Brightness matches UE3's units, with no 1/π.
- Patch previews follow the scripts. A hider with `bHideLights=True` switches off lights whose location is in its
  box or whose name is in `alsoHide` (including the map's sun and sky light). A `sun` or `photo` object adds
  XComMapEdSun's directional and sky light, which no hider takes.

In the game, static lights reach static geometry through baked lightmaps, with their shadows and Lightmass bounce
light. The viewer draws them as direct dynamic light with no shadows. Light can pass through walls into the next room,
and there is no bounce light, so interiors and shaded areas look darker than in the game; the **Light** slider
compensates. Area lights reach only dynamic objects in the game (static surfaces get their light from the bake), so
they can be switched off. The map's height fog, post-process colouring and Lightmass environment colour are not
applied yet.

## Current limits

Edits are drawn and saved as projects; there are no build or deploy controls yet, so nothing reaches the game. The patch resolver is experimental:
it has not been verified against a fresh game run. Inherited patches are composed from their saved scene state;
scripted changes made by those patches at runtime are not evaluated.
Unsupported operations/properties and missing sources are reported. Seeding, navigation, interactions, destruction
and native runtime tile rebuilding are not simulated. Spawn snapping at rounding boundaries still needs runtime parity checks.
Only the selected UPK's local references are resolved. External package references are reported; there is no
cross-package/class-default registry yet. Mission streams, game scripts, initial runtime state and Kismet do not run.

Animation-clip playback, door interaction states, ragdoll simulation and saved runtime bone poses are not implemented.
The rigs and reference poses are preserved for later work. Fogged-civilian procedural materials use a source-derived
constant-colour approximation. Alien surface glow uses the packed texture's green channel and source emissive colour
and intensity; its stripped cooked graph is approximated. Energy doors show a stationary tinted pattern. Layered
vertex painting, packed normal/specular maps, animated emissive effects, reflections and specialised shaders still need work.
Opaque materials with no colour texture to read draw a colour by kind or neutral grey (export 14; before it, a
diagnostic pink). Burning trees show their unburnt texture. Decals, particles, sky shaders,
instancing and LOD switching are not implemented. No claim of gameplay or performance parity is made.

All decoded game assets, scene manifests and screenshots belong in the external cache, never this repository.
The importer does not modify game packages or configuration. Re-export after changing source data or importer logic;
existing generations are retained. The cache is disposable; future editable projects will live separately.
The tile grid shows original saved surface data, not live movement range or a guarantee of reachability. Door states,
mission gates and runtime rebuilds are not evaluated. Patch previews deliberately lay it flat instead.

## Checks

Synthetic tests need no game files:

```powershell
python -m unittest discover -s tools/viewer/tests -p 'test_*.py' -v
```

`test_projects.py` covers project storage (revisions, conflicts, the previous revision, recovery, refused schema
versions and paths, file names from project names, renames, clashes, copies, the earlier folder layout moved), the HTTP routes (refusing other origins, hosts and non-JSON bodies), and the settings and doctor.

Marked editor shots for an in-game check (Playwright and Edge, like the smoke tests): a project open in the
editor, numbered circles on the pieces to look at and a legend saying what each should do, from the cameras a shots
file chooses (an overview and close-ups; the file's format is in the script's docstring). Point it at a test server
serving the project's projects folder:

```powershell
python tools/viewer/mark_shots.py "<experiment folder>\EXP-nn-shots.json" --server http://127.0.0.1:8790/
```

Optional development-only browser smoke test (requires Playwright's Python package and installed Microsoft Edge):

```powershell
python tools/viewer/tests/browser_smoke.py --screenshot "<a checks folder>\viewer.png"
```

`--projects` adds the projects check. It saves projects, so run it only against a test server started with
`serve --projects <scratch folder>`, never the main one, and give each run an empty folder (its saves would find the
last run's projects). It covers:

- saving with Ctrl+S and reopening identically;
- recovery after a lost tab;
- a stale save refused, then overwritten;
- a project of the untouched map;
- edits this export lacks kept unchanged;
- a missing project;
- each project saved as one file named after it, renamed with it.

`--play` adds Play in game and Game maps' Undo everything: the open map played unedited, then removed, and with
`--play-project <id>` that project's build installed and played (its build must be of its saved revision, so nothing
builds: Build's panel is answered with its default there, Play last build), then removed. It changes the server's
install and would start the game, so it refuses any server not started with `serve --install <scratch game folder>
--dry-play`. The scratch folder needs `DefaultMaps.ini` and `DefaultLZMutator.ini` in `XEW\XComGame\Config` (copies
of an LWR install's), the open map's package in `XEW\XComGame\CookedPCConsole` and an `XEW\Binaries` folder.
`test_play.py` covers the same on temporary installs, with a start that records its command: a map played with
nothing installed, a project's record added and taken out byte for byte, plain Enemy Within, the game's config kept
aside and put back when the game closes, an earlier version's intro install put back, a separate copy, lines and
files changed since, XCOM running, the routes, the squad's text and Steam's command.

It checks rendering, resource errors, the search list (hidden until there is text), the piece panel, typed
position/yaw with undo, copy and paste through the placing preview (Esc cancels, a click places; a linked car on Bar;
a whole-tile, quarter-turned paste), the milestone marks, delete and Reset all with undo, groups (locking two pieces,
selecting and moving them as one, the gold marks, unlocking, break together, pasting a group, ungrouping, each with
undo; with projects, a group saved and reopened), align (low edges on X and Z, then the first one picked as the
target, then a locked group lining up as one, each with undo), the piece
list (distinct entries, drawn thumbnails, kind filter, size sort, name filter, click and Shift+click placing with
undo), the menus, camera controls and grid, and saves a screenshot for visual review. Binary regression tests cover truncation, bad indices, winding, basis/component composition, compressed bulk
data and a known BC1 texture. A successful render is not a gameplay test.
Skeletal tests cover the EW vertex-stride/packing-hint discrepancy, influence validation, inverse-bind matrices and
skin attributes. Composition tests cover hidden content, identity collisions and copy/hide rules across levels.
The browser script runs on both checked maps; URB_Bar-specific roof, skeletal and EXP-07/08 assertions remain enabled
for that map. V10 checks include exact packed-light membership, a synthetic 300-light overlap, source grid dimensions,
and projecting every corner of the scene bounds inside the viewport. An isolated GPU test lights a surface using
only the 300th overlapping light. V11 also checks the default interior view, source transform preservation, clipping
and reversible scenery filtering. Each browser run saves a JSON report next to its screenshots.

With the cache library serving both checked maps, the separate map-switch check covers the map browser (sections,
a map under each mission type, search, the type chips, Prepared only), layout resets, independent assets,
URLs/history, a map that isn't listed and the compact header. `--prepare <map>` also opens a map not exported yet and
waits for its export on first open: point that at a test server on a scratch cache root (one linking the exported
maps' folders, say), since the export lands in the cache the server serves. It needs Playwright
(`pip install playwright`; it drives the installed Edge):

```powershell
python tools/viewer/tests/browser_maps_smoke.py --url http://127.0.0.1:8768/ --screenshot "<a checks folder>\base-maps.png"
python tools/viewer/tests/browser_maps_smoke.py --url http://127.0.0.1:8790/ --screenshot "<a scratch folder>\maps.png" --prepare URB_SmallCemetery
```

## Additional-map check: Temple Ship

The final mission's original `TempleShip.upk` was exported and browser-checked on 5 November 2026 with exporter v11:

```powershell
python tools/viewer/viewer.py export "<LWR install>\XEW\XComGame\CookedPCConsole\TempleShip.upk" --scope map
python tools/viewer/viewer.py serve "<cache>\TempleShip\029bedcaea20c9a8-v11-map" --port 8790
```

The export has 1,678 mesh components (1,667 visible in full scenery), 162 mesh variants, 52 materials, 143 PNG textures, 11 building groups
and 1,333 placed lights. All exported components loaded in headless Edge with no console errors or failed requests;
search, selection, framing, floor cutaway, wireframe and lighting switches were exercised. The companion
`TempleShip_Stream.upk` contains no mesh actors; the arrival cinematic and mission scripts were not run or composed.

Temple Ship defaults to **Playable interior**, showing 1,296 pieces and cutting away the outer shell and authored
hallway roofs. Its 5,902 saved floor records span Z -384 to 573; common platform heights are -192, 0 and 192.
The tile grid follows those surfaces and ramps around the selected piece. It leaves out cells whose floor actors are
hidden in the chosen view. **Full scenery** restores the large outer structure for inspection.

All 1,327 enabled local lights, including 1,190 generated area lights, are retained. The source tile volume is
45 x 203 x 15, at (-2111.6001, -9407.6973, -384), with 96 x 96 x 64 cells. Three textureless constant materials no longer use a diagnostic
colour; the remaining unsupported diffuse bindings belong to the suppressed sky/ocean shaders. Three energy-door
notes identify their stationary approximation. Texture counts include original packed maps and derived linear masks,
whose provenance is retained. The V10 check measured about 10 ms median headless Edge frame intervals at 1600 x 1000;
this is not a general performance guarantee. Reports and screenshots are in the cache's
`checks\TempleShip` folder. Fresh in-game visual comparison, cinematic state and gameplay parity
remain unchecked.

## Prefab builder

Open **Add → Prefabs → New**, a row's **Edit**, or the map browser's **Prefabs** group. The builder uses the main
editor window in place of a map. Its ground grows with the contents while snapping stays fixed. All maps supplies
pieces. Its Lights and Invisible categories offer point/spot lights and cover/floor recipes. Buildings, box selection,
nested groups, copy/paste and undo work as in a map.

The Prefab menu saves the complete document, including hidden lights/boxes and preserved unreadable pieces.
Save as may explicitly replace a different prefab; the original stays unchanged. Opening another document asks
Save/Discard/Cancel. Saved prefabs have complete recovery snapshots. Supported contents fit 256 by 256 tiles (the
largest map the editor makes) and heights −192 to 2,112: the tile grid 0 to 1,920 (30 levels; height 0 is the drawn
grid) and 192 units sticking out under or over it, including geometry and floor boxes. A selection is saved with its map's grid
bottom at 0. Old larger files open for repair. A warning over the size names the pieces that keep the pose rule and
stand off their grid; **Show** selects them and **Align to grid** moves the whole prefab the least that puts them
all on it (one undo step; refused while unreadable pieces are kept, as they would not move).

When you open or place a prefab with unreadable sources, the editor looks up their saved recipe keys in the
current **All maps** catalogue and warns about pieces it still can't load. In the builder, matches preserve
poses, groups and assembly links and can be undone in one step. Save to keep the new references. Unresolved
records stay in the prefab. After rescanning **All maps**, use **Prefab → Find missing pieces** to try again.

**Prefab → Test in game** builds a private snapshot of the current workspace on CB2_MP_Blank, grown to 18
levels (0 to 1,152), its ground hidden (still stood on) inside a noon sky above and below, and launches that
build with no aliens. A neutral fill light illuminates the stage with or without baking. Lighting is baked by
default. Unnamed and unsaved work can test. Missing content, off-grid poses
and a footprint that leaves insufficient squad room are refused with details. After a reload you can follow the
test and explicitly launch a ready result. The game watch takes out the test installation when XCOM closes.

Glowing props carry their source map's matched generated area lights into the prefab preview and every build.
Quick builds carry the live lights. Baking also updates the light that reaches nearby static surfaces.

A prefab holds **effects and ambient sounds** too (prefab schema 3): select them with the pieces (the Normal
button's Effects and sounds switch, or the Effects view) and save. Each is kept as a copy of its original with the
values set on it and its place in the prefab's groups; a sound's reach is no part of the footprint. An effect its
piece carries is not listed: the piece's copy brings it. Placing the prefab places them as the Add panel places an
effect of another map (read from their home map, built by the same path), with the effect's likeness under the
cursor, with their values. The builder shows
them (its Effects view, Shift+X, and the likeness), and Test in game plays them. A **lens flare** is held the same
way where the flare family builds (stage FX6b; prefab schema 3 still): a piece of `kind: flare`, a copy of its
original with no values, counted as a lens flare in the prefab's line; where the family doesn't build it can't be
selected, so it isn't saved, and a prefab that holds one places it only where the family builds.

Acceptance uses scratch stores on a test port; stop the server afterwards:

```powershell
python tools/viewer/viewer.py serve --port 8791 --no-open --projects "<scratch>/projects" --builds "<scratch>/builds"
python tools/viewer/tests/browser_builder.py --url http://127.0.0.1:8791/ --screenshot "<scratch>/builder.png" --large
python -m unittest discover -s tools/viewer/tests -p "test_prefab*.py"
node tools/viewer/tests/prefab_document_test.mjs
```

`browser_smoke.py --only builder` includes the builder check. The dedicated check's `--large` also times Bar's
whole building. The real-source check needs Bar and Police Station prepared and the All maps library scanned.
It writes a turned-placement project beside its screenshot for compiler readback. `--only prefab-test` checks the
Test in game dialog, snapshot submission, cancellation, retry and reconnect with a stubbed build and launch.
`--dry-play --install <scratch game>` can exercise the real build and installer without starting XCOM.

## Format provenance

Our readers build on this repository's package/property/LZO research. Pinned Uncooker serialization declarations
were consulted as format documentation; its implementation has not been vendored or used as a runtime dependency.
The [format note](../../research/native/viewer-formats.md) records the fields and the important winding correction.
