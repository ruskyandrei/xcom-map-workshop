### The Game look lights the pieces as the last baked Build made them from that Build's lightmaps

Stage B4 of the game-likeness plan, its second half. A baked Build relights the map: the pieces it makes as new
actors get lightmaps of their own, and the map's pieces near its changes get new ones. Before, the editor drew the
map's own lightmaps and lit every edited piece live, built or not. Now, with a project open whose last Build was
baked, each piece that is as that Build made it is lit by the Build's own lightmaps.

**The manifest** of a baked Build (not quick, its lighting changed) gains:
- `builtActors`: each project piece the Build made as a new actor (a moved original by its actor, an added piece by
  its output name) to the built actor; a made piece cut into parts to its parts, in order. They come from the copy
  tool's record of its copies, by each copy's label.
- `relitComponents`: the components whose lightmap or sun shadow map the relight wrote.
- `asBuilt`: the project as the Build read it.

A quick Build's manifest, and a baked one whose lighting is unchanged, are as before.

**The server** exports a Build's light into the cache the first time the page asks for it (GET
`/projects/<id>/build-light.json`), under the Build's ID: the baked light of every mesh component of each built actor
and every relit component, read with export 45's reader on the built package, and the atlases they name. Its files
are served from `/cache-builds/<buildId>/`. A newer Build of the same variant takes the older one's folder away. The
textures a Build did not write are read from the game install's maps, where the base map's caches are (F-190).

**The page**, once the Game look has been on, asks for the light of the open project's last Build where it has one,
and packs its atlases with the map's. A relit atlas keeps the map's texture's name, so it takes the map's atlas's
place. Then, after each edit:
- A piece is as built where its record now is the one it had as built (its flags, prefab and partner aside).
- One of the map's pieces as built is lit by its own lightmap, the Build's where the Build relit it. A moved original
  as built is lit by its copy's, an added piece by the Build's piece made for it.
- A piece changed since is lit live, as are the pieces a light changed since reaches: its bake's pieces for one of the
  map's, and those its sphere meets now and as built. Such a light is drawn live on the pieces as built; every other
  static light is in their lightmaps.
- Made pieces (drawn whole from their numbers) and cover blocks stay live.

View options says it under the look: "Lit by the Build of 27/11/2026, 15:23 · 1 piece changed since".

