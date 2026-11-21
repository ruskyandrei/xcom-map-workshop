# How the code is shaped

This is for anyone who changes the editor's code, person or agent. The [README](README.md) says what the editor does
and how the repository is laid out. This document says how the parts fit (section 1), where new code goes (section 2)
and the rules that keep the shape (section 3). A test holds what a test can hold (section 4); the rest needs
judgement, and is written here once. Section 5 says how to change the structure without changing what the code does,
and section 6 is a checklist for a change.

It describes the code as it is. A change that sets a new pattern (a new kind of module, a new home for some state)
writes the pattern here in the same commit: its section, and its row in section 2.

## 1. How the parts fit

A map goes through the editor in this order: the install's map is exported (the scene), the page edits it into a
project, the compiler turns the project into an edit, the Build makes that edit in a copy of the map and relights it,
and the packaged map is installed in the game.

**The map's export (the scene).** [`tools/viewer/export.py`](tools/viewer/export.py) (`Exporter`, run by
`viewer.py export`, and by [`exports.py`](tools/viewer/exports.py) the first time a map is opened) reads one of the
install's maps. It uses the package readers in [`tools/viewer/package.py`](tools/viewer/package.py) and
[`tools/upk`](tools/upk). It writes a generation folder in the cache (`<cache>/<Map>/<generation>/`). That folder holds
`scene.json`, with the pieces, lights, effects, sounds, spawn points, buildings, missions and the tile grid, and the
meshes, materials and textures the page draws. [`scene_metadata.py`](tools/viewer/scene_metadata.py) works out the
records that need more than reading, such as what an effect is carried by or who uses a spawn point. The contract is
`EXPORT_VERSION` in `export.py`, raised for every change of what an export holds, each raise listed beside it. An
export older than the editor's version is made again. The server picks its exports when it starts.

**The page.** [`tools/viewer/web`](tools/viewer/web): `index.html` loads [`app.js`](tools/viewer/web/app.js), the entry
module. three.js comes from `vendor/` through the import map (fetched by `setup_vendor.py`, not tracked). The page
draws the scene, edits it and keeps the project document. Each area of the page (a view, a panel, a tool, a dialog)
is a module of its own, listed in section 2. An area is mostly two modules: a pure one of its rules, records and words,
with a node test (`floors.js`, `walls.js`, `light_rules.js`), and a wiring one, made by a factory `create<Area>`, that
draws, fills its panel and changes the scene (`buildings_wiring.js`, `made_handles.js`, `lights_wiring.js`). What the
areas share has a few homes:
- [`editor_state.js`](tools/viewer/web/editor_state.js) owns the state several areas use, each value with its setter
  (section 3, "The page");
- [`edit_hub.js`](tools/viewer/web/edit_hub.js) keeps every area's panels up after an edit, an undo or a selection:
  each area registers its refresh in a named run, and whoever starts the run calls the hub;
- [`document_session.js`](tools/viewer/web/document_session.js) owns the open document's life: a project opened,
  saved and left, its unsaved state kept on the server as a draft against a lost tab and offered back, whether it has
  changes not saved (`dirty`, `saveState`, `unsavedDocument`), the banner under the header, and whether projects can
  be had on the scene open (`projectsAvailable`: not in the prefab builder, not on a patch preview);
- [`document_state.js`](tools/viewer/web/document_state.js) turns the scene into a document's state and back:
  `editStateNow` reads the edits on screen as a project records them (`editState` keeps its answer for one edit
  event), and `applyState` puts such a state back on the map, after taking the scene back to the map as exported
  (`clearEdits`) and noting what it could not put back (`projectNote`); `changes` counts what has changed. A project's
  file, its drafts and the prefab builder's document all go through these two;
- [`piece_records.js`](tools/viewer/web/piece_records.js) writes and reads an added thing's record (a copy of a piece,
  a made piece, a cover block, a light, an effect, a sound or a lens flare) for every writer and reader, and says what
  a piece as the page holds it stands for (`isStream`, `fromOf`, `sourceKey`);
- [`project.js`](tools/viewer/web/project.js) holds the project document's shape on the page;
- [`api.js`](tools/viewer/web/api.js) asks the server, and [`storage.js`](tools/viewer/web/storage.js) keeps what a
  browser remembers.

