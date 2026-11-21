# How the code is shaped

This is for anyone who changes the editor's code, person or agent. The [README](README.md) says what the editor does
and how the repository is laid out. This document says how the parts fit, where new code goes, and the rules that keep
the shape. A test holds what a test can hold (section 4). The rest needs judgement, and is here so that it is written
once.

It describes the code as it is. When a change sets a new pattern (a new kind of module, a new home for some state), the
same commit writes the pattern here.

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
module, whose `startScene` starts everything. app.js imports the page's other modules. three.js comes from `vendor/`
through the import map (fetched by `setup_vendor.py`, not tracked). The page draws the scene, edits it and keeps the
project document. It asks the server through [`api.js`](tools/viewer/web/api.js), and keeps what a browser remembers
through [`storage.js`](tools/viewer/web/storage.js). [`project.js`](tools/viewer/web/project.js) holds the document's
shape on the page. What several of the page's areas use (the scene, its roots, the selection, the project open, the
groups, the buildings, the cleared map's state, what the document session shares with other areas, what Play in
game goes by, the prefab builder's document, the clipboard and the Add panel's lists) lives in
[`editor_state.js`](tools/viewer/web/editor_state.js). After an edit, an undo or a selection, each area keeps its own
panels up through the edit hub, [`edit_hub.js`](tools/viewer/web/edit_hub.js), with which its module registers them.
The open document's life is
[`document_session.js`](tools/viewer/web/document_session.js)'s: a project opened, saved and left, its unsaved state
kept on the server as a draft against a lost tab and offered back, and the banner under the header. The scene to and
from a document's state is [`document_state.js`](tools/viewer/web/document_state.js)'s: `editStateNow` reads the edits
on screen as a project records them, and `applyState` puts such a state back on the map. A project's file, its drafts
and the prefab builder's document all go through these two. An added thing's record (a copy of a piece, a made piece,
a cover block, a light, an effect, a sound or a lens flare), as a project, a prefab and the prefab builder's document
keep it, is written and read in one place, [`piece_records.js`](tools/viewer/web/piece_records.js). Build and Play in
game are [`build_play.js`](tools/viewer/web/build_play.js)'s: Build's panel and the window that follows a build to its
end, Play's dialog and the Game menu's Installs, the header's Build and Play buttons, the test squad's line, the
prefab builder's Test in game and the build queue's chip. What a build status or a play's answer says, in words, is
worked out without the page in [`build_window.js`](tools/viewer/web/build_window.js) and
[`play.js`](tools/viewer/web/play.js). The prefab builder (the page opened on a prefab) is
[`builder_session.js`](tools/viewer/web/builder_session.js)'s: the prefab's document as the scene holds it, opened with
a draft offered back and saved, its size line and the ground drawn under it, Align to grid, missing pieces looked for
by recipe, and the Problems check. Prefabs saved and placed are [`prefab_place.js`](tools/viewer/web/prefab_place.js)'s:
the selection (or the builder's whole document) as a prefab's records, the Save as prefab dialog and the save, the
prefab's picture, and a prefab of the Add panel's Prefabs tab read into a clip and placed as a paste is. A prefab
document's rules (its size and limits, its records normalized) are
[`prefab_document.js`](tools/viewer/web/prefab_document.js)'s, and the Prefabs tab is
[`prefabs.js`](tools/viewer/web/prefabs.js)'s. The Lights view is [`lights_wiring.js`](tools/viewer/web/lights_wiring.js)'s:
the map's lights as roots, which are drawn and whether each can be edited, the view on or off, the area lights
following their glowing pieces, Solo, the selected light's reach, the panel's light section, the drag handles on the
selected light (and on the picked effect or sound), the Add panel's lights and the project's light records. What it
draws (markers, shapes, handles, Solo's lights) is made without the page in
[`lights_view.js`](tools/viewer/web/lights_view.js), and a light value's rules are
[`light_rules.js`](tools/viewer/web/light_rules.js)'s. The Effects view is
[`effects_wiring.js`](tools/viewer/web/effects_wiring.js)'s: the map's effects, sounds and lens flares as roots, where
each stands now (with the piece that carries it, the landing's with its zone), which are drawn and whether each can be
changed, the view on or off and its kinds, the likeness (each effect drawn moving where it stands, the Add panel's
pictures and hover pane), the panel with the Wave preview and the values, and the project's records of effects and
sounds. What it draws is made without the page in [`effects_view.js`](tools/viewer/web/effects_view.js) (markers,
boxes, spheres) and [`effects_preview.js`](tools/viewer/web/effects_preview.js) (the likeness); what a record says and
what of it can change is [`effects_rules.js`](tools/viewer/web/effects_rules.js)'s, and a particle system's stepping
[`effects_sim.js`](tools/viewer/web/effects_sim.js)'s. The Spawns view and the mission objects' moves are
[`spawns_wiring.js`](tools/viewer/web/spawns_wiring.js)'s: the markers of the base map's spawn points, the streams'
mission objects and a patch's spawn points, the view on or off and its families, a marker picked and its panel with
its controls, the project's moves and edits of them (moved, turned, given values, copied, deleted, each one undo step)
and what the project records of them, the picked marker's gizmo, a spawn point added from the Add panel, and the
project's spawn rule. What a marker is and says is worked out without the page in
[`spawns_view.js`](tools/viewer/web/spawns_view.js), and what the game does with a spawn point in
[`spawn_rules.js`](tools/viewer/web/spawn_rules.js). The Landing zones view is
[`zones_wiring.js`](tools/viewer/web/zones_wiring.js)'s: the zones drawn and the map's own landing pieces a moved zone
takes along, the view on or off, a zone picked with its gizmo and panel, the zones changed and added (each change one
undo step) and what follows a change of the cleared mark. A zone's rules (its soldier points, the map's own landings,
which zones plain Enemy Within lands at) are worked out without the page in
[`spawns.js`](tools/viewer/web/spawns.js). The Buildings view and box select are
[`buildings_wiring.js`](tools/viewer/web/buildings_wiring.js)'s: the project's buildings as boxes (roots in
`volumeRoots`) and the map's own (those that can be edited with them, the others in grey to be read), the project's
buildings worked out from the boxes after every edit and put back from a project, the view on or off and its tools,
the boxes changed (each change one undo step), the six face handles a box has (a picked no-spawn volume and box
select use them too) and their drags, the cursor's floors drawn round the boxes, the panel, the Normal button's Floor
boxes, and box select (a box drawn over the ground that selects what is inside). A building's floors, the cursor's
floors and a building's problems are worked out without the page in [`floors.js`](tools/viewer/web/floors.js).
The map's buildings' records are its too, at the start of its factory: every building the floors code reads
(`allBuildings`: the map's as exported where unchanged, the project's and the map's changed ones by their boxes),
which of the map's own can be edited, which the project changed or deleted (`mapEdits`), and what the project saves
of them (`savedBuildings`).
The made pieces (walls, floors, roofs and ground shapes made from numbers on a look's donor) are
[`made_handles.js`](tools/viewer/web/made_handles.js)'s at their base: what a made piece is, its look's donor as a
template, its state and its changes (a state put on it with its mesh drawn anew, each change one undo step), where made
walls meet worked out again after every change, and the picked piece's handles and their drags (a rock's corners moved
with a gizmo of their own). The made pieces' looks are
[`made_looks_wiring.js`](tools/viewer/web/made_looks_wiring.js)'s: the look each tool draws in (remembered in the
browser), the look picker's samples and what choosing a look does, the eyedropper, a made piece made again in another
look with the pieces the change takes, and its Look row in the piece panel. The looks' catalogues are
[`looks.js`](tools/viewer/web/looks.js)'s and the picker's panel [`look_picker.js`](tools/viewer/web/look_picker.js)'s.
Drawing a made piece is
[`made_drawing.js`](tools/viewer/web/made_drawing.js)'s: the Build menu, and a wall, a room (with a roof and its
building), a floor or roof, or a ground shape dragged out over the ground with its ghost and made as an added copy of
its look's donor. The piece panel's sections of a made piece are [`made_panel.js`](tools/viewer/web/made_panel.js)'s:
the Wall section with its openings (how each plays, a doorway wanting a door) and its buttons, the Floor section with
its holes, the Ground section, and the Room section of a drawn room picked whole (its walls' and roof's looks, its
storeys); Delete with an opening's handle last touched takes that opening out. Break and Repair are
[`made_breaking.js`](tools/viewer/web/made_breaking.js)'s: the Break rows, the Break tool's blasts on a made wall,
floor or roof or on one of the map's own fracturing pieces, and a broken piece drawn without the fragments its blasts
knock out, as the Build does. What is pure about the wall, slab and ground tools is
[`walls.js`](tools/viewer/web/walls.js)'s and [`ground.js`](tools/viewer/web/ground.js)'s, and a made piece's request
(its kind, version and numbers) and the look a plain one is made in are
[`made_requests.js`](tools/viewer/web/made_requests.js)'s.
Cover blocks and invisible floors (invisible pieces the Build makes from a recipe) are
[`cover_wiring.js`](tools/viewer/web/cover_wiring.js)'s: a cover piece's recipe, mesh and template, the Add panel's
Invisible kind, the ground under an invisible floor as the game's floor trace finds it (the map's collision asked for
once, Fit to ground), the piece panel's cover section, a new record put on a piece (one undo step), and the handles on
a picked cover piece and their drags. What is pure about a cover piece (its box, its tiles, its sizes, its words) is
[`cover.js`](tools/viewer/web/cover.js)'s. The piece panel's Flags group and its chip are
[`flags_panel.js`](tools/viewer/web/flags_panel.js)'s: a piece's five flags as the project has them, the group's rows
over the picked actors, a change of them (one undo step, after asking where a prop's pathing gate would change a half-on
role) and Reset; the flags' rules are [`piece_flags.js`](tools/viewer/web/piece_flags.js)'s. Select all of a kind is
[`select_kind.js`](tools/viewer/web/select_kind.js)'s: every drawn piece or effect of a picked one's kind (inside box
select's box, if one is drawn), so that the Flags group can set them all. The user's groups are
[`groups.js`](tools/viewer/web/groups.js)'s: the groups' basics (a group's parent and chain, the outermost locked group
it is in, a group's pieces, a piece's member record and key, the groups cloned: plain exports at its top), a group's
pieces on the map now, what the selection is to the groups, what a group's members are in words, the piece panel's
group section with the group chip, and the groups changed (Lock as group, Add to group, Ungroup, each change one undo
step); a group's record (its key, its members' keys, the tree pruned of a group left with one member)
is [`project.js`](tools/viewer/web/project.js)'s. Align is [`align.js`](tools/viewer/web/align.js)'s: the others of
the selection lined up with a target along the chosen axes (one undo step), the piece panel's Align section and the
white box on the target. Copy, paste and placing are [`clipboard.js`](tools/viewer/web/clipboard.js)'s: a clip of the
selection, a clip pasted (new pieces with links, groups and buildings of their own, one undo step), the see-through
preview that follows the cursor until a click places a copy (with the snaps, Level snap and the recipe snap), the Add
panel shown with its tab and an entry of it chosen and placed, and a copy dragged off with Shift. The pieces and
effects of other maps read as templates are [`library_templates.js`](tools/viewer/web/library_templates.js)'s: their
records read in a few requests, a piece's or an effect's template (its meshes, materials and textures joining the
page's tables), the templates a project's or a prefab's records name, and what such a piece costs and says; the Add
panel's All maps browser is [`library.js`](tools/viewer/web/library.js)'s.
The play area, the map's size as the project sets it and the rail's Map grid are
[`map_grid.js`](tools/viewer/web/map_grid.js)'s: the grid's origin and the corner the game counts its tiles from
(plain exports), the play area drawn, the map's own size kept and a size set (the grid
drawn at it, a grown map's new area as a faint sheet), and the Map grid's handles, drags and panel, each new size one
undo step. Clear map and what goes with it are [`clear_map.js`](tools/viewer/web/clear_map.js)'s: the landing zones as
the project has them (its own, or the map's own landings joined with the install's lines) and the landing zone's
pieces, the ground's height, the Clear map window and the clear (one undo step), the Missions panel and the header's
Mission picker, the Map picture dialog, and the ground grid with the saved floor tiles still carried.
The scene's pieces are [`scene_pieces.js`](tools/viewer/web/scene_pieces.js)'s: picking, a texture and a material made
from the export's records, the meshes' and materials' loads (each once, shared), a piece's root built, added and taken
away, an original's parts and its box of mesh vertices, a piece's box from what is drawn of it, an added piece made
from its template (a made piece's mesh from its numbers), the template a record's piece is copied from and the pose an
original's rule keeps under tile snap; an actor's pose at a render matrix, and the matrix of a pose, are plain exports
at its top. The map's families and assemblies (the families set as the map's arrive, each original's assembly with
its link tag, a piece's assembly, its own map's or another's) are [`map_families.js`](tools/viewer/web/map_families.js)'s.
The cutaway and the tile views are [`cutaway.js`](tools/viewer/web/cutaway.js)'s: which pieces are drawn and how each is
cut (the Floor picker, Interior, the streams shown, the clear), the tile grid round the selection, View options' Floor
tiles overlay with its tips and clicks, and the Floor picker's buttons.
The building floors a piece is listed on are [`floor_listings.js`](tools/viewer/web/floor_listings.js)'s: the project's
buildings' listings by the game editor's rule from what is drawn of the piece, the map's own unchanged buildings' saved
or carried listings, and the key of the pieces' edits that the cutaway, the ground grid and Level snap follow.
Floor pieces and Level snap are [`level_snap.js`](tools/viewer/web/level_snap.js)'s: the pieces that carry the map's
saved floor tiles and a floor piece's support, Level snap and its button, and the Floor picker's floor under a point.
Delete, Reset piece and Reset all are [`delete_reset.js`](tools/viewer/web/delete_reset.js)'s, each one undo step,
with a large step put under the busy mark.
Prepare is [`prepare.js`](tools/viewer/web/prepare.js)'s: the dialog that exports an old map again (when it opens,
before a build or a play, from a build that failed for want of it), Later's banner, and a build or a play waiting for
it.
As a map or a prefab opens, app.js's `startScene` starts the scene part by part, each part a function of the module
that owns it, called in the order the page always started them: the scene's pieces built (`buildPieces`), the landing
lines read and the header's Mission picker (Clear map's `readLandingLines`, `startMissionPicker`), the Map lighting
mode's buttons and the view lit (the Lights view's `lightingModes`, `applyMapLighting`), the lights and effects made
(`buildLights`, `buildEffects`), the Floor picker and View options' patch helpers (the cutaway's `sceneViewOptions`), the
camera framed, the map's export checked (Prepare's `prepareOpened`) and the prefab builder's page dressed
(`builderPage`). What is no one area's (the page's title, View options' Full or Interior and the Map menu's items, the
import notes, the gizmo's Linked button) is [`scene_start.js`](tools/viewer/web/scene_start.js)'s.
How the user drives the view and the editor is [`navigation.js`](tools/viewer/web/navigation.js)'s: the camera (Frame and
the framing of a piece or the map, the arrow keys and WASD with Q and E, the look-drag along the view, the wheel's zoom
to the point under the cursor, View options' camera speeds), the gizmo's buttons with the pivot and snap (kept up after
each edit by the edit hub's `tools` refresh), and the editor's keys, each calling the area that owns what it does.
The header's menus (one open at a time, a press elsewhere closing it) are [`popups.js`](tools/viewer/web/popups.js)'s.
The server's list of maps and the map browser made from it as the page opens are
[`map_menu.js`](tools/viewer/web/map_menu.js)'s: a map's name in the lists, the list brought up to the server's, the
browser made with what choosing a map does, and the Map menu's button and Change map; the browser itself is
[`map_browser.js`](tools/viewer/web/map_browser.js). The loading overlay (its message, bar and detail line, an opening
document's steps on it, a JSON file read with its progress) is [`loading.js`](tools/viewer/web/loading.js)'s.
The page's small helpers of the DOM and of words (an element of text, a term and its value in a list, a count with
its noun, a name's last part, a copy to the clipboard told on its button, a row of buttons used like a select, a
sentence's first letter made a capital) are [`dom_words.js`](tools/viewer/web/dom_words.js)'s, which imports nothing.
app.js's `open` starts the page: the map list read, the first run's install asked for, the map browser made, the map
the address asks for opened (or the browser shown on it, to prepare it), and `startScene`.
`window.viewer`, the set of hooks the browser checks drive, is made by [`test_api.js`](tools/viewer/web/test_api.js)
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
(which stop a Build), warnings, notes and the records left out. The `Compiler` class runs the document's and the
export's checks and the edit families, in `run`'s order. It keeps what joins them: the family gates (`FAMILIES` says
which families build for every project), the map's own pieces moved, deleted and copied and the pieces of other
maps (`overrides` and `added`, with the assemblies and the grid rule), cover blocks, `spec`, and the diagnostics
(`error`, `warn`, `note`, `leave_out`) through which the families report. The families, in modules of their own, are
each a class the compiler makes for itself:
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
made it, each file with its hash: build.py and the modules of `tools/editor` it imports (`editor_modules`, found from
their imports), and the tools of `tools/bake` and `tools/upk` it runs, which build.py lists.

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
`copy_record`, so no field of a copy is lost on the way; a test makes its own. `build(st)` runs the steps in their
order, each a function of the state that reads its fields and writes its results to fields `BuildState` names with
the step that fills them:
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

| Kind of work | Where it goes |
| --- | --- |
| An area of the page (a panel, a view, a tool) | A module of its own in `tools/viewer/web`. When it needs many of app.js's functions, it is made by a factory that takes them as one argument object: `createProjectDialog` in [`project_files.js`](tools/viewer/web/project_files.js) and `createQueueController` in [`build_queue.js`](tools/viewer/web/build_queue.js) are the model, and `createDocumentSession` in [`document_session.js`](tools/viewer/web/document_session.js) is one made from many of app.js's functions (section 3, "The page"). |
| Opening, saving or leaving a document, its drafts kept for recovery, the banner under the header | [`document_session.js`](tools/viewer/web/document_session.js) (`createDocumentSession`). The prefab builder's own saving and opening are in [`builder_session.js`](tools/viewer/web/builder_session.js), and share its drafts' state in [`editor_state.js`](tools/viewer/web/editor_state.js). |
| The prefab builder: the prefab's document as the scene holds it, opened, kept and saved; its size line and the ground under it, Align to grid, missing pieces looked for by recipe, the Problems check | [`builder_session.js`](tools/viewer/web/builder_session.js) (`createBuilderSession`). A prefab document's rules (its size and limits, its records normalized onto its own grid) go in [`prefab_document.js`](tools/viewer/web/prefab_document.js), pure, with its node test, and the server's side in [`prefabs.py`](tools/viewer/prefabs.py). |
| A prefab saved or placed: the selection as a prefab's records, the Save as prefab dialog, the save, the prefab's picture, a prefab of the Prefabs tab read and placed | [`prefab_place.js`](tools/viewer/web/prefab_place.js) (`createPrefabPlace`). The Add panel's Prefabs tab is [`prefabs.js`](tools/viewer/web/prefabs.js)'s browser; each piece's record is [`piece_records.js`](tools/viewer/web/piece_records.js)'s. |
| Build and Play in game: Build's panel and its window, Play's dialog, the Game menu's Installs, the header's Build and Play buttons, the test squad's line, the prefab builder's Test in game opened, the build queue's chip | [`build_play.js`](tools/viewer/web/build_play.js) (`createBuildPlay`). What a build status or a play's answer says, in words, goes in [`build_window.js`](tools/viewer/web/build_window.js) or [`play.js`](tools/viewer/web/play.js), pure, with their node tests; Build's panel itself is [`build_options.js`](tools/viewer/web/build_options.js), the test squad's dialog [`squad.js`](tools/viewer/web/squad.js), the prefab test's window [`prefab_test.js`](tools/viewer/web/prefab_test.js) and the queue's controller [`build_queue.js`](tools/viewer/web/build_queue.js). |
| The Lights view: a light's root, its panel section, Solo, its reach, its drag handles (and the picked effect's or sound's), the area lights following their pieces, a light added from the Add panel or a recipe, the project's light records | [`lights_wiring.js`](tools/viewer/web/lights_wiring.js) (`createLightsWiring`). What it draws (a marker, an emission shape, a handle, Solo's lights) goes in [`lights_view.js`](tools/viewer/web/lights_view.js) (three.js, nothing of the page), and a light value's rule in [`light_rules.js`](tools/viewer/web/light_rules.js), pure, with its node and Python tests (`shared_cases_test.mjs`, `twin_constants_test.mjs`, `test_lights.py`). |
| The Effects view: an effect's, sound's or lens flare's root and where it stands, the view's kinds, its panel, the Wave preview, its values' controls, the likeness, a copy added, the project's records of effects and sounds | [`effects_wiring.js`](tools/viewer/web/effects_wiring.js) (`createEffectsWiring`). What it draws goes in [`effects_view.js`](tools/viewer/web/effects_view.js) (a marker, a box, a sound's spheres) or [`effects_preview.js`](tools/viewer/web/effects_preview.js) (the likeness), three.js and nothing of the page; what a record says and what of it can change in [`effects_rules.js`](tools/viewer/web/effects_rules.js), and a particle system's stepping in [`effects_sim.js`](tools/viewer/web/effects_sim.js), pure, with their node tests. |
| The Spawns view and the mission objects' moves: a spawn point's or mission object's marker, the view's families, its panel and controls, a move, turn, value, copy or delete of one, its gizmo, a spawn point added from the Add panel, the project's spawn rule | [`spawns_wiring.js`](tools/viewer/web/spawns_wiring.js) (`createSpawnsWiring`). What a marker is, draws and says goes in [`spawns_view.js`](tools/viewer/web/spawns_view.js) (its shapes take three.js as an argument) and what the game does with a spawn point in [`spawn_rules.js`](tools/viewer/web/spawn_rules.js), pure, with their node tests (`spawns_view_test.mjs`, `spawn_rules_test.mjs`, `project_spawns_test.mjs`). |
| The Landing zones view: a zone drawn, picked, moved and turned with its gizmo, its panel and controls, a zone changed, copied, deleted or added, what follows the cleared mark | [`zones_wiring.js`](tools/viewer/web/zones_wiring.js) (`createZonesWiring`). A zone's rules go in [`spawns.js`](tools/viewer/web/spawns.js), pure, with its node tests (`clear_map_test.mjs`, `twin_constants_test.mjs`). |
| The Buildings view and box select: the buildings' records (every building the floors code reads, the map's own changed or deleted, what the project saves of them), a floor box (made, stretched, moved, copied, deleted), a building's name, kind and floors, the map's own buildings edited or read, the face handles and their drags, the cursor's floors round a box, the view's panel, the Normal button's Floor boxes, box select | [`buildings_wiring.js`](tools/viewer/web/buildings_wiring.js) (`createBuildingsWiring`). A building's or a floor's rule (the floors around pieces, the cursor's floors, a building's problems, the pieces a box lists) goes in [`floors.js`](tools/viewer/web/floors.js), pure, with its node tests (`floor_rules_test.mjs`, `map_buildings_test.mjs`, `source_floor_match_test.mjs`); a building's record in [`project.js`](tools/viewer/web/project.js) (`validBuilding`, `tidyBuilding`). |
| A made piece (a wall, floor, roof or ground shape made from numbers): whether a piece is one, its look's donor, its state and changes (each one undo step), its mesh's record, where made walls meet, the picked piece's handles and their drags, a rock's corners | [`made_handles.js`](tools/viewer/web/made_handles.js) (`createMadeHandles`). What is pure about a made piece's numbers and their changes (`resizedWall`, `movedOpening`, `raisedWall`, `resizedSlab`, `movedHole`, `resizedGround`, `movedPoint`, `wallJoins`, the mesh's numbers) goes in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js), with their node tests (`walls_test.mjs`, `ground_test.mjs`, `made_shapes_test.mjs`); its request and a plain piece's look (`madeRequest`, `isPlain`, `plainLook`) in [`made_requests.js`](tools/viewer/web/made_requests.js) (`made_requests_test.mjs`). |
| The made pieces' looks: the look a tool draws in, the look picker's samples and what choosing a look does, the eyedropper, a made piece's look changed (with the pieces the change takes), its Look row | [`made_looks_wiring.js`](tools/viewer/web/made_looks_wiring.js) (`createMadeLooksWiring`). A look's catalogue and entries go in [`looks.js`](tools/viewer/web/looks.js), the picker's panel in [`look_picker.js`](tools/viewer/web/look_picker.js), with their node tests (`looks_test.mjs`, `look_picker_test.mjs`). |
| Drawing a made piece: the Build menu's tools, a wall, room, floor, roof or ground shape dragged out with its ghost and made | [`made_drawing.js`](tools/viewer/web/made_drawing.js) (`createMadeDrawing`). Where a drawn piece stands and what its numbers are (`drawnWall`, `drawnRoom`, `drawnSlab`, `roomRoof`, `drawnGround`) go in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js), pure, with their node tests (`walls_test.mjs`, `ground_test.mjs`). |
| The piece panel's sections of a made piece: the Wall section and its openings, the Floor section and its holes, the Ground section, the Room section of a drawn room, an opening taken out by Delete | [`made_panel.js`](tools/viewer/web/made_panel.js) (`createMadePanel`). What an opening, a hole or a room's storeys are and say (`openingPlay`, `playWords`, `withOpening`, `withHole`, `steppedStoreys`, `slopeWords`) goes in [`walls.js`](tools/viewer/web/walls.js) or [`ground.js`](tools/viewer/web/ground.js), pure, with their node tests. |
| Break and Repair: a blast set off on a made piece or on one of the map's fracturing pieces, the Break rows and tool, a broken piece drawn without its knocked-out fragments | [`made_breaking.js`](tools/viewer/web/made_breaking.js) (`createMadeBreaking`). A blast's record goes in [`piece_records.js`](tools/viewer/web/piece_records.js) (`cloneBlasts`), a made piece's blasts in its mesh's request in [`walls.js`](tools/viewer/web/walls.js) (`blastQuery`), and the Build's side in [`made_blasts.py`](tools/bake/made_blasts.py). |
| A cover block or invisible floor: its recipe and template, the Add panel's Invisible kind, the ground under a floor (the map's collision, Fit to ground), the piece panel's cover section, a new record put on a piece, its handles and their drags | [`cover_wiring.js`](tools/viewer/web/cover_wiring.js) (`createCoverWiring`). What is pure about a cover piece (its box and mesh, the tiles it covers and what the game makes of them, a size changed by a handle, its words) goes in [`cover.js`](tools/viewer/web/cover.js), with its node tests (`cover_test.mjs`, `cover_tiles_test.mjs`), and the Build's side in [`cover_blocks.py`](tools/bake/cover_blocks.py). |
| The piece panel's Flags group and its chip: a piece's flags as the project has them, a row changed (one undo step), the question about a prop's pathing gate, Reset | [`flags_panel.js`](tools/viewer/web/flags_panel.js) (`createFlagsPanel`). A flag's rule (a piece's roles and their limits, what a request does, its normalized form) goes in [`piece_flags.js`](tools/viewer/web/piece_flags.js), pure, with its node tests (`piece_flags_test.mjs`, `project_flags_test.mjs`), and the compiler's side in [`flag_edits.py`](tools/editor/flag_edits.py). |
| Select all of a kind: what counts as a piece's or an effect's kind, the pieces and effects that match (inside box select's box), the button | [`select_kind.js`](tools/viewer/web/select_kind.js) (`createSelectKind`). |
| The user's groups: a group's chain, its pieces, a piece's member key, the groups cloned, a group's pieces on the map now, what the selection is to the groups, the group section and chip, a group made, added to or ended (one undo step) | [`groups.js`](tools/viewer/web/groups.js): the basics as plain exports, the rest in `createGroups`. A group's record (`groupKey`, `pruneGroups`) goes in [`project.js`](tools/viewer/web/project.js), and the compiler's side in [`group_edits.py`](tools/editor/group_edits.py). |
| Align: the others of the selection lined up with a target, the Align section and its white box | [`align.js`](tools/viewer/web/align.js) (`createAlign`). |
| The play area, the map's size as the project sets it, the rail's Map grid (its handles, drags and panel, a new size as one undo step), the grid's origin and tile corner | [`map_grid.js`](tools/viewer/web/map_grid.js) (`createMapGrid`; `gridOrigin` and `tileCorner` plain exports). A stage's record (its shape and limits) goes in [`project.js`](tools/viewer/web/project.js) (`validStage`, `tidyStage`, `stageMax`), the cursor's floors in [`floors.js`](tools/viewer/web/floors.js) (`cursorStoreys`), and the compiler's side in [`mission_edits.py`](tools/editor/mission_edits.py). |
| Clear map and the landings: the landing zones as the project has them, the landing zone's pieces, the ground's height, what a clear takes and keeps, the Clear map window and the clear; the Missions panel, which game is set, the header's Mission picker; the Map picture dialog; the ground grid | [`clear_map.js`](tools/viewer/web/clear_map.js) (`createClearMap`). A zone's rules go in [`spawns.js`](tools/viewer/web/spawns.js) (`startingZones`, `ownLandings`, `groundOf`), a mission kind's in [`missions.js`](tools/viewer/web/missions.js), what an effect does in a clear in [`effects_rules.js`](tools/viewer/web/effects_rules.js) (`survivesClear`), the dialogs in [`missions_panel.js`](tools/viewer/web/missions_panel.js) and [`map_picture.js`](tools/viewer/web/map_picture.js), and the compiler's side in [`mission_edits.py`](tools/editor/mission_edits.py). |
| The scene's pieces: picking, a texture or material made, the loads of meshes and materials, a piece's root built, added or taken away, its unedited matrix, an original's parts and boxes, a piece's box, an added piece made from its template, a record's template, an original's pose rule under tile snap, an actor's pose at a render matrix | [`scene_pieces.js`](tools/viewer/web/scene_pieces.js) (`createScenePieces`; the pose's helpers `actorPose` and `movedMatrix` plain exports). The meshes loaded are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`geometryCache`); what a material record says is the export's ([`export.py`](tools/viewer/export.py)). |
| The map's families and assemblies: the families set as they arrive, an original's assembly and its link tag, a piece's assembly (its own map's or another's) | [`map_families.js`](tools/viewer/web/map_families.js) (`createMapFamilies`). The families' rules are the server's ([`families.py`](tools/viewer/families.py)); the Add panel's use of them [`pieces.js`](tools/viewer/web/pieces.js)'s (`useFamilies`). |
| The cutaway, the tile grid, the Floor tiles overlay, the Floor picker's buttons | [`cutaway.js`](tools/viewer/web/cutaway.js) (`createCutaway`). What is pure about them (the visible bounds, a footprint, the tiles around it, Interior's planes, the overlay's tiles) goes in [`view_layout.js`](tools/viewer/web/view_layout.js), and a piece's listings in [`floor_listings.js`](tools/viewer/web/floor_listings.js). |
| The building floors a piece is listed on (the project's buildings', the map's own), the key of the pieces' edits | [`floor_listings.js`](tools/viewer/web/floor_listings.js) (`createFloorListings`). The rules (`touchedFloors`, `ruleListing`, `copyFloors`, `floorAt`, `carriedListing`, `sourceFloorMatch`) go in [`floors.js`](tools/viewer/web/floors.js), with their node tests, and the Build's side in [`buildings.py`](tools/bake/buildings.py). |
| Floor pieces, Level snap and its button, the Floor picker's floor under a point | [`level_snap.js`](tools/viewer/web/level_snap.js) (`createLevelSnap`). The floor rules (`ownedFloors`, `classifyFloors`, `floorStamps`, `buildingWithFloor`, `storeyHeight`) go in [`floors.js`](tools/viewer/web/floors.js), with their node tests. |
| The selection: a piece, light, building's box or effect picked (or nothing), the views stepping aside for it, the piece panel filled for it (a cover block's or invisible floor's too), the selected piece's highlight, a ladder's ends and its chip, the grid chip of a piece the recipe snap holds | [`selection.js`](tools/viewer/web/selection.js) (`createSelection`). An area's own part of the piece panel (its section shown or hidden for what is picked, its panel, a chip) is the area's module's, registered with one of the edit hub's select runs ([`edit_hub.js`](tools/viewer/web/edit_hub.js)), never called by name from `select`. |
| The camera (framing, the keys that move and turn it, the look-drag, the wheel, the speeds), the gizmo's mode buttons, the pivot and snap, a key of the editor | [`navigation.js`](tools/viewer/web/navigation.js) (`createNavigation`). A key calls the function of the area that owns what it does, given to the factory; the help panel in `index.html` lists the keys for users. |
| Delete, Reset piece, Reset all, a large step under the busy mark | [`delete_reset.js`](tools/viewer/web/delete_reset.js) (`createDeleteReset`). |
| A header menu (a button with `data-pop` and its menu) | `index.html`; [`popups.js`](tools/viewer/web/popups.js) (`createPopups`) opens and closes it, and draws a menu afresh as it opens where the menu needs it. |
| The map list, the map browser's making and what choosing a map does, the Map menu's button and Change map | [`map_menu.js`](tools/viewer/web/map_menu.js) (`createMapMenu`). The browser's dialog is [`map_browser.js`](tools/viewer/web/map_browser.js); the list and the browser are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`mapCatalogue`, `mapBrowser`). |
| The loading overlay's words and bar, a JSON file read with its progress | [`loading.js`](tools/viewer/web/loading.js) (`createLoading`). |
| An element of text, a term and its value in a list, a count with its noun, a name's last part, a copy to the clipboard told on its button, a row of buttons used like a select, a sentence's capital | [`dom_words.js`](tools/viewer/web/dom_words.js), pure (it imports nothing), with its node test (`dom_words_test.mjs`). An area's own words go in its own pure module. |
| Prepare: the dialog that exports the map again, a build or a play waiting for it | [`prepare.js`](tools/viewer/web/prepare.js) (`createPrepare`), and the server's side in [`exports.py`](tools/viewer/exports.py). |
| Copy, paste and placing: a clip of the selection, a paste, the preview that follows the cursor and where a click places it, the Add panel shown and its tab, an entry of it chosen and placed, a copy dragged off with Shift | [`clipboard.js`](tools/viewer/web/clipboard.js) (`createClipboard`). A copied thing's record goes in [`piece_records.js`](tools/viewer/web/piece_records.js) (`optionsOf`, `stateOfRoot`), a group's in [`project.js`](tools/viewer/web/project.js), the pose rule's snap in [`gizmo.js`](tools/viewer/web/gizmo.js) (`recipeMove`), and a floor's height under a point in [`floors.js`](tools/viewer/web/floors.js) (`levelHeight`, `floorUnder`). |
| A piece, effect, sound or lens flare of another map read as a template: its record read, its template made, the templates a project's records name, what such a piece costs and says | [`library_templates.js`](tools/viewer/web/library_templates.js) (`createLibraryTemplates`). The records read and the templates made are kept in [`editor_state.js`](tools/viewer/web/editor_state.js) (`libraryRecords`, `effectTemplates`, `foreignEffects`, `foreignTemplates`, `donorHashes`); the Add panel's All maps is [`library.js`](tools/viewer/web/library.js), and the server's side [`library.py`](tools/viewer/library.py). |
| A new part of what a project keeps of the scene (saved, and put back when it opens) | [`document_state.js`](tools/viewer/web/document_state.js): `editStateNow` writes it into the state, `applyState` puts it back on the map. [`document_session.js`](tools/viewer/web/document_session.js) carries it between the file and those two (`openProject`, `offerProjectDraft`, `saveProject`). Then as for a field of the project document. |
| What the page does for an area as a map or a prefab opens (its part of the scene made, its panel or menu set for the scene) | A function of the area's module, returned by its factory and called from app.js's `startScene` at its place in the order (`buildPieces` in [`scene_pieces.js`](tools/viewer/web/scene_pieces.js), `readLandingLines` in [`clear_map.js`](tools/viewer/web/clear_map.js)), given what `startScene` has worked out so far as its parameters (the streamed objects, the families' answer). What is no one area's goes in [`scene_start.js`](tools/viewer/web/scene_start.js), plain exports given what they need. |
| What an area keeps up after an edit, an undo or a selection (its panel or section, a button's state, a mark in the view) | Its area's module, which registers the refresh with the edit hub, [`edit_hub.js`](tools/viewer/web/edit_hub.js), as its factory is made (`onHub(run, name, refresh)`), under a name put in the hub's `RUNS` at the place in the run where it must be called (section 3, "The page"). |
| State of the page (a module-level `let` or a collection) | The module of the one area that uses it. State several areas use: [`editor_state.js`](tools/viewer/web/editor_state.js), exported with its setter. Never app.js. |
| A rule, a record or a sentence of the page | A pure module (no three.js, no document), with a node test in `tools/viewer/tests/<module>_test.mjs`. Examples: [`piece_records.js`](tools/viewer/web/piece_records.js), [`light_rules.js`](tools/viewer/web/light_rules.js), [`spawn_rules.js`](tools/viewer/web/spawn_rules.js), [`poserule.js`](tools/viewer/web/poserule.js). |
| The game's grid numbers on the page | [`constants.js`](tools/viewer/web/constants.js). |
| A call to the server, from the page | [`api.js`](tools/viewer/web/api.js). |
| A route of the server | A `handle_<area>` method of `viewer.py`'s handler that hands the request to its area's module (`handle_play` and [`play.py`](tools/viewer/play.py) are the model). |
| Something a browser remembers | [`storage.js`](tools/viewer/web/storage.js). |
| A setting (a folder, an install) | [`settings.py`](tools/viewer/settings.py). |
| A record of the map's export | [`export.py`](tools/viewer/export.py) or [`scene_metadata.py`](tools/viewer/scene_metadata.py), with `EXPORT_VERSION` raised. |
| A field of the project document | [`projects.py`](tools/viewer/projects.py) and [`project.js`](tools/viewer/web/project.js), with the compiler's reading of it, and the contract in [`research/editor-contracts.md`](research/editor-contracts.md). |
| A field of an added thing's record (a copy of a piece, a cover block, a light, an effect, a sound, a lens flare) | [`piece_records.js`](tools/viewer/web/piece_records.js): `recordOf` writes it (for every writer: a project, a prefab, the builder's document), `optionsOf` reads it (a project opened, a prefab placed, a paste), and `PIECE_FIELDS` names it; a case in [`piece_record_cases.json`](tools/viewer/tests/piece_record_cases.json) or [`piece_records_test.mjs`](tools/viewer/tests/piece_records_test.mjs). Then as for a field of the project document, and the prefab's check of a piece in [`prefabs.py`](tools/viewer/prefabs.py). |
| An edit family of the compiler | A class in a module of its own in `tools/editor`, made with the `Compiler` it works for (`self.c`), with its own tables and state. It takes what it shares with the compiler from [`compiler_tables.py`](tools/editor/compiler_tables.py), never imports the compiler, and reports through the compiler's `error`, `warn` and `note`. The compiler imports it at the top and names again the tables of it that others read through the compiler. The compiler holds it as an attribute named as its module (`self.effect_edits`), and reads the family's state through it (`self.effect_edits.ops`): the state has one home. A method of the family stays on the compiler only as a one-line forwarder, and only when a test or a tool calls it there by name (`Compiler.stage`). [`spawn_edits.py`](tools/editor/spawn_edits.py) is the model; section 1 lists the others. |
| A table or helper of the compiler that a family reads too | [`compiler_tables.py`](tools/editor/compiler_tables.py), named in its `__all__`. One only the compiler reads stays in `compiler.py`; one only a family reads goes in the family's module (the `SPAWN_*` tables in `spawn_edits.py`, the effects' in `effect_edits.py`, the `LIGHT_*` tables and `light_rule` in `light_edits.py`). |
| A lane of the native edit | One change across the compiler's spec, `native_split` in [`native_edit.py`](tools/editor/native_edit.py), the copy tool and the Build. In the copy tool ([`native_copy.py`](tools/bake/native_copy.py)): a maker module in `tools/bake` (as [`native_effects.py`](tools/bake/native_effects.py)); the lane's field on `BuildState` and its reading in `edit_state` (with its line in `CommandLine.LANES` of [`test_native_copy.py`](tools/bake/tests/test_native_copy.py)); and a step, a function taking the `BuildState` that reads its fields and writes its results to fields the class names, called from `build` in the place the map's writes need. |
| A piece lookup (what the compiler asks of the library of other maps' pieces) | [`piece_lookup.py`](tools/editor/piece_lookup.py) (`Library`), raising `LibraryError` (in [`compiler_tables.py`](tools/editor/compiler_tables.py)) with its code for what can't be had. The library's scan and its records are the viewer's [`library.py`](tools/viewer/library.py). |
| A reader of package bytes | [`tools/upk`](tools/upk): tagged properties through [`props.tags`](tools/upk/props.py), compressed chunks through [`decomp.read_chunk`](tools/upk/decomp.py), a map's objects through the viewer's [`Package`](tools/viewer/package.py), a mesh component's LOD records and a bulk record through [`native_fields`](tools/upk/native_fields.py)' `mesh_lods` and `bulk_record` (each value with its place in the package; [`lighting_records`](tools/upk/lighting_records.py) and [`lightmap_fields`](tools/bake/lightmap_fields.py) give their values and places in the forms their readers take). |
| A writer of package bytes | [`package_edit.write_edited`](tools/upk/package_edit.py) for edits in place, [`package_grow.py`](tools/upk/package_grow.py) for new exports. |
| A line of the game's config | [`mapsini.py`](tools/viewer/mapsini.py). |
| A tool folder on the import path | [`paths.use()`](tools/paths.py), at the top of the module. |
| A browser check | The table of checks (`CHECKS`) in [`browser_smoke.py`](tools/viewer/tests/browser_smoke.py). |
| A test hook (a name on `window.viewer` that a browser check, the guide's pictures or a script reads or calls) | [`test_api.js`](tools/viewer/web/test_api.js) (`createTestApi`): the shared state and a pure module's export imported there, what a factory returns given by `startScene` in its argument object. The name goes into [`viewer_api_names.json`](tools/viewer/tests/viewer_api_names.json) in the same change (`browser_smoke.py --url <test server> --write-api-names`), which the `api-names` check holds. |
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
  `native_copy.build` take only what joins the modules: they are large because everything was added to them.
- Keep files to about 1,500 lines and functions to about 150: past that, code gets hard to read whole. These are
  guidance, not limits (section 4). When a change makes a file or function grow well past them, see first whether
  the new code is a module or a function of its own.
- A function with more than about eight parameters takes a record instead. `Build.__init__` took 22 and
  `native_copy.build` 30, and every caller had to name them all (findings 23 and 51).
- An object's state is made where the object is made, with a comment saying which step fills it. It is never made by
  first use through `getattr` with a default: such state is invisible until it breaks (finding 23).

### One home

- A rule, a constant or a reader of a format is written once. Before writing a reader, a walker or a writer, look for
  the one there is: `props.tags`, `decomp.read_chunk`, `package_edit.write_edited`, `mapsini`; on the page `api.js`,
  `storage.js`, `constants.js` and `piece_records.js` (the one writer and reader of an added thing's record). Copies
  drift apart and each fails differently (findings 52, 55 and 56).
- A rule both the page and Python need lives in a JSON file both read, or has a case file both sides' tests read. It
  is never copied by hand with no test (finding 55).
- Code never decides by the words of a message. An error that code reads carries a code: words get rewritten
  (finding 55).

### The page

- Each piece of the page's state (a module-level `let`, or a collection changed in place) has one owner module, which
  declares and exports it:
  - other modules read it through the import, a live binding that sees each new value;
  - they give it a new value only through the owner's setter: `set<Name>` (`setSelected`, `setProject`, `setGroups`),
    or `set<Name>Value` where app.js has a `set<Name>` of its own that also draws (`setStageValue`, beside app.js's
    `setStage`);
  - a collection (a `Map`, an array) is changed in place through the import as it is.

  A counter taken one step at a time has a `next<Name>()` beside its setter (`nextCopySerial()`, where app.js wrote
  `++copySerial`; `nextChooseToken()`).

  What one area alone uses lives in that area's module, inside its factory when it is made by one (the document
  session's `navigating`). What several areas use lives in [`editor_state.js`](tools/viewer/web/editor_state.js):
  - the scene (`data`) and its roots, the selection, the project open, the groups, the buildings, the map's size, the
    cleared map's state and its landing zones, the project's missions, picture and spawn rules;
  - the server's list of maps (`mapCatalogue`) and the map browser made from it (`mapBrowser`), which app.js's `open`
    sets and shows, the map menu reads and shows, Prepare's check reads and the prefab builder's Open shows;
  - what the document session shares with other areas: `leaving`, `saving`, the drafts' timer, owner and trouble
    (the prefab builder's saves use them too), the build status, the copies' serial, and the reads a project waits for;
  - what the scene to and from a document reads of the areas that own it: the All maps library, the area lights'
    glowing pieces, the count of pieces that could not be drawn, `allBuildings`' list (the Buildings view's);
  - what Play in game goes by and other areas read or set: the play status (the Missions panel reads its mission
    kinds), the picked landing zone (the Landing zones view picks it, Land here plays it) and the mission picker's
    value;
  - what the prefab builder and prefabs saved and placed share with other areas: the builder's document (`builder`),
    the edit hub's memo of one edit event (`eventMemo`: app.js's `editChanged` makes it, and `editState` and the
    builder's document and key keep their answers in it), the map's families, the Add panel's piece list and Prefabs
    tab, the clipboard and the Add panel's choice counter, other maps' pieces and effects as read with their maps'
    hashes, the meshes loaded, and the saved prefabs' pictures waiting to be drawn;
  - which view is on (`lightsOn`, `volumesOn`, `zonesOn`, `effectsOn`, `spawnsOn`), the Normal button's Lights switch
    and whether lights are drawn (`normalLights`, `lightsShown`), which each view's switch, the selection and the keys
    read; the picked effect, the streams the Mission picker shows, what is being placed, the hint's timer, and the Map
    lighting mode with its lights' radius;
  - what of the Lights view the keys, the test hooks and app.js's event wiring, pointer handlers and draw loop read or
    set: View
    options' Area lights and reach outlines, Solo, the lights' sync with the Map lighting mode, the light whose glowing
    piece is being assigned, the area lights' copies, the drag handles and a drag under way, and the reach worked out;
  - what of the Effects view they read or set (the redraw asked, the markers drawn, the Normal button's Effects
    switch, the Wave preview's player, the likeness's switch, thinning and count), and what it reads of other areas:
    groups' pieces now (`liveCache`), box select's middles, the picked spawn marker, the pointer and its tips' redraw;
  - what of the Spawns view they (and the Clear map window and the Buildings view's handles on a no-spawn volume)
    read or set: the Normal button's spawn switch, whether its layer is made, the families shown, the zone it
    describes, the install's spawn rules, the entries drawn, the project's moves and edits of spawn points and mission
    objects (`missionMoves`) with their drag, and the kind being placed; and what it reads of the header's mission
    picker (`missionIndex`);
  - whether the next click places a landing zone (`zonePlacing`: the Landing zones view's, which the keys and the
    pointer handlers read);
  - what of the Buildings view and box select the selection (selection.js) and app.js's views' switches, the map's
    buildings' records, the keys, the pointer handlers and the test hooks read or set: the Normal button's Floor
    boxes, each building's name and kind (`buildingMeta`), the map's own buildings selected or picked to be read, the
    view's tool and a drag under way, and box select's tool, box, drag and what it would take;
  - the made pieces' look picker (`lookPicker`, made with the Add panel's piece browser) and the eyedropper
    (`lookPicking`), which app.js's dialogs' check, pointer handlers and draw loop, the keys and the test hooks read;
  - the Build menu's tool being drawn (`buildTool`) and the made piece being drawn (`wallDrawing`), which the made
    pieces' handles, app.js's pointer handlers, the keys and the test hooks read;
  - a made piece's handle being dragged (`wallDrag`), the opening whose handle was last touched (`wallFocus`: the
    selection lets it go, the made pieces' panel rings it and Delete takes it out) and the rock point picked
    (`rockPoint`), which the selection, app.js's pointer handlers, the keys and the test hooks read or set; the snap
    setting (`snapMode`; `setSnapModeValue`, beside navigation.js's `setSnapMode`, which also sets the gizmo's and draws its button)
    and a cover handle's drag (`coverDrag`: the cover blocks' handles set it), which the made pieces' handles read;
  - whether Break is on (`breaking`), which the keys and app.js's pointer handlers read;
  - the game's collision by mesh that the invisible floors measure the ground by (`lineCollision`, with
    `lineCollisionFailed`): the cover blocks' module asks for the map's, a piece of another map read adds its own, and
    the test hooks read both;
  - the target Align lines the others up with (`alignTarget`), which app.js's handler of the panel's target list sets;
  - what of placing app.js's pointer handlers and draw loop and the keys read or set: the preview's redraw asked
    (`ghostDirty`), the Add panel's tab (`libraryScope`; `setLibraryScopeValue`, beside the clipboard's
    `setLibraryScope`, which also shows the tab) and Level snap (`levelSnap`; `setLevelSnapValue`, beside Level snap's
    `setLevelSnap`, which also remembers it and draws its button); and the url the open map's export is served under
    (`cachePrefix`), which app.js's opening sets and the templates of other maps' pieces read, and the templates made
    of other maps' pieces (`foreignTemplates`), which app.js's recipes, templates and listings read;
  - the map's own size as exported (`ownGrid`), whether the rail's Map grid is on (`gridTool`; `setGridToolValue`,
    beside the map grid's `setGridTool`, which also draws) and a handle's drag (`gridDrag`), which app.js's scene start
    and pointer handlers, the keys and the test hooks read or set;
  - the install's landing lines for the map (`landingLines`), the starting zones worked out from them
    (`startingCache`), the last clear's time (`lastClearMs`) and the landing zone's pieces as the server's families name
    them (`landingActors`), which app.js's scene start, its map families and the test hooks read or set;
  - what the tile grid was drawn round (`tileKey`) and the Floor tiles overlay (`floorTileLayer`), which app.js's View
    options, draw loop and test hooks read or set;
  - what is wrong with the open map's export for lights and builds (`exportProblem`), which app.js's scene start sets
    and Prepare reads.

  A value such state takes from the browser's storage as the page loads is given by its setter's call where the `let`
  was (`setAreaShown(recall(AREA_SHOWN) === '1')`, `setLikenessOn(...)` inside the Effects view's factory), so it is
  read at the same point as before. A setter whose write sat inside an expression gives back what it set
  (`setWavePlayer`: `player = setWavePlayer({ ... })`). A logical assignment becomes the same test with the setter's
  call: `lineCollision ??= new Map()` is `lineCollision ?? setLineCollision(new Map())`, which sets it only when it is
  null, as before.

  app.js still declares the state of the areas not yet moved out of it; new state never goes there. An assignment to
  an imported name throws only when its line runs, and no browser check runs every line: a change that moves state
  searches for any assignment to the moved names left behind.
- A module made from many of app.js's functions (`createDocumentSession`, `createDocumentState`, `createBuildPlay`,
  `createBuilderSession`, `createPrefabPlace`, `createLightsWiring`, `createEffectsWiring`, `createSpawnsWiring`,
  `createZonesWiring`, `createBuildingsWiring`, `createMadeHandles`, `createMadeLooksWiring`, `createMadeDrawing`,
  `createMadePanel`, `createMadeBreaking`, `createCoverWiring`, `createFlagsPanel`, `createSelectKind`, `createGroups`,
  `createAlign`, `createLibraryTemplates`, `createClipboard`, `createMapGrid`, `createClearMap`, `createScenePieces`,
  `createCutaway`, `createFloorListings`, `createLevelSnap`, `createDeleteReset`, `createPrepare`, `createSelection`,
  `createNavigation`, `createTestApi`, `createPopups`, `createMapMenu`, `createLoading`) takes them as one
  argument object and destructures it, so the code moved into it calls them by the names it always did. It returns the
  functions other areas call, and app.js destructures them under the same names, so their callers stay as they were.
  app.js makes it after the functions and objects it is given, and before any code that runs as the page
  loads and uses what it returns (a dialog handed `loadProject`). A function app.js makes further down, a `const`, is
  given as a function that calls it, since it is not made yet: `openingProgress: name => openingProgress(name)`.
  That holds for what another factory returns too: the document session is made before Build and Play, which is given
  its `banner` and `saveProject`, so the session is given `followBuild: (status, id) => followBuild(status, id)`.
  What runs as the page loads (a button's handler set, a key listener added, a dialog made) moves into the factory
  with its functions and runs when the factory is made. app.js makes the factory where that code was, so the page
  sets things up in the order it did: the order of listeners on one target is the order they are called in. A factory
  given a value app.js makes further down that is not a function (a constant, as the page session's `SESSION`, or one
  another factory returns, as box select's `PICK_SLACK`, which Select all of a kind reads) is made after it instead,
  and what it sets up runs that much later: a change that moves it so checks that no other code sets a handler on, or
  listens to, the same targets in between, and that what it makes later is drawn as before (the clipboard, made after
  the cover blocks and the Buildings view for their floor clearance and own buildings' layer, makes its preview's
  materials later: see-through materials, which three.js sorts by render order and depth, consulting the order
  materials were made only for opaque ones; the preview's meshes are made when placing starts, as before). The prefab
  builder's session and prefabs saved and placed are made so, after the document session; they call each other (the
  builder's save opens the Save as prefab dialog, whose Save saves the builder), so the first made is given the
  second's functions as functions that call them.
  When part of an area's run of code stays in app.js (a helper other areas use, as `projector`, `gameToView` or
  `alongLine`; a constant of app.js's event wiring; a pointer listener that is app.js's pointer handlers', as the Map
  grid's, which write its `pointerStart`; a function that reads a value app.js makes further down that is not a
  function, as `grabView` (the Effects view's likeness layer) and `previewGroup` (the clipboard's ghost material)),
  app.js keeps those declarations where they were and makes the factory after them, where the run ended: what the run
  does as the page loads then still happens at the same point among the page's other code. An object a view makes as
  the page loads that a view made before it also uses (the landing zones' layer, which the Spawns view shows too; the
  floor boxes' outline of a clip, which prefabs saved and placed draw too; the group chip, which the groups and the
  selection, made later, put in the piece panel) stays in app.js where it was made, and both are given it. A function
  of the area that an earlier stage left elsewhere in app.js (the Landing zones view's `setZonesShown`) moves into
  the factory with the run: a function declaration runs nothing as the page loads. So does a short run of the
  area's elsewhere that only declares (functions, and constants holding functions or plain values: Clear map's rule of
  the landing pieces and its header's Mission picker), on either side of the area's main run.
  An area whose code was two runs
  with other code between (the Buildings view's, box select's after the made pieces') is made where the first run
  was, so what the second run did as the page loads (the panel's handlers, box select's layer) now happens there,
  earlier: a change that does so checks that no code between sets a handler on, or listens to, the same targets, and
  that what moves earlier makes only objects three.js draws by render order and depth (it consults the order objects
  were made only where both are equal), so nothing is drawn differently. When the first run needs a value app.js
  makes between the runs that is not a function (the cover blocks' run reads the handles' pick distance, `HANDLE_PICK`,
  and the meshes' caches), the area is made where its last run was instead, and what the first run did as the page
  loads now happens there, later: a change that does so checks that the first run only made values there (no handler
  set, nothing added to the scene; the cover blocks' collision material, made later, is never drawn), and gives the
  factories made between that read its functions as the page loads functions that call them. An area whose last run
  sets listeners whose order with others' matters (the camera's and the editor's keys: listeners on the document and
  the canvas, which other modules' factories add to as they are made) is made where that run was too, so those
  listeners keep their place: navigation's earlier runs (the gizmo buttons' handlers, which no other code sets, and
  the edit hub's `tools` refresh, registered before any run of the hub, none of which happens while app.js loads) come
  there, later; a constant of it that a factory made earlier is given (`RECIPE_NOTE`) is a plain export at its
  module's top. An area that is several
  modules (the made
  pieces: their base, `made_handles.js`, then their looks, drawing, panel sections and Break) has each made where its
  own first run was, so in the order of its code; each is given the functions of those made before it directly, and
  those of the ones made after it as functions that call them. A function app.js keeps in a `let` (`applyLighting`,
  set by `startScene`) is given as a function that calls it. The event wiring (a panel's field handlers set further down, the
  pointer handlers, the draw loop) stays in app.js and calls what the factory returns; the state it reads of the area
  is editor_state.js's.
  An area whose code makes nothing the page shows or listens with as it loads (it declares functions, and at most
  makes plain values: a table, a vector) does nothing that its place could change, so app.js makes it where the fewest
  functions must be called through: the scene's pieces before the gizmo, the first code given their functions; Delete
  and Reset after Break and Repair, the last factory whose functions they call; the selection after the Buildings
  view, the last factory whose functions it calls, so the eight factories made before it that are given `select`
  (and the two given `gridNow`) are given functions that call them; the loading overlay as soon as the words it takes
  are made, so that only the scene's pieces, made before, are given `loadingState` as a function that calls it. What is
  made on the other side of it is given its functions, or gives it theirs, as functions that call them.
  An area whose run sets a handler or a listener as the page loads may be made earlier than the run, before the
  factories given its functions, when no code between sets a handler on, or listens to, the same targets: the
  header's menus are made before the Lights view, the first area given `showPop` (their buttons' handlers and the
  document's press that closes a menu are set then; no other code listens to a press on the document, and the one
  button given a handler of its own later, the Map menu's, still gets it later, from the map menu), and the map menu
  where `mapLabel` was, its first run (the Map menu's button and Change map are given their handlers there).
  `moved_code.py` reads the functions a factory declares (`createX.f`) and finds them by their own names.
- An added thing's record is written only through `piece_records.js`'s `recordOf` and read only through its
  `optionsOf`. A writer gathers what it knows of the thing (a unit: its names, source, components, pose, links,
  state, recipe, a cover block's, a light's or an effect's own fields) and hands it to `recordOf`, which gives the
  fields in the one order every writer has always written. The saved files' bytes and a project's saved key
  (`stateKey`, which compares records as text) follow that order, so it changes only on purpose. A reader hands the
  record to `optionsOf` and makes the root from what it gives. Where the writers differ, the difference is the unit's (a prefab's records have no `id`) or the path's
  (`recordOf(unit, 'prefab')` puts a recipe light's values before its pose). The three writers and the readers were
  recorded on every kind of piece when they moved onto these, and those records are the node test's cases
  (`piece_record_cases.json`).
- A panel registers its refresh with the edit hub ([`edit_hub.js`](tools/viewer/web/edit_hub.js)); it is not called by
  name from another area. After an edit, an undo or a selection, the hub's `edit` run calls each area's refresh (its
  panel or section, a button's state, a mark in the view) in the order its `RUNS` lists them, the order the page has
  always called them in, whatever order the modules are made in; so an area's module can be made anywhere, and a new
  refresh is a name put in `RUNS` where it must be called and one `onHub(run, name, refresh)` in its module's factory.
  A refresh that returns `STOP` ends its run, and those after it wait for the next (the selection followed the gizmo
  and ran the hub itself; a box can't be turned; the cutaway's select ran it). A refresh that needs what another
  worked out in the same run is one refresh with it (app.js's `piece-status`: the pose fields and the edit status share
  the pose and the count of changes). Where another area's refresh must be called in the middle of one, it is a run
  of its own that the one runs: `drag`, the lights following a gizmo handle held, between the pose fields and the end
  of the edit's run; and `select` (selection.js) runs one at each place it fills the piece panel for what is picked
  (`select-sections`: each area's section shown or hidden; `select-none`, `select-light`, `select-cover`,
  `select-piece`: the Effects view's, a light's, a cover piece's and a made or breakable piece's panels;
  `select-chips`: the flags chip), given what it has there (the root picked, its source, the chips' row). The hub is
  its own module, not editor_state.js, so that its node test can import it.
- As a map or a prefab opens, app.js's `startScene` calls each area's part of the scene in the order the page always
  started them, and does little else. A part keeps its place in that order when it moves into its area's module, and
  is given what `startScene` worked out before it (the streamed objects, the families' answer, the server's map list)
  as its parameters, so that its statements move as they were.
- A module's top level only declares, so the order of imports means nothing. No module imports app.js.
- A rule, a record or a sentence is in a pure module with a node test. The wiring of a panel is beside it and has a
  browser check in the table of checks. A hook a browser check uses is on `window.viewer`: it is made in
  `test_api.js` from the modules' exports (the shared state and the pure modules' functions imported, a live binding
  each; what app.js's factories return given as one argument object), and its name is in the recorded list
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
  damaged or modded package then fails in one place with a reason. A writer goes through `write_edited` and reads
  back what it wrote (finding 52).
- Tagged properties are walked by `props.tags` (`props.read_tags` for a list) and by nothing else in what ships: a
  walker keeps only what it does with each property (its values, its rules), and a module whose callers catch an
  error of its own turns the walk's `ValueError` into that error (the viewer's `FormatError`, `pack_card`'s
  `CardError`, `typed_props`' `WalkError`). About sixteen walks once read the bytes each its own way, some with no
  bounds checked (finding 52). The research tools that do not ship keep walks of their own. In the same way a mesh
  component's LOD records and a bulk record have one reader, `native_fields`' (`mesh_lods`, `lod_record`,
  `lightmap_record`, `bulk_record`), which gives each value with its place; a module that needs another form of
  them makes it from that reader's record, and keeps any check of its own beside it (`lighting_records.bulk_meta`
  refuses a negative count). The three readers it replaced wrote Enemy Within's licensee branch three ways.
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

About 1,500 lines a file and 150 a function are guideline sizes, not limits: no test fails on them. A larger file or
function is fine when it has a reason, such as a table, a format read whole, a test file of many cases, or a run that
reads best in one piece. The same goes for app.js's module-level state and top-level functions: new ones belong in the
module that owns their area, but nothing counts them for you.

`python -B tools/repo/tests/test_structure.py --sizes` lists what is over the guideline sizes, largest first, and
app.js's counts of `let`s and top-level functions; the two numbers are `guideline sizes` in
[`tools/repo/structure.json`](tools/repo/structure.json). It measures:
- Python's functions and methods by their syntax tree, from `def` to their last line, with their nested functions;
- the page's top-level functions by their text;
- a page module made as a factory (`createX`, which declares its functions inside and returns them, as
  `createProjectDialog` does) by each function it declares, since a factory is a module made as a closure;
- functions only in what the release ships (the modules and page files `tools/release/make_release.py` lists), and
  files among every tracked Python file and page module.

The largest today are what the refactor is taking apart: app.js (every area of the page was added to it before the
page had modules), the compiler, the copy tool's `build`, and the browser checks in one file.

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
look's measurer by name. The test does not hold `paths.use()` calls: fourteen shipped ones are still inside
functions, left from the review's import work (a folder already on the path is left where it is, so they are
harmless). New code calls `paths.use()` at the top of its module, as section 3 says.

### Compiler families

A module listed under `compiler families` does not import the compiler. It lists the families in modules of their own
(section 1), `spawn_edits.py`, `effect_edits.py`, `light_edits.py`, `flag_edits.py`, `made_edits.py`,
`building_edits.py`, `mission_edits.py`, `group_edits.py` and `floor_edits.py`, each of which takes the tables and
helpers it shares with the compiler from `compiler_tables.py`. The other modules split off the compiler are listed
too, since none may import it either: `compiler_tables.py`, `native_edit.py` and `piece_lookup.py`. A family or module
moved out of the compiler is listed in the commit that moves it.

### structure.json's form

`structure.json` is sorted, with one entry a line (two-space indent, as `json.dumps(..., indent=2, sort_keys=True)`
writes it). Changes to different entries then merge without a conflict.

## 5. Changing the structure

Move, then change. A move changes nothing else: the moved code is the old code, and a step's stated substitutions
(`self.` to `self.c.`, say) are the only differences. A behaviour change found on the way is a commit of its own with
its own ledger entry. A function that cannot move without a change of behaviour stays where it is.

The tools that show a move changed nothing:
- [`tools/repo/moved_code.py`](tools/repo/moved_code.py) `<base commit> <old file> <new file> [--subst OLD=NEW ...]
  [--subst-file <json>] [--names ...]`: each moved Python function's syntax tree, or JavaScript function's tokens (a
  page factory's functions included, as `createX.f`), is
  the old one's, after the move's stated substitutions (`--subst-file` holds [OLD, NEW] pairs, for a write moved to its
  owner's setter). Use it for every move.
- `tools/editor/tests/build_outputs.py`: the quick and baked Builds of ten project inputs that hold every lane of the
  native edit, compared byte for byte. Record on the commit the change starts from (in a scratch worktree of that
  commit), record on the change, and compare. Use it for a change to the compiler, the Build, the copy tool, the
  package tools or the relight.
- `tools/editor/tests/compile_record.py`: every compile the editor suite makes (spec, report and native edit),
  recorded and compared. Use it for a change to the compiler.
- `web_names` in `tools/viewer/tests`: no name in the page's modules left undefined, no import left unused, and no
  assignment to an imported name (a write that must go through its owner's setter). A moved function's missing import,
  or such a write, throws only when its line runs. Use it for a change to the page.
- The `api-names` browser check (`browser_smoke.py`, against `tools/viewer/tests/viewer_api_names.json`):
  `window.viewer`'s names unchanged. Use it for a change to the page.
- `python -B tools/run_tests.py <suite> --times`: the slowest tests and classes. Use it before and after making a
  suite faster.

A change that sets a pattern writes it into this document: its section, and its row in section 2.

## 6. A checklist for a change

Before a commit that adds a module, a function longer than a screen, or a reader or writer of a format:

1. Does one exist already (section 3, "One home")?
2. Does it go where section 2 says? If the table has no row, add the module and the row.
3. Is its pure part apart from its wiring, and tested?
4. Is the same rule needed on the other side, the page or Python? Then one file both read, or a case file.
5. Did it make a file or a function grow well past the guideline sizes (section 4)? Then see whether the new code
   is a module or a function of its own.
