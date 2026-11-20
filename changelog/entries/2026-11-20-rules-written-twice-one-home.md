### The Build's rules that were written two to five times, one home each

Review finding 55, the twins with a Build side. Each rule below now lives in one place, and the others call it; what
the export writes and what the Build makes did not change.

- **Whether a piece collides:** [piece_flags.py](../../tools/viewer/piece_flags.py) `collides`, which
  [export.py](../../tools/viewer/export.py) and [native_copy.py](../../tools/bake/native_copy.py) now name in place
  of their own copies (export.py's import line alone changed).
- **The landing's actors that a clear keeps:** [scene_metadata.py](../../tools/viewer/scene_metadata.py)
  `landing_archetype` (the two prefabs by their archetype's path, case aside, and the Skyranger's dust), read by
  [effects_metadata.py](../../tools/viewer/effects_metadata.py) and native_copy's `landing_actor`; the two other
  tables are gone. [test_effects_metadata.py](../../tools/viewer/tests/test_effects_metadata.py) checks the Build
  reads the same rule and a few paths against it.
- **Which building is a van's own:** piece_flags `van_building`, read by the
  [compiler](../../tools/editor/compiler.py) (twice) and native_copy's `van_buildings`;
  [transplant.py](../../tools/bake/transplant.py) `van_volumes` asks `van_buildings` in place of its own walk.
- **The dropship intro's maps:** [outputnames.py](../../tools/viewer/outputnames.py) `INTROS`, which
  [build.py](../../tools/editor/build.py) names (intro_copy's copy went in the dead-code change).
- **The Kismet walk:** scene_metadata `kismet_walk`, the one walk `kismet_references` and `kismet_uses` read.
- **The Level's actor list:** native_copy `actor_list` (the map's own or as an edit has left it, owner checked),
  read by `level_actors`, `empty_slots`, `clear_level`, `add_to_level` and [shell.py](../../tools/bake/shell.py)
  `listed`. `clear_level` and `listed` did not check the list's owner before; they now refuse a Level that doesn't
  start its native data with its list, as the others did.
- **Setting a pose in place:** native_copy `set_pose` (Location, Rotation, RelativeLocation, or a Kismet Set
  Location's two, with or without the record of what was written and added), in place of shell's `set_location`,
  [native_effects.py](../../tools/bake/native_effects.py) `_set_pose`,
  [native_spawns.py](../../tools/bake/native_spawns.py) `_set`, [native_lights.py](../../tools/bake/native_lights.py)
  `write_pose` and the bodies of [intro_copy.py](../../tools/bake/intro_copy.py) `set_place` and
  [stream_copy.py](../../tools/bake/stream_copy.py)'s pose write.

Checked: the Kismet references and uses, the warnings, and both collides and landing rules give the same answers
before and after on five installed maps (the blank map, TempleShip, Bar, the pier stream and the police station);
quick and baked Build outputs of ten real project inputs (scratch builds, relight stubbed) are byte for byte those
of the code before; the bake tests of the native copies, effects, spawns, streams, shell, intro copy, lights, clear,
flags, buildings, sounds, flares, cover blocks and vans; the compiler tests; the viewer's effects, flags, output
names, spawns, links, tactical, destruction, streams, lights, formats, families and library tests; the editor's
Build tests.

Left: the Kismet walk still runs once for each of its two readers; the landing-zone ini offsets, the mission
summary and the installer's game kind (the finding's other twins) are outside the Build.
