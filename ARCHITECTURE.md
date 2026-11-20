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
groups, the buildings and the cleared map's state) lives in [`editor_state.js`](tools/viewer/web/editor_state.js).
`window.viewer`, set in `startScene`, is the set of hooks the browser checks drive.

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
(which stop a Build), warnings, notes and the records left out. The `Compiler` class runs the checks and the edit
families. `FAMILIES` says which families build for every project. The families in modules of their own, each a class
the compiler makes for itself:
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
  clear, the drop-in rule, landing zones, missions and the places units are dropped at.

The tables and helpers that the compiler and its families share (`FAMILIES`, `short`, `tidy` and the others its
`__all__` names) are in [`compiler_tables.py`](tools/editor/compiler_tables.py). The compiler takes them all with
`from compiler_tables import *`, so `compiler.FAMILIES` is that module's object. `native_split(spec)` splits the spec
into what a patch would do (nothing, for every project the compiler accepts today) and the native edit.

**The native edit.** It is the dict `native_split` returns, the contract between the compiler and the Build. It is a
set of lanes: `copies`, `breakOriginals`, `hides`, `assemblies`, `covers`, `buildings`, `buildingEdits`, `lights`,
`effects`, `sounds`, `flares`, `spawns` and the others `native_split`'s docstring lists. The Build writes it as
`native-edit.json` in its work folder and hands it to the copy tool.

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

A quick build makes the same edit without the relight. It hands on the package folder
`<output>/<Variant>/`: `CookedPCConsole/<Variant>.upk` (with the intro and stream copies its records need),
`README.txt`, and `manifest.json`. The manifest holds the project's revision, the source map's hash, each file with
its hash, the config lines, each stage's result, and whether the build was quick.