app.js holds only what joins the modules:
- the imports; the renderer, the camera and its controls, the world's layers and the gizmo;
- each area's factory made, in the order section 3 gives, handed the others' functions; the dialogs made with their
  elements (the first run's setup, the file dialog, the project manager, Game maps, Cache everything), the build
  queue's controller with its calls to the server (`queueCall`), and the Add panel's browsers (This map, All maps,
  Prefabs, the look picker);
- `open`, which starts the page (the map list read, the first run's install asked for, the map browser made, the map
  the address asks for opened, or the browser shown on it to prepare it) and calls `startScene`, which starts each
  area's part of the scene in its order (section 3);
- the event wiring: the panels' field handlers, the pointer handlers and the draw loop, each calling what the
  factories return;
- a few helpers that join the page's own objects to the modules: `$`, the sun's shadows asked for again
  (`touchShadows`), the edit event's memo around the hub's edit run (`editChanged`, the gizmo's `onEdit`), the hub's
  `scene` run with the state a scene change sets (`sceneChanged`), the view taken without the editor's helpers for the
  Map picture (`grabView`), the made pieces' looks read as the page loads (`readLooks`) and a toggle button's handler
  (`toggleButton`);
- and only the state its own wiring reads (section 3, "The page").

`window.viewer`, the hooks the browser checks drive, is made by [`test_api.js`](tools/viewer/web/test_api.js)
(`createTestApi`) and set by `startScene` once the scene has opened.

**The server.** `viewer.py serve` ([`tools/viewer/viewer.py`](tools/viewer/viewer.py)) serves the cache's exports, the
page and the editor's JSON routes. Its handler's `handle_<area>` methods hand each route to its area's module:
[`projects.py`](tools/viewer/projects.py), [`play.py`](tools/viewer/play.py), [`manager.py`](tools/viewer/manager.py),
[`buildqueue.py`](tools/viewer/buildqueue.py), [`library.py`](tools/viewer/library.py),
[`prefabs.py`](tools/viewer/prefabs.py) and the others. Every folder comes from
[`settings.py`](tools/viewer/settings.py) (`Documents\XCOM Map Workshop\settings.json`) or an argument.

**A project.** [`tools/viewer/projects.py`](tools/viewer/projects.py) keeps one JSON document per project in the
projects folder. It is saved atomically with the revision it was based on, so a save from an older revision is refused
as a conflict. The document says `schema: xcom-map-workshop/project` and its `schemaVersion` (`SCHEMA_VERSION`, with
the versions still read in `READ_VERSIONS`). Its `source` names the map and the SHA-256 of the map's package, by
which the Build finds the export and checks the install's map. It holds the edits: the map's pieces changed or
deleted (`overrides`), added pieces, groups, buildings, lights, effects, sounds, spawn points, landing zones, missions
and the map picture. [`research/editor-contracts.md`](research/editor-contracts.md) is the contract. The page
writes the document; the compiler reads it.

**The compiler.** [`tools/editor/compiler.py`](tools/editor/compiler.py): `compile_project(doc, scene, ...)` gives
`(spec, report)`. The spec is the edit, the same bytes for the same project and export. The report gives the errors
(which stop a Build), warnings, notes and the records left out. Each edit family is a class in a module of its own,
which the `Compiler` makes for itself and holds as an attribute named as its module (`self.spawn_edits`):
- [`spawn_edits.py`](tools/editor/spawn_edits.py) (`SpawnEdits`): the base map's spawn points;
- [`effect_edits.py`](tools/editor/effect_edits.py) (`EffectEdits`): the map's effects, ambient sounds and lens flares;
- [`light_edits.py`](tools/editor/light_edits.py) (`LightEdits`): the map's placed lights, and the area lights its
  glowing pieces take along;
- [`flag_edits.py`](tools/editor/flag_edits.py) (`FlagEdits`): pieces' flags (walking, cover, sight, floor, mouse);
- [`made_edits.py`](tools/editor/made_edits.py) (`MadeEdits`): walls, floors, roofs and ground shapes made from
  numbers, cut into pieces where they are too large, and the blasts that break a fracturing piece;
- [`building_edits.py`](tools/editor/building_edits.py) (`BuildingEdits`): buildings made from nothing, and the map's
  own buildings changed or deleted;
- [`mission_edits.py`](tools/editor/mission_edits.py) (`MissionEdits`): the map's grid made larger or smaller, the
  clear, the drop-in rule, landing zones, missions and the places units are dropped at;
- [`group_edits.py`](tools/editor/group_edits.py) (`GroupEdits`): the user's groups that break together, and what
  of each group breaks with it;
- [`floor_edits.py`](tools/editor/floor_edits.py) (`FloorEdits`): the floor a project leaves and the floors its
  pieces are checked against: the cursor's floors, the floor flat pieces give, ladders' climbs, the building floor a
  copy stands in, and the map's floor tiles still there.

The `Compiler` class holds only what joins them: the document's and the export's checks; `run`, which calls the
passes in their order; the family gates (`FAMILIES` says which families build for every project); the map's own
pieces moved, deleted and copied and the pieces of other maps (`overrides` and `added`, with the assemblies and the
grid rule); cover blocks (`cover_add`); `spec`, which puts the families' lanes together; the diagnostics (`error`,
`warn`, `note`, `leave_out`) through which the families report; and one-line forwarders to a family's method that a
test or a tool calls on the compiler by name (`stage`, `cursor_storeys`). The helpers its passes share (the grid
rule's poses, the assemblies, a cover block's shape) are functions of the module beside it, and `find_export` and
`main` run it from the command line.

The tables and helpers that the compiler and its families share (`FAMILIES`, `short`, `tidy` and the others its
`__all__` names) are in [`compiler_tables.py`](tools/editor/compiler_tables.py). The compiler takes them all with
`from compiler_tables import *`, so `compiler.FAMILIES` is that module's object. A piece of another map comes from the
library of other maps' pieces as [`piece_lookup.py`](tools/editor/piece_lookup.py) (`Library`) asks it, and
`native_split(spec)` in [`native_edit.py`](tools/editor/native_edit.py) splits the spec into what a patch would do
(nothing, for every project the compiler accepts today) and the native edit. The compiler names both again
(`compiler.Library`, `compiler.native_split`), and what uses them uses them there.

**The native edit.** It is the dict `native_split` ([`native_edit.py`](tools/editor/native_edit.py)) returns, the
contract between the compiler and the Build. It is a set of lanes: `copies`, `breakOriginals`, `hides`, `assemblies`,
`covers`, `buildings`, `buildingEdits`, `lights`, `effects`, `sounds`, `flares`, `spawns` and the others
`native_split`'s docstring lists. The Build writes it as `native-edit.json` in its work folder and hands it to the copy
tool.

**The Build.** [`tools/editor/build.py`](tools/editor/build.py) (`Build.run`) takes a saved project to a finished
package and never touches a game install: the install is only read. Its stages, in order:
- snapshot: the saved project, and the map's export and the pristine base map from the install, both found by the
  map's SHA-256;
- compile, and a preflight that every name the build writes is free for this project;
- patch, only when the native edit leaves a patch something to do;
- shell, which equips the game's blank map with what a battle needs;
- pieces of other maps, staged in a copy of the base map;
- light: the copy tool, then the seeds, the map picture and the lightmaps put inside the map;
- package.

A Build is given what it builds as one record, `BuildInputs`: the project, its folders, the options a command line
gives and the stand-ins a test gives for its tools. `main` makes it from the command line, which is how the server's
builds start it (as a process). `Build.__init__` reads the record once, and names the state each stage fills, with
the stage. The install's files (its maps under `XEW/XComGame/CookedPCConsole`, its config under `XEW/XComGame/Config`)
are found by `lwr_file` in [`game_files.py`](tools/editor/game_files.py), which the prefab test's stage
([`prefab_stage.py`](tools/editor/prefab_stage.py)) uses too, so that it need not load the Build.

A quick build makes the same edit without the relight. It hands on the package folder
`<output>/<Variant>/`: `CookedPCConsole/<Variant>.upk` (with the intro and stream copies its records need),
`README.txt`, and `manifest.json`. The manifest holds the project's revision, the source map's hash, each file with
its hash, the config lines, each stage's result, and whether the build was quick. Its `tools` names the code that
made it, each file with its hash: build.py and the modules of `tools/editor` it imports (`editor_modules`), and the
modules of `tools/bake` and `tools/upk` that the tools it runs and build.py itself import (`tool_modules`), both found
from their imports.

**The copy tool.** [`tools/bake/native_copy.py`](tools/bake/native_copy.py) (`build`) makes the native edit in a copy
of the pristine base map, with the growing writer ([`tools/upk/package_grow.py`](tools/upk/package_grow.py)). Each copy
is a new actor with a fresh name and net indices. Its tiles are seeded under a rebuild volume. The hidden pieces are
taken out. Each other lane has a maker module that `build` calls: [`native_lights.py`](tools/bake/native_lights.py),
[`native_effects.py`](tools/bake/native_effects.py), [`native_sounds.py`](tools/bake/native_sounds.py),
[`native_flares.py`](tools/bake/native_flares.py), [`native_spawns.py`](tools/bake/native_spawns.py),
[`cover_blocks.py`](tools/bake/cover_blocks.py), [`buildings.py`](tools/bake/buildings.py) and the made pieces'
modules. With `--bake`, the copies get lighting of their own and the relight runs. It writes the variant map and a
fixture manifest.

A Build of the copy tool is one record, `BuildState`. Its first fields are the inputs: the map, the output folder,
the variant, the copies, the native edit's other lanes and the options. The caller makes it: `main` through
`edit_state`, from the native edit the Build writes (`native-edit.json`) and the command line, each copy through
`copy_record`, so no field of a copy is lost on the way; a test makes its own. `build(st)` holds only what joins the
steps: it opens the map's reader and the growing writer, runs the steps in their order, with the few lanes' makers
called between them, and writes the record; its docstring lists its inputs. Each step is a function of the state that
reads its fields and writes its results to fields `BuildState` names with the step that fills them:
- the light edits (`native_lights`);
- `clone_copies`: the copies, an assembly's together, with their tiles, flags and blasts;
- the cover blocks, then `fracturing_copies`: the fracturing copies' columns, and the pieces made from numbers;
- the break groups, the hides and the effects' lanes, then `wall_columns`: the walls' columns after them;
- `edit_buildings`: the building floors, and the buildings made and edited;
- `edits_in_place`: the map's own pieces edited where they stand (lights registered, the clear, landings, flags,
  blasts);
- `floors_and_cursors`: the floors' effect lists and the made slabs' cursor floors;
- `write_and_verify`: the write, and what was written read back.

Then the record: the manifest (`manifest_parts`) and, with `--bake`, the relight (`relight_command`). The growing
writer's order is the map's, so the steps keep theirs. `st.gone()` is the one answer to what the edit has taken out
so far.

**The relight.** [`tools/bake/relight.py`](tools/bake/relight.py) relights each component an edit reaches as a change
on the original bake: the map's own lights through EW's lightmap codec
([`lightmap_encode.py`](tools/bake/lightmap_encode.py)), with shadows ([`shadows.py`](tools/bake/shadows.py), Embree),
the emissive surfaces' area lights and one bounce. It writes the variant's texture cache, `<Variant>_Lighting.tfc`.
The Build then puts those lightmaps inside the map ([`inline_lighting.py`](tools/bake/inline_lighting.py)).
`PieceCache` keeps a project's last baked pieces for its next build, under a key of everything their images depend on.

**The packaged map and the install.** [`tools/viewer/installs.py`](tools/viewer/installs.py) puts a package into a
game install, LWR or plain Enemy Within, and takes it back out:
- it copies the package's files into `CookedPCConsole`, each checked against the manifest first;
- it adds the variant's `DefaultMaps.ini` records ([`mapsini.py`](tools/viewer/mapsini.py) reads and writes the
  lines) and its landing zones;
- it never changes a line the install had, except when the project manager puts a variant in the base map's place.

Play in game ([`play.py`](tools/viewer/play.py), [`gamelaunch.py`](tools/viewer/gamelaunch.py)) installs one build
with a record no campaign draws and starts a battle on it. The project manager ([`manager.py`](tools/viewer/manager.py))
puts builds into the campaigns' rotation, beside the base map or in its place, and zips them into map packs
([`packs.py`](tools/viewer/packs.py)).

## 2. Where new code goes

On the page, the first module named in a row is the area's wiring, with its factory; the rest are the pure modules
its rules, records and words go in, with their node tests in `tools/viewer/tests`.

