### What the first round of review fixes left: malformed kinds, the Build's left-out pieces, waves, ladders, pack configs

Review findings 23, 26, 34 and 50, the parts the first round's fixes left open.

- **A kind that is a list or a record** ([missions.py](../../tools/viewer/missions.py) `valid_entry`,
  [spawns.py](../../tools/viewer/spawns.py) `valid_zone`) is no mission entry or zone, said by the checks themselves
  rather than a TypeError the compiler caught round them: [compiler.py](../../tools/editor/compiler.py) and
  [build.py](../../tools/editor/build.py) call them directly, and `compiler.valid_zone`/`valid_mission` are gone.
  [zone_cases.json](../../tools/viewer/tests/zone_cases.json), which the page's `validLandingZone` passes too, has a
  direction and a kind that are lists and a kind that is a record.
- **The Build's own left-out pieces** (untried pieces a failed copy stage named, `drop_untried`) go into the build's
  compile-report.json beside the compiler's, marked `stage: "leftout"`, with its `counts.leftOut`: the build window
  says that file has them all.
- **The Effects view's Wave preview** no longer reads the whole scene.json for every wave played:
  [audio.py](../../tools/viewer/audio.py) `WaveCache.scene` keeps what the wave route reads (name, source, stream
  names, soundWaves) for each version of the file ([viewer.py](../../tools/viewer/viewer.py)).
- **`breaksFurther` on an added copy** was noted as a field an added piece doesn't have, though the compiler reads
  it; it is a known field now, and without blasts it gets the override's note (it goes with blasts).
- **A ladder's ends** no longer count the floor of a piece the project deletes or moves (the compiler's `floor_now`,
  as its other floor checks count it); before, only a flags edit that took a floor away did that. The ladder chip
  ([app.js](../../tools/viewer/web/app.js) `ladderNow`) counts it the same.
- **A map pack's Install.cmd and Uninstall.cmd** ([pack_scripts.py](../../tools/viewer/pack_scripts.py)) write
  DefaultMaps.ini, DefaultLZMutator.ini and DefaultRandomSpawns.ini beside themselves, read the copy back and put it
  in place (File.Replace), trying again for a moment if something holds the file; a write that fails leaves the
  config byte for byte as it was, says so, and leaves no temporary file.

Checked: the editor suite (a ladder on a deleted or moved piece's floor in
[test_compiler.py](../../tools/editor/tests/test_compiler.py), an added copy's `breaksFurther` in
[test_compiler_generated.py](../../tools/editor/tests/test_compiler_generated.py), compile-report.json in
[test_build.py](../../tools/editor/tests/test_build.py)), and of the viewer suite
[test_audio.py](../../tools/viewer/tests/test_audio.py), [test_spawns.py](../../tools/viewer/tests/test_spawns.py),
`test_play` (`valid_entry`), [test_pack_scripts.py](../../tools/viewer/tests/test_pack_scripts.py) (a read-only
DefaultMaps.ini stays as it was) and the page's clear_map_test.mjs (the new zone cases).