**The copy tool.** [`tools/bake/native_copy.py`](tools/bake/native_copy.py) (`build`) makes the native edit in a copy
of the pristine base map, with the growing writer ([`tools/upk/package_grow.py`](tools/upk/package_grow.py)). Each copy
is a new actor with a fresh name and net indices. Its tiles are seeded under a rebuild volume. The hidden pieces are
taken out. Each other lane has a maker module that `build` calls: [`native_lights.py`](tools/bake/native_lights.py),
[`native_effects.py`](tools/bake/native_effects.py), [`native_sounds.py`](tools/bake/native_sounds.py),
[`native_flares.py`](tools/bake/native_flares.py), [`native_spawns.py`](tools/bake/native_spawns.py),
[`cover_blocks.py`](tools/bake/cover_blocks.py), [`buildings.py`](tools/bake/buildings.py) and the made pieces'
modules. With `--bake`, the copies get lighting of their own and the relight runs. It writes the variant map and a
fixture manifest.

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
| An area of the page (a panel, a view, a tool) | A module of its own in `tools/viewer/web`. When it needs many of app.js's functions, it is made by a factory that takes them as one argument object: `createProjectDialog` in [`project_files.js`](tools/viewer/web/project_files.js) and `createQueueController` in [`build_queue.js`](tools/viewer/web/build_queue.js) are the model. |
| State of the page (a module-level `let` or a collection) | The module of the one area that uses it. State several areas use: [`editor_state.js`](tools/viewer/web/editor_state.js), exported with its setter. Never app.js. |
| A rule, a record or a sentence of the page | A pure module (no three.js, no document), with a node test in `tools/viewer/tests/<module>_test.mjs`. Examples: [`piece_records.js`](tools/viewer/web/piece_records.js), [`light_rules.js`](tools/viewer/web/light_rules.js), [`spawn_rules.js`](tools/viewer/web/spawn_rules.js), [`poserule.js`](tools/viewer/web/poserule.js). |
| The game's grid numbers on the page | [`constants.js`](tools/viewer/web/constants.js). |
| A call to the server, from the page | [`api.js`](tools/viewer/web/api.js). |
| A route of the server | A `handle_<area>` method of `viewer.py`'s handler that hands the request to its area's module (`handle_play` and [`play.py`](tools/viewer/play.py) are the model). |
| Something a browser remembers | [`storage.js`](tools/viewer/web/storage.js). |
| A setting (a folder, an install) | [`settings.py`](tools/viewer/settings.py). |
| A record of the map's export | [`export.py`](tools/viewer/export.py) or [`scene_metadata.py`](tools/viewer/scene_metadata.py), with `EXPORT_VERSION` raised. |
| A field of the project document | [`projects.py`](tools/viewer/projects.py) and [`project.js`](tools/viewer/web/project.js), with the compiler's reading of it, and the contract in [`research/editor-contracts.md`](research/editor-contracts.md). |
| An edit family of the compiler | A class in a module of its own in `tools/editor`, made with the `Compiler` it works for (`self.c`), with its own tables and state. It takes what it shares with the compiler from [`compiler_tables.py`](tools/editor/compiler_tables.py), never imports the compiler, and reports through the compiler's `error`, `warn` and `note`. The compiler imports it at the top and names again the tables of it that others read through the compiler. The compiler holds it as an attribute named as its module (`self.effect_edits`), and reads the family's state through it (`self.effect_edits.ops`): the state has one home. A method of the family stays on the compiler only as a one-line forwarder, and only when a test or a tool calls it there by name (`Compiler.stage`). [`spawn_edits.py`](tools/editor/spawn_edits.py) is the model; section 1 lists the others. |
| A table or helper of the compiler that a family reads too | [`compiler_tables.py`](tools/editor/compiler_tables.py), named in its `__all__`. One only the compiler reads stays in `compiler.py`; one only a family reads goes in the family's module (the `SPAWN_*` tables in `spawn_edits.py`, the effects' in `effect_edits.py`, the `LIGHT_*` tables and `light_rule` in `light_edits.py`). |
| A lane of the native edit | One change across the compiler's spec, `native_split`, a maker module in `tools/bake` (as [`native_effects.py`](tools/bake/native_effects.py)) called from `native_copy.build`, and the Build. |
| A reader of package bytes | [`tools/upk`](tools/upk): tagged properties through [`props.tags`](tools/upk/props.py), compressed chunks through [`decomp.read_chunk`](tools/upk/decomp.py), a map's objects through the viewer's [`Package`](tools/viewer/package.py). |
| A writer of package bytes | [`package_edit.write_edited`](tools/upk/package_edit.py) for edits in place, [`package_grow.py`](tools/upk/package_grow.py) for new exports. |
| A line of the game's config | [`mapsini.py`](tools/viewer/mapsini.py). |
| A tool folder on the import path | [`paths.use()`](tools/paths.py), at the top of the module. |
| A browser check | The table of checks (`CHECKS`) in [`browser_smoke.py`](tools/viewer/tests/browser_smoke.py). |
| A test's shared records | Its suite's fixtures module: [`viewer_fixtures.py`](tools/viewer/tests/viewer_fixtures.py), [`tools/bake/tests/fixtures.py`](tools/bake/tests/fixtures.py). |
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
- A file stays under 1,500 lines and a function under 150. The ones over that today are listed (section 4) and may
  only shrink.
- A function with more than about eight parameters takes a record instead. `Build.__init__` took 22 and
  `native_copy.build` 30, and every caller had to name them all (findings 23 and 51).
- An object's state is made where the object is made, with a comment saying which step fills it. It is never made by
  first use through `getattr` with a default: such state is invisible until it breaks (finding 23).

### One home

- A rule, a constant or a reader of a format is written once. Before writing a reader, a walker or a writer, look for
  the one there is: `props.tags`, `decomp.read_chunk`, `package_edit.write_edited`, `mapsini`; on the page `api.js`,
  `storage.js`, `constants.js` and `piece_records.js`. Copies drift apart and each fails differently (findings 52, 55
  and 56).
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

  What one area alone uses lives in that area's module. What several areas use lives in
  [`editor_state.js`](tools/viewer/web/editor_state.js): the scene (`data`) and its roots, the selection, the project
  open, the groups, the buildings, the map's size, the cleared map's state and its landing zones, the project's
  missions, picture and spawn rules. app.js still declares the state of the areas not yet moved out of it; new state
  never goes there. An assignment to an imported name throws only when its line runs, and no browser check runs every
  line: a change that moves state searches for any assignment to the moved names left behind.
