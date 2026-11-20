### A baked Build that relights nothing says "lighting unchanged" in the Build window, not "lighting not baked"

What a user saw: a baked Build of landing-zone lines alone, a spawn rule alone, the missions list or map picture alone,
or a mission's objects moved or taken out in its stream relights nothing and keeps the map's own lightmaps. The manifest said so
(`quick: false`, `lightingUnchanged: true`) and the project manager showed "baked (lighting unchanged)". The Build
window's light step said "lighting not baked", the quick Build's words, because the light stage was recorded as a quick
Build's (`baked: false`). A baked Build of cover blocks, flags or effects alone already showed "lighting unchanged: no
texel to relight".

- [build.py](../../tools/editor/build.py): `Build.edit_unbaked` takes `unchanged`. `Build.light`'s first case (nothing
  in the map changes) calls it with `unchanged=True`, and the light stage is recorded with `baked: true` and
  `lightingUnchanged: true`, as a baked Build of cover blocks alone records it, with the same counts as before. The map,
  the manifest's other fields and the other stages are as they were. A quick Build's light stage is unchanged. A stream
  move still does not relight (the mission types plan, Part E).
- Only the Build window reads the light stage's `baked`
  ([build_window.js](../../tools/viewer/web/build_window.js) `stepDetail`, unchanged): with `baked` true and
  `lightingUnchanged` it already gives the unchanged words.
- Checked:
  - [test_build.py](../../tools/editor/tests/test_build.py)
    `test_a_baked_build_that_changes_nothing_in_the_map_records_its_lighting_unchanged`: a baked Build of landing-zone
    lines alone, and one of a spawn rule alone, record the light stage as baked with the lighting unchanged and no
    cache, and run no relight; their quick Builds record a quick Build's stage. It failed before the change
    (`(False, None, None, 0, 0)` against `(True, None, True, 0, 0)`).
  - The editor suite (371 tests) and the viewer suite's `test_builds` (23) and `test_buildqueue` (24) pass.
  - The ten Builds tool ([build_outputs.py](../../tools/editor/tests/build_outputs.py)), recorded on this branch and on
    its base and compared. The one difference is `police-streams` (a capture point moved in its mission stream): its
    baked Build's light stage now has `baked: true` and `lightingUnchanged: true`. Every file of the ten inputs' quick
    and baked packages is byte for byte as before, and so is every other record.
