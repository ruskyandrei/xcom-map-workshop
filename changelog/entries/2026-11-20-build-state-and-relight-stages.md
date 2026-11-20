### The Build's state, record and relight command apart; the relight's main in stages

Review finding 51, its first step: the two long functions split along the seams they had, their bodies moved as
they were.

- [native_copy.py](../../tools/bake/native_copy.py): a `BuildState` holds what the edit has taken out so far, and
  its `gone()` is the one answer the clear, the landings, the pieces' flags and the broken pieces read, in place of
  four sets built by hand with different members. The manifest's nativeCopies section (`manifest_parts`) and the
  relight's command line (`relight_command`, with the removed-casters and light-edits files it names) are plain
  functions of it, out of `build`.
- One change of behaviour comes with the one `gone()`: a project's landing moved in place now leaves alone a piece
  the edit's light deletes or its clear took out, as the clear, the flags and the broken pieces already did (before,
  it moved such a piece, which no longer stands in the level). No Build of the ten compared below has one.
- [relight.py](../../tools/bake/relight.py): `main` reads its arguments and calls the stages in turn:
  `edit_arguments` (the edit the command line gives), `edit_scenes` (the scenes before and after),
  `edit_receivers` (where the edit reaches, and the receivers it adds), `select_components` (what goes to the
  relight), `kept_pieces` (the last build's pieces kept), `run_pieces` (the workers, the results in the map's
  order, the shadow maps) and `write_record` (the lighting written and the record). Each takes what it reads and
  returns what the next ones need. The relight's piece cache is keyed on relight.py, so a project's kept pieces are
  relit once more after this change.

Checked: quick and baked Build outputs of ten real project inputs (scratch builds, the relight's run recorded, not
run) are byte for byte those of the code before, their manifests and relight commands too; two real baked Builds of
URB_Bar projects (one copy; two copies, a hidden piece and light edits), each run twice so that the second takes its
pieces from the first, give the same variant map, texture cache, manifest and relight record (timings aside) as the
code before; the bake tests of the relight, faster bake, shadow maps, native copies, lights, spawns, made walls,
transplant, light factory, shadows and bounce, lightmap encoding, clear, building edits, effects and cover blocks.

Left: `build` keeps its clone loop, made walls, buildings and floor lists in line (the plan's further seams), and
its thirty parameters.