- A module's top level only declares, so the order of imports means nothing. No module imports app.js.
- A rule, a record or a sentence is in a pure module with a node test. The wiring of a panel is beside it and has a
  browser check in the table of checks. A hook a browser check uses is on `window.viewer`.
- The server is asked through `api.js`, the browser's storage through `storage.js`.

### The compiler and the Build

- An edit family is a class in a module of its own, with its tables and its state. It reports through the compiler's
  `error`, `warn` and `note`, so the report stays one report (`spawn_edits.py`). It takes the tables and helpers it
  shares with the compiler from `compiler_tables.py` and never imports the compiler, so a family can be read, tested
  and moved without the rest of the compiler (section 4).
- The native edit is the contract between the compiler and the Build. A new lane is added in one change to the
  compiler's spec, `native_split`, the copy tool and the Build.
- A reader of package bytes checks its bounds and refuses (a `ValueError` saying what it met). It never reads on: a
  damaged or modded package then fails in one place with a reason. A writer goes through `write_edited` and reads
  back what it wrote (finding 52).
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
- A suite's shared records are in its own fixtures module. A test that cannot run says why it skipped, and a
  selection that runs nothing fails. A test checks the code of the checkout it runs in.
- A refactor is checked by equal outputs (section 5). A change of behaviour is checked by a test that failed before it.

### Changing things

- Move, then change: never both in one commit.
- What a change leaves unused goes out with it. No parameter, option or branch for a case nobody has.
- Measure before making something faster, and write the numbers in the ledger entry.
- A comment says why, in words that stay true. It names no line number and no private plan.

## 4. The limits and the exceptions

[`tools/repo/tests/test_structure.py`](tools/repo/tests/test_structure.py) (the repo suite) holds these rules, with its
numbers in [`tools/repo/structure.json`](tools/repo/structure.json). Each failure names its rule and this section.

A listed exception has a ceiling at its size when it was listed. A ceiling follows its file down and never back up:
- over its ceiling, it fails;
- more than a twentieth under its ceiling, it fails until the ceiling is lowered to the new size;
- within the limit, or gone, it fails until its entry is taken out (or written under its new name).

A ceiling is lowered in the commit that shrinks its file. It is raised only with the user's word, said in the ledger
entry. The files are the ones Git has or would add, so a new file counts before it is committed.

`python -B tools/repo/tests/test_structure.py --root <folder>` checks another checkout, such as a scratch copy, and
prints its problems by rule.

### File size

A tracked Python file or page module (`tools/viewer/web/*.js`) over 1,500 lines must be listed under `file lines`.
Listed on 20 November 2026:

| File | Lines | Why it is over |
| --- | --- | --- |
| `tools/viewer/web/app.js` | 12,767 | The page's entry. Every area of the page was added to it before the page had modules. |
| `tools/viewer/tests/browser_smoke.py` | 5,856 | Every browser check and its table in one file. Not shipped. |
| `tools/editor/compiler.py` | 3,713 | The compiler, and all its edit families but five with their own tables. |
| `tools/editor/tests/test_compiler.py` | 3,263 | The compiler's tests, grown with it. Not shipped. |
| `tools/bake/native_copy.py` | 3,177 | The copy tool: every lane's joining and several lanes' own code. |
| `tools/bake/relight.py` | 2,045 | The relight, its scenes and its piece cache. |
| `tools/viewer/installs.py` | 2,035 | Every way into and out of an install: records, files, ledger, LWR's files. |
| `tools/editor/tests/test_build.py` | 1,890 | The Build's tests. Not shipped. |
| `tools/editor/build.py` | 1,759 | The Build's stages in one class. |
| `tools/bake/wall_measure.py` | 1,619 | The wall measurer, kept as it is so that saved walls keep their numbers. Not shipped. |