| Kind of work | Where it goes |
| --- | --- |
| A new area of the page (a panel, a view, a tool) | A module of its own in `tools/viewer/web`, and a row here. Its rules, records and words go in a pure module with a node test; what draws and wires its panel goes in a factory that takes what it needs of other areas as one argument object (`createProjectDialog` in [`project_files.js`](tools/viewer/web/project_files.js) and `createQueueController` in [`build_queue.js`](tools/viewer/web/build_queue.js) are the model; section 3, "The page"). |
| Opening, saving or leaving a document, its drafts kept for recovery, whether it has changes not saved, whether projects can be had on the scene open, the banner under the header | [`document_session.js`](tools/viewer/web/document_session.js) (`createDocumentSession`; `projectsAvailable` a plain export). The prefab builder's own saving and opening are in [`builder_session.js`](tools/viewer/web/builder_session.js), and share its drafts' state in [`editor_state.js`](tools/viewer/web/editor_state.js). |
| A new part of what a project keeps of the scene (saved, and put back when it opens) | [`document_state.js`](tools/viewer/web/document_state.js): `editStateNow` writes it into the state, `applyState` puts it back on the map. [`document_session.js`](tools/viewer/web/document_session.js) carries it between the file and those two (`openProject`, `offerProjectDraft`, `saveProject`). Then as for a field of the project document. |
| The prefab builder: the prefab's document as the scene holds it, opened, kept and saved; its size line and the ground under it, Align to grid, missing pieces looked for by recipe, the Problems check | [`builder_session.js`](tools/viewer/web/builder_session.js) (`createBuilderSession`). A prefab document's rules (its size and limits, its records normalized onto its own grid) go in [`prefab_document.js`](tools/viewer/web/prefab_document.js), and the server's side in [`prefabs.py`](tools/viewer/prefabs.py). |
| A prefab saved or placed: the selection as a prefab's records, the Save as prefab dialog, the save, the prefab's picture, a prefab of the Prefabs tab read and placed | [`prefab_place.js`](tools/viewer/web/prefab_place.js) (`createPrefabPlace`). The Add panel's Prefabs tab is [`prefabs.js`](tools/viewer/web/prefabs.js)'s browser; each piece's record is [`piece_records.js`](tools/viewer/web/piece_records.js)'s. |
| Build and Play in game: Build's panel and its window, Play's dialog, the Game menu's Installs, the header's Build and Play buttons, the test squad's line, the prefab builder's Test in game, the build queue's chip | [`build_play.js`](tools/viewer/web/build_play.js) (`createBuildPlay`). What a build status or a play's answer says, in words, goes in [`build_window.js`](tools/viewer/web/build_window.js) or [`play.js`](tools/viewer/web/play.js); Build's panel itself is [`build_options.js`](tools/viewer/web/build_options.js), the test squad's dialog [`squad.js`](tools/viewer/web/squad.js), the prefab test's window [`prefab_test.js`](tools/viewer/web/prefab_test.js) and the queue's controller [`build_queue.js`](tools/viewer/web/build_queue.js). |
| The Lights view: a light's root, its panel section, Solo, its reach, its drag handles (and the picked effect's or sound's), the area lights following their pieces, a light added from the Add panel or a recipe, the project's light records, the Map lighting mode's buttons | [`lights_wiring.js`](tools/viewer/web/lights_wiring.js) (`createLightsWiring`). What it draws (a marker, an emission shape, a handle, Solo's lights) goes in [`lights_view.js`](tools/viewer/web/lights_view.js) (three.js, nothing of the page), and a light value's rule in [`light_rules.js`](tools/viewer/web/light_rules.js), with its node and Python tests (`shared_cases_test.mjs`, `twin_constants_test.mjs`, `test_lights.py`). The Map lighting mode's drawing of the map's own lights is [`lighting.js`](tools/viewer/web/lighting.js) (`createMapLighting`, made by `startScene`), with its light grid in [`light_grid.js`](tools/viewer/web/light_grid.js). |
| The Effects view: an effect's, sound's or lens flare's root and where it stands, the view's kinds, its panel, the Wave preview, its values' controls, the likeness, a copy added, the project's records of effects and sounds | [`effects_wiring.js`](tools/viewer/web/effects_wiring.js) (`createEffectsWiring`). What it draws goes in [`effects_view.js`](tools/viewer/web/effects_view.js) (a marker, a box, a sound's spheres) or [`effects_preview.js`](tools/viewer/web/effects_preview.js) (the likeness), three.js and nothing of the page; what a record says and what of it can change in [`effects_rules.js`](tools/viewer/web/effects_rules.js), and a particle system's stepping in [`effects_sim.js`](tools/viewer/web/effects_sim.js). |
| The Spawns view and the mission objects' moves: a spawn point's or mission object's marker, the view's families, its panel and controls, a move, turn, value, copy or delete of one, its gizmo, a spawn point added from the Add panel, the project's spawn rule | [`spawns_wiring.js`](tools/viewer/web/spawns_wiring.js) (`createSpawnsWiring`). What a marker is, draws and says goes in [`spawns_view.js`](tools/viewer/web/spawns_view.js) (its shapes take three.js as an argument) and what the game does with a spawn point in [`spawn_rules.js`](tools/viewer/web/spawn_rules.js) (`spawns_view_test.mjs`, `spawn_rules_test.mjs`, `project_spawns_test.mjs`). |
| The Landing zones view: a zone drawn, picked, moved and turned with its gizmo, its panel and controls, a zone changed, copied, deleted or added, what follows the cleared mark | [`zones_wiring.js`](tools/viewer/web/zones_wiring.js) (`createZonesWiring`). A zone's rules go in [`spawns.js`](tools/viewer/web/spawns.js) (`clear_map_test.mjs`, `twin_constants_test.mjs`). |
| The Buildings view and box select: the buildings' records (every building the floors code reads, `allBuildings`; the map's own changed or deleted, `mapEdits`; what the project saves of them, `savedBuildings`), a floor box made, stretched, moved, copied or deleted, a building's name, kind and floors, the map's own buildings edited or read, the face handles and their drags, the cursor's floors round a box, the view's panel, the Normal button's Floor boxes, box select | [`buildings_wiring.js`](tools/viewer/web/buildings_wiring.js) (`createBuildingsWiring`). A building's or a floor's rule (the floors around pieces, the cursor's floors, a building's problems, the pieces a box lists) goes in [`floors.js`](tools/viewer/web/floors.js) (`floor_rules_test.mjs`, `map_buildings_test.mjs`, `source_floor_match_test.mjs`); a building's record in [`project.js`](tools/viewer/web/project.js) (`validBuilding`, `tidyBuilding`). |
| Switching the views: the normal view, what follows a view or a Normal button's switch changing (whether lights are drawn, what stays selected), the views' buttons | [`views.js`](tools/viewer/web/views.js) (`createViews`). A view's own switch (`setLightsShown`, `setVolumesShown`, ...) is its module's. |
| What every area's drag handles share: the pick distance, a game point as a view point, screen positions of view points, a drag along a line | [`handles.js`](tools/viewer/web/handles.js) (`createHandles`; `HANDLE_PICK` and `gameToView` plain exports). An area's own handles (their meshes, stems and drags) are its module's. |
| A made piece (a wall, floor, roof or ground shape made from numbers): whether a piece is one, its look's donor as a template, its state and changes (each one undo step), its mesh drawn anew, where made walls meet, the picked piece's handles and their drags, a rock's corners | [`made_handles.js`](tools/viewer/web/made_handles.js) (`createMadeHandles`). What is pure about a made piece's numbers and their changes (`resizedWall`, `movedOpening`, `raisedWall`, `resizedSlab`, `movedHole`, `resizedGround`, `movedPoint`, `wallJoins`, the mesh's numbers) goes in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js) (`walls_test.mjs`, `ground_test.mjs`, `made_shapes_test.mjs`); its request and a plain piece's look (`madeRequest`, `isPlain`, `plainLook`) in [`made_requests.js`](tools/viewer/web/made_requests.js) (`made_requests_test.mjs`). |
| The made pieces' looks: the look a tool draws in, the look picker's samples and what choosing a look does, the eyedropper, a made piece's look changed (with the pieces the change takes), its Look row | [`made_looks_wiring.js`](tools/viewer/web/made_looks_wiring.js) (`createMadeLooksWiring`). A look's catalogue and entries go in [`looks.js`](tools/viewer/web/looks.js), the picker's panel in [`look_picker.js`](tools/viewer/web/look_picker.js) (`looks_test.mjs`, `look_picker_test.mjs`). |
| Drawing a made piece: the Build menu's tools, a wall, room (with its roof and building), floor, roof or ground shape dragged out with its ghost and made | [`made_drawing.js`](tools/viewer/web/made_drawing.js) (`createMadeDrawing`). Where a drawn piece stands and what its numbers are (`drawnWall`, `drawnRoom`, `drawnSlab`, `roomRoof`, `drawnGround`) go in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js). |
| The piece panel's sections of a made piece: the Wall section and its openings, the Floor section and its holes, the Ground section, the Room section of a drawn room, an opening taken out by Delete | [`made_panel.js`](tools/viewer/web/made_panel.js) (`createMadePanel`). What an opening, a hole or a room's storeys are and say (`openingPlay`, `playWords`, `withOpening`, `withHole`, `steppedStoreys`, `slopeWords`) goes in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js). |
| Break and Repair: a blast set off on a made piece or on one of the map's fracturing pieces, the Break rows and tool, a broken piece drawn without its knocked-out fragments | [`made_breaking.js`](tools/viewer/web/made_breaking.js) (`createMadeBreaking`). A blast's record goes in [`piece_records.js`](tools/viewer/web/piece_records.js) (`cloneBlasts`), a made piece's blasts in its mesh's request in [`walls.js`](tools/viewer/web/walls.js) (`blastQuery`), and the Build's side in [`made_blasts.py`](tools/bake/made_blasts.py). |
| A cover block or invisible floor: its recipe, mesh and template, the Add panel's Invisible kind, the ground under a floor (the map's collision, Fit to ground), the piece panel's cover section, a new record put on a piece, its handles and their drags | [`cover_wiring.js`](tools/viewer/web/cover_wiring.js) (`createCoverWiring`). What is pure about a cover piece (its box and mesh, the tiles it covers and what the game makes of them, a size changed by a handle, its words) goes in [`cover.js`](tools/viewer/web/cover.js) (`cover_test.mjs`, `cover_tiles_test.mjs`), and the Build's side in [`cover_blocks.py`](tools/bake/cover_blocks.py). |
| The piece panel's Flags group and its chip: a piece's five flags as the project has them, a row changed (one undo step), the question about a prop's pathing gate, Reset | [`flags_panel.js`](tools/viewer/web/flags_panel.js) (`createFlagsPanel`). A flag's rule (a piece's roles and their limits, what a request does, its normalized form) goes in [`piece_flags.js`](tools/viewer/web/piece_flags.js) (`piece_flags_test.mjs`, `project_flags_test.mjs`), and the compiler's side in [`flag_edits.py`](tools/editor/flag_edits.py). |
| Select all of a kind: what counts as a piece's or an effect's kind, the pieces and effects that match (inside box select's box), the button | [`select_kind.js`](tools/viewer/web/select_kind.js) (`createSelectKind`). |
| The user's groups: a group's chain, its pieces, a piece's member key, the groups cloned, a group's pieces on the map now, what the selection is to the groups, the group section and chip, a group made, added to or ended (one undo step) | [`groups.js`](tools/viewer/web/groups.js): the basics as plain exports, the rest in `createGroups`. A group's record (`groupKey`, `pruneGroups`) goes in [`project.js`](tools/viewer/web/project.js), and the compiler's side in [`group_edits.py`](tools/editor/group_edits.py). |
| Align: the others of the selection lined up with a target, the Align section and its white box | [`align.js`](tools/viewer/web/align.js) (`createAlign`). |
| The play area, the map's size as the project sets it, the rail's Map grid (its handles, drags and panel, a new size as one undo step), the grid's origin and tile corner | [`map_grid.js`](tools/viewer/web/map_grid.js) (`createMapGrid`; `gridOrigin` and `tileCorner` plain exports). A stage's record (its shape and limits) goes in [`project.js`](tools/viewer/web/project.js) (`validStage`, `tidyStage`, `stageMax`), the cursor's floors in [`floors.js`](tools/viewer/web/floors.js) (`cursorStoreys`), and the compiler's side in [`mission_edits.py`](tools/editor/mission_edits.py). |
| Clear map and the landings: the landing zones as the project has them, the landing zone's pieces, the ground's height, what a clear takes and keeps, the Clear map window and the clear; the Missions panel, which game is set, the header's Mission picker; the Map picture dialog; the ground grid | [`clear_map.js`](tools/viewer/web/clear_map.js) (`createClearMap`). A zone's rules go in [`spawns.js`](tools/viewer/web/spawns.js) (`startingZones`, `ownLandings`, `groundOf`), a mission kind's in [`missions.js`](tools/viewer/web/missions.js), what an effect does in a clear in [`effects_rules.js`](tools/viewer/web/effects_rules.js) (`survivesClear`), the dialogs in [`missions_panel.js`](tools/viewer/web/missions_panel.js) and [`map_picture.js`](tools/viewer/web/map_picture.js), and the compiler's side in [`mission_edits.py`](tools/editor/mission_edits.py). |
| The scene's pieces: picking, a texture or material made, the loads of meshes and materials (each once, shared), a piece's root built, added or taken away, its unedited matrix, an original's parts and boxes, a piece's box, an added piece made from its template, a record's template, an original's pose rule under tile snap, an actor's pose at a render matrix | [`scene_pieces.js`](tools/viewer/web/scene_pieces.js) (`createScenePieces`; the pose's helpers `actorPose` and `movedMatrix` plain exports). The meshes loaded are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`geometryCache`); what a material record says is the export's ([`export.py`](tools/viewer/export.py)). |
| The map's families and assemblies: the families set as they arrive, an original's assembly and its link tag, a piece's assembly (its own map's or another's) | [`map_families.js`](tools/viewer/web/map_families.js) (`createMapFamilies`). The families' rules are the server's ([`families.py`](tools/viewer/families.py)); the Add panel's use of them [`pieces.js`](tools/viewer/web/pieces.js)'s (`useFamilies`). |
| The cutaway (which pieces are drawn and how each is cut: the Floor picker, Interior, the streams shown, the clear), the tile grid round the selection, the Floor tiles overlay, the Floor picker's buttons | [`cutaway.js`](tools/viewer/web/cutaway.js) (`createCutaway`). What is pure about them (the visible bounds, a footprint, the tiles around it, Interior's planes, the overlay's tiles) goes in [`view_layout.js`](tools/viewer/web/view_layout.js), and a piece's listings in [`floor_listings.js`](tools/viewer/web/floor_listings.js). |
| The building floors a piece is listed on (the project's buildings', the map's own), the key of the pieces' edits that the cutaway, the ground grid and Level snap follow | [`floor_listings.js`](tools/viewer/web/floor_listings.js) (`createFloorListings`). The rules (`touchedFloors`, `ruleListing`, `copyFloors`, `floorAt`, `carriedListing`, `sourceFloorMatch`) go in [`floors.js`](tools/viewer/web/floors.js), and the Build's side in [`buildings.py`](tools/bake/buildings.py). |
| Floor pieces, Level snap and its button, the Floor picker's floor under a point | [`level_snap.js`](tools/viewer/web/level_snap.js) (`createLevelSnap`). The floor rules (`ownedFloors`, `classifyFloors`, `floorStamps`, `buildingWithFloor`, `storeyHeight`) go in [`floors.js`](tools/viewer/web/floors.js). |
| The selection: what is picked (a piece, light, building's box or effect, or nothing), the views stepping aside for it, the piece panel filled for it (a cover block's or invisible floor's too), the selected piece's highlight, a ladder's ends and its chip, the grid chip of a piece the recipe snap holds, what some roots are in words and a selected root's name in a list, the pieces an actor name stands for, the selection's sets (what can be copied or deleted, what Align lines up, the floor boxes selected with pieces, what a group can hold) | [`selection.js`](tools/viewer/web/selection.js) (`createSelection`, which gives back `copyable`, `copyablePieces`, `selectedBoxes` and `groupables`; `selectionWords` and `rootName` plain exports); a ladder's climb ends in [`ladders.js`](tools/viewer/web/ladders.js). An area's own part of the piece panel (its section shown or hidden for what is picked, its panel, a chip) is the area's module's, registered with one of the edit hub's select runs, never called by name from `select`. |
| The piece panel's pose fields and the edit status (what has changed and whether it is saved, Undo, Redo, Reset, Reset all) after an edit | [`piece_status.js`](tools/viewer/web/piece_status.js) (`createPieceStatus`), the edit hub's `piece-status` refresh. The count of changes is [`document_state.js`](tools/viewer/web/document_state.js)'s (`changes`). |
| The camera (framing, the keys that move and turn it, the look-drag, the wheel, the speeds), the gizmo's mode buttons, the pivot and snap, a key of the editor | [`navigation.js`](tools/viewer/web/navigation.js) (`createNavigation`). A key calls the function of the area that owns what it does, given to the factory; the help panel in `index.html` lists the keys for users. |
| Delete, Reset piece, Reset all (each one undo step), a large step under the busy mark | [`delete_reset.js`](tools/viewer/web/delete_reset.js) (`createDeleteReset`). |
| Copy, paste and placing: a clip of the selection, a paste, the preview that follows the cursor and where a click places it (with the snaps, Level snap and the recipe snap), the Add panel shown and its tab, an entry of it chosen and placed, a copy dragged off with Shift, a drawn-only copy of pieces (the preview, the Add panel's thumbnails, the look picker's samples, `previewGroup`) | [`clipboard.js`](tools/viewer/web/clipboard.js) (`createClipboard`). A copied thing's record goes in [`piece_records.js`](tools/viewer/web/piece_records.js) (`optionsOf`, `stateOfRoot`), a group's in [`project.js`](tools/viewer/web/project.js), the pose rule's snap in [`gizmo.js`](tools/viewer/web/gizmo.js) (`recipeMove`), and a floor's height under a point in [`floors.js`](tools/viewer/web/floors.js) (`levelHeight`, `floorUnder`). |
| A piece, effect, sound or lens flare of another map read as a template: its record read, its template made, the templates a project's records name, what such a piece costs and says | [`library_templates.js`](tools/viewer/web/library_templates.js) (`createLibraryTemplates`). The records read and the templates made are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`libraryRecords`, `effectTemplates`, `foreignEffects`, `foreignTemplates`, `donorHashes`); the Add panel's All maps is [`library.js`](tools/viewer/web/library.js), and the server's side [`library.py`](tools/viewer/library.py). |
| Prepare: the dialog that exports the map again (when it opens, before a build or a play, from a build that failed for want of it), Later's banner, a build or a play waiting for it | [`prepare.js`](tools/viewer/web/prepare.js) (`createPrepare`), and the server's side in [`exports.py`](tools/viewer/exports.py). |
| A header menu (a button with `data-pop` and its menu) | `index.html`; [`popups.js`](tools/viewer/web/popups.js) (`createPopups`) opens and closes it, one at a time, and draws a menu afresh as it opens where the menu needs it. |
| A dialog's keyboard (Tab going round its controls, its own Tab order, the focus given back), whether a dialog or the look picker is open | [`modal.js`](tools/viewer/web/modal.js): every `.modal` of `index.html` gets it once (`holdModals`); a dialog's own order is `tabOrder`; the editor's keys and windows ask `modalOpen` before they act. A dialog's own keys (Escape, its shortcuts) are its module's. |
| The Project menu drawn as it opens, the recent projects, a window its items open (the file dialog, the project manager, Game maps, Cache everything) | [`project_menu.js`](tools/viewer/web/project_menu.js) (`createProjectMenu`). A window's own dialog is its module's ([`project_files.js`](tools/viewer/web/project_files.js), [`manager.js`](tools/viewer/web/manager.js), [`gamemaps.js`](tools/viewer/web/gamemaps.js), [`precache.js`](tools/viewer/web/precache.js)), made by app.js with its elements; the first run's install dialog is [`setup.js`](tools/viewer/web/setup.js). |
| The map list, the map browser's making and what choosing a map does, the Map menu's button and Change map | [`map_menu.js`](tools/viewer/web/map_menu.js) (`createMapMenu`). The browser's dialog is [`map_browser.js`](tools/viewer/web/map_browser.js); the list and the browser are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`mapCatalogue`, `mapBrowser`). |
| The loading overlay's words and bar, an opening document's steps on it, a JSON file read with its progress | [`loading.js`](tools/viewer/web/loading.js) (`createLoading`). |
| The hint line under the view: a held gizmo handle's line, a short notice, the resting hint | [`hints.js`](tools/viewer/web/hints.js) (`createHints`). |
| A slow step under the busy mark (put up after a third of a second, or at once with the view's clicks and keys held), a long loop giving way, many pieces built a few at a time | [`busy.js`](tools/viewer/web/busy.js) (`createBusy`). |
| An element of text, a term and its value in a list, a count with its noun, a name's last part, a copy to the clipboard told on its button, a row of buttons used like a select, a sentence's capital | [`dom_words.js`](tools/viewer/web/dom_words.js), pure (it imports nothing), with its node test (`dom_words_test.mjs`). An area's own words go in its own pure module. |
| What the page does for an area as a map or a prefab opens (its part of the scene made, its panel or menu set for the scene) | A function of the area's module, returned by its factory and called from app.js's `startScene` at its place in the order (section 3, "The page"), given what `startScene` has worked out so far as its parameters (the streamed objects, the families' answer). What is no one area's (the page's title, View options' Full or Interior and the Map menu's items, the import notes, the gizmo's Linked button) goes in [`scene_start.js`](tools/viewer/web/scene_start.js), plain exports given what they need. |
| What an area keeps up after an edit, an undo or a selection (its panel or section, a button's state, a mark in the view) | Its area's module, which registers the refresh with the edit hub, [`edit_hub.js`](tools/viewer/web/edit_hub.js), as its factory is made (`onHub(run, name, refresh)`), under a name put in the hub's `RUNS` at the place in the run where it must be called (section 3, "The page"). |
| State of the page (a module-level `let` or a collection) | The module of the one area that uses it. State several areas use: [`editor_state.js`](tools/viewer/web/editor_state.js), exported with its setter, in the group of the area that owns it. Never app.js. |
| A rule, a record or a sentence of the page | A pure module (no three.js, no document), with a node test in `tools/viewer/tests/<module>_test.mjs`. Examples: [`piece_records.js`](tools/viewer/web/piece_records.js), [`light_rules.js`](tools/viewer/web/light_rules.js), [`spawn_rules.js`](tools/viewer/web/spawn_rules.js), [`poserule.js`](tools/viewer/web/poserule.js). |
| The game's grid numbers on the page, and the name a map's own actors begin with | [`constants.js`](tools/viewer/web/constants.js) (`TILE`, `LEVEL`, `QUARTER`; `PL`). |
| A call to the server, from the page | [`api.js`](tools/viewer/web/api.js). |
| Something a browser remembers | [`storage.js`](tools/viewer/web/storage.js). |
| A field of an added thing's record (a copy of a piece, a cover block, a light, an effect, a sound, a lens flare) | [`piece_records.js`](tools/viewer/web/piece_records.js): `recordOf` writes it (for every writer: a project, a prefab, the builder's document), `optionsOf` reads it (a project opened, a prefab placed, a paste), and `PIECE_FIELDS` names it; a case in [`piece_record_cases.json`](tools/viewer/tests/piece_record_cases.json) or [`piece_records_test.mjs`](tools/viewer/tests/piece_records_test.mjs). Then as for a field of the project document, and the prefab's check of a piece in [`prefabs.py`](tools/viewer/prefabs.py). |
| What a piece as the page holds it stands for: whether it is a streamed piece, the original it is or was copied from, a map's own piece's key in a project | [`piece_records.js`](tools/viewer/web/piece_records.js) (`isStream`, `fromOf`, `sourceKey`: plain exports). A target's key itself is [`project.js`](tools/viewer/web/project.js)'s (`targetKey`). |
| A test hook (a name on `window.viewer` that a browser check, the guide's pictures or a script reads or calls) | [`test_api.js`](tools/viewer/web/test_api.js) (`createTestApi`): the shared state and a pure module's export imported there, what a factory returns given by `startScene` in its argument object. The name goes into [`viewer_api_names.json`](tools/viewer/tests/viewer_api_names.json) in the same change (`browser_smoke.py --url <test server> --write-api-names`), which the `api-names` check holds. |
| A browser check | The table of checks (`CHECKS`) in [`browser_smoke.py`](tools/viewer/tests/browser_smoke.py). |
| A route of the server | A `handle_<area>` method of `viewer.py`'s handler that hands the request to its area's module (`handle_play` and [`play.py`](tools/viewer/play.py) are the model). |
| A setting (a folder, an install) | [`settings.py`](tools/viewer/settings.py). |
| A record of the map's export | [`export.py`](tools/viewer/export.py) or [`scene_metadata.py`](tools/viewer/scene_metadata.py), with `EXPORT_VERSION` raised. |
| A field of the project document | [`projects.py`](tools/viewer/projects.py) and [`project.js`](tools/viewer/web/project.js), with the compiler's reading of it, and the contract in [`research/editor-contracts.md`](research/editor-contracts.md). |
| An edit family of the compiler | A class in a module of its own in `tools/editor`, made with the `Compiler` it works for (`self.c`), with its own tables and state. It takes what it shares with the compiler from [`compiler_tables.py`](tools/editor/compiler_tables.py), never imports the compiler, and reports through the compiler's `error`, `warn` and `note`. The compiler imports it at the top and names again the tables of it that others read through the compiler. The compiler holds it as an attribute named as its module (`self.effect_edits`), and reads the family's state through it (`self.effect_edits.ops`): the state has one home. A method of the family stays on the compiler only as a one-line forwarder, and only when a test or a tool calls it there by name (`Compiler.stage`). [`spawn_edits.py`](tools/editor/spawn_edits.py) is the model; section 1 lists the others, and the family is listed under `compiler families` in `structure.json` (section 4). |
| A table or helper of the compiler that a family reads too | [`compiler_tables.py`](tools/editor/compiler_tables.py), named in its `__all__`. One only the compiler reads stays in `compiler.py`; one only a family reads goes in the family's module (the `SPAWN_*` tables in `spawn_edits.py`, the effects' in `effect_edits.py`, the `LIGHT_*` tables and `light_rule` in `light_edits.py`). |
| A lane of the native edit | One change across the compiler's spec, `native_split` in [`native_edit.py`](tools/editor/native_edit.py), the copy tool and the Build. In the copy tool ([`native_copy.py`](tools/bake/native_copy.py)): a maker module in `tools/bake` (as [`native_effects.py`](tools/bake/native_effects.py)); the lane's field on `BuildState` and its reading in `edit_state` (with its line in `CommandLine.LANES` of [`test_native_copy.py`](tools/bake/tests/test_native_copy.py)); and a step, a function taking the `BuildState` that reads its fields and writes its results to fields the class names, called from `build` in the place the map's writes need. One of the inputs of `build_outputs.py` (section 5) holds the lane: its `record` fails on a lane none holds. |
| A piece lookup (what the compiler asks of the library of other maps' pieces) | [`piece_lookup.py`](tools/editor/piece_lookup.py) (`Library`), raising `LibraryError` (in [`compiler_tables.py`](tools/editor/compiler_tables.py)) with its code for what can't be had. The library's scan and its records are the viewer's [`library.py`](tools/viewer/library.py). |
| A reader of package bytes | [`tools/upk`](tools/upk): tagged properties through [`props.tags`](tools/upk/props.py), compressed chunks through [`decomp.read_chunk`](tools/upk/decomp.py), a map's objects through the viewer's [`Package`](tools/viewer/package.py), a mesh component's LOD records and a bulk record through [`native_fields`](tools/upk/native_fields.py)' `mesh_lods` and `bulk_record` (each value with its place in the package; [`lighting_records`](tools/upk/lighting_records.py) and [`lightmap_fields`](tools/bake/lightmap_fields.py) give their values and places in the forms their readers take). |
| A writer of package bytes | [`package_edit.write_edited`](tools/upk/package_edit.py) for edits in place, [`package_grow.py`](tools/upk/package_grow.py) for new exports. |
| A line of the game's config, and a field of a `DefaultMaps.ini` record | [`mapsini.py`](tools/viewer/mapsini.py): a record's fields and streams read and written by `field`, `unquoted`, `set_field`, `slot_streams` and `add_stream`, on a line of bytes (the install) or of text (the Build, the map list, the export), blanks around `=` read as the game reads them (KB-11); a record's mission by [`maplist.record_kind`](tools/viewer/maplist.py). No other module writes a pattern for a record's field. |
| A file replaced whole: a project, a record, a picture, an index | [`atomic_files.py`](tools/viewer/atomic_files.py): `write_bytes` or `write_text` (a temporary file beside it, then a replace tried again while another program holds the file a moment), or `replace` for a temporary file the writer filled itself or a file it moves aside. The writer keeps its own lock, flush (`sync`), read-back and error words. No other module of `tools/viewer` calls `os.replace` (`test_atomic_files.py` scans for it; KB-10). |
| A tool folder on the import path | [`paths.use()`](tools/paths.py), at the top of the module. |
| A test's shared records and helpers | Its suite's fixtures module: [`viewer_fixtures.py`](tools/viewer/tests/viewer_fixtures.py), [`tools/bake/tests/fixtures.py`](tools/bake/tests/fixtures.py), [`editor_fixtures.py`](tools/editor/tests/editor_fixtures.py), [`upk_fixtures.py`](tools/upk/tests/upk_fixtures.py) (a suite without one makes one, named for the suite). One more than one suite needs: [`tools/tests/shared_fixtures.py`](tools/tests/shared_fixtures.py) (the DefaultMaps records, a made-up mesh), which each suite's fixtures module imports it from. |
| An environment variable a test or a tool reads | `ENVIRONMENT` in [`run_tests.py`](tools/run_tests.py), with what it does and what happens without it (`run_tests.py --help` prints it), in the commit that reads it. |
| A rule both the page and Python need | A JSON file both read, or a case file both sides' tests read ([`shared_cases_test.mjs`](tools/viewer/tests/shared_cases_test.mjs) lists them). |

Three places take no new code, only what joins the modules: [`app.js`](tools/viewer/web/app.js), the compiler's
`Compiler` class, and the copy tool's `native_copy.build`. A new area gets a new module and a row here.

## 3. The rules

Each rule is here because breaking it cost something. The reason is given with it, and the editor review's finding
where there is one.

### Shape

- A module is named for the one thing it does: an area of the page, an edit family, a file format. What the release
  ships is never in a module named as an audit, a fixture, an experiment or a test of the code: the config lines once
  lived in the lab's `deploy_fixture.py`, so the release shipped it (finding 53).
- New code goes into the module that owns its area. A new area gets a new module. app.js, the `Compiler` and
  `native_copy.build` take only what joins the modules: they grew past every size when everything was added to them
  (app.js to 12,792 lines, `native_copy.build` to 544), and had to be taken apart.
- Keep files to about 1,500 lines and functions to about 150: past that, code gets hard to read whole. These are
  guidance, not limits (section 4). When a change makes a file or function grow well past them, see first whether
  the new code is a module or a function of its own.
- A function with more than about eight parameters takes a record instead. `Build.__init__` took 22 and
  `native_copy.build` 30, and every caller had to name them all (findings 23 and 51).
- An object's state is made where the object is made, with a comment saying which step fills it. It is never made by
  first use through `getattr` with a default: such state is invisible until it breaks (finding 23).

### One home

- A rule, a constant or a reader of a format is written once. Before writing a reader, a walker or a writer, look for
  the one there is: `props.tags`, `decomp.read_chunk`, `package_edit.write_edited`, `mapsini`, `atomic_files`; on the
  page `api.js`, `storage.js`, `constants.js`, `dom_words.js` and `piece_records.js`. Copies drift apart and each fails
  differently (findings 52, 55 and 56; of the writers of whole files only the install's ledger and config writers
  tried a refused replace again, KB-10).
- A rule both the page and Python need lives in a JSON file both read, or has a case file both sides' tests read. It
  is never copied by hand with no test (finding 55).
- Code never decides by the words of a message. An error that code reads carries a code: words get rewritten
  (finding 55).

### The page

**State.** Each piece of the page's state (a module-level `let`, or a collection changed in place) has one owner
module, which declares and exports it. An imported name is a live binding that cannot be assigned to, and a copy of a
value goes stale, so:
- other modules read it through the import, a live binding that sees each new value;
- they give it a new value only through the owner's setter, `set<Name>` (`setSelected`, `setProject`, `setGroups`).
  Where the area that owns a value has a `set<Name>` of its own that also draws, the owner's plain setter is
  `set<Name>Value` (`setStageValue`, beside map_grid.js's `setStage`). A counter taken one step at a time has a
  `next<Name>()` beside its setter (`nextCopySerial()`, `nextChooseToken()`);
- a collection (a `Map`, an array) is changed in place through the import as it is.

What one area alone uses lives in that area's module, inside its factory (the document session's `navigating`); a
module made after it that reads it is given a getter the factory returns (the Spawns view's `spawnLayerReady`), never
a copy of the value. What several areas use lives in [`editor_state.js`](tools/viewer/web/editor_state.js), grouped by
the area that owns it, each group's comment saying who reads or sets it: the scene and its roots, the selection, the
project open and what it keeps (groups, buildings, the map's size, the clear and its landing zones, missions, picture,
spawn rules), the document session's state and drafts, Play in game's, the prefab builder's document, the edit hub's
memo of one edit event, the clipboard and the Add panel's lists, other maps' pieces as read, which view is on, and the
state of each view or tool that the keys, the pointer handlers, the draw loop and the test hooks read or set. New
shared state goes into its area's group there.

A write turned into a setter's call keeps its moment: a value taken from the browser's storage as the page loads is
given by the setter's call where the value was declared (`setAreaShown(recall(AREA_SHOWN) === '1')`); a setter whose
write sits inside an expression gives back what it set (`setWavePlayer`: `player = setWavePlayer({ ... })`); a
logical assignment is the same test with the setter's call (`lineCollision ?? setLineCollision(new Map())` sets it
only when it is null).

app.js declares only the state its own wiring reads: the sun's shadows' timer, the draw loop's clocks, the press the
pointer handlers share (`pointerStart`) and the Map lighting mode's `applyLighting`, which `startScene` sets. New
state never goes there. An assignment to an imported name throws only when its line runs, and no browser check runs
every line: `web_names` (section 5) finds one, and a change that moves state searches for writes to the moved names
left behind.

**Factories.** A module that needs functions of other areas is made by a factory, `create<Area>`, that takes them as
one argument object and destructures it, so the code in it calls them by their own names. It returns the functions
other areas call, and app.js destructures them under the same names, so their callers read as they would anywhere.
app.js makes each factory after the functions and objects it is given:
- A function made further down in app.js (a `const`, or one a factory made later returns) is given as a function that
  calls it, since it is not made yet: `select: (id, add, keep) => select(id, add, keep)`. So is a function app.js keeps
  in a `let` (`applyLighting`). A value that is not a function (a constant such as `SESSION`, or one a factory
  returns, such as box select's `PICK_SLACK`) cannot be called through: the factory that needs it is made after it.
- Two factories that call each other (the prefab builder's session, whose save opens the Save as prefab dialog, and
  prefabs saved and placed, whose Save saves the builder) are made one after the other, the first given the second's
  functions as functions that call them.
- What a factory sets up as the page loads (a handler set, a listener added, a dialog or a layer made) runs when it is
  made, so its place in app.js is the order in which the page sets things up. Listeners on one target are called in
  the order they were added, and three.js breaks ties in its drawing order by the order materials and objects were
  made. A change that moves a factory checks that no code between its old and its new place sets a handler on, or
  listens to, the same targets, and that what it makes earlier or later draws as before.
- A factory that sets nothing up as the page loads (it declares functions, and at most makes plain values: a table, a
  vector) can go anywhere, so it is made where the fewest functions must be called through: the scene's pieces before
  the gizmo, the first code given their functions; the selection after the Buildings view, the last factory whose
  functions it calls; the views' switching after the selection; Delete and Reset after Break and Repair.
- A factory whose listeners' order with others' matters is made where those listeners belong: navigation.js, whose
  camera keys and editor keys listen on the document and the canvas, is made last, after every factory whose functions
  the keys call.
- An object that areas made at different places share (the landing zones' layer, the floor-box outline of a clip, the
  group chip) is made in app.js before the first of them and given to each.
- An area of several modules is made in its code's order: the made pieces' base, `made_handles.js`, then their looks,
  drawing, panel sections and Break, each given the functions of those made before it directly and those of the ones
  made after it as functions that call them.
- app.js's comment above each factory says what the area is and why it is made where it is.

The order app.js makes them in:
1. the scene's pieces, the gizmo, the map's families, the loading overlay;
2. the Flags group (after the group chip it is given), the hints and the busy mark, other maps' templates, Level snap,
   the groups, Align;
3. the handles, the header's menus (before the first area given `showPop`), the Lights view, Prepare;
4. the document state, the document session, the piece status, the prefab builder's session, prefabs saved and
   placed, the map menu, Build and Play;
5. the dialogs (the first run's setup, the file dialog, the build queue's controller, the project manager, Game maps,
   Cache everything), then the Project menu, which is given them;
6. the floor listings, the Map grid (after its pointer listeners, which take the press first), Clear map;
7. the Spawns, Effects, Landing zones and Buildings views, the selection, the views' switching, Select all of a kind;
8. the cover blocks, the clipboard, the made pieces (base, looks, drawing, panel, Break), Delete and Reset, the
   cutaway;
9. `open` and `startScene`; then the event wiring, the Add panel's browsers, navigation and the draw loop.

**Opening a scene.** As a map or a prefab opens, app.js's `startScene` calls each area's part of the scene in a fixed
order, and does little else: the page's title and the Map lighting mode made, the Map menu's items, the landing lines
read (Clear map's `readLandingLines`), the play area drawn, the lighting mode's buttons (`lightingModes`), the mission
asked for chosen, the scene's pieces built (`buildPieces`), the map's families used, the buildings set, the lights and
effects made (`buildLights`, `buildEffects`), the lights' button, the header's Mission picker (`startMissionPicker`),
View options' patch helpers (`sceneViewOptions`), the pieces placed, the Floor picker and the camera framed, the view
lit (`applyMapLighting`), the ground grid, landing zones and spawn markers drawn and the spawn rules read, the import
notes and the gizmo's Linked button, the installs asked for, the map's export checked (`prepareOpened`), and the
prefab builder's page dressed (`builderPage`) or the project asked for opened. Then it makes the test hooks and calls
the hub's `checkHub`. A part keeps its place in that order, and is given what `startScene` worked out before it (the
streamed objects, the families' answer, the server's map list) as its parameters.

**The edit hub.** A panel registers its refresh with the edit hub ([`edit_hub.js`](tools/viewer/web/edit_hub.js)); it
is not called by name from another area. After an edit, an undo or a selection, the hub's `edit` run calls each area's
refresh (its panel or section, a button's state, a mark in the view) in the order `RUNS` lists them, whatever order
the modules are made in. So an area's module can be made anywhere, and a new refresh is a name put in `RUNS` where it
must be called and one `onHub(run, name, refresh)` in its module's factory.
- A refresh that returns `STOP` ends its run, and those after it wait for the next (the selection, which runs the hub
  itself; a building's box that cannot be turned; the cutaway's select).
- A refresh that needs what another worked out in the same run is one refresh with it (piece_status.js's
  `piece-status`: the pose fields and the edit status share the pose and the count of changes).
- Where another area's refresh must be called in the middle of one, it is a run of its own that the one runs: `drag`
  (the lights following a gizmo handle held, between the pose fields and the end of the edit's run), and the select
  runs, which `select` runs at each place it fills the piece panel for what is picked, given what it has there (the
  root picked, its source, the chips' row): `select-sections`, `select-none`, `select-light`, `select-cover`,
  `select-piece` and `select-chips`.
- Where an area's change must keep other areas up, it runs a run of its own rather than calling them by name: `scene`
  (app.js's `sceneChanged`: the cutaway, the ground grid, where made walls meet), `landing-zones` (the zones drawn),
  `clear` (a clear done or undone: the lights drawn), `mission` (the header's mission changed: the lights drawn, the
  spawn markers and their gizmo, the cutaway) and `snap` (the snap setting: the selected piece's grid chip). What is
  state (the sun's shadows asked for, the groups' pieces to be worked out again, the Effects view's redraw asked) is set
  directly.
- Every name `RUNS` lists has its refresh registered: `startScene` ends with the hub's `checkHub`, which throws (the
  page says it could not open, and the browser checks see the error) when one has none, and the hub's node test reads
  the page's modules for one `onHub` of each name. A run would pass over a lost registration without a word. The hub
  is a module of its own, not part of editor_state.js, so that its node test can import it.

**Records.** An added thing's record is written only through `piece_records.js`'s `recordOf` and read only through its
`optionsOf`. A writer gathers what it knows of the thing (a unit: its names, source, components, pose, links, state,
recipe, a cover block's, a light's or an effect's own fields) and hands it to `recordOf`, which gives the fields in
the one order every writer writes. The saved files' bytes and a project's saved key (`stateKey`, which compares
records as text) follow that order, so it changes only on purpose. A reader hands the record to `optionsOf` and makes
the root from what it gives. Where the writers differ, the difference is the unit's (a prefab's records have no `id`)
or the path's (`recordOf(unit, 'prefab')` puts a recipe light's values before its pose). The node test's cases
(`piece_record_cases.json`) are the writers' and readers' records on every kind of piece.

**Modules.**
- A module's top level only declares, so the order of imports means nothing; what must run at the start runs from a
  factory or from `startScene`. No module imports app.js: a module that needs app.js's functions takes them as one
  argument object when it is made.
- A rule, a record or a sentence is in a pure module with a node test. The wiring of a panel is beside it and has a
  browser check in the table of checks. A hook a browser check uses is on `window.viewer`: it is made in `test_api.js`
  from the modules' exports (the shared state and the pure modules' functions imported, each a live binding; what
  app.js's factories return given as one argument object), and its name is in the recorded list
  (`viewer_api_names.json`), so that a move that loses a hook fails the `api-names` check.
- The server is asked through `api.js`, the browser's storage through `storage.js`.

### The compiler and the Build

- An edit family is a class in a module of its own, with its tables and its state. It reports through the compiler's
  `error`, `warn` and `note`, so the report stays one report (`spawn_edits.py`). It takes the tables and helpers it
  shares with the compiler from `compiler_tables.py` and never imports the compiler, so a family can be read, tested
  and moved without the rest of the compiler (section 4).
- The native edit is the contract between the compiler and the Build. A new lane is added in one change to the
  compiler's spec, `native_split` (`native_edit.py`), the copy tool and the Build.
- A reader of package bytes checks its bounds and refuses (a `ValueError` saying what it met). It never reads on: a
  damaged or modded package then fails in one place with a reason. A package's summary and tables are read by
  `upkinfo`, which refuses a count, a string or a reference that does not fit; an export's native data is read through
  `Package.native`, which stops at the export's end; a chunk header, a map's or a bulk payload's, by
  `decomp.read_chunk` (KB-9). A writer goes through `write_edited` and reads back what it wrote (finding 52). A
  read-back may take the blocks the file keeps from its source (their packed bytes the source's at the same place)
  from the source's decode and decode only the rest: the growing writer's does (`decomp.decompress_written`,
  follow-up 1.1).
- Tagged properties are walked by `props.tags` (`props.read_tags` for a list) and by nothing else in what ships: a
  walker keeps only what it does with each property (its values, its rules), and a module whose callers catch an
  error of its own turns the walk's `ValueError` into that error (the viewer's `FormatError`, `pack_card`'s
  `CardError`, `typed_props`' `WalkError`). About sixteen walks once read the bytes each its own way, some with no
  bounds checked (finding 52). The research tools that do not ship keep walks of their own. In the same way a mesh
  component's LOD records and a bulk record have one reader, `native_fields`' (`mesh_lods`, `lod_record`,
  `lightmap_record`, `bulk_record`), which gives each value with its place; a module that needs another form of
  them makes it from that reader's record, and keeps any check of its own beside it (`lighting_records.bulk_meta`
  refuses a negative count). Three readers once wrote Enemy Within's licensee branch three ways. Bytes of the map
  being grown are read by it too, their references held to the grower's objects (`frac_walls.lod0` and
  `GrownObjects`, follow-up 3.11).
- Whatever a piece's relit images depend on is in the piece cache's key. A key that misses an input gives a stale
  piece that looks right (finding 42).

### Imports and folders

- A folder goes on the import path through `paths.use()`, which puts it there once, at the top of a module. A shipped
  function never changes `sys.path` itself (section 4). Python file names stay unique across the repository and
  take no standard or installed module's name (`tools/repo/tests/test_names.py`), so which file a name finds never
  depends on the path's order (finding 54).
- What the release ships does not import the lab, the research tools or a test (finding 54).
- A folder comes from the settings, an argument or the repository; never from one computer. Documents and notes write
  placeholders such as `<cache>`, `<LWR install>` or `<lab>`.

### Tests

- What is pure has a unit or node test. What is wired has a browser check. A reader of a format has a test on a
  made-up package that needs no install, besides any check over installed maps.
- A suite's shared records and helpers are in its own fixtures module, and no test file imports another: a test
  that imported another's helpers ran only beside it, and could run its tests twice. Each test file runs alone
  (`python -B -m unittest discover -s tools/<suite>/tests -p <file>`). A helper made of a test class's methods (the
  play tests' game installs, a server with a prefab library) is a mixin there, which a class takes as a base before
  `unittest.TestCase` or method by method; a mixin is no `TestCase`, so no importer runs tests of it.
- What more than one suite's tests need is in [`tools/tests/shared_fixtures.py`](tools/tests/shared_fixtures.py),
  which each suite's fixtures module names. No suite puts another suite's tests folder on the path or reads a file
  from it; a case file that a node test and a Python test both read is the exception ("One home" above).
- A test that cannot run says why it skipped, and a selection that runs nothing fails. A test checks the code of the
  checkout it runs in.
- Every environment variable the tests and the tools read is listed in `run_tests.py`'s `ENVIRONMENT`, with what it
  does and what skips without it, and the README gives the ones for running the tests on another setup.
  `test_run_tests.py` fails on a variable read and not listed. A variable names one thing: a test that needs another
  package of the install names a variable of its own, or takes it from the folder `XCOM_COOKED` names
  (`labpaths.install_map`).
- A refactor is checked by equal outputs (section 5). A change of behaviour is checked by a test that failed before it.
- A bake test class that builds packages shares one build among tests whose edits do not meet
  ([`fixtures.SharedBuild`](tools/bake/tests/fixtures.py): each test reads its own edit's part, inside a sub-test named
  for the edit; an edit that fails to apply fails its own test alone; classes of one module share builds through
  `fixtures.ModuleBuilds`), and keeps one build with one edit for each kind of edit, so a fault that shows only when an
  edit is alone, or only beside others, is still caught.

### Changing things

- Move, then change: never both in one commit.
- What a change leaves unused goes out with it. No parameter, option or branch for a case nobody has.
- Measure before making something faster, and write the numbers in the ledger entry.
- A comment says why, in words that stay true. It names no line number and no private plan.

## 4. Sizes, and the rules a test holds

### Sizes

About 1,500 lines a file and 150 a function are guideline sizes, not limits: no test fails on them, and nothing lists
exceptions. A larger file or function is fine when it has a reason, such as a table, a format read whole, a test file
of many cases, or a run that reads best in one piece. The same goes for app.js's module-level state and top-level
functions: new ones belong in the module that owns their area, but nothing counts them for you.

`python -B tools/repo/tests/test_structure.py --sizes` lists what is over the guideline sizes, largest first, and
app.js's counts of `let` statements and top-level functions; the two numbers are `guideline sizes` in
[`tools/repo/structure.json`](tools/repo/structure.json). It measures:
- Python's functions and methods by their syntax tree, from `def` to their last line, with their nested functions;
- the page's top-level functions by their text;
- a page module made as a factory (`createX`, which declares its functions inside and returns them) by each function
  it declares, since a factory is a module made as a closure;
- functions only in what the release ships (the modules and page files `tools/release/make_release.py` lists), and
  files among every tracked Python file and page module.

What is over them today, and why (app.js: 5 `let` statements, 11 top-level functions):
- `tools/viewer/tests/browser_smoke.py` (5,933 lines): the browser checks' runner, their table and most checks in one
  file; some areas' checks have modules of their own (`browser_walls.py`, `browser_editing.py` and others). The rest
  could follow them, by area; that split waits.
- `tools/bake/native_copy.py` (3,389): the copy tool's walker, clones, tiles and volumes, fracturing columns,
  building floors, flags, blasts and steps, which share the map's reader and the growing writer; its lanes' makers
  are modules already. A split of the columns, the building floors and the flags waits.
- `tools/editor/tests/test_compiler.py` (3,115): a test file of many cases; its classes could follow the families into
  files of their own.
- `tools/bake/relight.py` (2,041): one relight run over the components, with the piece cache; its codec, shadows and
  bounce are modules already.
- `tools/viewer/installs.py` (2,035): a package put into an install and taken out, with the ledger, the checks and the
  config records that change with it; a split waits.
- `tools/editor/compiler.py` (1,969): the `Compiler` and its helpers once the families left. The map's own pieces
  moved and the added pieces (`overrides`, `added`, with the assemblies and the grid rule: about 650 lines) are the
  next family if it grows.
- `tools/editor/tests/test_build.py` (1,933): a test file of many cases.
- `tools/editor/build.py` (1,842): the Build's stages, its config lines and its README (its records written through
  `mapsini.py` since 21 November 2026).
- `tools/bake/wall_measure.py` (1,619): the walls' look measurer, one format read whole: a fracturing mesh's LOD 0
  measured into a look.
- `tools/bake/buildings.py::edit` (210 lines): the map's own buildings edited in place, one pass over a building's
  floor volumes in the map's order; a split waits.
- `tools/bake/shell.py::equip` (191): the blank map equipped with what a battle needs, one run of steps in the map's
  order.
- `tools/viewer/manager.py::_pack` (188): a map pack made, one run over the projects, each staged and checked
  before it joins the pack; a split waits.
- `tools/bake/native_copy.py::main` (170): the copy tool's command line, and a summary printed from the manifest that
  could be a function of its own.
- `tools/bake/native_copy.py::build` (169): 81 of its lines are the docstring listing its inputs, which could move
  onto `BuildState`'s fields; the body is the steps in order.
- `tools/viewer/effects_metadata.py::describe` (169): a package's effects, sounds and flares described, one pass over
  their many fields.
- `tools/editor/group_edits.py::GroupEdits.groups` (166): the groups' pass, with a docstring of its contract; a split
  waits.
- `tools/bake/transplant.py::stage_edit` (154): the pieces of other maps staged in a copy of the map, one run.
- `tools/bake/frac_walls.py::add_walls` (153): the made walls added to the map being grown, one run over the copies.

### What the structure test holds

[`tools/repo/tests/test_structure.py`](tools/repo/tests/test_structure.py) (the repo suite) holds the rules below,
with its lists in `structure.json`. Each failure names its rule and this section. The files are the ones Git has or
would add, so a new file counts before it is committed. `python -B tools/repo/tests/test_structure.py --root <folder>`
checks another checkout, such as a scratch copy, and prints its problems by rule.

### The page's imports

No page module imports `app.js`: a module that needs app.js's functions takes them as one argument object when it is
made. No import cycle among the page's modules beyond those listed under `page cycles` (each listed as its modules'
sorted names). There are none today.

### What ships imports

No module the release ships imports a module of the lab, the research tools or the tests, beyond those listed under
`shipped imports`, each with its reason. `not shipped` names those modules by path pattern. There are none today.

### The import path

No function in what the release ships changes `sys.path` itself (a call of its `insert`, `append`, `extend`,
`remove`, `pop` or `clear`, or an assignment to it), beyond those listed under `path changes`, each with its reason.
Today they are `paths.use` itself, and `looks.measurer`, which puts its own folder on the path before it imports a
look's measurer by name. The test does not hold `paths.use()` calls: fourteen shipped ones are inside functions
(a folder already on the path is left where it is, so they are harmless). New code calls `paths.use()` at the top of
its module, as section 3 says.

### Compiler families

A module listed under `compiler families` does not import the compiler. The list holds the families (section 1),
each of which takes the tables and helpers it shares with the compiler from `compiler_tables.py`, and the other
modules split off the compiler, since none may import it either: `compiler_tables.py`, `native_edit.py` and
`piece_lookup.py`. A family or module moved out of the compiler is listed in the commit that moves it.

### structure.json's form

`structure.json` is sorted, with one entry a line (two-space indent, as `json.dumps(..., indent=2, sort_keys=True)`
writes it). Changes to different entries then merge without a conflict.

## 5. Changing the structure

Move, then change. A move changes nothing else: the moved code is the old code, and a step's stated substitutions
(`self.` to `self.c.`, a write to its owner's setter) are the only differences. A behaviour change found on the way is
a commit of its own with its own ledger entry. A function that cannot move without a change of behaviour stays where
it is.

The tools that show a move changed nothing:
- [`tools/repo/moved_code.py`](tools/repo/moved_code.py) `<base commit> <old file> <new file> [--subst OLD=NEW ...]
  [--subst-file <json>] [--names ...]`: each moved Python function's syntax tree, or JavaScript function's tokens (a
  page factory's functions included, as `createX.f`), is the old one's, after the move's stated substitutions
  (`--subst-file` holds [OLD, NEW] pairs, for an OLD holding `=`). Use it for every move.
- `tools/editor/tests/build_outputs.py`: the quick and baked Builds of its project inputs (its `INPUTS`), which
  together hold every lane of the native edit and take the Build's routes into the relight, compared byte for byte.
  Record on the commit the change starts from (in a scratch worktree of that commit), record on the change, and
  compare. Use it for a change to the compiler, the Build, the copy tool, the
  package tools or the relight.
- `tools/editor/tests/compile_record.py`: every compile the editor suite makes (spec, report and native edit),
  recorded and compared. Use it for a change to the compiler.
- `tools/viewer/tests/web_names.py`: no name in the page's modules left undefined, no import left unused, and no
  assignment to an imported name (a write that must go through its owner's setter). A moved function's missing
  import, or such a write, throws only when its line runs. It runs ESLint from a scratch folder (it needs node and
  npm), by hand: `run_tests.py` does not run it. Use it for a change to the page.
- The `api-names` browser check (`browser_smoke.py`, against `tools/viewer/tests/viewer_api_names.json`):
  `window.viewer`'s names unchanged. Use it for a change to the page.
- `python -B tools/run_tests.py <suite> --times`: the slowest tests and classes. Use it before and after making a
  suite faster.

## 6. A checklist for a change

Before a commit that adds a module, a function longer than a screen, or a reader or writer of a format:

1. Does one exist already (section 3, "One home")?
2. Does it go where section 2 says? If the table has no row, add the module and the row.
3. Is its pure part apart from its wiring, and tested?
4. Is the same rule needed on the other side, the page or Python? Then one file both read, or a case file.
5. Did it make a file or a function grow well past the guideline sizes (section 4)? Then see whether the new code
   is a module or a function of its own.
