### A made piece's texture mapping in the editor: the Texture mapping fold and its handles on the surface (design B)

The custom geometry improvements plan's stage 4, the editor page's side, as the design chosen (B, its section 10.6).

- **The fold.** The Wall, Floor and Ground sections show a Texture mapping fold after their Look row, its value on
  the shut line ("faces: size 64, 30°"). It holds one surface's mapping: Original, Size, Fit or Count, its repeat (U,
  V), offset (U, V) and turn, Flip U, Flip V, Aligned to the world, and Reset surface. Size first takes the look's
  repeat (a slab's catalogue entry's measured repeat, a ground look's own, else 192), Count and Fit 1 by 1; Original
  and Reset surface take the surface's entry out, and the mapping when none is left. Each change is one undo step, and
  an older piece goes into the free form first, as a size edit puts it.
  [made_mapping_wiring.js](../../tools/viewer/web/made_mapping_wiring.js) (`createMadeMapping`, `texturePanel`, which
  [made_panel.js](../../tools/viewer/web/made_panel.js)'s sections call), [index.html](../../tools/viewer/web/index.html),
  [style.css](../../tools/viewer/web/style.css).
- **The surface and its handles.** While the fold is open, a click on the picked piece picks the surface its normal
  falls on (a wall's faces, one surface on both; a slab's top or underside; a ground shape's top or sides), Tab the
  next (navigation.js); the surface is outlined in the accent colour and the piece's size handles step aside
  ([made_handles.js](../../tools/viewer/web/made_handles.js) reads editor_state.js's `texturePicked`). On it a blue
  dot at the pattern's corner slides the pattern (its offsets), a ring round the dot turns it about the dot, and a
  white dot a repeat along u (further out when one repeat is too near on the screen) sizes a repeat, v in
  proportion; in the snap setting's steps (a slide and a size on the surface, across and up on a face; a turn in its
  angular step; smooth with snap off), each drag one undo step, Esc putting it back, its hint in the hint line. A
  ground shape's sides take the fields alone. The ring follows the pointer seen from either side of a surface.
- **The rule's twin and the drags.** [made_mapping.js](../../tools/viewer/web/made_mapping.js) holds what is pure:
  each kind's surfaces, a surface from a normal, a surface's plane and extent, its mapping read and written, a mode's
  defaults, the words, `uv` (tools/bake/uv_mapping.py's twin in its new order: turned, scaled along the turned axes,
  mirrored, slid) and its inverse, a drag's new values (`slidMapping`, `turnedMapping`, `sizedMapping`) and
  `reframed`, the offsets Pivot to corner now takes from it ([made_free.js](../../tools/viewer/web/made_free.js)
  `pivotedToCorner`: flips · S · R(turn) · the shift on each axis tiled by size; a ground shape's sides and a
  world-aligned surface keep theirs). Node test
  [made_mapping_test.mjs](../../tools/viewer/tests/made_mapping_test.mjs), on test_uv_mapping.py's numbers.
- **World alignment.** A surface with `world` sends where the piece stands: `mappingOrigin` {role: [a0, b0]} (a
  wall's faces: along the piece's x and z; a top or underside: along its x and y) or, for a ground shape's sides,
  [x, y, z], from its location and its yaw's rounded step. The page puts it in the mesh's request
  (made_free.js `freeNumbers` with the pose; a piece moved, turned, pasted or undone is drawn again from where it
  stands, made_handles.js's `textures` refresh in the edit hub's edit and scene runs), the compiler in the Build's
  request ([made_edits.py](../../tools/editor/made_edits.py) `mapping_origin`, from the record's pose; `free_valid`
  takes one a record carries as `uv_mapping.check_origin` does and the lowering works it out again). The same rule
  both sides, with the cases both tests read: [mapping_origin_cases.json](../../tools/editor/tests/mapping_origin_cases.json)
  ([shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs),
  [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py)). The contract:
  [editor-contracts.md](../../research/editor-contracts.md).
- **Words and checks.** [UI-GUIDELINES.md](../../UI-GUIDELINES.md) section 1 holds the pattern; the help panel a line;
  [ARCHITECTURE.md](../../ARCHITECTURE.md) section 2 a row; test hooks `texturePicked`, `textureDragging`,
  `textureHandles`, `textureSurfaceAt` ([test_api.js](../../tools/viewer/web/test_api.js)), and `wallHandles` gives
  none while the fold is open. Browser check `texture-mapping`
  ([browser_walls.py](../../tools/viewer/tests/browser_walls.py)): the fold on a made wall, a face picked by Tab and
  by a click, Size, the dot slid a tile under tile snap, Esc during a drag, the white dot under tile snap and smoothly
  with snap off, the ring under fine snap about its corner, the fields, Aligned to the world (the mesh's key carries
  `mappingOrigin`), Original and Reset surface; a floor's top and underside picked by clicking them, Tab back.

Checked: the node (39 files), viewer (673 tests), editor (393) and repo (44) suites; web_names.py clean; on a test
server the browser checks api-names, walls (with its quick Build), looks, made-openings, free-handles and
texture-mapping, the last five times more on its own (one early run read the picked surface before the fold's toggle
event had come; the check now waits for it); the fold read at 1600, 1280, 1024 and 800 wide. The bake suite was not
run (nothing of tools/bake changed), nor build_outputs.py: the lowering changes only for a surface aligned to the
world, which none of its inputs has. Not checked: a mapping in the game (the plan's run, under baked light); how a
measured look that cannot tile shows a mapping (section 5, item 2: the catalogue says nothing of it yet).