### Function size

A function over 150 lines in what the release ships (the modules and page files `tools/release/make_release.py`
lists) must be listed under `function lines`, as `<file>::<name>`.
- Python's functions and methods are measured by their syntax tree, from `def` to their last line, with their nested
  functions.
- The page's top-level functions are measured by their text.
- A page module made as a factory (`createX`, which declares its functions inside and returns them, as
  `createProjectDialog` does) is a module made as a closure. Each function it declares is measured
  (`createProjectDialog.render`), not the factory, whose size its file's limit holds.

Listed on 20 November 2026:

| Function | Lines | What it is |
| --- | --- | --- |
| `tools/bake/native_copy.py::build` | 544 | The copy tool's whole run, lane by lane. |
| `tools/viewer/web/app.js::startScene` | 303 | The page's start, with the `window.viewer` hooks the browser checks use. |
| `tools/bake/buildings.py::edit` | 210 | The map's own buildings changed or deleted, edited in place. |
| `tools/bake/native_copy.py::main` | 198 | The copy tool's command line. |
| `tools/bake/shell.py::equip` | 191 | The game's blank map given what a battle needs from another map, and a larger grid. |
| `tools/viewer/manager.py::_pack` | 188 | A map pack made: its config lines, its card and its zip. |
| `tools/viewer/effects_metadata.py::describe` | 169 | The export's records of a package's effects, sounds and lens flares. |
| `tools/editor/compiler.py::Compiler.groups` | 166 | The user's groups, those that break together linked in the map. |
| `tools/bake/transplant.py::stage_edit` | 154 | Pieces of other maps staged in a copy of the map. |
| `tools/bake/frac_walls.py::add_walls` | 153 | Made walls built as fracturing pieces in the map being grown. |

Six files and ten functions among what ships are exceptions. Measured whole, eleven of the page's factories would be
over 150 lines too (the largest, `createProjectManager`, 442), though no function inside any of them is over 74. That
is why a factory is measured by its functions.

### app.js's top level

`app.js` has a ceiling on its module-level `let`s (105) and on its top-level functions (811: function declarations and
functions assigned to a top-level `const`), under `app.js`. New state and new functions go into the module that owns
their area, so both counts only go down.

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
`building_edits.py` and `mission_edits.py`, each of which takes the tables and helpers it shares with the compiler
from `compiler_tables.py`. A family moved out of the `Compiler` class is listed in the commit that moves it.

### structure.json's form

`structure.json` is sorted, with one entry a line (two-space indent, as `json.dumps(..., indent=2, sort_keys=True)`
writes it). Changes to different entries then merge without a conflict.

## 5. Changing the structure

Move, then change. A move changes nothing else: the moved code is the old code, and a step's stated substitutions
(`self.` to `self.c.`, say) are the only differences. A behaviour change found on the way is a commit of its own with
its own ledger entry. A function that cannot move without a change of behaviour stays where it is.

The tools that show a move changed nothing:
- [`tools/repo/moved_code.py`](tools/repo/moved_code.py) `<base commit> <old file> <new file> [--subst OLD=NEW ...]
  [--subst-file <json>] [--names ...]`: each moved Python function's syntax tree, or JavaScript function's tokens, is
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

A change that shrinks a listed file or function lowers its ceiling in `structure.json` in the same commit. A change
that sets a pattern writes it into this document: its section, and its row in section 2.

## 6. A checklist for a change

Before a commit that adds a module, a function longer than a screen, or a reader or writer of a format:

1. Does one exist already (section 3, "One home")?
2. Does it go where section 2 says? If the table has no row, add the module and the row.
3. Is its pure part apart from its wiring, and tested?
4. Is the same rule needed on the other side, the page or Python? Then one file both read, or a case file.
5. Did a number of the structure test go up? Then the change is in the wrong place.