- Where: [build.py](../../tools/editor/build.py) (`built_actors`, `relit_components`, the three fields),
  [build_light.py](../../tools/viewer/build_light.py) (new), [builds.py](../../tools/viewer/builds.py)
  (`BuildRunner.light`, the package summary's `light`), [viewer.py](../../tools/viewer/viewer.py) (the route,
  `/cache-builds/`), [package.py](../../tools/viewer/package.py) and [texture.py](../../tools/viewer/texture.py) (a
  package told the folder its texture caches are in), [build_light_rules.js](../../tools/viewer/web/build_light_rules.js)
  (new, pure), [build_light.js](../../tools/viewer/web/build_light.js) (new, `createBuildLight`),
  [baked_light.js](../../tools/viewer/web/baked_light.js) (`setBuild`, the Build's atlases and geometries, marks 5 to
  7, one fetch from the first place that answers), [lighting.js](../../tools/viewer/web/lighting.js) (`BAKED_BUILD`, a
  light's flag for the Build's lightmaps), [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) (`sinceBuild`,
  `reachedPieces`), [editor_state.js](../../tools/viewer/web/editor_state.js) (`lightsSinceBuild`),
  [build_play.js](../../tools/viewer/web/build_play.js) (the baked light follows the build status),
  [project.js](../../tools/viewer/web/project.js) (`api.buildLight`), [app.js](../../tools/viewer/web/app.js),
  [index.html](../../tools/viewer/web/index.html) (View options' line),
  [editor-contracts.md](../../research/editor-contracts.md) section 11, [ARCHITECTURE.md](../../ARCHITECTURE.md)
  (section 1, two rows, the plain fetches), [findings-register.md](../../research/findings-register.md) F-190.
- Checked:
  - [test_build.py](../../tools/editor/tests/test_build.py): a baked Build names a moved original's copy, an added
    piece's and a cut made piece's parts, leaves out a copy the project names nothing for, lists the relit components
    without a skipped shadow map, and keeps the project; a quick Build and one with its lighting unchanged have none
    of the three.
  - [build_outputs.py](../../tools/editor/tests/build_outputs.py) recorded before and after on its 12 inputs: every
    package file, quick manifest and record the same; the baked manifests differ by the three fields alone. Its
    `record` now fails when a baked Build's `builtActors` leaves out one of its copies (`unnamed_copies`,
    [test_record_tools.py](../../tools/editor/tests/test_record_tools.py)); on the 9 inputs whose baked Build has
    the map, it names all 68 copies. A whole `record` refuses on the base already (the lanes `kismetCuts` and
    `streamHides` are in no input), so both were recorded with every input named.
  - [test_build_light.py](../../tools/viewer/tests/test_build_light.py) (new): which manifests have a light of their
    own; the components read; the export written once, the variant's older Builds pruned; a package reading its
    caches from the folder it is told; the route on a made-up Build whose one added piece has a lightmap (its record
    by its built component, the actors, the project as built, its atlas served; nothing outside a Build's folder; 404
    for a quick Build and a project never built).
  - [build_light_rules_test.mjs](../../tools/viewer/tests/build_light_rules_test.mjs) (new): records by key, the
    same record within a thousandth with flags aside, what changed since, built components, a light's place as
    built, the line's words.
  - [browser_build_light.py](../../tools/viewer/tests/browser_build_light.py) (new, `build-light` in
    [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) on URB_Bar of export 45: a made-up Build of a
    saved copy, answered in the page's routes: nothing asked before the Game look; the copy marked 5 to 7 with its
    own record, the map's pieces as built 5 to 7, 1,040 lit by the Build; the line; the copy moved lit live with one
    piece changed since, back after Undo; a static light changed lights its bake's pieces live and carries
    `sinceBuild` until Undo; no error. `map-lights`, `lights`, `typed-pose` and `api-names` pass as before.
  - End to end on a test server: a real baked Build of that project (the install only read; 92 s, the copy built as
    `StaticMeshActor_312`, 436 components relit) exported by the route in 1.0 s (436 records, 44 atlases, 15 MB, no
    diagnostics; 0.03 s asked again); the page lit 1,040 pieces by it, 434 with the Build's own records, the copy
    marked 6 and live once moved. Read only, a Build made before 19 November read the same way (23 relit, 2 copies).
  - perf_probe.py on URB_Bar from track H's ub-1 camera, 40 frames a figure, the page as it was and as it is (no
    project open), two runs each; and a Game look frame timed the same way with the real Build's light in use:

    | Frame (ms) | Before | After |
    | --- | --- | --- |
    | Neutral, no shadow pass | 5.3, 5.2 | 5.4, 5.3 |
    | Game, lights live | 6.5, 6.6 | 6.4, 6.5 |
    | Game, baked light | 6.5, 6.5 | 6.4, 6.7 |
    | Game, baked light, the Build's in use | | 6.8, 6.4, 6.5 (6.8, 6.5, 6.3 without) |

    (The computer was busier than for B2's 4.9 ms; the rows are each other's measure.)
  - `viewer`, `editor`, `repo`, `node` and `release` suites pass; `web_names.py` finds nothing new (one unused import
    in clear_map.js is older).
- Known gaps:
  - Made pieces stay live: the page draws one whole from its numbers, the Build may cut it into parts, and whether
    the page's mesh carries the Build's lightmap UVs is not checked.
  - The pieces a change since darkens or lights (a piece moved away leaving its shadow on a neighbour) keep the
    Build's texels; only the changed piece and the lights changed since are lit live.
  - A Build's light is read with the game install's maps; without them a relit piece's texture the Build did not
    write is left out (F-190).
