### What nothing used taken out of the bake and package tools

Review finding 63, the part in [tools/bake](../../tools/bake) and [tools/upk](../../tools/upk). Each was checked by a
search over the repository, its tests, the research notes and the experiment scripts.

- **No caller at all:** `relight._relight_here`, `frac_walls.section_points`, `schema.REP_OFFSET` and the empty
  `SUPPLEMENT` with its loop, `cover_blocks.KINDS`, `intro_copy.INTROS` (the intro list lives in
  [outputnames.py](../../tools/viewer/outputnames.py) and the Build's), `map_frame.FORMAT`.
- **Branches that could not run:**
  - [effects_draw.py](../../tools/viewer/effects_draw.py)'s `if True:` and the four paths behind the empty `RULES`
    table. `RULES` and `attach`'s `rules` stay, unused, because the exporter and the library still pass them.
  - [native_copy.py](../../tools/bake/native_copy.py)'s `rebuild_template` asked the walker for `Rotation`, where it
    yields `Rotation[0]`, so its filter never matched. It is gone: `add_volume` saves the clone unturned, so a turned
    template gives the same box. No map of the install has one (the review's survey).
  - [ground.py](../../tools/bake/ground.py)'s branch for a missing `ground_looks.json`, which is checked in.
  - [shell.py](../../tools/bake/shell.py)'s test of a cursor volume being among the ones placed: they are one list.
- **The unused imports** in `frac_walls`, `test_faster_bake`, `test_gen_mesh`, `audit_clear`, `check_depends`,
  `map_picture` and `world_links`.
- **Test-only code out of the product:** `native_copy.add_tiles` (its test calls `add_tiles_box` with the piece's
  box, which is what it did). `map_frame.read_picture` and `cover_blocks.breaking_digest` moved into their tests (the editor's
  Build test of the picture reads it through `map_frame.locate` itself).
  `transplant.oracle` and `cook_noise` moved into
  [test_transplant.py](../../tools/bake/tests/test_transplant.py), which is what uses them; `XCOM_TRANSPLANT_RING`
  still runs the oracle over every pair.
- **Relight's `--as-before`** (and `XCOM_RELIGHT_AS_BEFORE`) is gone: nothing passed it and no test held its promise.

Kept, because research or experiment tools use them: `buildings.survey` (its own command line, EXP-50's read-back),
`hulls.wedge`, `face_loops` and `tri_rows` (`research/evidence/hull-audit.py`), relight's `--checker` (EXP-17's
checkerboard runs), `--direct-only` and `--source-radius`, and `native_copy.py`'s manual options (`--copy`, `--actor`,
`--at`, `--yaw`, `--no-tiles`, `--jobs`).

Checked: the map-frame, cover-block, ground, relight, native-copy, transplant oracle and wall tests of the bake suite,
the upk schema tests and the viewer's effects tests pass.
