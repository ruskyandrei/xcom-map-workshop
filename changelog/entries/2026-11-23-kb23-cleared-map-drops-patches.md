### A cleared map streams none of Long War's patch levels (KB-23 fixed)

- **What changed.** A cleared project's build no longer streams the map's Long War patch levels (`patch_*`) at all,
  where before it streamed a copy of each with only the patch's pieces taken out, leaving its lights, its rebuild
  volumes and its load script to act on the new map. Every patch goes, `patch_hide_randomized_objects` included,
  with the no-spawn volumes and Meld points some carry: a cleared map is a map to build on. A mission's own streamed
  levels stay. KB-23 is out of [the bug register](../../KNOWN-BUGS.md); KB-22 (marks inside a patch's rework) now
  says a cleared map is free of it.
- **Where.**
  - [mapsini.py](../../tools/viewer/mapsini.py) `drop_patches`: a record without its patch streams, the rest in
    order, renumbered only where a gap would be left.
  - [mission_edits.py](../../tools/editor/mission_edits.py) and [compiler.py](../../tools/editor/compiler.py): a cleared
    map gives the Build `dropPatches` (through [native_edit.py](../../tools/editor/native_edit.py)) and no stream copy
    of a patch.
  - [build.py](../../tools/editor/build.py) `config_lines` takes them out of every record before the intro copies and
    the edit patch go in. The manifest says `dropPatches` and `config.droppedStreams`, and the README names them.
  - [installs.py](../../tools/viewer/installs.py) `plan_record` (a play's or a prefab test's record made from the game's
    own, and a campaign install of an older package) and the lab's test-slot install
    ([deploy_fixture.py](../../tools/bake/deploy_fixture.py), [lab_install.py](../../tools/lab/lab_install.py)) do the
    same for such a package; a map pack's manifest carries `dropPatches` ([manager.py](../../tools/viewer/manager.py)).
  - The page ([clear_map.js](../../tools/viewer/web/clear_map.js)): the Clear map window names the patch levels that
    go, and a cleared map shows none of a patch's spawn points and effects (its pieces and lights were hidden
    already).
  - The guide's Clear map section says so ([guide.html](../../tools/release/guide/guide.html)).
- **Checked.** `drop_patches` on all 187 records of an LWR install (171 changed, nothing else of a record touched, no
  gap left). New tests in test_mapsini, test_compiler, test_build (config_lines and a Build's manifest and README) and
  test_play (plan_record, build_record). The browser check `clear-map` asserts the window's words and that nothing of
  a patch is drawn after a clear, run on the Bar and the farm. The editor, viewer, lab, repo and node suites, and the
  bake suite's deploy tests.
- **Not checked.** A cleared map's battle was not played after the change. LWR's own records without a patch
  (16 of 187) play, so a record without one loads. `patch_hide_randomized_objects` hides bombs, power nodes and Meld
  containers by kind and layer, and moves some on a Second Wave option: what a Long War bomb mission on a cleared map
  does without it is not seen in the game.
