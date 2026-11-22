### No build, pack or install ships a texture cache: every map holds its baked lighting inside it

Builds have put their baked lightmaps inside the map since 19 November 2026, but three places still let a `.tfc`
through. All three are gone, so every map is built and shipped the same way.

- **The Build** ([build.py](../../tools/editor/build.py) `lighting_inside`): a map whose lightmaps can't be put
  inside it used to ship its `<Map>_Lighting.tfc` beside it, with a note. Now that fails the build, saying why, and
  the last good package stays. The relight still writes its cache in the build's work folder, and the cache is moved
  into the map there. The manifest's `cache` is always None, and the README no longer has a "lightmaps in a .tfc"
  case. A build's cache name is no longer an output name: [outputnames.py](../../tools/viewer/outputnames.py) claims
  `<map>_Lighting` for no project, and a file of that name stops no build.
- **The map pack** ([manager.py](../../tools/viewer/manager.py)): the export no longer converts an older build's cache
  into its map (`_inline_lighting`), and no longer puts a cache beside the pack's folder. `pack.json` loses
  `cacheFiles`, and the READMEs and the [pack scripts](../../tools/viewer/pack_scripts.py) lose their cache lines.
  Every file of a pack is in its folder.
- **The installs** ([installs.py](../../tools/viewer/installs.py) `read_package`): a package whose files include a
  `.tfc` (a build from before 19 November 2026) is refused by Play in game, Install in the game and the map pack:
  "has its lighting in a texture cache beside the map ... build the project again". The project manager's list warns
  about such a build. The play's cache guard and [play_names.py](../../tools/viewer/play_names.py)' branch for files
  that keep their names are gone, since every file of a package is now a map package. A cache an earlier install put
  in the game is still the editor's, and Remove from game takes it out.

The lab's [pack_test.py](../../tools/lab/pack_test.py) no longer copies caches beside a pack's folder. Its `take`
still removes the ones an older note lists. The game's own shared caches (`Lighting.tfc` and the like), which the
game's maps and the lightmaps a build leaves as they were read, stay where the game keeps them.

Checked: the play, play-name, manager, pack export, output-name and build tests rewritten for it (a package with a
`.tfc` refused for a play, a campaign install and a pack, with the warning in the list; a map that can't take its
lightmaps in fails its build and leaves the last package), and the viewer, editor, lab, repo, release and node suites.

Known gaps: a project whose last build is from before 19 November 2026 has to be built again before it can be played,
installed or packed. The lab's bake-fixture tools still write caches for their own fixtures.
