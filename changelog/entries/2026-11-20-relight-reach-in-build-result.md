### The build result says when the relight's writes changed pieces it didn't relight; its left-out count agrees with itself

Review finding 15, and from finding 34 the build results' left-out list.

- **Texels changed in pieces not relit.** The baker records `otherPiecesChanged` (its writes re-encode whole 4-texel
  blocks, which can reach into a neighbour's lightmap) and prints a warning, which a successful build's short log
  scrolled away. [build.py](../../tools/editor/build.py) `other_pieces_changed` carries it into the light stage as a
  record of its own (`texels`, `largest`, `count`, the first 20 `pieces`, `textures`), by both command lines
  (native_copy.py `--bake` and relight.py alone), so it reaches the manifest's stages too. The build window
  ([app.js](../../tools/viewer/web/app.js), its results only) says it on the light step and, once built, under the
  package with the first pieces by name.
- **The warning parser finds an indented warning.** [builds.py](../../tools/viewer/builds.py) took only a `warning:`
  at a line's start, and build.py echoes a tool's lines indented, so the relight's never reached the job's
  `warnings` (which the build queue's results keep). It now takes one after leading spaces.
- **Left-out count.** The build window read `compiled.leftOut` without `?.`, and its "… and N more" line counted the
  compiler's left-out pieces only, while the heading added the Build's own (its `leftout` stage); both now use one
  count, and the line says how many beyond those shown.
- Checked: [test_build.py](../../tools/editor/tests/test_build.py) gives the relight record collateral changes on both
  command lines and a clean one; [test_builds.py](../../tools/viewer/tests/test_builds.py) feeds the parser a warning
  at a line's start, an indented one, and a line with the word in its middle. `node --check` on app.js. Not seen in a
  rendered page: no test build here has a relight that reaches another piece.
