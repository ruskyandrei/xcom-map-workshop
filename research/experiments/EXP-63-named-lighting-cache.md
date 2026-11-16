# EXP-63: the lighting file named after the map

Date: 16 November 2026. Status: **prepared, not run**. The output names plan's game check (stage N4): since this
date a build writes its baked lighting to `<Map>_Lighting.tfc`, a name the Build adds to the map's name table, which
the relit textures store as a plain name (number 0). EXP-17 showed the game reads a variant's own texture cache when
its name was `Lighting_<n>` (the shared `Lighting` name, numbered); it never showed a name added to the table, nor two
variants with caches of their own in one install. This run adds only that.

## What is known offline

- A full build of a project with a lighting change writes `<Map>_Lighting.tfc` beside `<Map>.upk` and nothing named
  `Lighting_<n>` (test_build). The name goes into the map's table by the growing writer before the relight
  (native_copy.py; for a relight alone the Build's named copy, Build.named_base), and every texture the relight moves
  names it, read back by a fresh reader (test_transplant FreshLight, a real bake of URB_Bar; test_fixture: the map
  changes only at those textures' cache names and mip records). The textures it doesn't move keep `Lighting`.
- The relight's kept pieces don't depend on the cache's name; the textures' mips are written afresh into the new file
  on every build (lighting_fixture.finish), and checked after writing (Fixture.check).
- A rebuild of a project built before replaces its package, `Lighting_<n>.tfc` with `<Map>_Lighting.tfc`. In a game
  install, the old file stays (noted as the project's) until Remove from game takes everything out (test_play).

## The projects

[exp63_projects.py](../../tools/editor/examples/exp63_projects.py) saves two projects of URB_Bar in the editor's
project store and, with `--build`, builds both with the lighting baked into the editor's builds folder:

| Project | Builds as | Its cache | The edit (as EXP-17) | What shows a cache read wrongly |
| --- | --- | --- | --- | --- |
| Output Names Lighting Tests | `OutputNamesLightingTests` (24 characters) | `OutputNamesLightingTests_Lighting.tfc` (33) | the pool table and the glass on its edge deleted (run 9) | the table's shadow still on the floor, or black, smeared or missing lightmaps round it |
| EXP-63 second | `EXP63Second` | `EXP63Second_Lighting.tfc` | a copy of the claw machine under the ceiling spot at (-48, 1008) (run 11) | no shadow under the copy, or the first variant's lighting |

## The builds

Both built with the lighting baked on 16 November (URB_Bar's SHA-256 starts `a3ae5a73457c`), each through the Build's
name checks against the projects, the builds folder and the game install:
- `OutputNamesLightingTests-20261116-182454`: 6 pieces relit, 112 unchanged, the two pieces hidden; its files
  `OutputNamesLightingTests.upk`, `OutputNamesLightingTests_Lighting.tfc` and
  `CIN_DropshipIntros_OutputNamesLightingTests.upk`.
- `EXP63Second-20261116-182525`: 35 pieces relit, 158 unchanged, the claw machine made as `XComDestructibleActor_528`
  in the map; its files `EXP63Second.upk`, `EXP63Second_Lighting.tfc` and `CIN_DropshipIntros_EXP63Second.upk`.

## Run 1 (to do)

The user drives and looks (F9 shots), each variant in its own play (Play in game, with the project open; the build
must be of its saved revision):
1. **OutputNamesLightingTests:** the bar's pool table corner. Expected: no table, and no table shadow on the floor;
   the floor round it lit as the rest of the room, with no black or smeared patch. The pieces further away look as in
   URB_Bar.
2. **EXP63Second:** the open floor under the ceiling spot by the island counter. Expected: the claw machine copy with
   its shadow on the floor; the pool table where URB_Bar has it, with its shadow.
3. After each: the game's `Launch.log` has no line about a missing or unreadable texture file cache, and the files
   installed are the package's (the manifest's list: the map, its intro copy and its own `.tfc`).

Pass: both variants show their own baked light. A fail would point at the plain name (a cache the game doesn't find
by it) and would be a finding with the log lines.
